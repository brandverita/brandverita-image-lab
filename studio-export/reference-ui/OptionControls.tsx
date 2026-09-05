/**
 * Studio export — enum-only option controls.
 *
 * There is deliberately no text input anywhere in this file. Every choice maps
 * to a server-owned enum key; free text is refused by the API.
 */

import {
  BACKGROUND_STYLES,
  OUTPAINT_ANCHORS_BY_DIRECTION,
  OUTPAINT_DIRECTIONS,
  OUTPAINT_OUTPUT_PRESETS,
  PRODUCT_SCENE_OUTPUT_PRESETS,
  SCENE_DIRECTIONS,
  type BackgroundStyle,
  type OutpaintAnchor,
  type OutpaintDirection,
  type OutpaintOutputPreset,
  type ProductSceneOutputPreset,
  type SceneDirection,
  type TransformationModule,
} from "../client/types";

const DIRECTION_LABELS: Record<OutpaintDirection, string> = {
  left: "Extend to the left",
  right: "Extend to the right",
  top: "Extend upwards",
  bottom: "Extend downwards",
  symmetric: "Extend both sides evenly",
};

const ANCHOR_LABELS: Record<OutpaintAnchor, string> = {
  left: "Keep image at the left edge",
  right: "Keep image at the right edge",
  top: "Keep image at the top edge",
  bottom: "Keep image at the bottom edge",
  center: "Centre the image",
};

const BACKGROUND_LABELS: Record<BackgroundStyle, string> = {
  neutral: "Neutral",
  soft_shadow: "Soft shadow",
  high_key: "Bright, high key",
  editorial: "Editorial",
};

const FALLBACK_SCENE_LABELS: Record<SceneDirection, string> = {
  clean_studio: "Clean studio",
  premium_neutral: "Premium neutral",
  warm_lifestyle: "Warm lifestyle",
  natural_surface: "Natural surface",
};

const fieldClass =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 " +
  "focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/30 disabled:opacity-60";

const labelClass = "mb-1 block text-sm font-medium text-slate-700";

export interface OutpaintSelection {
  outputPreset: OutpaintOutputPreset;
  direction: OutpaintDirection;
  anchor: OutpaintAnchor;
}

export interface ProductSceneSelection {
  outputPreset: ProductSceneOutputPreset;
  sceneDirection: SceneDirection;
  backgroundStyle: BackgroundStyle;
}

export function ModuleTabs({
  value,
  onChange,
  disabled,
}: {
  value: TransformationModule;
  onChange: (next: TransformationModule) => void;
  disabled?: boolean;
}) {
  const tabs: { key: TransformationModule; label: string }[] = [
    { key: "outpaint", label: "Smart resize" },
    { key: "product_scene", label: "Product scene" },
  ];
  return (
    <div role="tablist" aria-label="Transformation type" className="flex gap-1 rounded-lg bg-slate-100 p-1">
      {tabs.map((tab) => {
        const active = tab.key === value;
        return (
          <button
            key={tab.key}
            role="tab"
            type="button"
            aria-selected={active}
            disabled={disabled}
            onClick={() => onChange(tab.key)}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
              active ? "bg-white text-blue-700 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

export function OutpaintControls({
  value,
  onChange,
  disabled,
}: {
  value: OutpaintSelection;
  onChange: (next: OutpaintSelection) => void;
  disabled?: boolean;
}) {
  const anchors = OUTPAINT_ANCHORS_BY_DIRECTION[value.direction];

  return (
    <div className="space-y-4">
      <div>
        <label className={labelClass} htmlFor="outpaint-size">
          Output size
        </label>
        <select
          id="outpaint-size"
          className={fieldClass}
          value={value.outputPreset}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...value, outputPreset: event.target.value as OutpaintOutputPreset })
          }
        >
          {OUTPAINT_OUTPUT_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {preset.replace("x", " x ")} px
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={labelClass} htmlFor="outpaint-direction">
          Where to add space
        </label>
        <select
          id="outpaint-direction"
          className={fieldClass}
          value={value.direction}
          disabled={disabled}
          onChange={(event) => {
            const direction = event.target.value as OutpaintDirection;
            const allowed = OUTPAINT_ANCHORS_BY_DIRECTION[direction];
            const anchor = allowed.includes(value.anchor) ? value.anchor : allowed[0]!;
            onChange({ ...value, direction, anchor });
          }}
        >
          {OUTPAINT_DIRECTIONS.map((direction) => (
            <option key={direction} value={direction}>
              {DIRECTION_LABELS[direction]}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={labelClass} htmlFor="outpaint-anchor">
          Original image position
        </label>
        <select
          id="outpaint-anchor"
          className={fieldClass}
          value={value.anchor}
          disabled={disabled || anchors.length === 1}
          onChange={(event) => onChange({ ...value, anchor: event.target.value as OutpaintAnchor })}
        >
          {anchors.map((anchor) => (
            <option key={anchor} value={anchor}>
              {ANCHOR_LABELS[anchor]}
            </option>
          ))}
        </select>
        <p className="mt-2 text-xs text-slate-500">
          Your original pixels are put back unchanged after the new area is filled in.
        </p>
      </div>
    </div>
  );
}

export function ProductSceneControls({
  value,
  onChange,
  sceneLabels,
  disabled,
}: {
  value: ProductSceneSelection;
  onChange: (next: ProductSceneSelection) => void;
  /** Labels from GET /v1/scene-presets; falls back to the built-in table. */
  sceneLabels?: Partial<Record<SceneDirection, string>>;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-4">
      <div>
        <label className={labelClass} htmlFor="scene-size">
          Output size
        </label>
        <select
          id="scene-size"
          className={fieldClass}
          value={value.outputPreset}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...value, outputPreset: event.target.value as ProductSceneOutputPreset })
          }
        >
          {PRODUCT_SCENE_OUTPUT_PRESETS.map((preset) => (
            <option key={preset} value={preset}>
              {preset.replace("x", " x ")} px
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={labelClass} htmlFor="scene-direction">
          Scene
        </label>
        <select
          id="scene-direction"
          className={fieldClass}
          value={value.sceneDirection}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...value, sceneDirection: event.target.value as SceneDirection })
          }
        >
          {SCENE_DIRECTIONS.map((scene) => (
            <option key={scene} value={scene}>
              {sceneLabels?.[scene] ?? FALLBACK_SCENE_LABELS[scene]}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className={labelClass} htmlFor="scene-style">
          Lighting
        </label>
        <select
          id="scene-style"
          className={fieldClass}
          value={value.backgroundStyle}
          disabled={disabled}
          onChange={(event) =>
            onChange({ ...value, backgroundStyle: event.target.value as BackgroundStyle })
          }
        >
          {BACKGROUND_STYLES.map((style) => (
            <option key={style} value={style}>
              {BACKGROUND_LABELS[style]}
            </option>
          ))}
        </select>
        <p className="mt-2 text-xs text-slate-500">
          The whole picture is re-rendered around your product, so check the result before publishing.
        </p>
      </div>
    </div>
  );
}
