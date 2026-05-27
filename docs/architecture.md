# Exeboard Agent Workflow Platform Architecture

_Last updated: 2026-05-20_

## 1. Executive summary

Exeboard should be built as a **reusable multi-agent workflow platform for board/company operations**, not as a document-summary product, spreadsheet agent, or single hardcoded board-pack workflow.

The durable product is the **agent workflow runtime**: users should be able to create, configure, run, inspect, approve, and reuse agent workflows over company artifacts. Board briefs, meeting minutes, financial summaries, document Q&A, compliance checks, and follow-up tracking are initial workflow templates built on that runtime.

The platform should let users select artifacts, define or choose a workflow, compose reusable agent capabilities, assign tools and permissions, run the workflow, inspect what each agent did, approve or reject outputs/actions, and reuse the same agents/capabilities in other workflows.

Core principle:

```text
Workflows own control.
Agents provide reasoning.
Tools perform bounded actions.
Evidence/provenance makes outputs trustworthy.
Humans approve high-impact outputs.
```

The recommended v0 is therefore:

```text
Create and run reusable agent workflows over selected company artifacts.

Given selected artifacts + a user goal or workflow template,
classify the goal,
construct or load a workflow plan,
compose reusable capabilities,
run specialist agents/tools,
show the execution trace,
produce cited outputs,
route high-impact steps for approval,
and store a complete audit trail.
```

Initial workflow templates should include board brief generation, meeting minutes, financial spreadsheet summary, and document Q&A, but these are **demonstrations of the platform**, not the platform boundary.

---

## 2. Research-backed architecture decision

The strongest academic and industry evidence points toward a **compound AI system** with durable orchestration, specialist agents, registries, provenance, evaluation, and human review.

### Key research conclusions

1. **Use stateful workflow/graph orchestration instead of unbounded chat loops.** LangGraph supports graph state, checkpoints, replay/debugging, memory, and human-in-the-loop patterns. Temporal or an equivalent durable workflow engine should own retries, timeouts, approvals, and long-running execution.

2. **Use reusable registries.** Enterprise agent architectures increasingly rely on agent registries, data registries, tool registries, planners, task coordinators, budgets, and sessions.

3. **Use manager/specialist orchestration selectively.** Multi-agent manager patterns are useful when tasks are open-ended, but deterministic workflow templates are better when the process is known.

4. **Treat provenance as product infrastructure.** Board-grade outputs need traceability from final claim to source document/page/cell/timestamp, plus prompt/model/tool/run metadata.

5. **Evaluate at component and workflow levels.** RAG, spreadsheet analysis, meeting minutes, citations, and action extraction need separate regression datasets and metrics.

6. **Spreadsheet and meeting automation remain reliability risks.** Public benchmarks show that spreadsheet agents and meeting-summary systems still require validation, exact-source citations, and human approval.

---

## 3. Product framing

Exeboard is a platform for composing, running, governing, and reusing AI-agent workflows over company artifacts.

The core product surface is not a single generated report. It is the workflow layer where users can:

```text
create or select workflows
choose artifacts and context
compose agents/capabilities/tools
set permissions, budgets, and approval rules
run and monitor workflow executions
inspect evidence, traces, and audit logs
save successful ad hoc plans as reusable templates
```

### Core platform primitives

The primary product primitives are:

```text
Agent
Capability
Tool
Artifact
WorkflowTemplate
WorkflowPlan
WorkflowStep
WorkflowRun
Evidence
Approval
AuditEvent
GeneratedOutput
```

Outputs such as briefs, minutes, summaries, and answers are products of workflows, not the central architecture boundary.

### Core platform capabilities

```text
Artifact ingestion
Artifact classification
Document parsing
Spreadsheet parsing
Transcript parsing
Semantic/hybrid retrieval
Question answering with citations
Document summarization
Financial spreadsheet analysis
Meeting-minutes drafting
Action item extraction
Decision extraction
Risk extraction
Governance/compliance review
Citation verification
Report generation
Audit logging
Human approval
```

### Example workflow templates

