# Local-first workspace policy v1

Owner decision: 2026-10-30. This is an operational default and does not transfer authority.

1. DOMKAT (Windows), D:\Dev, is the preferred development host and local repository root. A manager capsule is stored with its project in its own repository and in the already-authoritative manager-state branch.
2. Code editing, testing, builds, debugging and capsule persistence normally occur in a local Git working copy. A separately located manager-state branch may require a second worktree. Never collapse it into product main by assumption.
3. GitHub provides repository history, collaboration, versioned backup, release publication and disaster recovery. Direct GitHub development remains allowed when useful or requested; it is not forbidden.
4. Before starting, verify machine/repository identity, current branch, local changes, capsule seal and remote status. Filesystem path alone is not a trust or authority boundary.
5. After meaningful changes, validate the capsule's existing seal, commit the relevant branch locally, fetch remote and reconcile divergence, then push and verify readback. Never force-push or discard conflicting unpublished changes automatically.
6. If DOMKAT is unavailable, the last independently verified GitHub state may be used for recovery. Label freshness and the possibility of newer unpublished local changes. Do not claim inaccessible local effects were absent.
7. Retain existing identities, mandates, Owner approval gates, engagement restrictions, history and integrity semantics. GitHub CI may still run; release evidence is not user acceptance.

Do not require a separate daemon, paid service, API billing or additional repository for this policy.
