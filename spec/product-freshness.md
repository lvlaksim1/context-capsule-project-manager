# Product freshness and bounded reconciliation (Project Manager v2)

## Problem

A coherent Context Capsule integrity seal does not prove that the manager
describes the current product. For example, the manager may still refer to
v0.1.20 after a later v0.1.23 release. Structural VALID and project READY
remain separate from product FRESHNESS.

## Evidence and authority

The audit reads the capsule manifest's repository and
authority.product_branch. It queries GitHub for:
- the current head SHA of that product branch;
- the latest *published, non-prerelease* GitHub release tag (if any);
- the actual commit SHA for that release tag, not the often ambiguous
  target_commitish field.

No data is inferred from release names in old history paragraphs. The audit
compares live GitHub evidence with a deliberately reconciled baseline in
.context/current/product-baseline.json.

Statuses:
- FRESH: both release identity and product branch head exactly match baseline.
- STALE: a published release tag or its commit differs.
- DRIFT: published release is unchanged, but product branch HEAD moved; it
  might be code or context-only changes, so do not claim the product changed
  without inspecting the diff.
- UNKNOWN: no baseline, missing/invalid evidence, inaccessible GitHub, or
  mismatched authority. UNKNOWN is never interpreted as FRESH.

A baseline records the *operator's explicit reconciliation assertion*, not
proof of user acceptance, passing tests or semantic correctness. It must not
be created merely to silence a failing audit.

## Use

From the installed Project Manager code:

    python installer/pmctl.py product-freshness --target /path/to/project

When the product has been reviewed against manager BDI, open commitments,
current state and release evidence, deliberately record the baseline:

    python installer/pmctl.py capture-product-baseline --target /path/to/project --confirm-reconciled

This writes a local file only. Review the changes and **commit it alongside**
the corresponding update of durable manager state, intentions, and handoff,
using the repository's atomic publication mechanism. A baseline alone is not
a semantic state update. For a separated manager-state branch, write this
file in the manager-state authority branch; query the product branch defined
in the manifest.

For consequential work, fail closed unless reconciled:

    python installer/pmctl.py ready --target /path/to/project --require-freshness
    python installer/pmctl.py recover --target /path/to/project --require-freshness

Normal validate/ready/recover remain backward-compatible, offline and do not
implicitly acquire a baseline. The audit requires GitHub network access and,
for private repositories, a read-capable GITHUB_TOKEN (never save the token
inside the capsule). The baseline may become DRIFT after context-only commits
on the same branch; review and re-record it only after verifying the diff.
Separate product and manager-state branches avoid this false-positive class.

## Operational trigger points

Run a freshness audit before consequential implementation, after a product
branch update, after each publication, before a cross-chat handoff and
before claiming that the manager is synchronized with product evidence.
On an observed version change, reconcile and persist:
1. factual current release and commit, keeping earlier history retrievable;
2. statuses of pending work (implemented, CI verified, released, accepted by
   owner), without conflating them;
3. ongoing intentions/commitments and next actions;
4. an explicit new baseline only after reconciliation.

Automating an audit is safe; auto-capturing a fresh baseline without semantic
review is **not** safe. For now, the tool does not alter project state or open
PRs automatically. A future atomic write protocol can couple baseline with
manager state integrity generation and establish stronger publication guards.

## Compact working sets

Retain full typed memory and evidence in Git. A short current view should
link to canonical state, record accepted decisions, active obligations,
blockers and next work, and be explicitly marked as a non-authoritative
index. Do not substitute the last historical paragraph for an exhaustive
list of active commitments. Compacting history must preserve provenance,
supersession and all unresolved accepted intentions.

## Compatibility

Existing v2 capsules require no migration and do not acquire new mandatory
fields. Absent baseline means UNKNOWN; strict freshness mode therefore
fails closed until the manager has reconciled and recorded its baseline.
This module belongs to Project Manager, not generic Context Capsule Core.
