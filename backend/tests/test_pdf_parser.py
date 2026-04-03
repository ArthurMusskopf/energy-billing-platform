
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

    def test_parse_unidade_consumidora_accepts_7_digit_uc_in_header_block(self):
        text = """
        COMERCIAL - OUTROS SERVICOS
        NOME: HOTEL UNIAO LTDA
        4299949
        CPF/CNPJ: 82.819.665/0001-96
        ENDERECO: DO COMERCIO 414 - CENTRO Cliente: 15673885 NOTA FISCAL Nº046259038 SERIE:001 DATA EMISSAO:09/05/2025
        """

        cliente_numero = parse_cliente_numero(text)
        unidade_consumidora = parse_unidade_consumidora(text, cliente_numero=cliente_numero)

        self.assertEqual(cliente_numero, "15673885")
        self.assertEqual(unidade_consumidora, "4299949")

    def test_parse_unidade_consumidora_ignores_nf_and_nosso_numero_in_canhoto(self):
        text = """
        Unidade Consumidora Nosso Número Referência Vencimento
        09/05/2025 202505-046279454 0004311469 17801790790 05/2025 12/06/2025
        Cliente: 64166808
        NOTA FISCAL Nº046279454 SERIE:001 DATA EMISSAO:09/05/2025
        """

        cliente_numero = parse_cliente_numero(text)
        unidade_consumidora = parse_unidade_consumidora(text, cliente_numero=cliente_numero)

        self.assertEqual(cliente_numero, "64166808")
        self.assertEqual(unidade_consumidora, "4311469")


if __name__ == "__main__":
    unittest.main()
