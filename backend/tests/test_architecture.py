import re
import unittest
from pathlib import Path


class ArchitectureRulesTests(unittest.TestCase):
    def test_controllers_and_services_do_not_contain_raw_sql(self) -> None:
        app_root = Path(__file__).resolve().parents[1] / "app"
        forbidden = re.compile(r"\b(?:SELECT|INSERT|UPDATE|DELETE)\s+", re.IGNORECASE)
        violations: list[str] = []
        for folder in (app_root / "controllers", app_root / "services"):
            for path in folder.glob("*.py"):
                if forbidden.search(path.read_text(encoding="utf-8")):
                    violations.append(str(path.relative_to(app_root)))
        self.assertEqual(violations, [], f"发现散落的原生 SQL: {violations}")


if __name__ == "__main__":
    unittest.main()
