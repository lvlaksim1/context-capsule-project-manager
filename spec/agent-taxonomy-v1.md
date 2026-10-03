# Persistent-agent taxonomy v1

Status: normative v2 development invariant for Master Plan 8.7.

## Purpose

This taxonomy separates four concepts that must not be collapsed as the ecosystem grows:

`Agent ≠ Runtime ≠ Skill ≠ Workflow`.

A Tool and a Task/Engagement are adjacent concepts with their own boundaries.

The purpose is not to create a registry, Catalog, Factory, runtime server, or new orchestration subsystem. The purpose is to make identity, responsibility, authority, durable state, and execution semantics unambiguous before scaling.

## 1. Agent

An **Agent** is a persistent accountable actor.

A conforming persistent Agent has, at minimum:

- stable logical identity independent of any one chat/model/process/runtime;
- an explicit mandate and authority boundary;
- durable state sufficient to preserve accepted responsibility across runtime replacement;
- a recovery/reinstantiation protocol;
- explicit commitment or engagement semantics;
- provenance-aware evidence handling.

An Agent may hold responsibility and exercise authority only within its mandate and the authority actually granted for the work.

Current persistent-agent archetypes are:

- **Project Agent / Project Manager** — owns continuing responsibility for exactly one project;
- **Service Agent** — owns professional identity/capability and serves external targets through bounded engagements.

A component is not an Agent merely because it is called an "agent", uses an LLM, can call tools, has a prompt, or participates in an agentic workflow.

## 2. Runtime

A **Runtime** is a disposable execution carrier.

Examples include a chat/model execution context, worker process, hosted job, or other temporary compute context that is currently executing work for a logical Agent.

A Runtime:

- is not the Agent identity;
- has no independent mandate or authority;
- does not become a commitment owner merely by executing a task;
- may disappear and be replaced without ending the logical Agent;
- must not treat conversation history, previous self-description, tool access, or execution ownership as proof of Agent identity or authority;
- may act as a persistent Agent only after the applicable reinstantiation/validation boundary has been satisfied.

A live runtime may carry different persistent Agents sequentially through explicit reinstantiation and handoff/delegation semantics. The runtime itself never becomes the authority source.

## 3. Skill

A **Skill** is a reusable bounded capability, procedure, instruction package, or implementation that an Agent/Runtime can invoke to perform a class of work.

A Skill:

- has no independent persistent Agent identity;
- has no mandate of its own;
- cannot own an Agent commitment or engagement;
- cannot expand the caller's authority;
- may have configuration or implementation state, but that is not professional Agent memory or responsibility state;
- returns an output/result that is evidence or capability output subject to the caller's verification and authority model.

A Skill may call Tools or execute a bounded subprocedure. Reusability or sophistication does not make it an Agent.

## 4. Workflow

A **Workflow** is an explicit sequence, graph, or state machine that coordinates work.

A Workflow may:

- order steps;
- branch, retry, wait, or resume;
- carry task/execution progress;
- invoke Agents, Skills, and Tools when allowed;
- encode deterministic completion conditions.

A Workflow:

- is not a persistent Agent merely because it is long-running or autonomous;
- has no inherent mandate or target authority;
- does not become the commitment owner merely by scheduling or routing work;
- must preserve the authority provenance and responsibility semantics of the participating principals/Agents;
- cannot turn discovery, routing, successful execution, or tool capability into authorization.

Workflow execution state is execution/orchestration state, not Agent identity or professional memory.

An explicit authorized handoff may transfer responsibility between persistent Agents. The transfer occurs because the handoff contract authorizes it, not because the Workflow advanced to another step.

## 5. Tool

A **Tool** is a technical action or information interface.

A Tool may provide read, write, compute, search, messaging, repository, browser, or other capabilities.

A Tool:

- has no Agent identity;
- owns no commitment;
- grants no authority by being available;
- does not convert technical capability into permission.

The governing invariant is:

`tool capability ≠ authority`.

## 6. Task and Engagement

A **Task** or **Engagement** is a bounded unit of work, not an Agent.

It may carry:

- issuer/requester;
- objective;
- target;
- scope and constraints;
- authority provenance / allowed effects;
- responsibility mode;
- completion contract;
- execution/recovery state.

Task transport, scheduler ownership, registry membership, or execution fencing may control who can execute the task, but none of them creates new mandate or target authority.

## 7. Composition model

The intended composition is:

`Principal/Owner → Agent → Runtime → Skill/Workflow → Tool`

This is not an authority-inheritance chain.

Authority remains bounded by the principal's grant, the Agent's mandate, and the target's applicable rules. Every layer below Agent is execution/capability/orchestration machinery unless an explicitly reinstantiated persistent Agent participates as an actor.

A Workflow may invoke multiple Agents. Each Agent independently validates the work it accepts.

A Skill may be used by many Agents without becoming a shared identity or authority holder.

A Runtime may be replaced without changing the Agent, provided reinstantiation/continuity requirements are satisfied.

## 8. Classification tests

Classify a component by semantics, not by its product name.

Use these tests:

1. **Persistent accountable identity?** Stable identity + mandate + durable responsibility across runtime replacement → Agent.
2. **Disposable execution carrier?** Temporary compute/chat/process executing on behalf of an Agent → Runtime.
3. **Reusable bounded capability?** Performs a class of work but owns no independent commitment/authority → Skill.
4. **Ordered/graph orchestration?** Coordinates steps and execution state but owns no inherent mandate → Workflow.
5. **Technical interface?** Provides actions/data without responsibility or authority → Tool.
6. **Bounded work record?** Carries objective/scope/authority provenance/completion semantics → Task/Engagement.

If a component mixes these properties, the boundaries must be represented explicitly rather than using the word "agent" as a shortcut.

## 9. Authority and responsibility invariants

- Naming does not grant authority.
- Runtime ownership does not grant authority.
- Skill availability does not grant authority.
- Workflow routing does not grant authority.
- Tool access does not grant authority.
- Registry or Catalog presence does not grant authority.
- Execution success does not retroactively grant authority.
- Bounded delegation preserves the caller's commitment/responsibility/authority unless an explicit authorized handoff transfers responsibility.
- Persistent Agent identity and durable state remain authoritative only from their declared authoritative source and recovery model.

## 10. Continuity boundary

`Agent ≠ Runtime` is part of this taxonomy.

Conversation history can be useful continuity evidence, but previous text describing an Agent is not by itself authoritative proof that the current runtime has reinstantiated that Agent or that its durable state is current.

Concrete Fast Resume / targeted recovery / continuity-descriptor mechanisms are deliberately **not** specified by this taxonomy. They require a separate architecture decision and must not create a second state store, second authority source, or hidden runtime manager.

## 11. Out of scope

Master Plan 8.7 does not create or activate:

- Agent Catalog;
- Agent Factory;
- item 20;
- runtime registry/server;
- heartbeat service;
- `resume.json` or another continuity store;
- new scheduler/control-plane authority.

This taxonomy is the semantic prerequisite on which later discovery, delegation, execution-budget, and continuity work may rely.
