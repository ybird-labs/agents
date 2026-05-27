# Research: file/repo structure industry practices for a Python-first multi-agent workflow platform

## Summary
A Python-first multi-agent workflow platform should use a monorepo with clear deployable applications (`apps/`) and independently importable shared packages (`packages/`) using `src/` layout and per-package `pyproject.toml` files. Keep FastAPI, Temporal workers, LangGraph agents, MCP servers, and ingestion/evaluation jobs as separate deployable apps, while centralizing cross-cutting concerns (auth/tenancy, persistence, audit/provenance, observability, RAG primitives, schemas) in shared packages. This matches official guidance from Python Packaging, uv workspaces, FastAPI, Temporal, LangGraph, MCP, LlamaIndex, LangSmith, OpenTelemetry, and credible production templates/samples.

## Recommended structure

```text
repo/
├── pyproject.toml                 # workspace/tooling config: ruff, mypy/pyright, pytest, uv workspace
├── uv.lock                        # single deterministic lock for workspace if dependency constraints align
├── README.md
├── .env.example
├── .github/workflows/             # CI: lint, typecheck, tests, evals, images, deployment gates
├── docs/                          # architecture, ADRs, runbooks, security model, data/provenance model
├── deploy/                        # docker-compose, k8s/helm, terraform, temporal/langgraph deployment manifests
├── dockerfiles/                   # app-specific Dockerfiles or shared base images
├── migrations/                    # optional root DB migration env if one shared DB
│   ├── alembic.ini
│   └── alembic/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
├── apps/                          # deployable/runtime entrypoints only
│   ├── api/                       # FastAPI app
│   │   ├── pyproject.toml
│   │   └── src/exeboard_api/
│   │       ├── main.py            # app factory/lifespan; include routers
│   │       ├── api/v1/
│   │       │   ├── router.py
│   │       │   └── routes/        # thin HTTP adapters; no business logic
│   │       ├── deps.py            # FastAPI dependencies: auth, DB sessions, tenant context
│   │       └── middleware.py
│   ├── temporal_worker/           # Temporal worker process image(s)
│   │   ├── pyproject.toml
│   │   └── src/exeboard_worker/
│   │       ├── main.py            # connect client, register workflows/activities, run worker
│   │       ├── task_queues.py     # constants shared with starters/clients
│   │       └── registry.py        # per-queue workflow/activity registration
│   ├── agents/                    # LangGraph deployable agent apps
│   │   ├── research_agent/
│   │   │   ├── pyproject.toml
│   │   │   ├── langgraph.json     # kept in agent directory, not monorepo root
│   │   │   └── src/research_agent/
│   │   │       ├── graph.py       # compile/export graph
│   │   │       ├── state.py
│   │   │       ├── nodes.py
│   │   │       ├── prompts.py
│   │   │       └── tools.py       # local graph tools or MCP clients
│   │   └── ...
│   ├── mcp_servers/               # standalone/mounted MCP tool servers
│   │   └── docs_tools/
│   │       ├── pyproject.toml
│   │       └── src/docs_tools_mcp/
│   │           ├── server.py      # FastMCP/low-level server
│   │           ├── tools.py
│   │           ├── resources.py
│   │           ├── prompts.py
│   │           └── auth.py
│   ├── ingestion/                 # document ETL/RAG ingestion app, often run by Temporal
│   │   ├── pyproject.toml
│   │   └── src/exeboard_ingestion/
│   │       ├── pipelines.py
│   │       ├── connectors/
│   │       ├── transformations/   # parse, chunk, normalize, metadata extraction
│   │       ├── embeddings/
│   │       └── stores/            # vector/doc/object stores
│   └── eval_runner/               # optional dedicated eval/backtest runner app
│       └── src/exeboard_evals_runner/
├── packages/                      # reusable libraries; no process entrypoints
│   ├── core/                      # domain models, commands/events, use cases, service interfaces
│   │   └── src/exeboard_core/
│   │       ├── domains/           # projects, agents, documents, runs, tenants, users
│   │       ├── schemas/           # public Pydantic DTOs/shared contracts
│   │       └── errors.py
│   ├── persistence/               # SQLAlchemy/SQLModel models, repositories, unit of work
│   ├── authz/                     # auth, RBAC/ABAC, tenant isolation policies
│   ├── temporal_shared/           # workflow/activity definitions, payload models, starters
│   │   └── src/exeboard_temporal/
│   │       ├── workflows/         # deterministic orchestration only
│   │       ├── activities/        # side effects: DB, HTTP, LLM, vector stores
│   │       └── payloads.py
│   ├── agent_runtime/             # shared LangGraph nodes, state, memory, tool adapters
│   ├── rag/                       # chunking, retrieval, citation/source models, vector abstractions
│   ├── audit/                     # append-only audit/provenance event models and writers
│   ├── observability/             # OpenTelemetry/LangSmith instrumentation helpers
│   └── settings/                  # pydantic-settings config, secrets/env loading
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── contract/                  # API/tool/schema compatibility tests
└── evals/
    ├── datasets/                  # curated examples, production backtest extracts (sanitized)
    ├── evaluators/                # LLM-as-judge + deterministic/code evaluators
    ├── offline/                   # regression/benchmark jobs
    └── reports/
```

