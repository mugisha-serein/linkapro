"""Architecture tests for identity application-layer boundaries."""

from __future__ import annotations

import ast
from pathlib import Path


APPLICATION_IDENTITY_ROOT = Path(__file__).resolve().parents[2] / "application" / "identity"
INFRASTRUCTURE_IDENTITY_ROOT = Path(__file__).resolve().parents[2] / "infrastructure" / "identity"
APPLICATION_FORBIDDEN_IMPORT_ROOTS = {
    "django",
    "infrastructure",
    "pyotp",
    "qrcode",
    "rest_framework",
    "rest_framework_simplejwt",
}
INFRASTRUCTURE_FORBIDDEN_IMPORT_ROOTS = {
    "django_app",
    "interface",
}


def _import_root(module_name: str) -> str:
    return module_name.split(".", 1)[0]


def _forbidden_imports(path: Path, forbidden_roots: set[str]) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _import_root(alias.name) in forbidden_roots:
                    violations.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if _import_root(node.module) in forbidden_roots:
                violations.append(node.module)
    return violations


def test_application_identity_does_not_import_framework_or_infrastructure_modules():
    violations: list[str] = []
    for path in sorted(APPLICATION_IDENTITY_ROOT.rglob("*.py")):
        relative_path = path.relative_to(APPLICATION_IDENTITY_ROOT.parents[1])
        for module_name in _forbidden_imports(path, APPLICATION_FORBIDDEN_IMPORT_ROOTS):
            violations.append(f"{relative_path}: imports {module_name}")

    assert violations == []


def test_infrastructure_identity_does_not_import_interface_package_modules():
    violations: list[str] = []
    for path in sorted(INFRASTRUCTURE_IDENTITY_ROOT.rglob("*.py")):
        relative_path = path.relative_to(INFRASTRUCTURE_IDENTITY_ROOT.parents[1])
        for module_name in _forbidden_imports(path, INFRASTRUCTURE_FORBIDDEN_IMPORT_ROOTS):
            violations.append(f"{relative_path}: imports {module_name}")

    assert violations == []
