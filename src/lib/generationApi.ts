/**
 * Typed client for the BrandVerita Generation API.
 *
 * This is the ONLY module that talks to the Generation API. It never touches
 * Modal, ComfyUI, or GPU infrastructure directly, and it never logs prompts,
 * image payloads, or auth tokens.
 */

export const WORKFLOW_ID = "flux-schnell-txt2img-v1" as const;

export const DIMENSION_OPTIONS = [
  { label: "512 x 512", width: 512, height: 512 },
  { label: "768 x 768", width: 768, height: 768 },
  { label: "1024 x 1024", width: 1024, height: 1024 },
  { label: "1280 x 1024", width: 1280, height: 1024 },
  { label: "1024 x 1280", width: 1024, height: 1280 },
] as const;

export type DimensionValue = `${number}x${number}`;

export const PROMPT_MAX_LENGTH = 2000;
export const NEGATIVE_PROMPT_MAX_LENGTH = 1000;
export const POLL_INTERVAL_MS = 2000;
export const POLL_TIMEOUT_MS = 5 * 60 * 1000;

export const API_BASE_URL = (import.meta.env["VITE_GENERATION_API_URL"] ?? "").replace(/\/+$/, "");
export const GENERATION_ENABLED = import.meta.env["VITE_GENERATION_ENABLED"] !== "false";

export type JobStatus = "queued" | "running" | "completed" | "failed" | "canceled";

export interface GenerationJob {
  job_id: string;
  status: JobStatus;
  workflow_id: string;
  width?: number;
  height?: number;
  result_url?: string | null;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface CreateGenerationInput {
  prompt: string;
  negativePrompt?: string;
  width: number;
  height: number;
  idempotencyKey: string;
  accessToken?: string | null;
}

export type GenerationErrorKind =
  | "not_configured"
  | "unauthorized"
  | "rate_limited"
  | "invalid_request"
  | "not_found"
  | "server_error"
  | "network"
  | "timeout";

export class GenerationApiError extends Error {
  readonly kind: GenerationErrorKind;
  readonly status?: number;

  constructor(kind: GenerationErrorKind, message: string, status?: number) {
    super(message);
    this.name = "GenerationApiError";
    this.kind = kind;
    this.status = status;
  }
}

function errorFromStatus(status: number, detail?: string): GenerationApiError {
  if (status === 401 || status === 403) {
    return new GenerationApiError("unauthorized", "Session expired. Please sign in again.", status);
  }
  if (status === 404) {
    return new GenerationApiError("not_found", "This generation job could not be found.", status);
  }
  if (status === 429) {
    return new GenerationApiError(
      "rate_limited",
      "Limit reached. Please wait a moment before generating again.",
      status,
    );
  }
  if (status >= 400 && status < 500) {
    return new GenerationApiError(
      "invalid_request",
      detail?.slice(0, 200) || "The request was rejected. Check the form values and try again.",
      status,
    );
  }
  return new GenerationApiError(
    "server_error",
    "Service temporarily unavailable. Please retry in a moment.",
    status,
  );
}

async function request<T>(
  path: string,
  init: RequestInit & { accessToken?: string | null } = {},
): Promise<T> {
  if (!API_BASE_URL) {
    throw new GenerationApiError(
      "not_configured",
      "Generation API URL is not configured for this environment.",
    );
  }

  const { accessToken, headers, ...rest } = init;
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...(headers as Record<string, string> | undefined),
      },
    });
  } catch {
    throw new GenerationApiError("network", "Could not reach the Generation API.");
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      detail = (await response.text()).slice(0, 200);
    } catch {
      detail = undefined;
    }
    throw errorFromStatus(response.status, detail);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new GenerationApiError("server_error", "The Generation API returned an unreadable response.");
  }
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // RFC4122 v4 fallback
  return "10000000-1000-4000-8000-100000000000".replace(/[018]/g, (c) => {
    const n = Number(c);
    const r = Math.floor(Math.random() * 16);
    return (n ^ (r & (15 >> (n / 4)))).toString(16);
  });
}

export function createGeneration(input: CreateGenerationInput): Promise<GenerationJob> {
  return request<GenerationJob>("/v1/generations", {
    method: "POST",
    accessToken: input.accessToken,
    body: JSON.stringify({
      workflow_id: WORKFLOW_ID,
      idempotency_key: input.idempotencyKey,
      inputs: {
        prompt: input.prompt,
        negative_prompt: input.negativePrompt || undefined,
        width: input.width,
        height: input.height,
      },
    }),
  });
}

export function getGeneration(jobId: string, accessToken?: string | null): Promise<GenerationJob> {
  return request<GenerationJob>(`/v1/generations/${encodeURIComponent(jobId)}`, {
    method: "GET",
    accessToken,
  });
}

/** Coarse environment label derived from the API host — never the full URL. */
export function apiEnvironmentLabel(): string {
  if (!API_BASE_URL) return "not configured";
  try {
    const host = new URL(API_BASE_URL).hostname.toLowerCase();
    if (host === "localhost" || host === "127.0.0.1") return "local";
    if (host.includes("staging") || host.includes("stg")) return "staging";
    if (host.includes("dev")) return "development";
    return "remote";
  } catch {
    return "unknown";
  }
}

export function isTerminalStatus(status: JobStatus): boolean {
  return status === "completed" || status === "failed" || status === "canceled";
}
