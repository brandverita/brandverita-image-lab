import { Button } from "@/components/ui/button";
import type { GenerationJob } from "@/lib/generationApi";

export type PanelState = "empty" | "loading" | "error" | "success";

interface ResultPanelProps {
  state: PanelState;
  job: GenerationJob | null;
  statusText?: string;
  errorMessage?: string | null;
  altText: string;
  onRetry: () => void;
}

export function ResultPanel({
  state,
  job,
  statusText,
  errorMessage,
  altText,
  onRetry,
}: ResultPanelProps) {
  if (state === "loading") {
    return (
      <div className="flex min-h-[22rem] flex-col items-center justify-center gap-4 rounded-lg border border-border bg-card p-8">
        <span
          role="status"
          aria-live="polite"
          className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-primary"
        >
          <span className="sr-only">Generation in progress</span>
        </span>
        <p className="text-sm text-muted-foreground">{statusText ?? "Generating your image…"}</p>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="min-h-[22rem] rounded-lg border border-destructive/30 bg-destructive/5 p-6">
        <h3 className="text-sm font-semibold text-destructive">Generation failed</h3>
        <p role="alert" className="mt-2 text-sm text-destructive/90">
          {errorMessage ?? "Something went wrong while generating this image."}
        </p>
        <Button variant="outline" className="mt-4" onClick={onRetry}>
          Retry
        </Button>
      </div>
    );
  }

  if (state === "success" && job?.result_url) {
    return (
      <div className="space-y-4 rounded-lg border border-border bg-card p-4">
        <img
          src={job.result_url}
          alt={altText}
          className="w-full rounded-md border border-border bg-muted object-contain"
        />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            {job.width ?? "?"} x {job.height ?? "?"} · job {job.job_id.slice(0, 8)}
          </p>
          <Button asChild>
            <a href={job.result_url} download target="_blank" rel="noreferrer">
              Download image
            </a>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[22rem] flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-card/60 p-8 text-center">
      <div className="h-10 w-10 rounded-md border border-border bg-muted" aria-hidden="true" />
      <p className="text-sm text-muted-foreground">
        No test generations yet. Create your first image from the form.
      </p>
    </div>
  );
}
