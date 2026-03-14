import { Leaf, TrendingUp, Users, Zap } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface DashboardKPIsProps {
  totalEconomia: number;
  totalReceita: number;
  totalClientes: number;
  energiaCompensadaTotal: number;
}

export function DashboardKPIs({
  totalEconomia,
  totalReceita,
  totalClientes,
  energiaCompensadaTotal
}: DashboardKPIsProps) {
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat("pt-BR").format(value);
  };

  const kpis = [
    {
      label: "Economia Total Gerada",
      value: formatCurrency(totalEconomia),
      icon: Leaf,
      color: "text-success",
      bgColor: "bg-success/10",
      change: "+12.5%",
      changePositive: true
    },
    {
      label: "Receita Acumulada",
      value: formatCurrency(totalReceita),
      icon: TrendingUp,
      color: "text-primary",
      bgColor: "bg-primary/10",
      change: "+8.3%",
      changePositive: true
    },
    {
      label: "Associados Ativos",
      value: totalClientes.toString(),
      icon: Users,
      color: "text-chart-2",
      bgColor: "bg-chart-2/10",
      change: "+7",
      changePositive: true
    },
    {
      label: "Energia Compensada",
      value: `${formatNumber(energiaCompensadaTotal)} kWh`,
      icon: Zap,
      color: "text-warning",
      bgColor: "bg-warning/10",
      change: "+15.2%",
      changePositive: true
    }
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {kpis.map((kpi, index) => (
        <Card 
          key={kpi.label} 
          className="animate-slide-up overflow-hidden" 
          style={{ animationDelay: `${index * 50}ms` }}
        >
          <CardContent className="p-6">
            <div className="flex items-start justify-between">
              <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${kpi.bgColor}`}>
                <kpi.icon className={`h-6 w-6 ${kpi.color}`} />
              </div>
              <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                kpi.changePositive ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive"
              }`}>
                {kpi.change}
              </span>
            </div>
            <div className="mt-4">
              <p className="text-2xl font-bold">{kpi.value}</p>
              <p className="text-sm text-muted-foreground">{kpi.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
