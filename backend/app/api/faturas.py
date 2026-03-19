from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.clients import (
    TABLE_FATURAS_WORKFLOW,
    execute_query,
    upsert_dataframe,
)
from app.core.config import get_settings
from app.schemas.faturas import (
    FaturaParseErroArquivoSchema,
    FaturaParseResumoSchema,
    FaturasParseResponseSchema,
)
from app.services import (
    build_workflow_from_parse_results,
    processar_lote_faturas,
)

router = APIRouter(prefix="/api/v1/faturas", tags=["faturas"])
settings = get_settings()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


@router.get("")
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao listar faturas: {e}")


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

    salvar_auto_executado = False
    bigquery_result = None

    if workflow_df is not None and not workflow_df.empty:
        try:
            affected = upsert_dataframe(
                workflow_df,
                TABLE_FATURAS_WORKFLOW,
                key_column="id",
            )
            salvar_auto_executado = True
            bigquery_result = {
                "ok": True,
                "table": TABLE_FATURAS_WORKFLOW,
                "affected_rows": int(affected),
            }
        except Exception as e:
            bigquery_result = {
                "ok": False,
                "table": TABLE_FATURAS_WORKFLOW,
                "error": str(e),
            }

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
        bigquery_result=bigquery_result,
    )