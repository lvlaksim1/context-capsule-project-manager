# Project Manager v2 gap analysis

Baseline reviewed: `v2-manager-runtime@a13840b9eea39d3e3b1db5403a977e39954c7964`.

| Area | Baseline | Gap found | Resolution |
|---|---|---|---|
| Stable identity / one-project ownership | Implemented | No foundational gap | Retained |
| BDI separation | Implemented | No foundational gap | Retained |
| Owner interaction semantics | Partial | Questions/discussion were not explicitly separated from authorization and directives | Contract + Protocol now classify owner communication |
| Commitment lifecycle | Partial | Continuity existed, but terminal transitions were not normative | Explicit proposed → active → terminal lifecycle |
| Evidence revision | Implemented | No foundational gap | Retained confirm/supersede/conflict |
| Authority transport resistance | Behaviorally demonstrated | Needed generic permanent rule | Contract/Protocol state that tool/model/summary/repetition do not upgrade authority |
| Reconciliation | Partial | Live reconciliation existed but minimum risk-scoped checks were not explicit | Contract defines material/risk-based reconciliation |
| Memory lifecycle | Partial | Typed memory existed; admission/revalidation/consolidation lifecycle was incomplete | Explicit candidate/admit/retrieve/revalidate/revise/consolidate lifecycle |
| Owner interaction memory | Partial | No explicit boundary against raw transcript accumulation | Durable semantic interaction only |
| Work lifecycle | Implemented | Completion and persistence linkage could be tighter | Completion requires verification; persistence requires semantic change |
| Self-modification | Partial | Self-authority expansion was not a first-class invariant | Explicit self-modification boundary + manifest invariant |
| External expertise | Missing as PM contract | No normative competence-gap/service-authority rule | Minimal specialist boundary added |
| Automated conformance | Strong but incomplete | New clauses lacked permanent checks | Manifest/schema invariants + regression tests |
| Consumer behavior | Existing independent evidence | Repetitive manual battery is unnecessary | Limited isolated smoke only |

## Hardening result

The foundational gaps were concentrated in owner semantics, commitment state transitions, durable-memory lifecycle, risk-scoped reconciliation, self-modification, and external-expertise boundaries.

Commits `48788a8dcbcc28983eaa79ecc4d9c5eabf81955c`, `1da1fed5ac39a050a2114aa739aa662efb8a546b`, and `7ac43d9cb1ab4a369f8cf910534a3ba7f1b1241d` close these gaps at the contract/protocol/validation layer. GitHub Actions run `35797112819` verified the resulting implementation successfully.

No general Service Agent framework is introduced here. That remains Master Plan item 2.