```text
Board Pack Review
  selected documents + spreadsheets
  -> summarize sections
  -> extract decisions, risks, KPIs, open questions
  -> verify citations
  -> produce board brief

Meeting Minutes
  transcript + agenda + selected context
  -> extract attendees, decisions, motions, votes, actions
  -> draft formal minutes
  -> cite transcript timestamps
  -> send to review

Financial Review
  spreadsheet + prior reports/context
  -> detect workbook structure
  -> extract KPIs and assumptions
  -> explain variance
  -> cite cells/ranges
  -> flag caveats

Ad hoc Artifact Q&A
  selected artifacts + user question
  -> retrieve permission-filtered evidence
  -> answer with citations
  -> verify grounding

Compliance/Governance Review
  minutes + policies + board rules
  -> check required elements
  -> flag missing approvals/actions
  -> produce review checklist
```

---

## 4. System goals and non-goals

### Goals

- Reusable capability-based architecture.
- Support multiple workflow templates and ad hoc user goals.
- Preserve source structure for documents, spreadsheets, and transcripts.
- Produce source-grounded outputs with citations.
- Maintain audit trails for uploads, parsing, agent runs, tool calls, outputs, approvals, and revisions.
- Support human review for high-impact outputs.
- Support evaluation/regression testing from day one.
- Keep agents bounded by typed tools, permissions, and budgets.

### Non-goals for v0

- Fully autonomous board operations.
- Arbitrary spreadsheet editing without review.
- Agent-to-agent freeform swarms as the primary architecture.
- Replacing legal, financial, or governance human review.
- Building a custom spreadsheet engine from scratch.
- Supporting every enterprise integration immediately.

---

## 5. Recommended stack

| Layer | Recommendation |
|---|---|
| API | FastAPI |
| Durable workflows | Temporal |
| Agent graphs | LangGraph |
| Agent/tool protocol | Internal typed registry + MCP adapters |
| Database | Postgres |
| Vector search | pgvector initially; Qdrant if scale requires |
| Cache/streaming | Redis |
| Object/artifact storage | S3/GCS/MinIO/local dev |
| Document parsing | Docling, LlamaParse/LlamaSheets, Unstructured, Reducto depending on file type and deployment needs |
| Spreadsheet tooling | spreadsheet-kit/spreadsheet-mcp, ExStruct, Excel/Graph/LibreOffice where fidelity demands |
| Transcription | Whisper, Deepgram, AssemblyAI, or equivalent |
| Observability | OpenTelemetry + Langfuse or LangSmith |
| Evals | Ragas, DeepEval, and custom golden datasets |
| Deployment | Docker Compose for dev; Kubernetes/KEDA for production |
| Security | RBAC/ABAC, tenant isolation, encryption, sandboxing, prompt-injection controls |

---

## 6. High-level architecture

```text
Client/UI/API
  -> Workspace + Artifact APIs
  -> Workflow Runner API
  -> Review/Approval API

Workflow Control Plane
  -> Temporal workflows
  -> workflow templates
  -> approval checkpoints
  -> retries/timeouts/idempotency
  -> audit events

Agent Reasoning Plane
  -> LangGraph graphs
  -> supervisor/router nodes
  -> specialist agents
  -> critique/verification nodes

Capability + Tool Plane
  -> capability registry
  -> tool registry
  -> MCP adapters
  -> parsers, retrievers, spreadsheet tools, transcript tools

Evidence + Knowledge Plane
  -> parsed artifacts
  -> chunks/blocks/tables/cells/segments
  -> embeddings + hybrid search
  -> citation and provenance records

Storage + Governance
  -> Postgres metadata
  -> object storage artifacts
  -> vector index
  -> audit log
  -> approvals
  -> traces/evals
```

---

## 7. Core domain model

The platform should be built around these primitives:

```text
Organization
User
Workspace
Artifact
ArtifactVersion
ParsedArtifact
ParsedBlock
EmbeddingRecord
Capability
WorkflowTemplate
WorkflowRun
AgentRun
ToolCall
Evidence
Citation
GeneratedOutput
Approval
AuditEvent
EvaluationRun
```

### Artifact

Represents an uploaded or connected source file.

Fields:

```text
id
workspace_id
kind: document | spreadsheet | transcript | presentation | email | other
filename
mime_type
storage_uri
sha256
uploaded_by
created_at
sensitivity_label
status
```

### ArtifactVersion

Source files and parsed outputs must be versioned.

```text
id
artifact_id
version_number
storage_uri
sha256
created_by
created_at
source: upload | import | generated | revised
```

### ParsedArtifact

Stores parser output metadata and references to structured artifacts.

