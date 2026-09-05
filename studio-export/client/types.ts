/**
 * Studio export — shared types for the two image-transformation features.
 *
 * Mirrors the server contract in ../01-contract.md exactly. No dependency on
 * any app framework, router or Supabase client.
 */

/* --------------------------------------------------------------------- */
/* Assets                                                                */
/* --------------------------------------------------------------------- */

export const ASSET_ALLOWED_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;
export type AssetContentType = (typeof ASSET_ALLOWED_TYPES)[number];

export const ASSET_MAX_BYTES = 10 * 1024 * 1024;
export const ASSET_MAX_WIDTH = 4096;
export const ASSET_MAX_HEIGHT = 4096;
export const ASSET_MAX_PIXELS = 16_777_216;
export const ASSET_ACCEPT_ATTRIBUTE = ASSET_ALLOWED_TYPES.join(",");

export type AssetStatus = "pending_upload" | "ready" | "rejected" | "deleted" | "expired";

export interface AssetRecord {
  asset_id: string;
  status: AssetStatus;
  kind?: "input" | "output" | null;
  content_type?: string | null;
  file_size?: number | null;
  width?: number | null;
  height?: number | null;
  sha256?: string | null;
  created_at?: string | null;
  finalized_at?: string | null;
  expires_at?: string | null;
  /** Short-lived signed URL. Never persist or log it. */
  read_url?: string | null;
  read_url_expires_in?: number | null;
}

export interface UploadAuthorization {
  asset_id: string;
  /** Short-lived, single-path signed URL. In-memory only. */
  upload_url: string;
  method: "PUT";
  content_type: AssetContentType;
  expires_in: number;
  max_file_size: number;
  reused?: boolean;
  already_finalized?: boolean;
}

/* --------------------------------------------------------------------- */
/* Modules and their enum-only parameters                                */
/* --------------------------------------------------------------------- */

export type TransformationModule = "outpaint" | "product_scene";

export const OUTPAINT_WORKFLOW = { workflow_id: "outpaint", workflow_version: "v1" } as const;
export const PRODUCT_SCENE_WORKFLOW = {
  workflow_id: "product_scene",
  workflow_version: "v1",
} as const;

export const OUTPAINT_OUTPUT_PRESETS = ["1200x627", "1600x900"] as const;
export type OutpaintOutputPreset = (typeof OUTPAINT_OUTPUT_PRESETS)[number];

export const OUTPAINT_DIRECTIONS = ["left", "right", "top", "bottom", "symmetric"] as const;
export type OutpaintDirection = (typeof OUTPAINT_DIRECTIONS)[number];

export type OutpaintAnchor = "left" | "right" | "top" | "bottom" | "center";

/** Server-enforced pairing: `direction` says where new pixels go. */
export const OUTPAINT_ANCHORS_BY_DIRECTION: Record<OutpaintDirection, readonly OutpaintAnchor[]> = {
  left: ["right", "center"],
  right: ["left", "center"],
  top: ["bottom", "center"],
  bottom: ["top", "center"],
  symmetric: ["center"],
};

export interface OutpaintParams {
  expansion_mode: "anchor_directional";
  direction: OutpaintDirection;
  anchor: OutpaintAnchor;
  style_mode: "preserve_source";
}

export const PRODUCT_SCENE_OUTPUT_PRESETS = [
  "1080x1080",
  "1080x1350",
  "1200x627",
  "1600x900",
] as const;
export type ProductSceneOutputPreset = (typeof PRODUCT_SCENE_OUTPUT_PRESETS)[number];

export const SCENE_DIRECTIONS = [
  "clean_studio",
  "premium_neutral",
  "warm_lifestyle",
  "natural_surface",
] as const;
export type SceneDirection = (typeof SCENE_DIRECTIONS)[number];

export const BACKGROUND_STYLES = ["neutral", "soft_shadow", "high_key", "editorial"] as const;
export type BackgroundStyle = (typeof BACKGROUND_STYLES)[number];

export interface ProductSceneParams {
  scene_direction: SceneDirection;
  background_style: BackgroundStyle;
  /** Must be true; false is rejected server-side. */
  preserve_subject: true;
}

export interface ScenePresetCatalog {
  scene_directions: { scene_direction: SceneDirection; label: string }[];
  background_styles: BackgroundStyle[];
  output_presets: ProductSceneOutputPreset[];
}

/* --------------------------------------------------------------------- */
/* Jobs                                                                  */
/* --------------------------------------------------------------------- */

export type JobStatus =
  | "queued"
  | "dispatching"
  | "running"
  | "uploading_output"
  | "completed"
  | "failed"
  | "canceled"
  | "cancelled"
  | "expired";

export interface TransformationJob {
  job_id: string;
  status: JobStatus;
  workflow_id: string;
  workflow_version?: string | null;
  provider?: string | null;
  provider_model?: string | null;
  workflow_config_hash?: string | null;
  progress?: number | null;
  width?: number | null;
  height?: number | null;
  /** Short-lived signed URL, present once completed. */
  result_url?: string | null;
  queued_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  source_asset_id?: string | null;
  output_asset_id?: string | null;
  output_preset?: string | null;
  request_params?: Record<string, unknown> | null;
}

export type OutpaintRequest = {
  module: "outpaint";
  source_asset_id: string;
  output_preset: OutpaintOutputPreset;
  params: OutpaintParams;
};

export type ProductSceneRequest = {
  module: "product_scene";
  source_asset_id: string;
  output_preset: ProductSceneOutputPreset;
  params: ProductSceneParams;
};

export type TransformationRequest = OutpaintRequest | ProductSceneRequest;

/** Safe workflow view from GET /v1/workflows. */
export interface WorkflowInfo {
  key: string;
  version: string;
  display_name?: string | null;
  description?: string | null;
  status?: string | null;
  provider?: string | null;
  provider_model?: string | null;
  commercial_status?: string | null;
  estimated_credits?: number | null;
  enabled_for_studio?: boolean | null;
  production_enabled?: boolean | null;
}

/* --------------------------------------------------------------------- */
/* Errors                                                                */
/* --------------------------------------------------------------------- */

export type TransformationErrorKind =
  | "not_configured"
  | "unauthorized"
  | "signed_out"
  | "service_misconfigured"
  | "feature_unavailable"
  | "invalid_request"
  | "asset_not_found"
  | "asset_not_ready"
  | "asset_expired"
  | "asset_validation_failed"
  | "integrity_failed"
  | "rate_limited"
  | "not_found"
  | "upload_failed"
  | "storage_unavailable"
  | "server_error"
  | "network"
  | "timeout";

export class TransformationApiError extends Error {
  readonly kind: TransformationErrorKind;
  readonly status?: number | undefined;

  constructor(kind: TransformationErrorKind, message: string, status?: number) {
    super(message);
    this.name = "TransformationApiError";
    this.kind = kind;
    this.status = status;
  }
}
