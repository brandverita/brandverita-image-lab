import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { AuthPanel } from "@/components/generation/AuthPanel";
import { GenerationForm } from "@/components/generation/GenerationForm";
import { RecentJobs } from "@/components/generation/RecentJobs";
import { ResultPanel, type PanelState } from "@/components/generation/ResultPanel";
import { useGeneration } from "@/hooks/use-generation";
import { useSupabaseSession } from "@/hooks/use-supabase-session";
import { API_BASE_URL, GENERATION_ENABLED, apiEnvironmentLabel } from "@/lib/generationApi";


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
  const { phase, job, errorMessage, statusText, submit, retry, isBusy, lastPrompt } =
    useGeneration();

  const apiConfigured = Boolean(API_BASE_URL) && GENERATION_ENABLED;

  const state: PanelState =
    phase === "submitting" || phase === "polling"
      ? "loading"
      : phase === "error"
        ? "error"
        : phase === "done"
          ? "success"
          : "empty";

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
            <StatusDot
              ok={apiConfigured}
              label={apiConfigured ? "Generation API configured" : "Generation API unavailable"}
            />
            <StatusDot
              ok={supabaseConfigured}
              label={supabaseConfigured ? "Supabase connected" : "Supabase not connected"}
            />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
        <div className="mb-6">
          <h2 className="text-left text-2xl font-semibold tracking-tight text-foreground">
            Text-to-image test run
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Submits a single Flux Schnell job to the BrandVerita Generation API and polls it until it
            completes. Results come only from the API — nothing here is simulated.
          </p>
        </div>

        {!apiConfigured ? (
          <div
            role="alert"
            className="mb-6 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
          >
            Generation is disabled for this environment because the Generation API URL is not
            configured. Set the API URL environment variable to run a test generation.
          </div>
        ) : null}

        <div className="grid gap-8 lg:grid-cols-2">
          <section aria-labelledby="form-heading" className="rounded-lg border border-border bg-card p-6">
            <h3 id="form-heading" className="mb-5 text-left text-sm font-semibold text-foreground">
              Generation request
            </h3>
            <GenerationForm isSubmitting={isBusy} disabled={!apiConfigured} onSubmit={submit} />
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
              altText={
                lastPrompt
                  ? `Generated image for the prompt: ${lastPrompt.slice(0, 120)}`
                  : "Generated test image"
              }
              onRetry={retry}
            />
          </section>
        </div>
      </main>

      <footer className="border-t border-border bg-card">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-4 text-xs text-muted-foreground">
          <span>API environment: {apiEnvironmentLabel()}</span>
          <span>Supabase: {supabaseConfigured ? "connected" : "not connected"}</span>
        </div>
      </footer>
    </div>
  );
}
