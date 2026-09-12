/**
 * Brand-consistency picker data (GET /v1/prompt-layers).
 *
 * The season/setting wording lives on the Generation API so every app and every
 * campaign composes the exact same text. This module only ever sees keys,
 * labels and hints — never the wording itself, and never any credentials.
 */

import { requestJson } from "@/lib/generationApi";

export interface PromptLayerOption {
  key: string;
  label: string;
  hint?: string | null;
}

export interface PromptLayerCatalog {
  seasons: PromptLayerOption[];
  worlds: PromptLayerOption[];
  subject_max_chars: number;
  layer_table_version: string;
}

export interface StyleRequest {
  season: string;
  world: string;
  subject: string;
}

/** Remembered brand setting for this device (Layer 2 lock). */
const WORLD_STORAGE_KEY = "bv.branding.world";
const SEASON_STORAGE_KEY = "bv.branding.season";

export function rememberedWorld(): string | null {
  try {
    return localStorage.getItem(WORLD_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function rememberWorld(world: string): void {
  try {
    localStorage.setItem(WORLD_STORAGE_KEY, world);
  } catch {
    /* private browsing — the picker simply won't remember */
  }
}

export function rememberedSeason(): string | null {
  try {
    return localStorage.getItem(SEASON_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function rememberSeason(season: string): void {
  try {
    localStorage.setItem(SEASON_STORAGE_KEY, season);
  } catch {
    /* ignored */
  }
}

export function fetchPromptLayers(accessToken?: string | null): Promise<PromptLayerCatalog> {
  return requestJson<PromptLayerCatalog>("/v1/prompt-layers", { method: "GET", accessToken });
}
