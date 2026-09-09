/**
 * Typed client for the staging-only advanced workflows (Smart Resize / Outpaint
 * and Product Scene) plus the evaluation endpoints.
 *
 * Everything the browser can send is an enum chosen from a server-owned list:
 * there is no free text, no provider setting, no URL and no workflow JSON in
 * any request built here. Signed URLs are used immediately and never persisted
 * or logged.
 */

import { API_BASE_URL, GenerationApiError } from "@/lib/generationApi";

export const OUTPAINT_WORKFLOW = { workflow_id: "outpaint", workflow_version: "v2" } as const;
export const PRODUCT_SCENE_WORKFLOW = {
  workflow_id: "product_scene",
  workflow_version: "v1",
} as const;

export const OUTPAINT_OUTPUT_PRESETS = ["1200x627", "1600x900"] as const;
export const OUTPAINT_DIRECTIONS = ["left", "right", "top", "bottom", "symmetric"] as const;
export type OutpaintDirection = (typeof OUTPAINT_DIRECTIONS)[number];
export type OutpaintAnchor = "left" | "right" | "top" | "bottom" | "center";

export const OUTPAINT_ANCHORS_BY_DIRECTION: Record<OutpaintDirection, readonly OutpaintAnchor[]> = {
  left: ["right", "center"],
  right: ["left", "center"],
  top: ["bottom", "center"],
  bottom: ["top", "center"],
  symmetric: ["center"],
};

export const PRODUCT_SCENE_OUTPUT_PRESETS = [
  "1080x1080",
  "1080x1350",
  "1200x627",
  "1600x900",
] as const;

export type AdvancedModule = "outpaint" | "product_scene";

export interface ResearchOptions {
  outpaint: { prompt_modes: string[]; guidance: number[]; steps: number[] };
  product_scene: { preset_variants: string[] };
}

export interface ScenePresetCatalog {
  scene_directions: { scene_direction: string; label: string }[];
  background_styles: string[];
  output_presets: string[];
  preset_variants?: string[];
  default_preset_variant?: string;
}

export interface AdvancedJob {
  job_id: string;
  status: string;
  workflow_id: string;
  workflow_version?: string | null;
  progress?: number | null;
  width?: number | null;
  height?: number | null;
  result_url?: string | null;
  output_asset_id?: string | null;
  output_preset?: string | null;
  request_params?: Record<string, unknown> | null;
  error_code?: string | null;
  error_message?: string | null;
  completed_at?: string | null;
}

export interface EvalScore {
  job_id: string;
  module: string;
  overall: number;
  invented_content: boolean;
  brightness?: number | null;
  notes?: string | null;
  created_at?: string | null;
  variant_id?: string | null;
  provider_params?: Record<string, unknown> | null;
  output_preset?: string | null;
  provider_model?: string | null;
  total_latency_ms?: number | null;
  estimated_cost?: number | null;
}

export interface EvalSummaryRow {
  module: string;
  variant_id: string;
  runs: number;
  overall_mean: number;
  brightness_mean: number | null;
  invented_rate: number;
}

function detailMessage(raw: string): string | undefined {
  try {
    const parsed = JSON.parse(raw) as {
      detail?: string | { error_message?: string };
      error_message?: string;
    };
    if (typeof parsed.error_message === "string") return parsed.error_message;
    if (typeof parsed.detail === "string") return parsed.detail;
    if (parsed.detail && typeof parsed.detail === "object") return parsed.detail.error_message;
  } catch {
    /* not JSON */
  }
  return undefined;
}

async function request<T>(
  path: string,
  init: RequestInit & { accessToken?: string | null | undefined } = {},
): Promise<T> {
  if (!API_BASE_URL) {
    throw new GenerationApiError("not_configured", "Generation API URL is not configured.");
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
    throw new GenerationApiError(
      "network",
      "The Generation API did not return a readable response. Please retry.",
    );
  }
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    const message = detailMessage(body.slice(0, 500));
    if (response.status === 401 || response.status === 403) {
      throw new GenerationApiError(
        "unauthorized",
        message || "This feature is not available for your account in this environment.",
        response.status,
      );
    }
    if (response.status === 429) {
      throw new GenerationApiError("rate_limited", message || "Limit reached.", response.status);
    }
    if (response.status >= 500) {
      throw new GenerationApiError(
        "server_error",
        message || "Service temporarily unavailable. Please retry.",
        response.status,
      );
    }
    throw new GenerationApiError(
      "invalid_request",
      message || "The request was rejected.",
      response.status,
    );
  }
  try {
    return (await response.json()) as T;
  } catch {
    throw new GenerationApiError("server_error", "The API returned an unreadable response.");
  }
}

