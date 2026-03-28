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
    FaturaRevisaoRequestSchema,
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

CADASTRO_REQUIRED_FIELDS = {
    "unidade_consumidora": "UC",
    "cliente_numero": "codigo_cliente",
    "nome": "nome",
    "cnpj_cpf": "cnpj_cpf",
    "cep": "cep",
    "cidade_uf": "cidade_uf",
    "desconto_contratado": "desconto_contratado",
    "subvencao": "subvencao",
    "status": "status",
    "custo_disp": "custo_disp",
}

WORKFLOW_PROPAGATION_FIELDS = {
    "unidade_consumidora": "unidade_consumidora",
    "cliente_numero": "cliente_numero",
    "nome": "nome",
    "cnpj_cpf": "cnpj_cpf",
    "referencia": "referencia",
    "vencimento": "vencimento",
    "leitura_anterior": "leitura_anterior",
    "leitura_atual": "leitura_atual",
    "dias": "dias",
    "proxima_leitura": "proxima_leitura",
    "cep": "cep",
    "cidade_uf": "cidade_uf",
}

ITEMS_PROPAGATION_FIELDS = {
    "unidade_consumidora": "unidade_consumidora",
    "cliente_numero": "cliente_numero",
    "nome": "nome",
    "cnpj_cpf": "cnpj",
    "referencia": "referencia",
    "vencimento": "vencimento",
    "leitura_anterior": "leitura_anterior",
    "leitura_atual": "leitura_atual",
    "dias": "dias",
    "proxima_leitura": "proxima_leitura",
    "cep": "cep",
    "cidade_uf": "cidade_uf",
}

MEDIDORES_PROPAGATION_FIELDS = {
    "unidade_consumidora": "unidade_consumidora",
    "cliente_numero": "cliente_numero",
    "nome": "nome",
    "referencia": "referencia",
}


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


def _safe_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
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
    if number is None:
        return 0.0
    if abs(number) <= 1:
        return number * 100
    return number


def _normalize_discount_fraction(value: Any) -> Optional[float]:
    number = _safe_float(value, default=None)
    if number is None:
        return None
    if abs(number) > 1:
        return number / 100.0
    return number


def _normalize_status(value: Any) -> Optional[str]:
    status = _safe_str(value)
    if not status:
        return None
    if status.lower() == "ativo":
        return "Ativo"
    if status.lower() == "inativo":
        return "Inativo"
    return status


def _coalesce_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


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
    client_df: pd.DataFrame,
) -> dict:
    workflow = _safe_records(workflow_df)[0]
    workflow_row = workflow_df.iloc[0]
    fatura_id = str(workflow.get("id"))
    cadastro_cliente = _build_cadastro_cliente_payload(workflow_row, itens_df, client_df)

    detalhe = dict(workflow)
    detalhe.update(
        {
            "leitura_anterior": _safe_str(
                _coalesce_value(workflow.get("leitura_anterior"), _first_non_null(itens_df, "leitura_anterior"))
            ),
            "leitura_atual": _safe_str(
                _coalesce_value(workflow.get("leitura_atual"), _first_non_null(itens_df, "leitura_atual"))
            ),
            "dias": _safe_int(_coalesce_value(workflow.get("dias"), _first_non_null(itens_df, "dias"))),
            "proxima_leitura": _safe_str(
                _coalesce_value(workflow.get("proxima_leitura"), _first_non_null(itens_df, "proxima_leitura"))
            ),
            "nota_fiscal_serie": _safe_str(
                _coalesce_value(workflow.get("nota_fiscal_serie"), _first_non_null(itens_df, "serie"))
            ),
            "nota_fiscal_emissao": _safe_str(
                _coalesce_value(workflow.get("nota_fiscal_emissao"), _first_non_null(itens_df, "data_emissao"))
            ),
            "cidade_uf": _safe_str(_coalesce_value(workflow.get("cidade_uf"), _first_non_null(itens_df, "cidade_uf"))),
            "cep": _safe_str(_coalesce_value(workflow.get("cep"), _first_non_null(itens_df, "cep"))),
            "itens": _safe_records(itens_df),
            "medidores": _safe_records(medidores_df),
            "alertas": _build_alertas(_safe_str(workflow.get("observacoes")), fatura_id),
            "cadastro_cliente": cadastro_cliente,
            "campos_pendentes_cadastro": cadastro_cliente.get("campos_pendentes", []),
            "pode_validar_calcular": bool(
                cadastro_cliente.get("elegivel_para_calculo")
                and _safe_str(workflow.get("status_parse")) != "erro_parse"
                and itens_df is not None
                and not itens_df.empty
                and medidores_df is not None
                and not medidores_df.empty
            ),
        }
    )
    return detalhe


