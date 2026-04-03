
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pdfplumber


UC_MIN_LEN = 7
UC_MAX_LEN = 12

_BANNED_UC_CONTEXT_RE = re.compile(
    "|".join(
        [
            r"\bcliente\b",
            r"nota\s+fiscal",
            r"nosso\s+n[úu]mero",
            r"n[úu]mero\s+refer",
            r"chave\s+de\s+acesso",
            r"protocolo",
            r"c[oó]digo\s+para\s+cadastro",
            r"linha\s+digit[aá]vel",
            r"\bbradesco\b",
            r"pague\s+com\s+pix",
        ]
    ),
    re.I,
)


@dataclass
class ResultadoParsing:
    sucesso: bool
    arquivo: str
    header: Dict[str, Any]
    periodo: Dict[str, Any]
    nf: Dict[str, Any]
    df_itens: pd.DataFrame
    df_medidores: pd.DataFrame
    erros: List[str]
    alertas: List[str]


def read_pdf_text(pdf_path: str) -> str:
    pages: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for p in pdf.pages:
            pages.append(p.extract_text() or "")
    return "\n".join(pages)


def br2float(s) -> Optional[float]:
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except Exception:
        return None


def clean_spaces(s) -> Optional[str]:
    if s is None:
        return None
    return re.sub(r"\s+", " ", str(s)).strip()


def safe_search(pattern, text, flags=0):
    m = re.search(pattern, text, flags)
    if not m:
        return None
    return (m.group(1) if m.groups() else m.group(0)).strip()


def as_text_or_none(v) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


LABELS = {
    "nome": "NOME:",
    "cpfcnpj": "CPF/CNPJ:",
    "endereco": "ENDERECO:",
    "cep": "CEP:",
    "cidade": "CIDADE:",
    "grupo": "Grupo/Subgrupo Tensão:",
    "cliente": "Cliente:",
    "unidade_consumidora": "Unidade Consumidora",
    "classe_modalidade": "Classificação / Modalidade Tarifária / Tipo de Fornecimento",
}


def extract_between(text, start_label, end_labels, flags=re.S):
    if isinstance(end_labels, str):
        end_labels = [end_labels]
    end_alt = "|".join(re.escape(lbl) for lbl in end_labels)
    pat = re.escape(start_label) + r"\s*(.*?)\s*(?=(?:" + end_alt + r"))"
    return safe_search(pat, text, flags=flags)


def _normalize_fases_truncadas(s: str) -> str:
    if not s:
        return s
    s = clean_spaces(s) or s
    s = re.sub(r"(TRIF[ÁA]?SIC)(?!O)", r"\1O", s, flags=re.I)
    s = re.sub(r"(BIF[ÁA]?SIC)(?!O)", r"\1O", s, flags=re.I)
    s = re.sub(r"(MONOF[ÁA]?SIC)(?!O)", r"\1O", s, flags=re.I)
    return s


def _normalize_numeric_code(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r"\D+", "", str(value))
    if not digits:
        return None
    return digits.lstrip("0") or digits


