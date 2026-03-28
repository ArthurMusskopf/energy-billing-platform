import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api import boletos as boletos_api


class BoletosApiTests(unittest.TestCase):
    def test_list_boletos_returns_real_rows_from_table_boletos(self):
        df_items = pd.DataFrame(
            [
                {
                    "id": "123",
                    "workflow_id": "123",
                    "nota_fiscal": "123",
                    "referencia": "03/2026",
                    "vencimento": "25/03/2026",
                    "unidade_consumidora": "24021394",
                    "cliente_numero": "68397731",
                    "nome": "Cliente Teste",
                    "cnpj_cpf": "12345678901",
                    "cep": "89200-000",
                    "cidade_uf": "Joinville/SC",
                    "desconto_contratado": 0.15,
                    "subvencao": 0.0,
                    "status_cliente": "Ativo",
                    "status_validacao": "validado",
                    "status_calculo": "calculado",
                    "status_emissao": "nao_emitido",
                    "leitura_anterior": "01/03/2026",
                    "leitura_atual": "31/03/2026",
                    "dias": 30,
                    "proxima_leitura": "30/04/2026",
                    "energia_compensada": 50.0,
                    "tarifa_sem_desconto": 0.8,
                    "tarifa_com_desconto": 0.68,
                    "percentual_desconto": 15.0,
                    "bandeiras": 3.0,
                    "bandeiras_com_desconto": 0.0,
                    "valor_total": 40.0,
                    "valor_concessionaria": 120.0,
                    "economia_gerada": 80.0,
                }
            ]
        )
        df_total = pd.DataFrame([{"total": 1}])

        with patch.object(boletos_api, "execute_query", side_effect=[df_items, df_total]):
            response = boletos_api.list_boletos(limit=100, offset=0)

        self.assertEqual(response["total"], 1)
        self.assertEqual(len(response["items"]), 1)
        item = response["items"][0]
        self.assertEqual(item["id"], "123")
        self.assertEqual(item["status_validacao"], "validada")
        self.assertEqual(item["status_calculo"], "calculada")
        self.assertEqual(item["status"], "calculada")
        self.assertEqual(item["unidade_consumidora"], "24021394")
        self.assertEqual(item["valor_total"], 40.0)


if __name__ == "__main__":
    unittest.main()
