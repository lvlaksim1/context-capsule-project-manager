# Agent Control-Plane Interoperability v1

Status: normative development contract for optional orchestration interoperability.

## Purpose

Context Capsule persistent agents may be invoked directly by a human or through external orchestration. The orchestration layer is optional infrastructure. It does not own agent identity and it does not grant authority merely by delivering work.

This contract is transport-neutral. Core intentionally does not depend on a particular queue, scheduler, repository layout, lease service, or worker implementation.

## Invariants

1. **Interactive-first execution is task-scoped and mandatory.** When an Owner-facing live runtime carries a specific authorized task/chain, GitHub stores the durable handoff and the next persistent agent is reinstantiated directly in that live runtime. If that task/chain has a control-plane or otherwise scheduler-visible projection, a fresh task-scoped live-carrier ownership fence **MUST be established before interactive execution proceeds**; a direct Owner interaction with no scheduler-visible projection does not require creating control-plane state.
2. **Direct invocation remains first-class.** Owner/requester ↔ agent interaction does not require Supervisor or a control plane.
3. **Autonomous scheduling remains available for unrelated work.** Owner presence must not globally disable, park, or delay scheduler infrastructure; unrelated tasks without fresh live carriers remain scheduler-eligible.
4. **Task-scoped fallback is explicit.** An expired live carrier may fall back to scheduler execution when configured; an explicit per-task Owner hold may block only that task indefinitely.
5. **Task transport is non-escalating.** Delivery, registry membership, worker allocation, or tool access cannot increase authority.
6. **Target-side validation is mandatory.** The reinstantiated target agent validates issuer, authority provenance, target identity, scope, constraints, requested effects, and completion contract against its own mandate before acceptance.
7. **Agent-to-agent routing is allowed but bounded.** An authorized Project Manager or Service Agent may request work directly; Supervisor is not a universal routing hop.
8. **Execution fencing is conditional but strict.** If an external execution context supplies a fence, the target runtime revalidates it immediately before every consequential write and before terminal completion. Stale or unverifiable runtimes do not write.
9. **Checkpointing is resumable, not cognitive persistence.** Checkpoints contain stable task/execution facts, verified evidence, current step, and next action; never hidden chain-of-thought.
10. **Completion is evidence-backed.** Success requires the declared completion evidence, not an agent assertion.
11. **Terminal cleanup is canonical.** A terminal task cannot retain an active execution claim/fence projection.
12. **Bounded delegation preserves responsibility.** Live agent-to-agent bounded delegation keeps the active commitment, responsibility, and authority with the caller; the immutable task names that caller as return target, and verified terminal completion must immediately reinstate the caller in the same live runtime without requiring a new Owner message.
13. **Explicit handoff is distinct.** Responsibility transfer exists only through an explicit authorized handoff contract to the target agent; bounded delegation and transport never imply such transfer, and an explicit handoff does not imply automatic return.

Profiles may add stricter requirements but may not weaken these invariants.
