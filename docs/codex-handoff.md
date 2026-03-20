# Codex Handoff - energy-billing-platform

## Objetivo do produto

Preservar o frontend do `energy-billing-hub` o mais fiel possivel, substituindo gradualmente o backend antigo em Streamlit do `erb_tech_acer` por um backend novo em FastAPI, com persistencia em BigQuery e futura integracao com Sicoob.

## Arquitetura atual

- `frontend/`: app React/Vite/TypeScript herdado do `energy-billing-hub`
- `backend/`: app FastAPI novo
- `infra/nginx/`: proxy reverso
- `docker-compose.yml`: sobe frontend, backend e nginx
- `docs/`: documentacao operacional e de handoff

## Estado funcional verificado

### Infraestrutura

- O projeto sobe com `docker compose up --build`
- Frontend funcional em `http://localhost` e `http://localhost:8080`
- Backend funcional em `http://localhost:8000`
- Swagger funcional em `http://localhost:8000/docs`

### Backend funcional

Rotas expostas e verificadas:

- `GET /api/v1/faturas`
- `POST /api/v1/faturas/parse`
- `GET /api/v1/faturas/{id}`
- `PATCH /api/v1/faturas/{id}/validar`
- `POST /api/v1/faturas/{id}/calcular`
- `GET /api/v1/boletos`
- `GET /api/v1/dashboard/resumo`
- `GET /api/v1/historico`

### Persistencia atual

O parse persiste os dados necessarios para o fluxo ate pre-boleto:

- `faturas_workflow`
- `fatura_itens`
- `medidores_leituras`

O calculo persiste o resultado pre-boleto em:

- `boletos_calculados`

### Frontend integrado com dados reais

#### Faturas

- lista real via `GET /api/v1/faturas`
- upload/parse real via `POST /api/v1/faturas/parse`
- detalhe expandido real via `GET /api/v1/faturas/{id}`
- validacao real via `PATCH /api/v1/faturas/{id}/validar`
- calculo real ate pre-boleto via `POST /api/v1/faturas/{id}/calcular`

#### Boletos

- listagem pre-boleto real via `GET /api/v1/boletos`
- acao principal da tela dispara calculo real
- emissao/elaboracao final nao esta implementada nesta etapa

#### Dashboard

- KPIs, series e ranking alimentados por `GET /api/v1/dashboard/resumo`

#### Historico

- clientes, historico de economia e tabela de faturas alimentados por `GET /api/v1/historico`

## Regra principal do projeto

**Preservar o frontend do `energy-billing-hub` ao maximo.**

Sempre que possivel:

- adaptar o backend ao frontend
- minimizar mudancas visuais
- evitar reescrever componentes desnecessariamente
- fazer mudancas pequenas e revisaveis

## O que esta fora do escopo atual

- emissao/elaboracao final via Sicoob
- geracao final de PDF/demonstrativo bancario
- refactors amplos de frontend
- adicao de credenciais reais ao codigo

## Como testar localmente

1. Rodar:

   `docker compose up --build`

2. Abrir:

   - `http://localhost`
   - `http://localhost:8080`
   - `http://localhost:8000/docs`

3. Validar em Swagger:

   - `GET /api/v1/faturas`
   - `POST /api/v1/faturas/parse`
   - `GET /api/v1/faturas/{id}`
   - `PATCH /api/v1/faturas/{id}/validar`
   - `POST /api/v1/faturas/{id}/calcular`
   - `GET /api/v1/boletos`
   - `GET /api/v1/dashboard/resumo`
   - `GET /api/v1/historico`

4. Validar na UI:

   - Faturas lista, faz upload, expande detalhe, valida e calcula
   - Boletos lista dados reais e dispara calculo
   - Dashboard carrega dados reais
   - Historico carrega dados reais

## Arquivos mais sensiveis

- `frontend/src/pages/FaturasPage.tsx`
- `frontend/src/components/faturas/FaturaTable.tsx`
- `frontend/src/pages/BoletosPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/HistoricoPage.tsx`
- `backend/app/api/faturas.py`
- `backend/app/api/router.py`
- `backend/app/services/pdf_parser.py`
- `backend/app/services/calc_engine.py`
- `backend/app/services/workflow_adapter.py`
- `backend/app/services/reporting_dataset.py`
- `backend/app/clients/bigquery_client.py`

## Restricoes

- nao commitar secrets reais
- manter `.env` e credenciais fora do Git
- nao reestruturar o frontend desnecessariamente
- nao quebrar a UX atual
- nao implementar emissao/elaboracao final via Sicoob nesta etapa

## Proximo passo logico

- preparar a etapa de revisao final do pre-boleto
- definir geracao de demonstrativo/PDF antes de qualquer emissao bancaria
- so depois abrir a integracao operacional de emissao via Sicoob
