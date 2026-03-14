import { useState } from "react";
import { ChevronDown, ChevronRight, Check, AlertTriangle, Edit2, X } from "lucide-react";
import { Fatura, FaturaItem } from "@/types";
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
  onValidate: (faturaId: string) => void;
  onUpdate: (faturaId: string, field: string, value: any) => void;
}

export function FaturaTable({ faturas, onValidate, onUpdate }: FaturaTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [editingCell, setEditingCell] = useState<{ faturaId: string; field: string } | null>(null);
  const [editValue, setEditValue] = useState("");

  const toggleRow = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedRows(newExpanded);
  };

  const startEdit = (faturaId: string, field: string, currentValue: string | number) => {
    setEditingCell({ faturaId, field });
    setEditValue(String(currentValue));
  };

  const saveEdit = () => {
    if (editingCell) {
      onUpdate(editingCell.faturaId, editingCell.field, editValue);
      setEditingCell(null);
    }
  };

  const cancelEdit = () => {
    setEditingCell(null);
    setEditValue("");
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL"
    }).format(value);
  };

  const getStatusBadge = (status: Fatura["status"], alertCount: number) => {
    if (status === "validado") {
      return <Badge className="bg-success/10 text-success border-success/20">Validado</Badge>;
    }
    if (alertCount > 0) {
      return <Badge className="bg-warning/10 text-warning border-warning/20">Alertas ({alertCount})</Badge>;
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
            <TableHead>Referência</TableHead>
            <TableHead>Vencimento</TableHead>
            <TableHead className="text-right">Total</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Ações</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {faturas.map((fatura) => (
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
                      </div>
                    </TableCell>
                    <TableCell>{fatura.unidade_consumidora}</TableCell>
                    <TableCell>{fatura.referencia}</TableCell>
                    <TableCell>{fatura.vencimento}</TableCell>
                    <TableCell className="text-right font-semibold">
                      {formatCurrency(fatura.total)}
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(fatura.status, fatura.alertas.length)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant={fatura.status === "validado" ? "secondary" : "default"}
                        disabled={fatura.status === "validado"}
                        onClick={(e) => {
                          e.stopPropagation();
                          onValidate(fatura.id);
                        }}
                      >
                        {fatura.status === "validado" ? (
                          <>
                            <Check className="mr-1 h-4 w-4" /> Validado
                          </>
                        ) : (
                          "Validar"
                        )}
                      </Button>
                    </TableCell>
                  </TableRow>
                </CollapsibleTrigger>
                <CollapsibleContent asChild>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableCell colSpan={8} className="p-0">
                      <div className="p-6 space-y-4">
                        {/* Alertas */}
                        {fatura.alertas.length > 0 && (
                          <div className="rounded-lg bg-warning/10 border border-warning/20 p-4">
                            <h4 className="flex items-center gap-2 font-semibold text-warning mb-2">
                              <AlertTriangle className="h-4 w-4" />
                              Alertas de Sanidade
                            </h4>
                            <ul className="space-y-1">
                              {fatura.alertas.map((alerta) => (
                                <li key={alerta.id} className="text-sm">
                                  <strong>{alerta.campo}:</strong> {alerta.mensagem} 
                                  <span className="text-muted-foreground ml-2">
                                    (Atual: {alerta.valor_atual} | Esperado: ~{alerta.valor_esperado} | Desvio: {alerta.desvio_percentual}%)
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Informações da Fatura */}
                        <div className="grid grid-cols-4 gap-4 text-sm">
                          <div>
                            <p className="text-muted-foreground">Leitura Anterior</p>
                            <p className="font-medium">{fatura.leitura_anterior}</p>
                          </div>
                          <div>
                            <p className="text-muted-foreground">Leitura Atual</p>
                            <p className="font-medium">{fatura.leitura_atual}</p>
                          </div>
                          <div>
                            <p className="text-muted-foreground">Dias</p>
                            <p className="font-medium">{fatura.dias}</p>
                          </div>
                          <div>
                            <p className="text-muted-foreground">Nota Fiscal</p>
                            <p className="font-medium">{fatura.nota_fiscal_numero}</p>
                          </div>
                        </div>

                        {/* Tabela de Itens */}
                        <div className="rounded-lg border overflow-hidden">
                          <Table>
                            <TableHeader>
                              <TableRow className="bg-muted/50">
                                <TableHead>Código</TableHead>
                                <TableHead>Descrição</TableHead>
                                <TableHead>Un</TableHead>
                                <TableHead className="text-right">Quantidade</TableHead>
                                <TableHead className="text-right">Tarifa</TableHead>
                                <TableHead className="text-right">Valor</TableHead>
                                <TableHead className="text-right">PIS</TableHead>
                                <TableHead className="text-right">ICMS %</TableHead>
                                <TableHead className="text-right">ICMS R$</TableHead>
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {fatura.itens.map((item) => (
                                <TableRow key={item.id}>
                                  <TableCell className="font-mono">{item.codigo}</TableCell>
                                  <TableCell>{item.descricao}</TableCell>
                                  <TableCell>{item.unidade}</TableCell>
                                  <TableCell className="text-right">
                                    <EditableCell
                                      value={item.quantidade}
                                      isEditing={editingCell?.faturaId === fatura.id && editingCell?.field === `quantidade-${item.id}`}
                                      editValue={editValue}
                                      onEdit={() => startEdit(fatura.id, `quantidade-${item.id}`, item.quantidade)}
                                      onSave={saveEdit}
                                      onCancel={cancelEdit}
                                      onChange={setEditValue}
                                    />
                                  </TableCell>
                                  <TableCell className="text-right">{item.tarifa.toFixed(6)}</TableCell>
                                  <TableCell className="text-right font-medium">
                                    {formatCurrency(item.valor)}
                                  </TableCell>
                                  <TableCell className="text-right">{formatCurrency(item.pis_valor)}</TableCell>
                                  <TableCell className="text-right">{item.icms_aliquota}%</TableCell>
                                  <TableCell className="text-right">{formatCurrency(item.icms_valor)}</TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </div>
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

interface EditableCellProps {
  value: number | string;
  isEditing: boolean;
  editValue: string;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
  onChange: (value: string) => void;
}

function EditableCell({ value, isEditing, editValue, onEdit, onSave, onCancel, onChange }: EditableCellProps) {
  if (isEditing) {
    return (
      <div className="flex items-center gap-1">
        <Input
          value={editValue}
          onChange={(e) => onChange(e.target.value)}
          className="h-7 w-24 text-right"
          autoFocus
          onKeyDown={(e) => {
            if (e.key === "Enter") onSave();
            if (e.key === "Escape") onCancel();
          }}
        />
        <Button size="icon" variant="ghost" className="h-6 w-6" onClick={onSave}>
          <Check className="h-3 w-3" />
        </Button>
        <Button size="icon" variant="ghost" className="h-6 w-6" onClick={onCancel}>
          <X className="h-3 w-3" />
        </Button>
      </div>
    );
  }

  return (
    <div className="group flex items-center justify-end gap-1">
      <span>{typeof value === "number" ? value.toLocaleString("pt-BR") : value}</span>
      <Button
        size="icon"
        variant="ghost"
        className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={(e) => {
          e.stopPropagation();
          onEdit();
        }}
      >
        <Edit2 className="h-3 w-3" />
      </Button>
    </div>
  );
}