Key conventions:
- Keep runtime apps thin: they wire dependencies, register routes/workers/graphs/tools, and call shared packages.
- Keep shared packages importable and testable without starting servers.
- Use domain/use-case packages for business logic; use `apps/api` routes only as HTTP adapters.
- Put all long-running and side-effectful orchestration behind Temporal activities/workflows or explicit service interfaces.
- Store provenance/audit as a first-class package and database model, not as ad hoc log lines.

## Findings

1. **Use a monorepo workspace with `apps/` + `packages/` when deployables share domain logic, schemas, and tooling.** uv workspaces are explicitly designed for “a FastAPI-based web application, alongside a series of libraries” in one repo, with each package having its own `pyproject.toml` and the workspace sharing one lockfile. Use this while dependencies can be resolved together; if packages need incompatible Python versions or dependency sets, use separate environments/path dependencies or split repos. [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/)

2. **Use `src/` layout for importable Python packages.** PyPA states that `src/` layout separates import packages from repository/tooling files and helps prevent accidentally importing the in-development copy instead of the installed package. That matters in a platform with many apps, generated files, tests, scripts, and deployment assets. [Python Packaging User Guide: src layout vs flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)

3. **FastAPI app code should be modular, but HTTP routing should remain an adapter layer.** Official FastAPI docs recommend splitting larger apps into packages with `APIRouter`, shared dependencies, and `include_router()` composition; the official full-stack template shows a production-ish backend with `app/api/routes`, `app/api/deps.py`, `app/core`, Alembic migrations, scripts, Docker, and tests. For a complex SaaS platform, prefer domain/use-case packages under `packages/` over putting business logic in route modules. [FastAPI bigger applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/), [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)

4. **Keep database migrations versioned with the app source and wired to the same Python environment as models.** Alembic describes a migration environment with `alembic.ini`/`pyproject.toml`, `env.py`, `script.py.mako`, and `versions/`, maintained with the application source; `env.py` is where model imports and DB connectivity are customized. Root-level migrations are simplest for one shared database; per-app/per-bounded-context migrations are cleaner if services own separate databases. [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)

