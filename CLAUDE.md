# Instructions for Claude

- Task tracking lives in GitHub Issues on this repo (`gh issue list`/`gh issue view`), not in a
  local TODO file. There used to be a `TODO.md` here; it was deleted 2026-11-02 because it had
  drifted out of sync with GitHub Issues (stale "open" items that had actually shipped, issues
  with no TODO.md entry at all, etc.) and the two were competing sources of truth. Don't recreate
  a local TODO file -- file a GitHub issue instead.
- `CHANGELOG.md`'s `[Unreleased]` section should only reflect what's actually been committed --
  update it as part of the release process (alongside the version bump and deploy), not while
  work is still in progress on disk.