export function getScenePresets(accessToken?: string | null): Promise<ScenePresetCatalog> {
  return request<ScenePresetCatalog>("/v1/scene-presets", { method: "GET", accessToken });
}

export function getResearchOptions(accessToken?: string | null): Promise<ResearchOptions> {
  return request<ResearchOptions>("/v1/research-options", { method: "GET", accessToken });
}

export interface OutpaintSelection {
  outputPreset: string;
  direction: OutpaintDirection;
  anchor: OutpaintAnchor;
  promptMode?: string | undefined;
  guidance?: number | undefined;
  steps?: number | undefined;
}

export interface ProductSceneSelection {
  outputPreset: string;
  sceneDirection: string;
  backgroundStyle: string;
  presetVariant?: string | undefined;
}

export function startOutpaint(input: {
  sourceAssetId: string;
  selection: OutpaintSelection;
  idempotencyKey: string;
  accessToken?: string | null;
}): Promise<AdvancedJob> {
  const s = input.selection;
  return request<AdvancedJob>("/v1/generations", {
    method: "POST",
    accessToken: input.accessToken,
    // The run key travels in the body; no extra header (keeps the request
    // inside the service's allowed browser headers).
    body: JSON.stringify({
      ...OUTPAINT_WORKFLOW,
      source_asset_id: input.sourceAssetId,
      output_preset: s.outputPreset,
      idempotency_key: input.idempotencyKey,
      params: {
        expansion_mode: "anchor_directional",
        direction: s.direction,
        anchor: s.anchor,
        style_mode: "preserve_source",
        ...(s.promptMode ? { prompt_mode: s.promptMode } : {}),
        ...(s.guidance !== undefined ? { guidance: s.guidance } : {}),
        ...(s.steps !== undefined ? { steps: s.steps } : {}),
      },
    }),
  });
}

export function startProductScene(input: {
  sourceAssetId: string;
  selection: ProductSceneSelection;
  idempotencyKey: string;
  accessToken?: string | null;
}): Promise<AdvancedJob> {
  const s = input.selection;
  return request<AdvancedJob>("/v1/generations", {
    method: "POST",
    accessToken: input.accessToken,
    // Run key in the body only — see startOutpaint.
    body: JSON.stringify({
      ...PRODUCT_SCENE_WORKFLOW,
      source_asset_id: input.sourceAssetId,
      output_preset: s.outputPreset,
      idempotency_key: input.idempotencyKey,
      params: {
        scene_direction: s.sceneDirection,
        background_style: s.backgroundStyle,
        preserve_subject: true,
        ...(s.presetVariant ? { preset_variant: s.presetVariant } : {}),
      },
    }),
  });
}

export function getAdvancedJob(jobId: string, accessToken?: string | null): Promise<AdvancedJob> {
  return request<AdvancedJob>(`/v1/generations/${jobId}`, { method: "GET", accessToken });
}

export async function refreshAdvancedResultUrl(
  jobId: string,
  accessToken?: string | null,
): Promise<string | null> {
  const data = await request<{ result_url?: string | null }>(`/v1/generations/${jobId}/result`, {
    method: "GET",
    accessToken,
  });
  return data.result_url ?? null;
}

export function submitScore(input: {
  jobId: string;
  overall: number;
  inventedContent: boolean;
  brightness?: number | null;
  notes?: string | null;
  accessToken?: string | null;
}): Promise<{ score: EvalScore }> {
  return request<{ score: EvalScore }>(`/v1/evaluations/${input.jobId}/score`, {
    method: "POST",
    accessToken: input.accessToken,
    body: JSON.stringify({
      overall: input.overall,
      invented_content: input.inventedContent,
      brightness: input.brightness ?? null,
      notes: input.notes ?? null,
    }),
  });
}

export function listEvaluations(
  module: AdvancedModule | "all",
  accessToken?: string | null,
): Promise<{ scores: EvalScore[]; summary: EvalSummaryRow[] }> {
  const query = module === "all" ? "" : `?module=${module}`;
  return request<{ scores: EvalScore[]; summary: EvalSummaryRow[] }>(`/v1/evaluations${query}`, {
    method: "GET",
    accessToken,
  });
}

export function isTerminalAdvancedStatus(status: string): boolean {
  return ["completed", "failed", "canceled", "cancelled", "expired"].includes(status);
}
