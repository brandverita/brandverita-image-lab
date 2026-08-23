import { Button } from "@/components/ui/button";
import { WORKFLOW_ID, type GenerationJob } from "@/lib/generationApi";

export type PanelState = "empty" | "loading" | "error" | "success";

interface ResultPanelProps {
  state: PanelState;
  job: GenerationJob | null;
  statusText?: string;
  errorMessage?: string | null;
  errorCode?: string | null;
  elapsedMs: number;
  altText: string;
  onRetry: () => void;
  onRefreshResult: () => void;
  onCheckNow: () => void;
}

function formatElapsed(ms: number): string {
  if (ms <= 0) return "—";
  const seconds = ms / 1000;
  return seconds < 60
    ? `${seconds.toFixed(1)}s`
    : `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
}

function DeveloperPanel({
  job,
  status,
  elapsedMs,
  errorCode,
}: {
  job: GenerationJob | null;
  status: string;
  elapsedMs: number;
  errorCode?: string | null | undefined;

}) {
  const rows: Array<[string, string]> = [
    ["Job ID", job?.job_id ?? "—"],
    ["Workflow ID", job?.workflow_id ?? WORKFLOW_ID],
    ["Workflow version", job?.workflow_version ?? "—"],
    ["Provider", job?.provider ?? "—"],
    ["Model", job?.provider_model ?? "—"],
    ["Config hash", job?.workflow_config_hash ? `${job.workflow_config_hash.slice(0, 12)}…` : "—"],
    ["Status", status],
    ["Progress", typeof job?.progress === "number" ? `${job.progress}%` : "—"],
    ["Modal call ID", job?.modal_call_id ?? "—"],
    ["Output path", job?.output_path ?? "—"],
    ["Seed", typeof job?.seed === "number" ? String(job.seed) : "—"],
    ["Elapsed", formatElapsed(elapsedMs)],
  ];
  if (errorCode) rows.push(["Error code", errorCode]);

  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-1 rounded-lg border border-border bg-muted/40 p-4 text-xs sm:grid-cols-2">
      {rows.map(([label, value]) => (
        <div key={label} className="flex items-baseline justify-between gap-3">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="truncate font-mono text-foreground" title={value}>
            {value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function ResultPanel({
  state,
  job,
  statusText,
  errorMessage,
  errorCode,
  elapsedMs,
  altText,
  onRetry,
  onRefreshResult,
  onCheckNow,
}: ResultPanelProps) {
  const statusLabel =
    state === "empty" ? "idle" : (job?.status ?? (state === "error" ? "failed" : "submitting"));

  let body: React.ReactNode;

  if (state === "loading") {
    const progress = typeof job?.progress === "number" ? job.progress : null;
      body = (
      <div className="flex min-h-[22rem] flex-col items-center justify-center gap-4 rounded-lg border border-border bg-card p-8">
        <span
          role="status"
          aria-live="polite"
          className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary"
        >
          <span className="sr-only">Generation in progress</span>
        </span>
        <p className="text-sm text-muted-foreground">{statusText ?? "Generating your image…"}</p>
        {progress !== null ? (
          <div
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-muted"
          >
            <div
              className="h-full rounded-full bg-primary transition-[width]"
              style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
            />
          </div>
        ) : null}
        <Button variant="outline" size="sm" onClick={onCheckNow}>
          Check now
        </Button>
      </div>
    );
  } else if (state === "error") {
    body = (
      <div className="min-h-[22rem] rounded-lg border border-destructive/30 bg-destructive/5 p-6">
        <h4 className="text-sm font-semibold text-destructive">Generation failed</h4>
        <p role="alert" className="mt-2 text-sm text-destructive/90">
          {errorMessage ?? "Something went wrong while generating this image."}
        </p>
        <Button variant="outline" className="mt-4" onClick={onRetry}>
          Retry
        </Button>
      </div>
    );
  } else if (state === "success" && job?.result_url) {
    body = (
      <div className="space-y-4 rounded-lg border border-border bg-card p-4">
        <img
          src={job.result_url}
          alt={altText}
          onError={onRefreshResult}
          className="w-full rounded-md border border-border bg-muted object-contain"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            {job.width ?? "?"} x {job.height ?? "?"}
            {job.completed_at ? ` · completed ${new Date(job.completed_at).toLocaleTimeString()}` : ""}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={onRefreshResult}>
              Refresh link
            </Button>
            <Button asChild>
              <a href={job.result_url} download target="_blank" rel="noreferrer">
                Download image
              </a>
            </Button>
          </div>
        </div>
      </div>
    );
  } else {
    body = (
      <div className="flex min-h-[22rem] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-card/60 p-8 text-center">
        <div className="h-10 w-10 rounded-md border border-border bg-muted" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">
          No test generations yet. Create your first image from the form.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {body}
      <DeveloperPanel job={job} status={statusLabel} elapsedMs={elapsedMs} errorCode={errorCode} />
    </div>
  );
}