def _get_client_df(
    workflow_row: pd.Series,
    *,
    uc: Optional[str] = None,
    cliente_numero: Optional[str] = None,
) -> pd.DataFrame:
    uc_value = _safe_str(uc) or _safe_str(workflow_row.get("unidade_consumidora"))
    if uc_value:
        query = f"""
        SELECT *
        FROM `{TABLE_CLIENTES}`
        WHERE unidade_consumidora = @uc
        LIMIT 1
        """
        client_df = _optional_query(query, {"uc": uc_value})
        if client_df is not None and not client_df.empty:
            return client_df

    cliente_value = _safe_str(cliente_numero) or _safe_str(workflow_row.get("cliente_numero"))
    if cliente_value:
        query = f"""
        SELECT *
        FROM `{TABLE_CLIENTES}`
        WHERE cliente_numero = @cliente_numero
        LIMIT 1
        """
        client_df = _optional_query(query, {"cliente_numero": cliente_value})
        if client_df is not None and not client_df.empty:
            return client_df

    return pd.DataFrame()


def _build_cadastro_cliente_payload(
    workflow_row: pd.Series,
    itens_df: pd.DataFrame,
    client_df: pd.DataFrame,
) -> dict:
    client_row = _safe_records(client_df)[0] if client_df is not None and not client_df.empty else {}

    n_fases = _safe_int(
        _coalesce_value(
            client_row.get("n_fases"),
            workflow_row.get("n_fases"),
            infer_n_fases(_safe_str(workflow_row.get("classe_modalidade"))),
        )
    )
    custo_disp = _safe_float(
        _coalesce_value(
            client_row.get("custo_disp"),
            workflow_row.get("custo_disp"),
            compute_custo_disp(n_fases),
        ),
        default=None,
    )

    cadastro = {
        "unidade_consumidora": _safe_str(
            _coalesce_value(
                client_row.get("unidade_consumidora"),
                workflow_row.get("unidade_consumidora"),
                _first_non_null(itens_df, "unidade_consumidora"),
            )
        ),
        "cliente_numero": _safe_str(
            _coalesce_value(
                client_row.get("cliente_numero"),
                workflow_row.get("cliente_numero"),
                _first_non_null(itens_df, "cliente_numero"),
            )
        ),
        "nome": _safe_str(
            _coalesce_value(
                client_row.get("nome"),
                workflow_row.get("nome"),
                _first_non_null(itens_df, "nome"),
            )
        ),
        "cnpj_cpf": _safe_str(
            _coalesce_value(
                client_row.get("cnpj_cpf"),
                client_row.get("cnpj"),
                workflow_row.get("cnpj_cpf"),
                _first_non_null(itens_df, "cnpj"),
                _first_non_null(itens_df, "cnpj_cpf"),
            )
        ),
        "cep": _safe_str(
            _coalesce_value(
                client_row.get("cep"),
                workflow_row.get("cep"),
                _first_non_null(itens_df, "cep"),
            )
        ),
        "cidade_uf": _safe_str(
            _coalesce_value(
                client_row.get("cidade_uf"),
                workflow_row.get("cidade_uf"),
                _first_non_null(itens_df, "cidade_uf"),
            )
        ),
        "desconto_contratado": _normalize_discount_fraction(client_row.get("desconto_contratado")),
        "subvencao": _safe_float(client_row.get("subvencao"), default=None),
        "status": _normalize_status(client_row.get("status")),
        "n_fases": n_fases,
        "custo_disp": custo_disp,
        "origem": "info_clientes" if client_row else "parse",
    }

    campos_pendentes: List[str] = []
    for field_name in CADASTRO_REQUIRED_FIELDS:
        value = cadastro.get(field_name)
        if field_name in {"desconto_contratado", "subvencao", "custo_disp"}:
            if value is None:
                campos_pendentes.append(field_name)
            continue

        if not _safe_str(value):
            campos_pendentes.append(field_name)

    cadastro["campos_pendentes"] = campos_pendentes
    cadastro["cadastro_minimo_completo"] = len(campos_pendentes) == 0
    cadastro["elegivel_para_calculo"] = bool(
        cadastro["cadastro_minimo_completo"] and cadastro.get("status") == "Ativo"
    )
    return cadastro


