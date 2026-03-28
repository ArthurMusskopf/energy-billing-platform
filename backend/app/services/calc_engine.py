from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import math
import re
import unicodedata

import numpy as np
import pandas as pd


def _to_str(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return str(x).strip()


def _to_float(x) -> float:
    if x is None:
        return float("nan")
    if isinstance(x, (int, float, np.integer, np.floating)):
        return float(x)
    s = str(x).strip()
    if not s:
        return float("nan")
    try:
        return float(s)
    except Exception:
        return float("nan")


def _norm_text(s: str) -> str:
    s = _to_str(s).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _isclose(a: float, b: float, tol: float = 1e-6) -> bool:
    if np.isnan(a) or np.isnan(b):
        return False
    return abs(a - b) <= tol


def infer_n_fases(classe_modalidade: Optional[str]) -> Optional[int]:
    if not classe_modalidade:
        return None
    s = _norm_text(classe_modalidade).upper()
    if "TRIF" in s:
        return 3
    if "BIF" in s:
        return 2
    if "MONOF" in s or "MONO" in s:
        return 1
    return None


def compute_custo_disp(n_fases: Optional[int]) -> Optional[float]:
    if n_fases == 3:
        return 100.0
    if n_fases == 2:
        return 50.0
    if n_fases == 1:
        return 30.0
    return None


@dataclass
class CalcResult:
    df_boletos: pd.DataFrame
    missing_clientes: List[str]
    missing_reason: Dict[str, str]


def _prepare_inputs(
    df_itens: pd.DataFrame,
    df_medidores: pd.DataFrame,
    df_clientes: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dfi = df_itens.copy()
    dfm = df_medidores.copy()
    dfc = df_clientes.copy()

    for col in [
        "numero",
        "unidade_consumidora",
        "descricao",
        "referencia",
        "nome",
        "vencimento",
        "cnpj",
        "cnpj_cpf",
        "cep",
        "cidade_uf",
        "cliente_numero",
    ]:
        if col in dfi.columns:
            dfi[col] = dfi[col].astype(str)

    for col in ["nota_fiscal_numero", "tipo", "unidade_consumidora"]:
        if col in dfm.columns:
            dfm[col] = dfm[col].astype(str)

    for col in ["unidade_consumidora", "status"]:
        if col in dfc.columns:
            dfc[col] = dfc[col].astype(str)

    for col in ["tarifa", "quantidade_registrada", "valor", "total_pagar", "injetada_calculo"]:
        if col in dfi.columns:
            dfi[col] = pd.to_numeric(dfi[col], errors="coerce")

    if "total_apurado" in dfm.columns:
        dfm["total_apurado"] = pd.to_numeric(dfm["total_apurado"], errors="coerce")

    for col in ["desconto_contratado", "subvencao", "custo_disp", "n_fases"]:
        if col in dfc.columns:
            dfc[col] = pd.to_numeric(dfc[col], errors="coerce")

    dfi["_desc_norm"] = dfi["descricao"].map(_norm_text) if "descricao" in dfi.columns else ""
    dfm["_tipo_norm"] = dfm["tipo"].map(_norm_text) if "tipo" in dfm.columns else ""

    return dfi, dfm, dfc


def _first_by_numero(dfi: pd.DataFrame, col: str) -> pd.Series:
    if "numero" not in dfi.columns or col not in dfi.columns:
        return pd.Series(dtype=object)

    tmp = dfi[["numero", col]].dropna(subset=["numero"])
    tmp = tmp.drop_duplicates(subset=["numero"], keep="first")
    return tmp.set_index("numero")[col]


def _sum_tarifa_by_desc(dfi: pd.DataFrame, desc: str) -> pd.Series:
    dn = _norm_text(desc)
    sub = dfi[dfi["_desc_norm"] == dn]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.groupby("numero")["tarifa"].sum(min_count=1)


def _sum_qtd_by_desc(dfi: pd.DataFrame, desc: str) -> pd.Series:
    dn = _norm_text(desc)
    sub = dfi[dfi["_desc_norm"] == dn]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.groupby("numero")["quantidade_registrada"].sum(min_count=1)


def _lookup_tarifa_numero_desc_first(
    dfi: pd.DataFrame,
    numero: str,
    desc: str,
    default: float = 0.0,
) -> float:
    dn = _norm_text(desc)
    sub = dfi[(dfi["numero"].astype(str) == str(numero)) & (dfi["_desc_norm"] == dn)]
    if sub.empty:
        return default
    v = sub.iloc[0].get("tarifa", np.nan)
    return default if pd.isna(v) else float(v)


def _max_tarifa_numero_desc(
    dfi: pd.DataFrame,
    numero: str,
    desc: str,
    default: float = 0.0,
) -> float:
    dn = _norm_text(desc)
    sub = dfi[(dfi["numero"].astype(str) == str(numero)) & (dfi["_desc_norm"] == dn)]
    if sub.empty:
        return default
    v = sub["tarifa"].max()
    return default if pd.isna(v) else float(v)


def _max_tarifa_numero_desc_injetada_calculo_eq_1(
    dfi: pd.DataFrame,
    numero: str,
    desc: str,
    default: float = 0.0,
) -> float:
    if "injetada_calculo" not in dfi.columns:
        return default

    dn = _norm_text(desc)
    sub = dfi[(dfi["numero"].astype(str) == str(numero)) & (dfi["_desc_norm"] == dn)].copy()
    if sub.empty:
        return default

    sub["injetada_calculo"] = pd.to_numeric(sub["injetada_calculo"], errors="coerce")
    sub = sub[sub["injetada_calculo"] == 1]
    if sub.empty:
        return default

    v = sub["tarifa"].max()
    return default if pd.isna(v) else float(v)


def _energia_injetada_tarifa(
    dfi: pd.DataFrame,
    numero: str,
    desc: str,
    med_inj_tusd: float,
    boleto: int,
    gerador: int,
) -> float:
    if boleto != 1:
        return 0.0

    dn = _norm_text(desc)
    sub = dfi[(dfi["numero"].astype(str) == str(numero)) & (dfi["_desc_norm"] == dn)]
    sub = sub.dropna(subset=["tarifa", "quantidade_registrada"])

    if sub.empty:
        return 0.0

    def xlookup_qty():
        if pd.isna(med_inj_tusd) or med_inj_tusd == 0:
            return 0.0
        for _, r in sub.iterrows():
            q = float(r["quantidade_registrada"])
            if _isclose(q, float(med_inj_tusd)):
                return float(r["tarifa"])
        return 0.0

    def weighted_avg_qty():
        weighted = sub.copy()
        weighted["peso_quantidade"] = weighted["quantidade_registrada"].abs()
        weighted = weighted[weighted["peso_quantidade"] > 0]
        if weighted.empty:
            return 0.0

        total_qty = float(weighted["peso_quantidade"].sum(min_count=1))
        if _isclose(total_qty, 0.0):
            return 0.0

        numerador = float((weighted["tarifa"] * weighted["peso_quantidade"]).sum(min_count=1))
        return numerador / total_qty

    if gerador == 0 and (not pd.isna(med_inj_tusd)) and float(med_inj_tusd) != 0.0:
        # Regra de negocio nova:
        # para consumidor nao gerador com energia injetada positiva,
        # a tarifa deve refletir a media ponderada das linhas efetivamente registradas.
        return weighted_avg_qty()

    return xlookup_qty()


def calculate_boletos(
    df_itens: pd.DataFrame,
    df_medidores: pd.DataFrame,
    df_clientes: pd.DataFrame,
    *,
    only_registered_clients: bool = True,
    only_status_ativo: bool = True,
) -> CalcResult:
    dfi, dfm, dfc = _prepare_inputs(df_itens, df_medidores, df_clientes)

    required_itens = {"numero", "unidade_consumidora", "descricao", "tarifa", "quantidade_registrada"}
    missing_req = [c for c in required_itens if c not in dfi.columns]
    if missing_req:
        raise ValueError(f"df_itens esta sem colunas obrigatorias: {missing_req}")

    required_med = {"nota_fiscal_numero", "tipo", "total_apurado"}
    missing_reqm = [c for c in required_med if c not in dfm.columns]
    if missing_reqm:
        raise ValueError(f"df_medidores esta sem colunas obrigatorias: {missing_reqm}")

    required_cli = {"unidade_consumidora", "desconto_contratado", "subvencao", "status", "custo_disp"}
    missing_reqc = [c for c in required_cli if c not in dfc.columns]
    if missing_reqc:
        raise ValueError(f"df_clientes esta sem colunas obrigatorias: {missing_reqc}")

    numeros = (
        dfi["numero"]
        .replace(["None", "nan", "NaN", ""], np.nan)
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    base = pd.DataFrame({"numero": numeros}).sort_values("numero").reset_index(drop=True)

    uc_map = _first_by_numero(dfi, "unidade_consumidora")
    periodo_map = _first_by_numero(dfi, "referencia") if "referencia" in dfi.columns else pd.Series(dtype=object)
    nome_map = _first_by_numero(dfi, "nome") if "nome" in dfi.columns else pd.Series(dtype=object)
    venc_map = _first_by_numero(dfi, "vencimento") if "vencimento" in dfi.columns else pd.Series(dtype=object)
    cep_map = _first_by_numero(dfi, "cep") if "cep" in dfi.columns else pd.Series(dtype=object)
    ciduf_map = _first_by_numero(dfi, "cidade_uf") if "cidade_uf" in dfi.columns else pd.Series(dtype=object)
    cnpj_map = _first_by_numero(dfi, "cnpj") if "cnpj" in dfi.columns else _first_by_numero(dfi, "cnpj_cpf")
    cli_num_map = _first_by_numero(dfi, "cliente_numero") if "cliente_numero" in dfi.columns else pd.Series(dtype=object)
    total_pagar_map = _first_by_numero(dfi, "total_pagar") if "total_pagar" in dfi.columns else pd.Series(dtype=object)

    base["unidade_consumidora"] = base["numero"].map(uc_map).astype(str)

    dfc2 = dfc.copy()
    dfc2["status_norm"] = dfc2["status"].map(_norm_text)

    base = base.merge(
        dfc2[["unidade_consumidora", "desconto_contratado", "subvencao", "status", "status_norm", "custo_disp"]],
        on="unidade_consumidora",
        how="left",
        suffixes=("", "_cli"),
    )

    missing_reason: Dict[str, str] = {}
    missing_clientes: List[str] = []

    if only_registered_clients:
        miss = base["custo_disp"].isna() | (base["desconto_contratado"].isna())
        for uc in base.loc[miss, "unidade_consumidora"].astype(str).tolist():
            missing_reason[uc] = "Cliente nao cadastrado em info_clientes"
        missing_clientes = sorted(set(base.loc[miss, "unidade_consumidora"].astype(str).tolist()))
        base = base.loc[~miss].copy()

    if only_status_ativo:
        mask_inativo = base["status_norm"].notna() & (base["status_norm"] != "ativo")
        if mask_inativo.any():
            for uc in base.loc[mask_inativo, "unidade_consumidora"].astype(str).tolist():
                missing_reason[uc] = "Cliente com status diferente de 'Ativo'"
            base = base.loc[~mask_inativo].copy()

    base["periodo"] = base["numero"].map(periodo_map)
    base["nome"] = base["numero"].map(nome_map)

    base["vencimento"] = base["numero"].map(venc_map)
    base["cnpj_cpf"] = base["numero"].map(cnpj_map)
    base["cep"] = base["numero"].map(cep_map)
    base["cidade_uf"] = base["numero"].map(ciduf_map)
    base["cliente_numero"] = base["numero"].map(cli_num_map)
    base["total_pagar"] = base["numero"].map(total_pagar_map)

    dfm2 = dfm.copy()
    dfm2["numero"] = dfm2["nota_fiscal_numero"].astype(str)

    g = dfm2.groupby(["numero", "_tipo_norm"])["total_apurado"].sum(min_count=1).unstack()

    energia = g.get(_norm_text("Energia"), pd.Series(dtype=float))
    inj = g.get(_norm_text("Energia injetada"), pd.Series(dtype=float))
    if inj.empty:
        inj = g.get(_norm_text("Energia Injetada"), pd.Series(dtype=float))

    base["medidores_apurado"] = base["numero"].map(energia).fillna(0.0) - base["numero"].map(inj).fillna(0.0)

    base["custo_disp"] = pd.to_numeric(base["custo_disp"], errors="coerce")
    base["injetada"] = base["medidores_apurado"] - base["custo_disp"]
    base["boleto"] = np.where(base["injetada"] <= 0, 0, 1).astype(int)

    te = _sum_tarifa_by_desc(dfi, "Consumo TE")
    tusd = _sum_tarifa_by_desc(dfi, "Consumo TUSD")
    base["tarifa_cheia_trib"] = base["numero"].map(te).fillna(0.0) + base["numero"].map(tusd).fillna(0.0)
    base.loc[base["boleto"] != 1, "tarifa_cheia_trib"] = 0.0

    def _check(v: float) -> str:
        if pd.isna(v):
            return ""
        if v > 10:
            return "Parseamento"
        if v > 1:
            return "Subvencao"
        return "Certo"

    base["check"] = base["tarifa_cheia_trib"].map(_check)
    base["subvencao"] = pd.to_numeric(base["subvencao"], errors="coerce")

    cons = dfi[dfi["_desc_norm"].isin({_norm_text("Consumo TE"), _norm_text("Consumo TUSD")})].copy()
    cons = cons.merge(base[["numero", "subvencao"]], on="numero", how="left")
    cons["subvencao"] = pd.to_numeric(cons["subvencao"], errors="coerce")
    cons["_keep"] = cons["subvencao"].isna() | (cons["quantidade_registrada"] != cons["subvencao"])
    cons2 = cons[cons["_keep"]]
    cons_sum_excl = cons2.groupby("numero")["tarifa"].sum(min_count=1)

    base["tarifa_cheia_trib2"] = base["tarifa_cheia_trib"]
    mask_sub = (base["check"] != "Certo") & (base["boleto"] == 1)
    base.loc[mask_sub, "tarifa_cheia_trib2"] = base.loc[mask_sub, "numero"].map(cons_sum_excl).fillna(0.0)

    first_tipo = (
        dfm2[["numero", "_tipo_norm"]]
        .dropna(subset=["numero"])
        .drop_duplicates(subset=["numero"], keep="first")
        .set_index("numero")["_tipo_norm"]
    )
    gerador_map = (
        (first_tipo == _norm_text("Energia injetada"))
        | (first_tipo == _norm_text("Energia Injetada"))
    ).astype(int)
    base["gerador"] = base["numero"].map(gerador_map).fillna(0).astype(int)

    qtd_inj_tusd = _sum_qtd_by_desc(dfi, "Energia Inj. TUSD")
    inj_med_sum = base["numero"].map(inj).fillna(0.0)
    base["med_inj_tusd"] = base["boleto"] * (base["numero"].map(qtd_inj_tusd).fillna(0.0) - inj_med_sum)

    if "injetada_calculo" not in dfi.columns:
        dfi = dfi.copy()
        dfi["injetada_calculo"] = dfi["numero"].map(base.set_index("numero")["medidores_apurado"])

    energia_inj_tusd_tar = []
    energia_injet_te_tar = []
    for _, r in base.iterrows():
        num = str(r["numero"])
        med = float(r["med_inj_tusd"]) if not pd.isna(r["med_inj_tusd"]) else float("nan")
        energia_inj_tusd_tar.append(
            _energia_injetada_tarifa(dfi, num, "Energia Inj. TUSD", med, int(r["boleto"]), int(r["gerador"]))
        )
        energia_injet_te_tar.append(
            _energia_injetada_tarifa(dfi, num, "Energia Injet. TE", med, int(r["boleto"]), int(r["gerador"]))
        )

    base["energia_inj_tusd_tarifa"] = energia_inj_tusd_tar
    base["energia_injet_te_tarifa"] = energia_injet_te_tar

    base["tarifa_cheia_trib3"] = np.where(
        (base["energia_inj_tusd_tarifa"] + base["energia_injet_te_tarifa"]) != 0,
        base["energia_inj_tusd_tarifa"] + base["energia_injet_te_tarifa"],
        0.0,
    )

    tarifa_inj_tusd = []
    tarifa_inj_te = []
    for _, r in base.iterrows():
        num = str(r["numero"])
        if int(r["boleto"]) != 1:
            tarifa_inj_tusd.append(0.0)
            tarifa_inj_te.append(0.0)
            continue
        if float(r["tarifa_cheia_trib3"]) != 0.0:
            tarifa_inj_tusd.append(0.0)
            tarifa_inj_te.append(0.0)
            continue

        tarifa_inj_tusd.append(
            _max_tarifa_numero_desc_injetada_calculo_eq_1(dfi, num, "Energia Inj. TUSD", default=0.0)
        )
        tarifa_inj_te.append(
            _max_tarifa_numero_desc_injetada_calculo_eq_1(dfi, num, "Energia Injet. TE", default=0.0)
        )

    base["tarifa_inj_tusd"] = tarifa_inj_tusd
    base["tarifa_inj_te"] = tarifa_inj_te

    base["tarifa_cheia"] = np.where(
        base["tarifa_cheia_trib3"] == 0.0,
        base["tarifa_inj_tusd"] + base["tarifa_inj_te"],
        base["tarifa_cheia_trib3"],
    )

    base["desconto_contratado"] = pd.to_numeric(base["desconto_contratado"], errors="coerce").fillna(0.0)

    base["tarifa_paga_conc"] = base["tarifa_cheia_trib2"] + base["tarifa_cheia"]
    base["tarifa_erb"] = (1.0 - base["desconto_contratado"]) * base["tarifa_cheia_trib2"]
    base["tarifa_bol"] = base["tarifa_erb"] - base["tarifa_paga_conc"]

    bandeira_amarela = []
    band_am_injet = []
    band_vermelha = []
    band_vrm_injet = []

    for _, r in base.iterrows():
        num = str(r["numero"])
        bol = int(r["boleto"])

        bandeira_amarela.append(_lookup_tarifa_numero_desc_first(dfi, num, "Bandeira Amarela", default=0.0))
        band_am_injet.append(bol * _lookup_tarifa_numero_desc_first(dfi, num, "Band. Am. Injet.", default=0.0))

        band_vermelha.append(bol * _lookup_tarifa_numero_desc_first(dfi, num, "Band. Vermelha", default=0.0))
        band_vrm_injet.append(bol * _lookup_tarifa_numero_desc_first(dfi, num, "Band. Vrm. Injet.", default=0.0))

    base["bandeira_amarela_tarifa"] = bandeira_amarela
    base["band_am_injet_tarifa"] = band_am_injet
    base["band_vermelha_tarifa"] = band_vermelha
    base["band_vrm_injet_tarifa"] = band_vrm_injet

    base["valor_band_amarela"] = base["boleto"] * (
        base["bandeira_amarela_tarifa"] + base["band_am_injet_tarifa"]
    )
    base["valor_band_amar_desc"] = base["boleto"] * (
        (1.0 - base["desconto_contratado"]) * (base["bandeira_amarela_tarifa"] - base["valor_band_amarela"])
    )

    base["valor_band_vermelha"] = base["boleto"] * (
        base["band_vermelha_tarifa"] + base["band_vrm_injet_tarifa"]
    )
    base["valor_band_vrm_desc"] = base["boleto"] * (
        (1.0 - base["desconto_contratado"]) * (base["band_vermelha_tarifa"] - base["valor_band_vermelha"])
    )

    base["tarifa_total_boleto"] = (
        (base["boleto"] * base["valor_band_vrm_desc"]) + base["valor_band_amar_desc"] + base["tarifa_bol"]
    )
    base["valor_total_boleto"] = base["tarifa_total_boleto"] * base["med_inj_tusd"]

    out_cols = [
        "numero",
        "unidade_consumidora",
        "periodo",
        "nome",
        "vencimento",
        "cnpj_cpf",
        "cep",
        "cidade_uf",
        "cliente_numero",
        "total_pagar",
        "custo_disp",
        "medidores_apurado",
        "injetada",
        "boleto",
        "desconto_contratado",
        "check",
        "subvencao",
        "tarifa_cheia_trib",
        "tarifa_cheia_trib2",
        "gerador",
        "med_inj_tusd",
        "energia_inj_tusd_tarifa",
        "energia_injet_te_tarifa",
        "tarifa_cheia_trib3",
        "tarifa_inj_tusd",
        "tarifa_inj_te",
        "tarifa_cheia",
        "tarifa_paga_conc",
        "tarifa_erb",
        "tarifa_bol",
        "bandeira_amarela_tarifa",
        "band_am_injet_tarifa",
        "valor_band_amarela",
        "valor_band_amar_desc",
        "band_vermelha_tarifa",
        "band_vrm_injet_tarifa",
        "valor_band_vermelha",
        "valor_band_vrm_desc",
        "tarifa_total_boleto",
        "valor_total_boleto",
    ]

    df_out = base[out_cols].copy()
    df_out = df_out.replace({np.nan: None})

    return CalcResult(
        df_boletos=df_out,
        missing_clientes=missing_clientes,
        missing_reason=missing_reason,
    )
