import { useEffect, useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  fetchPromptLayers,
  rememberSeason,
  rememberWorld,
  rememberedSeason,
  rememberedWorld,
  type PromptLayerCatalog,
  type StyleRequest,
} from "@/lib/promptLayers";
import { supabase } from "@/integrations/supabase/client";

interface StylePickerProps {
  value: StyleRequest;
  disabled?: boolean;
  onChange: (next: StyleRequest) => void;
  onReadyChange?: (ready: boolean) => void;
}

/**
 * Branding mode picker: choose the occasion and the fixed brand setting, then
 * say what is being sold. The wording behind each choice lives on the Generation
 * API, which is what keeps every picture in a campaign visually consistent.
 */
export function StylePicker({ value, disabled, onChange, onReadyChange }: StylePickerProps) {
  const [catalog, setCatalog] = useState<PromptLayerCatalog | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const { data } = await supabase.auth.getSession();
        const loaded = await fetchPromptLayers(data.session?.access_token ?? null);
        if (!active) return;
        setCatalog(loaded);
        setLoadError(null);
        const season = rememberedSeason() || value.season || loaded.seasons[0]?.key || "";
        const world = rememberedWorld() || value.world || loaded.worlds[0]?.key || "";
        const known = (list: { key: string }[], key: string) => list.some((o) => o.key === key);
        onChange({
          ...value,
          season: known(loaded.seasons, season) ? season : (loaded.seasons[0]?.key ?? ""),
          world: known(loaded.worlds, world) ? world : (loaded.worlds[0]?.key ?? ""),
        });
      } catch {
        if (active) {
          setLoadError(
            "The branding choices could not be loaded from the image service. Retry in a moment, or use free text meanwhile.",
          );
        }
      }
    })();
    return () => {
      active = false;
    };
    // Loaded once per mount on purpose.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    onReadyChange?.(Boolean(catalog));
  }, [catalog, onReadyChange]);

  const subjectMax = catalog?.subject_max_chars ?? 200;
  const selectClass =
    "h-10 w-full rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-60";

  if (loadError) {
    return (
      <div
        role="alert"
        className="rounded-md border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive"
      >
        {loadError}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="style-season">Occasion</Label>
          <select
            id="style-season"
            className={selectClass}
            value={value.season}
            disabled={disabled || !catalog}
            onChange={(event) => {
              rememberSeason(event.target.value);
              onChange({ ...value, season: event.target.value });
            }}
            aria-describedby="style-season-help"
          >
            {(catalog?.seasons ?? []).map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
          <p id="style-season-help" className="text-xs text-muted-foreground">
            {catalog?.seasons.find((o) => o.key === value.season)?.hint ?? "Loading choices…"}
          </p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="style-world">Brand setting</Label>
          <select
            id="style-world"
            className={selectClass}
            value={value.world}
            disabled={disabled || !catalog}
            onChange={(event) => {
              rememberWorld(event.target.value);
              onChange({ ...value, world: event.target.value });
            }}
            aria-describedby="style-world-help"
          >
            {(catalog?.worlds ?? []).map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </select>
          <p id="style-world-help" className="text-xs text-muted-foreground">
            {catalog?.worlds.find((o) => o.key === value.world)?.hint ??
              "Loading choices…"}{" "}
            Kept for next time on this device.
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-4">
          <Label htmlFor="style-subject">What you are selling</Label>
          <span className="text-xs text-muted-foreground" aria-hidden="true">
            {value.subject.length} / {subjectMax}
          </span>
        </div>
        <Input
          id="style-subject"
          value={value.subject}
          maxLength={subjectMax}
          disabled={disabled || !catalog}
          onChange={(event) =>
            onChange({ ...value, subject: event.target.value.replace(/[\r\n]/g, " ") })
          }
          placeholder="a hand-poured soy candle in an amber jar"
          aria-describedby="style-subject-help"
        />
        <p id="style-subject-help" className="text-xs text-muted-foreground">
          Required. Name the product only — the occasion and setting are handled for you.
        </p>
      </div>
    </div>
  );
}
