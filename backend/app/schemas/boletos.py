from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class BoletoListItemSchema(BaseModel):
    id: str
    workflow_id: Optional[str] = None
    nota_fiscal: Optional[str] = None
    referencia: Optional[str] = None
    vencimento: Optional[str] = None
    unidade_consumidora: Optional[str] = None
    cliente_numero: Optional[str] = None
    nome: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    cep: Optional[str] = None
    cidade_uf: Optional[str] = None
    desconto_contratado: Optional[float] = None
    subvencao: Optional[float] = None
    status_cliente: Optional[str] = None
    status_validacao: Optional[str] = None
    status_calculo: Optional[str] = None
    status_emissao: Optional[str] = None
    leitura_anterior: Optional[str] = None
    leitura_atual: Optional[str] = None
    dias: Optional[int] = None
    proxima_leitura: Optional[str] = None
    energia_compensada: Optional[float] = None
    tarifa_sem_desconto: Optional[float] = None
    tarifa_com_desconto: Optional[float] = None
    percentual_desconto: Optional[float] = None
    bandeiras: Optional[float] = None
    bandeiras_com_desconto: Optional[float] = None
    valor_total: Optional[float] = None
    valor_concessionaria: Optional[float] = None
    economia_gerada: Optional[float] = None
    status: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BoletosListResponseSchema(BaseModel):
    items: List[BoletoListItemSchema]
    total: int
    limit: int
    offset: int
