# Manager beliefs

- PM v2 source authority is this repository; baseline `0544517c14e115a70e40d1324d1e594035971eaa` passed CI run `37158811501`. source: GitHub Actions and repository state; authority: verified-repository.
- Context Capsule Core is a separate product; `v2-manager-runtime` is migration provenance, not new PM authority. source: context-capsule boundary commits; authority: owner-directed-architecture plus verified-repository.
- repo-factory uses exact component pins and verified temporary installs. source: components.lock.json and smoke run 37158937697; authority: verified-repository.
- Existing consumers are not silently migrated by this split. source: compatibility contract; authority: owner-directive plus verified-repository.
