# Diagnóstico de Integração Front-end (energy-billing-hub) × Back-end (erb-tech-acer)

Data: 2026-03-28

## 1) Leitura executiva

O projeto está em uma **fase intermediária de migração**: a trilha de faturas já saiu do mock e já conversa com a API + BigQuery, mas os módulos críticos de operação de negócio (boletos, dashboard, histórico, validação operacional e rastreabilidade completa do crédito compensado) ainda estão em estado base/planejado.

Em termos de maturidade, vocês estão aproximadamente em:

- **Fase 2 concluída parcialmente / Fase 3 iniciada**, conforme o plano de integração do repositório.
- A UI principal existe e está funcional para fluxo inicial, mas o backend novo ainda não cobre o ciclo completo de faturamento e repasse.

## 2) O que já existe e funciona

### 2.1 Back-end novo (FastAPI)

- Estrutura da aplicação FastAPI, CORS e roteador principal ativos.
- Rota de saúde e meta para observabilidade básica de módulos.
- Pipeline real de faturas:
  - `POST /api/v1/faturas/parse` recebe PDFs, processa lote, monta workflow e tenta persistir no BigQuery.
  - `GET /api/v1/faturas` lista workflow real com filtros e paginação.
- Clientes de integração estruturados para BigQuery e Sicoob.
- Serviços portados do legado para parsing/cálculo/workflow/reporting já presentes no backend novo.

### 2.2 Front-end (energy-billing-hub adaptado)

- Página de faturas já consome API real (`GET /faturas` e `POST /faturas/parse`) e exibe retorno no layout existente.
- Front-end mantém padrão visual e componentes originais, conforme diretriz de preservação.

## 3) Lacunas de implementação (foco no back-end da nova versão)

## 3.1 Domínio de faturas ainda incompleto

1. **Sem endpoint de detalhe da fatura (`GET /api/v1/faturas/{id}`)**
   - A expansão da tabela no front ainda usa placeholders para itens, leituras e medidores.

2. **Sem endpoint de validação operacional (`PATCH /api/v1/faturas/{id}/validar`)**
   - Botão “Validar” no front não altera estado real no workflow.

3. **Sem trilha completa de auditoria de correções manuais**
   - Há tabela/referência para log de edição no cliente BigQuery, mas não há rotas operacionais de edição + persistência + trilha de usuário expostas no backend atual.

## 3.2 Boletos (núcleo financeiro) ainda não operacional

1. **Endpoint `/api/v1/boletos` ainda retorna vazio com mensagem de “próxima etapa”**.
2. **Falta pipeline HTTP de cálculo de boletos no backend** (apesar de já existir `calc_engine.py`).
3. **Falta orquestração de emissão Sicoob exposta em rotas** (cliente já existe, mas falta fluxo API end-to-end).
4. **Falta modelagem explícita de repasse para gerador** por energia gerada × compensada (com rateio e fechamento por competência).

## 3.3 Dashboard e histórico ainda em estado “stub”

1. **`/api/v1/dashboard/resumo` retorna arrays vazios**.
2. **`/api/v1/historico` retorna payload base sem dados reais**.
3. **Front de Dashboard/Boletos/Histórico ainda depende de `@/data/mockData`**, mas o arquivo não está no repositório atual, indicando pendência de migração/organização dos dados de UI.

## 3.4 Rastreabilidade de créditos e “grafo de negócio” (ponto mais crítico)

Pelo processo descrito (gerador → lista de compensação → consumidor → créditos acumulados/subvenção/autossuficiência), o backend novo **ainda não expõe**:

1. Entidades e APIs para:
   - associação gerador-consumidor,
   - listas de compensação homologadas por competência,
   - saldo de créditos por UC (entrada, consumo, sobra, expiração/regra),
   - rastreio de origem do crédito utilizado no boleto.
2. Regras explícitas de exceção de compensação:
   - subvenção com zero necessidade externa,
   - autossuficiência por geração própria,
   - consumo de créditos antigos antes de novas entradas.
