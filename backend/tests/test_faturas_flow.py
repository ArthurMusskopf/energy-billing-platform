import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api import faturas as faturas_api
from app.schemas.faturas import FaturaValidacaoRequestSchema
from app.services.calc_engine import CalcResult


class FaturasFlowTests(unittest.TestCase):
    def test_build_fatura_detail_payload_includes_medidores_and_cadastro(self):
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
                    "nome": "Cliente Teste",
                    "cnpj_cpf": "12345678901",
                    "cep": "89200-000",
                    "cidade_uf": "Joinville/SC",
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
        self.assertEqual(len(payload["medidores"]), 1)
        self.assertTrue(payload["cadastro_cliente"]["cadastro_minimo_completo"])
        self.assertTrue(payload["pode_validar_calcular"])

    def test_validar_fatura_blocks_incomplete_cadastro(self):
        workflow_df = pd.DataFrame([{"id": "123", "classe_modalidade": "B1 TRIFASICO"}])
        itens_df = pd.DataFrame([{"id": "item-1"}])
        medidores_df = pd.DataFrame([{"id": "med-1"}])
        client_df = pd.DataFrame()

        with patch.object(
            faturas_api,
            "_load_fatura_context",
            return_value=(workflow_df, itens_df, medidores_df, client_df),
        ), patch.object(
            faturas_api,
            "_build_cadastro_cliente_payload",
            return_value={
                "campos_pendentes": ["desconto_contratado", "subvencao"],
                "cadastro_minimo_completo": False,
                "elegivel_para_calculo": False,
            },
        ):
            with self.assertRaises(HTTPException) as exc:
                faturas_api.validar_fatura("123", FaturaValidacaoRequestSchema(usuario="teste"))

        self.assertEqual(exc.exception.status_code, 400)
        self.assertIn("desconto_contratado", exc.exception.detail["fields"])

    def test_calculate_impl_marks_validation_when_needed(self):
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
                    "status_validacao": "pendente",
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
                }
            ]
        )
        medidores_df = pd.DataFrame([{"id": "med-1"}])
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
            faturas_api, "_build_client_df_for_calc", return_value=client_df
        ), patch.object(
            faturas_api, "calculate_boletos", return_value=calc_result
        ), patch.object(
            faturas_api, "_get_boleto_df", return_value=pd.DataFrame()
        ), patch.object(
            faturas_api, "upsert_dataframe", return_value=1
        ), patch.object(
            faturas_api, "_update_workflow_row", side_effect=fake_update
        ) as mock_update:
            response = faturas_api._calculate_fatura_impl("123", usuario_validacao="frontend")

        self.assertEqual(response["status_calculo"], "calculado")
        update_payload = mock_update.call_args.args[1]
        self.assertEqual(update_payload["status_validacao"], "validado")
        self.assertEqual(update_payload["validado_por"], "frontend")


if __name__ == "__main__":
    unittest.main()
