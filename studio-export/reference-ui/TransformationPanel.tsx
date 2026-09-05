/**
 * Studio export — reference two-pane screen for both features.
 *
 * Left: image + options. Right: result. Copy this file into Studio and replace
 * the styling with Studio's own components; the wiring is the part that matters.
 */

import { useEffect, useMemo, useState } from "react";
import { createGenerationClient } from "../client/generationClient";
import { useTransformation } from "../client/useTransformation";
import type {
  AssetRecord,
  SceneDirection,
  TransformationModule,
  TransformationRequest,
} from "../client/types";
import {
  ModuleTabs,
  OutpaintControls,
  ProductSceneControls,
  type OutpaintSelection,
  type ProductSceneSelection,
} from "./OptionControls";
import { ResultPane } from "./ResultPane";
import { SourceAssetPicker } from "./SourceAssetPicker";

export function TransformationPanel({
  baseUrl,
  getAccessToken,
}: {
  baseUrl: string;
  getAccessToken: () => Promise<string | null> | string | null;
}) {
  const client = useMemo(
    () => createGenerationClient({ baseUrl, getAccessToken }),
    [baseUrl, getAccessToken],
  );

  const [module, setModule] = useState<TransformationModule>("outpaint");
  const [source, setSource] = useState<AssetRecord | null>(null);
  const [sceneLabels, setSceneLabels] = useState<Partial<Record<SceneDirection, string>>>({});

  const [outpaint, setOutpaint] = useState<OutpaintSelection>({
    outputPreset: "1200x627",
    direction: "symmetric",
    anchor: "center",
  });
  const [scene, setScene] = useState<ProductSceneSelection>({
    outputPreset: "1080x1080",
    sceneDirection: "clean_studio",
    backgroundStyle: "neutral",
  });

  const { phase, job, resultUrl, errorMessage, isBusy, start, retry, reset, refreshResultUrl } =
    useTransformation(client);

  // Live labels for the product-scene options; silent fallback to the built-ins.
  useEffect(() => {
    if (module !== "product_scene") return;
    let active = true;
    void client
      .getScenePresets()
      .then((catalog) => {
        if (!active) return;
        setSceneLabels(
          Object.fromEntries(catalog.scene_directions.map((s) => [s.scene_direction, s.label])),
        );
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [client, module]);

  const canSubmit = Boolean(source?.asset_id) && !isBusy;

  function handleSubmit() {
    if (!source?.asset_id) return;
    const request: TransformationRequest =
      module === "outpaint"
        ? {
            module: "outpaint",
            source_asset_id: source.asset_id,
            output_preset: outpaint.outputPreset,
            params: {
              expansion_mode: "anchor_directional",
              direction: outpaint.direction,
              anchor: outpaint.anchor,
              style_mode: "preserve_source",
            },
          }
        : {
            module: "product_scene",
            source_asset_id: source.asset_id,
            output_preset: scene.outputPreset,
            params: {
              scene_direction: scene.sceneDirection,
              background_style: scene.backgroundStyle,
              preserve_subject: true,
            },
          };
    void start(request);
  }

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8">
      <header className="mx-auto mb-8 max-w-6xl">
        <h1 className="text-left text-2xl font-semibold tracking-tight text-slate-900">
          Image tools
        </h1>
        <p className="mt-1 text-left text-sm text-slate-600">
          Resize a picture without cropping it, or place a product in a new scene.
        </p>
      </header>

      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-2">
        <div className="space-y-6 rounded-lg border border-slate-200 bg-white p-6">
          <ModuleTabs
            value={module}
            disabled={isBusy}
            onChange={(next) => {
              setModule(next);
              reset();
            }}
          />

          <SourceAssetPicker
            client={client}
            selected={source}
            disabled={isBusy}
            onSelect={(asset) => {
              setSource(asset);
              reset();
            }}
          />

          <section aria-labelledby="options-heading" className="space-y-4">
            <h2 id="options-heading" className="text-left text-sm font-semibold text-slate-900">
              2. Choose how it should look
            </h2>
            {module === "outpaint" ? (
              <OutpaintControls value={outpaint} onChange={setOutpaint} disabled={isBusy} />
            ) : (
              <ProductSceneControls
                value={scene}
                onChange={setScene}
                sceneLabels={sceneLabels}
                disabled={isBusy}
              />
            )}
          </section>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="w-full rounded-md bg-blue-700 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            {isBusy ? "Working…" : "Create image"}
          </button>
          {!source ? (
            <p className="text-center text-xs text-slate-500">Choose an image to continue.</p>
          ) : null}
        </div>

        <ResultPane
          phase={phase}
          job={job}
          resultUrl={resultUrl}
          errorMessage={errorMessage}
          onRetry={retry}
          onRefreshUrl={refreshResultUrl}
        />
      </div>
    </div>
  );
}
