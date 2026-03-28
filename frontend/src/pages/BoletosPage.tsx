import { useCallback, useEffect, useState } from "react";

import { MainLayout } from "@/components/layout/MainLayout";
import { BoletoTable } from "@/components/boletos/BoletoTable";
import { BoletoSummary } from "@/components/boletos/BoletoSummary";
import { useToast } from "@/hooks/use-toast";
import { getJson } from "@/lib/api";
import { Boleto, Fatura } from "@/types";

interface ApiBoletoItem {
  id: string;
  workflow_id?: string | null;
  nota_fiscal?: string | null;
  referencia?: string | null;
  vencimento?: string | null;
  unidade_consumidora?: string | null;
  cliente_numero?: string | null;
  nome?: string | null;
  cnpj_cpf?: string | null;
  cep?: string | null;
  cidade_uf?: string | null;
  desconto_contratado?: number | null;
  subvencao?: number | null;
  status_cliente?: string | null;
  status_validacao?: string | null;
  status_calculo?: string | null;
  status_emissao?: string | null;
  leitura_anterior?: string | null;
  leitura_atual?: string | null;
  dias?: number | null;
  proxima_leitura?: string | null;
  energia_compensada?: number | null;
  tarifa_sem_desconto?: number | null;
  tarifa_com_desconto?: number | null;
  percentual_desconto?: number | null;
  bandeiras?: number | null;
  bandeiras_com_desconto?: number | null;
  valor_total?: number | null;
  valor_concessionaria?: number | null;
  economia_gerada?: number | null;
  status?: string | null;
}

interface ApiBoletosResponse {
  items: ApiBoletoItem[];
  total: number;
  limit: number;
  offset: number;
}

function mapApiBoletoStatus(status?: string | null): Boleto["status"] {
  if (status === "gerado") {
    return "gerado";
  }
  if (status === "calculada" || status === "validado") {
    return "calculada";
  }
  return "pendente";
}

function mapApiBoletoToUi(item: ApiBoletoItem): Boleto {
  const linkedFatura: Fatura = {
    id: item.workflow_id ?? item.id,
    unidade_consumidora: item.unidade_consumidora ?? "",
    cliente_numero: item.cliente_numero ?? "",
    nome: item.nome ?? "",
    cnpj: item.cnpj_cpf ?? "",
    referencia: item.referencia ?? "",
    vencimento: item.vencimento ?? "",
    total: Number(item.valor_concessionaria ?? item.valor_total ?? 0),
    leitura_anterior: item.leitura_anterior ?? "",
    leitura_atual: item.leitura_atual ?? "",
    dias: Number(item.dias ?? 0),
    proxima_leitura: item.proxima_leitura ?? "",
    nota_fiscal_numero: item.nota_fiscal ?? item.id,
    nota_fiscal_serie: "",
    nota_fiscal_emissao: "",
    cidade_uf: item.cidade_uf ?? "",
    cep: item.cep ?? "",
    itens: [],
    medidores: [],
    status: "validado",
    status_calculo: item.status_calculo ?? "",
    alertas: [],
  };

  return {
    id: item.id,
    workflow_id: item.workflow_id ?? undefined,
    nota_fiscal: item.nota_fiscal ?? item.id,
    cliente: {
      unidade_consumidora: item.unidade_consumidora ?? "",
      cliente_numero: item.cliente_numero ?? "",
      nome: item.nome ?? "",
      cnpj: item.cnpj_cpf ?? "",
      cep: item.cep ?? "",
      cidade_uf: item.cidade_uf ?? "",
      desconto_contratado: Number(item.desconto_contratado ?? 0),
      subvencao: Number(item.subvencao ?? 0),
      status: item.status_cliente === "Inativo" ? "Inativo" : "Ativo",
    },
    referencia: item.referencia ?? "",
    vencimento: item.vencimento ?? "",
    energia_compensada: Number(item.energia_compensada ?? 0),
    tarifa_sem_desconto: Number(item.tarifa_sem_desconto ?? 0),
    tarifa_com_desconto: Number(item.tarifa_com_desconto ?? 0),
    percentual_desconto: Number(item.percentual_desconto ?? 0),
    bandeiras: Number(item.bandeiras ?? 0),
    bandeiras_com_desconto: Number(item.bandeiras_com_desconto ?? 0),
    valor_total: Number(item.valor_total ?? 0),
    valor_concessionaria: Number(item.valor_concessionaria ?? 0),
    economia_gerada: Number(item.economia_gerada ?? 0),
    status: mapApiBoletoStatus(item.status),
    status_validacao: item.status_validacao ?? undefined,
    status_calculo: item.status_calculo ?? undefined,
    status_emissao: item.status_emissao ?? undefined,
    faturas: [linkedFatura],
  };
}

export default function BoletosPage() {
  const [boletos, setBoletos] = useState<Boleto[]>([]);
  const { toast } = useToast();

  const loadBoletos = useCallback(async () => {
    try {
      const response = await getJson<ApiBoletosResponse>("/boletos");
      setBoletos((response.items ?? []).map(mapApiBoletoToUi));
    } catch (error) {
      console.error(error);
      toast({
        title: "Erro ao carregar boletos",
        description: "Nao foi possivel buscar a saida operacional real em boletos_calculados.",
        variant: "destructive",
      });
    }
  }, [toast]);

  useEffect(() => {
    void loadBoletos();
  }, [loadBoletos]);

  const totalBoletos = boletos.length;
  const boletosCalculados = boletos.filter((boleto) => boleto.status === "calculada" || boleto.status === "gerado").length;
  const valorTotal = boletos.reduce((acc, boleto) => acc + boleto.valor_total, 0);
  const economiaTotal = boletos.reduce((acc, boleto) => acc + boleto.economia_gerada, 0);

  return (
    <MainLayout
      title="Saida Operacional de Boletos"
      subtitle="Visualize os registros calculados persistidos em boletos_calculados, sem emissao bancaria nesta etapa"
    >
      <div className="space-y-6 animate-fade-in">
        <BoletoSummary
          totalBoletos={totalBoletos}
          boletosCalculados={boletosCalculados}
          valorTotal={valorTotal}
          economiaTotal={economiaTotal}
        />

        <BoletoTable boletos={boletos} />
      </div>
    </MainLayout>
  );
}
