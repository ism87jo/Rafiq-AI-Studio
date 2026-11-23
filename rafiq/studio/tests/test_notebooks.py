import json
import unittest
from pathlib import Path


class NotebookChecks(unittest.TestCase):
    def test_notebook_code_compiles_without_saved_outputs(self):
        for path in (Path(__file__).resolve().parents[2] / "notebooks").glob("*.ipynb"):
            with self.subTest(notebook=path.name):
                notebook = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(notebook["nbformat"], 4)
                for cell in notebook["cells"]:
                    if cell["cell_type"] == "code":
                        self.assertFalse(cell["outputs"])
                        compile("".join(cell["source"]), str(path), "exec")
