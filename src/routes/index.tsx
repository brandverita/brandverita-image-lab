import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";

import { GenerationForm } from "@/components/generation/GenerationForm";
import { RecentJobs } from "@/components/generation/RecentJobs";
import { ResultPanel, type PanelState } from "@/components/generation/ResultPanel";
import { SignInScreen } from "@/components/generation/SignInScreen";
import { Button } from "@/components/ui/button";
import { useAccessCheck } from "@/hooks/use-access";
import { useGeneration } from "@/hooks/use-generation";
import { useSupabaseSession } from "@/hooks/use-supabase-session";
import { supabase } from "@/integrations/supabase/client";
import {
  API_BASE_URL,
  API_CONFIGURED,
  GENERATION_ENABLED,
  apiEnvironmentLabel,
  checkHealth,
  type HealthInfo,
} from "@/lib/generationApi";


export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "BrandVerita Generation Test — Flux Schnell text-to-image" },
      {
        name: "description",
        content:
          "Internal development harness for the BrandVerita Generation API: submit a Flux Schnell text-to-image job and inspect the returned result.",
      },
      { property: "og:title", content: "BrandVerita Generation Test" },
      {
        property: "og:description",
        content:
          "Internal development harness for the BrandVerita Generation API: submit a Flux Schnell text-to-image job and inspect the returned result.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
      { name: "robots", content: "noindex, nofollow" },
    ],
  }),
  component: Index,
});

const supabaseConfigured = Boolean(import.meta.env["VITE_SUPABASE_URL"]);

type HealthState =
  | { kind: "checking" }
  | { kind: "ok"; info: HealthInfo }
  | { kind: "unreachable" }
  | { kind: "not_configured" };

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-xs text-muted-foreground">
      <span
        aria-hidden="true"
        className={`h-2 w-2 rounded-full ${ok ? "bg-primary" : "bg-destructive"}`}
      />
      {label}
    </span>
  );
}

function Index() {
  const { session, loading: sessionLoading, userId } = useSupabaseSession();
  const { access } = useAccessCheck(userId);
  const authorized = Boolean(session) && access === "allowed";

  async function handleSignOut() {
    await supabase.auth.signOut();
  }

  const {
    phase,
    job,
    errorMessage,
    errorCode,
    statusText,
    elapsedMs,
    submit,
    retry,
    reset,
    refreshResultUrl,
    isBusy,
    lastPrompt,
  } = useGeneration();
  const [jobsRefreshKey, setJobsRefreshKey] = useState(0);
  const [health, setHealth] = useState<HealthState>(
    API_CONFIGURED ? { kind: "checking" } : { kind: "not_configured" },
  );

  const runHealthCheck = useCallback(async () => {
    if (!API_CONFIGURED) {
      setHealth({ kind: "not_configured" });
      return;
    }
    setHealth({ kind: "checking" });
    const info = await checkHealth();
    setHealth(info ? { kind: "ok", info } : { kind: "unreachable" });
  }, []);

  useEffect(() => {
    void runHealthCheck();
  }, [runHealthCheck]);

  useEffect(() => {
    if (phase === "done" || phase === "error") setJobsRefreshKey((key) => key + 1);
  }, [phase]);

  const healthOk = health.kind === "ok";

  // Never allow a submit before the Supabase session has settled — an unauthenticated
  // request is rejected by the API as a missing bearer token.
  const canGenerate = API_CONFIGURED && healthOk && !sessionLoading && Boolean(session);

  const unavailableReason = !API_BASE_URL
    ? "The Generation API URL is not configured for this environment."
    : !GENERATION_ENABLED
      ? "Generation is switched off for this environment."
      : health.kind === "unreachable"
        ? "The Generation API health check did not respond. The service may be starting up or offline."
        : null;

  const state: PanelState =
    phase === "submitting" || phase === "polling"
      ? "loading"
      : phase === "error"
        ? "error"
        : phase === "done"
          ? "success"
          : "empty";

  const apiStatusLabel =
    health.kind === "ok"
      ? "Generation API online"
      : health.kind === "checking"
        ? "Checking Generation API…"
        : health.kind === "unreachable"
          ? "Generation API unreachable"
          : "Generation API not configured";

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4">
          <div className="flex items-center gap-3">
            <h1 className="text-left text-lg font-semibold tracking-tight text-foreground">
              BrandVerita Generation Test
            </h1>
            <span className="rounded border border-border bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
              Development environment
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <StatusDot ok={health === "ok"} label={apiStatusLabel} />
            <StatusDot
              ok={supabaseConfigured}
              label={supabaseConfigured ? "Supabase connected" : "Supabase not connected"}
            />
            {session ? (
              <span className="flex items-center gap-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{session.user.email}</span>
                <Button variant="outline" size="sm" onClick={() => void handleSignOut()}>
                  Sign out
                </Button>
              </span>
            ) : null}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        {!authorized ? (
          sessionLoading || access === "checking" ? (
            <p className="text-sm text-muted-foreground">Checking access…</p>
          ) : (
            <SignInScreen
              unauthorizedEmail={session && access === "denied" ? (session.user.email ?? "") : null}
              onSignOut={() => void handleSignOut()}
            />
          )
        ) : (
        <>
        <div className="mb-6">
          <h2 className="text-left text-2xl font-semibold tracking-tight text-foreground">
            Text-to-image test run
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">

            Submits a single Flux Schnell job to the BrandVerita Generation API and polls it until it
            completes. Results come only from the API — nothing here is simulated.
          </p>
        </div>

        {unavailableReason ? (
          <div
            role="alert"
            className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          >
            <span>{unavailableReason}</span>
            {health === "unreachable" ? (
              <button
                type="button"
                onClick={() => void runHealthCheck()}
                className="rounded-md border border-destructive/40 px-3 py-1 text-xs font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                Check again
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="grid gap-8 lg:grid-cols-2">
          <section aria-labelledby="form-heading" className="rounded-lg border border-border bg-card p-6">
            <h3 id="form-heading" className="mb-5 text-left text-sm font-semibold text-foreground">
              Generation request
            </h3>
            <GenerationForm
              isSubmitting={isBusy}
              disabled={!canGenerate}
              onSubmit={submit}
              onReset={reset}
            />
          </section>

          <section aria-labelledby="result-heading" className="space-y-3">
            <h3 id="result-heading" className="text-left text-sm font-semibold text-foreground">
              Result
            </h3>
            <ResultPanel
              state={state}
              job={job}
              statusText={statusText}
              errorMessage={errorMessage}
              errorCode={errorCode}
              elapsedMs={elapsedMs}
              altText={
                lastPrompt
                  ? `Generated image for the prompt: ${lastPrompt.slice(0, 120)}`
                  : "Generated test image"
              }
              onRetry={retry}
              onRefreshResult={() => void refreshResultUrl()}
            />
          </section>
        </div>

        <section aria-labelledby="jobs-heading" className="mt-10 space-y-3">
          <h3 id="jobs-heading" className="text-left text-sm font-semibold text-foreground">
            Recent test jobs
          </h3>
          <RecentJobs userId={userId} refreshKey={jobsRefreshKey} />
        </section>
        </>
        )}
      </main>


      <footer className="border-t border-border bg-card">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4 text-xs text-muted-foreground">
          <span>API environment: {apiEnvironmentLabel()}</span>
          <span>API health: {health === "ok" ? "ok" : health.replace("_", " ")}</span>
          <span>Supabase: {supabaseConfigured ? "connected" : "not connected"}</span>
        </div>
      </footer>
    </div>
  );
}
