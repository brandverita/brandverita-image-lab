# WP2 integration steps — Module B (product scene, BFL)

Everything below happens in the existing staging deployment
`modal-project/phase1-v6-staging/`. No worker app change: Module B is a hosted
provider call, so there is nothing to build on GPU.

## 1. Copy files into `phase1-v6-staging/`

| From | To |
| --- | --- |
| `backend/phase2b/scene_presets.py` | `phase1-v6-staging/scene_presets.py` |
| `backend/phase2b/adapters/bfl_product_scene.py` | `phase1-v6-staging/adapters/bfl_product_scene.py` |
| `backend/phase2b/advanced.py` | `phase1-v6-staging/advanced.py` (overwrite) |
| `backend/phase2b/api.py` | `phase1-v6-staging/api.py` (overwrite) |

Delete `__pycache__` in both `phase1-v6-staging/` and `adapters/` afterwards.

## 2. Create the provider secret

```bash
modal secret create bfl-research-2b BFL_API_KEY=<your BFL API key>
```

It attaches only to `run_product_scene_job`. Do not add it to any other function
and do not put it in `.env` or the frontend.

## 3. Registry row

Run `backend/phase2b/wp2-registry-migration.sql` in the Supabase `comfy-ui` SQL
editor, then set the config hash with the API's own canonicalisation:

```bash
SUPABASE_URL=https://thspgkedjkiltrcimond.supabase.co \
SUPABASE_SERVICE_ROLE_KEY=<service role key> \
python backend/phase2b/tools/set_config_hash.py product_scene v1
```

Expected verify row: `testing / research_only / internal / f / f / {staging} / t`.

## 4. Deploy and confirm

```bash
cd modal-project/phase1-v6-staging
python -c "import api"      # import check before deploy
modal deploy api.py
curl -s $V6/health | python -m json.tool
```

`/health` must show:

```json
"product_scene_adapter": "bfl_product_scene",
"hosted_dispatch_enabled": true,
"modules": { "outpaint": true, "product_scene": true },
"workflows": ["...", "product_scene:v1", "..."]
```

`hosted_dispatch_enabled: false` means either
`HOSTED_PROVIDER_DISPATCH_ENABLED` or `PROVIDER_BFL_ENABLED` is off in the
`api_image` env block.

## 5. Controlled test

```bash
cd backend/phase2b/tests
V6=$V6 TOK_A=<staging JWT> SUPABASE_URL=https://thspgkedjkiltrcimond.supabase.co \
ASSET=/path/to/product.png python test_wp2_product_scene.py
```

Expect 16/16. Then paste the two SQL result sets the script prints
(`generation_assets` row and `transformation_eval_runs` row) so the WP2 build
manifest can be recorded.

## 6. Kill switch

To stop all hosted spend: set `HOSTED_PROVIDER_DISPATCH_ENABLED` to `"false"` in
the `api_image` `.env` block and `modal deploy api.py`. In-flight jobs fail with
`transformation_failed`; nothing is left half-written (no output row without
validated, hashed bytes).
