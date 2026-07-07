import ast
import importlib
import os
from pathlib import Path


FORBIDDEN_IMPORT_ROOTS = {
    "application",
    "celery",
    "cloudinary",
    "django",
    "django_app",
    "infrastructure",
    "rest_framework",
    "sqlalchemy",
    "tasks",
}


def test_vendor_domain_has_no_framework_or_infrastructure_imports():
    domain_root = Path(__file__).parents[3] / "domain" / "vendors"
    offenders: list[str] = []

    for path in sorted(domain_root.rglob("*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                imported_names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported_names = [node.module or ""]
            else:
                continue
            for imported_name in imported_names:
                root = imported_name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORT_ROOTS:
                    offenders.append(f"{path.relative_to(domain_root)} imports {imported_name}")

    assert offenders == []


def test_vendor_domain_modules_import_and_public_exports_exist():
    package = importlib.import_module("domain.vendors")

    for module_name in [
        "domain.vendors.entities",
        "domain.vendors.events",
        "domain.vendors.interfaces",
        "domain.vendors.package_rules",
        "domain.vendors.package_edit_policy",
        "domain.vendors.validation",
    ]:
        importlib.import_module(module_name)

    missing_exports = [name for name in package.__all__ if not hasattr(package, name)]
    assert missing_exports == []


def test_django_setup_smoke_for_admin_autodiscovery():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_app.settings.test")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["FASTAPI_DATABASE_URL"] = "postgresql+asyncpg://user:pass@localhost/linkapro_test"

    django = importlib.import_module("django")
    django.setup()
