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

## Compatibility

The first split preserves the existing v2 on-disk contract, including the legacy
`core_commit` provenance coordinate. This avoids silently rewriting installed managers.

A later explicit schema migration will separate Context Capsule Core provenance from
Project Manager product provenance.

## CLI

```bash
python installer/pmctl.py install --target /repo --repository owner/name --branch main --core-commit <pm-source-commit>
python installer/pmctl.py upgrade --target /repo --repository owner/name --branch main --core-commit <pm-source-commit>
python installer/pmctl.py repair --target /repo --repository owner/name --branch main --core-commit <pm-source-commit>
python installer/pmctl.py validate --target /repo
python installer/pmctl.py ready --target /repo
python installer/pmctl.py recover --target /repo
```
