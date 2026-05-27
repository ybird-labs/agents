# Research: Project/file structure patterns for Python/FastAPI + Temporal + LangGraph/LangChain + RAG + MCP/tool registry systems

## Summary
For Exeboard, the best default is a **single Python app package with vertical-slice feature modules plus a small shared kernel**, not a heavy clean-architecture package split on day one. Keep deployable entrypoints separate (`api`, `workers`, optional `mcp_server`) while sharing feature-owned application logic, RAG components, graph definitions, and tool contracts through internal packages. If/when Exeboard grows into independently deployed services or publishable libraries, migrate to a `uv` workspace/monorepo with `apps/*` and `packages/*`; until then, a `src/exeboard/...` layout gives simpler imports, tests, deployment, and refactoring.

## Findings
1. **FastAPI’s official large-app pattern is modular routers under one Python package** — FastAPI recommends moving beyond a single file into an `app` package with `main.py`, `dependencies.py`, `routers/*`, and optional internal modules; routers are included at startup with prefixes/dependencies/tags, so domain routers compose cleanly without runtime cost. This supports an Exeboard API entrypoint that stays thin and assembles routers from feature packages. [Source](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

2. **For larger FastAPI monoliths, feature/vertical-slice modules scale better than file-type folders** — The `fastapi-best-practices` repo argues that `crud/`, `routers/`, `models/` by file type works for small services but did not scale well for a monolith with many domains; it recommends `src/auth/{router,schemas,models,dependencies,service,...}` and similar per-domain folders. For Exeboard, this maps well to `projects`, `agents`, `runs`, `knowledge`, `tools`, and `workflows` slices. [Source](https://github.com/zhanymkanov/fastapi-best-practices)

3. **Clean architecture is useful as an internal discipline, but too much top-level layering can fight AI/RAG feature iteration** — Clean/layered FastAPI templates commonly split `domain`, `application`, `infrastructure`, and `presentation`, which is strong for stable domain rules and testability but creates cross-folder navigation for every feature. Exeboard should borrow the dependency rule—domain/application code should not import FastAPI, Temporal worker bootstraps, vector DB clients, or MCP transports—but keep most files grouped by vertical feature. [Source](https://github.com/eugeneliukindev/fastapi-clean-layered-arch-example)

4. **Temporal requires explicit worker registration per task queue, so workflows/activities need stable package boundaries** — Temporal Python workers register exact workflow/activity types and bind to exactly one task queue; all workers polling the same queue must register the same workflow/activity types. Exeboard should therefore centralize task queue names and provide worker entrypoints that import feature-owned workflows/activities through registry modules, instead of scattering worker startup code inside API routes. [Source](https://docs.temporal.io/develop/python/workers/run-worker-process)

5. **Temporal sample projects favor separate `worker.py`, `starter.py`, `workflows.py`, and `activities.py` modules per workflow area** — The official samples use small directories such as `batch_sliding_window/{worker.py,starter.py,*workflow.py,*activity.py}` and include LangChain/LangGraph examples. That pattern supports Exeboard feature folders like `features/executions/temporal/{workflows.py,activities.py}` plus top-level worker bootstraps such as `workers/executions.py`. [Source](https://github.com/temporalio/samples-python)

6. **LangGraph expects graph packages plus `langgraph.json` mapping graph names to compiled graph variables/functions** — Official LangGraph app structure has package code (`agent.py`, `utils/tools.py`, `utils/nodes.py`, `utils/state.py`) and `langgraph.json` declaring dependencies, graph paths, and env files. Exeboard should keep graph definitions importable independently from FastAPI and Temporal: e.g. `features/agents/graphs/supervisor.py:graph`, `features/knowledge/graphs/indexing.py:graph`, mapped in `langgraph.json`. [Source](https://docs.langchain.com/oss/python/langgraph/application-structure)

7. **Credible LangGraph RAG templates split indexing, retrieval, and researcher subgraphs** — LangChain’s RAG research agent template defines three graph areas: an index graph, retrieval graph, and researcher subgraph under `src/*_graph/graph.py`. For Exeboard, separate ingestion/indexing workflows from query-time retrieval/agent graphs; avoid one giant `rag.py`. [Source](https://github.com/langchain-ai/rag-research-agent-template)

8. **MCP tools are schema-defined capabilities, so a registry should own contracts separately from transports** — MCP servers expose `tools/list` and `tools/call`; each tool has a unique name, description, JSON Schema input, optional output schema, and servers may emit `notifications/tools/list_changed`. Exeboard should model tools as registered descriptors/adapters in `features/tools/registry.py` and expose them via MCP transport, LangChain tool adapters, and internal API without duplicating schemas. [Source](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

9. **MCP’s conceptual split of Tools, Resources, and Prompts is a useful folder boundary** — MCP servers provide tools for model-controlled actions, resources for application-controlled context, and prompts for user-controlled reusable templates. Exeboard’s MCP/tool system should avoid putting all capabilities under `tools/`; use `tools/`, `resources/`, and `prompts/` subpackages where MCP exposure matters. [Source](https://modelcontextprotocol.io/docs/learn/server-concepts)

10. **Use Python `src/` layout for correctness and packaging hygiene** — PyPA documents that `src` layout prevents accidental importing of the in-development root and ensures editable installs expose only intended import packages. Exeboard should use `src/exeboard` even as an application, because it will likely have CLI/worker/API entrypoints and tests that should exercise installed-package behavior. [Source](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)

11. **Use a `uv` workspace only once Exeboard has true multi-package needs** — `uv` workspaces are intended for multiple interconnected packages with separate `pyproject.toml` files but one lockfile; they fit a FastAPI app plus separate libraries, plugin packages, or CLI packages. They add isolation and package-level dependencies but also enforce one dependency resolution/Python-version intersection, and Python itself cannot prevent cross-member imports of undeclared dependencies. [Source](https://docs.astral.sh/uv/concepts/projects/workspaces/)

## Recommended Exeboard structure

### Recommended now: single app package, vertical slices, clean boundaries

```text
exeboard/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── langgraph.json
├── alembic/
├── src/
│   └── exeboard/
│       ├── __init__.py
│       ├── config.py                 # global settings
│       ├── logging.py
│       ├── bootstrap.py              # DI/container/factory wiring, no domain logic
│       ├── api/
│       │   ├── main.py               # FastAPI app factory + router inclusion
│       │   ├── deps.py               # request/session/auth dependencies
│       │   ├── errors.py             # exception -> HTTP mapping
│       │   └── v1.py                 # includes feature routers
│       ├── workers/
│       │   ├── temporal_client.py
│       │   ├── registry.py           # task queues -> workflows/activities
│       │   ├── executions_worker.py
│       │   ├── ingestion_worker.py
│       │   └── agent_worker.py
│       ├── mcp_server/
│       │   ├── app.py                # MCP transport/server startup
│       │   ├── tools.py              # bridge registry -> MCP tools/list/call
│       │   ├── resources.py
│       │   └── prompts.py
│       ├── shared/
│       │   ├── db/
│       │   ├── events/
│       │   ├── security/
│       │   ├── observability/
│       │   ├── schemas.py            # truly shared API/domain DTOs only
│       │   └── errors.py
│       ├── integrations/
│       │   ├── llm_providers/
│       │   ├── vectorstores/
│       │   ├── embedding_models/
│       │   ├── temporal/
│       │   └── external_tools/
│       └── features/
│           ├── projects/
│           │   ├── router.py
│           │   ├── schemas.py
│           │   ├── models.py
│           │   ├── service.py
│           │   ├── repository.py
│           │   └── tests/
│           ├── executions/
│           │   ├── router.py
│           │   ├── schemas.py
│           │   ├── service.py
│           │   ├── temporal/
│           │   │   ├── workflows.py
│           │   │   ├── activities.py
│           │   │   └── signals.py
│           │   └── tests/
│           ├── agents/
│           │   ├── router.py
│           │   ├── schemas.py
│           │   ├── service.py
│           │   ├── graphs/
│           │   │   ├── supervisor.py
│           │   │   ├── nodes.py
│           │   │   ├── state.py
│           │   │   └── prompts.py
│           │   └── tests/
│           ├── knowledge/
│           │   ├── router.py
│           │   ├── schemas.py
│           │   ├── service.py
│           │   ├── ingestion/
│           │   │   ├── loaders.py
│           │   │   ├── chunking.py
│           │   │   └── embeddings.py
│           │   ├── retrieval/
│           │   │   ├── retriever.py
│           │   │   ├── rerank.py
│           │   │   └── citations.py
│           │   ├── graphs/
│           │   │   ├── indexing.py
│           │   │   └── retrieval.py
│           │   └── temporal/
│           │       ├── workflows.py
│           │       └── activities.py
│           └── tools/
│               ├── router.py
│               ├── schemas.py
│               ├── registry.py       # canonical internal tool registry
│               ├── contracts.py      # names, JSON schemas, output schemas
│               ├── adapters/
│               │   ├── langchain.py  # registry -> LangChain tools
│               │   ├── mcp.py        # registry -> MCP descriptors/calls
│               │   └── temporal.py   # long-running tools -> workflows
│               └── providers/
│                   ├── github.py
│                   ├── filesystem.py
│                   └── browser.py
├── tests/
│   ├── integration/
│   └── e2e/
└── scripts/
```

Example `langgraph.json`:

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent_supervisor": "./src/exeboard/features/agents/graphs/supervisor.py:graph",
    "knowledge_indexing": "./src/exeboard/features/knowledge/graphs/indexing.py:graph",
    "knowledge_retrieval": "./src/exeboard/features/knowledge/graphs/retrieval.py:graph"
  },
  "env": "./.env"
}
```

### Upgrade path: `uv` workspace / monorepo when packages become independently deployable

Use this when Exeboard has multiple deployables, optional plugins, separate release cycles, or dependency isolation pressure:

```text
exeboard/
├── pyproject.toml             # workspace root + shared tool config
├── uv.lock
├── apps/
│   ├── api/                   # FastAPI app package
│   ├── temporal-workers/       # worker process package
│   ├── mcp-server/             # MCP server package
│   └── web/                    # if frontend lives here
└── packages/
    ├── exeboard-core/          # domain/application services
    ├── exeboard-ai/            # LangGraph/RAG abstractions
    ├── exeboard-tools/         # tool registry/contracts/providers
    └── exeboard-integrations/  # external clients
```

## Tradeoffs

| Pattern | Benefits | Costs / risks | Exeboard recommendation |
|---|---|---|---|
| File-type folders (`routers/`, `schemas/`, `models/`) | Simple for tiny apps; mirrors FastAPI examples | Cross-feature edits require jumping across many folders; weak ownership as domains grow | Avoid except inside a small feature package |
| Clean architecture top-level layers (`domain/`, `application/`, `infrastructure/`, `presentation/`) | Strong testability and dependency direction; good for stable business rules | Verbose; AI/RAG features often span graph/state/prompts/retrieval/tool adapters, causing scattered changes | Use as a rule, not as the primary folder layout |
| Vertical slices (`features/<domain>/...`) | High cohesion; feature-owned routers/schemas/services/graphs/Temporal activities; good for product iteration | Shared abstractions can duplicate if not curated; cross-feature imports need rules | Primary structure now |
| Single package `src/exeboard` | Easy deployment/imports; one lockfile; simple API/worker/MCP entrypoints | Less dependency isolation; package can become large | Best current default |
| `uv` workspace `apps/*` + `packages/*` | Good for multiple deployables/libraries, package-level dependencies, plugin systems | More packaging overhead; one resolved dependency universe; Python cannot fully enforce dependency isolation | Adopt later when boundaries harden |
| Separate microservice repos | Strong deploy/runtime isolation | Slow cross-cutting changes; duplication; early operational burden | Not recommended until clear scaling/security constraints require it |

## Sources
- Kept: FastAPI Bigger Applications (https://fastapi.tiangolo.com/tutorial/bigger-applications/) — official FastAPI modular router/package guidance.
- Kept: zhanymkanov/fastapi-best-practices (https://github.com/zhanymkanov/fastapi-best-practices) — credible production-oriented feature-module layout and tradeoff discussion.
- Kept: eugeneliukindev/fastapi-clean-layered-arch-example (https://github.com/eugeneliukindev/fastapi-clean-layered-arch-example) — representative clean/layered FastAPI template for comparison.
- Kept: Temporal Python worker docs (https://docs.temporal.io/develop/python/workers/run-worker-process) — authoritative worker/task-queue registration constraints.
- Kept: temporalio/samples-python (https://github.com/temporalio/samples-python) — official practical Python sample layouts, including LangChain/LangGraph-related samples.
- Kept: LangGraph application structure docs (https://docs.langchain.com/oss/python/langgraph/application-structure) — official `langgraph.json`, dependency, and graph file layout requirements.
- Kept: LangChain RAG research agent template (https://github.com/langchain-ai/rag-research-agent-template) — official RAG graph decomposition example.
- Kept: MCP Tools spec (https://modelcontextprotocol.io/specification/2025-06-18/server/tools) — authoritative tool schema/discovery/call protocol.
- Kept: MCP server concepts (https://modelcontextprotocol.io/docs/learn/server-concepts) — authoritative Tools/Resources/Prompts conceptual boundaries.
- Kept: PyPA src layout vs flat layout (https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/) — authoritative packaging rationale for `src/`.
- Kept: uv workspaces docs (https://docs.astral.sh/uv/concepts/projects/workspaces/) — authoritative workspace/monorepo mechanics and caveats.
- Dropped: Generic SEO FastAPI structure articles — redundant with official docs and stronger production repos.
- Dropped: Random LangGraph/MCP demo repos with low provenance — useful inspiration but less credible than LangChain/MCP/Temporal primary sources.
- Dropped: Broad Python monorepo blog posts — some useful examples, but `uv` and PyPA docs provide stronger primary evidence.

## Gaps
- I did not inspect Exeboard’s current repository files, so the recommendation is architecture-oriented rather than a migration diff.
- I did not benchmark import times, worker startup times, or graph hot-reload behavior for this layout.
- Next steps: map current Exeboard modules into the proposed `features/*`, define explicit import rules, and create a short ADR deciding when to split into `apps/*` + `packages/*`.
