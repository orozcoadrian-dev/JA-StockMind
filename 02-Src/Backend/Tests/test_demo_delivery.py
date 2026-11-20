import unittest
from pathlib import Path

from Backend.Agent.tools import execute_tool
from Backend.Services.excel_reader import read_excel_file


DEMO_DIR = Path(__file__).resolve().parents[2] / "demo"


class DemoDeliveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = sorted(DEMO_DIR.glob("*_demo.xlsx"))

    def test_four_demo_files_have_realistic_size_and_different_headers(self):
        self.assertEqual(len(self.files), 4)
        headers = []
        for path in self.files:
            result = read_excel_file(path)
            self.assertGreaterEqual(result["row_count"], 80)
            self.assertLessEqual(result["row_count"], 150)
            headers.append(tuple(result["field_mapping"].values()))
        self.assertEqual(len(set(headers)), 4)
        self.assertGreater(len({read_excel_file(path)["header_row"] for path in self.files}), 1)

    def test_demo_contains_red_blue_and_different_measure_grips(self):
        all_names = [row["data"]["raw_name"].lower() for path in self.files for row in read_excel_file(path)["rows"]]

        self.assertTrue(any("grip rojo" in name or "grips roj" in name for name in all_names))
        self.assertTrue(any("grip azul" in name for name in all_names))
        self.assertTrue(any("28mm" in name for name in all_names))

    def test_natural_rule_is_structured_before_confirmation(self):
        result = execute_tool("create_equivalence_rule", {"natural_text": "si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo"})

        condition = result["data"]["structured_condition"]
        self.assertTrue(result["confirmation_required"])
        self.assertEqual(condition["action"], "merge_to_canonical")
        self.assertEqual(condition["suppliers"], ["Inversiones Guerrero", "Malusa"])
        self.assertEqual(condition["match"]["attributes"]["color"], "rojo")


if __name__ == "__main__":
    unittest.main()