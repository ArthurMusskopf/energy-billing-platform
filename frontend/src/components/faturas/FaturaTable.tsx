import { useEffect, useState } from "react";
import { AlertTriangle, Check, ChevronDown, ChevronRight, Loader2, Save } from "lucide-react";
import { Fatura } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface FaturaTableProps {
  faturas: Fatura[];
  onSaveReview: (fatura: Fatura) => void;
  onValidateAndCalculate: (fatura: Fatura) => void;
  onRequestDetails?: (faturaId: string) => void;
  loadingDetails?: Record<string, boolean>;
  savingIds?: Record<string, boolean>;
  validatingIds?: Record<string, boolean>;
}

const FIELD_LABELS: Record<string, string> = {
  unidade_consumidora: "UC",
  cliente_numero: "Codigo do cliente",
  nome: "Nome",
  cnpj_cpf: "CPF/CNPJ",
  cep: "CEP",
  cidade_uf: "Cidade/UF",
  desconto_contratado: "Desconto contratado",
  subvencao: "Subvencao",
  status: "Status",
  custo_disp: "Custo de disponibilidade",
};

function getDraftPendingFields(fatura: Fatura): string[] {
  const cadastro = fatura.cadastro;
  if (!cadastro) {
    return Object.keys(FIELD_LABELS);
  }

  const missing: string[] = [];
  if (!cadastro.unidade_consumidora.trim()) missing.push("unidade_consumidora");
  if (!cadastro.cliente_numero.trim()) missing.push("cliente_numero");
  if (!cadastro.nome.trim()) missing.push("nome");
  if (!cadastro.cnpj.trim()) missing.push("cnpj_cpf");
  if (!cadastro.cep.trim()) missing.push("cep");
  if (!cadastro.cidade_uf.trim()) missing.push("cidade_uf");
  if (cadastro.desconto_contratado === null || Number.isNaN(cadastro.desconto_contratado)) {
    missing.push("desconto_contratado");
  }
  if (cadastro.subvencao === null || Number.isNaN(cadastro.subvencao)) {
    missing.push("subvencao");
  }
  if (!cadastro.status.trim()) missing.push("status");
  if (cadastro.custo_disp === null || Number.isNaN(cadastro.custo_disp)) {
    missing.push("custo_disp");
  }

  return missing;
}

function isEligibleForCalculation(fatura: Fatura): boolean {
  const cadastro = fatura.cadastro;
  if (!cadastro) {
    return false;
  }

  return getDraftPendingFields(fatura).length === 0 && cadastro.status.trim().toLowerCase() === "ativo";
}

