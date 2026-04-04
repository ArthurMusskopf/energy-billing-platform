from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pdfplumber


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
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def br2float(s: Any) -> Optional[float]:
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except Exception:
        return None


def clean_spaces(s: Any) -> Optional[str]:
    if s is None:
        return None
    return re.sub(r"\s+", " ", str(s)).strip()


def safe_search(pattern: str, text: str, flags: int = 0) -> Optional[str]:
    match = re.search(pattern, text, flags)
    if not match:
        return None
    return (match.group(1) if match.groups() else match.group(0)).strip()


def as_text_or_none(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _split_lines(txt: str) -> List[str]:
    return [clean_spaces(line) or "" for line in txt.splitlines()]


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
    return digits.lstrip("0") or "0"


def _line_numeric_candidate(line: str) -> Optional[str]:
    text = (line or "").strip()
    if not text:
        return None
    if re.search(r"[A-Za-zÀ-ÿ]", text):
        return None
    digits = re.sub(r"\D+", "", text)
    if re.fullmatch(r"\d{7,12}", digits or ""):
        return digits
    return None


def _cleanup_header_text(value: Optional[str]) -> Optional[str]:
    text = clean_spaces(value)
    if not text:
        return None

    text = re.split(
        r"\b(?:Cliente|CPF/CNPJ|ENDERECO|CEP|CIDADE|Grupo/Subgrupo|NOTA FISCAL|Etapa|Consulte Chave|https?://)\b\s*:?",
        text,
        maxsplit=1,
        flags=re.I,
    )[0]

    text = text.strip(" -:")
    return text or None


def parse_cliente_numero(txt: str) -> Optional[str]:
    patterns = [
        r"\bCliente\s*:\s*0*([0-9]{5,12})\b",
        r"\bC[oó]digo\s+do\s+Cliente\s*:\s*0*([0-9]{5,12})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, txt, flags=re.I)
        if match:
            return _normalize_numeric_code(match.group(1))
    return None


def parse_classe_modalidade(txt: str) -> Optional[str]:
    lines = [line for line in _split_lines(txt) if line]

    stop = min(len(lines), 20)
    for index, line in enumerate(lines[:stop]):
        if re.search(r"\b(?:Cliente|NOME)\s*:", line, flags=re.I):
            stop = index
            break

    for line in lines[:stop]:
        if re.search(r"\bB\d\b", line) and re.search(r"(MONO|BI|TRI|MONOF|BIF|TRIF)", line, flags=re.I):
            return _normalize_fases_truncadas(line)

    for line in lines[:stop]:
        if re.search(r"(MONO|BI|TRI|MONOF|BIF|TRIF)", line, flags=re.I):
            return _normalize_fases_truncadas(line)

    pattern = (
        r"Classifica(?:ç|c)ão\s*/\s*Modalidade\s*Tarif[aá]ria\s*/\s*Tipo\s*de\s*Fornecimento"
        r"\s*[:\-]?\s*(?:\n\s*)?([^\n]+)"
    )
    value = safe_search(pattern, txt, flags=re.I)
    return _normalize_fases_truncadas(value) if value else None


def infer_n_fases(classe_modalidade: Optional[str]) -> Optional[int]:
    if not classe_modalidade:
        return None
    text = clean_spaces(classe_modalidade).upper()
    if "TRIF" in text:
        return 3
    if "BIF" in text:
        return 2
    if "MONOF" in text or "MONO" in text:
        return 1
    return None


def parse_nome(lines: List[str]) -> Optional[str]:
    for index, line in enumerate(lines):
        if not re.search(r"^NOME\s*:", line, flags=re.I):
            continue

        after = re.sub(r"^NOME\s*:\s*", "", line, flags=re.I).strip()
        parts: List[str] = []
        if after:
            parts.append(after)

        cursor = index + 1
        while cursor < len(lines):
            nxt = lines[cursor].strip()
            if not nxt:
                cursor += 1
                continue
            if re.search(r"^(CPF/CNPJ|ENDERECO|CEP|CIDADE|Cliente|NOTA FISCAL)\s*:", nxt, flags=re.I):
                break
            if _line_numeric_candidate(nxt):
                break
            if re.search(r"\b(?:Cliente|NOTA FISCAL|Etapa|Consulte Chave|https?://)\b", nxt, flags=re.I):
                break
            parts.append(nxt)
            cursor += 1

        return _cleanup_header_text(" ".join(parts))

    return None


def parse_endereco(lines: List[str]) -> Optional[str]:
    for index, line in enumerate(lines):
        if not re.search(r"^ENDERECO\s*:", line, flags=re.I):
            continue

        after = re.sub(r"^ENDERECO\s*:\s*", "", line, flags=re.I).strip()
        parts: List[str] = []

        if after:
            base = _cleanup_header_text(after)
            if base:
                parts.append(base)

            base_upper = (base or "").upper()
            needs_continuation = after.rstrip().endswith("-") or base_upper.endswith("PINH")
            if needs_continuation:
                cursor = index + 1
                while cursor < len(lines):
                    nxt = lines[cursor].strip()
                    if not nxt:
                        cursor += 1
                        continue
                    if re.search(r"^(CEP|CIDADE|Grupo/Subgrupo|CPF/CNPJ|NOME)\s*:", nxt, flags=re.I):
                        break
                    nxt_clean = _cleanup_header_text(nxt)
                    if nxt_clean:
                        if parts and (parts[-1].endswith("-") or parts[-1].upper().endswith("PINH")):
                            parts[-1] = parts[-1].rstrip(" -") + " - " + nxt_clean
                        else:
                            parts.append(nxt_clean)
                    break

            return _cleanup_header_text(" ".join(parts))

        previous_parts: List[str] = []
        cursor = index - 1
        while cursor >= 0:
            prv = lines[cursor].strip()
            if not prv:
                cursor -= 1
                continue
            if re.search(r"^(CPF/CNPJ|NOME|Cliente|NOTA FISCAL|CEP|CIDADE)\s*:", prv, flags=re.I):
                break
            prv_clean = _cleanup_header_text(prv)
            if prv_clean:
                previous_parts.insert(0, prv_clean)
            cursor -= 1

        next_parts: List[str] = []
        cursor = index + 1
        while cursor < len(lines):
            cur = lines[cursor].strip()
            if not cur:
                cursor += 1
                continue
            if re.search(r"^(CEP|CIDADE|Grupo/Subgrupo|Cliente|NOTA FISCAL)\s*:", cur, flags=re.I):
                break
            cur_clean = _cleanup_header_text(cur)
            if cur_clean:
                next_parts.append(cur_clean)
            if not cur.rstrip().endswith("-") and not (cur_clean or "").upper().endswith("PINH"):
                break
            cursor += 1

        joined = " ".join(previous_parts + next_parts)
        return _cleanup_header_text(joined)

    return None


def parse_cep(lines: List[str]) -> Optional[str]:
    txt = "\n".join(lines)
    match = re.search(r"\bCEP\s*:\s*([0-9\-]{8,10})", txt, flags=re.I)
    return match.group(1) if match else None


def parse_cidade_uf(lines: List[str]) -> Optional[str]:
    txt = "\n".join(lines)
    match = re.search(
        r"\bCIDADE\s*:\s*([A-ZÇÃÂÉÊÍÓÔÕÚÜ\s]+?\s+[A-Z]{2})(?=\s+Grupo/Subgrupo|\s+https?://|$)",
        txt,
        flags=re.I,
    )
    return clean_spaces(match.group(1)) if match else None


def parse_grupo_subgrupo_tensao(txt: str) -> Optional[str]:
    match = re.search(r"Grupo/Subgrupo\s*Tens[aã]o:\s*([A-Z]/B\d+)", txt, flags=re.I)
    if match:
        return match.group(1)

    match = re.search(r"Grupo/Subgrupo\s*Tens[aã]o:\s*([^\n]+)", txt, flags=re.I)
    if not match:
        return None

    value = re.split(
        r"\s+(?:Consulte|https?://|Chave de Acesso|Protocolo)\b",
        clean_spaces(match.group(1)),
        maxsplit=1,
        flags=re.I,
    )[0]
    return value or None


def parse_unidade_consumidora(
    txt: str,
    cliente_numero: Optional[str] = None,
    nf_numero: Optional[str] = None,
) -> Optional[str]:
    cliente_norm = _normalize_numeric_code(cliente_numero)
    nf_norm = _normalize_numeric_code(nf_numero)
    lines = _split_lines(txt)
    candidates: List[tuple[int, str]] = []

    def add_candidate(value: str, score: int) -> None:
        normalized = _normalize_numeric_code(value)
        if not normalized:
            return
        if len(normalized) < 7 or len(normalized) > 12:
            return
        if normalized in {cliente_norm, nf_norm}:
            return
        if len(normalized) >= 11:
            return
        candidates.append((score, normalized))

    cpf_index = next(
        (index for index, line in enumerate(lines[:15]) if re.search(r"^CPF/CNPJ", line, flags=re.I)),
        min(len(lines), 15),
    )
    for index, line in enumerate(lines[:cpf_index]):
        candidate = _line_numeric_candidate(line)
        if candidate:
            add_candidate(candidate, 200 - index)

    for index, line in enumerate(lines):
        if not re.search(r"Unidade\s+Consumidora", line, flags=re.I):
            continue

        for cursor in range(index + 1, min(index + 5, len(lines))):
            candidate = _line_numeric_candidate(lines[cursor])
            if candidate:
                add_candidate(candidate, 180 - (cursor - index))

        for match in re.findall(r"\b0*([0-9]{7,12})\b", " ".join(lines[index : index + 4])):
            add_candidate(match, 150)

    match = re.search(r"Unidade\s+Consumidora\s*\n?\s*0*([0-9]{7,12})", txt, flags=re.I)
    if match:
        add_candidate(match.group(1), 190)

    for index, line in enumerate(lines):
        if re.fullmatch(r"Unidade Consumidora(?: Nosso Número Referência Vencimento)?", line, flags=re.I):
            for cursor in range(index + 1, min(index + 5, len(lines))):
                for match in re.findall(r"\b0*([0-9]{7,12})\b", lines[cursor]):
                    add_candidate(match, 170 - (cursor - index))

    for line in lines:
        if re.search(
            r"Iluminação pública|Chave de Acesso|Protocolo|23790|836[0-9]|BRADESCO|PAGUE COM PIX|D[ÉE]BITO AUTOM|Consulte Chave",
            line,
            flags=re.I,
        ):
            continue
        if re.search(r"NOTA FISCAL", line, flags=re.I):
            continue
        for match in re.findall(r"(?<!\d)0*([0-9]{7,12})(?![\d/])", line):
            add_candidate(match, 40)

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return candidates[0][1]


def parse_periodo_leituras(txt: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "leitura_anterior": None,
        "leitura_atual": None,
        "dias": None,
        "proxima_leitura": None,
    }

    upper_limit = txt.find("(0D)")
    text_window = txt[:upper_limit] if upper_limit != -1 else txt

    patterns = [
        r"([0-9]{2}/[0-9]{2}/[0-9]{4})\s+([0-9]{2}/[0-9]{2}/[0-9]{4})\s+([0-9]{1,3})(?:\s+(?:Lida|Lido|Lidas|Lidos))?\s+([0-9]{2}/[0-9]{2}/[0-9]{4})",
        r"Leitura\s+Anterior\s+([0-9]{2}/[0-9]{2}/[0-9]{4}).*?Leitura\s+Atual\s+([0-9]{2}/[0-9]{2}/[0-9]{4}).*?Dias\s+([0-9]{1,3}).*?Pr[oó]xima\s+Leitura\s+([0-9]{2}/[0-9]{2}/[0-9]{4})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text_window, flags=re.I | re.S)
        if match:
            out.update(
                {
                    "leitura_anterior": match.group(1),
                    "leitura_atual": match.group(2),
                    "dias": int(match.group(3)),
                    "proxima_leitura": match.group(4),
                }
            )
            return out

    def first_date_after(label_regex: str, text: str, lookahead: int = 180) -> Optional[str]:
        for match in re.finditer(label_regex, text, flags=re.I | re.S):
            segment = text[match.end() : match.end() + lookahead]
            date_match = re.search(r"([0-9]{2}/[0-9]{2}/[0-9]{4})", segment)
            if date_match:
                return date_match.group(1)
        return None

    leitura_anterior = first_date_after(r"Leit(?:\.|ura)?\s*Anterior", txt)
    leitura_atual = first_date_after(r"Leit(?:\.|ura)?\s*Atual", txt)
    proxima_leitura = first_date_after(r"Pr(?:[óo]x\.?|[óo]xima)\s*Leit(?:\.|ura)?", txt)

    dias = None
    if leitura_anterior and leitura_atual and proxima_leitura:
        start = txt.find(leitura_atual)
        end = txt.find(proxima_leitura)
        between = txt[start + len(leitura_atual) : end] if start != -1 and end != -1 else txt
        days_match = re.search(r"\b([0-9]{1,3})\b", between)
        if days_match:
            dias = int(days_match.group(1))

    if leitura_anterior and leitura_atual and proxima_leitura and dias is not None:
        out.update(
            {
                "leitura_anterior": leitura_anterior,
                "leitura_atual": leitura_atual,
                "dias": dias,
                "proxima_leitura": proxima_leitura,
            }
        )

    return out


def parse_nf(txt: str) -> Dict[str, Any]:
    match = re.search(
        r"NOTA\s+FISCAL\s+N[ºO]\s*([0-9]+)\s+SERIE:?\s*([0-9]+)\s+DATA\s+EMISS(?:A|Ã)O:\s*([0-9/]+)",
        txt,
        flags=re.I,
    )
    if not match:
        return {}
    return {
        "numero": match.group(1),
        "serie": match.group(2),
        "data_emissao": match.group(3),
    }


def parse_header(txt: str) -> Dict[str, Any]:
    lines = _split_lines(txt)
    nf = parse_nf(txt)

    header: Dict[str, Any] = {}
    header["classe_modalidade"] = parse_classe_modalidade(txt)
    header["n_fases_parseado"] = infer_n_fases(header.get("classe_modalidade"))
    header["cliente_numero"] = parse_cliente_numero(txt)
    header["unidade_consumidora"] = parse_unidade_consumidora(
        txt,
        cliente_numero=header.get("cliente_numero"),
        nf_numero=nf.get("numero"),
    )

    ref_match = re.search(r"\b(\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+R\$?\s*([0-9\.,]+)", txt)
    if ref_match:
        header["referencia"] = ref_match.group(1)
        header["vencimento"] = ref_match.group(2)
        header["total_pagar"] = br2float(ref_match.group(3))
    else:
        header["referencia"] = None
        header["vencimento"] = None
        header["total_pagar"] = None

    header["nome"] = parse_nome(lines)
    header["cnpj_cpf"] = _cleanup_header_text(safe_search(r"CPF/CNPJ:\s*([^\n]+)", txt))
    header["endereco"] = parse_endereco(lines)
    header["cep"] = parse_cep(lines)
    header["cidade_uf"] = parse_cidade_uf(lines)
    header["grupo_subgrupo_tensao"] = parse_grupo_subgrupo_tensao(txt)

    return header


def parse_itens(txt: str) -> List[Dict[str, Any]]:
    itens: List[Dict[str, Any]] = []

    for raw_line in txt.splitlines():
        line = clean_spaces(raw_line) or ""
        if not line.startswith("("):
            continue

        match = re.match(r"^\((\w{1,2})\)\s*(.*)$", line, flags=re.I)
        if not match:
            continue

        codigo = (match.group(1) or "").upper()
        rest = (match.group(2) or "").strip()
        if not rest:
            continue

        unit_match = re.search(r"\b(KWH|MWH|KVARH|KVAH|UN)\b", rest, flags=re.I)
        if unit_match:
            unidade = unit_match.group(1).upper()
            descricao = rest[: unit_match.start()].strip()
            tail = rest[unit_match.end() :].strip()
        else:
            number_match = re.search(r"[-+]?\d[\d\.,]*", rest)
            if not number_match:
                continue
            unidade = "UN"
            descricao = rest[: number_match.start()].strip()
            tail = rest[number_match.start() :].strip()

        if not descricao or not tail:
            continue

        values = [br2float(token) for token in tail.split()]
        item: Dict[str, Any] = {
            "codigo": codigo,
            "descricao": descricao,
            "unidade": unidade,
        }

        item_columns = [
            "quantidade",
            "tarifa",
            "valor",
            "pis_valor",
            "cofins_base",
            "icms_aliquota",
            "icms_valor",
            "tarifa_sem_trib",
        ]

        for index, value in enumerate(values):
            column_name = item_columns[index] if index < len(item_columns) else f"valor_extra_{index - len(item_columns) + 1}"
            item[column_name] = value

        itens.append(item)

    return itens


def parse_medidores(txt: str) -> List[Dict[str, Any]]:
    medidores: List[Dict[str, Any]] = []
    pattern = re.compile(
        r"^(?P<medidor>[A-Za-z0-9]+)\s+"
        r"(?P<tipo>Energia(?:\s+injetada)?)\s+"
        r"(?P<posto>Único|Unico)\s+"
        r"(?P<anterior>[\d\.,]+)\s+"
        r"(?P<atual>[\d\.,]+)\s+"
        r"(?P<constante>[\d\.,]+)\s+"
        r"(?P<fator>[\d\.,]+)\s+"
        r"(?P<total>[\d\.,]+)$",
        flags=re.I,
    )

    for raw_line in txt.splitlines():
        line = clean_spaces(raw_line) or ""
        if "Energia" not in line or ("Único" not in line and "Unico" not in line):
            continue

        match = pattern.match(line)
        if not match:
            continue

        medidores.append(
            {
                "medidor": match.group("medidor"),
                "tipo": clean_spaces(match.group("tipo")),
                "posto": "Único",
                "leitura_anterior": as_text_or_none(match.group("anterior")),
                "leitura_atual": as_text_or_none(match.group("atual")),
                "constante": br2float(match.group("constante")),
                "fator": br2float(match.group("fator")),
                "total_apurado": br2float(match.group("total")),
            }
        )

    return medidores


def make_item_id(codigo: Any, unidade_consumidora: Any, tarifa: Any, vencimento_str: Any) -> str:
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


def _dedupe_ids(values: List[str]) -> List[str]:
    counters: Dict[str, int] = {}
    result: List[str] = []
    for value in values:
        counters[value] = counters.get(value, 0) + 1
        if counters[value] == 1:
            result.append(value)
        else:
            result.append(f"{value}-{counters[value]}")
    return result


def parse_fatura(pdf_path: str) -> ResultadoParsing:
    arquivo = Path(pdf_path).name
    erros: List[str] = []
    alertas: List[str] = []

    try:
        txt = read_pdf_text(pdf_path)
    except Exception as exc:
        return ResultadoParsing(
            False,
            arquivo,
            {},
            {},
            {},
            pd.DataFrame(),
            pd.DataFrame(),
            [f"Erro: {exc}"],
            [],
        )

    header = parse_header(txt)
    periodo = parse_periodo_leituras(txt)
    nf = parse_nf(txt)
    itens = parse_itens(txt)
    medidores = parse_medidores(txt)

    uc = _normalize_numeric_code(header.get("unidade_consumidora"))
    cliente = _normalize_numeric_code(header.get("cliente_numero"))
    nf_numero = _normalize_numeric_code(nf.get("numero"))

    if not uc:
        erros.append("UC nao encontrada")
    elif uc in {cliente, nf_numero}:
        header["unidade_consumidora"] = None
        erros.append("UC suspeita: coincide com cliente ou nota fiscal")

    if not periodo.get("leitura_anterior") or not periodo.get("leitura_atual"):
        alertas.append("Periodo de leitura incompleto")

    if not itens:
        alertas.append("Sem itens tarifarios")

    if not medidores:
        alertas.append("Sem medidores")

    df_itens = pd.DataFrame(itens) if itens else pd.DataFrame()

    if not df_itens.empty:
        if "quantidade" in df_itens.columns:
            df_itens = df_itens.rename(columns={"quantidade": "quantidade_registrada"})

        for column in [
            "quantidade_registrada",
            "tarifa",
            "valor",
            "pis_valor",
            "cofins_base",
            "icms_aliquota",
            "icms_valor",
            "tarifa_sem_trib",
        ]:
            if column in df_itens.columns:
                df_itens[column] = pd.to_numeric(df_itens[column], errors="coerce")

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
            lambda row: make_item_id(
                row.get("codigo"),
                row.get("unidade_consumidora"),
                row.get("tarifa"),
                row.get("vencimento"),
            ),
            axis=1,
        )
        df_itens["id"] = _dedupe_ids(df_itens["id"].tolist())

        if "dias" in df_itens.columns:
            df_itens["dias"] = pd.to_numeric(df_itens["dias"], errors="coerce").astype("Int64")

        df_itens = df_itens[[column for column in df_itens.columns if not column.startswith("valor_extra")]]

    df_medidores = pd.DataFrame(medidores) if medidores else pd.DataFrame()

    if not df_medidores.empty:
        df_medidores["unidade_consumidora"] = header.get("unidade_consumidora")
        df_medidores["cliente_numero"] = header.get("cliente_numero")
        df_medidores["referencia"] = header.get("referencia")
        df_medidores["nome"] = header.get("nome")
        df_medidores["nota_fiscal_numero"] = nf.get("numero")

        for column in ["medidor", "tipo", "posto", "leitura_anterior", "leitura_atual"]:
            if column in df_medidores.columns:
                df_medidores[column] = df_medidores[column].map(as_text_or_none)

        df_medidores["id"] = df_medidores.apply(
            lambda row: hashlib.sha256(
                (
                    f"{row.get('unidade_consumidora', '')}|"
                    f"{row.get('cliente_numero', '')}|"
                    f"{row.get('referencia', '')}|"
                    f"{row.get('nota_fiscal_numero', '')}|"
                    f"{row.get('medidor', '')}|"
                    f"{row.get('tipo', '')}|"
                    f"{row.get('posto', '')}"
                ).encode()
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
    resultados: List[ResultadoParsing] = []
    itens_frames: List[pd.DataFrame] = []
    medidores_frames: List[pd.DataFrame] = []
    total = len(pdf_paths)

    for index, pdf_path in enumerate(pdf_paths):
        resultado = parse_fatura(pdf_path)
        resultados.append(resultado)

        if not resultado.df_itens.empty:
            itens_frames.append(resultado.df_itens)
        if not resultado.df_medidores.empty:
            medidores_frames.append(resultado.df_medidores)

        if progress_callback:
            progress_callback((index + 1) / total, resultado.arquivo)

    return {
        "total": total,
        "sucesso": sum(1 for resultado in resultados if resultado.sucesso),
        "erros": sum(1 for resultado in resultados if not resultado.sucesso),
        "resultados": resultados,
        "df_itens": pd.concat(itens_frames, ignore_index=True) if itens_frames else pd.DataFrame(),
        "df_medidores": pd.concat(medidores_frames, ignore_index=True) if medidores_frames else pd.DataFrame(),
    }
