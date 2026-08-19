# Re-test the session with a working console check

## Why that result means nothing

The app never assigns the Supabase client to `window`, so `window.supabase` is `undefined` on the live site. With the `?? {}` fallback, `data` is `undefined` and the log prints `has token: false` even when you are perfectly signed in. The check tested the wrong thing.

## Step 1 — Corrected diagnostic (no code changes, no redeploy)

Signed in on https://brandverita-image-lab.netlify.app, paste this in the console. It reads the session straight out of the storage key Supabase writes, and reports only booleans and an expiry — never the token itself.

```js
const k = Object.keys(localStorage).find(n => n.startsWith("sb-") && n.endsWith("-auth-token"));
const s = k ? JSON.parse(localStorage.getItem(k)) : null;
console.log({
  storageKeyFound: Boolean(k),
  hasAccessToken: Boolean(s?.access_token),
  expiresInSeconds: s?.expires_at ? s.expires_at - Math.floor(Date.now() / 1000) : null,
  user: s?.user?.email ? "present" : "absent",
});
```

Then, to test the API path with that token attached (prints status codes only):

```js
const k = Object.keys(localStorage).find(n => n.startsWith("sb-") && n.endsWith("-auth-token"));
const t = k ? JSON.parse(localStorage.getItem(k))?.access_token : null;
const r = await fetch("https://brandverita--brandverita-api-fastapi-app.modal.run/v1/generations", {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${t}` },
  body: JSON.stringify({
    workflow_id: "flux-schnell-txt2img-v1",
    prompt: "console connectivity test",
    width: 512, height: 512,
    idempotency_key: crypto.randomUUID(),
  }),
});
console.log("status", r.status, (await r.text()).slice(0, 200));
```

## How to read the outcomes

- `storageKeyFound: false` or `hasAccessToken: false` → there really is no session in this browser (magic-link redirect landed on a different origin, or storage is blocked). Fix: sign in again on the exact Netlify origin and confirm that origin is in Supabase URL Configuration.
- Token present, POST returns 200/202 → the API and your session are both fine; the failure was the app sending no token, which the fix already shipped in this project addresses. Next action is simply to redeploy the frontend and retest.
- Token present, POST returns 401 → the token itself is refused. Next step is inspecting the token's audience/issuer against the project the API validates with.
- Token present, POST returns 500 → the API cannot reach Supabase (secret naming/contents). That is the case the updated `api.py` reports honestly as `auth_backend_unavailable`.
- `expiresInSeconds` negative → an expired session that never refreshed; the shipped change reads a fresh token at call time and will resolve it.

## Step 2 — Then act on the result

- Frontend already reads a live token before each request, disables Generate until the session settles, and guards empty job ids. Deploy the current `main` to Netlify and retest through the UI.
- Redeploy `api.py` on Modal so 401 vs 500 stops being ambiguous; this is worth doing regardless, since it makes the next failure self-describing.
- No new code changes are proposed until the console output above says which branch we are in.

## Technical notes

- The diagnostic reads only `localStorage`; nothing is logged that reveals a token.
- No secrets, no server routes, and no schema changes are involved in this step.
