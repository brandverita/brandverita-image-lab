# Studio export package — Smart Resize/Outpaint + Product Scene

A self-contained handover folder Studio's team can lift out of this repository:
the exact contract, drop-in client code, a reference screen, and the list of what
must change before customers can use either feature.

Everything lands under a new `studio-export/` folder. No deployed service,
registry row, flag, or existing app file changes.

## What gets delivered

```text
studio-export/
  README.md                     entry point + how to use the package
  01-contract.md                endpoints, request/response, errors, gating
  02-catalogs.md                the two feature option catalogs
  03-integration-guide.md       step-by-step wiring for Studio
  04-production-readiness.md    what must change before customer use
  05-security-boundaries.md     what Studio must never do
  client/
    types.ts                    request/response + catalog types
    generationClient.ts         typed fetch client (create, poll, catalog, asset)
    useTransformation.ts        submit + poll hook, framework-agnostic React
  reference-ui/
    TransformationPanel.tsx     two-pane reference screen
    SourceAssetPicker.tsx       upload/select the input image
    OptionControls.tsx          enum-only controls for both modules
    ResultPane.tsx              signed-URL preview, download, error/retry
```

### 01-contract.md

- `POST /v1/generations` for both modules, with the exact accepted bodies
  (`outpaint:v1`: `source_asset_id`, `output_preset`, `expansion_mode`, `anchor`,
  `style_mode`; `product_scene:v1`: `source_asset_id`, `output_preset`,
  `scene_direction`, `background_style`, `preserve_subject`) plus
  `idempotency_key`.
- `GET /v1/generations/{job_id}` states and the lineage fields echoed back
  (`source_asset_id`, `output_asset_id`, `output_preset`).
- Asset endpoints: upload/finalise for inputs, short-lived `read_url` for
  outputs. No storage paths, no public URLs.
- `GET /v1/scene-presets` and the outpaint option catalog.
- Full error table with the client-facing meaning of each code
  (`workflow_not_available`, `asset_not_found`, `transformation_failed`,
  `provider_credential_missing`, 401/429/5xx behaviour) and the retry rule.
- The rejection rules Studio must respect: no free text, no geometry, no graph
  JSON, no provider names — anything outside the allow-list is refused server
  side.

### 02-catalogs.md

Enum keys plus display labels only, for both modules, and the four absolute
output presets each. Explicit note that instruction text is server-owned and
never returned.

### client/

Plain TypeScript, no dependency on this project's Supabase wiring: the client
takes a base URL and a token-getter callback. `useTransformation` performs
submit, 2-second polling, terminal-state halt, timeout, and manual retry —
mirroring the behaviour already proven in this app's generation hook.

### reference-ui/

Light neutral, two-pane, deep-blue primary; enum-only controls (dropdowns and
segmented buttons, never a text field); empty, loading, error and success
states; alt text and visible focus rings. Provided as copyable source, not wired
into this app's routes.

### 04-production-readiness.md

The blocking list, in order:

1. Registry: both rows are `testing / research_only / internal`, staging-only,
   `production_enabled=false`, `enabled_for_studio=false`. Studio dispatch is
   refused until a row is commercially approved *and* production-enabled.
2. Commercial approval per module — outpaint's checkpoint licence review, and a
   commercial agreement plus data-handling review for the hosted provider behind
   product scene.
3. A dedicated production Supabase project, separate from the permanent
   staging/Lab project; migrations, buckets, grants and RLS replayed there.
4. Production deployment with its own provider credential, its own flags, and
   `hosted_provider_dispatch` decided explicitly.
5. Metering handoff: this platform records usage rows only; credits, plan
   allowance and privileges stay with myaccount.brandverita.io. Names the rows
   Studio can read and the enforcement point it must call.
6. Latency/cost evidence to carry forward: outpaint 44.7s; product scene 16.7s
   warm after a 162.7s first call, $0.04/image estimate. p95 needs more samples.
7. Known limitation to state in Studio's own review: product scene re-renders
   the frame, so subject preservation is `unverified` and human-reviewed;
   outpaint verifies the original region byte-exactly.

### 05-security-boundaries.md

Never in Studio's client: service-role keys, provider keys, `STUDIO_HANDOFF_SECRET`,
storage paths, instruction text, workflow JSON. Outputs reach the browser only
through short-lived signed URLs after a server-side ownership check. Job status
is written by the platform, never by the client.

## Technical notes

- Docs are written from the accepted state in `module-a.md`, `module-b.md`,
  `scene_presets.py`, `advanced.py` and `api.py` — no new capability is implied.
- The reference UI and client are new files only; nothing in `src/` is modified,
  so the Lab app builds unchanged.
- Sizes, enum values and error codes are copied from the server modules rather
  than restated from memory, so the package cannot drift from the deployment at
  authoring time.
