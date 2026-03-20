import { useState, useCallback, useEffect } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { UploadZone } from "@/components/faturas/UploadZone";
import { FaturaTable } from "@/components/faturas/FaturaTable";
import { ProcessingSummary } from "@/components/faturas/ProcessingSummary";
import { Fatura, FaturaItem, Alerta } from "@/types";
import { useToast } from "@/hooks/use-toast";
import { getJson, patchJson, postFormData } from "@/lib/api";

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
  validado_por?: string | null;
  validado_em?: string | null;
  status_calculo?: string | null;
  calculado_em?: string | null;
  status_emissao?: string | null;
  emitido_em?: string | null;
  observacoes?: string | null;
}

interface ApiFaturaItem {
  id: string;
  codigo?: string | null;
  descricao?: string | null;
  unidade?: string | null;
  quantidade_registrada?: number | null;
  tarifa?: number | null;
  valor?: number | null;
  pis_valor?: number | null;
  cofins_base?: number | null;
  icms_aliquota?: number | null;
  icms_valor?: number | null;
  tarifa_sem_trib?: number | null;
}

interface ApiFaturaAlert {
  id: string;
  campo: string;
  tipo: "warning" | "error";
  mensagem: string;
  valor_atual?: number | null;
  valor_esperado?: number | null;
  desvio_percentual?: number | null;
}

interface ApiFaturaDetailResponse extends ApiFaturaWorkflowItem {
  leitura_anterior?: string | null;
  leitura_atual?: string | null;
  dias?: number | null;
  proxima_leitura?: string | null;
  nota_fiscal_serie?: string | null;
  nota_fiscal_emissao?: string | null;
  cidade_uf?: string | null;
  cep?: string | null;
  itens: ApiFaturaItem[];
  alertas: ApiFaturaAlert[];
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
    workflow?: { ok?: boolean; affected_rows?: number };
    itens?: { ok?: boolean; affected_rows?: number };
    medidores?: { ok?: boolean; affected_rows?: number };
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

function mapApiAlertToUi(alerta: ApiFaturaAlert): Alerta {
  return {
    id: alerta.id,
    campo: alerta.campo,
    tipo: alerta.tipo,
    mensagem: alerta.mensagem,
    valor_atual: Number(alerta.valor_atual ?? 0),
    valor_esperado: Number(alerta.valor_esperado ?? 0),
    desvio_percentual: Number(alerta.desvio_percentual ?? 0),
  };
}

function mapObservacaoToUiAlert(item: ApiFaturaWorkflowItem): Alerta[] {
  const observacoes = item.observacoes?.trim();
  if (!observacoes) {
    return [];
  }

  return [
    {
      id: `obs-${item.id}`,
      campo: "workflow",
      tipo: observacoes.toLowerCase().includes("erro") ? "error" : "warning",
      mensagem: observacoes,
      valor_atual: 0,
      valor_esperado: 0,
      desvio_percentual: 0,
    },
  ];
}

function mapApiItemToUi(item: ApiFaturaItem): FaturaItem {
  return {
    id: item.id,
    codigo: item.codigo ?? "",
    descricao: item.descricao ?? "",
    unidade: item.unidade ?? "",
    quantidade: Number(item.quantidade_registrada ?? 0),
    tarifa: Number(item.tarifa ?? 0),
    valor: Number(item.valor ?? 0),
    pis_valor: Number(item.pis_valor ?? 0),
    cofins_base: Number(item.cofins_base ?? 0),
    icms_aliquota: Number(item.icms_aliquota ?? 0),
    icms_valor: Number(item.icms_valor ?? 0),
    tarifa_sem_trib: Number(item.tarifa_sem_trib ?? 0),
  };
}

function mapApiFaturaToUi(item: ApiFaturaWorkflowItem): Fatura {
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
    alertas: mapObservacaoToUiAlert(item),
  };
}

function mergeApiDetailIntoUi(current: Fatura, detail: ApiFaturaDetailResponse): Fatura {
  return {
    ...current,
    unidade_consumidora: detail.unidade_consumidora ?? current.unidade_consumidora,
    cliente_numero: detail.cliente_numero ?? current.cliente_numero,
    nome: detail.nome ?? current.nome,
    cnpj: detail.cnpj_cpf ?? current.cnpj,
    referencia: detail.referencia ?? current.referencia,
    vencimento: detail.vencimento ?? current.vencimento,
    total: Number(detail.total_pagar ?? current.total),
    leitura_anterior: detail.leitura_anterior ?? current.leitura_anterior,
    leitura_atual: detail.leitura_atual ?? current.leitura_atual,
    dias: Number(detail.dias ?? current.dias ?? 0),
    proxima_leitura: detail.proxima_leitura ?? current.proxima_leitura,
    nota_fiscal_numero: detail.nota_fiscal ?? current.nota_fiscal_numero,
    nota_fiscal_serie: detail.nota_fiscal_serie ?? current.nota_fiscal_serie,
    nota_fiscal_emissao: detail.nota_fiscal_emissao ?? current.nota_fiscal_emissao,
    cidade_uf: detail.cidade_uf ?? current.cidade_uf,
    cep: detail.cep ?? current.cep,
    itens: (detail.itens ?? []).map(mapApiItemToUi),
    status: mapApiStatusToUiStatus(detail),
    alertas:
      detail.alertas && detail.alertas.length > 0
        ? detail.alertas.map(mapApiAlertToUi)
        : mapObservacaoToUiAlert(detail),
  };
}

