import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  DIMENSION_OPTIONS,
  NEGATIVE_PROMPT_MAX_LENGTH,
  PROMPT_MAX_LENGTH,
  WORKFLOW_ID,
} from "@/lib/generationApi";

export interface GenerationFormValues {
  prompt: string;
  negativePrompt: string;
  width: number;
  height: number;
}

interface GenerationFormProps {
  isSubmitting: boolean;
  disabled?: boolean;
  onSubmit: (values: GenerationFormValues) => void;
}

export function GenerationForm({ isSubmitting, disabled, onSubmit }: GenerationFormProps) {
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [dimension, setDimension] = useState("1024x1024");
  const [error, setError] = useState<string | null>(null);

  const busy = isSubmitting || Boolean(disabled);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed) {
      setError("A prompt is required.");
      return;
    }
    setError(null);
    const [width, height] = dimension.split("x").map(Number);
    onSubmit({
      prompt: trimmed,
      negativePrompt: negativePrompt.trim(),
      width: width ?? 1024,
      height: height ?? 1024,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6" noValidate>
      <div className="space-y-2">
        <div className="flex items-baseline justify-between gap-4">
          <Label htmlFor="prompt">Prompt</Label>
          <span className="text-xs text-muted-foreground" aria-hidden="true">
            {prompt.length} / {PROMPT_MAX_LENGTH}
          </span>
        </div>
        <Textarea
          id="prompt"
          required
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
          <Label htmlFor="workflow">Workflow</Label>
          <input
            id="workflow"
            readOnly
            value={WORKFLOW_ID}
            aria-label="Workflow identifier (fixed)"
            className="h-10 w-full rounded-md border border-input bg-muted px-3 text-sm text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          />
        </div>
      </div>

      {error ? (
        <p role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      ) : null}

      <Button type="submit" disabled={busy} className="w-full sm:w-auto">
        {isSubmitting ? "Generating…" : "Generate image"}
      </Button>
    </form>
  );
}
