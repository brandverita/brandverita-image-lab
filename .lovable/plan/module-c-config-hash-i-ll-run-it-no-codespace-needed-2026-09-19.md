# Module C — config hash: I'll run it (no Codespace needed)

**Answer to your question: I can run it — no Codespace.** I do it through the
connected `comfy-ui` project, so the service-role key is never pasted or handled
(the project's own connection holds it). The only reason it hasn't run yet: it
writes one field to the database, and I'm in read-only planning mode. Approve
this plan and I'll write it and read it back to confirm.

## Already done (read-only, just now)

- **Read the `editorial_layout:v1` row** — your migration inserted it correctly:
  `testing` / `research_only` / `internal`, staging-only, `requires_source_asset`
  true, and `config_hash` null (a fresh row, so it just needs the hash set).
- **Computed the exact hash** with the API's own canonicalisation and verified the
  method matches `registry.compute_config_hash` (registry.py lines 91–106): same
  8 fields, `json.dumps` with sorted keys + compact separators, SHA-256.

The hash to write:

```
ebb4603df70ac6a6b5fb0ebd357a3da3837d917f7362d79082cf43cc3ca4c0c6
```

## What I'll do on approval (one state-changing step)

Set `config_hash` to that value on the `editorial_layout:v1` row, then read it
back to confirm it stuck. Safe: a `testing` row isn't locked by the immutability
trigger, and `config_hash` is meant to be set exactly this way.

## Why not compute it in SQL

The migration warns that Postgres's JSON encoder doesn't reproduce Python's
compact, key-sorted encoding — a SQL-computed hash trips the
`config_hash_mismatch` tripwire on every request. I'm writing a **Python-computed**
value identical to what both `set_config_hash.py` and the running API produce, so
no tripwire.

## After that

- **Step 3 — capped eval batch (you):** a few editorial jobs from the Lab
  "Editorial layout" tab, score them, confirm rows under `editorial_layout`.
  Respect the $10 research cap.
- **Step 4 — close-out:** BFL disclosures, then decide Studio exposure (separate
  approval).

## Note

`roadmap.md` Track I updates are pending — plan mode locks all files except this
plan. I'll mark the deploy + migration + hash steps done once in build mode.
