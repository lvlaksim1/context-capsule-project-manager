# Project Manager versioning

All Project Manager versions are **stable** and consist only of `MAJOR.MINOR.PATCH`.
No `v` prefix and no dev/beta/rc/alpha suffix. Git tags use the exact same numeric identifier.

- MAJOR: incompatible persisted format or API changes requiring explicit migration.
- MINOR: compatible new capabilities.
- PATCH: compatible fixes.
- Every change to `installer/`, `schemas/` or `templates/` requires a version increase.
- Documentation, tests and project-only state updates do not change the product version.
- `VERSION`, `installer/model.py:PROJECT_MANAGER_VERSION` and installed metadata for new installations use the same version.
- After successful CI create a Git tag equal to the number and a stable GitHub Release (not a prerelease).
- Source commit SHA is the precise code provenance. Changes never silently upgrade an existing manager or the factory's pinned source.

Historical installed `2.0.0-dev` capsules remain readable so they can be migrated explicitly. This historical identifier is never emitted in a new installation or release.

The CI workflow invokes `scripts/check_version.py` to enforce numeric versions, reject regressions and require increments for functional code changes.