5. **Temporal workers should be separate deployable services, not hidden inside the FastAPI process.** Temporal Python workers register exact workflow/activity types and associate each worker entity with exactly one task queue; workers polling the same queue must register the same types. Separate worker apps/images make scaling, versioning, and runtime tuning independent from the API. [Temporal Python worker process docs](https://docs.temporal.io/develop/python/workers/run-worker-process)

6. **Use logical task queues, worker versioning, and payload boundaries as structural boundaries.** Temporal production guidance recommends separating task queues by workload, deploying enough workers per queue, tuning worker options, using Worker Versioning for safe workflow changes, and avoiding large workflow payloads/event histories; large document or RAG payloads should use a claim-check pattern, passing IDs/URIs and loading data in activities. Reflect this in code with `task_queues.py`, payload models, deterministic `workflows/`, and side-effectful `activities/`. [Temporal worker deployment and performance](https://docs.temporal.io/best-practices/worker)

7. **Keep Temporal workflow modules deterministic and dependency-light.** The Python SDK sandbox reloads non-standard modules and restricts known non-deterministic calls; docs recommend passing through only deterministic/side-effect-free modules and keeping activities/models in separate files where appropriate. This supports a package split where `workflows/` are pure orchestration and `activities/` perform DB, HTTP, model, vector, and file operations. [Temporal Python sandbox](https://docs.temporal.io/develop/python/python-sdk-sandbox)

8. **LangGraph agents should be deployable graph apps with colocated `langgraph.json`.** LangGraph’s official application structure requires one or more graphs, a `langgraph.json`, dependencies, and env configuration. Its monorepo guidance specifically says to place `langgraph.json` in the agent directory, use relative paths to shared packages, and test locally before deploying. [LangGraph application structure](https://docs.langchain.com/oss/python/langgraph/application-structure), [LangGraph monorepo support](https://docs.langchain.com/langsmith/monorepo-support)

9. **Separate reusable agent runtime code from agent deployments.** A credible LangChain sample repo (`cicd-pipeline-example`) keeps `agents/`, `examples/`, `helpers/`, `langgraph.json`, `tests/unit`, `tests/integrations`, `tests/e2e`, and `tests/offline_evals`, plus CI workflows for evaluations and deployments. Mirror this pattern inside each substantial agent app while moving shared nodes/tools/state into `packages/agent_runtime`. [langchain-ai/cicd-pipeline-example](https://github.com/langchain-ai/cicd-pipeline-example)

10. **MCP servers should be structured around protocol primitives and deployed like independent tool services.** The official MCP Python SDK distinguishes resources (data/context, GET-like), tools (actions/side effects, POST-like), and prompts; production deployments should prefer Streamable HTTP with `stateless_http=True` and `json_response=True` for scalability, and can mount multiple MCP servers under an ASGI app. This argues for `apps/mcp_servers/<server>/src/<pkg>/{server.py,tools.py,resources.py,prompts.py,auth.py}`. [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md)

11. **RAG ingestion should be its own pipeline/app with explicit document IDs, hashes, caches, metadata, and vector/doc stores.** LlamaIndex’s `IngestionPipeline` applies transformations, can write to vector stores, caches node+transformation pairs, supports remote caches, async execution, parallel processing, and document management via `doc_id`/hash duplicate detection and upserts. That maps well to `apps/ingestion` for orchestration plus `packages/rag` for reusable chunking, metadata, citation, retrieval, and storage abstractions. [LlamaIndex ingestion pipeline](https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/)

12. **Production RAG structure should support multiple retrieval strategies, not only vector similarity.** LlamaIndex production RAG guidance recommends decoupling chunks used for retrieval vs synthesis, using metadata filters/auto-retrieval, summary-to-chunk hierarchies, and task-dependent retrieval. Therefore keep retrieval/query assembly as replaceable modules (`rag/retrievers`, `rag/rerankers`, `rag/context_assembly`, `rag/citations`) rather than burying it in agents or API routes. [LlamaIndex production RAG](https://developers.llamaindex.ai/python/framework/optimizing/production_rag/)

13. **Treat evaluations as a first-class repo area with CI gates and production feedback loops.** LangSmith distinguishes offline evaluations (benchmarking, unit tests, regression tests, backtesting, pairwise evaluation) from online production monitoring/anomaly detection. Keep `evals/datasets`, `evals/evaluators`, and `tests/offline_evals`, and wire CI to run cheap deterministic tests on every PR and more expensive regression/backtest suites on model/prompt/graph changes. [LangSmith evaluation types](https://docs.langchain.com/langsmith/evaluation-types)

14. **Use OpenTelemetry GenAI semantic conventions as the common observability/provenance vocabulary.** OpenTelemetry defines spans/attributes for `invoke_agent`, `invoke_workflow`, `execute_tool`, model/provider names, conversation IDs, data source IDs, system instructions, tool definitions, token usage, and error types. Implement this in `packages/observability` and persist business audit/provenance events in `packages/audit` so traces and compliance records share correlation IDs but can have different retention/redaction policies. [OpenTelemetry GenAI agent spans](https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/)

15. **Enterprise SaaS concerns should be packages, not scattered helpers.** Authentication/authorization, tenant isolation, billing/quotas, secrets/config, audit logging, data retention, and observability cross every app. Put policy code in packages such as `authz`, `tenancy`, `audit`, `settings`, and `observability`, then inject them through FastAPI dependencies, Temporal activities, LangGraph runtime context, and MCP lifespan/context. The FastAPI full-stack template’s separation of `api`, `core`, tests, Docker, GitHub Actions, secrets, and DB migration setup is a useful baseline, but a multi-agent SaaS platform should go further with bounded shared packages. [Full Stack FastAPI Template](https://github.com/fastapi/full-stack-fastapi-template)

## Architectural tradeoffs

1. **Monorepo vs polyrepo**
   - Recommended now: monorepo with uv workspace because shared schemas, audit/provenance models, agent runtime code, and Temporal payloads must evolve together.
   - Split later when teams need independent release trains, dependency versions conflict, or a service has a distinct compliance/security boundary.

2. **Domain-first vs layer-first folders**
   - Use layer boundaries at app edges (`api/routes`, `workflows`, `activities`, `mcp/tools`) because frameworks expect them.
   - Use domain/use-case packages for core business logic (`packages/core/domains/documents`, `runs`, `agents`, `tenants`) so behavior is not fragmented across routers, workers, and agents.

3. **One Temporal worker app vs many worker apps**
   - Start with one `apps/temporal_worker` that can register multiple task queues if operationally simple.
   - Split into multiple worker apps/images when workloads have different scaling, dependency, GPU/CPU, security, or deployment-version needs.

4. **LangGraph agents inside API vs separate graph apps**
   - For local dev, an API can call graph code directly.
   - For production, keep each important graph as a deployable app with its own `langgraph.json` and dependency list; this aligns with LangGraph Platform/LangSmith deployment and avoids coupling agent rollout to API rollout.

5. **MCP servers as in-process routers vs standalone services**
   - In-process/mounted MCP is convenient for internal tools with the same scaling/security profile.
   - Standalone MCP server apps are better for tool isolation, OAuth/resource-server boundaries, independent rate limits, and separate audit scopes.

6. **Root migrations vs per-service migrations**
   - Root `migrations/` is simpler if the platform uses one primary Postgres schema.
   - Per-app/per-domain Alembic environments are cleaner when services own separate databases or schemas; they cost more CI/deployment coordination.

## Sources

- Kept: FastAPI Bigger Applications (https://fastapi.tiangolo.com/tutorial/bigger-applications/) — official guidance on modular routers, dependencies, and app composition.
- Kept: FastAPI Full Stack Template (https://github.com/fastapi/full-stack-fastapi-template) — official production-oriented template showing backend, migrations, Docker, tests, and CI/CD.
- Kept: Python Packaging User Guide: src layout vs flat layout (https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) — official rationale for `src/` layout.
- Kept: uv Workspaces (https://docs.astral.sh/uv/concepts/projects/workspaces/) — official Python workspace/monorepo guidance with shared lockfile and per-package metadata.
- Kept: Alembic Tutorial (https://alembic.sqlalchemy.org/en/latest/tutorial.html) — official migration environment structure and `env.py` role.
- Kept: Temporal Python Worker Process (https://docs.temporal.io/develop/python/workers/run-worker-process) — official worker/task-queue registration constraints.
- Kept: Temporal Worker Deployment and Performance (https://docs.temporal.io/best-practices/worker) — official production guidance for task queues, worker versioning, tuning, metrics, and payload boundaries.
- Kept: Temporal Python Sandbox (https://docs.temporal.io/develop/python/python-sdk-sandbox) — official determinism/sandbox guidance.
- Kept: LangGraph Application Structure (https://docs.langchain.com/oss/python/langgraph/application-structure) — official graph app layout and `langgraph.json` requirements.
- Kept: LangGraph Monorepo Support (https://docs.langchain.com/langsmith/monorepo-support) — official guidance for agent directories and shared packages in monorepos.
- Kept: langchain-ai/cicd-pipeline-example (https://github.com/langchain-ai/cicd-pipeline-example) — credible LangChain sample with agent, tests, offline evals, Docker, and deployment workflow.
- Kept: MCP Python SDK (https://github.com/modelcontextprotocol/python-sdk/blob/main/README.md) — official MCP primitives, server structure, transports, auth, and mounting examples.
- Kept: LlamaIndex Ingestion Pipeline (https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/) — official ingestion pipeline, caching, docstore, vector store, async/parallel ingestion guidance.
- Kept: LlamaIndex Production RAG (https://developers.llamaindex.ai/python/framework/optimizing/production_rag/) — credible production RAG tradeoffs and retrieval strategies.
- Kept: LangSmith Evaluation Types (https://docs.langchain.com/langsmith/evaluation-types) — official offline/online eval taxonomy.
- Kept: OpenTelemetry GenAI Agent Spans (https://opentelemetry.io/docs/specs/semconv/gen-ai/gen-ai-agent-spans/) — official/standard observability vocabulary for agents, workflows, tools, models, data sources, and conversations.

- Dropped: generic FastAPI boilerplate repos with low signal or no official backing — useful inspiration, but many are SEO/template-heavy and duplicate official FastAPI/Alembic patterns.
- Dropped: random “enterprise RAG” GitHub repos from 2026 with zero stars/single author — too little production evidence; kept LlamaIndex official docs instead.
- Dropped: SEO blog posts on Python monorepo structures — less authoritative than PyPA and uv official docs.
- Dropped: non-Python Temporal Go reference app details except conceptual guidance exposed in official docs — useful for deployment principles, but not directly a Python file-structure source.

## Gaps

- No single official template covers FastAPI + Temporal Python + LangGraph + MCP + enterprise RAG + evals + audit/provenance in one Python monorepo; the recommendation synthesizes official guidance across these ecosystems.
- Exact package names and bounded contexts should be validated against the product domain model, expected team ownership, and deployment topology.
- Security/compliance details such as SOC 2 evidence exports, retention classes, PII redaction, and tenant isolation should be captured in separate ADRs and threat models before implementation.
- Next step: create a thin scaffold with uv workspace members, import-boundary tests, CI jobs, and one vertical slice (API endpoint → Temporal workflow → LangGraph agent → MCP tool → RAG citation → audit event → eval case) to validate boundaries.
