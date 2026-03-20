from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.api.faturas import router as faturas_router
from app.core.config import get_settings
from app.schemas.health import HealthResponse
from app.schemas.reporting import (
    BoletosListResponseSchema,
    DashboardResumoResponseSchema,
    HistoricoResponseSchema,
)
from app.services import load_dashboard_drilldown, load_reporting_fact

router = APIRouter()
settings = get_settings()

MONTH_ABBR = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = pd.to_numeric(value, errors="coerce")
        if pd.isna(number):
            return default
        return float(number)
    except Exception:
        return default


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    if pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_percent(value: Any) -> float:
    number = _safe_float(value, default=0.0)
    if abs(number) <= 1:
        return number * 100
    return number


def _period_dt(periodo: Any) -> pd.Timestamp:
    return pd.to_datetime(f"01/{_safe_str(periodo)}", format="%d/%m/%Y", errors="coerce")


def _period_label(periodo: Any) -> str:
    text = _safe_str(periodo)
    if not text or "/" not in text:
        return text or "-"

    try:
        mes, ano = text.split("/", 1)
        return f"{MONTH_ABBR.get(int(mes), mes)}/{ano}"
    except Exception:
        return text


def _format_status_cliente(value: Any) -> str:
    status = _safe_str(value).lower()
    if status == "inativo":
        return "Inativo"
    return "Ativo"


def _map_boleto_status(row: pd.Series) -> str:
    status_emissao = _safe_str(row.get("status_emissao"))
    if status_emissao and status_emissao != "nao_emitido":
        return "gerado"

    if _safe_str(row.get("status_calculo")) == "calculado":
        return "validado"

    return "pendente"


def _map_fatura_status(row: pd.Series) -> str:
    if _safe_str(row.get("status_parse")) == "erro_parse":
        return "erro"
    if _safe_str(row.get("status_validacao")) == "validado":
        return "validado"
    return "pendente"


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        app=settings.app_name,
        env=settings.app_env,
        version="0.1.0",
    )


@router.get("/api/v1/meta", tags=["system"])
def meta():
    return {
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "server_time": datetime.utcnow().isoformat() + "Z",
        "modules": {
            "faturas": "partial",
            "boletos": "partial",
            "dashboard": "partial",
            "historico": "partial",
            "integrations": {
                "bigquery": "partial",
                "sicoob": "partial",
            },
        },
    }


@router.get("/api/v1/boletos", response_model=BoletosListResponseSchema, tags=["boletos"])
def list_boletos(
    q: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    try:
        df = load_reporting_fact()
        if df is None or df.empty:
            return {"items": [], "total": 0}

        data = df.copy()
        data = data[data["status_parse"].fillna("parseado") != "erro_parse"].copy()

        if q:
            needle = q.lower()
            mask = (
                data["nota_fiscal"].astype(str).str.lower().str.contains(needle, na=False)
                | data["unidade_consumidora"].astype(str).str.lower().str.contains(needle, na=False)
                | data["cliente_numero"].astype(str).str.lower().str.contains(needle, na=False)
                | data["nome"].astype(str).str.lower().str.contains(needle, na=False)
            )
            data = data[mask].copy()

        if "updated_at" in data.columns:
            data["_sort_dt"] = pd.to_datetime(data["updated_at"], errors="coerce", utc=True)
        else:
            data["_sort_dt"] = data["periodo"].map(_period_dt)
        data = data.sort_values("_sort_dt", ascending=False, na_position="last")

        items = []
        for _, row in data.iterrows():
            boleto_status = _map_boleto_status(row)
            if status and boleto_status != status:
                continue

            energia = _safe_float(row.get("energia_compensada_kwh"))
            if energia == 0:
                energia = _safe_float(row.get("injetada_kwh_parseada"))

            valor_bandeiras_total = _safe_float(row.get("bandeiras_valor_parseado"))
            valor_bandeiras_desc = _safe_float(row.get("valor_bandeiras"))

            items.append(
                {
                    "id": _safe_str(row.get("workflow_id") or row.get("nota_fiscal")),
                    "cliente": {
                        "unidade_consumidora": _safe_str(row.get("unidade_consumidora")),
                        "cliente_numero": _safe_str(row.get("cliente_numero")),
                        "nome": _safe_str(row.get("nome")),
                        "cnpj": _safe_str(row.get("cnpj_cpf")),
                        "cep": _safe_str(row.get("cep")),
                        "cidade_uf": _safe_str(row.get("cidade_uf")),
                        "desconto_contratado": _normalize_percent(row.get("desconto_contratado")),
                        "subvencao": _safe_float(row.get("subvencao")),
                        "status": _format_status_cliente(row.get("status_cliente")),
                    },
                    "referencia": _safe_str(row.get("periodo")),
                    "vencimento": _safe_str(row.get("vencimento")),
                    "energia_compensada": energia,
                    "tarifa_sem_desconto": _safe_float(row.get("tarifa_sem_desconto_candidata")),
                    "tarifa_com_desconto": _safe_float(row.get("tarifa_com_desconto_candidata")),
                    "percentual_desconto": _normalize_percent(row.get("desconto_contratado")),
                    "bandeiras": (valor_bandeiras_total / energia) if energia else 0.0,
                    "bandeiras_com_desconto": (valor_bandeiras_desc / energia) if energia else 0.0,
                    "valor_total": _safe_float(row.get("total_a_pagar_report")),
                    "economia_gerada": _safe_float(row.get("economia_calculada")),
                    "status": boleto_status,
                    "faturas": [
                        {
                            "id": _safe_str(row.get("workflow_id") or row.get("nota_fiscal")),
                            "referencia": _safe_str(row.get("periodo")),
                            "vencimento": _safe_str(row.get("vencimento")),
                            "nota_fiscal_numero": _safe_str(row.get("nota_fiscal")),
                            "leitura_anterior": _safe_str(row.get("leitura_anterior")),
                            "leitura_atual": _safe_str(row.get("leitura_atual")),
                            "total": _safe_float(row.get("valor_concessionaria")),
                        }
                    ],
                }
            )

        total = len(items)
        return {"items": items[offset : offset + limit], "total": total}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao listar boletos: {exc}")


@router.get(
    "/api/v1/dashboard/resumo",
    response_model=DashboardResumoResponseSchema,
    tags=["dashboard"],
)
def dashboard_resumo():
    df = load_dashboard_drilldown()
    if df is None or df.empty:
        return {
            "total_economia": 0,
            "total_receita": 0,
            "total_clientes": 0,
            "energia_compensada_total": 0,
            "economia_por_mes": [],
            "maiores_clientes": [],
            "receita_por_mes": [],
        }

    data = df.copy()
    for col in ["economia_calculada", "valor_boleto", "injetada_kwh", "injetada_kwh_parseada"]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0.0)

    data["_period_dt"] = data["periodo"].map(_period_dt)
    calc_data = data.copy()
    if "valor_boleto" in calc_data.columns:
        calc_data = calc_data[calc_data["valor_boleto"] != 0].copy()
    if calc_data.empty:
        calc_data = data.copy()

    economia_por_mes = (
        calc_data.groupby(["periodo", "_period_dt"], dropna=False)["economia_calculada"]
        .sum()
        .reset_index()
        .sort_values("_period_dt")
    )
    receita_por_mes = (
        calc_data.groupby(["periodo", "_period_dt"], dropna=False)["valor_boleto"]
        .sum()
        .reset_index()
        .sort_values("_period_dt")
    )
    top_clientes = (
        calc_data.groupby("nome", dropna=False)["economia_calculada"]
        .sum()
        .reset_index()
        .sort_values("economia_calculada", ascending=False)
        .head(5)
    )

    energia_total = 0.0
    if "injetada_kwh" in calc_data.columns:
        energia_total += float(calc_data["injetada_kwh"].sum())
    if energia_total == 0 and "injetada_kwh_parseada" in calc_data.columns:
        energia_total = float(calc_data["injetada_kwh_parseada"].sum())

    return {
        "total_economia": float(calc_data["economia_calculada"].sum()),
        "total_receita": float(calc_data["valor_boleto"].sum()),
        "total_clientes": int(data["cliente_numero"].fillna("").replace("", pd.NA).dropna().nunique()),
        "energia_compensada_total": energia_total,
        "economia_por_mes": [
            {"mes": _period_label(row["periodo"]), "valor": float(row["economia_calculada"])}
            for _, row in economia_por_mes.iterrows()
        ],
        "maiores_clientes": [
            {"nome": _safe_str(row["nome"]), "economia": float(row["economia_calculada"])}
            for _, row in top_clientes.iterrows()
        ],
        "receita_por_mes": [
            {"mes": _period_label(row["periodo"]), "valor": float(row["valor_boleto"])}
            for _, row in receita_por_mes.iterrows()
        ],
    }


