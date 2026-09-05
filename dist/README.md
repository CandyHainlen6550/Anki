# Generated release files

GitHub Actions writes the permanent deck here as:

`HT Joyo 2136.apkg`

The source ZIP intentionally does not include a stale APKG built with older component-rendering logic. After the repository is uploaded, the workflow fetches the pinned upstream sources and generates the current APKG plus QA/hashes in this directory.
