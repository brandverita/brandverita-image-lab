# Smart resize invents a person: the instruction is telling it to

## What the two tests show

Your square sunset/seal image was placed correctly: it is centred, at the right
size, and your original pixels are untouched (the integrity check passed). Only
the two new side bands are wrong — they contain a woman's face and shoulders,
content that appears nowhere in your image.

That is not a login, caching or stale-result problem, and not the old
self-hosted model — this run went to the hosted service. The cause is the
instruction we send with the picture. It currently ends with a list of things
not to add: "Do not add new subjects, people, objects, text, logos, borders or
frames." This family of image models has no concept of "do not"; every noun in
that sentence is read as something to include. We literally asked for people.
Hence a face on both sides.

## The fix

- Rewrite the extension instruction as a short, purely positive description:
  continue the existing scene, sky, water, horizon line, lighting and grain to
  the edges. No "do not" clause, no list of forbidden nouns.
- Keep an explicit "empty instruction" variant available behind a server
  constant, since the hosted extend model works from the picture alone; whichever
  of the two reads better in your side-by-side becomes the default.
- The instruction stays server-owned: it is not accepted from the browser, and
  its exact text and fingerprint keep being recorded with every run.

## Everything protective stays as it is

Server-side download and digest check, server-computed placement from your
dropdown choices only, the credential never leaving the server, private storage,
your original pixels pasted back and verified byte-for-byte, per-run cost against
the research cap. None of that changes, and the registry row does not change.

## Technical detail

- `backend/phase2b/adapters/bfl_outpaint.py`: replace `EXPAND_INSTRUCTION` with a
  negation-free continuation prompt, add `EXPAND_INSTRUCTION_EMPTY` toggle
  (`OUTPAINT_V2_PROMPT_MODE` env: `guided` | `bare`, default `guided`), and record
  `instruction_sha256` / `instruction_chars` in provenance alongside the text
  hash so runs are comparable.
- `prompt_upsampling` stays `false` (upsampling would re-expand the prompt and
  reintroduce invented subjects); `safety_tolerance` unchanged.
- No registry change and no re-hash: `config_hash` covers key, version, provider,
  model, reference and schemas only — the prompt text is not part of it, so
  `outpaint:v2` and its fingerprint `ba3ab4912eaa…` stay valid.
- Docs updated: `backend/phase2b/module-a.md` records the negation failure mode
  and the two prompt modes, `roadmap.md` gets the WP1b follow-up line.

## What you will need to do

Copy the updated `adapters/bfl_outpaint.py` to the Modal V6 app, clear
`__pycache__`, `modal deploy api.py`, then run the same square image at
1200 x 627 twice — once as deployed (`guided`), once with
`OUTPAINT_V2_PROMPT_MODE=bare` — and tell me which side bands look better. If
either still invents a subject, the next step is a mild guidance/steps change on
our side, not a provider change.

## Out of scope

No change to Product Scene, Flux text-to-image, the self-hosted `outpaint:v1`
path, Studio enablement, or production.
