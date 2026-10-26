# Durable event persistence and bounded working context

Project Manager v2 extension. Applies to manager-state authority only; Context Capsule Core is unchanged.

## Safety invariant

Durable semantic state is canonical; a working index is **never** canonical. An event transaction starts with a validated coherence-sealed READY Project Manager and an exact commit SHA. The transaction atomically records a verified event, structured commitments, and the updated manager state integrity marker. A race aborts publication without modifying the manager branch. An event never advances a product freshness baseline or asserts owner acceptance from a GitHub release.

## Event input

Create an input JSON file **outside** .context. Example:

```json
{
  "id": "release-0.3.107",
  "kind": "release",
  "summary": "GitHub release v0.3.107 was published; owner acceptance remains pending.",
  "product_repository": "owner/mailru-desktop",
  "product_branch": "main",
  "evidence_url": "https://github.com/owner/mailru-desktop/releases/tag/v0.3.107",
  "commitments": [
    {
      "id": "live-acceptance-107",
      "action": "open",
      "statement": "Obtain owner acceptance of v0.3.107 mailing behavior.",
      "requires_owner_acceptance": true
    }
  ]
}
```

Supported event kinds: `merge`, `release`, `verified-regression`, `owner-acceptance`. GitHub evidence is fetched from the exact product repository: merged PR must be merged, release must be published, CI run must have completed successfully. This proves only those specific GitHub facts, **not** end-to-end acceptance, semantic correctness or that every claim in the summary was independently verified. Operators must constrain statements to supported evidence.

An `owner-acceptance` event requires `owner_confirmed: true`, an HTTPS evidence link and the separate `--confirm-owner-acceptance` flag; confirmation is an explicit operator assertion and is not verifiable from GitHub. Nothing marks a user requirement accepted merely because tests or publishing passed.

Structured commitments use stable IDs. `open` requires a full statement and optional `requires_owner_acceptance`; terminal actions `complete`, `cancel`, `invalidate`, `supersede` require an explicit reason. No arbitrary deletion and no duplicate event replay. Legacy free-text intentions remain intact; until explicitly transcribed they are **not** machine-enumerable. All accepted legacy commitments must continue to be reviewed through their original BDI source.

## CLI, evidence and atomic publication

Use the installed source of the Project Manager executable from the authenticated, checked-out repo.

```bash
python installer/pmctl.py persist-event --target /repo --event /tmp/event.json --expected-head <manager-branch-sha>
```

By default this validates GitHub evidence and builds a plan, **without a write**. To publish in a single non-forced GitHub commit after reviewing the plan:

```bash
GITHUB_TOKEN=... python installer/pmctl.py persist-event --target /repo --event /tmp/event.json --expected-head <manager-branch-sha> --publish
```

Requires a clean local manager-state checkout matching the expected HEAD; the product branch is read from the manifest, never substituted with the manager branch. Branch moves fail closed, no force updates. A compatible GitHub token requires contents:write on the target repository. The planner seals the structured event/commitment registry with the existing BDI/current/handoff files. The evidence verifier uses GitHub read access.

Triggers: after merge, release, confirmed regression, or direct owner acceptance, submit the relevant event. Automatic *emission* by a supported workflow can call this command; an untrusted trigger cannot manufacture confirmation or secretly capture a new product freshness baseline. A GitHub trigger alone is not a replacement for semantic review.

## Compact working index

```bash
python installer/pmctl.py working-index --target /repo
python installer/pmctl.py working-index --target /repo --write
python installer/pmctl.py working-index --target /repo --verify
python installer/pmctl.py active-commitments --target /repo
```

The generated `.context/current/working-index.json` stores generation, product/manager branch coordinates, full canonical source paths/digests, and **all active structured commitment IDs**, not truncated descriptions. The canonical registry gives their full texts. The index always reports `legacy_commitments_not_machine_enumerated: true` and a legacy intentions source; no claim of comprehensive recovery from structured IDs alone. Freshness is `NOT_CHECKED` unless independently verified using the separate live product freshness gate.

Index is capped at 8192 characters by default. Insufficient space fails explicitly; callers must increase the budget or improve canonical source design. If any sealed source changes, index verification fails until regenerated. The working index is built automatically in the same durable event transaction, but manual local generation must be committed explicitly.

## Deployment

This change is additive. Old capsules remain valid; no automatic install or mutation of consumer projects occurs. The first accepted durable event adds manifest paths for structured commitments and durable events, and expands the integrity seal in the **same** atomic commit. Subsequent events preserve old event and commitment history and advance the sealed generation.

Recovery still loads mandatory authoritative manager state. It may load the compact index only for discovery, never to override missing or conflicting BDI evidence. Existing `ready` and `recover` retain their normal behavior and optional `--require-freshness` gate.
