import { useCallback, useEffect, useState } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { BoletoTable } from "@/components/boletos/BoletoTable";
import { BoletoSummary } from "@/components/boletos/BoletoSummary";
import { Boleto } from "@/types";
import { useToast } from "@/hooks/use-toast";
import { getJson, postJson } from "@/lib/api";

interface ApiBoletoCliente {
  unidade_consumidora: string;
  cliente_numero: string;
  nome: string;
  cnpj: string;
  cep: string;
  cidade_uf: string;
  desconto_contratado: number;
  subvencao: number;
  status: string;
}

interface ApiBoletoFatura {
  id: string;
  referencia: string;
  vencimento: string;
  nota_fiscal_numero: string;
  leitura_anterior: string;
  leitura_atual: string;
  total: number;
}

interface ApiBoletoItem {
  id: string;
  cliente: ApiBoletoCliente;
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
  status: "pendente" | "validado" | "gerado";
  faturas: ApiBoletoFatura[];
}

interface ApiBoletosResponse {
  items: ApiBoletoItem[];
  total: number;
}

function mapApiBoletoToUi(item: ApiBoletoItem): Boleto {
  return {
    id: item.id,
    cliente: {
      unidade_consumidora: item.cliente.unidade_consumidora,
      cliente_numero: item.cliente.cliente_numero,
      nome: item.cliente.nome,
      cnpj: item.cliente.cnpj,
      cep: item.cliente.cep,
      cidade_uf: item.cliente.cidade_uf,
      desconto_contratado: item.cliente.desconto_contratado,
      subvencao: item.cliente.subvencao,
      status: item.cliente.status === "Inativo" ? "Inativo" : "Ativo",
    },
    referencia: item.referencia,
    vencimento: item.vencimento,
    energia_compensada: Number(item.energia_compensada ?? 0),
    tarifa_sem_desconto: Number(item.tarifa_sem_desconto ?? 0),
    tarifa_com_desconto: Number(item.tarifa_com_desconto ?? 0),
    percentual_desconto: Number(item.percentual_desconto ?? 0),
    bandeiras: Number(item.bandeiras ?? 0),
    bandeiras_com_desconto: Number(item.bandeiras_com_desconto ?? 0),
    valor_total: Number(item.valor_total ?? 0),
    economia_gerada: Number(item.economia_gerada ?? 0),
    status: item.status,
    faturas: item.faturas.map((fatura) => ({
      id: fatura.id,
      unidade_consumidora: item.cliente.unidade_consumidora,
      cliente_numero: item.cliente.cliente_numero,
      nome: item.cliente.nome,
      cnpj: item.cliente.cnpj,
      referencia: fatura.referencia,
      vencimento: fatura.vencimento,
      total: Number(fatura.total ?? 0),
      leitura_anterior: fatura.leitura_anterior ?? "",
      leitura_atual: fatura.leitura_atual ?? "",
      dias: 0,
      proxima_leitura: "",
      nota_fiscal_numero: fatura.nota_fiscal_numero,
      nota_fiscal_serie: "",
      nota_fiscal_emissao: "",
      cidade_uf: item.cliente.cidade_uf,
      cep: item.cliente.cep,
      itens: [],
      status: item.status === "validado" ? "validado" : "pendente",
      alertas: [],
    })),
  };
}

export default function BoletosPage() {
  const [boletos, setBoletos] = useState<Boleto[]>([]);
  const [calculatingIds, setCalculatingIds] = useState<Record<string, boolean>>({});
  const { toast } = useToast();

  const loadBoletos = useCallback(async () => {
    try {
      const response = await getJson<ApiBoletosResponse>("/boletos");
      setBoletos((response.items ?? []).map(mapApiBoletoToUi));
    } catch (error) {
      console.error(error);
      toast({
        title: "Erro ao carregar boletos",
        description: "Nao foi possivel buscar a listagem pre-boleto.",
        variant: "destructive",
      });
    }
  }, [toast]);

  useEffect(() => {
    void loadBoletos();
  }, [loadBoletos]);

  const handleValidateBoleto = useCallback(
    async (boletoId: string) => {
      setCalculatingIds((prev) => ({ ...prev, [boletoId]: true }));

      try {
        await postJson(`/faturas/${boletoId}/calcular`);
        await loadBoletos();
        toast({
          title: "Calculo concluido",
          description: "O pre-boleto foi calculado e persistido sem emissao Sicoob.",
        });
      } catch (error) {
        console.error(error);
        toast({
          title: "Erro no calculo",
          description: "Nao foi possivel calcular este pre-boleto.",
          variant: "destructive",
        });
      } finally {
        setCalculatingIds((prev) => ({ ...prev, [boletoId]: false }));
      }
    },
    [loadBoletos, toast]
  );

  const handleGeneratePDF = useCallback(
    (boletoId: string) => {
      const boleto = boletos.find((item) => item.id === boletoId);
      toast({
        title: "Emissao final fora do escopo",
        description: boleto
          ? `O pre-boleto de ${boleto.cliente.nome} ja foi calculado. A emissao/elaboracao final nao faz parte desta tarefa.`
          : "A emissao/elaboracao final nao faz parte desta tarefa.",
      });
    },
    [boletos, toast]
  );

  const totalBoletos = boletos.length;
  const boletosValidados = boletos.filter((b) => b.status === "validado" || b.status === "gerado").length;
  const valorTotal = boletos.reduce((acc, b) => acc + b.valor_total, 0);
  const economiaTotal = boletos.reduce((acc, b) => acc + b.economia_gerada, 0);

  return (
    <MainLayout
      title="Geração de Boletos"
      subtitle="Calcule e valide os boletos de cobrança dos associados"
    >
      <div className="space-y-6 animate-fade-in">
        <BoletoSummary
          totalBoletos={totalBoletos}
          boletosValidados={boletosValidados}
          valorTotal={valorTotal}
          economiaTotal={economiaTotal}
        />

        <BoletoTable
          boletos={boletos}
          onValidate={handleValidateBoleto}
          onGeneratePDF={handleGeneratePDF}
          busyIds={calculatingIds}
        />
      </div>
    </MainLayout>
  );
}
