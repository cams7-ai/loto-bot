from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

import grimp

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
PROJECT_PACKAGES = ("api", "application", "domain", "infrastructure")


def test_domain_is_independent_from_outer_layers() -> None:
    assert_no_import_chain(
        importer="domain",
        forbidden_imports=("application", "api", "infrastructure"),
    )


def test_application_does_not_depend_on_api_or_infrastructure() -> None:
    assert_no_import_chain(
        importer="application",
        forbidden_imports=("api", "infrastructure"),
    )


def test_infrastructure_does_not_depend_on_api() -> None:
    assert_no_import_chain(
        importer="infrastructure",
        forbidden_imports=("api",),
    )


def test_forbidden_framework_imports_by_layer() -> None:
    rules = {
        "domain": {"beanie", "fastapi", "httpx", "motor", "playwright", "pydantic", "pydantic_settings", "pymongo"},
        "application": {"beanie", "fastapi", "httpx", "motor", "playwright", "pydantic_settings", "pymongo"},
        "infrastructure": {"fastapi"},
        "api": {"beanie", "httpx", "motor", "playwright", "pymongo"},
    }
    violations = [
        f"{source_file.relative_to(PROJECT_ROOT)} imports {imported_module}"
        for layer, forbidden_modules in rules.items()
        for source_file in _python_files_by_layer(layer)
        for imported_module in _imports_from(source_file)
        if imported_module.split(".", maxsplit=1)[0] in forbidden_modules
    ]

    assert violations == []


def assert_no_import_chain(importer: str, forbidden_imports: tuple[str, ...]) -> None:
    graph = import_graph()
    violations = [
        f"{importer} imports {forbidden_import}"
        for forbidden_import in forbidden_imports
        if graph.chain_exists(importer=importer, imported=forbidden_import)
    ]

    assert violations == []


@lru_cache(maxsize=1)
def import_graph() -> grimp.ImportGraph:
    return grimp.build_graph(*PROJECT_PACKAGES)


def _python_files_by_layer(layer: str) -> list[Path]:
    return [source_file for source_file in (SRC_ROOT / layer).rglob("*.py") if "__pycache__" not in source_file.parts]


def _imports_from(source_file: Path) -> set[str]:
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    return imports
