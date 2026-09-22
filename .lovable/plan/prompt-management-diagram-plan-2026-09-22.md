# Prompt Management Diagram Plan

## Goal
Create a clear diagram for managing Product Scene and Editorial Layout prompts, focused on diagnosing dark / underexposed outputs like the sunglasses example.

## What the diagram will show
- The two separate prompt systems:
  - Product Scene: scene direction + background style + preset variant.
  - Editorial Layout: look + people option + copy zone + local typography.
- Which parts are server-owned, fixed, and fingerprinted.
- Where brightness, exposure, copy-safe zones, subject preservation, and final text placement are controlled.
- A feedback loop from test results into scored prompt changes, without letting the UI send free-text provider prompts.

## Current diagnosis to represent
- Product Scene already has a brighter `v2` preset variant path.
- Editorial Layout currently has look wording that can push scenes darker, especially `cover_shot`, which uses language like deep muted backdrop, strong directional key light, and falloff.
- The underexposed editorial output should be treated as a prompt-layer tuning issue first, not as a Studio/account/dispatch issue.

## Proposed diagram structure
```text
Source image
  -> Module choice
      -> Product Scene prompt layers
          -> Scene direction
          -> Background style
          -> Brightness variant
          -> BFL edit
          -> Exact-size output
          -> Eval score
      -> Editorial Layout prompt layers
          -> Editorial look
          -> People option
          -> Copy-safe zone
          -> BFL clean picture
          -> Brightness / exposure check
          -> Local typography layer
          -> Eval score
  -> Prompt change decision
      -> Keep preset
      -> Add brighter variant
      -> Split look into variants
      -> Retire weak preset
```

## Deliverable after approval
- A standalone Mermaid diagram file for prompt analysis and management.
- A short companion note explaining how to read it and where the underexposure control points are.
- No code or prompt changes unless you ask for that separately.

## Technical details
- The diagram will keep the existing safety boundary: enum-only UI choices, server-owned prompt text, config-hash/fingerprint traceability, and local typography for Editorial Layout.
- The prompt management loop will separate image-model prompt tuning from typography tuning, because Editorial Layout has two outputs: clean picture and final typeset layout.
- The diagram will include a safe “brightness ladder” for evaluation: current wording, bright/even variant, high-key variant, and retire/replace decision.