def parse_cliente_numero(txt: str) -> Optional[str]:
    patterns = [
        r"\bCliente\s*:\s*0*([0-9]{6,12})\b",
        r"\bC[oó]digo\s+do\s+Cliente\s*:\s*0*([0-9]{6,12})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, txt, flags=re.I)
        if match:
            return _normalize_numeric_code(match.group(1))
    return None


def parse_nf(txt: str) -> dict:
    m = re.search(
        r"NOTA\s+FISCAL\s+N[ºO]\s*([0-9]+)\s+SERIE:?\s*([0-9]+)\s+DATA\s+EMISS(?:A|Ã)O:\s*([0-9/]+)",
        txt,
        re.I,
    )
    return {"numero": m.group(1), "serie": m.group(2), "data_emissao": m.group(3)} if m else {}


def _iter_numeric_candidates_from_line(line: str):
    line = line or ""
    if _BANNED_UC_CONTEXT_RE.search(line):
        return []

    pure_match = re.fullmatch(rf"\s*0*([0-9]{{{UC_MIN_LEN},{UC_MAX_LEN}}})\s*$", line)
    if pure_match:
        return [(_normalize_numeric_code(pure_match.group(1)), True, 0)]

    out = []
    for m in re.finditer(rf"(?<!\d)0*([0-9]{{{UC_MIN_LEN},{UC_MAX_LEN}}})(?![\d/])", line):
        out.append((_normalize_numeric_code(m.group(1)), False, m.start(1)))
    return out


def _validate_unidade_consumidora(
    unidade_consumidora: Optional[str],
    *,
    cliente_numero: Optional[str] = None,
    nf_numero: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    uc = _normalize_numeric_code(unidade_consumidora)
    if not uc:
        return None, "UC nao encontrada"

    if not (UC_MIN_LEN <= len(uc) <= UC_MAX_LEN):
        return None, "UC suspeita: quantidade de digitos fora do padrao esperado"

    cliente_norm = _normalize_numeric_code(cliente_numero)
    nf_norm = _normalize_numeric_code(nf_numero)

    if cliente_norm and uc == cliente_norm:
        return None, "UC suspeita: coincide com o codigo do cliente"

    if nf_norm and uc == nf_norm:
        return None, "UC suspeita: coincide com o numero da nota fiscal"

    return uc, None


def parse_unidade_consumidora(txt: str, cliente_numero: Optional[str] = None) -> Optional[str]:
    cliente_numero_norm = _normalize_numeric_code(cliente_numero)
    nf_numero_norm = _normalize_numeric_code(parse_nf(txt).get("numero"))
    blocked_codes = {code for code in (cliente_numero_norm, nf_numero_norm) if code}

    lines = [clean_spaces(line) or "" for line in txt.splitlines()]
    candidates: dict[str, tuple[tuple[int, int, int], str]] = {}

    def add_candidate(code: Optional[str], score: int, line_idx: int, token_pos: int, source: str) -> None:
        if not code or code in blocked_codes:
            return

        rank = (-score, line_idx, token_pos)
        current = candidates.get(code)
        if current is None or rank < current[0]:
            candidates[code] = (rank, source)

    for pattern, score in [
        (rf"Unidade\s+Consumidora\s*[:\-]?\s*\n?\s*0*([0-9]{{{UC_MIN_LEN},{UC_MAX_LEN}}})", 120),
        (rf"\bUC\s*[:\-]?\s*0*([0-9]{{{UC_MIN_LEN},{UC_MAX_LEN}}})\b", 115),
    ]:
        for match in re.finditer(pattern, txt, flags=re.I):
            add_candidate(
                _normalize_numeric_code(match.group(1)),
                score,
                txt[: match.start()].count("\n"),
                max(match.start(1) - match.start(), 0),
                "label-regex",
            )

    for idx, line in enumerate(lines):
        if not re.search(r"\b(Unidade\s+Consumidora|UC)\b", line, flags=re.I):
            continue

        for offset in range(0, 6):
            if idx + offset >= len(lines):
                break

            target = lines[idx + offset]
            for code, is_pure_numeric, token_pos in _iter_numeric_candidates_from_line(target):
                base_score = 105 if is_pure_numeric else 65
                if offset == 0 and is_pure_numeric:
                    base_score = 118

                add_candidate(code, base_score - offset, idx + offset, token_pos, f"label-vicinity:{offset}")

    stop = min(len(lines), 60)
    for i, line in enumerate(lines[:stop]):
        if re.search(r"\bCliente\s*:", line, flags=re.I):
            stop = i
            break

    for idx, line in enumerate(lines[:stop]):
        for code, is_pure_numeric, token_pos in _iter_numeric_candidates_from_line(line):
            base_score = 90 if is_pure_numeric else 60
            add_candidate(code, base_score - min(idx, 30), idx, token_pos, "top-block")

    item_start = next((i for i, line in enumerate(lines) if line.startswith("(")), min(len(lines), 120))
    for idx, line in enumerate(lines[: min(item_start, 120)]):
        match = re.fullmatch(rf"\s*0*([0-9]{{{UC_MIN_LEN},{UC_MAX_LEN}}})\s*$", line)
        if match and not _BANNED_UC_CONTEXT_RE.search(line):
            add_candidate(_normalize_numeric_code(match.group(1)), 50 - min(idx, 40), idx, 0, "early-numeric")

    if not candidates:
        return None

    ranked_codes = sorted(candidates.items(), key=lambda item: item[1][0])
    return ranked_codes[0][0]


def parse_periodo_leituras(txt: str) -> dict:
    flags = re.I | re.S
    out = {
        "leitura_anterior": None,
        "leitura_atual": None,
        "dias": None,
        "proxima_leitura": None,
    }

    def first_date_after(label_regex, text, lookahead=220):
        for m in re.finditer(label_regex, text, flags):
            seg = text[m.end() : m.end() + lookahead]
            md = re.search(r"([0-9]{2}/[0-9]{2}/[0-9]{4})", seg)
            if md:
                return md.group(1)
        return None

    la = first_date_after(r"Leit(?:\.|ura)?\s*Anterior", txt)
    lt = first_date_after(r"Leit(?:\.|ura)?\s*Atual", txt)
    pl = first_date_after(r"Pr(?:[óo]x\.?|[óo]xima)\s*Leit(?:\.|ura)?", txt)

    di = None
    for m in re.finditer(r"Dias(?:\s+no\s+per[ií]odo)?", txt, flags):
        seg = txt[m.end() : m.end() + 140]
        mi = re.search(r"([0-9]{1,3})\b", seg)
        if mi:
            di = int(mi.group(1))
            break

    if la and lt and pl and isinstance(di, int):
        out.update(
            {
                "leitura_anterior": la,
                "leitura_atual": lt,
                "dias": di,
                "proxima_leitura": pl,
            }
        )
        return out

    raw_pat = r"([0-9]{2}/[0-9]{2}/[0-9]{4})\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+([0-9]{1,3})(?:\s+(?:Lida|Lido|Lidas|Lidos))?\s+([0-9]{2}/[0-9]{2}/[0-9]{4})"
    m = re.search(raw_pat, txt, flags=re.I)
    if m:
        out.update(
            {
                "leitura_anterior": la or m.group(1),
                "leitura_atual": lt or m.group(2),
                "dias": di if di is not None else int(m.group(3)),
                "proxima_leitura": pl or m.group(4),
            }
        )
    return out


def parse_classe_modalidade(txt: str) -> Optional[str]:
    pat = (
        r"Classifica(?:ç|c)ão\s*/\s*Modalidade\s*Tarif[aá]ria\s*/\s*Tipo\s*de\s*Fornecimento"
        r"\s*[:\-]?\s*(?:\n\s*)?([^\n]+)"
    )
    v = safe_search(pat, txt, flags=re.I)
    v = clean_spaces(v)
    if v:
        return _normalize_fases_truncadas(v) or None

    lines = [clean_spaces(l) for l in txt.splitlines()]
    lines = [l for l in lines if l]

    stop = min(len(lines), 50)
    for i, l in enumerate(lines[:stop]):
        if re.search(r"\bCliente\s*:", l, flags=re.I):
            stop = i
            break

    phase_pat = re.compile(r"\b(MONOF|BIF|TRIF|MONO|BI|TRI)\b", re.I)
    for l in lines[:stop]:
        if l.strip().startswith("("):
            continue
        if phase_pat.search(l):
            return _normalize_fases_truncadas(l)

    v = safe_search(r"^(.*?(?:MONO|BI|TRI).*)$", txt, flags=re.M | re.I)
    v = clean_spaces(v)
    return _normalize_fases_truncadas(v) if v else None


def infer_n_fases(classe_modalidade: Optional[str]) -> Optional[int]:
    if not classe_modalidade:
        return None
    s = clean_spaces(classe_modalidade).upper()
    if "TRIF" in s:
        return 3
    if "BIF" in s:
        return 2
    if "MONOF" in s or "MONO" in s:
        return 1
    return None


def parse_header(txt: str) -> dict:
    h = {}

    h["classe_modalidade"] = parse_classe_modalidade(txt)
    h["n_fases_parseado"] = infer_n_fases(h.get("classe_modalidade"))

    h["cliente_numero"] = parse_cliente_numero(txt)
    h["unidade_consumidora"] = parse_unidade_consumidora(txt, cliente_numero=h.get("cliente_numero"))

    m = re.search(r"(\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+R\$?\s*([0-9\.,]+)", txt)
    if m:
        h["referencia"] = m.group(1)
        h["vencimento"] = m.group(2)
        h["total_pagar"] = br2float(m.group(3))

    nome = extract_between(txt, LABELS["nome"], LABELS["cpfcnpj"]) or safe_search(r"NOME:\s*(.+)", txt)
    h["nome"] = clean_spaces(nome)
    h["cnpj_cpf"] = safe_search(rf'{re.escape(LABELS["cpfcnpj"])}\s*([^\n]+)', txt)
    ender = extract_between(txt, LABELS["endereco"], LABELS["cep"])
    h["endereco"] = clean_spaces(ender)
    h["cep"] = safe_search(rf'{re.escape(LABELS["cep"])}\s*([0-9\-]+)', txt)

    cid_uf = safe_search(rf'{re.escape(LABELS["cidade"])}\s*([A-ZÇÃÂÉÊÍÓÔÕÚÜ\s]+[A-Z]{{2}})', txt)
    h["cidade_uf"] = clean_spaces(cid_uf)

    h["grupo_subgrupo_tensao"] = safe_search(r"Grupo/Subgrupo\s*Tens[aã]o:\s*([^\n]+)", txt, flags=re.I)

    return h


def parse_itens(txt: str) -> list:
    itens = []

    for raw in txt.splitlines():
        line = clean_spaces(raw) or ""
        if not line.startswith("("):
            continue

        m0 = re.match(r"^\((\w{1,2})\)\s*(.*)$", line, flags=re.I)
        if not m0:
            continue

        code = (m0.group(1) or "").upper()
        rest = (m0.group(2) or "").strip()
        if not rest:
            continue

        unit = None
        desc = None
        tail = None

        mu = re.search(r"\b(KWH|MWH|KVARH|KVAH|UN)\b", rest, flags=re.I)
        if mu:
            unit = mu.group(1).upper()
            desc = rest[: mu.start()].strip()
            tail = rest[mu.end() :].strip()
        else:
            mn = re.search(r"[-+]?\d[\d\.,]*", rest)
            if not mn:
                continue
            unit = "UN"
            desc = rest[: mn.start()].strip()
            tail = rest[mn.start() :].strip()

        if not desc or not tail:
            continue

        toks = tail.split()
        nums = [br2float(x) for x in toks]

        item = {"codigo": code, "descricao": desc, "unidade": unit}
        cols = [
            "quantidade",
            "tarifa",
            "valor",
            "pis_valor",
            "cofins_base",
            "icms_aliquota",
            "icms_valor",
            "tarifa_sem_trib",
        ]
        for i, v in enumerate(nums):
            item[cols[i] if i < len(cols) else f"valor_extra_{i-len(cols)+1}"] = v

        itens.append(item)

    return itens


def parse_medidores(txt: str) -> list:
    def is_unico(tok: str) -> bool:
        return tok.strip().lower() in ("único", "unico")

    medidores = []
    for raw in txt.splitlines():
        line = clean_spaces(raw) or ""
        if "Energia" not in line or not any(is_unico(t) for t in line.split()):
            continue

        parts = line.split()
        if not parts or not re.fullmatch(r"\d+", parts[0] or ""):
            continue

        try:
            unico_idx = next(i for i, p in enumerate(parts) if is_unico(p))
        except StopIteration:
            continue

        tipo = " ".join(parts[1:unico_idx]).strip() or "Energia"
        start = unico_idx + 1
        if len(parts) < start + 5:
            continue

        ant, atu, const, fator, tot = parts[start : start + 5]
        medidores.append(
            {
                "medidor": parts[0],
                "tipo": tipo,
                "posto": "Único",
                "leitura_anterior": br2float(ant),
                "leitura_atual": br2float(atu),
                "constante": br2float(const),
                "fator": br2float(fator),
                "total_apurado": br2float(tot),
            }
        )

    return medidores


def make_item_id(codigo, unidade_consumidora, tarifa, vencimento_str):
    if tarifa is None or (isinstance(tarifa, float) and pd.isna(tarifa)):
        tarifa_s = ""
    else:
        tarifa_s = str(tarifa).strip().replace(",", ".")
        tarifa_s = re.sub(r"[^0-9\.]", "", tarifa_s).replace(".", "")

    yymmdd = ""
    if vencimento_str:
        try:
            dt = datetime.strptime(str(vencimento_str).strip(), "%d/%m/%Y")
            yymmdd = dt.strftime("%y%m%d")
        except Exception:
            pass

    return f"{codigo}{unidade_consumidora}{tarifa_s}{yymmdd}"


def parse_fatura(pdf_path: str) -> ResultadoParsing:
    arquivo = Path(pdf_path).name
    erros: List[str] = []
    alertas: List[str] = []

    try:
        txt = read_pdf_text(pdf_path)
    except Exception as e:
        return ResultadoParsing(False, arquivo, {}, {}, {}, pd.DataFrame(), pd.DataFrame(), [f"Erro: {e}"], [])

    header = parse_header(txt)
    periodo = parse_periodo_leituras(txt)
    nf = parse_nf(txt)
    itens = parse_itens(txt)
    medidores = parse_medidores(txt)

    unidade_consumidora_validada, uc_erro = _validate_unidade_consumidora(
        header.get("unidade_consumidora"),
        cliente_numero=header.get("cliente_numero"),
        nf_numero=nf.get("numero"),
    )
    header["unidade_consumidora"] = unidade_consumidora_validada
    if uc_erro:
        erros.append(uc_erro)

    if not itens:
        alertas.append("Sem itens tarifarios")

    df_itens = pd.DataFrame(itens) if itens else pd.DataFrame()

    if not df_itens.empty:
        if "quantidade" in df_itens.columns:
            df_itens = df_itens.rename(columns={"quantidade": "quantidade_registrada"})

        for c in [
            "quantidade_registrada",
            "tarifa",
            "valor",
            "pis_valor",
            "cofins_base",
            "icms_aliquota",
            "icms_valor",
            "tarifa_sem_trib",
        ]:
            if c in df_itens.columns:
                df_itens[c] = pd.to_numeric(df_itens[c], errors="coerce")

        df_itens["unidade_consumidora"] = header.get("unidade_consumidora")
        df_itens["cliente_numero"] = header.get("cliente_numero")
        df_itens["referencia"] = header.get("referencia")
        df_itens["vencimento"] = header.get("vencimento")
        df_itens["total_pagar"] = header.get("total_pagar")
        df_itens["nome"] = header.get("nome")
        df_itens["cnpj"] = header.get("cnpj_cpf")
        df_itens["cep"] = header.get("cep")
        df_itens["cidade_uf"] = header.get("cidade_uf")
        df_itens["grupo_subgrupo_tensao"] = header.get("grupo_subgrupo_tensao")
        df_itens["classe_modalidade"] = header.get("classe_modalidade")

        df_itens["leitura_anterior"] = as_text_or_none(periodo.get("leitura_anterior"))
        df_itens["leitura_atual"] = as_text_or_none(periodo.get("leitura_atual"))
        df_itens["dias"] = periodo.get("dias")
        df_itens["proxima_leitura"] = as_text_or_none(periodo.get("proxima_leitura"))

        df_itens["numero"] = nf.get("numero")
        df_itens["serie"] = nf.get("serie")
        df_itens["data_emissao"] = as_text_or_none(nf.get("data_emissao"))

        df_itens["id"] = df_itens.apply(
            lambda r: make_item_id(
                r.get("codigo"),
                r.get("unidade_consumidora"),
                r.get("tarifa"),
                r.get("vencimento"),
            ),
            axis=1,
        )

        if "dias" in df_itens.columns:
            df_itens["dias"] = pd.to_numeric(df_itens["dias"], errors="coerce").astype("Int64")

        df_itens = df_itens[[c for c in df_itens.columns if not c.startswith("valor_extra")]]

    df_medidores = pd.DataFrame(medidores) if medidores else pd.DataFrame()

    if not df_medidores.empty:
        df_medidores["unidade_consumidora"] = header.get("unidade_consumidora")
        df_medidores["cliente_numero"] = header.get("cliente_numero")
        df_medidores["referencia"] = header.get("referencia")
        df_medidores["nome"] = header.get("nome")
        df_medidores["nota_fiscal_numero"] = nf.get("numero")

        df_medidores["id"] = df_medidores.apply(
            lambda r: hashlib.sha256(
                f"{r.get('unidade_consumidora','')}|{r.get('cliente_numero','')}|{r.get('referencia','')}|{r.get('nota_fiscal_numero','')}|{r.get('medidor','')}|{r.get('tipo','')}|{r.get('posto','')}".encode()
            ).hexdigest(),
            axis=1,
        )

    return ResultadoParsing(
        len(erros) == 0,
        arquivo,
        header,
        periodo,
        nf,
        df_itens,
        df_medidores,
        erros,
        alertas,
    )


def processar_lote_faturas(pdf_paths: List[str], progress_callback=None) -> Dict[str, Any]:
    resultados = []
    df_itens_all, df_medidores_all = [], []
    total = len(pdf_paths)

    for i, pdf_path in enumerate(pdf_paths):
        resultado = parse_fatura(pdf_path)
        resultados.append(resultado)

        if not resultado.df_itens.empty:
            df_itens_all.append(resultado.df_itens)
        if not resultado.df_medidores.empty:
            df_medidores_all.append(resultado.df_medidores)

        if progress_callback:
            progress_callback((i + 1) / total, resultado.arquivo)

    return {
        "total": total,
        "sucesso": sum(1 for r in resultados if r.sucesso),
        "erros": sum(1 for r in resultados if not r.sucesso),
        "resultados": resultados,
        "df_itens": pd.concat(df_itens_all, ignore_index=True) if df_itens_all else pd.DataFrame(),
        "df_medidores": pd.concat(df_medidores_all, ignore_index=True) if df_medidores_all else pd.DataFrame(),
    }
