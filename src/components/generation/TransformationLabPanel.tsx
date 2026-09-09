/**
 * Staging evaluation bench for the two advanced features.
 *
 * Internal Lab only. Every option below is an enum the API publishes; the
 * wording sent to the provider lives on the server and is never editable here.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { EvalTable } from "@/components/generation/EvalTable";
import { ScoreCard } from "@/components/generation/ScoreCard";
import { Button } from "@/components/ui/button";
import { useAssetUpload } from "@/hooks/use-asset-upload";
import { ASSET_ACCEPT_ATTRIBUTE, type AssetMetadata } from "@/lib/assetsApi";
import {
  GenerationApiError,
  POLL_INTERVAL_MS,
  POLL_TIMEOUT_MS,
  newIdempotencyKey,
} from "@/lib/generationApi";
import {
  OUTPAINT_ANCHORS_BY_DIRECTION,
  OUTPAINT_DIRECTIONS,
  OUTPAINT_OUTPUT_PRESETS,
  PRODUCT_SCENE_OUTPUT_PRESETS,
  getAdvancedJob,
  getResearchOptions,
  getScenePresets,
  isTerminalAdvancedStatus,
  refreshAdvancedResultUrl,
  startOutpaint,
  startProductScene,
  type AdvancedJob,
  type AdvancedModule,
  type OutpaintDirection,
  type OutpaintAnchor,
  type ResearchOptions,
  type ScenePresetCatalog,
} from "@/lib/advancedApi";

interface Props {
  accessToken: string | null;
}

type Phase = "idle" | "submitting" | "polling" | "done" | "error";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1 text-left">
      <span className="text-xs font-medium text-foreground">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-muted-foreground">{hint}</span> : null}
    </label>
  );
}

const selectClass =
  "w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50";

export function TransformationLabPanel({ accessToken }: Props) {
  const tokenRef = useRef(accessToken);
  tokenRef.current = accessToken;
  const getToken = useCallback(() => tokenRef.current, []);

  const [module, setModule] = useState<AdvancedModule>("outpaint");
  const [source, setSource] = useState<AssetMetadata | null>(null);
  const [options, setOptions] = useState<ResearchOptions | null>(null);
  const [scenes, setScenes] = useState<ScenePresetCatalog | null>(null);

  const [outpaintPreset, setOutpaintPreset] = useState<string>(OUTPAINT_OUTPUT_PRESETS[0]);
  const [direction, setDirection] = useState<OutpaintDirection>("symmetric");
  const [anchor, setAnchor] = useState<OutpaintAnchor>("center");
  const [promptMode, setPromptMode] = useState<string>("guided");
  const [guidance, setGuidance] = useState<number>(1.5);
  const [steps, setSteps] = useState<number>(50);

  const [scenePreset, setScenePreset] = useState<string>(PRODUCT_SCENE_OUTPUT_PRESETS[0]);
  const [sceneDirection, setSceneDirection] = useState<string>("clean_studio");
  const [backgroundStyle, setBackgroundStyle] = useState<string>("neutral");
  const [presetVariant, setPresetVariant] = useState<string>("v1");

  const [phase, setPhase] = useState<Phase>("idle");
  const [job, setJob] = useState<AdvancedJob | null>(null);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [evalRefreshKey, setEvalRefreshKey] = useState(0);

  const upload = useAssetUpload(getToken);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<number | null>(null);
  const runRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  // Server-published option lists. A failure here leaves the built-in enums.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const research = await getResearchOptions(tokenRef.current);
        if (!cancelled) setOptions(research);
      } catch {
        /* keep defaults */
      }
      try {
        const catalog = await getScenePresets(tokenRef.current);
        if (!cancelled) setScenes(catalog);
      } catch {
        /* keep defaults */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [accessToken]);

  // A result belongs to one module + one picture; changing either clears it.
  const clearRun = useCallback(() => {
    stopPolling();
    runRef.current += 1;
    setPhase("idle");
    setJob(null);
    setResultUrl(null);
    setRunError(null);
  }, [stopPolling]);

  useEffect(() => {
    if (upload.state.phase === "ready" && upload.state.asset) {
      setSource(upload.state.asset);
      clearRun();
    }
  }, [upload.state.phase, upload.state.asset, clearRun]);

  useEffect(() => {
    const allowed = OUTPAINT_ANCHORS_BY_DIRECTION[direction];
    if (!allowed.includes(anchor)) setAnchor(allowed[0] as OutpaintAnchor);
  }, [direction, anchor]);

  const busy = phase === "submitting" || phase === "polling" || upload.busy;

  const poll = useCallback(
    (jobId: string, runId: number) => {
      const startedAt = Date.now();
      stopPolling();
      pollRef.current = window.setInterval(() => {
        void (async () => {
          if (runRef.current !== runId) return;
          if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
            stopPolling();
            setPhase("error");
            setRunError("This run is taking longer than expected. Try again.");
            return;
          }
          try {
            const next = await getAdvancedJob(jobId, tokenRef.current);
            if (runRef.current !== runId) return;
            setJob(next);
            if (!isTerminalAdvancedStatus(next.status)) return;
            stopPolling();
            if (next.status === "completed") {
              const url =
                next.result_url ?? (await refreshAdvancedResultUrl(jobId, tokenRef.current));
              if (runRef.current !== runId) return;
              setResultUrl(url);
              setPhase("done");
            } else {
              setPhase("error");
              setRunError(
                next.error_message || "The transformation could not be completed. Try again.",
              );
            }
          } catch (caught) {
            if (runRef.current !== runId) return;
            stopPolling();
            setPhase("error");
            setRunError(
              caught instanceof GenerationApiError
                ? caught.message
                : "The run could not be checked. Try again.",
            );
          }
        })();
      }, POLL_INTERVAL_MS);
    },
    [stopPolling],
  );

  async function handleSubmit() {
    if (!source?.asset_id) return;
    clearRun();
    const runId = runRef.current;
    setPhase("submitting");
    const idempotencyKey = newIdempotencyKey();
    try {
      const created =
        module === "outpaint"
          ? await startOutpaint({
              sourceAssetId: source.asset_id,
              idempotencyKey,
              accessToken: tokenRef.current,
              selection: {
                outputPreset: outpaintPreset,
                direction,
                anchor,
                promptMode,
                guidance,
                steps,
              },
            })
          : await startProductScene({
              sourceAssetId: source.asset_id,
              idempotencyKey,
              accessToken: tokenRef.current,
              selection: {
                outputPreset: scenePreset,
                sceneDirection,
                backgroundStyle,
                presetVariant,
              },
            });
      if (runRef.current !== runId) return;
      setJob(created);
      if (isTerminalAdvancedStatus(created.status)) {
        if (created.status === "completed") {
          setResultUrl(created.result_url ?? null);
          setPhase("done");
        } else {
          setPhase("error");
          setRunError(created.error_message || "The transformation could not be completed.");
        }
        return;
      }
      setPhase("polling");
      poll(created.job_id, runId);
    } catch (caught) {
      if (runRef.current !== runId) return;
      setPhase("error");
      setRunError(
        caught instanceof GenerationApiError
          ? caught.message
          : "The run could not be started. Try again.",
      );
    }
  }

  const sceneOptions = scenes?.scene_directions ?? [
    { scene_direction: "clean_studio", label: "Clean studio" },
    { scene_direction: "premium_neutral", label: "Premium neutral" },
    { scene_direction: "warm_lifestyle", label: "Warm lifestyle" },
    { scene_direction: "natural_surface", label: "Natural surface" },
  ];
  const backgroundOptions = scenes?.background_styles ?? [
    "neutral",
    "soft_shadow",
    "high_key",
    "editorial",
  ];
  const variantOptions = scenes?.preset_variants ??
    options?.product_scene.preset_variants ?? ["v1", "v2"];
  const promptModes = options?.outpaint.prompt_modes ?? ["guided", "bare", "bright"];
  const guidanceValues = options?.outpaint.guidance ?? [1.5, 2, 2.5, 3, 3.5, 4, 5, 6];
  const stepsValues = options?.outpaint.steps ?? [20, 30, 40, 50];

  return (
    <div className="space-y-8">
      <div>
        <h3 className="text-left text-sm font-semibold text-foreground">
          Advanced features test bench
        </h3>
        <p className="mt-1 max-w-2xl text-left text-sm text-muted-foreground">
          Run smart resize or product scene on a picture with different settings, rate each result,
          and compare the averages below. Staging only.
        </p>
      </div>

      <div className="flex gap-2" role="tablist" aria-label="Feature">
        {(["outpaint", "product_scene"] as AdvancedModule[]).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={module === value}
            disabled={busy}
            onClick={() => {
              setModule(value);
              clearRun();
            }}
            className={`rounded-md border px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 ${
              module === value
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card text-foreground"
            }`}
          >
            {value === "outpaint" ? "Smart resize" : "Product scene"}
          </button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-5 rounded-lg border border-border bg-card p-6">
          <div className="space-y-2">
            <h4 className="text-left text-sm font-semibold text-foreground">1. Choose a picture</h4>
            <input
              ref={fileInputRef}
              type="file"
              accept={ASSET_ACCEPT_ATTRIBUTE}
              disabled={busy}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void upload.upload(file);
                event.target.value = "";
              }}
              className="block w-full text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              aria-label="Choose a picture to transform"
            />
            {upload.busy ? (
              <p className="text-left text-xs text-muted-foreground">Uploading…</p>
            ) : null}
            {upload.state.errorMessage ? (
              <p
                role="alert"
                className="rounded-md border border-destructive/30 bg-destructive/5 p-2 text-xs text-destructive"
              >
                {upload.state.errorMessage}
              </p>
            ) : null}
            {source ? (
              <div className="flex items-center gap-3 rounded-md border border-border p-2">
                <div className="h-16 w-16 overflow-hidden rounded border border-border bg-muted">
                  {source.read_url ? (
                    <img
                      src={source.read_url}
                      alt={`Chosen picture, ${source.width ?? "?"} by ${source.height ?? "?"} pixels`}
                      className="h-full w-full object-cover"
                    />
                  ) : null}
                </div>
                <p className="text-left text-xs text-muted-foreground">
                  {source.width ?? "?"} x {source.height ?? "?"} · ready
                </p>
              </div>
            ) : null}
          </div>

          <div className="space-y-4">
            <h4 className="text-left text-sm font-semibold text-foreground">2. Settings</h4>
            {module === "outpaint" ? (
              <>
                <Field label="Final size">
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={outpaintPreset}
                    onChange={(event) => setOutpaintPreset(event.target.value)}
                  >
                    {OUTPAINT_OUTPUT_PRESETS.map((preset) => (
                      <option key={preset} value={preset}>
                        {preset.replace("x", " x ")}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Where the new space goes">
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={direction}
                    onChange={(event) => setDirection(event.target.value as OutpaintDirection)}
                  >
                    {OUTPAINT_DIRECTIONS.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Keep the original at">
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={anchor}
                    onChange={(event) => setAnchor(event.target.value as OutpaintAnchor)}
                  >
                    {OUTPAINT_ANCHORS_BY_DIRECTION[direction].map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label="Wording sent with the picture"
                  hint="Chooses between fixed server texts. 'bare' sends no words at all."
                >
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={promptMode}
                    onChange={(event) => setPromptMode(event.target.value)}
                  >
                    {promptModes.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label="Imagination"
                  hint="Lower keeps the new area closer to the surrounding picture."
                >
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={String(guidance)}
                    onChange={(event) => setGuidance(Number(event.target.value))}
                  >
                    {guidanceValues.map((value) => (
                      <option key={value} value={String(value)}>
                        {value}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Detail passes" hint="More passes take longer.">
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={String(steps)}
                    onChange={(event) => setSteps(Number(event.target.value))}
                  >
                    {stepsValues.map((value) => (
                      <option key={value} value={String(value)}>
                        {value}
                      </option>
                    ))}
                  </select>
                </Field>
              </>
            ) : (
              <>
                <Field label="Final size">
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={scenePreset}
                    onChange={(event) => setScenePreset(event.target.value)}
                  >
                    {(scenes?.output_presets ?? PRODUCT_SCENE_OUTPUT_PRESETS).map((preset) => (
                      <option key={preset} value={preset}>
                        {preset.replace("x", " x ")}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Scene">
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={sceneDirection}
                    onChange={(event) => setSceneDirection(event.target.value)}
                  >
                    {sceneOptions.map((scene) => (
                      <option key={scene.scene_direction} value={scene.scene_direction}>
                        {scene.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Background">
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={backgroundStyle}
                    onChange={(event) => setBackgroundStyle(event.target.value)}
                  >
                    {backgroundOptions.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label="Scene wording"
                  hint="v1 is the wording live today; v2 asks for a brighter, more open exposure."
                >
                  <select
                    className={selectClass}
                    disabled={busy}
                    value={presetVariant}
                    onChange={(event) => setPresetVariant(event.target.value)}
                  >
                    {variantOptions.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </Field>
              </>
            )}
          </div>

          <Button
            type="button"
            className="w-full"
            disabled={!source?.asset_id || busy}
            onClick={() => void handleSubmit()}
          >
            {busy ? "Working…" : "Create image"}
          </Button>
          {!source ? (
            <p className="text-center text-xs text-muted-foreground">
              Choose a picture to continue.
            </p>
          ) : null}
        </section>

        <section className="space-y-4">
          <h4 className="text-left text-sm font-semibold text-foreground">Result</h4>
          {phase === "idle" ? (
            <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              No result yet. Choose a picture and settings, then create an image.
            </p>
          ) : null}
          {phase === "submitting" || phase === "polling" ? (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
              Working on it… {job?.progress ? `${job.progress}%` : ""}
            </div>
          ) : null}
          {phase === "error" ? (
            <div
              role="alert"
              className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive"
            >
              <span>{runError}</span>
              <Button type="button" variant="outline" size="sm" onClick={() => void handleSubmit()}>
                Retry
              </Button>
            </div>
          ) : null}
          {phase === "done" ? (
            resultUrl ? (
              <div className="space-y-3">
                <img
                  src={resultUrl}
                  alt={
                    module === "outpaint"
                      ? "Your picture extended to the chosen size"
                      : "Your product shown in the chosen scene"
                  }
                  className="w-full rounded-lg border border-border"
                />
                <a
                  href={resultUrl}
                  download
                  className="inline-flex rounded-md bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                >
                  Download
                </a>
                {job ? (
                  <ScoreCard
                    jobId={job.job_id}
                    accessToken={accessToken}
                    askBrightness={module === "product_scene"}
                    onSaved={() => setEvalRefreshKey((key) => key + 1)}
                  />
                ) : null}
              </div>
            ) : (
              <div className="rounded-lg border border-border bg-card p-4 text-sm">
                <p className="text-muted-foreground">The image is ready but the link expired.</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2"
                  onClick={() => {
                    if (!job) return;
                    void refreshAdvancedResultUrl(job.job_id, tokenRef.current).then(setResultUrl);
                  }}
                >
                  Show it
                </Button>
              </div>
            )
          ) : null}
        </section>
      </div>

      <EvalTable accessToken={accessToken} module={module} refreshKey={evalRefreshKey} />
    </div>
  );
}
