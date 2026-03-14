import { useState } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { BoletoTable } from "@/components/boletos/BoletoTable";
import { BoletoSummary } from "@/components/boletos/BoletoSummary";
import { mockBoletos } from "@/data/mockData";
import { Boleto } from "@/types";
import { useToast } from "@/hooks/use-toast";

export default function BoletosPage() {
  const [boletos, setBoletos] = useState<Boleto[]>(mockBoletos);
  const { toast } = useToast();

  const handleValidateBoleto = (boletoId: string) => {
    setBoletos(prev => prev.map(b => 
      b.id === boletoId ? { ...b, status: 'validado' as const } : b
    ));
    toast({
      title: "Boleto validado",
      description: "O boleto foi marcado como validado.",
    });
  };

  const handleGeneratePDF = (boletoId: string) => {
    const boleto = boletos.find(b => b.id === boletoId);
    if (boleto) {
      setBoletos(prev => prev.map(b => 
        b.id === boletoId ? { ...b, status: 'gerado' as const } : b
      ));
      toast({
        title: "PDF Gerado",
        description: `Demonstrativo de economia para ${boleto.cliente.nome} gerado com sucesso.`,
      });
    }
  };

  const totalBoletos = boletos.length;
  const boletosValidados = boletos.filter(b => b.status === 'validado' || b.status === 'gerado').length;
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
        />
      </div>
    </MainLayout>
  );
}