```text
id
artifact_version_id
parser_name
parser_version
status
parsed_storage_uri
extracted_text_uri
metadata_json
created_at
```

### WorkflowTemplate

Reusable workflow definition. Templates can be system-defined or user/org-defined.

```text
id
name
version
description
template_type: system | custom
scope: global | organization | workspace
created_by
status: draft | active | deprecated
input_schema
output_schema
parameters_json
step_graph_json
required_capabilities
approval_policy
risk_level
requires_approval
```

### WorkflowPlan and WorkflowStep

Ad hoc user goals should be converted into explicit plans before execution. Plans may be one-off or saved back as custom templates.

```text
WorkflowPlan
  id
  workflow_run_id
  planner_agent_run_id
  status: proposed | approved | executing | completed | rejected
  rationale
  risk_level
  approval_policy

WorkflowStep
  id
  workflow_plan_id
  order_index
  capability_name
  input_bindings_json
  output_bindings_json
  required_tools
  risk_level
  status
```

### WorkflowRun

A single execution of a template or ad hoc goal.

```text
id
workspace_id
workflow_template_id nullable
user_goal
selected_artifact_ids
status
started_by
started_at
completed_at
temporal_workflow_id
budget
risk_level
```

### Capability

A reusable platform ability.

```text
id
name
version
description
input_schema
output_schema
allowed_tools
required_permissions
risk_level
owner
```

### Citation

A source reference used by a generated output.

```text
id
workspace_id
artifact_id
artifact_version_id
source_type: pdf | docx | xlsx | transcript | html | text
page_number nullable
bbox nullable
sheet_name nullable
cell_range nullable
timestamp_start nullable
timestamp_end nullable
text_quote nullable
confidence
used_by_output_id
created_at
```

### Evidence

Evidence is a normalized pointer to source material or derived facts used by agents and outputs.

```text
id
workspace_id
artifact_id
artifact_version_id
parsed_block_id nullable
sheet_name nullable
cell_range nullable
transcript_segment_id nullable
page_number nullable
bbox nullable
quote nullable
extracted_value_json nullable
confidence
parser_name
parser_version
created_at
```

### AgentRun

```text
id
workflow_run_id
agent_name
agent_version
capability_name
model_provider
model_name
model_version nullable
prompt_version
input_hash
output_hash
status
latency_ms
cost_usd nullable
started_at
completed_at
```

### ToolCall

```text
id
workflow_run_id
agent_run_id nullable
tool_name
tool_version
input_schema_version
input_hash
output_hash
status
latency_ms
error_type nullable
created_at
```

### GeneratedOutput

```text
id
workflow_run_id
output_type: answer | brief | minutes | report | checklist | artifact
version
storage_uri nullable
body_json
created_by_agent_run_id
citation_ids
validator_scores_json
approval_status
created_at
```

### ProvenanceEdge

Use explicit lineage edges so downstream outputs can be invalidated or replayed when a source parse/model/tool changes.

```text
id
workspace_id
from_entity_type
from_entity_id
to_entity_type
to_entity_id
relationship: derived_from | cited_by | generated_by | validated_by | approved_by | supersedes
created_at
metadata_json
```

### AuditEvent

Audit events should be application records, not scattered logs.

```text
id
workspace_id
actor_type: user | agent | system
actor_id
event_type
entity_type
entity_id
timestamp
request_id
metadata_json
input_hash nullable
output_hash nullable
```

---

## 8. Runtime flow

### Generic execution loop

```text
User selects artifacts + enters goal
  -> API creates WorkflowRun
  -> classify goal and artifacts
  -> select template or create ad hoc plan
  -> resolve required capabilities
  -> run Temporal workflow
  -> call LangGraph graph for reasoning/planning/synthesis
  -> invoke bounded tools through registry
  -> collect evidence/citations
  -> validate output and citations
  -> request human approval if needed
  -> persist GeneratedOutput
  -> write AuditEvents
```

### Deterministic vs agentic control

Use deterministic workflow templates when the process is known:

```text
parse -> retrieve -> summarize -> verify -> approve -> export
```

Use agentic planning when the user goal is open-ended:

```text
classify goal -> propose plan -> validate plan -> execute capabilities -> review
```

The planner may propose steps, but the workflow executes them.

---

## 9. Capability registry design

Capabilities are product-level abilities. Agents and tools are implementation details behind capabilities.

