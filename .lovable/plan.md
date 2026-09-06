# Smart resize: the "your pixels are unchanged" check is comparing the wrong thing

## What the evidence shows

The run `d537e304-…` failed with `RuntimeError: source_region_integrity_failed`,
`source_region_verified = false`, after the GPU work had already finished
successfully (worker booted, graph queued, `Prompt executed in 11.95 seconds`,
`wp1_worker_graph_done`, clean cleanup). So the image was generated; the job was
then rejected by its own final safety check.

That check works like this today: before generation, the placed source image is
saved as a PNG and hashed; after generation the same rectangle is cropped out of
the result, saved as a PNG again, and the two hashes are compared.

Reproduced locally with Pillow: when the uploaded image carries an embedded
colour profile (very common for images that come out of a browser or a phone),
the profile travels with the pre-generation copy and is written into its PNG, but
is **not** present on the rectangle cropped from the result. The two PNG files
then differ in size (929,548 vs 929,162 bytes) and therefore in hash — while the
actual pixels are byte-for-byte identical (`tobytes()` equal). Earlier test
images had no such profile, which is why the same code passed on 2026-09-01 and
fails on a Studio upload now.

So this is a false alarm in the verifier, not damaged pixels: PNG-encoded bytes
are not a canonical form for comparing pixels.

## The fix (one file)

In `backend/phase2b/outpaint_geometry.py`:

- Compute the source-region digest from the raw pixel buffer instead of a PNG
  file: hash `mode`, `width`, `height` and `tobytes()` of the placed source.
- Use the identical function on the cropped rectangle in
  `composite_and_verify`, so both sides hash the same canonical form.
- Keep everything else unchanged: same LANCZOS placement, same feathered mask,
  same paste-the-original-back-over-the-result step, same rule that an unverified
  result fails the job and writes no asset and no storage object.

The guarantee gets stronger, not weaker: it now compares actual pixels rather
than an encoder's output, so it cannot pass a genuinely altered region and cannot
fail on metadata.

No change to the adapter, the worker, the graph, the registry, Studio, Flux or
Product Scene.

## Deploy and verify

1. Copy the updated `outpaint_geometry.py` into
   `modal-project/phase1-v6-staging/`, delete `__pycache__`, and
   `modal deploy api.py`.
2. Re-run `backend/phase2b/tests/test_wp1_outpaint.py` — target 17/17.
3. Repeat the same Smart resize from Studio: same image, 1200 x 627, extend to
   the right. Expected: a result image, job `completed`, and a
   `transformation_eval_runs` row with `source_region_verified = true` at
   1200x627.
4. Record the outcome in `backend/phase2b/module-a.md` and note the fix in
   `roadmap.md`.

## Notes

- The `pydantic_settings`, `pyav`, `alembic` and `IMPORT FAILED: nodes_*` lines in
  the worker log are harmless upstream ComfyUI warnings for optional API nodes;
  the worker booted and executed the graph. Nothing to do there.
- Registry stays testing / research_only / internal / staging-only.
