# Semantic memory

- Agent identity/state and runtime execution are separate concerns. source: PM v2 recovery contract/tests; authority: verified-repository.
- Context format and Project Manager behavior have different lifecycles and separate source authorities. source: 2026-10-04 Owner-approved split; authority: owner-directive plus verified-repository.
- One component lock is safer than duplicated hidden pins. source: repo-factory lock migration; authority: verified-repository.
- Freshness alone does not imply semantic supersession. source: PM evidence-revision contract; authority: verified-repository-design.

- Durable rule storage, rule application, and pre-output compliance verification are separate properties. A known mandatory rule omitted from an action is `EXECUTION_INVARIANT_VIOLATION`, not automatically a memory failure. source: Owner directive 2026-10-07 + observed Supervisor incident; authority: owner-directive.
- Persistent-agent reliability requires regression checks across fresh runtimes and context changes; memory presence alone is insufficient evidence of reliable behavior. source: Owner directive 2026-10-07; authority: owner-directive.
