/**
 * Studio export — submit + poll hook for both transformation features.
 *
 * Framework-agnostic React (no router, no data library). Behaviour mirrors the
 * accepted Lab implementation: single submit, 2s polling, halt on any terminal
 * status, hard timeout with manual retry, and a fresh signed URL on demand.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  isTerminalStatus,
  newIdempotencyKey,
  POLL_INTERVAL_MS,
  POLL_TIMEOUT_MS,
  type GenerationClient,
} from "./generationClient";
import { TransformationApiError, type TransformationJob, type TransformationRequest } from "./types";

export type TransformationPhase = "idle" | "uploading" | "submitting" | "running" | "done" | "error";

export interface UseTransformationResult {
  phase: TransformationPhase;
  job: TransformationJob | null;
  /** Short-lived signed URL for the finished image, or null. */
  resultUrl: string | null;
  errorMessage: string | null;
  isBusy: boolean;
  start: (request: TransformationRequest) => Promise<void>;
  retry: () => Promise<void>;
  reset: () => void;
  refreshResultUrl: () => Promise<void>;
}

export function useTransformation(client: GenerationClient): UseTransformationResult {
  const [phase, setPhase] = useState<TransformationPhase>("idle");
  const [job, setJob] = useState<TransformationJob | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelled = useRef(false);
  const lastRequest = useRef<TransformationRequest | null>(null);
  const idempotencyKey = useRef<string | null>(null);

  const clearTimer = useCallback(() => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
      clearTimer();
    };
  }, [clearTimer]);

  const fail = useCallback((message: string) => {
    setPhase("error");
    setErrorMessage(message);
  }, []);

  const poll = useCallback(
    (jobId: string, deadline: number) => {
      clearTimer();
      timer.current = setTimeout(async () => {
        if (cancelled.current) return;
        try {
          const next = await client.getJob(jobId);
          if (cancelled.current) return;
          setJob(next);

          if (next.status === "completed") {
            setResultUrl(next.result_url ?? null);
            setPhase("done");
            return;
          }
          if (isTerminalStatus(next.status)) {
            fail(
              next.error_message ||
                (next.error_code === "provider_credential_missing"
                  ? "This feature is temporarily unavailable. The team has been notified."
                  : "The image could not be created. Please try again."),
            );
            return;
          }
          if (Date.now() > deadline) {
            fail("This is taking longer than expected. You can try again.");
            return;
          }
          poll(jobId, deadline);
        } catch (error) {
          if (cancelled.current) return;
          fail(
            error instanceof TransformationApiError
              ? error.message
              : "Something went wrong while checking progress. Please try again.",
          );
        }
      }, POLL_INTERVAL_MS);
    },
    [clearTimer, client, fail],
  );

  const submit = useCallback(
    async (request: TransformationRequest, key: string) => {
      setPhase("submitting");
      setErrorMessage(null);
      setResultUrl(null);
      try {
        const created = await client.createTransformation(request, key);
        if (cancelled.current) return;
        setJob(created);
        if (created.status === "completed") {
          setResultUrl(created.result_url ?? null);
          setPhase("done");
          return;
        }
        if (isTerminalStatus(created.status)) {
          fail(created.error_message || "The image could not be created. Please try again.");
          return;
        }
        setPhase("running");
        poll(created.job_id, Date.now() + POLL_TIMEOUT_MS);
      } catch (error) {
        if (cancelled.current) return;
        fail(
          error instanceof TransformationApiError
            ? error.message
            : "The request could not be sent. Please try again.",
        );
      }
    },
    [client, fail, poll],
  );

  const start = useCallback(
    async (request: TransformationRequest) => {
      clearTimer();
      lastRequest.current = request;
      idempotencyKey.current = newIdempotencyKey();
      await submit(request, idempotencyKey.current);
    },
    [clearTimer, submit],
  );

  /** Retries the same submission with the same key — safe and non-duplicating. */
  const retry = useCallback(async () => {
    const request = lastRequest.current;
    if (!request) return;
    clearTimer();
    await submit(request, idempotencyKey.current ?? newIdempotencyKey());
  }, [clearTimer, submit]);

  const reset = useCallback(() => {
    clearTimer();
    lastRequest.current = null;
    idempotencyKey.current = null;
    setJob(null);
    setResultUrl(null);
    setErrorMessage(null);
    setPhase("idle");
  }, [clearTimer]);

  const refreshResultUrl = useCallback(async () => {
    if (!job?.job_id) return;
    try {
      setResultUrl(await client.getFreshResultUrl(job.job_id));
    } catch {
      fail("The download link could not be refreshed. Please try again.");
    }
  }, [client, fail, job?.job_id]);

  return {
    phase,
    job,
    resultUrl,
    errorMessage,
    isBusy: phase === "uploading" || phase === "submitting" || phase === "running",
    start,
    retry,
    reset,
    refreshResultUrl,
  };
}