def _ensure_fatura_ready_for_calc(
    workflow_row: pd.Series,
    itens_df: pd.DataFrame,
    medidores_df: pd.DataFrame,
    cadastro_cliente: dict,
) -> None:
    if _safe_str(workflow_row.get("status_parse")) == "erro_parse":
        raise HTTPException(
            status_code=400,
            detail="Nao e possivel calcular uma fatura com erro de parse.",
        )

    if itens_df is None or itens_df.empty:
        raise HTTPException(status_code=400, detail="A fatura nao possui itens parseados para calculo.")

    if medidores_df is None or medidores_df.empty:
        raise HTTPException(status_code=400, detail="A fatura nao possui medidores parseados para calculo.")

    campos_pendentes = cadastro_cliente.get("campos_pendentes", [])
    if campos_pendentes:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Cadastro minimo incompleto para calcular a fatura.",
                "fields": campos_pendentes,
            },
        )

    if cadastro_cliente.get("status") != "Ativo":
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Cliente/UC sem status elegivel para calculo.",
                "fields": ["status"],
            },
        )


def _build_client_df_for_calc(
    workflow_row: pd.Series,
    itens_df: pd.DataFrame,
    medidores_df: pd.DataFrame,
) -> pd.DataFrame:
    client_df = _get_client_df(workflow_row)
    cadastro_cliente = _build_cadastro_cliente_payload(workflow_row, itens_df, client_df)
    _ensure_fatura_ready_for_calc(workflow_row, itens_df, medidores_df, cadastro_cliente)

    base_df = client_df.head(1).copy() if client_df is not None and not client_df.empty else pd.DataFrame([{}])
    payload = {
        "unidade_consumidora": cadastro_cliente.get("unidade_consumidora"),
        "cliente_numero": cadastro_cliente.get("cliente_numero"),
        "nome": cadastro_cliente.get("nome"),
        "cnpj_cpf": cadastro_cliente.get("cnpj_cpf"),
        "cep": cadastro_cliente.get("cep"),
        "cidade_uf": cadastro_cliente.get("cidade_uf"),
        "desconto_contratado": cadastro_cliente.get("desconto_contratado"),
        "subvencao": cadastro_cliente.get("subvencao"),
        "status": cadastro_cliente.get("status"),
        "n_fases": cadastro_cliente.get("n_fases"),
        "custo_disp": cadastro_cliente.get("custo_disp"),
    }

    for key, value in payload.items():
        base_df.loc[:, key] = value

    return base_df


def _apply_updates_to_df(
    df: pd.DataFrame,
    field_map: Dict[str, str],
    updates: Dict[str, Any],
) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    updated_df = df.copy()
    for source_field, dest_field in field_map.items():
        if source_field not in updates:
            continue
        updated_df.loc[:, dest_field] = updates[source_field]

    return updated_df


