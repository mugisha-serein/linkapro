"""Architecture tests for identity application-layer boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


APPLICATION_IDENTITY_ROOT = Path(__file__).resolve().parents[2] / "application" / "identity"
FORBIDDEN_IMPORT_ROOTS = {
    "django",
    "infrastructure",
    "pyotp",
    "qrcode",
    "rest_framework",
    "rest_framework_simplejwt",
}


def _import_root(module_name: str) -> str:
    return module_name.split(".", 1)[0]


def _forbidden_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _import_root(alias.name) in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if _import_root(node.module) in FORBIDDEN_IMPORT_ROOTS:
                violations.append(node.module)
    return violations


def test_application_identity_does_not_import_framework_or_infrastructure_modules():
    violations: list[str] = []
    for path in sorted(APPLICATION_IDENTITY_ROOT.rglob("*.py")):
        relative_path = path.relative_to(APPLICATION_IDENTITY_ROOT.parents[1])
        for module_name in _forbidden_imports(path):
            violations.append(f"{relative_path}: imports {module_name}")

    assert violations == []
