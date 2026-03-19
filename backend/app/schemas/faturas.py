from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class FaturaParseResumoSchema(BaseModel):
    total_nf: int
    ineditas: int
    repetidas: int
    parseadas: int
    erro_parse: int


class FaturaParseErroArquivoSchema(BaseModel):
    arquivo: str
    erros: List[str]


class FaturaWorkflowItemSchema(BaseModel):
    id: str
    nota_fiscal: Optional[str] = None
    unidade_consumidora: Optional[str] = None
    cliente_numero: Optional[str] = None
    nome: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    referencia: Optional[str] = None
    vencimento: Optional[str] = None
    classe_modalidade: Optional[str] = None
    grupo_subgrupo_tensao: Optional[str] = None
    total_pagar: Optional[float] = None
    arquivo_nome_original: Optional[str] = None
    arquivo_hash: Optional[str] = None
    pdf_uri: Optional[str] = None
    is_inedita: Optional[bool] = None
    duplicada_de: Optional[str] = None
    status_parse: Optional[str] = None
    status_validacao: Optional[str] = None
    status_calculo: Optional[str] = None
    status_emissao: Optional[str] = None
    observacoes: Optional[str] = None


class FaturasParseResponseSchema(BaseModel):
    total_arquivos: int
    parseadas_com_sucesso: int
    erros_parse: int
    resumo: FaturaParseResumoSchema
    arquivos_com_erro: List[FaturaParseErroArquivoSchema]
    workflow: List[FaturaWorkflowItemSchema]
    salvar_auto_executado: bool
    bigquery_result: Optional[Dict[str, Any]] = None