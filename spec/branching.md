# Branching

## New installations

New clean installations are single-branch: the repository's primary working branch is both discovery and authority.

## Installed redirect topology

A repository may retain an explicit `branch_mode: redirect` topology when its discovery branch and authoritative context branch differ.

This is supported installed state, not a signal to create redirect topology for new projects. Repair preserves the recorded authoritative/discovery branches and refuses to run from a different branch than `authoritative_branch`.

## Publication concurrency

Lifecycle publication is based on an expected HEAD. The planned commit has that HEAD as its parent and the branch update is non-forced. If the branch advances concurrently, publication is rejected.
