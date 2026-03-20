from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel


class DashboardSerieItemSchema(BaseModel):
    mes: str
    valor: float


class DashboardTopClienteSchema(BaseModel):
    nome: str
    economia: float


class DashboardResumoResponseSchema(BaseModel):
    total_economia: float
    total_receita: float
    total_clientes: int
    energia_compensada_total: float
    economia_por_mes: List[DashboardSerieItemSchema]
    maiores_clientes: List[DashboardTopClienteSchema]
    receita_por_mes: List[DashboardSerieItemSchema]


class BoletoClienteSchema(BaseModel):
    unidade_consumidora: str
    cliente_numero: str
    nome: str
    cnpj: str
    cep: str
    cidade_uf: str
    desconto_contratado: float
    subvencao: float
    status: str


class BoletoFaturaVinculadaSchema(BaseModel):
    id: str
    referencia: str
    vencimento: str
    nota_fiscal_numero: str
    leitura_anterior: str
    leitura_atual: str
    total: float


class BoletoListItemSchema(BaseModel):
    id: str
    cliente: BoletoClienteSchema
    referencia: str
    vencimento: str
    energia_compensada: float
    tarifa_sem_desconto: float
    tarifa_com_desconto: float
    percentual_desconto: float
    bandeiras: float
    bandeiras_com_desconto: float
    valor_total: float
    economia_gerada: float
    status: Literal["pendente", "validado", "gerado"]
    faturas: List[BoletoFaturaVinculadaSchema]


class BoletosListResponseSchema(BaseModel):
    items: List[BoletoListItemSchema]
    total: int


class HistoricoEconomiaItemSchema(BaseModel):
    mes: str
    valor: float


class HistoricoFaturaItemSchema(BaseModel):
    id: str
    referencia: str
    vencimento: str
    nota_fiscal_numero: str
    total: float
    status: Literal["pendente", "validado", "erro"]


class HistoricoClienteItemSchema(BaseModel):
    unidade_consumidora: str
    cliente_numero: str
    nome: str
    cnpj: str
    cep: str
    cidade_uf: str
    desconto_contratado: float
    subvencao: float
    status: str
    historico_economia: List[HistoricoEconomiaItemSchema]
    faturas: List[HistoricoFaturaItemSchema]


class HistoricoResponseSchema(BaseModel):
    items: List[HistoricoClienteItemSchema]
