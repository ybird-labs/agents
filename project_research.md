# Workflow and Orchestration Stack for the AI Agent Platform

_Last updated: 2026-05-07_

## Executive recommendation

Use a **two-layer workflow architecture**:

```text
Temporal = durable business workflow engine
LangGraph = AI-agent workflow / graph orchestration layer
MCP = tool integration protocol
Agent Registry = capability discovery and routing metadata
FastAPI = external API surface
Postgres + Redis = application state, registry/audit data, streaming, cache, and coordination
Langfuse or Phoenix = observability and tracing
Ragas / DeepEval = evals and regression gates
Kubernetes + KEDA = production deployment and autoscaling
```

The core design rule is:

```text
Temporal owns durable execution and external side-effect reliability.
LangGraph owns agent reasoning flow and graph/state-machine orchestration.
Workflows coordinate agents.
Agents do not freely call each other.
```

---

## Why this architecture

Production agent systems need two different kinds of orchestration:

1. **Business/process durability**
   - long-running jobs
   - retries
   - idempotency
   - crash recovery
   - human approvals
   - external side effects
   - resumability

2. **Agent reasoning orchestration**
   - routing between reasoning steps
   - model/tool loops
   - planner-executor flows
   - evaluator-optimizer loops
   - multi-agent fan-out/fan-in
   - context/state transitions

Temporal is excellent for the first category. LangGraph is excellent for the second.

Together:

```text
Temporal Workflow
  -> creates durable run
  -> schedules LangGraph execution through a Temporal Activity or external LangGraph service client
  -> waits for human approval if needed
  -> retries external side-effect activities safely
  -> records final status and audit trail

Important boundary: Temporal workflow code must remain deterministic. LLM calls, tool calls, LangGraph runs, network calls, and side effects belong in Temporal Activities or external services. A "child workflow" should mean a Temporal child workflow, not arbitrary LangGraph code running directly inside Temporal workflow logic.

LangGraph Workflow
  -> routes task
  -> calls specialist agent nodes
  -> calls tools through MCP
  -> evaluates intermediate outputs
  -> loops or branches when needed
  -> returns structured result to Temporal
```

---

## Recommended stack

| Layer | Tool | Role |
|---|---|---|
| External API | FastAPI | Request intake, auth, sessions, streaming endpoints, admin APIs. |
| Durable workflow engine | Temporal | Long-running workflows, retries, idempotency, approvals, crash recovery. |
| Agent workflow engine | LangGraph | Graph/state-machine orchestration for agent reasoning. |
| Agent framework | LangGraph nodes and/or Pydantic AI agents | Specialist reasoning units with typed inputs/outputs. |
| Tool protocol | MCP | Standardized tool discovery and invocation. |
| Agent discovery | Internal Agent Registry / A2A-style manifests | Capability lookup, versions, permissions, endpoint metadata. |
| Application state | Postgres | Users, sessions, registry metadata, approvals, audit logs, run summaries, artifact metadata. |
| Temporal persistence | Temporal DB | Workflow history, timers, retries, task queues, durable execution state. |
| LangGraph checkpoints | Postgres or dedicated checkpointer store | Agent graph state, thread state, resumable intermediate agent steps. |
| Streaming/cache/queue | Redis | Streaming, pub-sub, short-lived state, cache, background coordination. Avoid using Redis as the source of truth. For LangGraph standalone deployments, expect Redis to support streaming/background pub-sub while Postgres/checkpointer storage owns durable assistant/thread/run persistence. |
| Artifact storage | S3/GCS/MinIO/local object store | Large files, intermediate reports, trace exports, generated artifacts, document snapshots. |
| RAG workflows | LlamaIndex Workflows or Haystack Pipelines | Document ingestion, retrieval, reranking, context packs. Treat these as bounded components/nodes, not a third global control plane. |
| Observability | Langfuse or Phoenix | LLM traces, tool traces, cost, latency, eval metadata. |
| Evals | Ragas / DeepEval | RAG evals, agent regression tests, CI gates. |
| Deployment | Docker → Kubernetes | Local and production runtime. |
| Autoscaling | KEDA | Queue/event-based worker scaling. |
| Secrets | External Secrets / Vault | Secure API keys and service credentials. |
| Sandbox | gVisor / Daytona / E2B-style sandbox | Isolated code/browser/shell execution. |
| GitOps | Argo CD / Helm / Kustomize | Reproducible production deployments. |

