# Context Capsule compatibility

Project Manager v2 is a separate product built on the Context Capsule durable-context contract.

## Version coordinates

The products are versioned independently:

- Context Capsule Core version: `1.3.1`;
- Project Manager version: `2.0.0-dev`.

New and repaired installations record canonical component objects
`context_capsule.version` and `project_manager.version`, plus transitional top-level
`context_capsule_version` and `project_manager_version` mirrors.

The historical top-level `version` field is deprecated. In PM v2 metadata its value
`2.0.0-dev` means **Project Manager version**, never Context Capsule Core version.

The manifest follows the same rule: use `context_capsule_version` and
`project_manager_version`. Historical `context_version` is deprecated because it carried
the PM version despite its ambiguous name.

## Provenance coordinates

New or explicitly repaired v2 installations record both immutable product coordinates:

- `provenance.context_capsule.repository` + `commit` identify the Context Capsule Core contract;
- `provenance.project_manager.repository` + `commit` identify the Project Manager implementation.

For transition compatibility, top-level `project_manager_commit` and
`context_capsule_commit` mirror those coordinates. The historical top-level
`core_commit` remains a deprecated alias for the Project Manager commit only.

## Legacy v2 compatibility

Legacy v2 capsules that contain only `core_commit` remain structurally valid. The value is
interpreted using the historical v2 meaning: it identifies the Project Manager source commit,
not Context Capsule Core.

An explicit `repair` or other lifecycle migration may enrich that metadata with the split
provenance coordinates. Existing consumers are never silently rewritten merely because the
source repositories were separated.

## v1.3 upgrade rule

When an installed Context Capsule v1.3.x capsule is upgraded and no Core coordinate is supplied,
the upgrade preserves that capsule's existing `core_commit` as Context Capsule Core provenance.

## Current Core compatibility baseline

For clean installs and legacy v2 repairs where no Core coordinate exists, Project Manager uses
the canonical Context Capsule Core v1.3.1 commit
`2ef41a5ed57ae514cc5980065560d7e55d5e4b9a`.

Distribution systems such as `repo-factory` should pass their own immutable Core pin explicitly
rather than relying on this compatibility default.
