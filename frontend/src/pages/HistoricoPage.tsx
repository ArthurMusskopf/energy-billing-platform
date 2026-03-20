import { useEffect, useState } from "react";
import { MainLayout } from "@/components/layout/MainLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Search, Filter, Download, Eye } from "lucide-react";
import { getJson } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

interface ApiHistoricoEconomia {
  mes: string;
  valor: number;
}

interface ApiHistoricoFatura {
  id: string;
  referencia: string;
  vencimento: string;
  nota_fiscal_numero: string;
  total: number;
  status: "pendente" | "validado" | "erro";
}

interface ApiHistoricoCliente {
  unidade_consumidora: string;
  cliente_numero: string;
  nome: string;
  cnpj: string;
  cep: string;
  cidade_uf: string;
  desconto_contratado: number;
  subvencao: number;
  status: string;
  historico_economia: ApiHistoricoEconomia[];
  faturas: ApiHistoricoFatura[];
}

interface ApiHistoricoResponse {
  items: ApiHistoricoCliente[];
}

export default function HistoricoPage() {
  const [clientes, setClientes] = useState<ApiHistoricoCliente[]>([]);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCliente, setSelectedCliente] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    let cancelled = false;

    async function loadHistorico() {
      try {
        const response = await getJson<ApiHistoricoResponse>("/historico");
        if (!cancelled) {
          setClientes(response.items ?? []);
          if (!selectedCliente && response.items && response.items.length > 0) {
            setSelectedCliente(response.items[0].unidade_consumidora);
          }
        }
      } catch (error) {
        console.error(error);
        if (!cancelled) {
          toast({
            title: "Erro ao carregar historico",
            description: "Nao foi possivel buscar os dados reais do historico.",
            variant: "destructive",
          });
        }
      }
    }

    void loadHistorico();

    return () => {
      cancelled = true;
    };
  }, [toast]);

  const filteredClientes = clientes.filter(
    (cliente) =>
      cliente.nome.toLowerCase().includes(searchTerm.toLowerCase()) ||
      cliente.unidade_consumidora.includes(searchTerm)
  );

  const clienteSelecionado =
    clientes.find((cliente) => cliente.unidade_consumidora === selectedCliente) ?? null;

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(value);
  };

  return (
    <MainLayout
      title="Histórico"
      subtitle="Consulte o histórico de faturas e economia dos clientes"
    >
      <div className="space-y-6 animate-fade-in">
        <Card>
          <CardContent className="p-6">
            <div className="flex gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Buscar por nome ou unidade consumidora..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Button
                variant="outline"
                onClick={() =>
                  toast({
                    title: "Filtros mantidos simples",
                    description: "A busca textual ja esta integrada aos dados reais.",
                  })
                }
              >
                <Filter className="mr-2 h-4 w-4" /> Filtros
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  toast({
                    title: "Exportacao ainda nao integrada",
                    description: "Os dados reais ja estao visiveis, mas a exportacao nao faz parte desta entrega.",
                  })
                }
              >
                <Download className="mr-2 h-4 w-4" /> Exportar
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-1">
            <CardHeader>
              <CardTitle className="text-lg">Clientes ({filteredClientes.length})</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="max-h-[600px] overflow-y-auto">
                {filteredClientes.map((cliente) => (
                  <button
                    key={cliente.unidade_consumidora}
                    onClick={() => setSelectedCliente(cliente.unidade_consumidora)}
                    className={`w-full p-4 text-left border-b transition-colors hover:bg-muted/50 ${
                      selectedCliente === cliente.unidade_consumidora
                        ? "bg-primary/5 border-l-4 border-l-primary"
                        : ""
                    }`}
                  >
                    <p className="font-medium text-sm truncate">{cliente.nome}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">
                        UC: {cliente.unidade_consumidora}
                      </span>
                      <Badge
                        variant={cliente.status === "Ativo" ? "default" : "secondary"}
                        className="text-xs"
                      >
                        {cliente.status}
                      </Badge>
                    </div>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="lg:col-span-2 space-y-6">
            {clienteSelecionado ? (
              <>
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-xl">{clienteSelecionado.nome}</CardTitle>
                        <p className="text-sm text-muted-foreground mt-1">{clienteSelecionado.cnpj}</p>
                      </div>
                      <Badge variant={clienteSelecionado.status === "Ativo" ? "default" : "secondary"}>
                        {clienteSelecionado.status}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Unidade Consumidora</p>
                        <p className="font-medium">{clienteSelecionado.unidade_consumidora}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Cidade/UF</p>
                        <p className="font-medium">{clienteSelecionado.cidade_uf}</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Desconto Contratado</p>
                        <p className="font-medium">{clienteSelecionado.desconto_contratado}%</p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Subvenção</p>
                        <p className="font-medium">{formatCurrency(clienteSelecionado.subvencao)}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Histórico de Economia (R$)</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            {clienteSelecionado.historico_economia.map((item) => (
                              <TableHead key={item.mes} className="text-center min-w-[80px]">
                                {item.mes.split("/")[0]}
                              </TableHead>
                            ))}
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          <TableRow>
                            {clienteSelecionado.historico_economia.map((item) => (
                              <TableCell key={item.mes} className="text-center">
                                {item.valor > 0 ? (
                                  <span className="font-medium text-success">
                                    {formatCurrency(item.valor)}
                                  </span>
                                ) : (
                                  <span className="text-muted-foreground">R$ -</span>
                                )}
                              </TableCell>
                            ))}
                          </TableRow>
                        </TableBody>
                      </Table>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">
                      Faturas ({clienteSelecionado.faturas.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-0">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Referência</TableHead>
                          <TableHead>Vencimento</TableHead>
                          <TableHead>NF</TableHead>
                          <TableHead className="text-right">Total</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Ações</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {clienteSelecionado.faturas.map((fatura) => (
                          <TableRow key={fatura.id}>
                            <TableCell className="font-medium">{fatura.referencia}</TableCell>
                            <TableCell>{fatura.vencimento}</TableCell>
                            <TableCell className="font-mono">{fatura.nota_fiscal_numero}</TableCell>
                            <TableCell className="text-right font-medium">
                              {formatCurrency(fatura.total)}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={fatura.status === "validado" ? "default" : "secondary"}
                                className={
                                  fatura.status === "validado"
                                    ? "bg-success/10 text-success border-success/20"
                                    : fatura.status === "erro"
                                      ? "bg-destructive/10 text-destructive border-destructive/20"
                                      : ""
                                }
                              >
                                {fatura.status === "validado"
                                  ? "Validado"
                                  : fatura.status === "erro"
                                    ? "Erro"
                                    : "Pendente"}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() =>
                                  toast({
                                    title: "Use a tela de Faturas",
                                    description: `A fatura ${fatura.nota_fiscal_numero} pode ser inspecionada em detalhes na tela principal de Faturas.`,
                                  })
                                }
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                        {clienteSelecionado.faturas.length === 0 && (
                          <TableRow>
                            <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                              Nenhuma fatura encontrada para este cliente.
                            </TableCell>
                          </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </CardContent>
                </Card>
              </>
            ) : (
              <Card className="flex items-center justify-center h-[400px]">
                <div className="text-center text-muted-foreground">
                  <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Selecione um cliente para ver o histórico</p>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>
    </MainLayout>
  );
}
