# Research: Exeboard domain-driven / vertical-slice file organization for enterprise agent workflow products

## Summary
Exeboard should use a **modular monolith organized by product/domain capability**, with **vertical slices inside each bounded context**, rather than a top-level Clean Architecture layout split into `domain/application/infrastructure` across the whole repo. Keep Clean Architecture's dependency rule locally inside each module where it buys testability and adapter isolation, but make the primary navigation path match product iteration: workflow templates, runs, registries, tools, knowledge/RAG, artifacts, provenance, approvals, audit, and evals.

## Findings
1. **Enterprise agent platforms converge on the same control-plane domains Exeboard needs.** Google frames an enterprise agent platform around Build, Scale, Govern, and Optimize, with explicit components for Agent Registry, Agent Gateway, Governance Policies, RAG Engine, Vector Search, Agent Evaluation, observability, and trace viewing. Exeboard's folders should therefore model these as first-class product domains, not hidden infrastructure utilities. [Source](https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview)

2. **Registries should be independent bounded contexts, not config folders.** AWS Agent Registry is a centralized catalog for MCP servers, tools, agents, skills, and custom resources, with publishing, approval/curation, semantic + keyword discovery, and record metadata. Exeboard should separate `agent-registry`, `capability-registry`, and `tool-registry` because their records, approvals, lifecycle states, and search semantics will evolve separately. [Source](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry.html)

3. **Tool governance belongs at the boundary, outside agent code.** AWS AgentCore Policy intercepts agent-to-tool requests at the gateway, evaluates deterministic policies, supports fine-grained conditions on identity and tool inputs, and logs enforcement decisions. Exeboard should put tool authorization, approval requirements, credential brokering, and policy decisions in `tools`/`governance` modules and call them from workflow/runtime slices instead of embedding checks in each agent. [Source](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html)

