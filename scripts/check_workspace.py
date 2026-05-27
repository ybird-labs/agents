"""Workspace scaffold sanity checks.

This intentionally stays lightweight: it verifies the expected uv workspace
members and import-package directories exist without importing application code.
It avoids third-party dependencies so it can run before the workspace is synced.
"""

from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MEMBERS = [
    "apps/api",
    "apps/workers/ingestion",
    "apps/workers/workflow",
    "apps/workers/agent",
    "apps/mcp-server",
    "apps/agents/board_minutes",
    "packages/exeboard-domain",
    "packages/exeboard-application",
    "packages/exeboard-platform",
    "packages/exeboard-temporal",
    "packages/exeboard-ai",
    "packages/exeboard-tools",
    "packages/exeboard-integrations",
    "packages/exeboard-evals",
]


def read_workspace_members(pyproject_text: str) -> list[str]:
    """Extract workspace members from the simple root pyproject scaffold."""
    match = re.search(r"members\s*=\s*\[(.*?)\]", pyproject_text, flags=re.S)
    if not match:
        return []
    return re.findall(r'"([^"]+)"', match.group(1))


def package_dir_for(member: str) -> Path:
    """Return the expected src package directory for a workspace member."""
    if member.startswith("packages/exeboard-"):
        name = member.split("/")[-1].replace("-", "_")
    elif member == "apps/mcp-server":
        name = "exeboard_mcp_server"
    elif member == "apps/agents/board_minutes":
        name = "exeboard_agent_board_minutes"
    elif member.startswith("apps/workers/"):
        name = f"exeboard_worker_{member.split('/')[-1]}"
    elif member == "apps/api":
        name = "exeboard_api"
    else:
        name = member.split("/")[-1].replace("-", "_")
    return ROOT / member / "src" / name


def main() -> None:
    root_pyproject = ROOT / "pyproject.toml"
    if not root_pyproject.is_file():
        raise SystemExit("pyproject.toml not found")

    members = read_workspace_members(root_pyproject.read_text())
    missing = sorted(set(EXPECTED_MEMBERS) - set(members))
    extra = sorted(set(members) - set(EXPECTED_MEMBERS))
    if missing or extra:
        raise SystemExit(f"workspace members mismatch; missing={missing}, extra={extra}")

    errors: list[str] = []
    for member in EXPECTED_MEMBERS:
        member_path = ROOT / member
        pyproject = member_path / "pyproject.toml"
        pkg_dir = package_dir_for(member)
        init_file = pkg_dir / "__init__.py"
        if not pyproject.is_file():
            errors.append(f"missing {pyproject.relative_to(ROOT)}")
        if not init_file.is_file():
            errors.append(f"missing {init_file.relative_to(ROOT)}")

    if (ROOT / "apps/web" / "pyproject.toml").exists():
        errors.append("apps/web should remain outside the Python uv workspace")

    if errors:
        raise SystemExit("\n".join(errors))

    print("workspace scaffold valid")


if __name__ == "__main__":
    main()
