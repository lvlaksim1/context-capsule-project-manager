# Product boundaries

## Owned here

This repository owns the Project Manager product: manager lifecycle, identity, mandate, BDI state,
manager-specific memory semantics, authority rules, schemas, templates, and lifecycle tooling.

## Not owned here

- Generic durable-context protocol and stable Context Capsule Core: `lvlaksim1/context-capsule`.
- Independent audit implementation and audit records: `lvlaksim1/project-manager-auditor`.
- Supervisor service-agent implementation and portfolio state: `lvlaksim1/supervisor`.
- Repository provisioning and compatible component pinning: `lvlaksim1/repo-factory`.

## Dependency direction

`Context Capsule <- Project Manager <- consumer project`

Auditor and Supervisor may inspect or consume the same durable context contract, but Project Manager
does not own their identities or professional state.

The repository split does not silently migrate existing consumer state. Compatibility changes that
alter on-disk state require an explicit schema migration.
