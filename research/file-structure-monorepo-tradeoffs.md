# Research: monorepo vs single-package structure for AI workflow platforms

## Summary
Use a **monorepo**, but not a single Python package. For an AI workflow platform with an API, web app, Temporal workers, MCP server, LangGraph agents, shared domain/core code, integrations, infra, tests, and evals, the strongest default is a **uv workspace with separate Python packages for each deployable and shared library**, plus a separate JS workspace for the web app if needed. A single Python package is acceptable only for an early prototype or one tightly-coupled deployable; it will quickly over-install dependencies, blur ownership, and make worker/API/agent/MCP deployments harder to package independently.

## Recommended structure

```text
repo/
├── pyproject.toml              # uv workspace root; no importable app code
├── uv.lock                     # shared Python lockfile
├── README.md
├── apps/
│   ├── api/
│   │   ├── pyproject.toml
│   │   └── src/exeboard_api/
│   │       ├── main.py         # FastAPI app factory / app object
│   │       ├── dependencies.py
│   │       ├── api/routers/    # APIRouter modules by bounded context
│   │       └── lifespan.py
│   ├── worker/
│   │   ├── pyproject.toml
│   │   └── src/exeboard_worker/
│   │       ├── main.py         # Temporal Worker entrypoint
│   │       ├── workflows/
│   │       └── activities/
│   ├── mcp-server/
│   │   ├── pyproject.toml
│   │   └── src/exeboard_mcp/
│   │       ├── server.py       # FastMCP instance and transport entrypoint
│   │       ├── tools/
│   │       └── resources/
│   ├── agents/
│   │   └── support-agent/
│   │       ├── pyproject.toml
│   │       ├── langgraph.json  # kept in the agent directory
│   │       └── src/exeboard_support_agent/
│   │           ├── agent.py
│   │           ├── nodes.py
│   │           ├── state.py
│   │           └── tools.py
│   └── web/                    # package.json / pnpm workspace / Next, etc.
├── packages/
│   ├── core/
│   │   ├── pyproject.toml
│   │   └── src/exeboard_core/
│   ├── domain/
│   │   ├── pyproject.toml
│   │   └── src/exeboard_domain/
│   ├── integrations/
│   │   ├── slack/...
│   │   ├── github/...
│   │   └── openai/...
│   └── evals/
│       ├── pyproject.toml
│       └── src/exeboard_evals/
├── tests/
│   ├── integration/
│   └── e2e/
├── evals/                      # datasets, prompts, reports; code lives in package
├── infra/
│   ├── docker/
│   ├── k8s/
│   └── terraform/
└── scripts/
```

Root `pyproject.toml` sketch:

```toml
[project]
name = "exeboard-workspace"
version = "0.0.0"
requires-python = ">=3.12"

[tool.uv]
package = false

[tool.uv.workspace]
members = ["apps/api", "apps/worker", "apps/mcp-server", "apps/agents/*", "packages/*", "packages/integrations/*"]

[tool.uv.sources]
exeboard-core = { workspace = true }
exeboard-domain = { workspace = true }
exeboard-integrations-slack = { workspace = true }

[dependency-groups]
dev = ["pytest", "ruff", "mypy"]
eval = ["pytest", "deepeval"]
```

Each deployable should explicitly depend on the shared packages it imports, for example `apps/api/pyproject.toml`:

```toml
[project]
name = "exeboard-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["fastapi", "uvicorn", "exeboard-core", "exeboard-domain"]

[build-system]
requires = ["uv_build>=0.11,<0.12"]
build-backend = "uv_build"

[project.scripts]
exeboard-api = "exeboard_api.main:main"
```

## Findings

1. **Prefer uv workspaces when there are multiple related Python packages in one repo** — uv describes a workspace as multiple packages “managed together,” with each package having its own `pyproject.toml` and a shared `uv.lock`; it explicitly gives a FastAPI app plus libraries as a typical case. Workspace members can be applications or libraries, and `uv run --package ...` / `uv sync --package ...` lets commands target a member. [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/)

