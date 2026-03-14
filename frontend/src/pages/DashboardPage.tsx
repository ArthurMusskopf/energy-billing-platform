import { MainLayout } from "@/components/layout/MainLayout";
import { DashboardKPIs } from "@/components/dashboard/DashboardKPIs";
import { EconomiaChart } from "@/components/dashboard/EconomiaChart";
import { ReceitaChart } from "@/components/dashboard/ReceitaChart";
import { TopClientes } from "@/components/dashboard/TopClientes";
import { mockDashboardData } from "@/data/mockData";

export default function DashboardPage() {
  const data = mockDashboardData;

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
            {/* Insights */}
            <div className="rounded-xl border bg-card p-6 space-y-4">
              <h3 className="font-semibold">Principais Oportunidades</h3>
              <div className="space-y-3">
                <div className="p-3 rounded-lg border-l-4 border-l-success bg-success/5">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm">Crescimento Q4</span>
                    <span className="text-xs font-bold text-success">+R$ 5.2k</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Economia acumulada cresceu 15% no último trimestre
                  </p>
                </div>
                <div className="p-3 rounded-lg border-l-4 border-l-primary bg-primary/5">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm">Novos Associados</span>
                    <span className="text-xs font-bold text-primary">+12</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    12 novos associados nos últimos 3 meses
                  </p>
                </div>
                <div className="p-3 rounded-lg border-l-4 border-l-warning bg-warning/5">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-sm">Otimização</span>
                    <span className="text-xs font-bold text-warning">-R$ 2.1k</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Potencial de economia com ajuste de contratos
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
