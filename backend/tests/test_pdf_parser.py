import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.pdf_parser import parse_cliente_numero, parse_periodo_leituras, parse_unidade_consumidora


class PdfParserTests(unittest.TestCase):
    def test_parse_unidade_consumidora_prefers_real_uc_over_cliente_codigo(self):
        text = """
        Unidade Consumidora
        024021394
        Cliente: 68397731
        """

        cliente_numero = parse_cliente_numero(text)
        unidade_consumidora = parse_unidade_consumidora(text, cliente_numero=cliente_numero)

        self.assertEqual(cliente_numero, "68397731")
        self.assertEqual(unidade_consumidora, "24021394")

    def test_parse_unidade_consumidora_does_not_fallback_to_cliente_codigo(self):
        text = """
        068397731
        Nome qualquer
        Cliente: 68397731
        """

        unidade_consumidora = parse_unidade_consumidora(text, cliente_numero="68397731")

        self.assertIsNone(unidade_consumidora)

    def test_parse_unidade_consumidora_accepts_uc_from_explicit_header_slot_even_if_equal_to_cliente(self):
        text = """
        Unidade Consumidora Nosso Número Referência Vencimento Total a Pagar (R$)
        21/01/2026 202601-077489757 0010511267 01/2026 18/02/2026 301,35
        Cliente:10511267
        """

        unidade_consumidora = parse_unidade_consumidora(text, cliente_numero="10511267")

        self.assertEqual(unidade_consumidora, "10511267")

    def test_parse_periodo_leituras_accepts_compact_line_with_lida_token(self):
        text = """
        19/12/2025 21/01/2026 33 Lida 20/02/2026 Amarela R$ 0,01885
        """

        periodo = parse_periodo_leituras(text)

        self.assertEqual(periodo["leitura_anterior"], "19/12/2025")
        self.assertEqual(periodo["leitura_atual"], "21/01/2026")
        self.assertEqual(periodo["dias"], 33)
        self.assertEqual(periodo["proxima_leitura"], "20/02/2026")

    def test_parse_periodo_leituras_prefers_compact_line_days_over_historic_dias_label_noise(self):
        text = """
        Consumo Faturado Dias Faturados
        DEZ/25 1207 25
        19/12/2025 21/01/2026 33 Lida 20/02/2026 Amarela R$ 0,01885
        """

        periodo = parse_periodo_leituras(text)

        self.assertEqual(periodo["dias"], 33)


if __name__ == "__main__":
    unittest.main()
