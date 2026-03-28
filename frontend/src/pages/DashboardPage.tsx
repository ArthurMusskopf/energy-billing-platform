import { useEffect, useState } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { DashboardKPIs } from "@/components/dashboard/DashboardKPIs";
import { EconomiaChart } from "@/components/dashboard/EconomiaChart";
import { ReceitaChart } from "@/components/dashboard/ReceitaChart";
import { TopClientes } from "@/components/dashboard/TopClientes";
import { DashboardData } from "@/types";
import { getJson } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

const emptyDashboardData: DashboardData = {
  total_economia: 0,
  total_receita: 0,
  total_clientes: 0,
  energia_compensada_total: 0,
  economia_por_mes: [],
  maiores_clientes: [],
  receita_por_mes: [],
};

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData>(emptyDashboardData);
  const { toast } = useToast();

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      try {
        const response = await getJson<DashboardData>("/dashboard/resumo");
        if (!cancelled) {
          setData(response);
        }
      } catch (error) {
        console.error(error);
        if (!cancelled) {
          toast({
            title: "Erro ao carregar dashboard",
            description: "Nao foi possivel buscar os dados reais do dashboard.",
            variant: "destructive",
          });
        }
      }
    }

    void loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [toast]);

  const maiorEconomiaMes = [...data.economia_por_mes].sort((a, b) => b.valor - a.valor)[0];
  const maiorReceitaMes = [...data.receita_por_mes].sort((a, b) => b.valor - a.valor)[0];
  const melhorCliente = data.maiores_clientes[0];
  const insights = [
    {
      title: "Melhor mês de economia",
      value: maiorEconomiaMes ? maiorEconomiaMes.mes : "Sem dados",
      description: maiorEconomiaMes
        ? `Economia acumulada de R$ ${maiorEconomiaMes.valor.toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}.`
        : "Os valores aparecerao aqui assim que houver calculos persistidos.",
      tone: "success",
    },
    {
      title: "Maior receita registrada",
      value: maiorReceitaMes ? maiorReceitaMes.mes : "Sem dados",
      description: maiorReceitaMes
        ? `Receita total de R$ ${maiorReceitaMes.valor.toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}.`
        : "Ainda nao ha receita calculada para o periodo selecionado.",
      tone: "primary",
    },
    {
      title: "Cliente com maior economia",
      value: melhorCliente ? melhorCliente.nome : "Sem dados",
      description: melhorCliente
        ? `Economia acumulada de R$ ${melhorCliente.economia.toLocaleString("pt-BR", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}.`
        : "O ranking sera preenchido quando os boletos estiverem calculados.",
      tone: "warning",
    },
  ];

  return (
    <MainLayout
      title="Dashboard Gerencial"
      subtitle="Visão geral da ACER - Associação Catarinense de Energias Renováveis"
    >
      <div className="space-y-6 animate-fade-in">
        <DashboardKPIs
          totalEconomia={data.total_economia}
          totalReceita={data.total_receita}
          totalClientes={data.total_clientes}
          energiaCompensadaTotal={data.energia_compensada_total}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <EconomiaChart data={data.economia_por_mes} />
          <ReceitaChart data={data.receita_por_mes} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <TopClientes clientes={data.maiores_clientes} />
          </div>
          <div className="space-y-6">
            <div className="rounded-xl border bg-card p-6 space-y-4">
              <h3 className="font-semibold">Principais Oportunidades</h3>
              <div className="space-y-3">
                {insights.map((insight) => (
                  <div
                    key={insight.title}
                    className={
                      insight.tone === "success"
                        ? "p-3 rounded-lg border-l-4 border-l-success bg-success/5"
                        : insight.tone === "primary"
                          ? "p-3 rounded-lg border-l-4 border-l-primary bg-primary/5"
                          : "p-3 rounded-lg border-l-4 border-l-warning bg-warning/5"
                    }
                  >
                    <div className="flex items-center justify-between mb-1 gap-3">
                      <span className="font-medium text-sm">{insight.title}</span>
                      <span
                        className={
                          insight.tone === "success"
                            ? "text-xs font-bold text-success"
                            : insight.tone === "primary"
                              ? "text-xs font-bold text-primary"
                              : "text-xs font-bold text-warning"
                        }
                      >
                        {insight.value}
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">{insight.description}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