4. **Workflows and agents are different abstractions and should not be merged.** Microsoft Agent Framework distinguishes dynamic LLM-driven agents from predefined workflows that explicitly model business processes, human interactions, external integrations, checkpointing, and multi-agent orchestration. Exeboard should keep `workflows` as the owner of templates, versions, graph definitions, runs, checkpoints, and run state, while `agent-registry` owns agent definitions and versions. [Source](https://learn.microsoft.com/en-us/agent-framework/workflows/)

5. **Approvals need durable workflow state and a domain of their own.** Microsoft's HITL workflow mechanism emits request events, waits for external responses, supports tool approval requests, and saves pending requests in checkpoints; LangGraph similarly uses checkpoints for human inspection, approval, replay, memory, and fault tolerance. Exeboard should model approvals as persistent records linked to workflow runs, tool calls, policy evaluations, and audit events, not as transient UI modals. [Microsoft](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop), [LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence)

6. **Provenance, audit, and tracing are related but should be separated.** OpenAI Agents SDK tracing captures workflow runs, agent spans, LLM generations, tool calls, guardrails, handoffs, and custom spans; AWS Observability exposes production traces, metrics, spans, logs, token usage, latency, and error rates. Provenance should capture causal lineage of artifacts and evidence, audit should capture compliance/security decisions, and tracing should capture operational telemetry; all three should share correlation IDs. [OpenAI](https://openai.github.io/openai-agents-python/tracing/), [AWS](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)

7. **RAG/knowledge needs source-level provenance, not only vector indexes.** LlamaIndex's citation workflow explicitly retrieves nodes, creates numbered citation nodes, and synthesizes answers with inline source citations. TrustGraph separates extraction provenance from query-time explainability and links answers back through retrieval traces to chunks, pages, and source documents. Exeboard should keep ingestion, chunks, embeddings, retrieval traces, citations, and evidence ledgers in `knowledge`, with durable links into `provenance`. [LlamaIndex](https://developers.llamaindex.ai/python/examples/workflow/citation_query_engine/), [TrustGraph](https://docs.trustgraph.ai/overview/explainability.html)

8. **Use W3C PROV-style concepts for lineage.** PROV-O gives interoperable primitives such as `Entity`, `Activity`, `Agent`, `used`, `wasGeneratedBy`, `wasDerivedFrom`, and attribution/association relationships. Exeboard can map workflow runs, agent steps, tool calls, source chunks, generated artifacts, approvals, and eval results to these primitives without adopting RDF everywhere. [Source](https://www.w3.org/TR/2013/PR-prov-o-20130312/)

9. **Clean Architecture is useful as a dependency rule, but poor as the top-level product folder structure.** Clean Architecture's value is inward dependencies, framework/database independence, and testability. Jason Taylor's template still organizes features as vertical slices inside layers, which shows the two ideas can be combined. For Exeboard, top-level folders should scream product domains; each domain can keep local `domain`, `ports`, and `infra` folders only where the slice needs adapter isolation. [Clean Coder](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture), [Jason Taylor](https://cleanarchitecture.jasontaylor.dev/docs/architecture/)

10. **Vertical slices improve product iteration inside modules.** Modular-monolith guidance distinguishes macro architecture (module boundaries, APIs, data isolation) from micro architecture (how code is organized inside a module), and notes that vertical slices group request, handler, validation, and data access for a single use case. This maps well to Exeboard because most changes will add or change product use cases such as `publish-template`, `approve-tool-call`, `run-eval`, or `attach-artifact`. [Source](https://www.milanjovanovic.tech/blog/where-vertical-slices-fit-inside-the-modular-monolith-architecture)

11. **AgentOps evidence supports separate evals, prompt/templates, registries, and deployment concerns.** CNOE's AgentOps guide defines Agent Registry, Prompt Library, and MCP Registry with provenance; it also describes routing/tool-match evaluators, dataset-driven evals, Langfuse tracing, Helm deployment, independent agent services, and sanity checks. Exeboard should keep eval datasets/scorers and deployment/runtime concerns separate from core workflow authoring. [Source](https://github.com/cnoe-io/ai-platform-engineering/blob/main/docs/docs/agent-ops/index.md)

12. **Recommended architecture decision: modular domain slices with local clean boundaries.** Use top-level `modules/<bounded-context>` folders for product domains; inside each module, organize by `features/<use-case>` first, with shared local `domain`, `ports`, `infra`, `events`, and `ui` only as needed. Avoid a global `services/`, `utils/`, or `repositories/` dumping ground; allow duplication until a stable domain concept emerges.

### Clean Architecture vs feature modules for Exeboard

| Question | Pure top-level Clean Architecture | Domain modules + vertical slices | Exeboard recommendation |
|---|---|---|---|
| Primary navigation | `domain/`, `application/`, `infrastructure/`, `web/` | `modules/workflows/features/start-run`, etc. | Prefer module/slice navigation because product changes are use-case driven. |
| Dependency safety | Strong, explicit inward dependencies | Needs module boundary rules and lint/import checks | Keep local ports/adapters and enforce imports. |
| Discoverability | Use-case code may be scattered across layers | Request/schema/handler/policy/test are colocated | Prefer slices for faster iteration. |
| Shared domain models | Easy to centralize | Can drift or duplicate if unmanaged | Use `shared-kernel` sparingly; promote only stable concepts. |
| Enterprise integrations | Often placed in global infrastructure | Adapters live beside owning module or platform boundary | Put external adapters under owning module `infra/adapters`. |
| Scaling to services later | Layer split does not equal deployable boundary | Modules can become services more easily | Use bounded-context modules as future service seams. |

## Exeboard-specific proposed folder tree

```txt
exeboard/
  apps/
    web/                              # Next/React UI shell; imports module UI surfaces only
    api/                              # HTTP/RPC entrypoint, auth middleware, DI, OpenAPI
    worker/                           # background jobs: runs, ingestion, evals, trace export
    cli/                              # admin/dev commands

  src/
    platform/                         # cross-cutting runtime, not business features
      auth/                           # users, orgs, RBAC/ABAC primitives, auth middleware
      config/
      database/                       # migrations bootstrap, transaction helpers
      event-bus/                      # domain/integration event dispatch
      observability/                  # OpenTelemetry, logs, metrics, trace exporters
      queue/
      tenancy/
      idempotency/
      errors/

    shared-kernel/                    # stable ubiquitous language only
      ids/                            # RunId, AgentId, ToolId, ArtifactId, TenantId
      time/
      result/
      pagination/
      money-or-usage/                 # only if billing/usage becomes core

    modules/
      workflows/                      # templates, definitions, versions, runs, checkpoints
        public-api/
          workflow-commands.ts
          workflow-queries.ts
          workflow-events.ts
        domain/
          workflow-template.ts
          workflow-version.ts
          workflow-run.ts
          workflow-step.ts
          checkpoint.ts
        features/
          create-template/
            command.ts
            handler.ts
            schema.ts
            policy.ts
            test.ts
          publish-template/
          version-template/
          start-run/
          pause-run/
          resume-run/
          cancel-run/
          replay-run-from-checkpoint/
          list-run-timeline/
        infra/
          persistence/
          graph-runtime/              # LangGraph/MAF/custom workflow adapters
          schedulers/
        ui/
          template-builder/
          run-console/

      capability-registry/            # discoverable business capabilities/skills
        domain/
          capability.ts
          capability-version.ts
          compatibility.ts
        features/
          register-capability/
          map-capability-to-agent/
          map-capability-to-tool/
          search-capabilities/
          deprecate-capability/
        infra/search/
        public-api/

      agent-registry/                 # agents, versions, configs, manifests, ownership
        domain/
          agent.ts
          agent-version.ts
          agent-manifest.ts
          agent-runtime-binding.ts
        features/
          register-agent/
          publish-agent-version/
          approve-agent/
          discover-agent/
          bind-agent-to-runtime/
          deprecate-agent/
        infra/
          manifest-validators/        # A2A/MCP/custom schema validation
          runtime-catalog-clients/
        public-api/

      tools/                          # tool catalog + execution gateway + credentials
        domain/
          tool.ts
          tool-version.ts
          tool-call.ts
          tool-policy.ts
          credential-binding.ts
        features/
          register-tool/
          import-openapi-tool/
          import-mcp-server/
          simulate-tool-call/
          request-tool-call/
          authorize-tool-call/
          execute-tool-call/
          rotate-tool-credential/
        infra/
          mcp/
          openapi/
          gateways/
          secret-stores/
        public-api/

      knowledge/                       # enterprise knowledge/RAG
        domain/
          source.ts
          document.ts
          chunk.ts
          embedding-index.ts
          retrieval.ts
          citation.ts
          evidence-ledger.ts
        features/
          connect-source/
          ingest-source/
          chunk-document/
          build-index/
          retrieve-context/
          generate-cited-answer/
          refresh-stale-knowledge/
          redact-source/
        infra/
          loaders/
          vector-stores/
          graph-stores/
          rerankers/
        public-api/

      artifacts/                       # generated files, reports, plans, patches, exports
        domain/
          artifact.ts
          artifact-version.ts
          artifact-hash.ts
          artifact-link.ts
        features/
          create-artifact/
          attach-artifact-to-run/
          version-artifact/
          sign-artifact/
          export-artifact/
        infra/object-store/
        public-api/

      provenance/                      # causal lineage / evidence graph
        domain/
          prov-entity.ts              # maps to generated artifact, source chunk, eval result
          prov-activity.ts            # workflow run, step, tool call, model call
          prov-agent.ts               # user, agent, service account
          lineage-edge.ts             # used, generatedBy, derivedFrom, attributedTo
        features/
          record-lineage-event/
          link-artifact-to-sources/
          link-answer-to-citations/
          query-lineage/
          export-provenance-bundle/
        infra/lineage-store/
        public-api/

      approvals/                       # human-in-the-loop and policy-gated work
        domain/
          approval-request.ts
          approval-decision.ts
          approval-policy.ts
          approver.ts
        features/
          request-approval/
          decide-approval/
          expire-approval/
          escalate-approval/
          list-pending-approvals/
        infra/notifications/
        ui/inbox/
        public-api/

      audit/                           # compliance/security event log
        domain/
          audit-event.ts
          audit-subject.ts
          retention-policy.ts
        features/
          record-audit-event/
          search-audit-log/
          export-audit-log/
          apply-retention-policy/
        infra/append-only-store/
        public-api/

      evals/                           # quality gates, datasets, scorers, experiments
        domain/
          dataset.ts
          eval-case.ts
          scorer.ts
          eval-run.ts
          score.ts
        features/
          create-dataset/
          run-eval-suite/
          score-routing/
          score-tool-use/
          score-groundedness/
          compare-agent-version/
          promote-version-if-passing/
        infra/
          trace-readers/
          evaluator-providers/
        public-api/

      policies/                        # optional shared policy authoring module
        domain/
          policy.ts
          policy-decision.ts
          policy-simulation.ts
        features/
          author-policy/
          simulate-policy/
          publish-policy/
          evaluate-policy/
        infra/engines/                 # Cedar/OPA/custom adapters
        public-api/

    contracts/                         # external API schemas generated from module public APIs
      openapi/
      events/
      mcp/
      a2a/

    composition/                       # wires module public APIs together; no business rules
      api-routes.ts
      worker-jobs.ts
      module-registry.ts

  tests/
    architecture/                      # import-boundary tests, module dependency rules
    integration/
    e2e/
    fixtures/

  evals/                               # checked-in datasets/prompt suites; product data not code
    datasets/
    scorers/
    golden-traces/

  docs/
    architecture/
      adr/
      c4/
      domain-map.md
    runbooks/
```

### Boundary rules for this tree

1. `apps/*` may call only module `public-api`, `composition`, and `platform` APIs.
2. `modules/*/features/*` may use its module `domain`, local `infra` through ports, `shared-kernel`, and other modules only through `public-api`.
3. `modules/*/domain` must not import `infra`, UI, queues, HTTP, SDK clients, or database libraries.
4. `platform/*` must not know Exeboard product concepts such as `WorkflowRun` or `ToolCall`.
5. `provenance`, `audit`, and `observability` events should all share `tenantId`, `runId`, `traceId`, `spanId`, `artifactId`, and `actorId`, but keep separate write models.
6. Add architecture tests to prevent cross-module imports except through `public-api`.

## Sources
- Kept: Google Gemini Enterprise Agent Platform overview (https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview) — current enterprise-agent platform taxonomy: build, scale, govern, optimize.
- Kept: AWS Agent Registry (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry.html) — primary evidence for registry records, curation, approvals, and discovery.
- Kept: AWS AgentCore Policy (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy.html) — primary evidence for deterministic tool-call policy enforcement and audit logging.
- Kept: AWS AgentCore Observability (https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) — primary evidence for production traces, spans, metrics, and logs.
- Kept: Microsoft Agent Framework Workflows (https://learn.microsoft.com/en-us/agent-framework/workflows/) — clear distinction between agents and explicit workflows.
- Kept: Microsoft Agent Framework HITL (https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop) — concrete request/response and tool-approval pattern.
- Kept: LangGraph persistence (https://docs.langchain.com/oss/python/langgraph/persistence) — checkpoints, replay, memory, fault tolerance, and HITL state.
- Kept: OpenAI Agents SDK tracing (https://openai.github.io/openai-agents-python/tracing/) — span taxonomy for model calls, tools, guardrails, handoffs.
- Kept: CNOE AgentOps guide (https://github.com/cnoe-io/ai-platform-engineering/blob/main/docs/docs/agent-ops/index.md) — practical AgentOps structure: registries, prompt library, evals, tracing, deployment.
- Kept: LlamaIndex citation workflow (https://developers.llamaindex.ai/python/examples/workflow/citation_query_engine/) — RAG citation/source-node implementation.
- Kept: TrustGraph Explainability (https://docs.trustgraph.ai/overview/explainability.html) — extraction provenance and query-time explainability model.
- Kept: W3C PROV-O (https://www.w3.org/TR/2013/PR-prov-o-20130312/) — interoperable provenance concepts.
- Kept: Clean Architecture by Robert C. Martin (https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture) — dependency rule and rationale.
- Kept: Jason Taylor Clean Architecture overview (https://cleanarchitecture.jasontaylor.dev/docs/architecture/) — pragmatic Clean Architecture with vertical feature organization.
- Kept: Milan Jovanovic on vertical slices in modular monoliths (https://www.milanjovanovic.tech/blog/where-vertical-slices-fit-inside-the-modular-monolith-architecture) — macro modules vs micro vertical slices.
- Dropped: Medium/SEO posts on generic vertical slices — redundant with stronger modular-monolith and primary Clean Architecture sources.
- Dropped: Vendor marketing pages for Credal/Waxell/AURA/AgentOven — useful directional confirmation but less primary than Google/AWS/Microsoft docs.
- Dropped: Small GitHub proof-of-concept repos for agents — weaker evidence than CNOE AgentOps and official platform docs.

## Gaps
- I could not verify the current Exeboard codebase shape from expected root files (`README.md`, `package.json`, `pyproject.toml` were not present at the checked paths), so the tree is a target architecture rather than a diff against current code.
- The exact language/framework conventions should be adapted once the implementation stack is confirmed.
- Next steps: create ADRs for module boundaries, add import-boundary tests, and pilot the pattern by implementing one full slice such as `workflows/start-run` plus linked `approvals/request-approval`, `tools/authorize-tool-call`, `provenance/record-lineage-event`, and `audit/record-audit-event`.
