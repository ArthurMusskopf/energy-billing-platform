import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp } from "lucide-react";

interface TopClientesProps {
  clientes: { nome: string; economia: number }[];
}

export function TopClientes({ clientes }: TopClientesProps) {
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL"
    }).format(value);
  };

  const maxEconomia = Math.max(...clientes.map(c => c.economia));

  return (
    <Card className="animate-slide-up" style={{ animationDelay: "300ms" }}>
      <CardHeader>
        <CardTitle className="text-lg">Maiores Economias por Cliente</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {clientes.map((cliente, index) => (
            <div key={cliente.nome} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                    {index + 1}
                  </span>
                  <span className="font-medium text-sm truncate max-w-[200px]" title={cliente.nome}>
                    {cliente.nome}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-success" />
                  <span className="font-semibold text-success">
                    {formatCurrency(cliente.economia)}
                  </span>
                </div>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div 
                  className="h-full rounded-full gradient-success transition-all duration-500"
                  style={{ width: `${(cliente.economia / maxEconomia) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