def _persist_cliente_from_review(
    workflow_row: pd.Series,
    itens_df: pd.DataFrame,
    review_payload: FaturaRevisaoRequestSchema,
) -> None:
    nested = review_payload.cadastro_cliente
    merged_payload = {
        "unidade_consumidora": nested.unidade_consumidora if nested and nested.unidade_consumidora is not None else review_payload.unidade_consumidora,
        "cliente_numero": nested.cliente_numero if nested and nested.cliente_numero is not None else review_payload.cliente_numero,
        "nome": nested.nome if nested and nested.nome is not None else review_payload.nome,
        "cnpj_cpf": nested.cnpj_cpf if nested and nested.cnpj_cpf is not None else review_payload.cnpj_cpf,
        "cep": nested.cep if nested and nested.cep is not None else review_payload.cep,
        "cidade_uf": nested.cidade_uf if nested and nested.cidade_uf is not None else review_payload.cidade_uf,
        "desconto_contratado": nested.desconto_contratado if nested else None,
        "subvencao": nested.subvencao if nested else None,
        "status": nested.status if nested else None,
        "n_fases": nested.n_fases if nested else None,
        "custo_disp": nested.custo_disp if nested else None,
    }

    client_df = _get_client_df(
        workflow_row,
        uc=_safe_str(merged_payload.get("unidade_consumidora")),
        cliente_numero=_safe_str(merged_payload.get("cliente_numero")),
    )
    cadastro_cliente = _build_cadastro_cliente_payload(workflow_row, itens_df, client_df)

    for key, value in merged_payload.items():
        if value is None:
            continue
        if key == "desconto_contratado":
            cadastro_cliente[key] = _normalize_discount_fraction(value)
        elif key == "subvencao":
            cadastro_cliente[key] = _safe_float(value, default=None)
        elif key == "status":
            cadastro_cliente[key] = _normalize_status(value)
        elif key == "n_fases":
            cadastro_cliente[key] = _safe_int(value)
        elif key == "custo_disp":
            cadastro_cliente[key] = _safe_float(value, default=None)
        else:
            cadastro_cliente[key] = _safe_str(value)

    if cadastro_cliente.get("n_fases") is None:
        cadastro_cliente["n_fases"] = infer_n_fases(_safe_str(workflow_row.get("classe_modalidade")))

    if cadastro_cliente.get("custo_disp") is None:
        cadastro_cliente["custo_disp"] = compute_custo_disp(_safe_int(cadastro_cliente.get("n_fases")))

    if not _safe_str(cadastro_cliente.get("unidade_consumidora")):
        return

    client_payload = {
        "unidade_consumidora": cadastro_cliente.get("unidade_consumidora"),
        "cliente_numero": cadastro_cliente.get("cliente_numero"),
        "nome": cadastro_cliente.get("nome"),
        "cnpj_cpf": cadastro_cliente.get("cnpj_cpf"),
        "cep": cadastro_cliente.get("cep"),
        "cidade_uf": cadastro_cliente.get("cidade_uf"),
        "desconto_contratado": cadastro_cliente.get("desconto_contratado"),
        "subvencao": cadastro_cliente.get("subvencao"),
        "status": cadastro_cliente.get("status"),
        "n_fases": cadastro_cliente.get("n_fases"),
        "custo_disp": cadastro_cliente.get("custo_disp"),
        "updated_at": _now_utc(),
    }

    upsert_dataframe(pd.DataFrame([client_payload]), TABLE_CLIENTES, key_column="unidade_consumidora")


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
            "cep": _safe_str(_coalesce_value(workflow_row.get("cep"), _first_non_null(itens_df, "cep"))),
            "cidade_uf": _safe_str(
                _coalesce_value(workflow_row.get("cidade_uf"), _first_non_null(itens_df, "cidade_uf"))
            ),
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