@router.get("/api/v1/historico", response_model=HistoricoResponseSchema, tags=["historico"])
def historico():
    df = load_reporting_fact()
    if df is None or df.empty:
        return {"items": []}

    data = df.copy()
    data = data[data["status_parse"].fillna("parseado") != "erro_parse"].copy()

    for col in [
        "economia_calculada",
        "valor_concessionaria",
        "desconto_contratado",
        "subvencao",
    ]:
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0.0)

    data["_period_dt"] = data["periodo"].map(_period_dt)
    data = data.sort_values(["unidade_consumidora", "_period_dt"], ascending=[True, False])

    items = []
    grouped = data.groupby(["unidade_consumidora", "cliente_numero"], dropna=False)
    for (uc, cliente_numero), group in grouped:
        first = group.iloc[0]
        historico_df = (
            group.groupby(["periodo", "_period_dt"], dropna=False)["economia_calculada"]
            .sum()
            .reset_index()
            .sort_values("_period_dt")
        )

        faturas = [
            {
                "id": _safe_str(row.get("workflow_id") or row.get("nota_fiscal")),
                "referencia": _safe_str(row.get("periodo")),
                "vencimento": _safe_str(row.get("vencimento")),
                "nota_fiscal_numero": _safe_str(row.get("nota_fiscal")),
                "total": _safe_float(row.get("valor_concessionaria")),
                "status": _map_fatura_status(row),
            }
            for _, row in group.iterrows()
        ]

        items.append(
            {
                "unidade_consumidora": _safe_str(uc),
                "cliente_numero": _safe_str(cliente_numero),
                "nome": _safe_str(first.get("nome")),
                "cnpj": _safe_str(first.get("cnpj_cpf")),
                "cep": _safe_str(first.get("cep")),
                "cidade_uf": _safe_str(first.get("cidade_uf")),
                "desconto_contratado": _normalize_percent(first.get("desconto_contratado")),
                "subvencao": _safe_float(first.get("subvencao")),
                "status": _format_status_cliente(first.get("status_cliente")),
                "historico_economia": [
                    {"mes": _period_label(row["periodo"]), "valor": float(row["economia_calculada"])}
                    for _, row in historico_df.iterrows()
                ],
                "faturas": faturas,
            }
        )

    items.sort(key=lambda item: item["nome"] or item["unidade_consumidora"])
    return {"items": items}


router.include_router(faturas_router)