export default function FaturasPage() {
  const [faturas, setFaturas] = useState<Fatura[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({});
  const [loadedDetails, setLoadedDetails] = useState<Record<string, boolean>>({});
  const [validatingIds, setValidatingIds] = useState<Record<string, boolean>>({});
  const { toast } = useToast();

  const loadFaturas = useCallback(async () => {
    try {
      const response = await getJson<ApiListFaturasResponse>("/faturas");
      const mapped = (response.items ?? []).map(mapApiFaturaToUi);

      setFaturas((prev) => {
        const prevById = new Map(prev.map((item) => [item.id, item]));

        return mapped.map((item) => {
          const previous = prevById.get(item.id);
          if (!previous || !loadedDetails[item.id]) {
            return item;
          }

          return {
            ...item,
            leitura_anterior: previous.leitura_anterior,
            leitura_atual: previous.leitura_atual,
            dias: previous.dias,
            proxima_leitura: previous.proxima_leitura,
            nota_fiscal_serie: previous.nota_fiscal_serie,
            nota_fiscal_emissao: previous.nota_fiscal_emissao,
            cidade_uf: previous.cidade_uf,
            cep: previous.cep,
            itens: previous.itens,
            alertas: previous.alertas.length > 0 ? previous.alertas : item.alertas,
          };
        });
      });
    } catch (error) {
      console.error(error);
      toast({
        title: "Erro ao carregar faturas",
        description: "Nao foi possivel buscar o workflow real no backend.",
        variant: "destructive",
      });
    }
  }, [loadedDetails, toast]);

  useEffect(() => {
    void loadFaturas();
  }, [loadFaturas]);

  const loadFaturaDetail = useCallback(
    async (faturaId: string) => {
      if (loadedDetails[faturaId] || loadingDetails[faturaId]) {
        return;
      }

      setLoadingDetails((prev) => ({ ...prev, [faturaId]: true }));

      try {
        const response = await getJson<ApiFaturaDetailResponse>(`/faturas/${faturaId}`);
        setFaturas((prev) =>
          prev.map((item) => (item.id === faturaId ? mergeApiDetailIntoUi(item, response) : item))
        );
        setLoadedDetails((prev) => ({ ...prev, [faturaId]: true }));
      } catch (error) {
        console.error(error);
        toast({
          title: "Erro ao carregar detalhe",
          description: `Nao foi possivel buscar os dados completos da fatura ${faturaId}.`,
          variant: "destructive",
        });
      } finally {
        setLoadingDetails((prev) => ({ ...prev, [faturaId]: false }));
      }
    },
    [loadedDetails, loadingDetails, toast]
  );

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

        const workflowOk = response.bigquery_result?.workflow?.ok === true;
        const itensOk = response.bigquery_result?.itens?.ok === true;
        const medidoresOk = response.bigquery_result?.medidores?.ok === true;
        const detalhePersistencia =
          workflowOk && itensOk && medidoresOk
            ? "Workflow, itens e medidores salvos no BigQuery."
            : "Parse concluido, mas a persistencia nao confirmou todas as tabelas.";

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
    async (faturaId: string) => {
      setValidatingIds((prev) => ({ ...prev, [faturaId]: true }));

      try {
        await patchJson(`/faturas/${faturaId}/validar`, {
          usuario: "frontend",
        });

        await loadFaturas();

        toast({
          title: "Fatura validada",
          description: `A fatura ${faturaId} foi validada no backend.`,
        });
      } catch (error) {
        console.error(error);
        toast({
          title: "Erro na validacao",
          description: `Nao foi possivel validar a fatura ${faturaId}.`,
          variant: "destructive",
        });
      } finally {
        setValidatingIds((prev) => ({ ...prev, [faturaId]: false }));
      }
    },
    [loadFaturas, toast]
  );

  const handleUpdateFatura = useCallback((faturaId: string, field: string, value: any) => {
    setFaturas((prev) => prev.map((f) => (f.id === faturaId ? { ...f, [field]: value } : f)));
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
          onRequestDetails={loadFaturaDetail}
          loadingDetails={loadingDetails}
          validatingIds={validatingIds}
        />
      </div>
    </MainLayout>
  );
}
