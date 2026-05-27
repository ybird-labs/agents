# Research: academic and framework evidence for a reusable multi-agent board/company intelligence platform

## Summary
Build the platform as a compound-AI system: deterministic workflow/state orchestration around specialized agents, enterprise data/tool registries, explicit provenance, and continuous evals rather than a single autonomous “super-agent.” The strongest current evidence supports graph/stateful orchestration (LangGraph, Microsoft Magentic/AutoGen, OpenAI Agents), RAG with component-level evaluation and citations, human review at planning/tool-execution boundaries, and domain-specific eval suites for board workflows such as spreadsheets and minutes. Confidence is high for architectural patterns and eval needs; lower for general-purpose agent reliability on complex spreadsheet/meeting tasks because benchmarks show these remain hard.

## Findings
1. **Use stateful graph/workflow orchestration, not unbounded chat loops.** LangGraph’s persistence model checkpoints graph state at each step and enables human-in-the-loop inspection/approval, memory, time travel/debugging, and fault tolerance—features directly relevant to reusable board/company intelligence workflows. [LangGraph persistence docs](https://docs.langchain.com/oss/python/langgraph/persistence)

2. **Model the enterprise platform as a compound-AI architecture with registries and planners.** A 2025 enterprise blueprint proposes agent registries, data registries, task/data planners, task coordinators, budgets/QoS, streams, and sessions to integrate proprietary APIs/data while optimizing accuracy, latency, and cost. This maps well to board/company intelligence: data connectors become registered sources; analysis/reporting skills become agents; sessions represent board packs, companies, or meeting workflows. [Orchestrating Agents and Data for Enterprise](https://arxiv.org/html/2504.08148v1)

3. **Adopt manager/specialist orchestration only where tasks are open-ended.** Microsoft’s Magentic orchestration uses a manager agent to plan, select specialists, track progress, detect stalls, replan, and optionally request human plan review; the docs warn it is best for complex tasks where the path is not known and simpler group/chat workflows may be preferable otherwise. [Microsoft Magentic orchestration docs](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/magentic)

4. **Design human-in-the-loop as a first-class runtime primitive.** OpenAI’s Agents guidance separates guardrails (automatic checks) from human review (pause for approval/rejection), while Microsoft Magentic supports plan review with approve/revise responses. Use HITL for sensitive actions: publishing board outputs, modifying spreadsheets, sending emails, retrieving privileged data, or accepting uncertain claims. [OpenAI guardrails/human review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals), [Microsoft Magentic plan review](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/magentic)

5. **Keep orchestration traces and provenance separate but linked.** PROV-AGENT extends W3C PROV for AI-agent workflows by recording agents, tools, prompts, model invocations, responses, decisions, telemetry, and downstream data lineage. For board intelligence, this supports “why did the system say this?”, “which source caused this claim?”, and “which downstream outputs are affected by a bad extraction?” [PROV-AGENT](https://arxiv.org/html/2508.02866v1)

6. **Require citation-grounded RAG, not generic summaries.** LlamaIndex’s citation workflow explicitly indexes documents, retrieves source nodes, attaches citations, and synthesizes answers from cited nodes; its eval docs distinguish response quality from retrieval quality. This is directly applicable to board packs, diligence rooms, KPI memos, contracts, and meeting materials. [LlamaIndex inline citations](https://developers.llamaindex.ai/python/examples/workflow/citation_query_engine/), [LlamaIndex evaluating docs](https://developers.llamaindex.ai/python/framework/module_guides/evaluating/)

7. **Evaluate RAG at both component and end-to-end levels.** RAGAS provides reference-free metrics for RAG pipelines; CRAG/Comprehensive RAG Benchmark tests factual QA with web/KG-like APIs and reports that even advanced systems struggle with fully trustworthy QA; newer datasets such as FRAMES and GaRAGe focus on factuality, retrieval, reasoning, and grounding annotations. Use these patterns to create company-specific gold sets. [RAGAS paper](https://aclanthology.org/anthology-files/anthology-files/pdf/eacl/2024.eacl-demo.16.pdf), [CRAG NeurIPS 2024](https://proceedings.neurips.cc/paper_files/paper/2024/file/1435d2d0fca85a84d83ddcb754f58c29-Paper-Datasets_and_Benchmarks_Track.pdf), [FRAMES](https://aclanthology.org/2025.naacl-long.243.pdf), [GaRAGe](https://aclanthology.org/2025.findings-acl.875.pdf)

8. **Spreadsheet workflows need specialized agents, sandboxing, and exact-file evals.** SpreadsheetBench contains real-world spreadsheet manipulation tasks with online-judge-style evaluation; SpreadsheetBench 2 focuses on end-to-end business workflows such as financial modeling, debugging, and visualization. Reported 2026 top overall accuracy for SpreadsheetBench 2 is still only 34.89%, signaling that board/finance spreadsheet automation should default to human review and deterministic validation. [SpreadsheetBench](https://spreadsheetbench.github.io/)

9. **Meeting-minutes workflows need fact/error-type evaluation.** Recent meeting summarization work evaluates omissions, hallucinations, incoherence, irrelevance, structure, and language quality; newer approaches reframe meeting summaries around extracted salient facts and personalized outlines. For board minutes, evaluate action items, decisions, attendees, owners, dates, and cited transcript spans rather than only ROUGE-style similarity. [Is my Meeting Summary Good?](https://aclanthology.org/2025.coling-industry.48.pdf), [Re-FRAME/SCOPE](https://aclanthology.org/2025.findings-emnlp.1094v1.pdf)

10. **Recommendation: implement platform primitives before product-specific agents.** Prioritize: (a) source/document registry, (b) agent/tool registry with permissions, (c) workflow state/checkpoints, (d) provenance graph and citation store, (e) HITL gates, (f) eval harness with regression datasets, and (g) sandboxed spreadsheet/meeting processors. Then add reusable agents: company profile, board-pack QA, KPI variance analyst, minutes/action extractor, spreadsheet auditor, and citation verifier.

## Sources
- Kept: LangGraph Persistence docs (https://docs.langchain.com/oss/python/langgraph/persistence) — official evidence for checkpointing, resume, HITL, memory, time travel, and fault tolerance.
- Kept: OpenAI Orchestration and Handoffs (https://developers.openai.com/api/docs/guides/agents/orchestration) — official patterns for handoffs vs agents-as-tools.
- Kept: OpenAI Guardrails and Human Review (https://developers.openai.com/api/docs/guides/agents/guardrails-approvals) — official guidance for guardrails plus approval pauses.
- Kept: Microsoft Magentic Orchestration (https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/magentic) — official manager/specialist multi-agent pattern with plan review and stall handling.
- Kept: Orchestrating Agents and Data for Enterprise (https://arxiv.org/html/2504.08148v1) — credible architecture reference for enterprise compound-AI systems.
- Kept: PROV-AGENT (https://arxiv.org/html/2508.02866v1) — primary academic evidence for agentic provenance/lineage.
- Kept: LlamaIndex Inline Citations (https://developers.llamaindex.ai/python/examples/workflow/citation_query_engine/) — official implementation pattern for citation-grounded RAG.
- Kept: LlamaIndex Evaluating (https://developers.llamaindex.ai/python/framework/module_guides/evaluating/) — official evaluation categories for RAG/agents.
- Kept: RAGAS (https://aclanthology.org/anthology-files/anthology-files/pdf/eacl/2024.eacl-demo.16.pdf) — academic RAG evaluation framework.
- Kept: CRAG (https://proceedings.neurips.cc/paper_files/paper/2024/file/1435d2d0fca85a84d83ddcb754f58c29-Paper-Datasets_and_Benchmarks_Track.pdf) — NeurIPS benchmark for factual RAG.
- Kept: FRAMES (https://aclanthology.org/2025.naacl-long.243.pdf) and GaRAGe (https://aclanthology.org/2025.findings-acl.875.pdf) — recent RAG factuality/grounding eval datasets.
- Kept: SpreadsheetBench (https://spreadsheetbench.github.io/) — direct benchmark for spreadsheet manipulation and business spreadsheet workflows.
- Kept: Meeting summary evaluation papers (https://aclanthology.org/2025.coling-industry.48.pdf, https://aclanthology.org/2025.findings-emnlp.1094v1.pdf) — direct evidence for minutes quality dimensions and fact-based summarization.
- Dropped: CrewAI marketing page — useful product signal but less authoritative than official technical docs/benchmarks.
- Dropped: arXiv papers dated 2026 in search results — possibly relevant but beyond current date and less stable for this brief.
- Dropped: SEO/general “AI agents for enterprise” commentary — lower evidentiary value than academic papers and official docs.

## Gaps
- **End-to-end board/company intelligence benchmarks are not established.** Next step: build internal eval sets from real board packs, minutes, spreadsheets, and company filings with expert-labeled answers and citations.
- **Agent orchestration benchmarks are still emerging and not directly board-specific.** Treat multi-agent designs as engineering hypotheses validated by task-level evals, latency, cost, and human acceptance.
- **Spreadsheet and meeting automation remain reliability risks.** Use sandboxed execution, exact-output checks, diff previews, and mandatory human approval for financial or governance-critical outputs.
- **Provenance standards for LLM agents are promising but early.** PROV-AGENT is compelling but should be implemented pragmatically as an internal trace/provenance schema mapped to W3C PROV concepts.

## Confidence
- **High:** Need for stateful orchestration, HITL gates, citations/provenance, and RAG/component evals.
- **Medium:** Choice of a specific framework; LangGraph, OpenAI Agents SDK, and Microsoft Agent Framework all support relevant patterns, but ecosystem maturity and team fit should drive selection.
- **Medium-low:** Fully autonomous spreadsheet/minutes workflows; benchmarks show rapid progress but persistent reliability gaps.
