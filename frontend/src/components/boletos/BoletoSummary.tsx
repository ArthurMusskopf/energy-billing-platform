import { Receipt, CheckCircle, DollarSign, Leaf } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface BoletoSummaryProps {
  totalBoletos: number;
  boletosValidados: number;
  valorTotal: number;
  economiaTotal: number;
}

export function BoletoSummary({
  totalBoletos,
  boletosValidados,
  valorTotal,
  economiaTotal
}: BoletoSummaryProps) {
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL"
    }).format(value);
  };

  const stats = [
    {
      label: "Total de Boletos",
      value: totalBoletos.toString(),
      icon: Receipt,
      color: "text-primary",
      bgColor: "bg-primary/10"
    },
    {
      label: "Validados",
      value: boletosValidados.toString(),
      icon: CheckCircle,
      color: "text-success",
      bgColor: "bg-success/10"
    },
    {
      label: "Valor a Receber",
      value: formatCurrency(valorTotal),
      icon: DollarSign,
      color: "text-chart-2",
      bgColor: "bg-chart-2/10"
    },
    {
      label: "Economia Gerada",
      value: formatCurrency(economiaTotal),
      icon: Leaf,
      color: "text-success",
      bgColor: "bg-success/10"
    }
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat, index) => (
        <Card key={stat.label} className="animate-slide-up" style={{ animationDelay: `${index * 50}ms` }}>
          <CardContent className="flex items-center gap-4 p-6">
            <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${stat.bgColor}`}>
              <stat.icon className={`h-6 w-6 ${stat.color}`} />
            </div>
            <div>
              <p className="text-xl font-bold">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
