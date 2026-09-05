/**
 * Studio export — typed Generation API client.
 *
 * Zero dependencies. Construct once with a base URL and an async token getter;
 * Studio keeps its own session handling.
 *
 *   const client = createGenerationClient({
 *     baseUrl: STUDIO_GENERATION_API_URL,
 *     getAccessToken: () => session.getAccessToken(),
 *   });
 *
 * Never log a request body, a signed URL or a token.
 */

import {
  ASSET_MAX_BYTES,
  ASSET_ALLOWED_TYPES,
  type AssetContentType,
  type AssetRecord,
  type ScenePresetCatalog,
  type TransformationJob,
  type TransformationRequest,
  TransformationApiError,
  type UploadAuthorization,
  type WorkflowInfo,
} from "./types";

export interface GenerationClientConfig {
  /** Generation API base URL for this environment, no trailing slash needed. */
  baseUrl: string;
  /** Returns a current Supabase access token, or null when signed out. */
  getAccessToken: () => Promise<string | null> | string | null;
}

export const POLL_INTERVAL_MS = 2000;
export const POLL_TIMEOUT_MS = 12 * 60 * 1000;

const TERMINAL: ReadonlySet<string> = new Set([
  "completed",
  "failed",
  "canceled",
  "cancelled",
  "expired",
]);

