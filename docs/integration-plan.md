# Integration Plan - energy-billing-platform

## Objetivo
Usar o frontend do energy-billing-hub como base visual principal, conectando-o ao motor operacional do erb_tech_acer via uma nova API FastAPI.

## Fase 1
- Criar monorepo
- Configurar backend base
- Configurar frontend para consumir API
- Preparar docker-compose e nginx
- Padronizar variáveis de ambiente

## Fase 2
- Extrair configuração BigQuery para fora do Streamlit
- Extrair configuração Sicoob para fora do Streamlit
- Portar módulos utilitários do erb_tech_acer

## Fase 3
- Implementar endpoints reais:
  - faturas
  - boletos
  - dashboard
  - histórico

## Fase 4
- Substituir mocks do frontend por chamadas reais
- Ajustar estados, loading e errors

## Fase 5
- Preparar deploy definitivo na VPS
- SSL
- backup de arquivos
- observabilidade mínima
