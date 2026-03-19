\# Codex Handoff - energy-billing-platform



\## Objetivo do produto

Preservar o frontend do `energy-billing-hub` o mais fiel possível, substituindo gradualmente o backend antigo em Streamlit do `erb\_tech\_acer` por um backend novo em FastAPI, com persistência em BigQuery e futura integração com Sicoob.



\## Arquitetura atual

\- `frontend/`: app React/Vite/TypeScript herdado do `energy-billing-hub`

\- `backend/`: app FastAPI novo

\- `infra/nginx/`: proxy reverso

\- `docker-compose.yml`: sobe frontend, backend e nginx

\- `docs/`: documentação de integração e handoff



\## Estado atual do projeto

\### Infraestrutura

\- Projeto sobe com `docker compose up --build`

\- Frontend funcional em `http://localhost`

\- Backend funcional em `http://localhost:8000`

\- Swagger funcional em `http://localhost:8000/docs`



\### Backend já implementado

\#### Base

\- `backend/app/core/config.py`

\- `backend/app/clients/bigquery\_client.py`

\- `backend/app/clients/sicoob\_client.py`



\#### Serviços portados do backend antigo

\- `backend/app/services/pdf\_parser.py`

\- `backend/app/services/calc\_engine.py`

\- `backend/app/services/workflow\_adapter.py`

\- `backend/app/services/reporting\_dataset.py`



\#### Rotas já funcionais

\- `POST /api/v1/faturas/parse`

&#x20; - faz upload de PDFs

&#x20; - parseia faturas reais

&#x20; - monta workflow

&#x20; - persiste em `football-data-science.erb\_tech.faturas\_workflow`

\- `GET /api/v1/faturas`

&#x20; - lista workflow real direto do BigQuery



\### Frontend já integrado

A tela `FaturasPage.tsx` já foi adaptada para:

\- consumir `GET /api/v1/faturas`

\- enviar PDFs para `POST /api/v1/faturas/parse`

\- recarregar a lista após upload

\- preservar os componentes visuais existentes:

&#x20; - `UploadZone`

&#x20; - `ProcessingSummary`

&#x20; - `FaturaTable`



\## Regra principal do projeto

\*\*Preservar o frontend do `energy-billing-hub` ao máximo.\*\*



Sempre que possível:

\- adaptar o backend ao frontend

\- minimizar mudanças visuais

\- evitar reescrever componentes desnecessariamente

\- fazer mudanças pequenas e revisáveis



\## O que ainda está pendente

\### Na tela de Faturas

\- detalhe expandido ainda usa placeholders

\- botão de validar ainda não muda status real no backend

\- itens/leituras/medidores ainda não vêm de endpoint de detalhe



\### Outras áreas

\- Boletos ainda não ligados ao backend real

\- Dashboard ainda não ligado ao backend real

\- Histórico ainda não ligado ao backend real

\- Emissão Sicoob ainda não exposta em rotas operacionais novas



\## Próxima tarefa recomendada para o Codex

\### Implementar detalhe real da fatura

\#### Backend

Criar:

\- `GET /api/v1/faturas/{id}`



Essa rota deve retornar, idealmente:

\- cabeçalho da fatura

\- itens parseados

\- dados de leitura/período

\- medidores, se disponíveis



\#### Frontend

Integrar a expansão da `FaturaTable` para consumir dados reais dessa rota.



\## Critérios de aceite da próxima tarefa

\- backend sobe sem erro com `docker compose up --build`

\- rota aparece no Swagger

\- ao expandir uma fatura na UI, aparecem dados reais

\- upload e listagem continuam funcionando

\- layout atual da tela de Faturas é preservado

\- nenhuma credencial real é adicionada ao código



\## Como testar localmente

1\. Rodar:

&#x20;  `docker compose up --build`

2\. Abrir:

&#x20;  - `http://localhost`

&#x20;  - `http://localhost:8000/docs`

3\. Testar:

&#x20;  - `GET /api/v1/faturas`

&#x20;  - `POST /api/v1/faturas/parse`

4\. Validar que a tela de Faturas lista workflow real e faz upload real



\## Arquivos mais sensíveis

\- `frontend/src/pages/FaturasPage.tsx`

\- `frontend/src/components/faturas/FaturaTable.tsx`

\- `backend/app/api/faturas.py`

\- `backend/app/api/router.py`

\- `backend/app/services/pdf\_parser.py`

\- `backend/app/services/calc\_engine.py`

\- `backend/app/services/workflow\_adapter.py`

\- `backend/app/services/reporting\_dataset.py`

\- `backend/app/clients/bigquery\_client.py`



\## Restrições

\- não commitar secrets reais

\- manter `.env` e credenciais fora do Git

\- não reestruturar o frontend desnecessariamente

\- não quebrar a UX atual



\## Próximo passo após a tarefa de detalhe

\- `PATCH /api/v1/faturas/{id}/validar`

\- depois integração real da tela de Boletos