Example:

```yaml
name: analyze_spreadsheet
version: 0.1.0
description: Analyze financial spreadsheet structure and summarize KPIs, assumptions, and variances.
input_schema: SpreadsheetAnalysisRequest
output_schema: SpreadsheetAnalysisResult
allowed_tools:
  - describe_workbook
  - read_range
  - profile_table
  - inspect_formula
  - cite_cell_range
risk_level: medium
requires_review: true
```

Initial capabilities:

```text
classify_artifact
parse_artifact
summarize_document
answer_with_citations
verify_citations
analyze_spreadsheet
extract_decisions
extract_action_items
draft_meeting_minutes
review_governance_requirements
generate_report
produce_audit_log
```

---

## 10. Agent design

Agents should be specialist workers with bounded tools and typed outputs.

Initial agents:

```text
GoalClassifierAgent
ArtifactClassifierAgent
DocumentSummarizerAgent
SpreadsheetAnalystAgent
TranscriptAnalystAgent
MeetingMinutesWriterAgent
ActionDecisionExtractorAgent
GovernanceReviewerAgent
CitationVerifierAgent
SynthesisEditorAgent
```

Each agent should have a manifest:

```yaml
name: meeting_minutes_writer
version: 0.1.0
owner: exeboard-ai
capabilities:
  - draft_meeting_minutes
  - extract_action_items
  - extract_decisions
allowed_tools:
  - search_transcript
  - get_transcript_segment
  - cite_timestamp
permissions:
  network: false
  filesystem: read_only
input_schema: MeetingMinutesRequest
output_schema: MeetingMinutesDraft
requires_review: true
```

Rules:

1. Workflows may call agents through the registry.
2. Agents should not directly call other agents by default.
3. Agents only use allowlisted tools.
4. Risky actions require workflow-level approval.
5. Agents return structured outputs, citations, confidence, and caveats.

---

## 11. Tool design

Tools should be narrow, typed, permission-checked, and traceable.

Good tools:

```text
describe_artifact
search_artifact
get_source_context
extract_document_tables
describe_workbook
read_range
profile_table
inspect_formula
compare_periods
get_transcript_segment
cite_page
cite_cell_range
cite_timestamp
validate_citations
render_report
```

Avoid broad unsafe tools:

```text
read_entire_workspace
execute_arbitrary_python
modify_any_file
send_email_anywhere
rewrite_workbook_without_diff
```

For side-effecting tools:

```text
plan -> dry run -> diff/proof -> validation -> approval -> execute
```

MCP can be used as an adapter, but the internal tool registry should be canonical so the same tool contracts can be exposed to LangGraph, Temporal activities, MCP servers, and API routes.

---

## 12. Ingestion and parsing pipeline

Ingestion should be asynchronous, versioned, event-driven, and replayable.

```text
Upload/import
  -> malware/content checks
  -> immutable object storage write
  -> Artifact + ArtifactVersion rows
  -> document-received event
  -> classification
  -> parser routing
  -> structured extraction
  -> confidence scoring
  -> deterministic validators/business rules
  -> normalized blocks/tables/cells/segments
  -> embeddings/indexing
  -> provenance records
  -> low-confidence or high-risk review queue
```

Each stage should write per-stage status, timings, artifact references, confidence scores, validation outcomes, retry counts, and errors. Failed stages should support retry and dead-letter handling. Parser output must be reproducible from immutable raw artifacts plus parser/model/container/prompt versions.

### Document representation

```text
DocumentBlock
  artifact_version_id
  page_number
  section_heading
  block_type: paragraph | table | figure | list
  text
  bbox
  source_offset
  metadata
```

### Spreadsheet representation

```text
WorkbookModel
  sheets
  tables/regions
  named_ranges
  formulas
  cached_values
  charts
  pivots
  merged_cells
  hidden_rows_columns_sheets
  cell_metadata
```

Spreadsheet-specific rule:

```text
Do not flatten spreadsheets into plain text too early.
Preserve workbook structure and cite cells/ranges.
```

Spreadsheet workflows should explicitly separate three lanes:

```text
Workbook lane: exact cells, formulas, styles, names, charts, diffs, recalc, proof.
Analytics lane: DuckDB/pandas/Polars-style table summaries, filters, joins, profiling.
LLM lane: planning, explanation, assumption surfacing, and narrative synthesis.
```