---

## Workflow framework choices

### 1. LangGraph

**Use for AI-native agent workflows.**

Best for:

- graph/state-machine orchestration
- branching and loops
- planner-executor flows
- evaluator-optimizer flows
- multi-agent fan-out/fan-in
- human-in-the-loop within agent reasoning
- checkpointed agent state
- streaming agent runs

Recommended use:

```text
ResearchGraph
  -> route_request
  -> gather_context
  -> call_research_agent
  -> call_reviewer_agent
  -> synthesize_answer
  -> evaluate_answer
  -> final_response
```

References:

- https://docs.langchain.com/langgraph
- https://github.com/langchain-ai/langgraph
- https://docs.langchain.com/langgraph-platform/deploy-standalone-server

### 2. Temporal

**Use for durable production execution.**

Best for:

- long-running workflows
- external API side effects
- retries with backoff
- idempotency
- compensation/rollback patterns
- crash recovery
- human approval waits
- distributed workers

Recommended use:

```text
AgentTaskTemporalWorkflow
  -> validate request
  -> schedule LangGraphRunActivity or call external LangGraph service
  -> wait for approval if action is risky
  -> execute side-effecting tools as idempotent activities
  -> persist final result
  -> emit observability/eval event
```

Temporal integration rules:

- Keep workflow code deterministic.
- Put LLM calls, tool calls, network calls, and LangGraph execution in Activities or external services.
- Use activity timeouts, heartbeats, and cancellation propagation for long-running agent work.
- Use idempotency keys for every side-effecting activity.
- Decide retry ownership explicitly to avoid duplicate retry storms across Temporal, model providers, and agent frameworks.
- Keep workflow/activity payloads serializable and small.
- Store large outputs in artifact storage and pass references through workflow state.
- Publish streaming events through an external stream/pub-sub channel rather than relying on direct Activity streaming.

References:

- https://temporal.io
- https://docs.temporal.io
- https://docs.temporal.io/develop/python
- https://docs.temporal.io/ai-cookbook/durable-agent-with-tools

### 3. Pydantic AI Graph / Durable Execution

**Use when typed Python app code is the priority.**

Pydantic AI is a strong option for typed agent implementations and can integrate with Temporal for durable execution.

Use for:

- typed tools
- typed outputs
- structured validation
- Python-first agents
- testing-heavy services

References:

- https://ai.pydantic.dev
- https://ai.pydantic.dev/graph/
- https://ai.pydantic.dev/durable_execution/overview/
- https://ai.pydantic.dev/durable_execution/temporal/

### 4. LlamaIndex Workflows

**Use for RAG-heavy workflows.**

Best for:

- document ingestion
- knowledge assistant flows
- retrieval pipelines
- query transformation
- RAG context construction

References:

- https://llamaindex.ai/workflows
- https://developers.llamaindex.ai/python/workflows/
- https://developers.llamaindex.ai/python/workflows/durable_workflows/
- https://docs.llamaindex.ai/en/latest/optimizing/production_rag/

### 5. Haystack Pipelines

**Use for explicit retrieval/search pipelines.**

Best for:

- deterministic RAG pipelines
- document search
- reranking
- semantic retrieval
- serving pipelines through Hayhooks

References:

- https://docs.haystack.deepset.ai/docs/pipelines
- https://docs.haystack.deepset.ai/docs/deployment
- https://deepset-ai.github.io/hayhooks/

### 6. Prefect / Dagster / Airflow

**Use for offline data workflows, not live agent conversations.**

Good for:

- scheduled ingestion
- embedding refresh jobs
- offline evals
- data quality checks
- report generation

References:

- https://docs.prefect.io
- https://docs.dagster.io
- https://airflow.apache.org

---

## API and background-work caveat

FastAPI `BackgroundTasks` are acceptable only for small post-response work, such as sending a notification or writing a lightweight audit event. Do not use in-process background tasks for durable, long-running, retry-sensitive agent jobs. Those should run through Temporal, a queue worker, or a durable LangGraph/Pydantic execution layer.

---

## Recommended orchestration patterns

### Workflow-first

Use deterministic workflows whenever the process is known.

