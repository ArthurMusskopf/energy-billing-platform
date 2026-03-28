import { useCallback, useEffect, useState } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { UploadZone } from "@/components/faturas/UploadZone";
import { FaturaTable } from "@/components/faturas/FaturaTable";
import { ProcessingSummary } from "@/components/faturas/ProcessingSummary";
import {
  Alerta,
  Fatura,
  FaturaCadastroMinimo,
  FaturaItem,
  FaturaMedidor,
} from "@/types";
import { useToast } from "@/hooks/use-toast";
import { getJson, patchJson, postFormData, postJson } from "@/lib/api";

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
  leitura_anterior?: string | null;
  leitura_atual?: string | null;
  dias?: number | null;
  proxima_leitura?: string | null;
  nota_fiscal_serie?: string | null;
  nota_fiscal_emissao?: string | null;
  cidade_uf?: string | null;
  cep?: string | null;
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

interface ApiFaturaMedidor {
  id: string;
  medidor?: string | null;
  tipo?: string | null;
  posto?: string | null;
  leitura_anterior?: string | null;
  leitura_atual?: string | null;
  total_apurado?: number | null;
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

interface ApiFaturaCadastro {
  unidade_consumidora?: string | null;
  cliente_numero?: string | null;
  nome?: string | null;
  cnpj_cpf?: string | null;
  cep?: string | null;
  cidade_uf?: string | null;
  desconto_contratado?: number | null;
  subvencao?: number | null;
  status?: string | null;
  n_fases?: number | null;
  custo_disp?: number | null;
  origem?: string | null;
  uc_cadastrada?: boolean | null;
  motivo_bloqueio?: string | null;
  campos_pendentes?: string[] | null;
  cadastro_minimo_completo?: boolean | null;
  elegivel_para_calculo?: boolean | null;
}

interface ApiFaturaDetailResponse extends ApiFaturaWorkflowItem {
  itens: ApiFaturaItem[];
  medidores: ApiFaturaMedidor[];
  alertas: ApiFaturaAlert[];
  cadastro_cliente: ApiFaturaCadastro;
  campos_pendentes_cadastro?: string[] | null;
  motivo_bloqueio?: string | null;
  pode_validar_calcular?: boolean | null;
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

interface ApiValidacaoCalculoResponse {
  id: string;
  status_validacao: string;
  validado_por?: string | null;
  validado_em?: string | null;
  updated_at?: string | null;
  status_calculo?: string | null;
  calculado_em?: string | null;
}

function mapApiStatusToUiStatus(item: ApiFaturaWorkflowItem): Fatura["status"] {
  if (item.status_parse === "erro_parse") {
    return "erro";
  }

  if (item.status_calculo === "calculado" || item.status_validacao === "validado") {
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

function mapApiMedidorToUi(item: ApiFaturaMedidor): FaturaMedidor {
  return {
    id: item.id,
    medidor: item.medidor ?? "",
    tipo: item.tipo ?? "",
    posto: item.posto ?? "",
    leitura_anterior: item.leitura_anterior ?? "",
    leitura_atual: item.leitura_atual ?? "",
    total_apurado: Number(item.total_apurado ?? 0),
  };
}

function buildFallbackCadastro(item: Partial<ApiFaturaWorkflowItem>): FaturaCadastroMinimo {
  return {
    unidade_consumidora: item.unidade_consumidora ?? "",
    cliente_numero: item.cliente_numero ?? "",
    nome: item.nome ?? "",
    cnpj: item.cnpj_cpf ?? "",
    cep: item.cep ?? "",
    cidade_uf: item.cidade_uf ?? "",
    desconto_contratado: null,
    subvencao: null,
    status: "",
    n_fases: null,
    custo_disp: null,
    campos_pendentes: [],
    cadastro_minimo_completo: false,
    elegivel_para_calculo: false,
    uc_cadastrada: false,
  };
}

function mapApiCadastroToUi(
  cadastro: ApiFaturaCadastro | null | undefined,
  base: Partial<ApiFaturaWorkflowItem>
): FaturaCadastroMinimo {
  const fallback = buildFallbackCadastro(base);

  if (!cadastro) {
    return fallback;
  }

  return {
    unidade_consumidora: cadastro.unidade_consumidora ?? fallback.unidade_consumidora,
    cliente_numero: cadastro.cliente_numero ?? fallback.cliente_numero,
    nome: cadastro.nome ?? fallback.nome,
    cnpj: cadastro.cnpj_cpf ?? fallback.cnpj,
    cep: cadastro.cep ?? fallback.cep,
    cidade_uf: cadastro.cidade_uf ?? fallback.cidade_uf,
    desconto_contratado:
      cadastro.desconto_contratado === null || cadastro.desconto_contratado === undefined
        ? null
        : Number(cadastro.desconto_contratado),
    subvencao:
      cadastro.subvencao === null || cadastro.subvencao === undefined
        ? null
        : Number(cadastro.subvencao),
    status: cadastro.status ?? fallback.status,
    n_fases: cadastro.n_fases === null || cadastro.n_fases === undefined ? null : Number(cadastro.n_fases),
    custo_disp:
      cadastro.custo_disp === null || cadastro.custo_disp === undefined ? null : Number(cadastro.custo_disp),
    origem: cadastro.origem ?? fallback.origem,
    uc_cadastrada: Boolean(cadastro.uc_cadastrada),
    motivo_bloqueio: cadastro.motivo_bloqueio ?? undefined,
    campos_pendentes: cadastro.campos_pendentes ?? [],
    cadastro_minimo_completo: Boolean(cadastro.cadastro_minimo_completo),
    elegivel_para_calculo: Boolean(cadastro.elegivel_para_calculo),
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
    leitura_anterior: item.leitura_anterior ?? "",
    leitura_atual: item.leitura_atual ?? "",
    dias: Number(item.dias ?? 0),
    proxima_leitura: item.proxima_leitura ?? "",
    nota_fiscal_numero: item.nota_fiscal ?? item.id,
    nota_fiscal_serie: item.nota_fiscal_serie ?? "",
    nota_fiscal_emissao: item.nota_fiscal_emissao ?? "",
    cidade_uf: item.cidade_uf ?? "",
    cep: item.cep ?? "",
    itens: [],
    medidores: [],
    cadastro: buildFallbackCadastro(item),
    campos_pendentes_cadastro: [],
    motivo_bloqueio: undefined,
    pode_validar_calcular: false,
    status_calculo: item.status_calculo ?? "",
    status: mapApiStatusToUiStatus(item),
    alertas: mapObservacaoToUiAlert(item),
  };
}

function mergeApiDetailIntoUi(current: Fatura, detail: ApiFaturaDetailResponse): Fatura {
  const cadastro = mapApiCadastroToUi(detail.cadastro_cliente, detail);

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
    medidores: (detail.medidores ?? []).map(mapApiMedidorToUi),
    cadastro,
    campos_pendentes_cadastro: detail.campos_pendentes_cadastro ?? cadastro.campos_pendentes,
    motivo_bloqueio: detail.motivo_bloqueio ?? cadastro.motivo_bloqueio,
    pode_validar_calcular: Boolean(detail.pode_validar_calcular),
    status_calculo: detail.status_calculo ?? current.status_calculo,
    status: mapApiStatusToUiStatus(detail),
    alertas:
      detail.alertas && detail.alertas.length > 0
        ? detail.alertas.map(mapApiAlertToUi)
        : mapObservacaoToUiAlert(detail),
  };
}

function buildReviewPayload(fatura: Fatura) {
  return {
    unidade_consumidora: fatura.unidade_consumidora || undefined,
    cliente_numero: fatura.cliente_numero || undefined,
    nome: fatura.nome || undefined,
    cnpj_cpf: fatura.cnpj || undefined,
    referencia: fatura.referencia || undefined,
    vencimento: fatura.vencimento || undefined,
    leitura_anterior: fatura.leitura_anterior || undefined,
    leitura_atual: fatura.leitura_atual || undefined,
    dias: Number.isFinite(fatura.dias) ? fatura.dias : undefined,
    proxima_leitura: fatura.proxima_leitura || undefined,
    cep: fatura.cep || undefined,
    cidade_uf: fatura.cidade_uf || undefined,
    cadastro_cliente: fatura.cadastro
      ? {
          unidade_consumidora: fatura.cadastro.unidade_consumidora || undefined,
          cliente_numero: fatura.cadastro.cliente_numero || undefined,
          nome: fatura.cadastro.nome || undefined,
          cnpj_cpf: fatura.cadastro.cnpj || undefined,
          cep: fatura.cadastro.cep || undefined,
          cidade_uf: fatura.cadastro.cidade_uf || undefined,
          desconto_contratado:
            fatura.cadastro.desconto_contratado === null ? undefined : fatura.cadastro.desconto_contratado,
          subvencao: fatura.cadastro.subvencao === null ? undefined : fatura.cadastro.subvencao,
          status: fatura.cadastro.status || undefined,
          n_fases: fatura.cadastro.n_fases === null ? undefined : fatura.cadastro.n_fases,
          custo_disp: fatura.cadastro.custo_disp === null ? undefined : fatura.cadastro.custo_disp,
        }
      : undefined,
  };
}

function mergePersistedDetails(previous: Fatura, current: Fatura): Fatura {
  return {
    ...current,
    leitura_anterior: previous.leitura_anterior || current.leitura_anterior,
    leitura_atual: previous.leitura_atual || current.leitura_atual,
    dias: previous.dias || current.dias,
    proxima_leitura: previous.proxima_leitura || current.proxima_leitura,
    nota_fiscal_serie: previous.nota_fiscal_serie || current.nota_fiscal_serie,
    nota_fiscal_emissao: previous.nota_fiscal_emissao || current.nota_fiscal_emissao,
    cidade_uf: previous.cidade_uf || current.cidade_uf,
    cep: previous.cep || current.cep,
    itens: previous.itens.length > 0 ? previous.itens : current.itens,
    medidores: previous.medidores && previous.medidores.length > 0 ? previous.medidores : current.medidores,
    cadastro: previous.cadastro ?? current.cadastro,
    campos_pendentes_cadastro:
      previous.campos_pendentes_cadastro && previous.campos_pendentes_cadastro.length > 0
        ? previous.campos_pendentes_cadastro
        : current.campos_pendentes_cadastro,
    motivo_bloqueio: previous.motivo_bloqueio || current.motivo_bloqueio,
    pode_validar_calcular: previous.pode_validar_calcular ?? current.pode_validar_calcular,
    alertas: previous.alertas.length > 0 ? previous.alertas : current.alertas,
  };
}

export default function FaturasPage() {
  const [faturas, setFaturas] = useState<Fatura[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({});
  const [loadedDetails, setLoadedDetails] = useState<Record<string, boolean>>({});
  const [savingIds, setSavingIds] = useState<Record<string, boolean>>({});
  const [validatingIds, setValidatingIds] = useState<Record<string, boolean>>({});
  const { toast } = useToast();

  const loadFaturas = useCallback(async () => {
    try {
      const response = await getJson<ApiListFaturasResponse>("/faturas");
      const mapped = (response.items ?? []).map(mapApiFaturaToUi);

      setFaturas((previousFaturas) => {
        const previousById = new Map(previousFaturas.map((item) => [item.id, item]));

        return mapped.map((item) => {
          const previous = previousById.get(item.id);
          if (!previous || !loadedDetails[item.id]) {
            return item;
          }

          return mergePersistedDetails(previous, item);
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
    async (faturaId: string, force = false) => {
      if (!force && (loadedDetails[faturaId] || loadingDetails[faturaId])) {
        return;
      }

      setLoadingDetails((previous) => ({ ...previous, [faturaId]: true }));

      try {
        const response = await getJson<ApiFaturaDetailResponse>(`/faturas/${faturaId}`);
        setFaturas((previous) =>
          previous.map((item) => (item.id === faturaId ? mergeApiDetailIntoUi(item, response) : item))
        );
        setLoadedDetails((previous) => ({ ...previous, [faturaId]: true }));
      } catch (error) {
        console.error(error);
        toast({
          title: "Erro ao carregar detalhe",
          description: `Nao foi possivel buscar os dados completos da fatura ${faturaId}.`,
          variant: "destructive",
        });
      } finally {
        setLoadingDetails((previous) => ({ ...previous, [faturaId]: false }));
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

  const handleSaveReview = useCallback(
    async (fatura: Fatura) => {
      setSavingIds((previous) => ({ ...previous, [fatura.id]: true }));

      try {
        const response = await patchJson<ApiFaturaDetailResponse>(
          `/faturas/${fatura.id}/revisao`,
          buildReviewPayload(fatura)
        );

        setFaturas((previous) =>
          previous.map((item) => (item.id === fatura.id ? mergeApiDetailIntoUi(item, response) : item))
        );
        setLoadedDetails((previous) => ({ ...previous, [fatura.id]: true }));

        toast({
          title: "Revisao salva",
          description: `As correcoes da fatura ${fatura.id} foram persistidas.`,
        });
      } catch (error) {
        console.error(error);
        toast({
          title: "Erro ao salvar revisao",
          description:
            error instanceof Error ? error.message : `Nao foi possivel salvar a fatura ${fatura.id}.`,
          variant: "destructive",
        });
      } finally {
        setSavingIds((previous) => ({ ...previous, [fatura.id]: false }));
      }
    },
    [toast]
  );

  const handleValidateAndCalculate = useCallback(
    async (fatura: Fatura) => {
      setValidatingIds((previous) => ({ ...previous, [fatura.id]: true }));

      try {
        const reviewResponse = await patchJson<ApiFaturaDetailResponse>(
          `/faturas/${fatura.id}/revisao`,
          buildReviewPayload(fatura)
        );

        setFaturas((previous) =>
          previous.map((item) => (item.id === fatura.id ? mergeApiDetailIntoUi(item, reviewResponse) : item))
        );

        await postJson<ApiValidacaoCalculoResponse>(`/faturas/${fatura.id}/validar-e-calcular`, {
          usuario: "frontend",
        });

        await loadFaturaDetail(fatura.id, true);
        await loadFaturas();

        toast({
          title: "Fatura validada e calculada",
          description: `A fatura ${fatura.id} foi revisada, validada e enviada para calculo sem emissao bancaria.`,
        });
      } catch (error) {
        console.error(error);
        toast({
          title: "Erro no fluxo de validacao",
          description:
            error instanceof Error
              ? error.message
              : `Nao foi possivel validar e calcular a fatura ${fatura.id}.`,
          variant: "destructive",
        });
      } finally {
        setValidatingIds((previous) => ({ ...previous, [fatura.id]: false }));
      }
    },
    [loadFaturaDetail, loadFaturas, toast]
  );

  const totalFaturas = faturas.length;
  const faturasValidadas = faturas.filter((fatura) => fatura.status === "validado").length;
  const faturasComAlerta = faturas.filter((fatura) => fatura.alertas.length > 0).length;

  return (
    <MainLayout
      title="Upload de Faturas"
      subtitle="Carregue faturas em PDF para parseamento automatico"
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
          onSaveReview={handleSaveReview}
          onValidateAndCalculate={handleValidateAndCalculate}
          onRequestDetails={loadFaturaDetail}
          loadingDetails={loadingDetails}
          savingIds={savingIds}
          validatingIds={validatingIds}
        />
      </div>
    </MainLayout>
  );
}