Formula recalculation and fidelity must be explicit. Every spreadsheet output should disclose the active mode:

```text
Excel-native
LibreOffice/headless
native formula engine
cached-values-only
```

After any spreadsheet edit, the workflow must run dry-run/diff/proof, recalculate with the selected backend, read back target cells, capture formula errors, detect unintended changes, and require human approval for financial or governance-critical outputs.

### Transcript representation

```text
TranscriptSegment
  speaker
  start_time
  end_time
  text
  confidence
  source_audio_uri
```

---

## 13. Retrieval and citations

Retrieval should support:

```text
keyword search
vector search
hybrid search
metadata filters
permission filters
artifact selection
reranking
citation construction
```

Every generated claim that depends on source material should be linkable to evidence:

```text
PDF/DOCX -> page + quote + optional bounding box
Spreadsheet -> sheet + cell/range + value/formula context
Transcript -> timestamp range + speaker + quote
```

Citation verification should be a separate step, not just a prompt instruction.

---

## 14. Human review and approvals

Human-in-the-loop should be a workflow primitive.

Require approval for:

```text
final board minutes
final board brief
external messages
spreadsheet edits
financially material claims with low confidence
governance/legal/compliance-sensitive outputs
high-cost or broad data actions
```

Approval records should include:

```text
approver
input output version
citations shown
changes requested
approved/rejected timestamp
final artifact version
```

---

## 15. Evaluation strategy

Build evals from day one.

### Eval datasets

```text
evals/datasets/
  document_qa.yaml
  board_brief.yaml
  meeting_minutes.yaml
  action_items.yaml
  decisions.yaml
  spreadsheet_summary.yaml
  citation_grounding.yaml
  adversarial_prompt_injection.yaml
```

### Metrics

```text
citation correctness
unsupported claim rate
groundedness
answer correctness
action item precision/recall
decision extraction precision/recall
meeting-minutes completeness
spreadsheet KPI correctness
cell/range citation accuracy
latency
cost
human correction rate
```

Use Ragas/DeepEval where helpful, but board-specific evals must be custom and source-grounded.

Evaluation requirements:

```text
Every workflow/capability has an owner.
Every eval suite has thresholds.
CI and pre-deploy checks block critical regressions.
Waivers require explicit approval and expiration.
Sampled production traces can be promoted into eval datasets after privacy review.
Eval results are linked to prompt/model/tool/parser versions.
```

Spreadsheet evals should use executable workbook fixtures, checking values, formulas, styles, intended output ranges, unintended changes, and cell/range citations. Meeting-minutes evals should score omissions, hallucinations, attendees, motions, votes, decisions, action owners, due dates, and timestamp-span correctness.

---

## 16. Security requirements

Treat all artifacts as untrusted input.

Minimum controls:

```text
tenant isolation
RBAC/ABAC
permission-filtered retrieval
encryption at rest and in transit
object storage versioning
short-lived per-run credentials
secrets manager
KMS/CMEK support where required
data residency and retention policies
private networking/private endpoints where required
sandboxed code and spreadsheet execution
macro blocking by default
formula injection detection
hidden sheet/row/comment prompt-injection checks
network egress controls for tools
PII/sensitive-data redaction for traces
rate and cost limits
audit export
incident-response runbooks
SBOM generation, image scanning, and image signing
Kubernetes admission policies and network policies in production
```

LLM-specific controls:

```text
server-side prompts
schema validation for model outputs
tool allowlists
prompt-injection detection
output validation
human approval for sensitive operations
anomaly/cost monitoring
```

---

## 17. Observability and audit

Trace the full path:

```text
upload -> parse -> index -> retrieve -> agent run -> tool calls -> citation verification -> approval -> output
```

Capture:

```text
workflow id
agent id/version
model id/version
prompt version
tool name/version
input/output hashes
latency
cost
retries
errors
validator scores
approval decisions
```

Use OpenTelemetry for distributed traces/metrics/logs and Langfuse or LangSmith for LLM/tool traces and prompt/model observability. Treat traces as sensitive data: apply access controls, redaction, retention limits, and tenant scoping.

---

## 18. Recommended repository structure

Start with a single Python package using vertical-slice modules and clean boundaries.

