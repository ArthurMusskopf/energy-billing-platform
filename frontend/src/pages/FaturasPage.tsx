import { useState, useCallback, useEffect } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { UploadZone } from "@/components/faturas/UploadZone";
import { FaturaTable } from "@/components/faturas/FaturaTable";
import { ProcessingSummary } from "@/components/faturas/ProcessingSummary";
import { Fatura } from "@/types";
import { useToast } from "@/hooks/use-toast";
import { getJson, postFormData } from "@/lib/api";

interface ApiFaturaWorkflowItem {
  id: string;
  nota_fiscal?: string | null;
  unidade_consumidora?: string | null;
  cliente_numero?: string | null;
  nome?: string | null;
  cnpj_cpf?: string | null;
  referencia?: string | null;
  vencimento?: string | null;
  classe_modalidade?: string | null;
  grupo_subgrupo_tensao?: string | null;
  total_pagar?: number | null;
  arquivo_nome_original?: string | null;
  arquivo_hash?: string | null;
  pdf_uri?: string | null;
  is_inedita?: boolean | null;
  duplicada_de?: string | null;
  status_parse?: string | null;
  status_validacao?: string | null;
  status_calculo?: string | null;
  status_emissao?: string | null;
  observacoes?: string | null;
}

interface ApiListFaturasResponse {
  items: ApiFaturaWorkflowItem[];
  total: number;
  limit: number;
  offset: number;
}

interface ApiParseFaturasResponse {
  total_arquivos: number;
  parseadas_com_sucesso: number;
  erros_parse: number;
  resumo: {
    total_nf: number;
    ineditas: number;
    repetidas: number;
    parseadas: number;
    erro_parse: number;
  };
  workflow: ApiFaturaWorkflowItem[];
  salvar_auto_executado: boolean;
  bigquery_result?: {
    ok?: boolean;
    table?: string;
    affected_rows?: number;
    error?: string;
  } | null;
}

function mapApiStatusToUiStatus(item: ApiFaturaWorkflowItem): Fatura["status"] {
  if (item.status_parse === "erro_parse") {
    return "erro";
  }

  if (item.status_validacao === "validado") {
    return "validado";
  }

  return "pendente";
}

function mapApiFaturaToUi(item: ApiFaturaWorkflowItem): Fatura {
  const observacoes = item.observacoes?.trim();

  return {
    id: item.id,
    unidade_consumidora: item.unidade_consumidora ?? "",
    cliente_numero: item.cliente_numero ?? "",
    nome: item.nome ?? "",
    cnpj: item.cnpj_cpf ?? "",
    referencia: item.referencia ?? "",
    vencimento: item.vencimento ?? "",
    total: Number(item.total_pagar ?? 0),
    leitura_anterior: "",
    leitura_atual: "",
    dias: 0,
    proxima_leitura: "",
    nota_fiscal_numero: item.nota_fiscal ?? item.id,
    nota_fiscal_serie: "",
    nota_fiscal_emissao: "",
    cidade_uf: "",
    cep: "",
    itens: [],
    status: mapApiStatusToUiStatus(item),
    alertas: observacoes
      ? [
          {
            id: `obs-${item.id}`,
            campo: "workflow",
            tipo: "warning",
            mensagem: observacoes,
            valor_atual: 0,
            valor_esperado: 0,
            desvio_percentual: 0,
          },
        ]
      : [],
  };
}

export default function FaturasPage() {
  const [faturas, setFaturas] = useState<Fatura[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const { toast } = useToast();

  const loadFaturas = useCallback(async () => {
    try {
      const response = await getJson<ApiListFaturasResponse>("/faturas");
      const mapped = (response.items ?? []).map(mapApiFaturaToUi);
      setFaturas(mapped);
    } catch (error) {
      console.error(error);
      toast({
        title: "Erro ao carregar faturas",
        description: "Nao foi possivel buscar o workflow real no backend.",
        variant: "destructive",
      });
    }
  }, [toast]);

  useEffect(() => {
    void loadFaturas();
  }, [loadFaturas]);

  const handleFilesUploaded = useCallback(
    async (files: File[]) => {
      setIsProcessing(true);

      try {
        const formData = new FormData();
        files.forEach((file) => {
          formData.append("files", file);
        });

        const response = await postFormData<ApiParseFaturasResponse>("/faturas/parse", formData);

        await loadFaturas();

        const detalhePersistencia =
          response.bigquery_result?.ok === true
            ? "Workflow salvo no BigQuery."
            : "Parse concluido, mas a persistencia nao confirmou sucesso.";

        toast({
          title: "Processamento concluido",
          description: `${response.parseadas_com_sucesso} arquivo(s) processado(s). ${detalhePersistencia}`,
        });
      } catch (error) {
        console.error(error);
        toast({
          title: "Erro no processamento",
          description: "Nao foi possivel enviar os PDFs para parseamento.",
          variant: "destructive",
        });
      } finally {
        setIsProcessing(false);
      }
    },
    [loadFaturas, toast]
  );

  const handleValidateFatura = useCallback(
    (faturaId: string) => {
      toast({
        title: "Validacao ainda nao integrada",
        description: `A mudanca real de status da fatura ${faturaId} sera a proxima etapa.`,
      });
    },
    [toast]
  );

  const handleUpdateFatura = useCallback((faturaId: string, field: string, value: any) => {
    setFaturas((prev) =>
      prev.map((f) => (f.id === faturaId ? { ...f, [field]: value } : f))
    );
  }, []);

  const totalFaturas = faturas.length;
  const faturasValidadas = faturas.filter((f) => f.status === "validado").length;
  const faturasComAlerta = faturas.filter((f) => f.alertas.length > 0).length;

  return (
    <MainLayout
      title="Upload de Faturas"
      subtitle="Carregue faturas em PDF para parseamento automático"
    >
      <div className="space-y-6 animate-fade-in">
        <UploadZone onFilesUploaded={handleFilesUploaded} isProcessing={isProcessing} />

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