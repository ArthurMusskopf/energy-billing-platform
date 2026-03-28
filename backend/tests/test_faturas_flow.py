import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api import faturas as faturas_api
from app.schemas.faturas import FaturaRevisaoCadastroRequestSchema, FaturaRevisaoRequestSchema, FaturaValidacaoRequestSchema
from app.services.calc_engine import CalcResult


class FaturasFlowTests(unittest.TestCase):
    def test_build_fatura_detail_payload_includes_leituras_itens_medidores_and_cadastro(self):
        workflow_df = pd.DataFrame(
            [
                {
                    "id": "123",
                    "nota_fiscal": "123",
                    "unidade_consumidora": "24021394",
                    "cliente_numero": "68397731",
                    "nome": "Cliente Teste",
                    "cnpj_cpf": "12345678901",
                    "referencia": "03/2026",
                    "vencimento": "25/03/2026",
                    "status_parse": "parseado",
                    "status_validacao": "pendente",
                    "status_calculo": "nao_calculada",
                    "observacoes": None,
                    "classe_modalidade": "B1 TRIFASICO",
                    "cidade_uf": "Joinville/SC",
                    "cep": "89200-000",
                }
            ]
        )
        itens_df = pd.DataFrame(
            [
                {
                    "id": "item-1",
                    "numero": "123",
                    "codigo": "0R",
                    "descricao": "Energia",
                    "quantidade_registrada": 30,
                    "leitura_anterior": "01/03/2026",
                    "leitura_atual": "31/03/2026",
                    "dias": 30,
                    "proxima_leitura": "30/04/2026",
                    "serie": "1",
                    "data_emissao": "31/03/2026",
                    "cidade_uf": "Joinville/SC",
                    "cep": "89200-000",
                }
            ]
        )
        medidores_df = pd.DataFrame(
            [
                {
                    "id": "med-1",
                    "medidor": "998877",
                    "tipo": "Energia",
                    "posto": "Unico",
                    "leitura_anterior": "100",
                    "leitura_atual": "200",
                    "total_apurado": 100,
                }
            ]
        )
        client_df = pd.DataFrame(
            [
                {
                    "unidade_consumidora": "24021394",
                    "cliente_numero": "68397731",
                    "desconto_contratado": 0.15,
                    "subvencao": 0,
                    "status": "Ativo",
                    "n_fases": 3,
                    "custo_disp": 100,
                }
            ]
        )

        payload = faturas_api._build_fatura_detail_payload(workflow_df, itens_df, medidores_df, client_df)

        self.assertEqual(payload["unidade_consumidora"], "24021394")
        self.assertEqual(payload["cliente_numero"], "68397731")
        self.assertEqual(payload["leitura_anterior"], "01/03/2026")
        self.assertEqual(payload["leitura_atual"], "31/03/2026")
        self.assertEqual(payload["dias"], 30)
        self.assertEqual(len(payload["itens"]), 1)
        self.assertEqual(len(payload["medidores"]), 1)
        self.assertTrue(payload["cadastro_cliente"]["uc_cadastrada"])
        self.assertTrue(payload["cadastro_cliente"]["cadastro_minimo_completo"])
        self.assertTrue(payload["pode_validar_calcular"])

    def test_revisao_persists_minimum_changes(self):
        workflow_df = pd.DataFrame(
            [
                {
                    "id": "123",
                    "unidade_consumidora": "24021394",
                    "cliente_numero": "68397731",
                    "nome": "Cliente Teste",
                    "cnpj_cpf": "12345678901",
                    "referencia": "03/2026",
                    "vencimento": "25/03/2026",
                    "status_parse": "parseado",
                    "status_validacao": "pendente",
                    "status_calculo": "nao_calculada",
                    "classe_modalidade": "B1 TRIFASICO",
                }
            ]
        )
        itens_df = pd.DataFrame(
            [
                {
                    "id": "item-1",
                    "numero": "123",
                    "unidade_consumidora": "24021394",
                    "cliente_numero": "68397731",
                    "leitura_atual": "31/03/2026",
                    "cidade_uf": "Joinville/SC",
                    "cep": "89200-000",
                }
            ]
        )
        medidores_df = pd.DataFrame(
            [
                {
                    "id": "med-1",
                    "nota_fiscal_numero": "123",
                    "unidade_consumidora": "24021394",
                    "cliente_numero": "68397731",
                }
            ]
        )
        client_df_after = pd.DataFrame(
            [
                {
                    "unidade_consumidora": "24021394",
                    "cliente_numero": "68397731",
                    "desconto_contratado": 0.15,
                    "subvencao": 0,
                    "status": "Ativo",
                    "custo_disp": 100,
                }
            ]
        )
        updated_workflow_df = workflow_df.copy()
        updated_workflow_df.loc[:, "leitura_atual"] = "01/04/2026"
        updated_workflow_df.loc[:, "cidade_uf"] = "Blumenau/SC"
        updated_workflow_df.loc[:, "cep"] = "89000-000"
        updated_itens_df = itens_df.copy()
        updated_itens_df.loc[:, "leitura_atual"] = "01/04/2026"
        updated_itens_df.loc[:, "cidade_uf"] = "Blumenau/SC"
        updated_itens_df.loc[:, "cep"] = "89000-000"
        updated_medidores_df = medidores_df.copy()
        payload = FaturaRevisaoRequestSchema(
            leitura_atual="01/04/2026",
            cidade_uf="Blumenau/SC",
            cep="89000-000",
            cadastro_cliente=FaturaRevisaoCadastroRequestSchema(
                unidade_consumidora="24021394",
                desconto_contratado=0.15,
                status="Ativo",
                custo_disp=100,
            ),
        )

        with patch.object(
            faturas_api,
            "_load_fatura_context",
            side_effect=[
                (workflow_df, itens_df, medidores_df, pd.DataFrame()),
                (updated_workflow_df, updated_itens_df, updated_medidores_df, client_df_after),
            ],
        ), patch.object(faturas_api, "_get_client_df", return_value=pd.DataFrame()), patch.object(
            faturas_api, "upsert_dataframe", return_value=1
        ) as mock_upsert:
            response = faturas_api.revisar_fatura("123", payload)

        tables = [call.args[1] for call in mock_upsert.call_args_list]
        self.assertIn(faturas_api.TABLE_FATURAS_WORKFLOW, tables)
        self.assertIn(faturas_api.TABLE_FATURA_ITENS, tables)
        self.assertIn(faturas_api.TABLE_MEDIDORES, tables)
        self.assertIn(faturas_api.TABLE_CLIENTES, tables)

        clientes_calls = [call for call in mock_upsert.call_args_list if call.args[1] == faturas_api.TABLE_CLIENTES]
        self.assertEqual(len(clientes_calls), 1)
        clientes_payload = clientes_calls[0].args[0]
        self.assertEqual(
            set(clientes_payload.columns),
            {"unidade_consumidora", "desconto_contratado", "subvencao", "status", "n_fases", "custo_disp", "updated_at"},
        )

        self.assertEqual(response["leitura_atual"], "01/04/2026")
        self.assertEqual(response["cidade_uf"], "Blumenau/SC")
        self.assertEqual(response["cadastro_cliente"]["status"], "Ativo")
        self.assertTrue(response["pode_validar_calcular"])

    def test_validar_e_calcular_blocks_incomplete_cadastro(self):
        workflow_df = pd.DataFrame(
            [
                {
                    "id": "123",
                    "unidade_consumidora": "24021394",
                    "cliente_numero": "68397731",
                    "classe_modalidade": "B1 TRIFASICO",
                    "status_parse": "parseado",
                }
            ]
        )
        itens_df = pd.DataFrame([{"id": "item-1", "numero": "123", "codigo": "0R", "quantidade_registrada": 10}])
        medidores_df = pd.DataFrame([{"id": "med-1", "nota_fiscal_numero": "123", "tipo": "Energia", "total_apurado": 50}])

        with patch.object(faturas_api, "_get_workflow_df", return_value=workflow_df), patch.object(
            faturas_api, "_get_itens_df", return_value=itens_df
        ), patch.object(faturas_api, "_get_medidores_df", return_value=medidores_df), patch.object(
            faturas_api, "_get_client_df", return_value=pd.DataFrame()
        ):
            with self.assertRaises(HTTPException) as exc:
                faturas_api.validar_e_calcular_fatura("123", FaturaValidacaoRequestSchema(usuario="teste"))

        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("unidade_consumidora", exc.exception.detail["fields"])
        self.assertIn("desconto_contratado", exc.exception.detail["fields"])
        self.assertIn("status", exc.exception.detail["fields"])

    def test_validar_e_calcular_success_persists_boleto_and_updates_workflow(self):
        workflow_df = pd.DataFrame(
            [
                {
                    "id": "123",
                    "referencia": "03/2026",
                    "vencimento": "25/03/2026",
                    "nome": "Cliente Teste",
                    "cliente_numero": "68397731",
                    "unidade_consumidora": "24021394",
                    "cnpj_cpf": "12345678901",
                    "total_pagar": 120.0,
                    "status_parse": "parseado",
                }
            ]
        )
        itens_df = pd.DataFrame(
            [
                {
                    "id": "item-1",
                    "numero": "123",
                    "cep": "89200-000",
                    "cidade_uf": "Joinville/SC",
                    "codigo": "0R",
                    "quantidade_registrada": 50.0,
                    "total_pagar": 120.0,
                    "descricao": "Energia",
                    "tarifa": 0.8,
                    "unidade_consumidora": "24021394",
                }
            ]
        )
        medidores_df = pd.DataFrame(
            [
                {
                    "id": "med-1",
                    "nota_fiscal_numero": "123",
                    "tipo": "Energia",
                    "total_apurado": 150.0,
                }
            ]
        )
        client_df = pd.DataFrame(
            [
                {
                    "unidade_consumidora": "24021394",
                    "cliente_numero": "68397731",
                    "desconto_contratado": 0.15,
                    "subvencao": 0,
                    "status": "Ativo",
                    "custo_disp": 100,
                }
            ]
        )
        calc_result = CalcResult(
            df_boletos=pd.DataFrame(
                [
                    {
                        "numero": "123",
                        "med_inj_tusd": 50.0,
                        "injetada": 50.0,
                        "valor_total_boleto": 40.0,
                        "tarifa_bol": 0.8,
                        "tarifa_total_boleto": 0.8,
                        "valor_band_amar_desc": 0.0,
                        "valor_band_vrm_desc": 0.0,
                        "energia_inj_tusd_tarifa": 0.0,
                        "energia_injet_te_tarifa": 0.0,
                    }
                ]
            ),
            missing_clientes=[],
            missing_reason={},
        )

        def fake_update(fatura_id: str, updates: dict):
            return {"id": fatura_id, **updates}

        with patch.object(faturas_api, "_get_workflow_df", return_value=workflow_df), patch.object(
            faturas_api, "_get_itens_df", return_value=itens_df
        ), patch.object(faturas_api, "_get_medidores_df", return_value=medidores_df), patch.object(
            faturas_api, "_get_client_df", return_value=client_df
        ), patch.object(
            faturas_api, "calculate_boletos", return_value=calc_result
        ), patch.object(
            faturas_api, "_get_boleto_df", return_value=pd.DataFrame()
        ), patch.object(
            faturas_api, "upsert_dataframe", return_value=1
        ) as mock_upsert, patch.object(
            faturas_api, "_update_workflow_row", side_effect=fake_update
        ) as mock_update:
            response = faturas_api.validar_e_calcular_fatura("123", FaturaValidacaoRequestSchema(usuario="frontend"))

        self.assertEqual(response["status_validacao"], "validada")
        self.assertEqual(response["status_calculo"], "calculada")
        self.assertEqual(mock_upsert.call_args.args[1], faturas_api.TABLE_BOLETOS)
        update_payload = mock_update.call_args.args[1]
        self.assertEqual(update_payload["status_validacao"], "validada")
        self.assertEqual(update_payload["validado_por"], "frontend")
        self.assertEqual(update_payload["status_calculo"], "calculada")


if __name__ == "__main__":
    unittest.main()