```text
route -> retrieve context -> call specialist -> evaluate -> approve -> respond
```

This should be the default for production features.

Reference:

- https://www.anthropic.com/engineering/building-effective-agents

### Graph/state-machine orchestration

Use LangGraph when the flow needs loops, branches, checkpoints, and human intervention.

```text
node A -> node B -> conditional branch -> tool node -> evaluator -> final
```

### Planner-executor

Use when steps cannot be known upfront.

```text
PlannerAgent -> structured plan -> workflow validates plan -> ExecutorAgent executes approved steps
```

Rule:

```text
The planner creates plans.
The workflow executes plans.
The planner does not directly perform privileged actions.
```

### Orchestrator-worker

Use for research, coding, analysis, or decomposition-heavy tasks.

```text
Orchestrator
  -> Worker A
  -> Worker B
  -> Worker C
  -> Synthesizer
```

Workers should receive bounded tasks and return structured outputs.

### Evaluator-optimizer

Use for high-value outputs.

```text
Draft -> Evaluate -> Revise -> Evaluate -> Final
```

Requirements:

- max iterations
- scoring rubric
- evaluator traces
- human escalation when score remains low

### Agents-as-tools

Preferred internal composition strategy.

```text
Workflow calls ResearchAgent as a bounded capability.
ResearchAgent returns structured result.
Workflow keeps ownership of state, policy, budget, and final synthesis.

Token, request, cost, and time budgets must propagate to child/delegated agents and tool loops.
```

### Handoffs

Use only when a specialist should own the next task or user-facing response.

Example:

```text
Support workflow -> Billing specialist owns refund conversation
```

### Swarm/group chat

Use sparingly, only inside bounded workflow nodes.

Allowed for:

- brainstorming
- adversarial review
- exploratory research

Required controls:

- max rounds
- max budget
- explicit termination
- evaluator gate
- complete trace capture

---

## Tool contract requirements

Every tool exposed to agents should be treated as a production API for a non-deterministic caller.

Requirements:

- clear, non-overlapping names
- strict typed input/output schemas
- concise default responses
- pagination or truncation for large outputs
- deterministic permission checks inside the tool/service layer
- idempotency keys for side-effecting tools
- safe, actionable errors with no secret leakage
- trace spans for tool name, version, latency, status, and redacted arguments
- trajectory evals for correct tool choice, arguments, sequencing, and failure recovery

---

## Agent dependency rules

The platform should enforce this direction:

```text
apps -> workflows -> registry -> agent clients -> agents
```

Avoid this:

```text
agent -> agent -> agent
```

Rules:

1. Workflows may call agents through the registry.
2. Workflows must not import concrete agent internals directly.
3. Agents must not call other agents directly by default.
4. Agents may use tools only from their allowlist.
5. Tools must not call agents or workflows.
6. Registry stores metadata and clients; it does not execute business logic.
7. Human approvals are workflow nodes, not ad-hoc messages.
8. Security, budgets, retries, tracing, and audit are workflow/runtime concerns.
9. Remote A2A-style delegation must still be initiated by workflows through registry policy, not by agents directly.
10. Use import-boundary checks and CI validation to prevent agents from importing concrete agent implementations.

---

## Agent registry design

Each agent should have a manifest.

Example:

```yaml
name: research_agent
version: 1.0.0
owner: research-platform
capabilities:
  - web_research
  - source_synthesis
input_schema: ResearchRequest
output_schema: ResearchResult
allowed_tools:
  - web_search
  - fetch_content
permissions:
  network: true
  filesystem: false
  shell: false
cost_profile: medium
latency_slo_ms: 60000
eval_score: 0.91
endpoint: internal://research_agent
```

Registry metadata should include:

- name
- version
- owner
- capabilities
- input schema
- output schema
- tool allowlist
- permissions
- cost profile
- latency SLO
- eval scores
- endpoint
- supported modalities
- deprecation status

---

## Project structure implications

Recommended structure:

