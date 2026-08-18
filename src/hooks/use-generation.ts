import { useCallback, useEffect, useRef, useState } from "react";

import {
  createGeneration,
  getFreshResultUrl,
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

export function useGeneration(accessToken: string | null) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [statusText, setStatusText] = useState<string>("Submitting job…");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const tokenRef = useRef(accessToken);
  tokenRef.current = accessToken;

  const lastRequest = useRef<{ values: GenerationFormValues; idempotencyKey: string } | null>(null);
  const cancelled = useRef(false);

  useEffect(
    () => () => {
      cancelled.current = true;
    },
    [],
  );

  // Elapsed-time ticker, stopped as soon as the job reaches a terminal state.
  useEffect(() => {
    if (startedAt === null) return;
    if (phase !== "submitting" && phase !== "polling") return;
    const id = setInterval(() => setElapsedMs(Date.now() - startedAt), 250);
    return () => clearInterval(id);
  }, [startedAt, phase]);

  const run = useCallback(async (values: GenerationFormValues, idempotencyKey: string) => {
    cancelled.current = false;
    const began = Date.now();
    setErrorMessage(null);
    setErrorCode(null);
    setJob(null);
    setStartedAt(began);
    setElapsedMs(0);
    setPhase("submitting");
    setStatusText("Submitting job…");

    function finish(final: GenerationJob) {
      setElapsedMs(Date.now() - began);
      if (final.status === "completed" && final.result_url) {
        setPhase("done");
        return;
      }
      setPhase("error");
      setErrorCode(final.error_code ?? null);
      setErrorMessage(
        final.status === "completed"
          ? "The job completed but no image was returned."
          : (final.error_message ?? "The Generation API reported a failed job."),
      );
    }

    try {
      const created = await createGeneration({
        prompt: values.prompt,
        negativePrompt: values.negativePrompt,
        width: values.width,
        height: values.height,
        seed: values.seed,
        idempotencyKey,
        accessToken: tokenRef.current,
      });
      if (cancelled.current) return;
      setJob(created);

      if (isTerminalStatus(created.status)) {
        finish(created);
        return;
      }

      setPhase("polling");
      setStatusText("Queued…");
      const deadline = began + POLL_TIMEOUT_MS;

      while (!cancelled.current) {
        if (Date.now() > deadline) {
          setPhase("error");
          setElapsedMs(Date.now() - began);
          setErrorMessage("This generation timed out. You can retry the request.");
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
        if (cancelled.current) return;

        const next = await getGeneration(created.job_id, tokenRef.current);
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
      setElapsedMs(Date.now() - began);
      setErrorMessage(
        caught instanceof GenerationApiError
          ? caught.message
          : "Service temporarily unavailable. Please retry in a moment.",
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

  const reset = useCallback(() => {
    cancelled.current = true;
    lastRequest.current = null;
    setPhase("idle");
    setJob(null);
    setErrorMessage(null);
    setErrorCode(null);
    setStartedAt(null);
    setElapsedMs(0);
  }, []);

  /** Signed URLs are short-lived; re-sign through the API instead of guessing. */
  const refreshResultUrl = useCallback(async () => {
    const current = job;
    if (!current) return;
    try {
      const fresh = await getFreshResultUrl(current.job_id, tokenRef.current);
      if (!fresh) {
        setPhase("error");
        setErrorMessage("The stored result is no longer available. Re-run the generation to view it.");
        return;
      }
      setJob({ ...current, result_url: fresh });
    } catch (caught) {
      setPhase("error");
      setErrorMessage(
        caught instanceof GenerationApiError
          ? caught.message
          : "Could not refresh the result link. Re-run the generation to view it.",
      );
    }
  }, [job]);

  return {
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
    isBusy: phase === "submitting" || phase === "polling",
    lastPrompt: lastRequest.current?.values.prompt ?? "",
  };
}
