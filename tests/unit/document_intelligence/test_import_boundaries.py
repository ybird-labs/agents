from __future__ import annotations

import ast
from pathlib import Path

DENIED_IMPORT_ROOTS = {
    "anthropic",
    "exeboard_integrations",
    "litellm",
    "openai",
    "pydantic_ai",
}
DENIED_IMPORT_MODULES = {
    "google.genai",
    "google.generativeai",
}

PACKAGE_ROOT = Path("packages/exeboard-ai/src/exeboard_ai")
PYPROJECT_PATH = Path("packages/exeboard-ai/pyproject.toml")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_exeboard_ai_does_not_import_provider_sdks_or_integrations() -> None:
    violations: list[str] = []
    for path in PACKAGE_ROOT.rglob("*.py"):
        for module in _imported_modules(path):
            root = module.split(".", maxsplit=1)[0]
            if root in DENIED_IMPORT_ROOTS or module in DENIED_IMPORT_MODULES:
                violations.append(f"{path}: {module}")

    assert violations == []


def test_exeboard_ai_pyproject_has_no_llm_provider_or_pydanticai_dependencies() -> None:
    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")

    for denied in sorted(DENIED_IMPORT_ROOTS - {"exeboard_integrations"}):
        assert denied not in pyproject
    assert "google-genai" not in pyproject
    assert "google-generativeai" not in pyproject