```text
src/platform/
  orchestration/
    workflows/
    nodes/
    policies/
    state/
    adapters/

  agents/
    research_agent/
      manifest.yaml
      agent.py
      prompts/
      evals/
    planner_agent/
    executor_agent/
    review_agent/

  registry/
    agents.py
    tools.py
    workflows.py
    validation.py

  agent_clients/
    base.py
    local.py
    remote.py
    langgraph.py
    a2a.py

  protocols/
    mcp/
    a2a/
    internal.py

  tools/
    mcp_clients/
    local_adapters/
    schemas/

  memory/
    checkpoints/
    session/
    long_term/
    stores.py

  retrieval/
    retrievers/
    rerankers/
    context_packing/
    access_filters/

  ingestion/
    loaders/
    chunkers/
    indexers/
    jobs/

  observability/
    tracing.py
    metrics.py
    eval_events.py

  security/
    permissions.py
    guardrails/
    sandbox/
    secrets/
    audit/
    approvals/

  artifacts/
    store.py
    references.py

  human_review/
    queues.py
    schemas.py
```

---

## RAG and memory constraints

RAG and memory are not generic prompt stuffing. Enforce:

- permission and sensitivity filters before retrieval
- final visibility checks before generation
- separation of short-term session state, long-term memory, retrieved knowledge, artifacts, and traces
- provenance, timestamps, confidence, and source references for memory writes
- no long-term storage of unverified model guesses without validation or user confirmation

---

## Deployment architecture

### Local MVP

```text
Docker Compose
+ FastAPI API service
+ worker service
+ Postgres
+ Redis
+ Langfuse
+ optional Qdrant/pgvector
```

### Production

```text
Kubernetes
+ API Deployment
+ Temporal workers
+ LangGraph agent workers
+ Postgres
+ Redis
+ vector DB
+ object/artifact storage, such as S3, GCS, or MinIO
+ Langfuse/Phoenix/OpenTelemetry
+ KEDA autoscaling for queue/event-driven workers
+ Kubernetes Jobs or KEDA ScaledJobs for finite long-running jobs that should not be interrupted by Deployment scale-down
+ External Secrets/Vault
+ sandbox namespace with gVisor
+ Argo CD GitOps
```

---

## Observability requirements

Trace orchestration decisions, not only model calls.

Log:

- selected workflow
- router decision
- selected agent
- skipped agents
- handoff reason
- tool calls
- model version
- prompt version
- retries
- approval events
- evaluator scores
- budget usage
- latency
- cost
- final outcome

Privacy requirements:

- Do not put secrets or sensitive PII in prompts, logs, OpenTelemetry baggage, span attributes, labels, or trace metadata.
- Redact tool arguments and model outputs before exporting traces when needed.
- Treat traces as sensitive production data with retention and access controls.

---

## Evaluation requirements

Create eval suites for:

- routing accuracy
- agent selection
- handoff correctness
- tool selection
- plan quality
- task success
- failure recovery
- cost and latency
- approval frequency
- RAG groundedness
- citation quality
- safety/permission compliance

Run evals:

```text
on pull request
before deployment
after model/prompt/tool changes
after retrieval-index changes
on sampled production traces
```

Operational requirements:

- Every workflow and agent has an owner for eval datasets and thresholds.
- CI blocks releases on critical regression failures.
- Waivers require explicit approval and an expiration date.
- Production traces should be sampled into eval datasets after privacy review.

---

## Human approval requirements

Human approval should be a durable workflow checkpoint.

Require approval for:

- payments
- destructive writes
- external messages
- production deployments
- permission changes
- data exports
- legal/medical/financial high-impact actions
- low-confidence evaluator results
- high-cost actions

---

## Security requirements

Minimum requirements:

- per-run scoped credentials
- tool allowlists by agent and workflow
- MCP server authorization
- sandboxed code/browser/shell execution
- audit logs for all tool calls
- redacted traces
- no secrets in prompts or logs
- approval gates for side effects
- network egress controls for risky tools
- Kubernetes admission policies for privileged pods, secret mounts, sandbox enforcement, and network policies
- image scanning, SBOM generation, and image provenance/signing before production deploys

References:

- https://modelcontextprotocol.io/specification/latest/basic
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- https://external-secrets.io/main/
- https://www.openpolicyagent.org/docs/latest/kubernetes

---

## Phase plan

### Phase 1: Minimal reliable platform / non-production MVP

Build:

```text
FastAPI
+ one LangGraph workflow
+ two specialist agents
+ Postgres
+ Redis
+ Langfuse or Phoenix tracing
+ Docker Compose
+ minimal agent manifests and registry-backed calls
+ basic evals
```