```text
exeboard/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── langgraph.json
├── alembic/
├── docs/
│   └── architecture.md
├── src/
│   └── exeboard/
│       ├── __init__.py
│       ├── config.py
│       ├── logging.py
│       ├── bootstrap.py
│       ├── api/
│       │   ├── main.py
│       │   ├── deps.py
│       │   ├── errors.py
│       │   └── v1.py
│       ├── workers/
│       │   ├── temporal_client.py
│       │   ├── registry.py
│       │   ├── ingestion_worker.py
│       │   ├── workflow_worker.py
│       │   └── agent_worker.py
│       ├── mcp_server/
│       │   ├── app.py
│       │   ├── tools.py
│       │   ├── resources.py
│       │   └── prompts.py
│       ├── shared/
│       │   ├── db/
│       │   ├── events/
│       │   ├── security/
│       │   ├── observability/
│       │   ├── schemas.py
│       │   └── errors.py
│       ├── integrations/
│       │   ├── llm_providers/
│       │   ├── vectorstores/
│       │   ├── embedding_models/
│       │   ├── temporal/
│       │   └── external_tools/
│       └── features/
│           ├── workspaces/
│           ├── artifacts/
│           ├── ingestion/
│           ├── knowledge/
│           ├── capabilities/
│           ├── workflows/
│           ├── agents/
│           ├── tools/
│           ├── provenance/
│           ├── approvals/
│           ├── outputs/
│           └── evals/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
│       ├── documents/
│       ├── spreadsheets/
│       ├── transcripts/
│       └── adversarial/
├── scripts/
└── infra/
    ├── compose.yaml
    ├── docker/
    ├── k8s/
    └── terraform/
```

### Feature module shape

```text
features/artifacts/
  router.py
  schemas.py
  models.py
  service.py
  repository.py
  temporal/
    workflows.py
    activities.py
  tests/
```

### LangGraph configuration

```json
{
  "dependencies": ["."],
  "graphs": {
    "goal_router": "./src/exeboard/features/agents/graphs/goal_router.py:graph",
    "document_qa": "./src/exeboard/features/knowledge/graphs/document_qa.py:graph",
    "workflow_runner": "./src/exeboard/features/workflows/graphs/runner.py:graph"
  },
  "env": "./.env"
}
```

### When to split into a monorepo

Start with `src/exeboard`. Move to `apps/*` and `packages/*` only when boundaries harden.

Future layout:

```text
apps/
  api/
  temporal-workers/
  mcp-server/
  web/
packages/
  exeboard-core/
  exeboard-ai/
  exeboard-tools/
  exeboard-integrations/
```

---

## 19. Implementation phases

Important distinction:

```text
Phase 1 is the technical foundation.
The first shippable v0 should include Phases 1-2 plus minimal durable execution, citations, audit, and review gates.
Board-grade minutes, financial summaries, or external-facing outputs should not be marketed as production-ready until durable workflow execution and approval checkpoints are in place.
```

### Phase 1: Platform foundation

Build:

```text
FastAPI app
Postgres schema
object storage abstraction
artifact upload/versioning
basic parsing pipeline
audit events
OpenTelemetry/Langfuse tracing
capability registry skeleton
tool registry skeleton
minimal Temporal worker/client scaffold
idempotency key conventions
```

Ship:

```text
Upload/manage artifacts
Parse documents/transcripts/simple spreadsheets
Store provenance records
Run basic document Q&A with citations
```

### Phase 2: Workflow runner

Build:

```text
WorkflowTemplate and WorkflowRun models
WorkflowPlan and WorkflowStep models
custom/ad hoc workflow plan support
LangGraph goal router
first reusable capabilities
human approval records
GeneratedOutput model
citation verification step
minimal Temporal workflow for user-facing runs
```

Ship:

```text
Run selected artifacts + user goal
Generate cited outputs
Store workflow/agent/tool audit trail
```

### Phase 3: Initial workflow templates

Build templates:

```text
Board brief
Meeting minutes
Financial spreadsheet summary
Document Q&A
```

These should compose existing capabilities rather than hardcode one flow.

### Phase 4: Production durable execution hardening

Expand:

```text
complete Temporal workflow coverage
idempotent activities for all side effects
retry/timeouts/heartbeats
approval checkpoints for high-risk workflows
background workers by task queue
dead-letter/error handling
load testing and worker tuning
```

### Phase 5: Hardening and evals

Add:

