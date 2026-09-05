/**
 * Studio export — result pane: empty, loading, error and success states.
 *
 * The image is shown from a short-lived signed URL. When a download fails
 * because the link aged out, ask for a fresh one instead of caching it.
 */

import type { TransformationJob } from "../client/types";
import type { TransformationPhase } from "../client/useTransformation";

export function ResultPane({
  phase,
  job,
  resultUrl,
  errorMessage,
  onRetry,
  onRefreshUrl,
}: {
  phase: TransformationPhase;
  job: TransformationJob | null;
  resultUrl: string | null;
  errorMessage: string | null;
  onRetry: () => void;
  onRefreshUrl: () => void;
}) {
  return (
    <section
      aria-labelledby="result-heading"
      aria-live="polite"
      className="flex min-h-[28rem] flex-col rounded-lg border border-slate-200 bg-white p-6"
    >
      <h2 id="result-heading" className="text-left text-sm font-semibold text-slate-900">
        Result
      </h2>

      <div className="mt-4 flex flex-1 items-center justify-center">
        {phase === "idle" ? (
          <p className="max-w-xs text-center text-sm text-slate-500">
            No image yet. Choose a picture and a style on the left, then create your image.
          </p>
        ) : null}

        {phase === "submitting" || phase === "running" ? (
          <div className="flex flex-col items-center gap-3 text-center">
            <span
              aria-hidden="true"
              className="h-6 w-6 animate-spin rounded-full border-2 border-slate-300 border-t-blue-600"
            />
            <p className="text-sm text-slate-600">
              {phase === "submitting" ? "Sending your request…" : "Creating your image…"}
            </p>
            <p className="text-xs text-slate-500">This usually takes under a minute.</p>
          </div>
        ) : null}

        {phase === "error" ? (
          <div className="w-full rounded-md bg-red-50 p-4 text-left">
            <p role="alert" className="text-sm font-medium text-red-800">
              {errorMessage ?? "Something went wrong. Please try again."}
            </p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 rounded-md bg-blue-700 px-3 py-2 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
            >
              Try again
            </button>
          </div>
        ) : null}

        {phase === "done" && resultUrl ? (
          <figure className="w-full">
            <img
              src={resultUrl}
              alt={`Generated image, ${job?.width ?? ""} by ${job?.height ?? ""} pixels`}
              className="mx-auto max-h-[22rem] w-auto rounded border border-slate-200"
            />
            <figcaption className="mt-2 text-center text-xs text-slate-500">
              {job?.output_preset ? `${job.output_preset.replace("x", " x ")} px` : null}
            </figcaption>
          </figure>
        ) : null}
      </div>

      {phase === "done" && resultUrl ? (
        <div className="mt-4 flex items-center justify-between gap-3">
          <a
            href={resultUrl}
            download
            className="rounded-md bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
          >
            Download image
          </a>
          <button
            type="button"
            onClick={onRefreshUrl}
            className="text-sm font-medium text-blue-700 underline hover:text-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
          >
            Link expired? Refresh it
          </button>
        </div>
      ) : null}
    </section>
  );
}
