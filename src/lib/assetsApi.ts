/**
 * Typed client for the Phase 2A asset endpoints of the BrandVerita Generation API.
 *
 * Security notes:
 *  - Upload credentials (the signed upload URL) are held in memory only. They are
 *    never persisted, never put in state that is logged, and never printed.
 *  - Client-side checks mirror the server limits for fast feedback only; the API
 *    is authoritative and re-validates magic bytes, format, dimensions and size.
 */

import { API_BASE_URL, newIdempotencyKey } from "@/lib/generationApi";

export const ASSET_MAX_BYTES = 10 * 1024 * 1024;
export const ASSET_MAX_WIDTH = 4096;
export const ASSET_MAX_HEIGHT = 4096;
export const ASSET_MAX_PIXELS = 16_777_216;

export const ASSET_ALLOWED_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
export type AssetContentType = (typeof ASSET_ALLOWED_TYPES)[number];

const EXTENSIONS: Record<AssetContentType, readonly string[]> = {
  "image/png": ["png"],
  "image/jpeg": ["jpg", "jpeg"],
  "image/webp": ["webp"],
};

export const ASSET_ACCEPT_ATTRIBUTE = ASSET_ALLOWED_TYPES.join(",");

export type AssetErrorCode =
  | "invalid_file_type"
  | "file_too_large"
  | "asset_not_found"
  | "asset_not_owned"
  | "asset_not_ready"
  | "asset_validation_failed"
  | "storage_unavailable"
  | "unauthorized"
  | "not_configured"
  | "upload_failed"
  | "network"
  | "server_error";

const MESSAGES: Record<AssetErrorCode, string> = {
  invalid_file_type: "Only PNG, JPEG and WebP images are supported.",
  file_too_large: "Images must be 10 MB or smaller.",
  asset_not_found: "This asset could not be found.",
  asset_not_owned: "This asset could not be found.",
  asset_not_ready: "This asset is not ready yet.",
  asset_validation_failed:
    "The file was rejected: it must be a single-frame PNG, JPEG or WebP no larger than 4096 x 4096.",
  storage_unavailable: "Storage is temporarily unavailable. Please retry in a moment.",
  unauthorized: "Session expired. Please sign in again.",
  not_configured: "Generation API URL is not configured for this environment.",
  upload_failed: "The upload did not complete. Please retry.",
  network: "The Generation API did not return a readable response. Please retry.",
  server_error: "Service temporarily unavailable. Please retry in a moment.",
};

export class AssetApiError extends Error {
  readonly code: AssetErrorCode;
  readonly status?: number | undefined;

  constructor(code: AssetErrorCode, message?: string, status?: number) {
    super(message || MESSAGES[code]);
    this.name = "AssetApiError";
    this.code = code;
    this.status = status;
  }
}

export function assetErrorMessage(code: AssetErrorCode): string {
  return MESSAGES[code];
}

export interface AssetMetadata {
  asset_id: string;
  status: "pending_upload" | "ready" | "rejected" | "deleted" | "expired";
  kind?: string | null;
  content_type?: string | null;
  file_size?: number | null;
  width?: number | null;
  height?: number | null;
  sha256?: string | null;
  created_at?: string | null;
  finalized_at?: string | null;
  expires_at?: string | null;
  read_url?: string | null;
  read_url_expires_in?: number | null;
}

export interface UploadAuthorization {
  asset_id: string;
  /** Short-lived, single-path signed upload URL. In-memory only — never store it. */
  upload_url: string;
  method: "PUT";
  content_type: AssetContentType;
  expires_in: number;
  max_file_size: number;
  reused?: boolean;
  already_finalized?: boolean;
}

export function isAllowedAssetType(type: string): type is AssetContentType {
  return (ASSET_ALLOWED_TYPES as readonly string[]).includes(type);
}

/** Fast local pre-check; the server still re-validates everything. */
export function validateFileLocally(file: { name: string; type: string; size: number }): void {
  if (!isAllowedAssetType(file.type)) {
    throw new AssetApiError("invalid_file_type");
  }
  const ext = file.name.includes(".") ? file.name.split(".").pop()!.toLowerCase() : "";
  if (!EXTENSIONS[file.type].includes(ext)) {
    throw new AssetApiError(
      "invalid_file_type",
      "The file extension does not match the image type.",
    );
  }
  if (file.size > ASSET_MAX_BYTES) {
    throw new AssetApiError("file_too_large");
  }
  if (file.size <= 0) {
    throw new AssetApiError("asset_validation_failed", "The selected file is empty.");
  }
}