```text
custom eval datasets
Ragas/DeepEval integration
adversarial artifact tests
spreadsheet benchmark fixtures
meeting-minutes quality metrics
security controls
Kubernetes deployment
```

---

## 20. Primary references

### Agent/workflow orchestration

- LangGraph persistence and stateful graphs: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph application structure: https://docs.langchain.com/oss/python/langgraph/application-structure
- Temporal Python workers: https://docs.temporal.io/develop/python/workers/run-worker-process
- Temporal production checklist: https://docs.temporal.io/self-hosted-guide/production-checklist
- Temporal worker best practices: https://docs.temporal.io/best-practices/worker
- OpenAI agents orchestration: https://developers.openai.com/api/docs/guides/agents/orchestration
- OpenAI guardrails and human review: https://developers.openai.com/api/docs/guides/agents/guardrails-approvals
- Microsoft Magentic orchestration: https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/magentic
- Orchestrating Agents and Data for Enterprise: https://arxiv.org/html/2504.08148v1

### Provenance, RAG, and evaluation

- PROV-AGENT: https://arxiv.org/html/2508.02866v1
- LlamaIndex citation workflow: https://developers.llamaindex.ai/python/examples/workflow/citation_query_engine/
- LlamaIndex evaluation docs: https://developers.llamaindex.ai/python/framework/module_guides/evaluating/
- RAGAS: https://aclanthology.org/anthology-files/anthology-files/pdf/eacl/2024.eacl-demo.16.pdf
- CRAG benchmark: https://proceedings.neurips.cc/paper_files/paper/2024/file/1435d2d0fca85a84d83ddcb754f58c29-Paper-Datasets_and_Benchmarks_Track.pdf
- FRAMES: https://aclanthology.org/2025.naacl-long.243.pdf
- GaRAGe: https://aclanthology.org/2025.findings-acl.875.pdf

### Document intelligence and security

- Azure multimodal content processing architecture: https://learn.microsoft.com/en-us/azure/architecture/ai-ml/idea/multi-modal-content-processing
- AWS intelligent document processing guidance: https://aws.amazon.com/solutions/guidance/intelligent-document-processing-on-aws/
- AWS regulated document pipeline sample: https://github.com/aws-samples/document-processing-pipeline-for-regulated-industries
- Google Document AI security: https://docs.cloud.google.com/document-ai/docs/security
- OWASP LLM Verification Standard: https://owasp.org/www-project-llm-verification-standard/LLMSVS-v1.0-en.html
- Kubernetes multi-tenancy: https://kubernetes.io/docs/concepts/security/multi-tenancy/
- Kubernetes RBAC good practices: https://kubernetes.io/docs/concepts/security/rbac-good-practices/
- Kubernetes auditing: https://kubernetes.io/docs/tasks/debug/debug-cluster/audit/
- OpenTelemetry observability primer: https://opentelemetry.io/docs/concepts/observability-primer/

### Spreadsheets and meetings

- SpreadsheetBench: https://spreadsheetbench.github.io/
- Meeting-summary evaluation paper: https://aclanthology.org/2025.coling-industry.48.pdf
- Re-FRAME/SCOPE meeting summarization: https://aclanthology.org/2025.findings-emnlp.1094v1.pdf

### Project structure

- FastAPI bigger applications: https://fastapi.tiangolo.com/tutorial/bigger-applications/
- FastAPI best practices: https://github.com/zhanymkanov/fastapi-best-practices
- PyPA src layout: https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
- uv workspaces: https://docs.astral.sh/uv/concepts/projects/workspaces/
- MCP tools specification: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- MCP server concepts: https://modelcontextprotocol.io/docs/learn/server-concepts

---

## 21. Final decision

Build Exeboard as a **workflow-first, evidence-grounded, reusable multi-agent workflow platform**.

The first product milestone is not a board-pack generator, minutes generator, spreadsheet summarizer, or document Q&A tool. It is a runtime that can:

```text
create or load a workflow,
accept selected artifacts and a user goal,
resolve reusable agents/capabilities/tools,
execute bounded workflow steps,
show what each agent did,
verify citations/evidence,
route risky steps for approval,
produce reviewable outputs,
and preserve a complete audit trail.
```

Board briefs, meeting minutes, spreadsheet summaries, document Q&A, compliance checks, and future custom workflows are reusable templates on top of this runtime. The durable asset is the governed agent workflow platform.
