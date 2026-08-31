# Deploy Process

This describes how a change goes from "committed on disk" to "live on
[x4.fly.dev](https://x4.fly.dev)". It's a manual checklist today -- see
"Scripting this later" at the bottom for what a future automated version
would need to cover.

Related files: `CHANGELOG.md` (Production/Development convention),
`VERSION` (this tool's own version, read by `api.py` and shown on the
About page), `fly.toml` / `fly.staging.toml` (per-environment Fly app
config), `Dockerfile`.

**Three mandatory pauses for explicit user confirmation, not just
recommendations:** after the staging deploy (step 4), before writing the
version number anywhere (step 5), and before running `git commit` (step
8). Don't guess past any of these or treat silence as approval -- stop and
wait for an actual answer each time, every deploy, even a small one.

## 1. Decide what's shipping

Everything currently listed under `CHANGELOG.md`'s `## [Unreleased] -
Development` section is what a deploy right now would ship. Read it over
-- if something in there isn't actually ready, either finish it or pull
its bullet back out before continuing.

## 2. If any game-data pipeline files changed, regenerate the database

`data/` (the SQLite database, CSVs, and every extracted image) is
gitignored but gets baked into the Docker image straight from the local
filesystem at build time (see the Dockerfile's own comment) -- Fly never
sees git history for that folder at all, only whatever's on disk right
now. So if this deploy touches anything under `src/generate_ships_table.py`,
`src/extract_game_data.py`, `src/generate_ship_icons.py`,
`src/generate_faction_icons.py`, `src/generate_minor_faction_icons.py`, or
any of the game-file parsing logic, make sure `data/x4.db` and
`data/images/` already reflect that change (re-run the relevant
`extract_game_data.py --only <group>` + the regeneration script + `python
src/generate_ships_table.py`) *before* deploying -- otherwise the deploy
ships whatever stale data happens to be sitting in `data/`, not the new
code's actual output.

## 3. Smoke-test locally

Start the app locally (`python src/api.py` from `src/`, or `uvicorn
api:app` from `src/`) and sanity-check whatever the Development section
claims changed. This project has no automated test suite, so this is the
only real check before something goes live.

## 4. (Optional but recommended) Deploy to staging first

```
flyctl deploy --config fly.staging.toml --app x4-staging
```

Verify at [x4-staging.fly.dev](https://x4-staging.fly.dev). Staging has
its own separate Tigris storage bucket, so nothing tested there can affect
real production share-link data. This step can be skipped for a trivial
change, but is the whole reason staging exists for anything riskier.

**Stop here and ask the user to confirm staging actually looks right**
before touching anything else. Report what you checked, then wait for
their go-ahead -- don't move on to step 5 on your own judgment alone, even
if everything you tested looks fine.

## 5. Pick the new version number

Semantic Versioning (`MAJOR.MINOR.PATCH`), pre-1.0 so still `0.x.y`:

- **PATCH** (`0.3.1` -> `0.3.2`): only bug fixes, no new user-facing
  behavior.
- **MINOR** (`0.3.1` -> `0.4.0`): any new feature, even a small one.
- **MAJOR**: reserved for 1.0 itself / a genuine breaking change -- hasn't
  happened yet.

**Propose which bump type applies and why, then wait for the user to
confirm it** before writing the number into `CHANGELOG.md` or `VERSION` --
don't just pick one and proceed.

## 6. Update CHANGELOG.md

1. Retitle `## [Unreleased] - Development` to `## [<new version>] -
   <today's date> - Production`.
2. Remove `- Production` from whichever entry currently has it (there
   should only ever be one Production tag at a time).
3. Add a fresh, empty `## [Unreleased] - Development` section above the
   entry from step 1, ready for the next batch of changes.

## 7. Update VERSION

Set the repo-root `VERSION` file to the exact same number chosen in step
5. This is what `api.py` reads (`GET /api/config`'s `"version"` field) and
what the About page's "Built From" section shows as this tool's own
version -- it must match the CHANGELOG entry, or the two will visibly
disagree on the live site.

## 8. Commit and push to main

Draft the commit message first and show it to the user before running
anything -- **wait for explicit approval of the exact wording**, especially
which issues it references with `Fixes #N`/`Closes #N` (a closing keyword
in the commit message closes that issue the moment the push lands, before
there's any chance to check whether the issue is *actually* fully done --
see #12's history for exactly this mistake). Only after they confirm it:

```
git add -A
git commit -m "<the approved message>"
git push origin main
```

Commit *before* deploying, not after -- the deployed image should always
trace back to a real commit, not a mix of committed and uncommitted state
that's hard to reproduce later.

Push right after committing, not left for later -- `flyctl deploy` itself
builds from the local working directory, not from GitHub, so a deploy
*can* technically succeed without ever pushing, but that leaves the
site running code that doesn't match `main`, which defeats the point of
tracking it in git at all. Confirm the push actually landed before moving
on:

```
git status
```

should report `Your branch is up to date with 'origin/main'.` with a
clean working tree -- if it doesn't (e.g. the push was rejected because
`main` moved upstream), resolve that first rather than deploying anyway.

## 9. Deploy to production

```
flyctl deploy --app x4
```

## 10. Verify

```
curl -s https://x4.fly.dev/api/config
```

Confirm `"version"` matches what was just set in step 7, and spot-check
whatever the Development section's own bullets claimed changed.

## 11. Close out any resolved GitHub issues

If this deploy closes tracked issues that weren't already closed by a
`Fixes #N` commit message, close them manually with a short summary
comment (same pattern as issue #18's own closing writeup).

---

## Scripting this later

Steps 6/7 (changelog retitle + VERSION bump) and step 10 (post-deploy
verification) are the most mechanical and the best first candidates for a
real script -- they're pure text/file manipulation with no judgment calls.
Steps 1, 2, and 3 need a human (or an AI assistant) to actually decide
what's ready and confirm it works; steps 4, 8, 9, and 11 are already just
single commands and mostly need the script to sequence them correctly
(e.g. refuse to run step 9 if step 8's push hasn't actually landed on
`origin/main`, or if `git status` shows unrelated unstaged changes). A
script still needs to stop and prompt at the three mandatory checkpoints
noted at the top (post-staging, version bump, commit message) rather than
running straight through -- those aren't things to automate away, just to
make quick to answer.
