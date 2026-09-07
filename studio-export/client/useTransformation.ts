/**
 * Studio export — submit + poll hook for both transformation features.
 *
 * Framework-agnostic React (no router, no data library). Behaviour mirrors the
 * accepted Lab implementation: single submit, 2s polling, halt on any terminal
 * status, hard timeout with manual retry, and a fresh signed URL on demand.
 *
 * Stale-result protection (WP1b): a finished image is only ever shown for the
 * run it belongs to.
 *  - every run carries a monotonically increasing `runId`; a late poll or submit
 *    response from a superseded run is discarded instead of being displayed;
 *  - the result is tagged with the run's context key (module + source asset).
 *    Call `syncContext(key)` on render with the current selection: when the key
 *    changes the previous result, job and error are cleared immediately, so a
 *    new source image can never show the previous image's output;
 *  - `refreshResultUrl()` only ever renews the current completed run.
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

/** Identity of the current selection: module/workflow plus source asset. */
export function transformationContextKey(
  workflowId: string,
  workflowVersion: string | null | undefined,
  sourceAssetId: string | null | undefined,
): string {
  return `${workflowId}:${workflowVersion ?? ""}:${sourceAssetId ?? ""}`;
}

export interface UseTransformationResult {
  phase: TransformationPhase;
  job: TransformationJob | null;
  /** Short-lived signed URL for the finished image, or null. */
  resultUrl: string | null;
  /** Context key the current result belongs to, or null when there is none. */
  resultKey: string | null;
  errorMessage: string | null;
  isBusy: boolean;
  start: (request: TransformationRequest) => Promise<void>;
  retry: () => Promise<void>;
  reset: () => void;
  refreshResultUrl: () => Promise<void>;
  /**
   * Declare the current selection. Any change (different module or different
   * source image) drops the previous result so nothing stale stays on screen.
   */
  syncContext: (key: string) => void;
}

export function useTransformation(client: GenerationClient): UseTransformationResult {
  const [phase, setPhase] = useState<TransformationPhase>("idle");
  const [job, setJob] = useState<TransformationJob | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [resultKey, setResultKey] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelled = useRef(false);
  const lastRequest = useRef<TransformationRequest | null>(null);
  const idempotencyKey = useRef<string | null>(null);
  const contextKey = useRef<string | null>(null);
  const runId = useRef(0);

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
    setResultUrl(null);
    setResultKey(null);
  }, []);


  const poll = useCallback(
    (jobId: string, deadline: number, id: number) => {
      clearTimer();
      timer.current = setTimeout(async () => {
        if (cancelled.current || id !== runId.current) return;
        try {
          const next = await client.getJob(jobId);
          // A response that belongs to a superseded run must never be shown.
          if (cancelled.current || id !== runId.current) return;
          setJob(next);

          if (next.status === "completed") {
            setResultUrl(next.result_url ?? null);
            setResultKey(contextKey.current);
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
          poll(jobId, deadline, id);
        } catch (error) {
          if (cancelled.current || id !== runId.current) return;
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
    async (request: TransformationRequest, key: string, id: number) => {
      setPhase("submitting");
      setErrorMessage(null);
      setResultUrl(null);
      setResultKey(null);
      setJob(null);
      try {
        const created = await client.createTransformation(request, key);
        if (cancelled.current || id !== runId.current) return;
        setJob(created);
        if (created.status === "completed") {
          setResultUrl(created.result_url ?? null);
          setResultKey(contextKey.current);
          setPhase("done");
          return;
        }
        if (isTerminalStatus(created.status)) {
          fail(created.error_message || "The image could not be created. Please try again.");
          return;
        }
        setPhase("running");
        poll(created.job_id, Date.now() + POLL_TIMEOUT_MS, id);
      } catch (error) {
        if (cancelled.current || id !== runId.current) return;
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
      runId.current += 1;
      await submit(request, idempotencyKey.current, runId.current);
    },
    [clearTimer, submit],
  );

  /** Retries the same submission with the same key — safe and non-duplicating. */
  const retry = useCallback(async () => {
    const request = lastRequest.current;
    if (!request) return;
    clearTimer();
    runId.current += 1;
    await submit(request, idempotencyKey.current ?? newIdempotencyKey(), runId.current);
  }, [clearTimer, submit]);

  const reset = useCallback(() => {
    clearTimer();
    runId.current += 1;
    lastRequest.current = null;
    idempotencyKey.current = null;
    setJob(null);
    setResultUrl(null);
    setResultKey(null);
    setErrorMessage(null);
    setPhase("idle");
  }, [clearTimer]);

  /**
   * Called on render with the current selection. A different module or a
   * different source image invalidates whatever is on screen: the previous
   * result is dropped and any in-flight run is orphaned by the runId bump.
   */
  const syncContext = useCallback(
    (key: string) => {
      if (contextKey.current === key) return;
      const first = contextKey.current === null;
      contextKey.current = key;
      if (!first) reset();
    },
    [reset],
  );

  const refreshResultUrl = useCallback(async () => {
    // Only the current, completed run can be refreshed — never a stale one.
    if (!job?.job_id || phase !== "done" || resultKey !== contextKey.current) return;
    const id = runId.current;
    try {
      const fresh = await client.getFreshResultUrl(job.job_id);
      if (cancelled.current || id !== runId.current) return;
      setResultUrl(fresh);
    } catch {
      fail("The download link could not be refreshed. Please try again.");
    }
  }, [client, fail, job?.job_id, phase, resultKey]);

  return {
    phase,
    job,
    // A result whose context no longer matches the selection is never exposed.
    resultUrl: resultKey !== null && resultKey === contextKey.current ? resultUrl : null,
    resultKey,
    errorMessage,
    isBusy: phase === "uploading" || phase === "submitting" || phase === "running",
    start,
    retry,
    reset,
    refreshResultUrl,
    syncContext,
  };
}

