# Semantic sync

Context Capsule v2 is not an append-only runtime event log.

## Promote into durable manager/project state

Promote verified consequences such as:
- decisions and requirements;
- durable rules/preferences;
- architecture changes;
- manager beliefs that can affect future decisions, including provenance;
- goals and accepted intentions/commitments;
- blocker/root-cause findings;
- accepted/rejected approaches;
- milestone/release meaning;
- durable semantic/episodic/procedural lessons.

## Keep out

Do not routinely persist:
- heartbeats, leases, polling ticks, queue transitions;
- transient CI status;
- pending tool calls;
- raw chat turns;
- hidden chain-of-thought;
- runtime checkpoint internals.

## Supersession

When durable understanding changes, preserve enough provenance to explain what superseded what. Do not rewrite uncertain/external claims into owner-authoritative facts merely through summarization.

## Consolidation

Periodically compact the active working set while retaining deeper typed memory. Consolidation should remove duplication, not provenance or meaningful historical reversals.
