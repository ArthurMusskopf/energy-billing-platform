from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.clients import (
    TABLE_BOLETOS,
    TABLE_CLIENTES,
    TABLE_FATURA_ITENS,
    TABLE_FATURAS_WORKFLOW,
    TABLE_MEDIDORES,
    execute_query,
    upsert_dataframe,
)
from app.core.config import get_settings
from app.schemas.faturas import (
    FaturaCalculoResponseSchema,
    FaturaDetalheSchema,
    FaturaParseErroArquivoSchema,
    FaturaParseResumoSchema,
    FaturaValidacaoRequestSchema,
    FaturaValidacaoResponseSchema,
    FaturasListResponseSchema,
    FaturasParseResponseSchema,
)
from app.services import (
    build_workflow_from_parse_results,
    calculate_boletos,
    compute_custo_disp,
    infer_n_fases,
    processar_lote_faturas,
)

router = APIRouter(prefix="/api/v1/faturas", tags=["faturas"])
settings = get_settings()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = pd.to_numeric(value, errors="coerce")
        if pd.isna(number):
            return default
        return float(number)
    except Exception:
        return default


def _safe_int(value: Any) -> Optional[int]:
    try:
        number = pd.to_numeric(value, errors="coerce")
        if pd.isna(number):
            return None
        return int(number)
    except Exception:
        return None


def _normalize_percent(value: Any) -> float:
    number = _safe_float(value, default=0.0)
    if abs(number) <= 1:
        return number * 100
    return number


def _load_existing_workflow() -> pd.DataFrame:
    try:
        query = f"""
        SELECT *
        FROM `{TABLE_FATURAS_WORKFLOW}`
        """
        return execute_query(query)
    except Exception:
        return pd.DataFrame()


def _safe_records(df: pd.DataFrame) -> List[dict]:
    if df is None or df.empty:
        return []

    out = df.copy()

    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype(str).replace({"NaT": None})

    out = out.where(pd.notna(out), None)
    return out.to_dict(orient="records")


def _optional_query(query: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    try:
        return execute_query(query, params or {})
    except Exception:
        return pd.DataFrame()


def _get_workflow_df(fatura_id: str) -> pd.DataFrame:
    query = f"""
    SELECT *
    FROM `{TABLE_FATURAS_WORKFLOW}`
    WHERE id = @id
    LIMIT 1
    """
    df = execute_query(query, {"id": str(fatura_id)})
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="Fatura nao encontrada.")
    return df


def _get_boleto_df(fatura_id: str) -> pd.DataFrame:
    query = f"""
    SELECT *
    FROM `{TABLE_BOLETOS}`
    WHERE id = @id
    LIMIT 1
    """
    return _optional_query(query, {"id": str(fatura_id)})


def _get_itens_df(fatura_id: str) -> pd.DataFrame:
    query = f"""
    SELECT *
    FROM `{TABLE_FATURA_ITENS}`
    WHERE numero = @id
    ORDER BY codigo, descricao, id
    """
    return _optional_query(query, {"id": str(fatura_id)})


def _get_medidores_df(fatura_id: str) -> pd.DataFrame:
    query = f"""
    SELECT *
    FROM `{TABLE_MEDIDORES}`
    WHERE nota_fiscal_numero = @id
    ORDER BY medidor, tipo, posto, id
    """
    return _optional_query(query, {"id": str(fatura_id)})


def _first_non_null(df: pd.DataFrame, col: str) -> Any:
    if df is None or df.empty or col not in df.columns:
        return None
    series = df[col].dropna()
    if series.empty:
        return None
    return series.iloc[0]


