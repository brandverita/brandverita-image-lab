import { useState } from "react";

import { Button } from "@/components/ui/button";
import { GenerationApiError } from "@/lib/generationApi";
import { submitScore } from "@/lib/advancedApi";

interface ScoreCardProps {
  jobId: string;
  accessToken: string | null;
  /** Shown only for Product Scene, where exposure is the thing being compared. */
  askBrightness: boolean;
  onSaved: () => void;
}

const RATINGS = [1, 2, 3, 4, 5] as const;

function RatingRow({
  label,
  value,
  onChange,
  disabled,
  hint,
}: {
  label: string;
  value: number | null;
  onChange: (next: number) => void;
  disabled: boolean;
  hint: string;
}) {
  return (
    <fieldset className="space-y-1">
      <legend className="text-left text-xs font-medium text-foreground">{label}</legend>
      <div className="flex gap-2">
        {RATINGS.map((rating) => (
          <button
            key={rating}
            type="button"
            disabled={disabled}
            aria-pressed={value === rating}
            onClick={() => onChange(rating)}
            className={`h-9 w-9 rounded-md border text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 ${
              value === rating
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card text-foreground"
            }`}
          >
            {rating}
          </button>
        ))}
      </div>
      <p className="text-left text-xs text-muted-foreground">{hint}</p>
    </fieldset>
  );
}

export function ScoreCard({ jobId, accessToken, askBrightness, onSaved }: ScoreCardProps) {
  const [overall, setOverall] = useState<number | null>(null);
  const [brightness, setBrightness] = useState<number | null>(null);
  const [invented, setInvented] = useState(false);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    if (overall === null) return;
    setSaving(true);
    setError(null);
    try {
      await submitScore({
        jobId,
        overall,
        inventedContent: invented,
        brightness: askBrightness ? brightness : null,
        notes: notes.trim() || null,
        accessToken,
      });
      setSaved(true);
      onSaved();
    } catch (caught) {
      setError(
        caught instanceof GenerationApiError
          ? caught.message
          : "The score could not be saved. Please retry.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4">
      <div>
        <h4 className="text-left text-sm font-semibold text-foreground">Rate this result</h4>
        <p className="mt-1 text-left text-xs text-muted-foreground">
          Your rating is stored with the exact settings that produced this image, so the comparison
          table can pick a winner.
        </p>
      </div>

      <RatingRow
        label="Overall quality"
        value={overall}
        onChange={setOverall}
        disabled={saving || saved}
        hint="1 = unusable, 5 = ready to ship."
      />

      {askBrightness ? (
        <RatingRow
          label="Brightness"
          value={brightness}
          onChange={setBrightness}
          disabled={saving || saved}
          hint="1 = too dark, 3 = right, 5 = too bright."
        />
      ) : null}

      <label className="flex items-start gap-2 text-left text-xs text-foreground">
        <input
          type="checkbox"
          checked={invented}
          disabled={saving || saved}
          onChange={(event) => setInvented(event.target.checked)}
          className="mt-0.5 h-4 w-4 rounded border-border outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
        <span>
          It added something that was not in my picture (a face, an object, text or a seam).
        </span>
      </label>

      <label className="block space-y-1 text-left">
        <span className="text-xs font-medium text-foreground">Note (optional)</span>
        <textarea
          value={notes}
          disabled={saving || saved}
          maxLength={500}
          rows={2}
          onChange={(event) => setNotes(event.target.value)}
          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          placeholder="What stood out?"
        />
      </label>

      {error ? (
        <p
          role="alert"
          className="rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive"
        >
          {error}
        </p>
      ) : null}

      {saved ? (
        <p className="text-left text-xs font-medium text-foreground">Rating saved.</p>
      ) : (
        <Button
          type="button"
          onClick={() => void handleSave()}
          disabled={overall === null || saving}
        >
          {saving ? "Saving…" : "Save rating"}
        </Button>
      )}
    </div>
  );
}
