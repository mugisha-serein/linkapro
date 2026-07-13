import ast
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


def test_vendor_domain_has_no_legacy_profile_completion_module():
    domain_root = Path(__file__).parents[3] / "domain" / "vendors"

    assert not (domain_root / "profile_completion.py").exists()
