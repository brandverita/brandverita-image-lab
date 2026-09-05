# 02 — Option catalogs

Everything a user can choose is an enum key. Labels below are the wording used in
the Lab; Studio may re-label for customers but must send the exact keys.

The instruction text behind each option lives in the server image and is covered
by the workflow config hash. It is never returned to a client and never logged.
Changing an option is a server code change plus a registry version bump — not a
runtime setting.

---

## Smart Resize / Outpaint — `outpaint:v1`

Output presets (absolute pixel sizes, no client geometry):

| Key | Size |
| --- | --- |
| `1200x627` | 1200 x 627 |
| `1600x900` | 1600 x 900 |

`params`:

| Field | Allowed values | Notes |
| --- | --- | --- |
| `expansion_mode` | `anchor_directional` | Only value. Send it explicitly. |
| `direction` | `left`, `right`, `top`, `bottom`, `symmetric` | Where the **new** pixels go. |
| `anchor` | depends on `direction` (below) | Where the source is pinned. |
| `style_mode` | `preserve_source` | Only value. |

Valid `direction` / `anchor` combinations — anything else is 400:

| direction | allowed anchor | result |
| --- | --- | --- |
| `left` | `right`, `center` | source flush right, or centred |
| `right` | `left`, `center` | source flush left, or centred |
| `top` | `bottom`, `center` | source flush bottom, or centred |
| `bottom` | `top`, `center` | source flush top, or centred |
| `symmetric` | `center` | source centred on both axes |

Behaviour worth surfacing in the UI: the source is never upscaled. It is
downscaled only when it does not fit the canvas. The original source region is
composited back byte-exactly after generation and hash-verified, so the user's
own pixels are guaranteed unchanged.

Suggested labels: Extend left / Extend right / Extend top / Extend bottom /
Extend both sides; anchor as "Keep image at right edge" / "Centre the image".

---

## Product Background / Scene — `product_scene:v1`

Output presets:

| Key | Size | Typical use |
| --- | --- | --- |
| `1080x1080` | 1080 x 1080 | square social |
| `1080x1350` | 1080 x 1350 | portrait social |
| `1200x627` | 1200 x 627 | link/banner |
| `1600x900` | 1600 x 900 | wide banner |

`params`:

| Field | Allowed values | Notes |
| --- | --- | --- |
| `scene_direction` | `clean_studio`, `premium_neutral`, `warm_lifestyle`, `natural_surface` | Fetch labels from `GET /v1/scene-presets`. |
| `background_style` | `neutral`, `soft_shadow`, `high_key`, `editorial` | Lighting/finish modifier. Defaults to `neutral`. |
| `preserve_subject` | `true` | Must be `true`. `false` is rejected. |

Labels returned by the catalog endpoint today:

| Key | Label |
| --- | --- |
| `clean_studio` | Clean studio |
| `premium_neutral` | Premium neutral |
| `warm_lifestyle` | Warm lifestyle |
| `natural_surface` | Natural surface |

Prefer the live catalog over this table so a server-side preset change reaches
Studio without a redeploy. Fall back to these keys if the call fails.

Honest limitation to reflect in the UI copy: this module re-renders the whole
frame, so there is no byte-exact region to verify. Provenance records
`subject_preserved: "unverified"`. Tell users to review the result before use;
do not claim the product is untouched.