def _load_fatura_context(fatura_id: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    workflow_df = _get_workflow_df(fatura_id)
    workflow_row = workflow_df.iloc[0]
    itens_df = _get_itens_df(fatura_id)
    medidores_df = _get_medidores_df(fatura_id)
    client_df = _get_client_df(workflow_row)
    return workflow_df, itens_df, medidores_df, client_df


def _mark_fatura_validada(fatura_id: str, usuario: str) -> dict:
    return _update_workflow_row(
        fatura_id,
        {
            "status_validacao": "validado",
            "validado_por": usuario,
            "validado_em": _now_utc(),
        },
    )


def _calculate_fatura_impl(fatura_id: str, usuario_validacao: Optional[str] = None) -> dict:
    workflow_df = _get_workflow_df(fatura_id)
    workflow_row = workflow_df.iloc[0]
    itens_df = _get_itens_df(fatura_id)
    medidores_df = _get_medidores_df(fatura_id)

    client_df = _build_client_df_for_calc(workflow_row, itens_df, medidores_df)
    calc_result = calculate_boletos(
        itens_df,
        medidores_df,
        client_df,
        only_registered_clients=True,
        only_status_ativo=True,
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
            "missing_reason": calc_result.missing_reason,
            "detail": detail,
        }

    boleto_df = boleto_df[boleto_df["numero"].astype(str) == str(fatura_id)].copy()
    if boleto_df.empty:
        boleto_df = calc_result.df_boletos.head(1).copy()

    existing_boleto_df = _get_boleto_df(fatura_id)
    persist_df = _build_boleto_calc_row(workflow_row, itens_df, boleto_df, existing_boleto_df)
    affected = upsert_dataframe(persist_df, TABLE_BOLETOS, key_column="id")

    update_payload = {
        "status_calculo": "calculado",
        "calculado_em": _now_utc(),
    }
    if _safe_str(workflow_row.get("status_validacao")) != "validado":
        update_payload.update(
            {
                "status_validacao": "validado",
                "validado_por": usuario_validacao or _safe_str(workflow_row.get("validado_por")) or "calculo",
                "validado_em": _coalesce_value(workflow_row.get("validado_em"), _now_utc()),
            }
        )

    updated = _update_workflow_row(fatura_id, update_payload)

    return {
        "id": updated["id"],
        "status_calculo": updated.get("status_calculo") or "calculado",
        "calculado_em": updated.get("calculado_em"),
        "table": TABLE_BOLETOS,
        "affected_rows": int(affected),
        "missing_clientes": calc_result.missing_clientes,
        "missing_reason": calc_result.missing_reason,
        "detail": "Calculo persistido sem emissao Sicoob.",
    }


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
      leitura_anterior,
      leitura_atual,
      dias,
      proxima_leitura,
      nota_fiscal_serie,
      nota_fiscal_emissao,
      cidade_uf,
      cep,
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
        workflow_df, itens_df, medidores_df, client_df = _load_fatura_context(fatura_id)
        return _build_fatura_detail_payload(workflow_df, itens_df, medidores_df, client_df)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar detalhe da fatura: {exc}")


@router.patch("/{fatura_id}/revisao", response_model=FaturaDetalheSchema)
def revisar_fatura(
    fatura_id: str,
    payload: FaturaRevisaoRequestSchema,
):
    try:
        workflow_df, itens_df, medidores_df, _ = _load_fatura_context(fatura_id)

        shared_workflow_values = {
            "unidade_consumidora": payload.cadastro_cliente.unidade_consumidora
            if payload.cadastro_cliente and payload.cadastro_cliente.unidade_consumidora is not None
            else payload.unidade_consumidora,
            "cliente_numero": payload.cadastro_cliente.cliente_numero
            if payload.cadastro_cliente and payload.cadastro_cliente.cliente_numero is not None
            else payload.cliente_numero,
            "nome": payload.cadastro_cliente.nome
            if payload.cadastro_cliente and payload.cadastro_cliente.nome is not None
            else payload.nome,
            "cnpj_cpf": payload.cadastro_cliente.cnpj_cpf
            if payload.cadastro_cliente and payload.cadastro_cliente.cnpj_cpf is not None
            else payload.cnpj_cpf,
            "cep": payload.cadastro_cliente.cep
            if payload.cadastro_cliente and payload.cadastro_cliente.cep is not None
            else payload.cep,
            "cidade_uf": payload.cadastro_cliente.cidade_uf
            if payload.cadastro_cliente and payload.cadastro_cliente.cidade_uf is not None
            else payload.cidade_uf,
            "referencia": payload.referencia,
            "vencimento": payload.vencimento,
            "leitura_anterior": payload.leitura_anterior,
            "leitura_atual": payload.leitura_atual,
            "dias": _safe_int(payload.dias) if payload.dias is not None else None,
            "proxima_leitura": payload.proxima_leitura,
        }
        workflow_updates: Dict[str, Any] = {}
        for key, value in shared_workflow_values.items():
            if value is None:
                continue
            workflow_updates[key] = value

        has_review_changes = bool(workflow_updates) or payload.cadastro_cliente is not None
        updated_workflow_df = workflow_df.copy()
        if workflow_updates:
            updated_workflow_df = _apply_updates_to_df(updated_workflow_df, WORKFLOW_PROPAGATION_FIELDS, workflow_updates)

        if has_review_changes:
            updated_workflow_df.loc[:, "status_validacao"] = "pendente"
            updated_workflow_df.loc[:, "validado_por"] = None
            updated_workflow_df.loc[:, "validado_em"] = None
            updated_workflow_df.loc[:, "status_calculo"] = "nao_calculada"
            updated_workflow_df.loc[:, "calculado_em"] = None
            updated_workflow_df.loc[:, "updated_at"] = _now_utc()
            upsert_dataframe(updated_workflow_df, TABLE_FATURAS_WORKFLOW, key_column="id")

        updated_itens_df = _apply_updates_to_df(itens_df, ITEMS_PROPAGATION_FIELDS, workflow_updates)
        if updated_itens_df is not None and not updated_itens_df.empty and workflow_updates:
            upsert_dataframe(updated_itens_df, TABLE_FATURA_ITENS, key_column="id")

        updated_medidores_df = _apply_updates_to_df(medidores_df, MEDIDORES_PROPAGATION_FIELDS, workflow_updates)
        if updated_medidores_df is not None and not updated_medidores_df.empty and workflow_updates:
            upsert_dataframe(updated_medidores_df, TABLE_MEDIDORES, key_column="id")

        _persist_cliente_from_review(updated_workflow_df.iloc[0], updated_itens_df, payload)

        workflow_df, itens_df, medidores_df, client_df = _load_fatura_context(fatura_id)
        return _build_fatura_detail_payload(workflow_df, itens_df, medidores_df, client_df)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar revisao da fatura: {exc}")


@router.patch("/{fatura_id}/validar", response_model=FaturaValidacaoResponseSchema)
def validar_fatura(
    fatura_id: str,
    payload: Optional[FaturaValidacaoRequestSchema] = None,
):
    usuario = (payload.usuario if payload else None) or "frontend"

    try:
        workflow_df, itens_df, medidores_df, client_df = _load_fatura_context(fatura_id)
        cadastro_cliente = _build_cadastro_cliente_payload(workflow_df.iloc[0], itens_df, client_df)
        if cadastro_cliente.get("campos_pendentes"):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Preencha e salve o cadastro minimo antes de validar a fatura.",
                    "fields": cadastro_cliente.get("campos_pendentes", []),
                },
            )

        updated = _mark_fatura_validada(fatura_id, usuario)
        return {
            "id": updated["id"],
            "status_validacao": updated.get("status_validacao") or "validado",
            "validado_por": updated.get("validado_por"),
            "validado_em": updated.get("validado_em"),
            "updated_at": updated.get("updated_at"),
            "status_calculo": updated.get("status_calculo"),
            "calculado_em": updated.get("calculado_em"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao validar fatura: {exc}")


@router.post("/{fatura_id}/validar-e-calcular", response_model=FaturaValidacaoResponseSchema)
def validar_e_calcular_fatura(
    fatura_id: str,
    payload: Optional[FaturaValidacaoRequestSchema] = None,
):
    usuario = (payload.usuario if payload else None) or "frontend"

    try:
        workflow_df, itens_df, medidores_df, _ = _load_fatura_context(fatura_id)
        _build_client_df_for_calc(workflow_df.iloc[0], itens_df, medidores_df)
        _mark_fatura_validada(fatura_id, usuario)
        calculo = _calculate_fatura_impl(fatura_id, usuario_validacao=usuario)
        updated = _get_workflow_df(fatura_id).iloc[0]
        return {
            "id": str(updated.get("id")),
            "status_validacao": _safe_str(updated.get("status_validacao")) or "validado",
            "validado_por": _safe_str(updated.get("validado_por")),
            "validado_em": _safe_str(updated.get("validado_em")),
            "updated_at": _safe_str(updated.get("updated_at")),
            "status_calculo": calculo.get("status_calculo"),
            "calculado_em": calculo.get("calculado_em"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao validar e calcular fatura: {exc}")


@router.post("/{fatura_id}/calcular", response_model=FaturaCalculoResponseSchema)
def calcular_fatura(fatura_id: str):
    try:
        return _calculate_fatura_impl(fatura_id, usuario_validacao="calculo")
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