export function FaturaTable({
  faturas,
  onSaveReview,
  onValidateAndCalculate,
  onRequestDetails,
  loadingDetails = {},
  savingIds = {},
  validatingIds = {},
}: FaturaTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [drafts, setDrafts] = useState<Record<string, Fatura>>({});

  useEffect(() => {
    setDrafts((previous) => {
      const next = { ...previous };
      faturas.forEach((fatura) => {
        if (next[fatura.id]) {
          next[fatura.id] = { ...fatura };
        }
      });
      return next;
    });
  }, [faturas]);

  const toggleRow = (id: string) => {
    const nextExpanded = new Set(expandedRows);
    const willOpen = !nextExpanded.has(id);

    if (willOpen) {
      nextExpanded.add(id);
      onRequestDetails?.(id);
      const current = faturas.find((item) => item.id === id);
      if (current) {
        setDrafts((previous) => ({ ...previous, [id]: { ...current } }));
      }
    } else {
      nextExpanded.delete(id);
    }

    setExpandedRows(nextExpanded);
  };

  const updateDraft = (faturaId: string, updater: (current: Fatura) => Fatura) => {
    setDrafts((previous) => {
      const base = previous[faturaId] ?? faturas.find((item) => item.id === faturaId);
      if (!base) {
        return previous;
      }

      return { ...previous, [faturaId]: updater(base) };
    });
  };

  const updateMainField = (faturaId: string, field: keyof Fatura, value: string | number) => {
    updateDraft(faturaId, (current) => {
      const next = { ...current, [field]: value } as Fatura;
      const cadastro = current.cadastro
        ? {
            ...current.cadastro,
          }
        : undefined;

      if (cadastro) {
        if (field === "unidade_consumidora") cadastro.unidade_consumidora = String(value);
        if (field === "cliente_numero") cadastro.cliente_numero = String(value);
        if (field === "nome") cadastro.nome = String(value);
        if (field === "cnpj") cadastro.cnpj = String(value);
        if (field === "cep") cadastro.cep = String(value);
        if (field === "cidade_uf") cadastro.cidade_uf = String(value);
        next.cadastro = cadastro;
      }

      return next;
    });
  };

  const updateCadastroField = (faturaId: string, field: string, value: string | number | null) => {
    updateDraft(faturaId, (current) => {
      const cadastro = current.cadastro
        ? {
            ...current.cadastro,
            [field]: value,
          }
        : current.cadastro;

      const next: Fatura = {
        ...current,
        cadastro,
      };

      if (field === "cep" && typeof value === "string") next.cep = value;
      if (field === "cidade_uf" && typeof value === "string") next.cidade_uf = value;
      if (field === "status" && cadastro) {
        next.pode_validar_calcular = cadastro.status.trim().toLowerCase() === "ativo";
      }

      return next;
    });
  };

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(value);

  const getStatusBadge = (fatura: Fatura) => {
    if (fatura.status_calculo === "calculado") {
      return <Badge className="bg-success/10 text-success border-success/20">Calculada</Badge>;
    }
    if (fatura.status === "validado") {
      return <Badge className="bg-success/10 text-success border-success/20">Validada</Badge>;
    }
    if (fatura.alertas.length > 0) {
      return <Badge className="bg-warning/10 text-warning border-warning/20">Alertas ({fatura.alertas.length})</Badge>;
    }
    if (fatura.status === "erro") {
      return <Badge className="bg-destructive/10 text-destructive border-destructive/20">Erro</Badge>;
    }
    return <Badge variant="secondary">Pendente</Badge>;
  };

  return (
    <div className="rounded-xl border bg-card">
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="w-12"></TableHead>
            <TableHead>Cliente</TableHead>
            <TableHead>UC</TableHead>
            <TableHead>Referencia</TableHead>
            <TableHead>Vencimento</TableHead>
            <TableHead className="text-right">Total</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Acoes</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {faturas.map((originalFatura) => {
            const fatura = drafts[originalFatura.id] ?? originalFatura;
            const isLoadingDetails = Boolean(loadingDetails[fatura.id]);
            const isSaving = Boolean(savingIds[fatura.id]);
            const isValidating = Boolean(validatingIds[fatura.id]);
            const pendingFields = getDraftPendingFields(fatura);
            const canValidateAndCalculate = isEligibleForCalculation(fatura);

            return (
              <Collapsible key={fatura.id} asChild open={expandedRows.has(fatura.id)}>
                <>
                  <CollapsibleTrigger asChild>
                    <TableRow
                      className={cn(
                        "cursor-pointer transition-colors",
                        fatura.alertas.length > 0 && "bg-warning/5"
                      )}
                      onClick={() => toggleRow(fatura.id)}
                    >
                      <TableCell>
                        {expandedRows.has(fatura.id) ? (
                          <ChevronDown className="h-4 w-4" />
                        ) : (
                          <ChevronRight className="h-4 w-4" />
                        )}
                      </TableCell>
                      <TableCell className="font-medium">
                        <div>
                          <p className="font-semibold">{fatura.nome}</p>
                          <p className="text-xs text-muted-foreground">{fatura.cnpj}</p>
                          <p className="text-xs text-muted-foreground">Codigo: {fatura.cliente_numero || "-"}</p>
                        </div>
                      </TableCell>
                      <TableCell>{fatura.unidade_consumidora || "-"}</TableCell>
                      <TableCell>{fatura.referencia || "-"}</TableCell>
                      <TableCell>{fatura.vencimento || "-"}</TableCell>
                      <TableCell className="text-right font-semibold">
                        {formatCurrency(fatura.total)}
                      </TableCell>
                      <TableCell>{getStatusBadge(fatura)}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant={fatura.status_calculo === "calculado" ? "secondary" : "default"}
                          disabled={
                            fatura.status_calculo === "calculado" ||
                            isValidating ||
                            !canValidateAndCalculate
                          }
                          onClick={(event) => {
                            event.stopPropagation();
                            onValidateAndCalculate(fatura);
                          }}
                        >
                          {fatura.status_calculo === "calculado" ? (
                            <>
                              <Check className="mr-1 h-4 w-4" /> Calculada
                            </>
                          ) : isValidating ? (
                            "Validando..."
                          ) : (
                            "Validar e calcular"
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  </CollapsibleTrigger>
                  <CollapsibleContent asChild>
                    <TableRow className="bg-muted/30 hover:bg-muted/30">
                      <TableCell colSpan={8} className="p-0">
                        <div className="space-y-4 p-6">
                          {isLoadingDetails && (
                            <div className="text-sm text-muted-foreground">
                              Carregando detalhes reais da fatura...
                            </div>
                          )}

                          {fatura.alertas.length > 0 && (
                            <div className="rounded-lg border border-warning/20 bg-warning/10 p-4">
                              <h4 className="mb-2 flex items-center gap-2 font-semibold text-warning">
                                <AlertTriangle className="h-4 w-4" />
                                Alertas de sanidade
                              </h4>
                              <ul className="space-y-1">
                                {fatura.alertas.map((alerta) => (
                                  <li key={alerta.id} className="text-sm">
                                    <strong>{alerta.campo}:</strong> {alerta.mensagem}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {pendingFields.length > 0 && (
                            <div className="rounded-lg border border-warning/20 bg-warning/10 p-4">
                              <h4 className="font-semibold text-warning">Cadastro minimo pendente</h4>
                              <p className="mt-1 text-sm text-muted-foreground">
                                Preencha e salve os campos abaixo antes de validar e calcular.
                              </p>
                              <p className="mt-2 text-sm">
                                {pendingFields.map((field) => FIELD_LABELS[field] ?? field).join(", ")}
                              </p>
                            </div>
                          )}

                          {!canValidateAndCalculate && fatura.cadastro?.status.trim().toLowerCase() === "inativo" && (
                            <div className="rounded-lg border border-destructive/20 bg-destructive/5 p-4 text-sm">
                              O cadastro esta preenchido, mas o status atual nao e elegivel para calculo.
                            </div>
                          )}

                          <div className="grid gap-4 lg:grid-cols-2">
                            <div className="space-y-3 rounded-lg border bg-background p-4">
                              <div>
                                <h4 className="font-semibold">Revisao da fatura</h4>
                                <p className="text-sm text-muted-foreground">
                                  Ajuste os dados operacionais que vieram do parse antes de confirmar o calculo.
                                </p>
                              </div>

                              <div className="grid gap-3 md:grid-cols-2">
                                <FieldInput
                                  label="UC"
                                  value={fatura.unidade_consumidora}
                                  onChange={(value) => updateMainField(fatura.id, "unidade_consumidora", value)}
                                />
                                <FieldInput
                                  label="Codigo do cliente"
                                  value={fatura.cliente_numero}
                                  onChange={(value) => updateMainField(fatura.id, "cliente_numero", value)}
                                />
                                <FieldInput
                                  label="Nome"
                                  value={fatura.nome}
                                  onChange={(value) => updateMainField(fatura.id, "nome", value)}
                                />
                                <FieldInput
                                  label="CPF/CNPJ"
                                  value={fatura.cnpj}
                                  onChange={(value) => updateMainField(fatura.id, "cnpj", value)}
                                />
                                <FieldInput
                                  label="Referencia"
                                  value={fatura.referencia}
                                  onChange={(value) => updateMainField(fatura.id, "referencia", value)}
                                />
                                <FieldInput
                                  label="Vencimento"
                                  value={fatura.vencimento}
                                  onChange={(value) => updateMainField(fatura.id, "vencimento", value)}
                                />
                                <FieldInput
                                  label="Leitura anterior"
                                  value={fatura.leitura_anterior}
                                  onChange={(value) => updateMainField(fatura.id, "leitura_anterior", value)}
                                />
                                <FieldInput
                                  label="Leitura atual"
                                  value={fatura.leitura_atual}
                                  onChange={(value) => updateMainField(fatura.id, "leitura_atual", value)}
                                />
                                <FieldInput
                                  label="Dias"
                                  value={fatura.dias ? String(fatura.dias) : ""}
                                  type="number"
                                  onChange={(value) =>
                                    updateMainField(
                                      fatura.id,
                                      "dias",
                                      value === "" ? 0 : Number(value)
                                    )
                                  }
                                />
                                <FieldInput
                                  label="Proxima leitura"
                                  value={fatura.proxima_leitura}
                                  onChange={(value) => updateMainField(fatura.id, "proxima_leitura", value)}
                                />
                              </div>
                            </div>

                            <div className="space-y-3 rounded-lg border bg-background p-4">
                              <div>
                                <h4 className="font-semibold">Cadastro minimo</h4>
                                <p className="text-sm text-muted-foreground">
                                  Esta etapa substitui a validacao operacional redundante em outra tela.
                                </p>
                              </div>

                              <div className="grid gap-3 md:grid-cols-2">
                                <FieldInput
                                  label="CEP"
                                  value={fatura.cadastro?.cep ?? ""}
                                  onChange={(value) => updateCadastroField(fatura.id, "cep", value)}
                                />
                                <FieldInput
                                  label="Cidade/UF"
                                  value={fatura.cadastro?.cidade_uf ?? ""}
                                  onChange={(value) => updateCadastroField(fatura.id, "cidade_uf", value)}
                                />
                                <FieldInput
                                  label="Desconto contratado (15 ou 0.15)"
                                  value={
                                    fatura.cadastro?.desconto_contratado === null
                                      ? ""
                                      : String(fatura.cadastro?.desconto_contratado ?? "")
                                  }
                                  type="number"
                                  step="0.01"
                                  onChange={(value) =>
                                    updateCadastroField(
                                      fatura.id,
                                      "desconto_contratado",
                                      value === "" ? null : Number(value)
                                    )
                                  }
                                />
                                <FieldInput
                                  label="Subvencao"
                                  value={
                                    fatura.cadastro?.subvencao === null
                                      ? ""
                                      : String(fatura.cadastro?.subvencao ?? "")
                                  }
                                  type="number"
                                  step="0.01"
                                  onChange={(value) =>
                                    updateCadastroField(
                                      fatura.id,
                                      "subvencao",
                                      value === "" ? null : Number(value)
                                    )
                                  }
                                />
                                <div className="space-y-2">
                                  <label className="text-sm font-medium">Status</label>
                                  <select
                                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                    value={fatura.cadastro?.status ?? ""}
                                    onChange={(event) =>
                                      updateCadastroField(fatura.id, "status", event.target.value)
                                    }
                                  >
                                    <option value="">Selecione</option>
                                    <option value="Ativo">Ativo</option>
                                    <option value="Inativo">Inativo</option>
                                  </select>
                                </div>
                                <FieldInput
                                  label="Numero de fases"
                                  value={
                                    fatura.cadastro?.n_fases === null
                                      ? ""
                                      : String(fatura.cadastro?.n_fases ?? "")
                                  }
                                  type="number"
                                  onChange={(value) =>
                                    updateCadastroField(
                                      fatura.id,
                                      "n_fases",
                                      value === "" ? null : Number(value)
                                    )
                                  }
                                />
                                <FieldInput
                                  label="Custo de disponibilidade"
                                  value={
                                    fatura.cadastro?.custo_disp === null
                                      ? ""
                                      : String(fatura.cadastro?.custo_disp ?? "")
                                  }
                                  type="number"
                                  step="0.01"
                                  onChange={(value) =>
                                    updateCadastroField(
                                      fatura.id,
                                      "custo_disp",
                                      value === "" ? null : Number(value)
                                    )
                                  }
                                />
                              </div>

                              <div className="flex flex-wrap gap-2 pt-2">
                                <Button
                                  type="button"
                                  variant="secondary"
                                  disabled={isSaving}
                                  onClick={() => onSaveReview(fatura)}
                                >
                                  {isSaving ? (
                                    <>
                                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                      Salvando...
                                    </>
                                  ) : (
                                    <>
                                      <Save className="mr-2 h-4 w-4" />
                                      Salvar revisao
                                    </>
                                  )}
                                </Button>
                                <Button
                                  type="button"
                                  disabled={isValidating || !canValidateAndCalculate}
                                  onClick={() => onValidateAndCalculate(fatura)}
                                >
                                  {isValidating ? "Validando..." : "Validar e calcular"}
                                </Button>
                              </div>
                            </div>
                          </div>

                          <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-5">
                            <InfoBlock label="Leitura anterior" value={fatura.leitura_anterior || "-"} />
                            <InfoBlock label="Leitura atual" value={fatura.leitura_atual || "-"} />
                            <InfoBlock label="Dias" value={fatura.dias ? String(fatura.dias) : "-"} />
                            <InfoBlock label="Nota fiscal" value={fatura.nota_fiscal_numero || "-"} />
                            <InfoBlock label="Serie" value={fatura.nota_fiscal_serie || "-"} />
                          </div>

                          {fatura.itens.length > 0 ? (
                            <div className="rounded-lg border overflow-hidden">
                              <div className="border-b bg-muted/40 px-4 py-3">
                                <h4 className="font-semibold">Itens da fatura</h4>
                              </div>
                              <Table>
                                <TableHeader>
                                  <TableRow className="bg-muted/50">
                                    <TableHead>Codigo</TableHead>
                                    <TableHead>Descricao</TableHead>
                                    <TableHead>Un</TableHead>
                                    <TableHead className="text-right">Quantidade</TableHead>
                                    <TableHead className="text-right">Tarifa</TableHead>
                                    <TableHead className="text-right">Valor</TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {fatura.itens.map((item) => (
                                    <TableRow key={item.id}>
                                      <TableCell className="font-mono">{item.codigo}</TableCell>
                                      <TableCell>{item.descricao}</TableCell>
                                      <TableCell>{item.unidade}</TableCell>
                                      <TableCell className="text-right">
                                        {item.quantidade.toLocaleString("pt-BR")}
                                      </TableCell>
                                      <TableCell className="text-right">{item.tarifa.toFixed(6)}</TableCell>
                                      <TableCell className="text-right font-medium">
                                        {formatCurrency(item.valor)}
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </div>
                          ) : (
                            !isLoadingDetails && (
                              <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
                                Nenhum item parseado encontrado para esta fatura.
                              </div>
                            )
                          )}

                          {fatura.medidores && fatura.medidores.length > 0 && (
                            <div className="rounded-lg border overflow-hidden">
                              <div className="border-b bg-muted/40 px-4 py-3">
                                <h4 className="font-semibold">Medidores</h4>
                              </div>
                              <Table>
                                <TableHeader>
                                  <TableRow className="bg-muted/50">
                                    <TableHead>Medidor</TableHead>
                                    <TableHead>Tipo</TableHead>
                                    <TableHead>Posto</TableHead>
                                    <TableHead>Leitura anterior</TableHead>
                                    <TableHead>Leitura atual</TableHead>
                                    <TableHead className="text-right">Total apurado</TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {fatura.medidores.map((medidor) => (
                                    <TableRow key={medidor.id}>
                                      <TableCell className="font-mono">{medidor.medidor || "-"}</TableCell>
                                      <TableCell>{medidor.tipo || "-"}</TableCell>
                                      <TableCell>{medidor.posto || "-"}</TableCell>
                                      <TableCell>{medidor.leitura_anterior || "-"}</TableCell>
                                      <TableCell>{medidor.leitura_atual || "-"}</TableCell>
                                      <TableCell className="text-right">
                                        {medidor.total_apurado.toLocaleString("pt-BR")}
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </div>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  </CollapsibleContent>
                </>
              </Collapsible>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

interface FieldInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  step?: string;
}

function FieldInput({ label, value, onChange, type = "text", step }: FieldInputProps) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      <Input type={type} step={step} value={value} onChange={(event) => onChange(event.target.value)} />
    </div>
  );
}

interface InfoBlockProps {
  label: string;
  value: string;
}

function InfoBlock({ label, value }: InfoBlockProps) {
  return (
    <div>
      <p className="text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  );
}
