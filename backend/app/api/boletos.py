from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.clients import TABLE_BOLETOS, TABLE_CLIENTES, TABLE_FATURAS_WORKFLOW, execute_query
from app.schemas.boletos import BoletosListResponseSchema

router = APIRouter(prefix="/api/v1/boletos", tags=["boletos"])


def _safe_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    text = str(value).strip()
    return text or None


def _safe_records(df: pd.DataFrame) -> List[dict]:
    if df is None or df.empty:
        return []

    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype(str).replace({"NaT": None})

    out = out.where(pd.notna(out), None)
    return out.to_dict(orient="records")


def _normalize_status_validacao(value: Any) -> Optional[str]:
    status = _safe_str(value)
    if not status:
        return None
    if status.lower() in {"validado", "validada"}:
        return "validada"
    return status


def _normalize_status_calculo(value: Any) -> Optional[str]:
    status = _safe_str(value)
    if not status:
        return None
    if status.lower() in {"calculado", "calculada"}:
        return "calculada"
    return status


def _map_boleto_status(record: dict) -> str:
    status_emissao = _safe_str(record.get("status_emissao"))
    status_calculo = _normalize_status_calculo(record.get("status_calculo"))

    if status_emissao and status_emissao not in {"nao_emitido", "pendente", "nao_gerado"}:
        return "gerado"
    if status_calculo == "calculada":
        return "calculada"
    return "pendente"


@router.get("", response_model=BoletosListResponseSchema)
def list_boletos(
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    where_parts = ["1=1"]
    params: Dict[str, Any] = {"limit": int(limit), "offset": int(offset)}

    if q:
        where_parts.append(
            """
            (
              CAST(b.id AS STRING) LIKE CONCAT('%', @q, '%')
              OR CAST(COALESCE(b.nota_fiscal, b.id) AS STRING) LIKE CONCAT('%', @q, '%')
              OR CAST(COALESCE(b.unidade_consumidora, wf.unidade_consumidora) AS STRING) LIKE CONCAT('%', @q, '%')
              OR CAST(COALESCE(b.cliente_numero, wf.cliente_numero) AS STRING) LIKE CONCAT('%', @q, '%')
              OR LOWER(COALESCE(b.nome, wf.nome, '')) LIKE LOWER(CONCAT('%', @q, '%'))
            )
            """
        )
        params["q"] = str(q)

    where_sql = " AND ".join(where_parts)

    query_items = f"""
    SELECT
      b.id,
      b.workflow_id,
      COALESCE(b.nota_fiscal, b.id) AS nota_fiscal,
      COALESCE(b.periodo, wf.referencia) AS referencia,
      COALESCE(b.vencimento, wf.vencimento) AS vencimento,
      COALESCE(b.unidade_consumidora, wf.unidade_consumidora) AS unidade_consumidora,
      COALESCE(b.cliente_numero, wf.cliente_numero) AS cliente_numero,
      COALESCE(b.nome, wf.nome) AS nome,
      COALESCE(b.cnpj_cpf, wf.cnpj_cpf) AS cnpj_cpf,
      COALESCE(b.cep, wf.cep) AS cep,
      COALESCE(b.cidade_uf, wf.cidade_uf) AS cidade_uf,
      cli.desconto_contratado,
      cli.subvencao,
      cli.status AS status_cliente,
      wf.status_validacao,
      wf.status_calculo,
      wf.status_emissao,
      wf.leitura_anterior,
      wf.leitura_atual,
      wf.dias,
      wf.proxima_leitura,
      COALESCE(b.injetada_kwh, 0) AS energia_compensada,
      COALESCE(b.tarifa_paga_conc, b.tarifa_cheia, 0) AS tarifa_sem_desconto,
      COALESCE(b.tarifa_erb, b.tarifa_liquida, 0) AS tarifa_com_desconto,
      COALESCE(cli.desconto_contratado, 0) * 100 AS percentual_desconto,
      COALESCE(b.valor_bandeiras, 0) AS bandeiras,
      0 AS bandeiras_com_desconto,
      COALESCE(b.valor_final, 0) AS valor_total,
      COALESCE(b.valor_concessionaria, 0) AS valor_concessionaria,
      COALESCE(b.valor_concessionaria, 0) - COALESCE(b.valor_final, 0) AS economia_gerada,
      b.created_at,
      b.updated_at
    FROM `{TABLE_BOLETOS}` b
    LEFT JOIN `{TABLE_FATURAS_WORKFLOW}` wf
      ON wf.id = COALESCE(b.workflow_id, b.id)
    LEFT JOIN `{TABLE_CLIENTES}` cli
      ON cli.unidade_consumidora = COALESCE(b.unidade_consumidora, wf.unidade_consumidora)
    WHERE {where_sql}
    ORDER BY COALESCE(b.updated_at, b.created_at) DESC, b.id DESC
    LIMIT @limit
    OFFSET @offset
    """

    query_total = f"""
    SELECT COUNT(1) AS total
    FROM `{TABLE_BOLETOS}` b
    LEFT JOIN `{TABLE_FATURAS_WORKFLOW}` wf
      ON wf.id = COALESCE(b.workflow_id, b.id)
    WHERE {where_sql}
    """

    try:
        df_items = execute_query(query_items, params)
        df_total = execute_query(query_total, {k: v for k, v in params.items() if k not in ("limit", "offset")})

        total = 0
        if df_total is not None and not df_total.empty and "total" in df_total.columns:
            total = int(df_total.iloc[0]["total"])

        items = []
        for record in _safe_records(df_items):
            normalized = dict(record)
            normalized["status_validacao"] = _normalize_status_validacao(record.get("status_validacao"))
            normalized["status_calculo"] = _normalize_status_calculo(record.get("status_calculo"))
            normalized["status"] = _map_boleto_status(normalized)
            items.append(normalized)

        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao listar boletos: {exc}")