2. **Do not use uv workspaces as dependency isolation** — uv workspaces share one lockfile and one environment model; uv says they are not suited when members have conflicting requirements or need separate virtual environments, and it cannot prevent one workspace package from importing another member’s undeclared dependency. If GPU evals, workers, and API dependencies diverge sharply, split those into separate uv projects/locks or adopt a build tool with multiple resolves. [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/)

3. **Use `src/` layout for every importable Python package** — PyPA’s packaging guide says `src` layout prevents accidental imports from the in-development tree and ensures editable installs only expose files intended to be importable. This matters in a monorepo where root scripts, tests, and multiple packages otherwise make import path mistakes easy. [PyPA src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)

4. **Package deployables separately, not as one giant package** — uv’s project configuration docs say a project should be a package when it needs commands, distribution, a `src`/test layout, or library behavior; each deployable here needs commands/containers and each shared module is a library. This supports separate Docker images and clearer runtime dependencies. [uv project packaging](https://docs.astral.sh/uv/concepts/projects/config/)

5. **FastAPI should be an adapter package with routers, not the whole platform** — FastAPI’s large-app docs recommend splitting route groups into modules with `APIRouter`, dependencies in separate modules, and `main.py` tying routers together. Keep business logic in shared domain/core packages; keep `apps/api` focused on HTTP concerns. [FastAPI bigger applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

6. **Temporal workers deserve their own deployable package and image** — Temporal workers must register the exact Workflow and Activity types they execute and bind to a task queue; all workers polling the same task queue must register the same types. Temporal’s EKS guide treats the worker as separately containerized code configured by environment variables such as address, namespace, and task queue. Put worker entrypoints in `apps/worker`, and use separate entrypoints/images per materially different task queue. [Temporal worker process](https://docs.temporal.io/develop/python/workers/run-worker-process), [Temporal EKS worker deployment](https://docs.temporal.io/production-deployment/worker-deployments/deploy-workers-to-aws-eks)

7. **LangGraph agents fit naturally as per-agent deployable packages inside the monorepo** — LangGraph apps consist of graph code, dependencies, env, and `langgraph.json`. LangSmith’s monorepo support specifically recommends keeping `langgraph.json` in each agent directory, using relative paths for Python shared packages, and supporting multiple agents in one monorepo without deploying all agents together. [LangGraph application structure](https://docs.langchain.com/oss/python/langgraph/application-structure), [LangSmith monorepo support](https://docs.langchain.com/langsmith/monorepo-support)

8. **MCP servers should be separate deployables, even if they reuse core packages** — The MCP Python SDK treats a FastMCP server as the protocol boundary with tools/resources/prompts and gives direct execution plus streamable HTTP deployment patterns. It recommends streamable HTTP for production scalability, and Google’s Cloud Run tutorial describes a remote MCP server as an independent process handling multiple client connections. [MCP Python SDK server docs](https://modelcontextprotocol.github.io/python-sdk/server/), [Google Cloud Run MCP tutorial](https://cloud.google.com/run/docs/tutorials/deploy-remote-mcp-server)

9. **For the web app, use native JS package workspaces rather than forcing it into Python structure** — Nx’s dependency strategy docs distinguish per-project dependencies from a single-version policy; the same governance choice applies to a polyglot monorepo. Keep `apps/web` as a normal Node package/workspace with its own tooling, while sharing API contracts through generated clients or schema packages rather than importing Python code. [Nx dependency management strategies](https://nx.dev/docs/concepts/decisions/dependency-management)

10. **Single-version policy is useful but creates coordination cost** — A shared uv lock gives consistent Python dependency versions and atomic changes across API/worker/agents, but it also means dependency upgrades require coordination. Nx documents this general monorepo tradeoff: single-version policy reduces runtime conflicts and simplifies sharing, but slows teams that need independent upgrade velocity. [Nx dependency management strategies](https://nx.dev/docs/concepts/decisions/dependency-management)

11. **If the repo grows beyond uv’s model, consider Pants/Bazel-style build graph tooling** — Pants supports multiple Python resolves/lockfiles for genuinely conflicting dependency sets and packages artifacts containing only true transitive dependencies. Bazel best practices emphasize fine-grained dependencies for parallelism, incrementality, encapsulation, and testability. For a small-to-medium AI platform, uv workspaces are simpler; for many deployables, conflicting stacks, or heavy CI caching needs, Pants/Bazel may pay off. [Pants lockfiles](https://www.pantsbuild.org/stable/docs/python/overview/lockfiles), [Pants package goal](https://www.pantsbuild.org/dev/docs/python/goals/package), [Bazel best practices](https://preview.bazel.build/configure/best-practices)

## Concrete recommendations

1. **Choose monorepo + uv workspace now.** Use one repo for product, API, workers, MCP, agents, shared libraries, infra, and evals so cross-cutting workflow changes are atomic.

2. **Make each deployable its own package under `apps/`.** `apps/api`, `apps/worker`, `apps/mcp-server`, and each important LangGraph agent should have its own `pyproject.toml`, `src/` package, entrypoint, tests, and Docker target.

3. **Put reusable logic under `packages/`, never under an app.** Suggested split:
   - `exeboard-domain`: entities, value objects, policy interfaces, workflow state types.
   - `exeboard-core`: orchestration services/use cases that are framework-agnostic.
   - `exeboard-integrations-*`: external APIs/tools split by provider when dependencies are heavy.
   - `exeboard-evals`: eval runners and metrics code; datasets/reports can live in top-level `evals/`.

4. **Keep dependency direction one-way.** `apps/* -> packages/*`; `packages/core -> packages/domain`; provider integrations depend on core/domain only when necessary. Shared packages must not import from `apps/*`.

5. **Use explicit workspace dependencies.** Every package that imports `exeboard-core` should list it in `project.dependencies` and map it with `{ workspace = true }`. Do not rely on the shared environment making undeclared imports work.

6. **Use Docker builds per deployable.** Production images should run targeted, non-editable syncs such as `uv sync --package exeboard-api --no-dev --no-editable` or equivalent, then launch that package’s script/module. Do not ship the whole repo runtime unless intentionally needed.

7. **Separate workers by task queue semantics.** If worker groups register different Temporal workflows/activities, create separate entrypoints and potentially separate packages/images (`worker-ingest`, `worker-agent`, `worker-evals`) to avoid task-queue registration mismatches.

8. **Keep LangGraph config beside each agent.** Put `langgraph.json` in `apps/agents/<agent>/`, not at repo root, and reference shared packages via relative dependencies/workspace packages so agents can deploy independently.

9. **Treat MCP as an API boundary, not a helper module.** `apps/mcp-server` should own protocol tools/resources/prompts and lifecycle wiring; it can call shared core services. Prefer streamable HTTP for remote/production deployments and stdio only for local/editor integration.

10. **Do not over-split too early.** Start with 3-5 shared packages. Split integrations/evals later when dependency weight, ownership, release cadence, or import boundaries justify it.

## Tradeoffs

| Option | Pros | Cons | Best fit |
|---|---|---|---|
| Single Python package | Simple imports, one pyproject, fastest initial setup | Every deployable installs all deps; unclear boundaries; API/worker/MCP/LangGraph configs mixed; larger images; hidden coupling; hard to test package boundaries | Short prototype, one deployable, throwaway proof-of-concept |
| Monorepo with uv workspaces | Atomic cross-app changes; shared lock; per-package metadata; editable local shared libs; targeted commands with `--package`; good fit for API + workers + agents + MCP | One dependency resolution; conflicts hurt; one venv can mask undeclared deps; more pyproject files; web still needs JS tooling | Recommended default for this platform |
| Multiple independent repos | Strong isolation; independent releases/locks; less lockfile coordination | Harder atomic changes; versioning shared libs becomes overhead; duplicated CI/infra; slower refactors | Mature org with separately owned services and stable package publishing |
| Monorepo with Pants/Bazel | Fine-grained dependency graph, caching, packaging only true deps, multiple resolves/lockfiles | More tooling complexity and BUILD metadata | Large repo, many teams/deployables, conflicting Python stacks, advanced CI needs |

## Sources

- Kept: uv “Using workspaces” (https://docs.astral.sh/uv/concepts/projects/workspaces/) — primary source for uv workspace model, shared lockfile, package targeting, and limitations.
- Kept: uv “Configuring projects” (https://docs.astral.sh/uv/concepts/projects/config/) — primary source for packaging, build systems, project scripts, and deployment `--no-editable` behavior.
- Kept: uv “Managing dependencies” (https://docs.astral.sh/uv/concepts/projects/dependencies/) — primary source for workspace sources, path deps, dependency groups, editable deps, and `tool.uv.sources` caveats.
- Kept: PyPA “src layout vs flat layout” (https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) — authoritative Python packaging guidance for `src/` layout.
- Kept: FastAPI “Bigger Applications” (https://fastapi.tiangolo.com/tutorial/bigger-applications/) — official large FastAPI app structure and `APIRouter` guidance.
- Kept: Temporal Python worker process docs (https://docs.temporal.io/develop/python/workers/run-worker-process) — official worker/task queue registration constraints.
- Kept: Temporal EKS worker deployment (https://docs.temporal.io/production-deployment/worker-deployments/deploy-workers-to-aws-eks) — official separate worker containerization pattern.
- Kept: LangGraph application structure (https://docs.langchain.com/oss/python/langgraph/application-structure) — official `langgraph.json`, graph, dependency, env structure.
- Kept: LangSmith monorepo support (https://docs.langchain.com/langsmith/monorepo-support) — official monorepo guidance for shared packages and per-agent configs.
- Kept: MCP Python SDK server docs (https://modelcontextprotocol.github.io/python-sdk/server/) — official FastMCP server, run modes, and streamable HTTP guidance.
- Kept: Google Cloud Run remote MCP tutorial (https://cloud.google.com/run/docs/tutorials/deploy-remote-mcp-server) — concrete deployment example for MCP as independent process.
- Kept: Nx dependency management strategies (https://nx.dev/docs/concepts/decisions/dependency-management) — useful general monorepo dependency tradeoffs, especially web/JS side.
- Kept: Pants lockfiles (https://www.pantsbuild.org/stable/docs/python/overview/lockfiles) and package goal (https://www.pantsbuild.org/dev/docs/python/goals/package) — evidence for multiple resolves and precise deployable artifacts if uv is insufficient.
- Kept: Bazel best practices (https://preview.bazel.build/configure/best-practices) — general build-graph principles for large monorepos.
- Dropped: pydevtools uv monorepo article — useful tutorial but secondary to official uv docs.
- Dropped: FastAPI GitHub issue #386 and community best-practices repos — redundant/commentary compared with official FastAPI docs.
- Dropped: random MCP templates — not authoritative enough compared with MCP SDK and Google Cloud docs.
- Dropped: uv GitHub issues about workspace limitations — useful color, but official uv docs already state the relevant limitations.

## Gaps

- No platform-specific benchmark was found comparing uv workspace vs single-package Docker image size/build time for AI workloads; recommended next step is a small internal benchmark with API, worker, and eval images.
- Exact web tooling choice was out of scope; if the web app is substantial, evaluate pnpm/Nx/Turborepo separately.
- If evals require incompatible GPU/ML dependency stacks, validate whether uv workspace resolution remains practical; otherwise split evals into a separate uv project/lock or introduce Pants resolves.

## Supervisor coordination

No supervisor decision was needed; research completed without blockers.
