import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.pdf_parser import parse_cliente_numero, parse_unidade_consumidora


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


if __name__ == "__main__":
    unittest.main()
