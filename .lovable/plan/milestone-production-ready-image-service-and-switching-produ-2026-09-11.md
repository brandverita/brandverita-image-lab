# Milestone: production-ready image service, and switching Product scene on

Three things: freeze today's state as a named milestone, add an approved
Product scene entry so the Studio app can switch it on, and write down what a
duplicate test environment would involve without committing to it yet.

## 1. Name and freeze the milestone

Add `MILESTONE-2026-09-11.md` recording the accepted state:

- Generate image — self-hosted on Modal, approved, offered to the Studio app
- Smart resize — hosted with Black Forest Labs, approved, offered
- Product scene — hosted with Black Forest Labs, approved as of this milestone

For each: which service runs it, which model, the approval basis, measured
run time and per-run cost, and the exact fingerprint of its settings so a
future change is provable. Older experiment entries stay listed as
score-bench only. This is a document, not a code change.

## 2. Make Product scene available to the Studio app

Today's Product scene entry is marked research-only, which is why the Studio
app blocks it. Approved entries are never edited in place, so a new entry is
added alongside it:

- New `product_scene:v2`: same provider and same fixed server-owned scene
  presets, marked active, approved for commercial use, visible to the Studio
  app, enabled, allowed in both environments, with its own settings
  fingerprint.
- The existing `product_scene:v1` is left untouched as the research entry.
- The Studio app then sees Product scene in its own discovery call and can
  show it. Nothing about how it runs changes.

The user-facing disclosure work on the Studio side (third-party processing,
no personal-data uploads) stays an open item on the roadmap, tracked with the
same items already listed for Smart resize.

Then update the handover pack so the Studio team has one instruction:
Product scene is `product_scene`, version `v2`, same request shape as today.

## 3. Duplicate environment — shape only, no move

A short section in the milestone document covering what a second environment
actually requires, so the decision can be made later:

- A separate database project (jobs, assets, access rules, cleanup job
  replayed; nothing copies across)
- Its own service deployments and its own provider key
- Its own login/identity configuration
- Its own copies of the three approved entries, each restricted to that
  environment, with fresh fingerprints
- Which side keeps today's setup, and the fact that test and customer data
  must never share one project

No environment is created or moved in this step.

## Technical notes

- New registry row inserted via data SQL, then `set_config_hash.py product_scene v2`
  run against the staging project (needs the service-role key locally; it never
  enters app code).
- No change to `bfl_product_scene.py`, `advanced.py`, or `api.py` — the second
  admission path added on 2026-09-11 already admits active + studio_safe +
  production_enabled + approved rows, so `product_scene:v2` dispatches without
  a redeploy. Registry cache refreshes within 60s.
- Files touched: new `MILESTONE-2026-09-11.md`, `studio-export/README.md`,
  `studio-export/07-team-requests.md`, `studio-export/04-production-readiness.md`,
  `studio-export/client/types.ts`, `roadmap.md`.
- Still open after this: Modal redeploy of `advanced.py`/`outpaint_geometry.py`
  from the earlier tracks, and the Studio/myaccount actions already listed.
