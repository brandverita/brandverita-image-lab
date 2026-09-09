import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { GenerationApiError } from "@/lib/generationApi";
import {
  listEvaluations,
  type AdvancedModule,
  type EvalScore,
  type EvalSummaryRow,
} from "@/lib/advancedApi";

interface EvalTableProps {
  accessToken: string | null;
  module: AdvancedModule;
  refreshKey: number;
}

const MODULE_LABEL: Record<string, string> = {
  outpaint: "Smart resize",
  product_scene: "Product scene",
};

function formatSeconds(ms: number | null | undefined): string {
  if (!ms) return "—";
  return `${(ms / 1000).toFixed(1)}s`;
}

function settingsLabel(score: EvalScore): string {
  const params = score.provider_params ?? {};
  const parts: string[] = [];
  if (typeof params["prompt_mode"] === "string") parts.push(String(params["prompt_mode"]));
  if (params["guidance"] !== undefined) parts.push(`guidance ${String(params["guidance"])}`);
  if (params["steps"] !== undefined) parts.push(`${String(params["steps"])} steps`);
  if (typeof params["scene_direction"] === "string") parts.push(String(params["scene_direction"]));
  if (typeof params["preset_variant"] === "string") parts.push(`wording ${String(params["preset_variant"])}`);
  return parts.length ? parts.join(" · ") : (score.variant_id ?? "default");
}

export function EvalTable({ accessToken, module, refreshKey }: EvalTableProps) {
  const [summary, setSummary] = useState<EvalSummaryRow[]>([]);
  const [scores, setScores] = useState<EvalScore[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listEvaluations(module, accessToken);
      setSummary(data.summary ?? []);
      setScores(data.scores ?? []);
    } catch (caught) {
      setError(
        caught instanceof GenerationApiError
          ? caught.message
          : "The comparison could not be loaded.",
      );
    } finally {
      setLoading(false);
    }
  }, [accessToken, module]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  return (
    <section aria-labelledby="eval-heading" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 id="eval-heading" className="text-left text-sm font-semibold text-foreground">
            Comparison — {MODULE_LABEL[module] ?? module}
          </h3>
          <p className="mt-1 text-left text-xs text-muted-foreground">
            Averages of your own ratings, grouped by the settings each run used.
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </Button>
      </div>

      {error ? (
        <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
          {error}
        </p>
      ) : null}

      {!error && summary.length === 0 && !loading ? (
        <p className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          No ratings yet. Create a run above, then rate the result.
        </p>
      ) : null}

      {summary.length ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Average ratings per settings variant</caption>
            <thead className="bg-muted text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">Variant</th>
                <th scope="col" className="px-3 py-2 font-medium">Runs rated</th>
                <th scope="col" className="px-3 py-2 font-medium">Overall</th>
                <th scope="col" className="px-3 py-2 font-medium">Brightness</th>
                <th scope="col" className="px-3 py-2 font-medium">Added content</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((row) => (
                <tr key={`${row.module}-${row.variant_id}`} className="border-t border-border">
                  <td className="px-3 py-2 font-mono text-xs">{row.variant_id}</td>
                  <td className="px-3 py-2">{row.runs}</td>
                  <td className="px-3 py-2 font-medium">{row.overall_mean.toFixed(2)}</td>
                  <td className="px-3 py-2">
                    {row.brightness_mean === null ? "—" : row.brightness_mean.toFixed(2)}
                  </td>
                  <td className="px-3 py-2">{Math.round(row.invented_rate * 100)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {scores.length ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Individual rated runs</caption>
            <thead className="bg-muted text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">Settings</th>
                <th scope="col" className="px-3 py-2 font-medium">Size</th>
                <th scope="col" className="px-3 py-2 font-medium">Overall</th>
                <th scope="col" className="px-3 py-2 font-medium">Added</th>
                <th scope="col" className="px-3 py-2 font-medium">Time</th>
                <th scope="col" className="px-3 py-2 font-medium">Note</th>
              </tr>
            </thead>
            <tbody>
              {scores.map((score) => (
                <tr key={score.job_id} className="border-t border-border align-top">
                  <td className="px-3 py-2 text-xs">{settingsLabel(score)}</td>
                  <td className="px-3 py-2 text-xs">{score.output_preset ?? "—"}</td>
                  <td className="px-3 py-2 font-medium">{score.overall}</td>
                  <td className="px-3 py-2 text-xs">{score.invented_content ? "yes" : "no"}</td>
                  <td className="px-3 py-2 text-xs">{formatSeconds(score.total_latency_ms)}</td>
                  <td className="max-w-xs px-3 py-2 text-xs text-muted-foreground">
                    {score.notes ?? ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
