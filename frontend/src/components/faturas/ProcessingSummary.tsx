import { FileText, CheckCircle, AlertTriangle, Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface ProcessingSummaryProps {
  totalFaturas: number;
  faturasValidadas: number;
  faturasComAlerta: number;
  isProcessing: boolean;
}

export function ProcessingSummary({
  totalFaturas,
  faturasValidadas,
  faturasComAlerta,
  isProcessing
}: ProcessingSummaryProps) {
  const stats = [
    {
      label: "Total de Faturas",
      value: totalFaturas,
      icon: FileText,
      color: "text-primary",
      bgColor: "bg-primary/10"
    },
    {
      label: "Validadas",
      value: faturasValidadas,
      icon: CheckCircle,
      color: "text-success",
      bgColor: "bg-success/10"
    },
    {
      label: "Com Alertas",
      value: faturasComAlerta,
      icon: AlertTriangle,
      color: "text-warning",
      bgColor: "bg-warning/10"
    },
    {
      label: "Pendentes",
      value: totalFaturas - faturasValidadas,
      icon: isProcessing ? Loader2 : FileText,
      color: "text-muted-foreground",
      bgColor: "bg-muted"
    }
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat, index) => (
        <Card key={stat.label} className="animate-slide-up" style={{ animationDelay: `${index * 50}ms` }}>
          <CardContent className="flex items-center gap-4 p-6">
            <div className={`flex h-12 w-12 items-center justify-center rounded-lg ${stat.bgColor}`}>
              <stat.icon className={`h-6 w-6 ${stat.color} ${isProcessing && stat.label === "Pendentes" ? "animate-spin" : ""}`} />
            </div>
            <div>
              <p className="text-2xl font-bold">{stat.value}</p>
              <p className="text-sm text-muted-foreground">{stat.label}</p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