def _build_alertas(observacoes: Optional[str], fatura_id: str) -> List[dict]:
    if not observacoes:
        return []

    alertas: List[dict] = []
    for idx, chunk in enumerate(str(observacoes).split("||"), start=1):
        trecho = chunk.strip()
        if not trecho:
            continue

        campo = "workflow"
        mensagem = trecho
        if ":" in trecho:
            prefixo, sufixo = trecho.split(":", 1)
            if prefixo.strip():
                campo = prefixo.strip()
            if sufixo.strip():
                mensagem = sufixo.strip()

        alertas.append(
            {
                "id": f"{fatura_id}-alerta-{idx}",
                "campo": campo,
                "tipo": "error" if "erro" in trecho.lower() else "warning",
                "mensagem": mensagem,
                "valor_atual": 0,
                "valor_esperado": 0,
                "desvio_percentual": 0,
            }
        )

    return alertas


def _persist_parse_outputs(
    lote: Dict[str, Any],
    workflow_df: pd.DataFrame,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for name, df, table in [
        ("workflow", workflow_df, TABLE_FATURAS_WORKFLOW),
        ("itens", lote.get("df_itens"), TABLE_FATURA_ITENS),
        ("medidores", lote.get("df_medidores"), TABLE_MEDIDORES),
    ]:
        if df is None or df.empty:
            result[name] = {
                "ok": True,
                "table": table,
                "affected_rows": 0,
            }
            continue

        try:
            affected = upsert_dataframe(df, table, key_column="id")
            result[name] = {
                "ok": True,
                "table": table,
                "affected_rows": int(affected),
            }
        except Exception as exc:
            result[name] = {
                "ok": False,
                "table": table,
                "affected_rows": 0,
                "error": str(exc),
            }

    return result


def _build_fatura_detail_payload(
    workflow_df: pd.DataFrame,
    itens_df: pd.DataFrame,
    medidores_df: pd.DataFrame,
) -> dict:
    workflow = _safe_records(workflow_df)[0]
    fatura_id = str(workflow.get("id"))

    detalhe = dict(workflow)
    detalhe.update(
        {
            "leitura_anterior": _safe_str(_first_non_null(itens_df, "leitura_anterior")),
            "leitura_atual": _safe_str(_first_non_null(itens_df, "leitura_atual")),
            "dias": _safe_int(_first_non_null(itens_df, "dias")),
            "proxima_leitura": _safe_str(_first_non_null(itens_df, "proxima_leitura")),
            "nota_fiscal_serie": _safe_str(_first_non_null(itens_df, "serie")),
            "nota_fiscal_emissao": _safe_str(_first_non_null(itens_df, "data_emissao")),
            "cidade_uf": _safe_str(_first_non_null(itens_df, "cidade_uf")),
            "cep": _safe_str(_first_non_null(itens_df, "cep")),
            "itens": _safe_records(itens_df),
            "medidores": _safe_records(medidores_df),
            "alertas": _build_alertas(_safe_str(workflow.get("observacoes")), fatura_id),
        }
    )
    return detalhe


def _build_client_df_for_calc(workflow_row: pd.Series) -> tuple[pd.DataFrame, Dict[str, str]]:
    uc = _safe_str(workflow_row.get("unidade_consumidora")) or ""
    warnings: Dict[str, str] = {}

    if uc:
        query = f"""
        SELECT *
        FROM `{TABLE_CLIENTES}`
        WHERE unidade_consumidora = @uc
        LIMIT 1
        """
        client_df = _optional_query(query, {"uc": uc})
    else:
        client_df = pd.DataFrame()

    if client_df is None or client_df.empty:
        warnings[uc or "sem_uc"] = "Cliente nao encontrado em info_clientes; calculo usou defaults."
        client_df = pd.DataFrame(
            [
                {
                    "unidade_consumidora": uc,
                    "cliente_numero": _safe_str(workflow_row.get("cliente_numero")),
                    "nome": _safe_str(workflow_row.get("nome")),
                    "cnpj_cpf": _safe_str(workflow_row.get("cnpj_cpf")),
                    "cep": None,
                    "cidade_uf": None,
                    "desconto_contratado": 0.0,
                    "subvencao": 0.0,
                    "status": "Ativo",
                }
            ]
        )

    client_df = client_df.copy()

    if "status" not in client_df.columns:
        client_df["status"] = "Ativo"
    client_df["status"] = client_df["status"].fillna("Ativo")

    if "desconto_contratado" not in client_df.columns:
        client_df["desconto_contratado"] = 0.0
    client_df["desconto_contratado"] = pd.to_numeric(
        client_df["desconto_contratado"], errors="coerce"
    ).fillna(0.0)

    if "subvencao" not in client_df.columns:
        client_df["subvencao"] = 0.0
    client_df["subvencao"] = pd.to_numeric(client_df["subvencao"], errors="coerce").fillna(0.0)

    classe_modalidade = _safe_str(workflow_row.get("classe_modalidade"))
    inferred_n_fases = infer_n_fases(classe_modalidade)
    inferred_custo_disp = compute_custo_disp(inferred_n_fases)

    if "n_fases" not in client_df.columns:
        client_df["n_fases"] = inferred_n_fases
    else:
        client_df["n_fases"] = pd.to_numeric(client_df["n_fases"], errors="coerce")
        if inferred_n_fases is not None:
            client_df["n_fases"] = client_df["n_fases"].fillna(inferred_n_fases)

    if "custo_disp" not in client_df.columns:
        client_df["custo_disp"] = inferred_custo_disp
    else:
        client_df["custo_disp"] = pd.to_numeric(client_df["custo_disp"], errors="coerce")
        if inferred_custo_disp is not None:
            client_df["custo_disp"] = client_df["custo_disp"].fillna(inferred_custo_disp)

    return client_df, warnings


def _sum_item_quantity(itens_df: pd.DataFrame, codigos: set[str]) -> float:
    if itens_df is None or itens_df.empty or "codigo" not in itens_df.columns:
        return 0.0

    data = itens_df.copy()
    data["codigo"] = data["codigo"].astype(str)
    if "quantidade_registrada" not in data.columns:
        return 0.0

    data["quantidade_registrada"] = pd.to_numeric(data["quantidade_registrada"], errors="coerce")
    filtered = data[data["codigo"].isin(codigos)]
    if filtered.empty:
        return 0.0

    grouped = filtered.groupby("codigo")["quantidade_registrada"].sum(min_count=1).abs()
    if grouped.empty:
        return 0.0

    return float(grouped.max())


def _append_observacao(observacoes_atual: Any, nova: str) -> str:
    atual = _safe_str(observacoes_atual)
    if not atual:
        return nova
    if nova in atual:
        return atual
    return f"{atual} || {nova}"


def _update_workflow_row(fatura_id: str, updates: Dict[str, Any]) -> dict:
    workflow_df = _get_workflow_df(fatura_id)
    updated_df = workflow_df.copy()
    now = _now_utc()

    for key, value in updates.items():
        updated_df.loc[:, key] = value

    updated_df.loc[:, "updated_at"] = now
    upsert_dataframe(updated_df, TABLE_FATURAS_WORKFLOW, key_column="id")

    return _safe_records(updated_df)[0]


def _build_boleto_calc_row(
    workflow_row: pd.Series,
    itens_df: pd.DataFrame,
    calc_df: pd.DataFrame,
    existing_boleto_df: pd.DataFrame,
) -> pd.DataFrame:
    calc_row = calc_df.iloc[0].to_dict()
    created_at = _first_non_null(existing_boleto_df, "created_at") if existing_boleto_df is not None else None
    now = _now_utc()

    energia_compensada = _safe_float(calc_row.get("med_inj_tusd"), default=0.0)
    if energia_compensada == 0:
        energia_compensada = _safe_float(calc_row.get("injetada"), default=0.0)
    if energia_compensada == 0:
        energia_compensada = _sum_item_quantity(itens_df, {"0R", "0S"})

    valor_final = _safe_float(calc_row.get("valor_total_boleto"), default=0.0)
    valor_concessionaria = _safe_float(
        workflow_row.get("total_pagar"),
        default=_safe_float(_first_non_null(itens_df, "total_pagar"), default=0.0),
    )

    valor_bandeiras_desc = _safe_float(calc_row.get("valor_band_amar_desc")) + _safe_float(
        calc_row.get("valor_band_vrm_desc")
    )
    valor_bandeiras_total = abs(valor_bandeiras_desc * energia_compensada)

    payload = dict(calc_row)
    payload.update(
        {
            "id": _safe_str(workflow_row.get("id")),
            "workflow_id": _safe_str(workflow_row.get("id")),
            "nota_fiscal": _safe_str(workflow_row.get("id")),
            "periodo": _safe_str(workflow_row.get("referencia")),
            "nome": _safe_str(workflow_row.get("nome")),
            "vencimento": _safe_str(workflow_row.get("vencimento")),
            "cliente_numero": _safe_str(workflow_row.get("cliente_numero")),
            "unidade_consumidora": _safe_str(workflow_row.get("unidade_consumidora")),
            "cnpj_cpf": _safe_str(workflow_row.get("cnpj_cpf")),
            "cep": _safe_str(_first_non_null(itens_df, "cep")),
            "cidade_uf": _safe_str(_first_non_null(itens_df, "cidade_uf")),
            "consumo_kwh": _sum_item_quantity(itens_df, {"0D", "0E"}),
            "injetada_kwh": energia_compensada,
            "tarifa_injetada": _safe_float(calc_row.get("tarifa_bol")),
            "tarifa_liquida": _safe_float(calc_row.get("tarifa_total_boleto")),
            "valor_erb": valor_final,
            "valor_final": valor_final,
            "valor_concessionaria": valor_concessionaria,
            "valor_bandeiras": valor_bandeiras_total,
            "energia_inj_tusd": _safe_float(calc_row.get("energia_inj_tusd_tarifa")),
            "energia_injet_te": _safe_float(calc_row.get("energia_injet_te_tarifa")),
            "created_at": created_at or now,
            "updated_at": now,
        }
    )

    return pd.DataFrame([payload])


@router.get("", response_model=FaturasListResponseSchema)
def list_faturas(
    q: Optional[str] = Query(default=None),
    status_parse: Optional[str] = Query(default=None),
    status_validacao: Optional[str] = Query(default=None),
    status_calculo: Optional[str] = Query(default=None),
    status_emissao: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    where_parts = ["1=1"]
    params = {"limit": int(limit), "offset": int(offset)}

    if q:
        where_parts.append(
            """
            (
              CAST(id AS STRING) LIKE CONCAT('%', @q, '%')
              OR CAST(nota_fiscal AS STRING) LIKE CONCAT('%', @q, '%')
              OR CAST(unidade_consumidora AS STRING) LIKE CONCAT('%', @q, '%')
              OR CAST(cliente_numero AS STRING) LIKE CONCAT('%', @q, '%')
              OR LOWER(COALESCE(nome, '')) LIKE LOWER(CONCAT('%', @q, '%'))
            )
            """
        )
        params["q"] = str(q)

    if status_parse:
        where_parts.append("status_parse = @status_parse")
        params["status_parse"] = str(status_parse)

    if status_validacao:
        where_parts.append("status_validacao = @status_validacao")
        params["status_validacao"] = str(status_validacao)

    if status_calculo:
        where_parts.append("status_calculo = @status_calculo")
        params["status_calculo"] = str(status_calculo)

    if status_emissao:
        where_parts.append("status_emissao = @status_emissao")
        params["status_emissao"] = str(status_emissao)

    where_sql = " AND ".join(where_parts)

    query_items = f"""
    SELECT
      id,
      nota_fiscal,
      unidade_consumidora,
      cliente_numero,
      nome,
      cnpj_cpf,
      referencia,
      vencimento,
      classe_modalidade,
      grupo_subgrupo_tensao,
      total_pagar,
      arquivo_nome_original,
      arquivo_hash,
      pdf_uri,
      is_inedita,
      duplicada_de,
      status_parse,
      status_validacao,
      validado_por,
      validado_em,
      status_calculo,
      calculado_em,
      status_emissao,
      emitido_em,
      observacoes,
      created_at,
      updated_at
    FROM `{TABLE_FATURAS_WORKFLOW}`
    WHERE {where_sql}
    ORDER BY updated_at DESC, created_at DESC, id DESC
    LIMIT @limit
    OFFSET @offset
    """

    query_total = f"""
    SELECT COUNT(1) AS total
    FROM `{TABLE_FATURAS_WORKFLOW}`
    WHERE {where_sql}
    """

    try:
        df_items = execute_query(query_items, params)
        df_total = execute_query(
            query_total,
            {k: v for k, v in params.items() if k not in ("limit", "offset")},
        )

        total = 0
        if df_total is not None and not df_total.empty and "total" in df_total.columns:
            total = int(df_total.iloc[0]["total"])

        return {
            "items": _safe_records(df_items),
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao listar faturas: {exc}")


@router.get("/{fatura_id}", response_model=FaturaDetalheSchema)
def get_fatura_detail(fatura_id: str):
    try:
        workflow_df = _get_workflow_df(fatura_id)
        itens_df = _get_itens_df(fatura_id)
        medidores_df = _get_medidores_df(fatura_id)
        return _build_fatura_detail_payload(workflow_df, itens_df, medidores_df)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar detalhe da fatura: {exc}")


@router.patch("/{fatura_id}/validar", response_model=FaturaValidacaoResponseSchema)
def validar_fatura(
    fatura_id: str,
    payload: Optional[FaturaValidacaoRequestSchema] = None,
):
    usuario = (payload.usuario if payload else None) or "frontend"
    now = _now_utc()

    try:
        updated = _update_workflow_row(
            fatura_id,
            {
                "status_validacao": "validado",
                "validado_por": usuario,
                "validado_em": now,
            },
        )
        return {
            "id": updated["id"],
            "status_validacao": updated.get("status_validacao") or "validado",
            "validado_por": updated.get("validado_por"),
            "validado_em": updated.get("validado_em"),
            "updated_at": updated.get("updated_at"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao validar fatura: {exc}")


@router.post("/{fatura_id}/calcular", response_model=FaturaCalculoResponseSchema)
def calcular_fatura(fatura_id: str):
    try:
        workflow_df = _get_workflow_df(fatura_id)
        workflow_row = workflow_df.iloc[0]

        if _safe_str(workflow_row.get("status_parse")) == "erro_parse":
            raise HTTPException(
                status_code=400,
                detail="Nao e possivel calcular uma fatura com erro de parse.",
            )

        itens_df = _get_itens_df(fatura_id)
        medidores_df = _get_medidores_df(fatura_id)

        if itens_df is None or itens_df.empty:
            raise HTTPException(status_code=400, detail="A fatura nao possui itens parseados para calculo.")

        if medidores_df is None or medidores_df.empty:
            raise HTTPException(status_code=400, detail="A fatura nao possui medidores parseados para calculo.")

        client_df, warnings = _build_client_df_for_calc(workflow_row)
        calc_result = calculate_boletos(
            itens_df,
            medidores_df,
            client_df,
            only_registered_clients=False,
            only_status_ativo=False,
        )

        boleto_df = calc_result.df_boletos.copy()
        if boleto_df is None or boleto_df.empty:
            detail = "Nao houve linhas elegiveis para calculo."
            updated = _update_workflow_row(
                fatura_id,
                {
                    "status_calculo": "erro_calculo",
                    "calculado_em": _now_utc(),
                    "observacoes": _append_observacao(workflow_row.get("observacoes"), detail),
                },
            )
            return {
                "id": updated["id"],
                "status_calculo": updated.get("status_calculo") or "erro_calculo",
                "calculado_em": updated.get("calculado_em"),
                "table": TABLE_BOLETOS,
                "affected_rows": 0,
                "missing_clientes": calc_result.missing_clientes,
                "missing_reason": {**calc_result.missing_reason, **warnings},
                "detail": detail,
            }

        boleto_df = boleto_df[boleto_df["numero"].astype(str) == str(fatura_id)].copy()
        if boleto_df.empty:
            boleto_df = calc_result.df_boletos.head(1).copy()

        existing_boleto_df = _get_boleto_df(fatura_id)
        persist_df = _build_boleto_calc_row(workflow_row, itens_df, boleto_df, existing_boleto_df)
        affected = upsert_dataframe(persist_df, TABLE_BOLETOS, key_column="id")

        warning_msg = " | ".join(warnings.values()) if warnings else None
        observacoes = workflow_row.get("observacoes")
        if warning_msg:
            observacoes = _append_observacao(observacoes, warning_msg)

        updated = _update_workflow_row(
            fatura_id,
            {
                "status_calculo": "calculado",
                "calculado_em": _now_utc(),
                "observacoes": observacoes,
            },
        )

        return {
            "id": updated["id"],
            "status_calculo": updated.get("status_calculo") or "calculado",
            "calculado_em": updated.get("calculado_em"),
            "table": TABLE_BOLETOS,
            "affected_rows": int(affected),
            "missing_clientes": calc_result.missing_clientes,
            "missing_reason": {**calc_result.missing_reason, **warnings},
            "detail": "Calculo persistido sem emissao Sicoob.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao calcular fatura: {exc}")


@router.post("/parse", response_model=FaturasParseResponseSchema)
async def parse_faturas(files: List[UploadFile] = File(...)) -> FaturasParseResponseSchema:
    if not files:
        raise HTTPException(status_code=400, detail="Nenhum arquivo enviado.")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: List[str] = []
    arquivo_hash_by_name: dict[str, str] = {}
    pdf_uri_by_name: dict[str, str] = {}

    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Arquivo sem nome.")
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Arquivo invalido: {file.filename}. Envie apenas PDFs.",
            )

        dest = upload_dir / file.filename
        content = await file.read()
        dest.write_bytes(content)

        saved_paths.append(str(dest))
        arquivo_hash_by_name[file.filename] = _sha256_file(dest)
        pdf_uri_by_name[file.filename] = str(dest)

    lote = processar_lote_faturas(saved_paths)
    resultados = lote.get("resultados", [])

    existing_workflow_df = _load_existing_workflow()

    workflow_df = build_workflow_from_parse_results(
        resultados,
        existing_workflow_df=existing_workflow_df,
        arquivo_hash_by_name=arquivo_hash_by_name,
        pdf_uri_by_name=pdf_uri_by_name,
    )

    persist_result = _persist_parse_outputs(lote, workflow_df)
    salvar_auto_executado = all(
        entry.get("ok", False) for entry in persist_result.values()
    )

    total_nf = int(len(workflow_df)) if workflow_df is not None else 0
    ineditas = (
        int(pd.to_numeric(workflow_df["is_inedita"], errors="coerce").fillna(0).astype(bool).sum())
        if workflow_df is not None and not workflow_df.empty and "is_inedita" in workflow_df.columns
        else 0
    )
    repetidas = max(total_nf - ineditas, 0)

    parseadas = (
        int((workflow_df["status_parse"] == "parseado").sum())
        if workflow_df is not None and not workflow_df.empty and "status_parse" in workflow_df.columns
        else 0
    )
    erro_parse = (
        int((workflow_df["status_parse"] == "erro_parse").sum())
        if workflow_df is not None and not workflow_df.empty and "status_parse" in workflow_df.columns
        else 0
    )

    arquivos_com_erro = [
        FaturaParseErroArquivoSchema(
            arquivo=r.arquivo,
            erros=list(r.erros or []),
        )
        for r in resultados
        if not r.sucesso
    ]

    return FaturasParseResponseSchema(
        total_arquivos=len(files),
        parseadas_com_sucesso=int(lote.get("sucesso", 0)),
        erros_parse=int(lote.get("erros", 0)),
        resumo=FaturaParseResumoSchema(
            total_nf=total_nf,
            ineditas=ineditas,
            repetidas=repetidas,
            parseadas=parseadas,
            erro_parse=erro_parse,
        ),
        arquivos_com_erro=arquivos_com_erro,
        workflow=_safe_records(workflow_df),
        salvar_auto_executado=salvar_auto_executado,
        bigquery_result=persist_result,
    )
