# Architecture

Context Capsule v2 represents a persistent Project Manager in the project repository itself.

## Permanent layers

- `project/`: objective identity, goals, architecture, constraints.
- `manager/`: stable manager identity, project-specific mandate, BDI-style active state, and Core-managed Manager Protocol.
- `memory/`: semantic, episodic, and procedural memory.
- `rules/` and `decisions/`: binding durable choices.
- `current/`: compact verified project state, blockers, next work.
- `handoffs/latest.md`: optional emergency/convenience summary rather than the continuity root.
- `dialogues/` and `history/`: deeper evidence/history.

`capsule.json` identifies the installed Core version and exact immutable `core_commit`. `manifest.json` maps project-owned context while preserving safe extensions.

## Runtime boundary

Chat/session history and workflow checkpoints are not Manager identity. The same manager may be instantiated by different runtimes over time.

## Mutation boundary

Canonical lifecycle mutations are planned and validated as a complete snapshot and published with an expected-parent non-forced Git ref update.

## Branch model

A permanent authoritative context branch may differ from a discovery branch. Disposable feature/runtime branches never become manager identity or durable context authority merely because execution occurs there.

## Persistent-agent taxonomy boundary

The normative cross-profile taxonomy is `spec/agent-taxonomy-v1.md`.

Context Capsule distinguishes `Agent ≠ Runtime ≠ Skill ≠ Workflow`:

- persistent Agent carries identity, mandate, durable responsibility, and recovery semantics;
- Runtime is a disposable execution carrier;
- Skill is reusable capability without independent mandate or commitment ownership;
- Workflow coordinates execution but has no inherent authority or persistent Agent identity;
- Tool capability never implies permission.

This boundary is semantic infrastructure only. It does not create Agent Catalog, Agent Factory, or a runtime/continuity subsystem.

## Delegation / responsibility / authority boundary

The normative source-level semantics are in `spec/delegation-responsibility-authority-v1.md`.

Core treats commitment responsibility, execution responsibility, authority, and execution ownership as separate concepts.

New executable agent-to-agent tasks use hardened responsibility semantics version 2. Historical completed version-1 responsibility artifacts remain readable and are not rewritten.
