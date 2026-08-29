# Fix Phase 2A acceptance failures: animated-image rejection + test 16b crash

## Test result summary

24/26 automated checks passed. All security-critical checks pass: auth (401), type/size limits, magic-byte rejection of renamed foreign payloads (SVG/GIF/TIFF/HEIC/PDF/AVIF), decompression-bomb guard, signed-URL single-use, cross-user isolation (404s), private-bucket signed reads.

Two issues remain:

1. **Tests 11 FAIL (backend bug):** animated WebP and APNG uploads were accepted and finalized as `ready` instead of rejected with 422.
2. **Test 16b crash (test-script bug):** `SUPABASE_URL` was not set in the local shell, so `httpx.get()` crashed with `UnsupportedProtocol` before printing the summary. Manual checks 17/18 also still outstanding.

## Root cause

`validate_image()` in `backend/phase2a-v6/assets.py` detects animation via Pillow attributes only:

```python
if getattr(img, "n_frames", 1) > 1 or bool(img.info.get("is_animated")):
```

These are plugin- and Pillow-version-dependent. For PNG, APNG frame info (`n_frames`, `is_animated`) is only exposed by newer Pillow versions and never via `img.info`; on the Modal API image the check silently evaluates to "not animated" and the file passes. The check must not depend on the Pillow build.

Fix: detect animation at the container level before decoding — every APNG contains an `acTL` chunk, every animated WebP contains an `ANIM` RIFF chunk. Both are found with a simple byte scan of the header/file, regardless of Pillow version. This errs toward over-rejection (safe direction): a false positive just means a rare file with that byte sequence in compressed data is rejected, never that an animated file is accepted.

## Changes

### 1. `backend/phase2a-v6/assets.py` — harden animation detection

Add a container-level sniff used inside `validate_image()` before the Pillow decode:

```python
def is_animated_container(data: bytes, mime: str) -> bool:
    if mime == "image/png":
        return b"acTL" in data            # APNG animation control chunk
    if mime == "image/webp":
        return b"ANIM" in data[:64] or b"ANIM" in data  # RIFF ANIM chunk
    return False
```

- In `validate_image()`: after the magic-byte check, call `is_animated_container(data, declared_mime)` and raise `asset_validation_failed` ("Animated images are not supported.") when true.
- Keep the existing Pillow `n_frames`/`is_animated` check as a second layer (defense in depth).
- No API contract, schema, or limit changes. Rejection path (mark `rejected`, delete object, 422) is unchanged and already tested.

### 2. `backend/phase2a-v6/tests/test_assets_phase2a.py` — fail fast on missing env

- Add `SUPABASE_URL` to the required env vars at the top (`os.environ["SUPABASE_URL"]`), matching the existing `V6`/`TOK_A`/`TOK_B` pattern, and document it in the docstring. The crash becomes a clear `KeyError: 'SUPABASE_URL'` at startup instead of a mid-run traceback that hides the summary line.

### 3. Redeploy and re-verify (your actions, commands provided)

1. Copy the updated `assets.py` next to `api.py` in `modal-project/phase1-v6-staging/` and redeploy the V6 API app on Modal (same command as before).
2. Re-run the acceptance script with all four env vars:
   ```bash
   export V6=https://brandverita--brandverita-api-v6-fastapi-app.modal.run
   export TOK_A="<user A token>"   # brandverita@gmail.com
   export TOK_B="<user B token>"   # hi@brandverita.io
   export SUPABASE_URL="https://thspgkedjkiltrcimond.supabase.co"
   python tests/test_assets_phase2a.py
   ```
   Expected: 26/26 pass — tests 11 now reject animated WebP and APNG with 422, and 16b confirms the public bucket URL does not serve objects.
3. Run the remaining manual checks printed by the script:
   - SQL: `select public from storage.buckets where id='generation-assets';` → expect `false`.
   - One Flux V6 generation still completes end-to-end (regression check).
   - `select count(*) from usage_ledger;` → expect 0 (ledger still unwired).
   - V5 `/health` still reports version v5 (no V5 impact).

### 4. Note on cleanup

The two animated test files that were wrongly accepted reached `ready` status in the staging bucket. They are harmless (private bucket, 30-day TTL), but I can delete the two `generation_assets` rows + storage objects via SQL/service calls if you want a clean slate — say the word.

## Out of scope (unchanged)

No outpainting, Replicate/BFL dispatch, Studio UI, billing, production deployment, or usage-ledger wiring.
