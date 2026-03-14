import { MainLayout } from "@/components/layout/MainLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Database, Key, Bell, Shield, Save } from "lucide-react";

export default function ConfiguracoesPage() {
  return (
    <MainLayout 
      title="Configurações" 
      subtitle="Gerencie as configurações do sistema"
    >
      <div className="space-y-6 animate-fade-in max-w-4xl">
        {/* BigQuery */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                <Database className="h-5 w-5 text-primary" />
              </div>
              <div>
                <CardTitle>Google BigQuery</CardTitle>
                <CardDescription>Configurações de conexão com o banco de dados</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="project-id">Project ID</Label>
                <Input id="project-id" placeholder="football-data-science" defaultValue="football-data-science" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="dataset-id">Dataset ID</Label>
                <Input id="dataset-id" placeholder="erb_tech" defaultValue="erb_tech" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="table-faturas">Tabela Faturas</Label>
                <Input id="table-faturas" placeholder="fatura_itens" defaultValue="fatura_itens" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="table-medidores">Tabela Medidores</Label>
                <Input id="table-medidores" placeholder="medidores_leituras" defaultValue="medidores_leituras" />
              </div>
            </div>
            <div className="flex justify-end">
              <Button>
                <Save className="mr-2 h-4 w-4" /> Salvar Alterações
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* API Keys */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-warning/10">
                <Key className="h-5 w-5 text-warning" />
              </div>
              <div>
                <CardTitle>Chaves de API</CardTitle>
                <CardDescription>Configure as chaves de integração</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="sicoob-key">API Sicoob (Boletos)</Label>
              <Input id="sicoob-key" type="password" placeholder="••••••••••••••••" />
              <p className="text-xs text-muted-foreground">Integração com Sicoob para geração automática de boletos (em desenvolvimento)</p>
            </div>
            <Separator />
            <div className="space-y-2">
              <Label htmlFor="gcp-credentials">Credenciais GCP</Label>
              <Input id="gcp-credentials" type="file" accept=".json" />
              <p className="text-xs text-muted-foreground">Arquivo JSON de credenciais do Google Cloud Platform</p>
            </div>
          </CardContent>
        </Card>

        {/* Notificações */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-chart-2/10">
                <Bell className="h-5 w-5 text-chart-2" />
              </div>
              <div>
                <CardTitle>Notificações</CardTitle>
                <CardDescription>Configure alertas e notificações do sistema</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Alertas de Sanidade</p>
                <p className="text-sm text-muted-foreground">Notificar quando valores estiverem fora do padrão</p>
              </div>
              <Switch defaultChecked />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Erros de Processamento</p>
                <p className="text-sm text-muted-foreground">Notificar falhas no parsing de faturas</p>
              </div>
              <Switch defaultChecked />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Boletos Pendentes</p>
                <p className="text-sm text-muted-foreground">Lembrete diário de boletos não validados</p>
              </div>
              <Switch />
            </div>
          </CardContent>
        </Card>

        {/* Parâmetros de Sanidade */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-success/10">
                <Shield className="h-5 w-5 text-success" />
              </div>
              <div>
                <CardTitle>Parâmetros de Sanidade</CardTitle>
                <CardDescription>Configure os limites para alertas de desvio</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="desvio-warning">Desvio para Aviso (%)</Label>
                <Input id="desvio-warning" type="number" placeholder="30" defaultValue="30" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="desvio-error">Desvio para Erro (%)</Label>
                <Input id="desvio-error" type="number" placeholder="50" defaultValue="50" />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Valores que desviam mais que o limite serão destacados nas faturas processadas.
              Avisos são mostrados em amarelo e erros em vermelho.
            </p>
            <div className="flex justify-end">
              <Button>
                <Save className="mr-2 h-4 w-4" /> Salvar Alterações
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </MainLayout>
  );
}