function parseErrorBody(raw: string): { code?: AssetErrorCode; message?: string } {
  try {
    const parsed = JSON.parse(raw) as {
      error_code?: string;
      error_message?: string;
      detail?: { error_code?: string; error_message?: string } | string;
    };
    const detail = typeof parsed.detail === "object" && parsed.detail ? parsed.detail : parsed;
    const code = (detail.error_code ?? parsed.error_code) as AssetErrorCode | undefined;
    const message = detail.error_message ?? parsed.error_message;
    return { ...(code ? { code } : {}), ...(message ? { message } : {}) };
  } catch {
    return {};
  }
}

function errorFor(status: number, raw: string): AssetApiError {
  const { code, message } = parseErrorBody(raw);
  if (code && code in MESSAGES) return new AssetApiError(code, message, status);
  if (status === 401 || status === 403) return new AssetApiError("unauthorized", undefined, status);
  if (status === 404) return new AssetApiError("asset_not_found", undefined, status);
  if (status === 409) return new AssetApiError("asset_not_ready", undefined, status);
  if (status === 422) return new AssetApiError("asset_validation_failed", undefined, status);
  if (status === 503) return new AssetApiError("storage_unavailable", undefined, status);
  return new AssetApiError("server_error", undefined, status);
}

async function request<T>(
  path: string,
  init: { method: "GET" | "POST"; accessToken?: string | null; body?: unknown },
): Promise<T> {
  if (!API_BASE_URL) throw new AssetApiError("not_configured");

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: init.method,
      headers: {
        "Content-Type": "application/json",
        ...(init.accessToken ? { Authorization: `Bearer ${init.accessToken}` } : {}),
      },
      ...(init.body === undefined ? {} : { body: JSON.stringify(init.body) }),
    });
  } catch {
    throw new AssetApiError("network");
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
    throw new AssetApiError("server_error", "The Generation API returned an unreadable response.");
  }
}

export function newAssetIdempotencyKey(): string {
  return newIdempotencyKey();
}

export function createUploadAuthorization(input: {
  file: { name: string; type: string; size: number };
  idempotencyKey: string;
  accessToken?: string | null;
}): Promise<UploadAuthorization> {
  validateFileLocally(input.file);
  return request<UploadAuthorization>("/v1/assets/upload-authorizations", {
    method: "POST",
    accessToken: input.accessToken,
    body: {
      file_name: input.file.name,
      content_type: input.file.type,
      file_size: input.file.size,
      idempotency_key: input.idempotencyKey,
    },
  });
}

/** Single direct-to-storage PUT. The signed URL stays in this call's scope. */
export async function uploadToAuthorization(
  authorization: Pick<UploadAuthorization, "upload_url" | "content_type">,
  file: Blob,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(authorization.upload_url, {
      method: "PUT",
      headers: { "Content-Type": authorization.content_type },
      body: file,
    });
  } catch {
    throw new AssetApiError("upload_failed");
  }
  if (!response.ok) {
    throw new AssetApiError("upload_failed", undefined, response.status);
  }
}

export function finalizeAsset(assetId: string, accessToken?: string | null): Promise<AssetMetadata> {
  return request<AssetMetadata>(`/v1/assets/${encodeURIComponent(assetId)}/finalize`, {
    method: "POST",
    accessToken,
  });
}

export function getAsset(assetId: string, accessToken?: string | null): Promise<AssetMetadata> {
  return request<AssetMetadata>(`/v1/assets/${encodeURIComponent(assetId)}`, {
    method: "GET",
    accessToken,
  });
}

export function listAssets(
  accessToken?: string | null,
  limit = 12,
): Promise<AssetMetadata[]> {
  return request<{ assets?: AssetMetadata[] }>(`/v1/assets?limit=${limit}`, {
    method: "GET",
    accessToken,
  }).then((body) => body.assets ?? []);
}

export function formatBytes(bytes: number | null | undefined): string {
  if (typeof bytes !== "number" || bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function shortHash(sha256: string | null | undefined): string {
  return sha256 ? `${sha256.slice(0, 12)}…` : "—";
}
