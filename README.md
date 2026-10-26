# Context Capsule Project Manager

Portable Project Manager built on the Context Capsule durable-context contract.

## Product boundary

This repository is the authoritative source for **Project Manager v2**. It owns:

- Project Manager identity, mandate, BDI state and lifecycle semantics;
- manager-specific schemas and templates;
- install / upgrade / repair / validate / ready / recover tooling;
- manager authority, evidence, memory and delegation contracts.

It does **not** own the generic Context Capsule product and it does not own Service Agent profiles.

- Context Capsule Core: `lvlaksim1/context-capsule`
- Project Manager: `lvlaksim1/context-capsule-project-manager`
- Auditor: `lvlaksim1/project-manager-auditor`
- Supervisor: `lvlaksim1/supervisor`
- Repository provisioning: `lvlaksim1/repo-factory`

## Migration provenance

Split from `lvlaksim1/context-capsule:v2-manager-runtime` at immutable source commit
`724c3e1c1960497b38eec106a4e9999305e5a046`.

The old branch is migration history. New PM product development belongs here.

## Version semantics

Context Capsule Core and Project Manager are independently versioned products:

- Context Capsule Core: **v1.3.1**;
- Project Manager: **v2.0.0-dev**.

New and repaired PM installations record both explicitly in `.context/capsule.json`:

```json
{
  "context_capsule": {
    "version": "1.3.1",
    "repository": "lvlaksim1/context-capsule",
    "commit": "<core-sha>"
  },
  "project_manager": {
    "version": "2.0.0-dev",
    "repository": "lvlaksim1/context-capsule-project-manager",
    "commit": "<pm-sha>"
  }
}
```

The historical top-level `version: "2.0.0-dev"` is retained only as a deprecated
compatibility alias for the Project Manager version. It must not be read as a Context Capsule
Core version. The manifest likewise exposes explicit `context_capsule_version` and
`project_manager_version`; its historical `context_version` field remains deprecated.

## Compatibility

The repository split now has an explicit provenance model. New or repaired v2 installations
record separate immutable coordinates for Context Capsule Core and Project Manager.

The historical `core_commit` field remains as a deprecated compatibility alias for the
Project Manager source commit so existing v2 consumers are not invalidated. Legacy metadata
is accepted and is upgraded in place by an explicit lifecycle operation.

## CLI

```bash
python installer/pmctl.py install --target /repo --repository owner/name --branch main --project-manager-commit <pm-source-commit> --context-capsule-commit <core-commit>
python installer/pmctl.py upgrade --target /repo --repository owner/name --branch main --project-manager-commit <pm-source-commit> --context-capsule-commit <core-commit>
python installer/pmctl.py repair --target /repo --repository owner/name --branch main --project-manager-commit <pm-source-commit> --context-capsule-commit <core-commit>
python installer/pmctl.py validate --target /repo
python installer/pmctl.py ready --target /repo
python installer/pmctl.py recover --target /repo
```


## Live product freshness (optional strict gate)

Structural integrity does not guarantee that the Project Manager has caught up
with the latest product release. Reconcile the project against GitHub and record
a reviewed baseline, then use the fail-closed mode for consequential work:

```bash
python installer/pmctl.py product-freshness --target /repo
python installer/pmctl.py capture-product-baseline --target /repo --confirm-reconciled
python installer/pmctl.py ready --target /repo --require-freshness
python installer/pmctl.py recover --target /repo --require-freshness
```

An absent baseline, unavailable GitHub, and mismatched authority never count as
fresh. Product head drift is distinguished from a new published release.
Older installations remain compatible; the new gate is opt-in. See
[product freshness protocol](spec/product-freshness.md) for limitations and
required manual reconciliation before recapturing evidence.

## Durable event persistence and compact working context

Record a **verified event** and any commitment lifecycle transitions against an
exact manager-state branch head. The default command only plans; `--publish`
creates one non-forced GitHub commit containing BDI/current updates, a durable
event log, a commitment registry, refreshed state seal and compact index.

```bash
python installer/pmctl.py persist-event --target /repo --event /tmp/verified-event.json --expected-head <sha>
GITHUB_TOKEN=... python installer/pmctl.py persist-event --target /repo --event /tmp/verified-event.json --expected-head <sha> --publish
python installer/pmctl.py working-index --target /repo --verify
python installer/pmctl.py active-commitments --target /repo
```

Owner acceptance is never inferred from a successful CI run or release.
Existing capsules remain valid until explicitly updated. The compact working
index is non-authoritative and links to complete, sealed sources. See
[durable event and working index protocol](spec/durable-events-and-working-index.md).

## Recovery budget

The default reinstantiation-pack budget is 131072 characters. Project Manager Contract and
Protocol are mandatory recovery state, and the previous 65536-character default became too small
for valid, substantive projects as those governing contracts grew. Callers may still pass a
smaller or larger explicit `--max-chars`; mandatory state always fails closed if it cannot fit.

## Legacy v2 provenance normalization

Older v2 managers may contain durable beliefs or memory written before per-entry provenance became
mandatory. After `repair`, run:

```bash
python installer/pmctl.py normalize-legacy-provenance --target /repo --branch main
```

The command does not reinterpret the statement. It only adds conservative metadata where missing:
`source: legacy-v2-state` and `authority: legacy-unverified`.

Structured entries are parsed logically: a `##` memory section is one durable entry, and indented
`source`/`authority` bullets belong to their parent belief rather than becoming separate facts.
If coupled manager state changes, the state-integrity seal advances only after the previous
generation has been verified coherent.
