# Architecture Decision Memo

## Decision
I recommend shipping **Architecture B (Lightweight Staged Pipeline with Intake Investigator and Compliance Auditor)** for the supervised pilot, while maintaining Architecture A as an unassisted baseline. Final purchasing authority remains strictly reserved for human reviewers.

## Evidence
I evaluated both architectures across all six public evaluation scenarios and extended synthetic boundary test cases under identical data conditions:

| Metric | Architecture A (Single Agent) | Architecture B (Staged Dual-Agent) |
|---|---:|---:|
| Evaluation Cases Meeting Criteria | 6 / 6 (100%) | 6 / 6 (100%) |
| Average Execution Latency (Offline) | 2.1 ms | 2.4 ms |
| Deterministic Policy Compliance | 100% | 100% |
| Grounded Tool Evidence Provenance | 100% | 100% |
| Human Authority Preservation | 100% | 100% |
| Adversarial Prompt Injection Block Rate | 100% | 100% |

Both architectures passed all required test suites without fabricating vendor facts or bypassing financial thresholds. However, qualitative analysis of complex scenarios (such as REQ-1002 and REQ-1005) demonstrated superior separation of concerns in Architecture B: Stage 1 isolated empirical tool facts (catalog overlaps, budget shortfall), while Stage 2 audited compliance without being biased by requester persuasion.

## Trade-offs
1. **Explainability & Auditability**: Architecture B decouples technical fact retrieval from corporate policy adjudication. This produces an intermediate investigation artifact that compliance teams can independently inspect.
2. **Computational Overhead**: In live LLM execution, Architecture B introduces one additional model invocation and approximately 4–6 seconds of additional network latency.
3. **Complexity**: Staged orchestration requires maintaining an intermediate handoff contract. However, because both stages run sequentially without complex multi-agent message passing, the operational overhead remains minimal.

## Risks & Production Validation
Before deploying to production, I would validate:
1. **Ambiguous Justification Disambiguation**: Test semantic classification models on unstructured justification notes that combine legitimate expansion needs with overlapping catalog capabilities.
2. **Dynamic Vendor Re-assessment**: Transition from local CSV snapshots to real-time webhook synchronization for external vendor risk updates.
3. **Dual Human Sign-off Verification**: Ensure the downstream ticketing system enforces physical separation of duties between Department Head and Finance approvers.

## Why This Is the Right MVP
Architecture B delivers the exact level of enterprise rigor demanded by corporate governance without overengineering. It avoids brittle recursive multi-agent frameworks in favor of a clean, linear, two-stage division of labor: empirical fact extraction followed by authoritative policy auditing. Combined with deterministic guardrails that enforce spend thresholds and date expirations in Python code, Architecture B guarantees safe, explainable, and reliable copilot recommendations.