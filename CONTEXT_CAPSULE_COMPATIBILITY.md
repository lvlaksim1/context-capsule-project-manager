# Context Capsule compatibility

Project Manager v2 was extracted from the former combined v2 development line.

Current compatibility rule:

- existing v2 capsules keep their current on-disk schema;
- stable `manager_id`, project semantics, memory and branch topology are preserved;
- no consumer is silently upgraded by the repository split;
- new Project Manager product authority is this repository;
- generic Context Capsule Core authority remains `lvlaksim1/context-capsule`;
- Core provenance and PM provenance will be split only through an explicit schema migration.
