# Fix the Netlify deployment

## What the log tells us

Two separate problems, in order:

1. `Build script returned non-zero exit code: 2` — the `bun run build` step itself
   failed. Netlify's resolved config shows only two env vars available at build
   time: `VITE_GENERATION_API_URL` and `VITE_GENERATION_ENABLED`. The Supabase
   vars are missing. `src/integrations/supabase/client.ts` throws when
   `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` are absent, and that
   throw happens during the build's server-render/prerender step, so the build
   aborts.
2. `Deploy directory 'dist/client' does not exist` — even on a green build this
   path is wrong for Netlify. The build defaults to a Cloudflare Worker target
   outside the Lovable sandbox, which writes to `.output/`. `dist/client` only
   exists inside Lovable's own build environment.

## The fix

### 1. Add the missing Netlify environment variables (you, in the Netlify UI)

Site settings -> Environment variables, add:

- `VITE_SUPABASE_URL` — `https://thspgkedjkiltrcimond.supabase.co`
- `VITE_SUPABASE_PUBLISHABLE_KEY` — the publishable/anon key from the comfy-ui project
- `VITE_SUPABASE_PROJECT_ID` — `thspgkedjkiltrcimond`

All three are client-safe by design (they ship in the browser bundle; RLS is the
real control). No service-role key, Modal token, or HF token goes here.

### 2. Build for Netlify instead of Cloudflare (code change)

Set an explicit Netlify deploy target in `vite.config.ts`:

```ts
export default defineConfig({
  tanstackStart: { server: { entry: "server" } },
  nitro: { preset: "netlify" },
});
```

The Netlify target writes static assets to `dist/` and the SSR handler to
`.netlify/functions-internal/`, and it emits the `_headers`/`_redirects` Netlify
needs. Lovable's own sandbox build overrides this preset internally, so the
Lovable preview keeps working unchanged.

### 3. Point Netlify at the right directory

Add a committed `netlify.toml` so the paths live in the repo instead of the UI:

```toml
[build]
  command = "bun run build"
  publish = "dist"
```

Then in Netlify UI, clear the `publish` override (currently
`/opt/build/repo/dist/client`, origin `ui`) so `netlify.toml` wins — a UI value
takes precedence over the file.

### 4. Ignore the new build artifact

Add `.netlify` to `.gitignore`.

## Order of operations

1. I make the code changes (steps 2-4).
2. You add the three Supabase env vars and clear the publish-directory override.
3. Trigger a redeploy.

## Notes

- This app is server-rendered, so it needs Netlify Functions, not a pure static
  deploy. The Netlify preset handles that automatically; nothing else to
  configure.
- No Supabase, RLS, or migration changes. No server routes added to this
  project. No secrets introduced.
- If the redeploy still fails, the next thing to read is the full `vite build`
  output above the "Configuration error" block — that will name the exact
  module if something other than the env vars is breaking.
