/**
 * @process project/summary-agent-slice0-observability-boundary
 * @description Implement Slice 0 from the updated evidence-backed summary-agent plan: grounding observability and LLM-boundary guardrails before live-model measurement.
 * @process methodologies/atdd-tdd/atdd-tdd
 * @process tdd-quality-convergence
 * @process methodologies/planning-with-files/planning-orchestrator
 * @process specializations/ai-agents-conversational/agent-evaluation-framework
 * @process specializations/ai-agents-conversational/advanced-rag-patterns
 */

import { defineTask } from '@a5c-ai/babysitter-sdk';

const PROJECT_ROOT = '/Users/jeancarlobarrios/Developing/exeboard/ai';

export const preflightInventory = defineTask('slice0-observability-preflight-inventory', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Preflight inventory for Slice 0 observability and LLM-boundary guardrails',
  agent: {
    name: 'scout',
    prompt: {
      role: 'Codebase reconnaissance specialist for Python document-intelligence components',
      task: 'Inspect the current document-intelligence implementation and produce the smallest safe TDD plan for Slice 0: grounding observability plus LLM-boundary guardrails.',
      context: args,
      instructions: [
        'Work from the current repository; do not edit files in this task.',
        'Check branch/remotes/status and identify whether the working tree is dirty. Do not perform destructive git operations.',
        'Read docs/document-intelligence/summary-agent-improved-plan.md, especially Slice 0.',
        'Read deep-research/local-implementation-gap-analysis.md, deep-research/llm-boundary-plan-review.md, deep-research/summary-model-plan-review.md, and deep-research/validation-grounding-plan-review.md.',
        'Inspect packages/exeboard-ai/src/exeboard_ai/document_intelligence/summarization/{models.py,ports.py,chunk_summarizer.py,pipeline.py} and validation/aggregate_validator.py.',
        'Inspect tests/unit/document_intelligence and tests/integration/document_intelligence for current fake-generator and pipeline patterns.',
        'Produce a focused TDD plan for: SummarizationRunResult, minimal GroundingRunReport, dropped-claim records/conservation, zero-valid-claim result behavior, StructuredGenerationError taxonomy, and import-boundary tests.',
        'Explicitly exclude canonical anchoring, live provider adapter, replay, judge, app/API/UI, Docling, OCR, DB, and broad validator rewrite.',
        'List proposed files/tests, risks, and acceptance criteria.'
      ],
      outputFormat: 'JSON with summary, dirtyTreeCaveat, proposedTests, proposedFiles, risks, acceptanceCriteria, sequencing'
    },
    outputSchema: {
      type: 'object',
      required: ['summary', 'proposedTests', 'proposedFiles', 'risks', 'acceptanceCriteria', 'sequencing'],
      properties: {
        summary: { type: 'string' },
        dirtyTreeCaveat: { type: 'string' },
        proposedTests: { type: 'array', items: { type: 'string' } },
        proposedFiles: { type: 'array', items: { type: 'string' } },
        risks: { type: 'array', items: { type: 'string' } },
        acceptanceCriteria: { type: 'array', items: { type: 'string' } },
        sequencing: { type: 'array', items: { type: 'string' } }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

export const implementSlice0 = defineTask('implement-slice0-observability-boundary', (args, taskCtx) => ({
  kind: 'agent',
  title: 'TDD implement Slice 0 grounding observability and LLM-boundary guardrails',
  agent: {
    name: 'worker',
    prompt: {
      role: 'Senior Python TDD engineer for evidence-backed document summarization',
      task: 'Implement only Slice 0 from the updated summary-agent plan: grounding observability plus LLM-boundary guardrails.',
      context: args,
      instructions: [
        'Use strict TDD: add/update focused behavior tests first, then minimal implementation.',
        'Implement SummarizationRunResult and minimal GroundingRunReport / DroppedClaimRecord models where they best fit the existing package boundaries.',
        'Track generated/proposed claims, evidence count if practical from generated payloads, assembly drops, citation-validation drops, quote-validation drops, valid claims, parser counters available from current DocumentIR/ParserRun warnings, and counts_by_error_code.',
        'Add/report conservation invariant: claims_proposed == claims_valid + len(drops). Multi-evidence generated claims should drop once with useful failure details if a single evidence fails.',
        'Do not implement canonical anchoring or change current exact-validity semantics in this slice. Do not accept normalized/fuzzy/page-scope matches as valid.',
        'Make zero-valid-claim outcomes explicit without fabricating a non-empty DocumentSummary. Prefer summary: None in SummarizationRunResult if that is the smallest safe API change.',
        'Add StructuredGenerationError, InvalidOutput, Unavailable, and RequestRejected to the provider-agnostic summarization port. Do not add provider SDKs or PydanticAI.',
        'Add an architecture/import-boundary test ensuring exeboard_ai does not import pydantic_ai, provider SDKs, or exeboard_integrations.',
        'Update docs only if needed to keep summary_pipeline/evaluation aligned with the new result/report behavior.',
        'Preserve existing MVP boundaries: no app/API/UI/DB/Temporal, no OCR, no Docling adapter, no replay cache, no judge, no live remote inference, no provider adapter.',
        'Run focused tests and report exact commands/results; if a check cannot run, explain why.'
      ],
      outputFormat: 'JSON with success, changedFiles, testsAddedOrUpdated, testsRun, summary, remainingRisks'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'changedFiles', 'testsAddedOrUpdated', 'testsRun', 'summary', 'remainingRisks'],
      properties: {
        success: { type: 'boolean' },
        changedFiles: { type: 'array', items: { type: 'string' } },
        testsAddedOrUpdated: { type: 'array', items: { type: 'string' } },
        testsRun: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' },
        remainingRisks: { type: 'array', items: { type: 'string' } }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

export const runFocusedQualityGates = defineTask('run-slice0-focused-quality-gates', (_args, taskCtx) => ({
  kind: 'shell',
  title: 'Run Slice 0 focused quality gates',
  shell: {
    command: 'uv run python scripts/check_workspace.py && uv run --package exeboard-ai --with pytest pytest tests/unit/document_intelligence tests/integration/document_intelligence && uv run --with pyright --with pytest pyright',
    cwd: PROJECT_ROOT
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

export const summaryModelReview = defineTask('slice0-summary-model-review', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Summary model expert review for Slice 0 observability',
  agent: {
    name: 'exeboard.document-summary-model-expert',
    prompt: {
      role: 'Evidence-backed summary schema and provenance reviewer',
      task: 'Review the implemented Slice 0 observability/result model changes.',
      context: args,
      instructions: [
        'Inspect the actual diff and relevant tests/docs.',
        'Check that SummarizationRunResult/GroundingRunReport represent generated proposals, drops, valid claims, and zero-valid outcomes honestly.',
        'Check that final summaries are not fabricated when no valid claims exist.',
        'Check no unsupported board-pack/schema/product expansion entered this slice.',
        'Return APPROVE, CHANGE, or REJECT. Put every required fix in blockers and/or requiredChanges; do not edit files.'
      ],
      outputFormat: 'JSON with verdict, blockers, requiredChanges, optionalFollowUps, summary'
    },
    outputSchema: reviewSchema()
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

export const llmBoundaryReview = defineTask('slice0-llm-boundary-review', (args, taskCtx) => ({
  kind: 'agent',
  title: 'LLM boundary expert review for Slice 0 guardrails',
  agent: {
    name: 'exeboard.agentic-llm-boundary-expert',
    prompt: {
      role: 'Provider-agnostic LLM boundary reviewer',
      task: 'Review Slice 0 LLM-boundary guardrails and error taxonomy.',
      context: args,
      instructions: [
        'Inspect the actual diff and relevant tests/docs.',
        'Check the StructuredGenerationError taxonomy is domain-owned and provider-agnostic.',
        'Check exeboard_ai has no provider SDK/PydanticAI/exeboard_integrations imports and no live inference path.',
        'Check tests enforce no silent remote inference/provider leakage assumptions relevant to this slice.',
        'Return APPROVE, CHANGE, or REJECT. Put every required fix in blockers and/or requiredChanges; do not edit files.'
      ],
      outputFormat: 'JSON with verdict, blockers, requiredChanges, optionalFollowUps, summary'
    },
    outputSchema: reviewSchema()
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

export const validationReview = defineTask('slice0-validation-grounding-review', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Validation expert review for Slice 0 grounding telemetry',
  agent: {
    name: 'exeboard.agentic-python-di-validation-expert',
    prompt: {
      role: 'Python document-intelligence validation reviewer',
      task: 'Review Slice 0 validation/drop reporting behavior.',
      context: args,
      instructions: [
        'Inspect the actual diff and relevant tests/docs.',
        'Check drops are represented rather than silently disappearing before reporting.',
        'Check conservation invariant and error-code accounting are deterministic.',
        'Check the slice did not accidentally implement or weaken canonical/fuzzy/page-scope validation semantics.',
        'Return APPROVE, CHANGE, or REJECT. Put every required fix in blockers and/or requiredChanges; do not edit files.'
      ],
      outputFormat: 'JSON with verdict, blockers, requiredChanges, optionalFollowUps, summary'
    },
    outputSchema: reviewSchema()
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

export const addressReviewBlockers = defineTask('address-slice0-review-blockers', (args, taskCtx) => ({
  kind: 'agent',
  title: 'Address blocking review feedback for Slice 0',
  agent: {
    name: 'worker',
    prompt: {
      role: 'Senior Python TDD engineer handling focused review feedback',
      task: 'Address only the blocking reviewer feedback for Slice 0 observability/boundary changes.',
      context: args,
      instructions: [
        'Make the smallest safe changes needed to resolve blockers.',
        'Use TDD for behavior changes: add/adjust tests first, then code.',
        'Do not expand scope into live providers, replay, judges, apps, UI, DB, Temporal, Docling, OCR, or canonical anchoring.',
        'Run focused tests if practical and report exact commands/results.'
      ],
      outputFormat: 'JSON with success, changedFiles, testsRun, summary, remainingRisks'
    },
    outputSchema: {
      type: 'object',
      required: ['success', 'changedFiles', 'testsRun', 'summary', 'remainingRisks'],
      properties: {
        success: { type: 'boolean' },
        changedFiles: { type: 'array', items: { type: 'string' } },
        testsRun: { type: 'array', items: { type: 'string' } },
        summary: { type: 'string' },
        remainingRisks: { type: 'array', items: { type: 'string' } }
      }
    }
  },
  io: {
    inputJsonPath: `tasks/${taskCtx.effectId}/input.json`,
    outputJsonPath: `tasks/${taskCtx.effectId}/output.json`
  }
}));

function reviewSchema() {
  return {
    type: 'object',
    required: ['verdict', 'blockers', 'requiredChanges', 'optionalFollowUps', 'summary'],
    properties: {
      verdict: { type: 'string', enum: ['APPROVE', 'CHANGE', 'REJECT'] },
      blockers: { type: 'array', items: { type: 'string' } },
      requiredChanges: { type: 'array', items: { type: 'string' } },
      optionalFollowUps: { type: 'array', items: { type: 'string' } },
      summary: { type: 'string' }
    }
  };
}

function hasBlockingChange(reviews) {
  return reviews.some((review) => {
    const verdict = String(review.verdict || '').toUpperCase();
    return (
      verdict !== 'APPROVE' ||
      (Array.isArray(review.blockers) && review.blockers.length > 0) ||
      (Array.isArray(review.requiredChanges) && review.requiredChanges.length > 0)
    );
  });
}

export async function process(inputs, ctx) {
  ctx.log('info', 'Preflighting Slice 0 observability and LLM-boundary guardrails');
  const preflight = await ctx.task(preflightInventory, inputs);

  await ctx.breakpoint({
    title: 'Approve Slice 0 implementation',
    question: 'Approve implementing Slice 0: grounding observability plus LLM-boundary guardrails, with no live providers/replay/judge/UI/Docling/OCR?',
    context: {
      runId: ctx.runId,
      summary: preflight,
      files: [
        { path: '.a5c/processes/summary-agent-slice0-observability-boundary.process.md', format: 'markdown' },
        { path: '.a5c/processes/summary-agent-slice0-observability-boundary.mermaid.md', format: 'markdown' },
        { path: 'docs/document-intelligence/summary-agent-improved-plan.md', format: 'markdown' }
      ]
    },
    expert: 'owner',
    tags: ['approval-gate', 'architecture']
  });

  let implementation = await ctx.task(implementSlice0, { ...inputs, preflight });
  let qualityGates = await ctx.task(runFocusedQualityGates, { implementation });
  let reviews = await ctx.parallel.all([
    () => ctx.task(summaryModelReview, { implementation, qualityGates }),
    () => ctx.task(llmBoundaryReview, { implementation, qualityGates }),
    () => ctx.task(validationReview, { implementation, qualityGates })
  ]);

  const refinements = [];
  for (let pass = 1; pass <= 2 && hasBlockingChange(reviews); pass++) {
    const refinement = await ctx.task(addressReviewBlockers, {
      pass,
      implementation,
      qualityGates,
      reviews
    });
    refinements.push(refinement);
    qualityGates = await ctx.task(runFocusedQualityGates, { implementation, refinement, pass });
    reviews = await ctx.parallel.all([
      () => ctx.task(summaryModelReview, { implementation, refinement, qualityGates, pass }),
      () => ctx.task(llmBoundaryReview, { implementation, refinement, qualityGates, pass }),
      () => ctx.task(validationReview, { implementation, refinement, qualityGates, pass })
    ]);
  }

  const blockingReviewRemaining = hasBlockingChange(reviews);

  return {
    ok: !blockingReviewRemaining,
    processId: 'project/summary-agent-slice0-observability-boundary',
    preflight,
    implementation,
    qualityGates,
    reviews: {
      summaryModel: reviews[0],
      llmBoundary: reviews[1],
      validation: reviews[2]
    },
    refinements,
    blockingReviewRemaining,
    metadata: {
      projectRoot: PROJECT_ROOT,
      timestamp: ctx.now()
    }
  };
}
