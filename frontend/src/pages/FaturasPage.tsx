import { useState, useCallback } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { UploadZone } from "@/components/faturas/UploadZone";
import { FaturaTable } from "@/components/faturas/FaturaTable";
import { ProcessingSummary } from "@/components/faturas/ProcessingSummary";
import { mockFaturas } from "@/data/mockData";
import { Fatura } from "@/types";
import { useToast } from "@/hooks/use-toast";

export default function FaturasPage() {
  const [faturas, setFaturas] = useState<Fatura[]>(mockFaturas);
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const { toast } = useToast();

  const handleFilesUploaded = useCallback((files: File[]) => {
    setUploadedFiles(files);
    setIsProcessing(true);
    
    // Simulate processing
    setTimeout(() => {
      setIsProcessing(false);
      toast({
        title: "Processamento concluído",
        description: `${files.length} fatura(s) processada(s) com sucesso.`,
      });
    }, 2000);
  }, [toast]);

  const handleValidateFatura = useCallback((faturaId: string) => {
    setFaturas(prev => prev.map(f => 
      f.id === faturaId ? { ...f, status: 'validado' as const } : f
    ));
    toast({
      title: "Fatura validada",
      description: "Os dados foram registrados no banco de dados.",
    });
  }, [toast]);

  const handleUpdateFatura = useCallback((faturaId: string, field: string, value: any) => {
    setFaturas(prev => prev.map(f => 
      f.id === faturaId ? { ...f, [field]: value } : f
    ));
  }, []);

  const totalFaturas = faturas.length;
  const faturasValidadas = faturas.filter(f => f.status === 'validado').length;
  const faturasComAlerta = faturas.filter(f => f.alertas.length > 0).length;

  return (
    <MainLayout 
      title="Upload de Faturas" 
      subtitle="Carregue faturas em PDF para parseamento automático"
    >
      <div className="space-y-6 animate-fade-in">
        <UploadZone 
          onFilesUploaded={handleFilesUploaded}
          isProcessing={isProcessing}
        />

        <ProcessingSummary
          totalFaturas={totalFaturas}
          faturasValidadas={faturasValidadas}
          faturasComAlerta={faturasComAlerta}
          isProcessing={isProcessing}
        />

        <FaturaTable
          faturas={faturas}
          onValidate={handleValidateFatura}
          onUpdate={handleUpdateFatura}
        />
      </div>
    </MainLayout>
  );
}
