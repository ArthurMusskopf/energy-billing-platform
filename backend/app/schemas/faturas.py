from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


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
    leitura_anterior: Optional[str] = None
    leitura_atual: Optional[str] = None
    dias: Optional[int] = None
    proxima_leitura: Optional[str] = None
    nota_fiscal_serie: Optional[str] = None
    nota_fiscal_emissao: Optional[str] = None
    cidade_uf: Optional[str] = None
    cep: Optional[str] = None
    arquivo_nome_original: Optional[str] = None
    arquivo_hash: Optional[str] = None
    pdf_uri: Optional[str] = None
    is_inedita: Optional[bool] = None
    duplicada_de: Optional[str] = None
    status_parse: Optional[str] = None
    status_validacao: Optional[str] = None
    validado_por: Optional[str] = None
    validado_em: Optional[str] = None
    status_calculo: Optional[str] = None
    calculado_em: Optional[str] = None
    status_emissao: Optional[str] = None
    emitido_em: Optional[str] = None
    observacoes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class FaturaAlertaSchema(BaseModel):
    id: str
    campo: str
    tipo: Literal["warning", "error"] = "warning"
    mensagem: str
    valor_atual: float = 0
    valor_esperado: float = 0
    desvio_percentual: float = 0


class FaturaItemDetalheSchema(BaseModel):
    id: str
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    unidade: Optional[str] = None
    quantidade_registrada: Optional[float] = None
    tarifa: Optional[float] = None
    valor: Optional[float] = None
    pis_valor: Optional[float] = None
    cofins_base: Optional[float] = None
    icms_aliquota: Optional[float] = None
    icms_valor: Optional[float] = None
    tarifa_sem_trib: Optional[float] = None


class FaturaMedidorDetalheSchema(BaseModel):
    id: str
    medidor: Optional[str] = None
    tipo: Optional[str] = None
    posto: Optional[str] = None
    leitura_anterior: Optional[str] = None
    leitura_atual: Optional[str] = None
    total_apurado: Optional[float] = None


class FaturaCadastroClienteSchema(BaseModel):
    unidade_consumidora: Optional[str] = None
    cliente_numero: Optional[str] = None
    nome: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    cep: Optional[str] = None
    cidade_uf: Optional[str] = None
    desconto_contratado: Optional[float] = None
    subvencao: Optional[float] = None
    status: Optional[str] = None
    n_fases: Optional[int] = None
    custo_disp: Optional[float] = None
    origem: Optional[str] = None
    campos_pendentes: List[str] = Field(default_factory=list)
    cadastro_minimo_completo: bool = False
    elegivel_para_calculo: bool = False


class FaturaDetalheSchema(FaturaWorkflowItemSchema):
    itens: List[FaturaItemDetalheSchema]
    medidores: List[FaturaMedidorDetalheSchema]
    alertas: List[FaturaAlertaSchema]
    cadastro_cliente: FaturaCadastroClienteSchema
    campos_pendentes_cadastro: List[str] = Field(default_factory=list)
    pode_validar_calcular: bool = False


class FaturaValidacaoRequestSchema(BaseModel):
    usuario: Optional[str] = None


class FaturaRevisaoCadastroRequestSchema(BaseModel):
    unidade_consumidora: Optional[str] = None
    cliente_numero: Optional[str] = None
    nome: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    cep: Optional[str] = None
    cidade_uf: Optional[str] = None
    desconto_contratado: Optional[float] = None
    subvencao: Optional[float] = None
    status: Optional[str] = None
    n_fases: Optional[int] = None
    custo_disp: Optional[float] = None


class FaturaRevisaoRequestSchema(BaseModel):
    usuario: Optional[str] = None
    unidade_consumidora: Optional[str] = None
    cliente_numero: Optional[str] = None
    nome: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    referencia: Optional[str] = None
    vencimento: Optional[str] = None
    leitura_anterior: Optional[str] = None
    leitura_atual: Optional[str] = None
    dias: Optional[int] = None
    proxima_leitura: Optional[str] = None
    cep: Optional[str] = None
    cidade_uf: Optional[str] = None
    cadastro_cliente: Optional[FaturaRevisaoCadastroRequestSchema] = None


class FaturaValidacaoResponseSchema(BaseModel):
    id: str
    status_validacao: str
    validado_por: Optional[str] = None
    validado_em: Optional[str] = None
    updated_at: Optional[str] = None
    status_calculo: Optional[str] = None
    calculado_em: Optional[str] = None


class FaturaCalculoResponseSchema(BaseModel):
    id: str
    status_calculo: str
    calculado_em: Optional[str] = None
    table: str
    affected_rows: int
    missing_clientes: List[str]
    missing_reason: Dict[str, str]
    detail: Optional[str] = None


class FaturasParseResponseSchema(BaseModel):
    total_arquivos: int
    parseadas_com_sucesso: int
    erros_parse: int
    resumo: FaturaParseResumoSchema
    arquivos_com_erro: List[FaturaParseErroArquivoSchema]
    workflow: List[FaturaWorkflowItemSchema]
    salvar_auto_executado: bool
    bigquery_result: Optional[Dict[str, Any]] = None


class FaturasListResponseSchema(BaseModel):
    items: List[FaturaWorkflowItemSchema]
    total: int
    limit: int
    offset: int
