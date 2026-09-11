# Fix the 400 on Generate image (and name the missing field)

## What is actually wrong

Studio's request is correct in spirit but the service reads one field from the
wrong place.

Studio sends:

```json
{
  "workflow_id": "flux_text_to_image",
  "workflow_version": "v2",
  "inputs": { "prompt": "...", "width": 768, "height": 768 },
  "idempotency_key": "<unique-reference>"
}
```

The service supports two request shapes. When a nested `inputs` object is
present it validates **only** that object and ignores the rest of the body.
`idempotency_key` is a required member of that validated set, and Studio puts it
next to `inputs`, not inside it. So validation fails with exactly the observed
`400 invalid_request / "Field required"` — the missing field is
`inputs.idempotency_key`.

Two secondary problems the log exposes:

- The error message drops the field name, which is why the Studio team could not
  identify it. Only the message text (`"Field required"`) is returned, never the
  field path.
- Advanced (asset-to-asset) requests already read `idempotency_key` with a
  top-level-tolerant fallback, so the two paths behave inconsistently today.

## Changes (Generation API only)

All edits in `backend/phase2b/api.py`. No registry, database, worker, adapter,
provider, or Studio change. No change to limits, gates, or which workflows are
offered.

1. **Accept the key from either position.** Before validating the normalized
   input set, if the nested `inputs` object carries no `idempotency_key`, take
   the top-level one from the body. Nested value wins when both are present.
   This makes the structured shape behave like the advanced path already does,
   and keeps the legacy flat shape untouched.

2. **Return the field path in validation errors.** Build the detail as
   `invalid_request: <field>: <message>` from the first validation error's
   location, prefixed with `inputs.` for the structured shape. A future missing
   field is then self-diagnosing for the calling team. Still no prompt text,
   token, or payload echoed — field names and validation messages only.

3. **Keep everything else as is.** Same 2000/1000 character limits, same
   registry `input_schema` enforcement, same dimension allow-list, same
   idempotency replay behaviour keyed on that value.

## Reply to send to the Studio team

The missing field is `idempotency_key`, and it must sit **inside** `inputs`:

```json
{
  "workflow_id": "flux_text_to_image",
  "workflow_version": "v2",
  "inputs": {
    "prompt": "<prompt>",
    "width": 768,
    "height": 768,
    "idempotency_key": "<unique-reference>"
  }
}
```

After the service change above, the top-level position they use today will also
be accepted, so they can ship either shape. Nothing else about their request
needs to change: no `origin`, no provider, no source image, `v2` is correct.

## Verification

1. Redeploy the API (copy `api.py` into the Modal staging folder, clear
   `__pycache__`, `modal deploy api.py`, confirm `/health`).
2. POST with `idempotency_key` top-level only — expect a job id, not a 400.
3. POST with it inside `inputs` — same result.
4. POST with no `idempotency_key` anywhere — expect
   `400 invalid_request: inputs.idempotency_key: Field required`.
5. Re-run one Smart resize and one Product scene run to confirm the advanced
   path is unaffected, then one Generate image run from Studio end to end.

## Your action

Copy the amended `api.py` to the Modal staging folder and deploy; then pass the
reply above to the Studio team.
