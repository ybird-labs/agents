# File Structure and Boundaries

Exeboard uses a Python-first `uv` workspace monorepo. The root `pyproject.toml` is the workspace manifest; each deployable Python app and reusable Python package has its own `pyproject.toml`, `src/` package, and placeholder entrypoint or library module.

## Top-level layout

```text
apps/                  Deployable processes and app-specific composition
packages/              Reusable Python packages with explicit boundaries
tests/                 Architecture, integration, e2e, and fixture tests
evals/                 Evaluation assets, prompts, reports, and traces
infra/                 Docker, Kubernetes, and Terraform assets
db/alembic/            Database migration assets
scripts/               Developer and repository utility scripts
docs/                  Architecture and repository documentation
research/              Structured research briefs generated during planning
spec/                  Product and agent specifications
*.md research files    Root-level research and recommendation briefs preserved from planning
```

Existing research and specification documents are preserved as source material; do not move or rewrite them as part of scaffold work. This includes `project_research.md`, `research-*.md`, `review-recommendation.md`, `research/*.md`, `spec/*.md`, and `docs/architecture.md`.

## uv workspace

The workspace members are the Python deployable apps and reusable packages listed in the root `pyproject.toml`. Keep dependency declarations local to the workspace member that needs them. Apps should depend on packages rather than importing from another app.

Python apps are packaged workspace members, not anonymous script folders. Each app should expose a `[project.scripts]` entrypoint so it can be imported, tested, and built into a deployable image with predictable dependencies.

`apps/web` is intentionally a placeholder and is not currently a Python workspace member.

## Deployment apps

- `apps/api`: HTTP/API process and request-time composition.
- `apps/workers/ingestion`: ingestion worker entrypoint and deployment wiring.
- `apps/workers/workflow`: workflow orchestration worker entrypoint and deployment wiring.
- `apps/workers/agent`: agent execution worker entrypoint and deployment wiring.
- `apps/mcp-server`: MCP server process exposing approved tools and resources.
- `apps/agents/board_minutes`: deployable board-minutes agent composition.
- `apps/web`: future web client placeholder.

Apps should contain minimal runtime entrypoints, configuration loading, dependency injection, and process-specific adapters. Shared business rules, workflows, tools, prompts, and integrations belong under `packages/`.

## Package responsibilities

- `packages/exeboard-domain`: pure domain models, entities, value objects, domain events, and business invariants. No infrastructure, network, database, Temporal, or model-provider imports.
- `packages/exeboard-application`: use cases, service interfaces, ports, commands, queries, and application-level policies. Depends inward on domain; defines interfaces implemented elsewhere.
- `packages/exeboard-platform`: runtime adapters such as persistence, configuration, logging, observability, auth, and process glue. Implements application ports.
- `packages/exeboard-temporal`: Temporal workflow and activity definitions plus worker registration helpers.
- `packages/exeboard-ai`: agent orchestration, graph definitions, LLM-facing abstractions, prompt loading, and AI runtime composition.
- `packages/exeboard-tools`: tool contracts and tool implementations shared by agents, workflows, and MCP.
- `packages/exeboard-integrations`: external API clients and integration adapters.
- `packages/exeboard-evals`: executable evaluation harnesses, metrics, and regression helpers. Static eval assets live in top-level `evals/`.

## Temporal determinism rules

Temporal workflow code must remain deterministic:

- Do not perform network, database, filesystem, random, wall-clock, or model-provider calls directly inside workflows.
- Put side effects in activities and call those activities from workflows.
- Keep workflow inputs and outputs serializable and version-tolerant.
- Use Temporal-provided time, sleep, retry, and versioning primitives instead of Python runtime equivalents inside workflows.
- Keep provider SDK clients and credentials out of workflow definitions.

## LangGraph layout

LangGraph or graph-style agent code belongs in `packages/exeboard-ai`. Keep graph state schemas, node definitions, routers, and graph assembly separate from app entrypoints. App-specific graphs can be composed in `apps/agents/<agent_name>` only when the composition is deployable-specific; reusable nodes and policies should move back into `packages/exeboard-ai` or `packages/exeboard-tools`.

## MCP layout

`apps/mcp-server` is the deployable MCP process. MCP tool/resource registration should adapt reusable tool contracts from `packages/exeboard-tools` and application use cases from `packages/exeboard-application`. Avoid placing business logic directly in MCP handlers.

## Evals

Top-level `evals/` stores non-package evaluation assets:

- `evals/datasets`: input datasets and fixtures for repeatable evaluations.
- `evals/prompts`: prompt variants and prompt regression inputs.
- `evals/reports`: generated or reviewed evaluation reports.
- `evals/golden_traces`: known-good agent/workflow traces for regression checks.

Executable eval code belongs in `packages/exeboard-evals` so it can import internal packages through normal workspace dependencies.

## Import-boundary rules

Use inward-facing dependencies and avoid cycles:

1. `exeboard-domain` imports only the Python standard library and explicitly approved pure-domain dependencies.
2. `exeboard-application` may import `exeboard-domain` and define ports, but should not import infrastructure implementations.
3. `exeboard-platform`, `exeboard-integrations`, `exeboard-tools`, `exeboard-ai`, and `exeboard-temporal` may implement application ports as needed, but should not create cycles between packages.
4. Apps may import packages, but packages must not import from `apps/`.
5. Tests may import any workspace member appropriate to the test layer.
6. Evals may import runtime packages through `packages/exeboard-evals`; static assets in top-level `evals/` should not become application modules.