Phase 1 constraints:

- No irreversible external side effects.
- No long-running jobs that must survive process crashes.
- No high-impact approvals.
- Direct agent imports are allowed only for throwaway prototypes; the recommended Phase 1 path is already registry-backed.

Example first workflow:

```text
Research request
  -> ResearchAgent
  -> ReviewAgent
  -> Synthesis node
  -> Final response
```

### Phase 2: Durable execution

Add:

```text
Temporal
+ human approval checkpoints
+ idempotent activities
+ retry policies
+ artifact storage
+ registry-backed agent calls
```

### Phase 3: Production hardening

Add:

```text
Kubernetes
+ KEDA
+ External Secrets/Vault
+ sandbox runtime
+ CI eval gates
+ Argo CD
+ full OpenTelemetry traces
```

### Phase 4: Advanced orchestration

Add only when evals justify it:

```text
planner-executor flows
evaluator-optimizer loops
bounded swarm/group-review nodes
A2A-style remote agent delegation
multi-agent capability marketplace
```

---

## Final decision

Adopt this as the workflow/orchestration stack:

```text
Temporal for durable business orchestration.
LangGraph for agent reasoning workflows.
MCP for tool integration.
Typed Agent Registry for agent discovery.
FastAPI for API entrypoints.
Postgres/Redis/object storage for application state, coordination, and artifacts.
Langfuse/Phoenix for observability.
Ragas/DeepEval for evals.
Kubernetes/KEDA for production deployment.
```

The most important architecture constraint:

```text
Agents are workers.
Workflows are the control plane.
```

This architecture gives us the right foundations for reliability, explicit control, auditability, and room to scale from simple independent agents to complex coordinated multi-agent workflows. It does not guarantee reliability by itself: correctness still depends on idempotency, checkpointing, evals, permissions, observability, failure testing, and operational discipline.

Before implementation, re-check current framework APIs, deployment terms, and licensing/open-core boundaries for LangGraph/LangSmith, Langfuse/Phoenix, MCP/A2A, and any hosted services.

---

## Primary references

- Anthropic, Building Effective Agents: https://www.anthropic.com/engineering/building-effective-agents
- LangGraph docs: https://docs.langchain.com/langgraph
- LangGraph deployment: https://docs.langchain.com/langgraph-platform/deploy-standalone-server
- Temporal docs: https://docs.temporal.io
- Temporal durable agent example: https://docs.temporal.io/ai-cookbook/durable-agent-with-tools
- Pydantic AI: https://ai.pydantic.dev
- Pydantic AI Graph: https://ai.pydantic.dev/graph/
- Pydantic AI Temporal integration: https://ai.pydantic.dev/durable_execution/temporal/
- OpenAI Agents orchestration: https://developers.openai.com/api/docs/guides/agents/orchestration
- Google ADK workflow agents: https://google.github.io/adk-docs/agents/workflow-agents/
- Microsoft Multi-agent Reference Architecture: https://microsoft.github.io/multi-agent-reference-architecture/docs/reference-architecture/Reference-Architecture.html
- CrewAI production architecture: https://docs.crewai.com/en/concepts/production-architecture
- AG2 orchestration patterns: https://docs.ag2.ai/latest/docs/user-guide/advanced-concepts/orchestration/group-chat/patterns/
- LlamaIndex Workflows: https://developers.llamaindex.ai/python/workflows/
- LlamaIndex durable workflows: https://developers.llamaindex.ai/python/workflows/durable_workflows/
- Haystack pipelines: https://docs.haystack.deepset.ai/docs/pipelines
- MCP specification: https://modelcontextprotocol.io/specification/latest/basic
- A2A specification: https://github.com/google/A2A/blob/7b900e77/docs/specification.md
- Langfuse: https://docs.langfuse.com
- Phoenix tracing: https://docs.arize.com/phoenix/tracing/llm-traces
- Ragas: https://docs.ragas.io
- DeepEval: https://github.com/confident-ai/deepeval
- KEDA: https://keda.sh/docs/2.17/concepts/scaling-deployments/
- External Secrets Operator: https://external-secrets.io/main/
- Argo CD: https://argo-cd.readthedocs.io/en/stable/

