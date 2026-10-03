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


## Provenance boundary

Installed Project Manager state records Context Capsule Core compatibility and Project Manager
implementation provenance as separate immutable coordinates. Project Manager lifecycle integrity
binds PM-managed governing files to the Project Manager coordinate; it does not reinterpret the
Context Capsule Core coordinate as PM source authority.
