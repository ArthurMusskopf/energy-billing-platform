export interface FaturaItem {
  id: string;
  codigo: string;
  descricao: string;
  unidade: string;
  quantidade: number;
  tarifa: number;
  valor: number;
  pis_valor: number;
  cofins_base: number;
  icms_aliquota: number;
  icms_valor: number;
  tarifa_sem_trib: number;
}

export interface Fatura {
  id: string;
  unidade_consumidora: string;
  cliente_numero: string;
  nome: string;
  cnpj: string;
  referencia: string;
  vencimento: string;
  total: number;
  leitura_anterior: string;
  leitura_atual: string;
  dias: number;
  proxima_leitura: string;
  nota_fiscal_numero: string;
  nota_fiscal_serie: string;
  nota_fiscal_emissao: string;
  cidade_uf: string;
  cep: string;
  itens: FaturaItem[];
  status: 'pendente' | 'validado' | 'erro';
  alertas: Alerta[];
}

export interface Alerta {
  id: string;
  campo: string;
  tipo: 'warning' | 'error';
  mensagem: string;
  valor_atual: number;
  valor_esperado: number;
  desvio_percentual: number;
}

export interface Cliente {
  unidade_consumidora: string;
  cliente_numero: string;
  nome: string;
  cnpj: string;
  cep: string;
  cidade_uf: string;
  desconto_contratado: number;
  subvencao: number;
  status: 'Ativo' | 'Inativo';
}

export interface Boleto {
  id: string;
  cliente: Cliente;
  referencia: string;
  vencimento: string;
  energia_compensada: number;
  tarifa_sem_desconto: number;
  tarifa_com_desconto: number;
  percentual_desconto: number;
  bandeiras: number;
  bandeiras_com_desconto: number;
  valor_total: number;
  economia_gerada: number;
  status: 'pendente' | 'validado' | 'gerado';
  faturas: Fatura[];
}

export interface HistoricoEconomia {
  mes: string;
  valor: number;
}

export interface DashboardData {
  total_economia: number;
  total_receita: number;
  total_clientes: number;
  energia_compensada_total: number;
  economia_por_mes: HistoricoEconomia[];
  maiores_clientes: {
    nome: string;
    economia: number;
  }[];
  receita_por_mes: {
    mes: string;
    valor: number;
  }[];
}

export interface EditLog {
  id: string;
  fatura_id: string;
  campo: string;
  valor_anterior: string;
  valor_novo: string;
  usuario: string;
  data_hora: string;
}
