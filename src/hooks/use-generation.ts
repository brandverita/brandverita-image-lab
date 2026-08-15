import { useCallback, useEffect, useRef, useState } from "react";

import {
  createGeneration,
  getGeneration,
  isTerminalStatus,
  newIdempotencyKey,
  POLL_INTERVAL_MS,
  POLL_TIMEOUT_MS,
  GenerationApiError,
  type GenerationJob,
} from "@/lib/generationApi";
import type { GenerationFormValues } from "@/components/generation/GenerationForm";

type Phase = "idle" | "submitting" | "polling" | "done" | "error";

export function useGeneration() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusText, setStatusText] = useState<string>("Submitting job…");

  const lastRequest = useRef<{ values: GenerationFormValues; idempotencyKey: string } | null>(null);
  const cancelled = useRef(false);

  useEffect(() => () => {
    cancelled.current = true;
  }, []);

  const run = useCallback(async (values: GenerationFormValues, idempotencyKey: string) => {
    cancelled.current = false;
    setErrorMessage(null);
    setJob(null);
    setPhase("submitting");
    setStatusText("Submitting job…");

    try {
      const created = await createGeneration({
        prompt: values.prompt,
        negativePrompt: values.negativePrompt,
        width: values.width,
        height: values.height,
        idempotencyKey,
      });
      if (cancelled.current) return;
      setJob(created);

      if (isTerminalStatus(created.status)) {
        finish(created);
        return;
      }

      setPhase("polling");
      const deadline = Date.now() + POLL_TIMEOUT_MS;

      while (!cancelled.current) {
        if (Date.now() > deadline) {
          setPhase("error");
          setErrorMessage("This generation timed out. You can retry the request.");
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
        if (cancelled.current) return;

        const next = await getGeneration(created.job_id);
        if (cancelled.current) return;
        setJob(next);
        setStatusText(next.status === "queued" ? "Queued…" : "Rendering on the Generation API…");

        if (isTerminalStatus(next.status)) {
          finish(next);
          return;
        }
      }
    } catch (caught) {
      if (cancelled.current) return;
      setPhase("error");
      setErrorMessage(
        caught instanceof GenerationApiError
          ? caught.message
          : "Service temporarily unavailable. Please retry in a moment.",
      );
    }

    function finish(final: GenerationJob) {
      if (final.status === "completed" && final.result_url) {
        setPhase("done");
        return;
      }
      setPhase("error");
      setErrorMessage(
        final.status === "completed"
          ? "The job completed but no image was returned."
          : (final.error ?? "The Generation API reported a failed job."),
      );
    }
  }, []);

  const submit = useCallback(
    (values: GenerationFormValues) => {
      const idempotencyKey = newIdempotencyKey();
      lastRequest.current = { values, idempotencyKey };
      void run(values, idempotencyKey);
    },
    [run],
  );

  const retry = useCallback(() => {
    const previous = lastRequest.current;
    if (!previous) return;
    void run(previous.values, newIdempotencyKey());
  }, [run]);

  return {
    phase,
    job,
    errorMessage,
    statusText,
    submit,
    retry,
    isBusy: phase === "submitting" || phase === "polling",
    lastPrompt: lastRequest.current?.values.prompt ?? "",
  };
}
