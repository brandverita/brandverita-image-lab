/**
 * Studio export — input image pane.
 *
 * Upload a new image or pick a recent one. Images are referenced by asset ID;
 * previews use the short-lived signed `read_url` returned by the API and are
 * never stored anywhere.
 */

import { useCallback, useEffect, useState } from "react";
import {
  ASSET_ACCEPT_ATTRIBUTE,
  ASSET_MAX_BYTES,
  TransformationApiError,
  type AssetRecord,
} from "../client/types";
import type { GenerationClient } from "../client/generationClient";

export function SourceAssetPicker({
  client,
  selected,
  onSelect,
  disabled,
}: {
  client: GenerationClient;
  selected: AssetRecord | null;
  onSelect: (asset: AssetRecord | null) => void;
  disabled?: boolean;
}) {
  const [recent, setRecent] = useState<AssetRecord[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRecent((await client.listAssets(8)).filter((asset) => asset.status === "ready"));
    } catch {
      /* a failed list is not worth an error banner here */
    }
  }, [client]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setUploading(true);
      try {
        const asset = await client.uploadInputAsset(file);
        if (asset.status !== "ready") {
          setError("That image was not accepted. Try a different file.");
          return;
        }
        onSelect(asset);
        void refresh();
      } catch (uploadError) {
        setError(
          uploadError instanceof TransformationApiError
            ? uploadError.message
            : "The upload did not complete. Please try again.",
        );
      } finally {
        setUploading(false);
      }
    },
    [client, onSelect, refresh],
  );

  return (
    <section className="space-y-4" aria-labelledby="source-heading">
      <h2 id="source-heading" className="text-left text-sm font-semibold text-slate-900">
        1. Choose an image
      </h2>

      <label
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 bg-white px-4 py-8 text-center transition hover:border-blue-600 focus-within:border-blue-600 focus-within:ring-2 focus-within:ring-blue-600/30 ${
          disabled || uploading ? "pointer-events-none opacity-60" : ""
        }`}
      >
        <span className="text-sm font-medium text-slate-700">
          {uploading ? "Checking your image…" : "Upload a PNG, JPEG or WebP"}
        </span>
        <span className="text-xs text-slate-500">
          Up to {Math.round(ASSET_MAX_BYTES / (1024 * 1024))} MB and 4096 x 4096 pixels
        </span>
        <input
          type="file"
          className="sr-only"
          accept={ASSET_ACCEPT_ATTRIBUTE}
          disabled={disabled || uploading}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) void handleFile(file);
          }}
        />
      </label>

      {error ? (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      ) : null}

      {selected?.read_url ? (
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <img
            src={selected.read_url}
            alt="The image you selected, ready to transform"
            className="mx-auto max-h-48 w-auto rounded"
          />
          <p className="mt-2 text-center text-xs text-slate-500">
            {selected.width} x {selected.height} px
          </p>
        </div>
      ) : null}

      {recent.length > 0 ? (
        <div>
          <p className="mb-2 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            Recent uploads
          </p>
          <ul className="grid grid-cols-4 gap-2">
            {recent.map((asset) => (
              <li key={asset.asset_id}>
                <button
                  type="button"
                  disabled={disabled}
                  onClick={() => onSelect(asset)}
                  aria-label={`Use the ${asset.width} by ${asset.height} pixel upload`}
                  aria-pressed={selected?.asset_id === asset.asset_id}
                  className={`block w-full overflow-hidden rounded border bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
                    selected?.asset_id === asset.asset_id ? "border-blue-600" : "border-slate-200"
                  }`}
                >
                  {asset.read_url ? (
                    <img src={asset.read_url} alt="" className="h-16 w-full object-cover" />
                  ) : (
                    <span className="block h-16 w-full" />
                  )}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