export function isTerminalStatus(status: string): boolean {
  return TERMINAL.has(status);
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2, 10)}`;
}

/* --------------------------------------------------------------------- */
/* Error mapping                                                         */
/* --------------------------------------------------------------------- */

interface ErrorBody {
  error_code?: string;
  error_message?: string;
  detail?: string | { error_code?: string; error_message?: string };
}

function parseError(raw: string): { code?: string; message?: string } {
  try {
    const body = JSON.parse(raw) as ErrorBody;
    if (typeof body.detail === "string") {
      const [head, ...rest] = body.detail.split(":");
      return rest.length
        ? { code: head?.trim(), message: rest.join(":").trim() }
        : { message: body.detail };
    }
    if (body.detail && typeof body.detail === "object") {
      return { code: body.detail.error_code, message: body.detail.error_message };
    }
    return { code: body.error_code, message: body.error_message };
  } catch {
    return {};
  }
}

const MESSAGES: Record<string, string> = {
  invalid_request: "That selection was rejected. Reset the options and try again.",
  workflow_not_available: "This feature is not available in this environment yet.",
  asset_not_found: "This image could not be found. Upload it again.",
  asset_not_owned: "This image could not be found. Upload it again.",
  asset_not_ready: "This image is still being checked. Try again in a moment.",
  asset_expired: "This image has expired. Upload it again.",
  asset_validation_failed:
    "The file was rejected: use a single-frame PNG, JPEG or WebP up to 4096 x 4096 and 10 MB.",
  source_integrity_failed: "The result failed its integrity check and was discarded. Please retry.",
  rate_limited: "Limit reached. Please wait a moment before trying again.",
  storage_unavailable: "Storage is temporarily unavailable. Please retry in a moment.",
  token_missing: "The request was sent without a login token. Sign out and sign in again.",
  auth_backend_unavailable:
    "Logins cannot be verified right now (service configuration). This is not a problem with your session.",
};

const KINDS: Record<string, TransformationApiError["kind"]> = {
  invalid_request: "invalid_request",
  workflow_not_available: "feature_unavailable",
  asset_not_found: "asset_not_found",
  asset_not_owned: "asset_not_found",
  asset_not_ready: "asset_not_ready",
  asset_expired: "asset_expired",
  asset_validation_failed: "asset_validation_failed",
  source_integrity_failed: "integrity_failed",
  rate_limited: "rate_limited",
  storage_unavailable: "storage_unavailable",
  token_missing: "signed_out",
  auth_backend_unavailable: "service_misconfigured",
};

function errorFor(status: number, raw: string): TransformationApiError {
  const { code, message } = parseError(raw);
  const key = (code ?? "").toLowerCase();
  if (key && KINDS[key]) {
    return new TransformationApiError(KINDS[key]!, MESSAGES[key] ?? message ?? "Request rejected.", status);
  }
  if (status === 401 || status === 403) {
    return new TransformationApiError("unauthorized", "Session expired. Please sign in again.", status);
  }
  if (status === 404) {
    return new TransformationApiError("not_found", "This item could not be found.", status);
  }
  if (status === 429) {
    return new TransformationApiError("rate_limited", MESSAGES["rate_limited"]!, status);
  }
  if (status >= 400 && status < 500) {
    return new TransformationApiError(
      "invalid_request",
      message?.slice(0, 200) || "The request was rejected. Check the selected options.",
      status,
    );
  }
  return new TransformationApiError(
    "server_error",
    "Service temporarily unavailable. Please retry in a moment.",
    status,
  );
}

/* --------------------------------------------------------------------- */
/* Client                                                                */
/* --------------------------------------------------------------------- */

export interface GenerationClient {
  listWorkflows(origin?: "studio" | "lab"): Promise<WorkflowInfo[]>;
  getScenePresets(): Promise<ScenePresetCatalog>;
  uploadInputAsset(file: File, idempotencyKey?: string): Promise<AssetRecord>;
  getAsset(assetId: string): Promise<AssetRecord>;
  listAssets(limit?: number): Promise<AssetRecord[]>;
  createTransformation(request: TransformationRequest, idempotencyKey?: string): Promise<TransformationJob>;
  getJob(jobId: string): Promise<TransformationJob>;
  getFreshResultUrl(jobId: string): Promise<string | null>;
}

export function createGenerationClient(config: GenerationClientConfig): GenerationClient {
  const baseUrl = config.baseUrl.replace(/\/+$/, "");

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (!baseUrl) {
      throw new TransformationApiError(
        "not_configured",
        "The Generation API URL is not configured for this environment.",
      );
    }
    const token = await config.getAccessToken();
    let response: Response;
    try {
      response = await fetch(`${baseUrl}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(init.headers as Record<string, string> | undefined),
        },
      });
    } catch {
      throw new TransformationApiError(
        "network",
        "The service did not return a readable response. Please retry.",
      );
    }
    if (!response.ok) {
      let raw = "";
      try {
        raw = (await response.text()).slice(0, 500);
      } catch {
        raw = "";
      }
      throw errorFor(response.status, raw);
    }
    try {
      return (await response.json()) as T;
    } catch {
      throw new TransformationApiError("server_error", "The service returned an unreadable response.");
    }
  }

  function validateLocally(file: File): asserts file is File & { type: AssetContentType } {
    if (!(ASSET_ALLOWED_TYPES as readonly string[]).includes(file.type)) {
      throw new TransformationApiError(
        "asset_validation_failed",
        "Only PNG, JPEG and WebP images are supported.",
      );
    }
    if (file.size > ASSET_MAX_BYTES) {
      throw new TransformationApiError("asset_validation_failed", "Images must be 10 MB or smaller.");
    }
  }

  return {
    async listWorkflows(origin = "studio") {
      const data = await request<{ workflows?: WorkflowInfo[] }>(`/v1/workflows?origin=${origin}`);
      return data.workflows ?? [];
    },

    getScenePresets() {
      return request<ScenePresetCatalog>("/v1/scene-presets");
    },

    /** Authorize -> PUT bytes -> finalize. Resolves with the ready asset row. */
    async uploadInputAsset(file, idempotencyKey = newIdempotencyKey()) {
      validateLocally(file);
      const authorization = await request<UploadAuthorization>("/v1/assets/upload-authorizations", {
        method: "POST",
        body: JSON.stringify({
          file_name: file.name,
          content_type: file.type,
          file_size: file.size,
          idempotency_key: idempotencyKey,
        }),
      });

      if (!authorization.already_finalized) {
        let put: Response;
        try {
          put = await fetch(authorization.upload_url, {
            method: "PUT",
            headers: { "Content-Type": authorization.content_type },
            body: file,
          });
        } catch {
          throw new TransformationApiError("upload_failed", "The upload did not complete. Please retry.");
        }
        if (!put.ok) {
          throw new TransformationApiError(
            "upload_failed",
            "The upload did not complete. Please retry.",
            put.status,
          );
        }
      }

      return request<AssetRecord>(`/v1/assets/${encodeURIComponent(authorization.asset_id)}/finalize`, {
        method: "POST",
      });
    },

    getAsset(assetId) {
      return request<AssetRecord>(`/v1/assets/${encodeURIComponent(assetId)}`);
    },

    async listAssets(limit = 12) {
      const data = await request<{ assets?: AssetRecord[] }>(`/v1/assets?limit=${limit}`);
      return data.assets ?? [];
    },

    createTransformation(transformation, idempotencyKey = newIdempotencyKey()) {
      const { module, ...rest } = transformation;
      return request<TransformationJob>("/v1/generations", {
        method: "POST",
        body: JSON.stringify({
          workflow_id: module,
          workflow_version: "v1",
          ...rest,
          idempotency_key: idempotencyKey,
        }),
      });
    },

    getJob(jobId) {
      return request<TransformationJob>(`/v1/generations/${encodeURIComponent(jobId)}`);
    },

    async getFreshResultUrl(jobId) {
      const data = await request<{ result_url?: string | null }>(
        `/v1/generations/${encodeURIComponent(jobId)}/result`,
      );
      return data.result_url ?? null;
    },
  };
}
