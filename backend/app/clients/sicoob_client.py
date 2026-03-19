from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from app.core.config import get_settings

settings = get_settings()


@dataclass
class SicoobConfig:
    base_url: str
    client_id: str
    access_token: str
    numero_cliente: int
    codigo_modalidade: int
    numero_contrato_cobranca: int
    numero_conta_corrente: int = 0


def _digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")


def get_sicoob_config() -> SicoobConfig:
    return SicoobConfig(
        base_url=str(settings.sicoob_base_url).rstrip("/"),
        client_id=str(settings.sicoob_client_id or ""),
        access_token=str(settings.sicoob_access_token or ""),
        numero_cliente=int(settings.sicoob_numero_cliente or 0),
        codigo_modalidade=int(settings.sicoob_codigo_modalidade or 1),
        numero_contrato_cobranca=int(settings.sicoob_numero_contrato_cobranca or 1),
        numero_conta_corrente=int(settings.sicoob_numero_conta_corrente or 0),
    )


class SicoobCobrancaV3Client:
    def __init__(self, config: Optional[SicoobConfig] = None, timeout: int = 30):
        self.cfg = config or get_sicoob_config()
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cfg.access_token}",
            "client_id": self.cfg.client_id,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _raise_for_status(self, resp: requests.Response) -> None:
        if 200 <= resp.status_code < 300:
            return
        try:
            payload = resp.json()
        except Exception:
            payload = resp.text
        raise RuntimeError(f"Sicoob API erro {resp.status_code}: {payload}")

    def create_boleto(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.cfg.base_url}/boletos"
        resp = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
        self._raise_for_status(resp)
        return resp.json()

    def faixa_nosso_numero(self) -> Dict[str, Any]:
        url = f"{self.cfg.base_url}/boletos/faixas-nosso-numero"
        params = {
            "numeroCliente": self.cfg.numero_cliente,
            "codigoModalidade": self.cfg.codigo_modalidade,
            "numeroContratoCobranca": self.cfg.numero_contrato_cobranca,
        }
        resp = requests.get(url, params=params, headers=self._headers(), timeout=self.timeout)
        self._raise_for_status(resp)
        return resp.json()

    def segunda_via_pdf(
        self,
        *,
        nosso_numero: Optional[int] = None,
        linha_digitavel: Optional[str] = None,
        codigo_barras: Optional[str] = None,
        gerar_pdf: bool = True,
    ) -> Dict[str, Any]:
        url = f"{self.cfg.base_url}/boletos/segunda-via"
        params: Dict[str, Any] = {
            "numeroCliente": self.cfg.numero_cliente,
            "codigoModalidade": self.cfg.codigo_modalidade,
            "numeroContratoCobranca": self.cfg.numero_contrato_cobranca,
        }
        if nosso_numero is not None:
            params["nossoNumero"] = int(nosso_numero)
        if linha_digitavel:
            params["linhaDigitavel"] = str(linha_digitavel)
        if codigo_barras:
            params["codigoBarras"] = str(codigo_barras)
        if gerar_pdf:
            params["gerarPdf"] = "true"

        resp = requests.get(url, params=params, headers=self._headers(), timeout=self.timeout)
        self._raise_for_status(resp)
        return resp.json()

    @staticmethod
    def decode_pdf_boleto(resp_json: Dict[str, Any]) -> bytes:
        resultado = resp_json.get("resultado", {}) if isinstance(resp_json, dict) else {}
        pdf_b64 = resultado.get("pdfBoleto")
        if not pdf_b64:
            raise RuntimeError("Resposta nao trouxe 'resultado.pdfBoleto'.")
        return base64.b64decode(pdf_b64)


def build_boleto_payload_from_row(
    row: Dict[str, Any],
    *,
    cfg: Optional[SicoobConfig] = None,
    nosso_numero: int,
    data_emissao: str,
    data_vencimento: str,
    valor: float,
) -> Dict[str, Any]:
    cfg = cfg or get_sicoob_config()

    nome = str(row.get("nome") or "PAGADOR")
    cnpj_cpf = _digits(str(row.get("cnpj_cpf") or row.get("cnpj") or ""))
    cep = _digits(str(row.get("cep") or ""))
    cidade_uf = str(row.get("cidade_uf") or "")
    uf = cidade_uf.strip()[-2:] if len(cidade_uf.strip()) >= 2 else "SC"
    cidade = cidade_uf.strip()[:-2].strip() if len(cidade_uf.strip()) > 2 else "Cidade"

    payload = {
        "numeroCliente": cfg.numero_cliente,
        "codigoModalidade": cfg.codigo_modalidade,
        "numeroContaCorrente": cfg.numero_conta_corrente,
        "codigoEspecieDocumento": "DM",
        "dataEmissao": data_emissao,
        "nossoNumero": int(nosso_numero),
        "seuNumero": str(row.get("numero") or nosso_numero),
        "identificacaoBoletoEmpresa": str(row.get("numero") or nosso_numero),
        "identificacaoEmissaoBoleto": 1,
        "identificacaoDistribuicaoBoleto": 1,
        "valor": float(valor),
        "dataVencimento": data_vencimento,
        "dataLimitePagamento": data_vencimento,
        "valorAbatimento": 0,
        "tipoDesconto": 0,
        "tipoMulta": 0,
        "tipoJurosMora": 0,
        "aceite": True,
        "codigoNegativacao": 0,
        "codigoProtesto": 0,
        "pagador": {
            "numeroCpfCnpj": cnpj_cpf or "12345678900",
            "nome": nome[:80],
            "endereco": "ENDERECO NAO INFORMADO",
            "bairro": "CENTRO",
            "cidade": cidade[:40] or "Cidade",
            "cep": cep or "00000000",
            "uf": uf,
            "email": "nao-informado@acer.local",
        },
        "mensagensInstrucao": [
            f"Referencia {row.get('periodo')}",
            f"UC {row.get('unidade_consumidora')}",
            "Cobranca ACER - creditos energia",
        ],
        "gerarPdf": False,
        "numeroContratoCobranca": cfg.numero_contrato_cobranca,
    }
    return payload