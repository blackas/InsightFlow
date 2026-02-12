"""Smoke tests to verify basic infrastructure."""

import importlib
import pkgutil
from pathlib import Path


def test_import_all_modules() -> None:
    """Verify all src modules can be imported without errors."""
    src_path = Path(__file__).parent.parent / "src"

    modules = []
    for _, modname, _ in pkgutil.iter_modules([str(src_path)]):
        if not modname.startswith("_"):
            modules.append(f"src.{modname}")

    failed = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            failed.append((mod, str(e)))

    assert not failed, f"Failed imports: {failed}"
    assert len(modules) >= 8, f"Expected >=8 modules, found {len(modules)}"
