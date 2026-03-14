import { useState } from "react";
import { ChevronDown, ChevronRight, Check, FileDown, History, Eye } from "lucide-react";
import { Boleto } from "@/types";
import { Button } from "@/components/ui/button";
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
import { Link } from "react-router-dom";

interface BoletoTableProps {
  boletos: Boleto[];
  onValidate: (boletoId: string) => void;
  onGeneratePDF: (boletoId: string) => void;
}

export function BoletoTable({ boletos, onValidate, onGeneratePDF }: BoletoTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL"
    }).format(value);
  };

  const getStatusBadge = (status: Boleto["status"]) => {
    switch (status) {
      case "gerado":
        return <Badge className="bg-success/10 text-success border-success/20">PDF Gerado</Badge>;
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
            <TableHead>Referência</TableHead>
            <TableHead className="text-right">Energia Compensada</TableHead>
            <TableHead className="text-right">Valor Total</TableHead>
            <TableHead className="text-right">Economia</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Ações</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {boletos.map((boleto) => (
            <Collapsible key={boleto.id} asChild open={expandedRows.has(boleto.id)}>
              <>
                <CollapsibleTrigger asChild>
                  <TableRow 
                    className="cursor-pointer transition-colors"
                    onClick={() => toggleRow(boleto.id)}
                  >
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
                    <TableCell>
                      {getStatusBadge(boleto.status)}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        {boleto.status === "pendente" && (
                          <Button
                            size="sm"
                            variant="default"
                            onClick={(e) => {
                              e.stopPropagation();
                              onValidate(boleto.id);
                            }}
                          >
                            <Check className="mr-1 h-4 w-4" /> Validar
                          </Button>
                        )}
                        {boleto.status === "validado" && (
                          <Button
                            size="sm"
                            variant="default"
                            onClick={(e) => {
                              e.stopPropagation();
                              onGeneratePDF(boleto.id);
                            }}
                          >
                            <FileDown className="mr-1 h-4 w-4" /> Gerar PDF
                          </Button>
                        )}
                        {boleto.status === "gerado" && (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={(e) => {
                              e.stopPropagation();
                            }}
                          >
                            <Eye className="mr-1 h-4 w-4" /> Ver PDF
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                </CollapsibleTrigger>
                <CollapsibleContent asChild>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableCell colSpan={9} className="p-0">
                      <div className="p-6 space-y-6">
                        {/* Detalhes do Cálculo */}
                        <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
                          <div className="space-y-4">
                            <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">Tarifas</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Sem desconto</span>
                                <span className="font-medium">{formatCurrency(boleto.tarifa_sem_desconto)}/kWh</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Com desconto</span>
                                <span className="font-medium text-success">{formatCurrency(boleto.tarifa_com_desconto)}/kWh</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Desconto</span>
                                <span className="font-medium">{boleto.percentual_desconto}%</span>
                              </div>
                            </div>
                          </div>

                          <div className="space-y-4">
                            <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">Bandeiras</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Somatório</span>
                                <span className="font-medium">{formatCurrency(boleto.bandeiras)}/kWh</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Com desconto</span>
                                <span className="font-medium text-success">{formatCurrency(boleto.bandeiras_com_desconto)}/kWh</span>
                              </div>
                            </div>
                          </div>

                          <div className="space-y-4">
                            <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">Resumo</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Energia Compensada</span>
                                <span className="font-medium">{boleto.energia_compensada.toLocaleString("pt-BR")} kWh</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Vencimento</span>
                                <span className="font-medium">{boleto.vencimento}</span>
                              </div>
                            </div>
                          </div>

                          <div className="space-y-4">
                            <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">Valores</h4>
                            <div className="space-y-2">
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Total a Pagar</span>
                                <span className="font-bold text-lg">{formatCurrency(boleto.valor_total)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-sm text-muted-foreground">Economia</span>
                                <span className="font-bold text-lg text-success">{formatCurrency(boleto.economia_gerada)}</span>
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Faturas Vinculadas */}
                        {boleto.faturas.length > 0 && (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between">
                              <h4 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">
                                Faturas Vinculadas ({boleto.faturas.length})
                              </h4>
                              <Link to="/historico">
                                <Button variant="ghost" size="sm">
                                  <History className="mr-1 h-4 w-4" /> Ver Histórico Completo
                                </Button>
                              </Link>
                            </div>
                            <div className="rounded-lg border overflow-hidden">
                              <Table>
                                <TableHeader>
                                  <TableRow className="bg-muted/50">
                                    <TableHead>NF</TableHead>
                                    <TableHead>Referência</TableHead>
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
                                        {fatura.leitura_anterior} → {fatura.leitura_atual}
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