3. Fechamento contábil-operacional completo:
   - “quanto foi gerado”, “quanto foi compensado”, “quanto ficou em crédito”, “quanto virou cobrança”, “quanto vira pagamento ao gerador”.

## 4) Estágio atual versus aspiração do projeto

### Aspiração declarada

- Automação ponta-a-ponta: parse → validação → cálculo cobrança → emissão boleto → pagamentos geradores → acompanhamento gerencial.
- Rastreabilidade dos créditos.
- Vinculação gerador-beneficiário.
- Otimização da criação das Listas de Compensação.

### Estágio observado

- **Conquistado:** ingestão e workflow inicial de faturas.
- **Parcial:** base técnica para BigQuery/Sicoob e motor de cálculo legado portado.
- **Não conquistado ainda:** execução operacional completa de cobrança/repasse com rastreabilidade e governança de créditos.

## 5) Próximos passos recomendados (priorizados)

## Sprint A — Fechar o ciclo mínimo operacional (MVP funcional)

1. Implementar `GET /api/v1/faturas/{id}` com detalhes reais:
   - cabeçalho, itens, medidores, leituras, alertas e histórico de edição.
2. Implementar `PATCH /api/v1/faturas/{id}/validar`:
   - atualização de status,
   - `validado_por`, `validado_em`,
   - idempotência e controle de concorrência.
3. Expor `POST /api/v1/boletos/calcular` e `GET /api/v1/boletos`:
   - usar `calc_engine.py` com insumos versionados por competência.
4. Integrar página de boletos ao backend real (remover mock desse fluxo).

## Sprint B — Rastreabilidade e compliance do crédito energético

1. Modelar tabelas de domínio no BigQuery:
   - `associados`, `usinas_geradoras`, `listas_compensacao`, `creditos_ledger`, `alocacoes_credito`, `fechamentos_competencia`.
2. Criar ledger de créditos (estilo contábil):
   - evento, origem, destino, referência normativa, competência e usuário/processo.
3. Implementar motor de alocação:
   - prioridade de consumo de créditos antigos,
   - regras de subvenção/autossuficiência,
   - cálculo de sobra e carry-over.

## Sprint C — Emissão financeira e repasse

1. Expor API operacional Sicoob (`emitir`, `consultar`, `segunda via`, `status`).
2. Persistir rastros de emissão (request/response/status) para auditoria.
3. Implementar cálculo de repasse ao gerador:
   - base = energia gerada e efetivamente compensada,
   - visões por usina, gerador e competência.

## Sprint D — Gestão e confiabilidade

1. Dashboard real (`/dashboard/resumo`) com KPIs de:
   - energia gerada/compensada,
   - saldo de créditos,
   - receita da associação,
   - passivo de repasse a geradores.
2. Histórico real (`/historico`) com filtros por UC, gerador, competência e status.
3. Observabilidade mínima:
   - logs estruturados,
   - correlação por `request_id`,
   - métricas de pipeline e falhas.
4. Testes:
   - unitários (motores de cálculo),
   - integração (BigQuery/Sicoob mocked),
   - contrato de API com front.

## 6) Riscos atuais (se seguir sem fechar lacunas)

- Erros de cobrança ou repasse por ausência de ledger explícito de crédito.
- Dificuldade de auditoria/regulatório em divergências com associados/concessionária.
- Acúmulo de dívida técnica por coexistência de UI mock + backend parcial.
- Dificuldade para escalar operação com múltiplas usinas/listas de compensação.

## 7) Recomendação objetiva de foco imediato

Para tornar o produto **funcional para operação real** no menor caminho:

1. Fechar **faturas detalhe + validação**.
2. Fechar **cálculo e listagem real de boletos**.
3. Implementar **ledger de créditos e alocação por competência** (mesmo em versão inicial).
4. Só então expandir dashboard avançado.

Isso reduz risco financeiro e aumenta confiabilidade operacional logo no curto prazo.
