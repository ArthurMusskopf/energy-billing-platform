import { useState } from "react";
import { ChevronDown, ChevronRight, History } from "lucide-react";
import { Link } from "react-router-dom";

import { Boleto } from "@/types";
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

interface BoletoTableProps {
  boletos: Boleto[];
}

export function BoletoTable({ boletos }: BoletoTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (id: string) => {
    const next = new Set(expandedRows);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setExpandedRows(next);
  };

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(value);

  const getStatusBadge = (status: Boleto["status"]) => {
    switch (status) {
      case "gerado":
        return <Badge className="bg-success/10 text-success border-success/20">PDF Gerado</Badge>;
      case "calculada":
        return <Badge className="bg-success/10 text-success border-success/20">Calculada</Badge>;
      case "validado":
        return <Badge className="bg-primary/10 text-primary border-primary/20">Validado</Badge>;
      default:
        return <Badge variant="secondary">Pendente</Badge>;
    }
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
            <TableHead className="text-right">Energia Compensada</TableHead>
            <TableHead className="text-right">Valor Total</TableHead>
            <TableHead className="text-right">Economia</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {boletos.length === 0 && (
            <TableRow>
              <TableCell colSpan={8} className="py-10 text-center text-sm text-muted-foreground">
                Nenhuma NF calculada encontrada em `boletos_calculados`.
              </TableCell>
            </TableRow>
          )}

          {boletos.map((boleto) => (
            <Collapsible key={boleto.id} asChild open={expandedRows.has(boleto.id)}>
              <>
                <CollapsibleTrigger asChild>
                  <TableRow className="cursor-pointer transition-colors" onClick={() => toggleRow(boleto.id)}>
                    <TableCell>
                      {expandedRows.has(boleto.id) ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                    </TableCell>
                    <TableCell className="font-medium">
                      <div>
                        <p className="font-semibold">{boleto.cliente.nome}</p>
                        <p className="text-xs text-muted-foreground">{boleto.cliente.cnpj}</p>
                      </div>
                    </TableCell>
                    <TableCell>{boleto.cliente.unidade_consumidora}</TableCell>
                    <TableCell>{boleto.referencia}</TableCell>
                    <TableCell className="text-right">
                      {boleto.energia_compensada.toLocaleString("pt-BR")} kWh
                    </TableCell>
                    <TableCell className="text-right font-semibold">
                      {formatCurrency(boleto.valor_total)}
                    </TableCell>
                    <TableCell className="text-right font-semibold text-success">
                      {formatCurrency(boleto.economia_gerada)}
                    </TableCell>
                    <TableCell>{getStatusBadge(boleto.status)}</TableCell>
                  </TableRow>
                </CollapsibleTrigger>

                <CollapsibleContent asChild>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableCell colSpan={8} className="p-0">
                      <div className="space-y-6 p-6">
                        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 text-sm">
                          Saida operacional calculada a partir de `boletos_calculados`. Emissao bancaria final ainda nao faz parte desta etapa.
                        </div>

                        <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">
                          <div className="space-y-4">
                            <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Tarifas</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Concessionaria</span>
                                <span className="font-medium">{formatCurrency(boleto.tarifa_sem_desconto)}/kWh</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">ERB</span>
                                <span className="font-medium text-success">{formatCurrency(boleto.tarifa_com_desconto)}/kWh</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Desconto</span>
                                <span className="font-medium">{boleto.percentual_desconto}%</span>
                              </div>
                            </div>
                          </div>

                          <div className="space-y-4">
                            <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Workflow</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Validacao</span>
                                <span className="font-medium">{boleto.status_validacao ?? "-"}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Calculo</span>
                                <span className="font-medium text-success">{boleto.status_calculo ?? "-"}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Emissao</span>
                                <span className="font-medium">{boleto.status_emissao ?? "-"}</span>
                              </div>
                            </div>
                          </div>

                          <div className="space-y-4">
                            <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Resumo</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Energia compensada</span>
                                <span className="font-medium">{boleto.energia_compensada.toLocaleString("pt-BR")} kWh</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Vencimento</span>
                                <span className="font-medium">{boleto.vencimento}</span>
                              </div>
                            </div>
                          </div>

                          <div className="space-y-4">
                            <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Valores</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Concessionaria</span>
                                <span className="font-medium">{formatCurrency(boleto.valor_concessionaria ?? 0)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Total calculado</span>
                                <span className="text-lg font-bold">{formatCurrency(boleto.valor_total)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Economia</span>
                                <span className="text-lg font-bold text-success">{formatCurrency(boleto.economia_gerada)}</span>
                              </div>
                            </div>
                          </div>
                        </div>

                        {boleto.faturas.length > 0 && (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <h4 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                                Faturas vinculadas ({boleto.faturas.length})
                              </h4>
                              <Link to="/" className="inline-flex items-center gap-1 text-sm text-primary">
                                <History className="h-4 w-4" />
                                Abrir trilha de faturas
                              </Link>
                            </div>

                            <div className="overflow-hidden rounded-lg border">
                              <Table>
                                <TableHeader>
                                  <TableRow className="bg-muted/50">
                                    <TableHead>NF</TableHead>
                                    <TableHead>Referencia</TableHead>
                                    <TableHead>Leitura</TableHead>
                                    <TableHead className="text-right">Total</TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {boleto.faturas.map((fatura) => (
                                    <TableRow key={fatura.id}>
                                      <TableCell className="font-mono">{fatura.nota_fiscal_numero}</TableCell>
                                      <TableCell>{fatura.referencia}</TableCell>
                                      <TableCell>
                                        {fatura.leitura_anterior} {"->"} {fatura.leitura_atual}
                                      </TableCell>
                                      <TableCell className="text-right font-medium">
                                        {formatCurrency(fatura.total)}
                                      </TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </div>
                          </div>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                </CollapsibleContent>
              </>
            </Collapsible>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
