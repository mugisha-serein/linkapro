from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys


HANDLER_METHODS = (
    "queue_portfolio_media",
    "mark_portfolio_media_processing",
    "mark_portfolio_media_uploaded",
    "update_portfolio_caption",
    "update_vendor_branding_media",
)

LEGACY_SIDE_EFFECT_MODULES = (
    "portfolio_media_queue_handler.py",
    "portfolio_media_processing_handler.py",
    "portfolio_media_uploaded_handler.py",
    "portfolio_caption_update_handler.py",
    "vendor_branding_update_handler.py",
)


def test_vendor_command_handlers_exposes_all_extended_handlers_after_direct_import_only():
    script = """
import sys
from application.vendors.handlers import VendorCommandHandlers

expected = {
    'queue_portfolio_media',
    'mark_portfolio_media_processing',
    'mark_portfolio_media_uploaded',
    'update_portfolio_caption',
    'update_vendor_branding_media',
}
missing = sorted(name for name in expected if not callable(getattr(VendorCommandHandlers, name, None)))
legacy_imports = sorted(
    name
    for name in sys.modules
    if name in {
        'application.vendors.portfolio_media_queue_handler',
        'application.vendors.portfolio_media_processing_handler',
        'application.vendors.portfolio_media_uploaded_handler',
        'application.vendors.portfolio_caption_update_handler',
        'application.vendors.vendor_branding_update_handler',
    }
)
assert missing == [], missing
assert legacy_imports == [], legacy_imports
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr


def test_extended_handlers_are_normal_methods_declared_on_vendor_command_handlers():
    from application.vendors.handlers import VendorCommandHandlers

    for method_name in HANDLER_METHODS:
        method = VendorCommandHandlers.__dict__.get(method_name)
        assert callable(method), method_name
        assert method.__module__ == "application.vendors.handlers"
        assert method.__qualname__ == f"VendorCommandHandlers.{method_name}"


def test_application_vendor_modules_contain_no_vendor_command_handler_assignments():
    application_directory = Path(__file__).parents[3] / "application" / "vendors"
    assignments: list[tuple[str, int]] = []

    for module_path in application_directory.glob("*.py"):
        tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "VendorCommandHandlers"
                ):
                    assignments.append((module_path.name, node.lineno))

    assert assignments == []


def test_legacy_side_effect_handler_modules_are_deleted():
    application_directory = Path(__file__).parents[3] / "application" / "vendors"

    assert [
        module_name
        for module_name in LEGACY_SIDE_EFFECT_MODULES
        if (application_directory / module_name).exists()
    ] == []
