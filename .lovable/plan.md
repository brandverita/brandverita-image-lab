# Local layout check — phase2b-research-worker

## Verdict: your local structure is correct

The screenshot shows `modal-project/phase2b-research-worker/` containing `research_worker.py` and `outpaint_graph.py` **side by side** (plus `__pycache__`). That is exactly what is required — there must be **no `worker/` subfolder** on your machine.

Reason: `research_worker.py` does `.add_local_file("outpaint_graph.py", "/root/outpaint_graph.py", copy=True)` and later `import outpaint_graph`. Both paths are resolved relative to the file's own directory, so the two files must be flat siblings.

The `worker/` folder only exists in this repo (`backend/phase2b/worker/`) as the source location to copy from.

## Expected local tree

```text
modal-project/
  phase1-v6-staging/      api.py, registry.py, jobs.py, assets.py, advanced.py,
                          outpaint_geometry.py, adapters/modal_research_outpaint.py
  phase2b-research-worker/
    research_worker.py
    outpaint_graph.py
  v5-current/
```

## Two things to confirm before deploying

1. Delete `phase2b-research-worker/__pycache__` — stale bytecode from the earlier gated-repo build can shadow the re-pinned graph module.
2. Confirm both files are the latest versions (ungated `sd-v1-5-inpainting.ckpt`, sha256 `c6bbc15e…`, build-time weight fetch). If unsure, re-download both from the repo.

## Then

```bash
cd modal-project/phase2b-research-worker
modal deploy research_worker.py     # ~4.3 GB fetch, fails loudly on digest mismatch

cd ../phase1-v6-staging
modal deploy api.py
curl -s .../health                  # expect advanced_flags_enabled: true
```

Then run `tests/test_wp1_outpaint.py` end to end — it no longer pauses for flag flips — and paste the output so the WP1 build manifest can be recorded.
