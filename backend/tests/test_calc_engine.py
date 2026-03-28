import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.calc_engine import _energia_injetada_tarifa, _norm_text


class CalcEngineTests(unittest.TestCase):
    def test_energia_injetada_tarifa_uses_weighted_average_for_non_generator(self):
        dfi = pd.DataFrame(
            [
                {
                    "numero": "123",
                    "descricao": "Energia Inj. TUSD",
                    "_desc_norm": _norm_text("Energia Inj. TUSD"),
                    "tarifa": 0.2,
                    "quantidade_registrada": 40.0,
                },
                {
                    "numero": "123",
                    "descricao": "Energia Inj. TUSD",
                    "_desc_norm": _norm_text("Energia Inj. TUSD"),
                    "tarifa": 0.5,
                    "quantidade_registrada": 60.0,
                },
                {
                    "numero": "123",
                    "descricao": "Energia Injet. TE",
                    "_desc_norm": _norm_text("Energia Injet. TE"),
                    "tarifa": 0.1,
                    "quantidade_registrada": 40.0,
                },
                {
                    "numero": "123",
                    "descricao": "Energia Injet. TE",
                    "_desc_norm": _norm_text("Energia Injet. TE"),
                    "tarifa": 0.4,
                    "quantidade_registrada": 60.0,
                },
            ]
        )

        tarifa_tusd = _energia_injetada_tarifa(dfi, "123", "Energia Inj. TUSD", 100.0, 1, 0)
        tarifa_te = _energia_injetada_tarifa(dfi, "123", "Energia Injet. TE", 100.0, 1, 0)

        self.assertAlmostEqual(tarifa_tusd, 0.38, places=6)
        self.assertAlmostEqual(tarifa_te, 0.28, places=6)


if __name__ == "__main__":
    unittest.main()
