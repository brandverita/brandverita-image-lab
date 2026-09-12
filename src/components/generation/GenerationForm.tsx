import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { StylePicker } from "@/components/generation/StylePicker";
import type { StyleRequest } from "@/lib/promptLayers";
import {
  DIMENSION_OPTIONS,
  NEGATIVE_PROMPT_MAX_LENGTH,
  PROMPT_MAX_LENGTH,
  SEED_MAX,
  WORKFLOW_ID,
} from "@/lib/generationApi";

export interface GenerationFormValues {
  prompt: string;
  negativePrompt: string;
  width: number;
  height: number;
  seed: number | null;
  /** Set in Branding mode; the API then composes the prompt from its own wording. */
  style?: StyleRequest | null;
}

interface GenerationFormProps {
  isSubmitting: boolean;
  disabled?: boolean;
  onSubmit: (values: GenerationFormValues) => void;
  onReset: () => void;
}

const DEFAULT_DIMENSION = "1024x1024";

type Mode = "free" | "branding";

export function GenerationForm({ isSubmitting, disabled, onSubmit, onReset }: GenerationFormProps) {
  const [mode, setMode] = useState<Mode>("free");
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState<StyleRequest>({ season: "", world: "", subject: "" });
  const [styleReady, setStyleReady] = useState(false);
  const [negativePrompt, setNegativePrompt] = useState("");
  const [dimension, setDimension] = useState(DEFAULT_DIMENSION);
  const [seed, setSeed] = useState("");
  const [error, setError] = useState<string | null>(null);

  const busy = isSubmitting || Boolean(disabled);
  const handleStyleReady = useCallback((ready: boolean) => setStyleReady(ready), []);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return; // guards against double submits

    let seedValue: number | null = null;
    const rawSeed = seed.trim();
    if (rawSeed) {
      if (!/^\d+$/.test(rawSeed) || Number(rawSeed) > SEED_MAX) {
        setError(`Seed must be a whole number between 0 and ${SEED_MAX}.`);
        return;
      }
      seedValue = Number(rawSeed);
    }

    const [width, height] = dimension.split("x").map(Number);
    const size = { width: width ?? 1024, height: height ?? 1024 };

    if (mode === "branding") {
      const subject = style.subject.trim();
      if (!style.season || !style.world) {
        setError("Choose an occasion and a brand setting.");
        return;
      }
      if (!subject) {
        setError("Say what you are selling.");
        return;
      }
      setError(null);
      onSubmit({
        // Not sent to the service in this mode — used locally for the image description.
        prompt: subject,
        negativePrompt: negativePrompt.trim(),
        ...size,
        seed: seedValue,
        style: { ...style, subject },
      });
      return;
    }

    const trimmed = prompt.trim();
    if (!trimmed) {
      setError("A prompt is required.");
      return;
    }
    if (trimmed.length > PROMPT_MAX_LENGTH) {
      setError(`The prompt must be ${PROMPT_MAX_LENGTH} characters or fewer.`);
      return;
    }

    setError(null);
    onSubmit({
      prompt: trimmed,
      negativePrompt: negativePrompt.trim(),
      ...size,
      seed: seedValue,
      style: null,
    });
  }

  function handleReset() {
    setPrompt("");
    setStyle((current) => ({ ...current, subject: "" }));
    setNegativePrompt("");
    setDimension(DEFAULT_DIMENSION);
    setSeed("");
    setError(null);
    onReset();
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      <div
        role="tablist"
        aria-label="How to describe the image"
        className="inline-flex rounded-md border border-input bg-muted p-1"
      >
        {(
          [
            { key: "free" as Mode, label: "Describe the picture you want" },
            { key: "branding" as Mode, label: "Branding" },
          ]
        ).map((tab) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={mode === tab.key}
            disabled={busy}
            onClick={() => {
              setMode(tab.key);
              setError(null);
            }}
            className={`rounded px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-60 ${
              mode === tab.key
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {mode === "branding" ? (
        <>
          <p className="text-sm text-muted-foreground">
            Same setting and finish every time, so a whole campaign looks like one series. Only the
            occasion and the product change.
          </p>
          <StylePicker
            value={style}
            disabled={busy}
            onChange={setStyle}
            onReadyChange={handleStyleReady}
          />
        </>
      ) : (
        <div className="space-y-2">
          <div className="flex items-baseline justify-between gap-4">
            <Label htmlFor="prompt">Describe the picture you want</Label>
            <span className="text-xs text-muted-foreground" aria-hidden="true">
              {prompt.length} / {PROMPT_MAX_LENGTH}
            </span>
          </div>
          <Textarea
            id="prompt"
            rows={6}
            maxLength={PROMPT_MAX_LENGTH}
            value={prompt}
            disabled={busy}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Describe the image to generate…"
            aria-describedby="prompt-help"
          />
          <p id="prompt-help" className="text-xs text-muted-foreground">
            Required. Up to {PROMPT_MAX_LENGTH} characters.
          </p>
        </div>
      )}


      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-4">
          <Label htmlFor="negative-prompt">Negative prompt</Label>
          <span className="text-xs text-muted-foreground" aria-hidden="true">
            {negativePrompt.length} / {NEGATIVE_PROMPT_MAX_LENGTH}
          </span>
        </div>
        <Textarea
          id="negative-prompt"
          rows={3}
          maxLength={NEGATIVE_PROMPT_MAX_LENGTH}
          value={negativePrompt}
          disabled={busy}
          onChange={(event) => setNegativePrompt(event.target.value)}
          placeholder="Elements to avoid (optional)"
          aria-describedby="negative-prompt-help"
        />
        <p id="negative-prompt-help" className="text-xs text-muted-foreground">
          Optional. Up to {NEGATIVE_PROMPT_MAX_LENGTH} characters.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="dimensions">Dimensions</Label>
          <select
            id="dimensions"
            value={dimension}
            disabled={busy}
            onChange={(event) => setDimension(event.target.value)}
            className="h-10 w-full rounded-md border border-input bg-card px-3 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:opacity-60"
          >
            {DIMENSION_OPTIONS.map((option) => (
              <option key={option.label} value={`${option.width}x${option.height}`}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="seed">Seed</Label>
          <Input
            id="seed"
            inputMode="numeric"
            value={seed}
            disabled={busy}
            onChange={(event) => setSeed(event.target.value.replace(/[^\d]/g, ""))}
            placeholder="Random"
            aria-describedby="seed-help"
          />
          <p id="seed-help" className="text-xs text-muted-foreground">
            Optional. Leave blank for a random seed.
          </p>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="workflow">Workflow</Label>
        <Input
          id="workflow"
          readOnly
          value={WORKFLOW_ID}
          aria-label="Workflow identifier (fixed)"
          className="bg-muted text-muted-foreground"
        />
      </div>

      {error ? (
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy}>
          {isSubmitting ? "Generating…" : "Generate image"}
        </Button>
        <Button type="button" variant="outline" onClick={handleReset} disabled={isSubmitting}>
          Reset
        </Button>
      </div>
    </form>
  );
}
