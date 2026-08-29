import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useAssetUpload } from "@/hooks/use-asset-upload";
import {
  ASSET_ACCEPT_ATTRIBUTE,
  ASSET_MAX_BYTES,
  AssetApiError,
  formatBytes,
  listAssets,
  shortHash,
  type AssetMetadata,
} from "@/lib/assetsApi";

interface AssetTestPanelProps {
  accessToken: string | null;
}

const PHASE_LABEL: Record<string, string> = {
  authorizing: "Requesting upload authorization…",
  uploading: "Uploading to private storage…",
  finalizing: "Validating and finalizing…",
};

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-mono text-foreground">{value}</dd>
    </div>
  );
}

function AssetCard({ asset }: { asset: AssetMetadata }) {
  const dimensions =
    asset.width && asset.height ? `${asset.width} x ${asset.height}` : "—";
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex gap-4">
        <div className="h-24 w-24 shrink-0 overflow-hidden rounded-md border border-border bg-muted">
          {asset.read_url ? (
            <img
              src={asset.read_url}
              alt={`Private staging asset ${asset.asset_id.slice(0, 8)}, ${dimensions} pixels`}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
              no preview
            </div>
          )}
        </div>
        <dl className="min-w-0 flex-1">
          <MetaRow label="Status" value={asset.status} />
          <MetaRow label="Dimensions" value={dimensions} />
          <MetaRow label="Type" value={asset.content_type ?? "—"} />
          <MetaRow label="Size" value={formatBytes(asset.file_size)} />
          <MetaRow label="SHA256" value={shortHash(asset.sha256)} />
        </dl>
      </div>
    </div>
  );
}

export function AssetTestPanel({ accessToken }: AssetTestPanelProps) {
  const tokenRef = useRef(accessToken);
  tokenRef.current = accessToken;
  const getToken = useCallback(() => tokenRef.current, []);

  const { state, busy, upload, retry, reset, canRetry } = useAssetUpload(getToken);
  const [recent, setRecent] = useState<AssetMetadata[]>([]);
  const [recentError, setRecentError] = useState<string | null>(null);
  const [loadingRecent, setLoadingRecent] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const refreshRecent = useCallback(async () => {
    setLoadingRecent(true);
    setRecentError(null);
    try {
      setRecent(await listAssets(tokenRef.current, 12));
    } catch (error) {
      // A 404 here means the staging API does not expose the asset endpoints yet
      // (Phase 2A backend not deployed); that is not a user-facing error.
      if (error instanceof AssetApiError && error.code === "asset_not_found") {
        setRecent([]);
        setRecentError(null);
      } else {
        setRecentError(
          error instanceof AssetApiError
            ? error.message
            : "Could not load your recent staging assets.",
        );
      }
    } finally {
      setLoadingRecent(false);
    }
  }, []);

  useEffect(() => {
    void refreshRecent();
  }, [refreshRecent]);

  useEffect(() => {
    if (state.phase === "ready") void refreshRecent();
  }, [state.phase, refreshRecent]);

  const onPick = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) void upload(file);
  };

  return (
    <section aria-labelledby="asset-test-heading" className="space-y-4">
      <div>
        <h2 id="asset-test-heading" className="text-left text-lg font-semibold text-foreground">
          Asset Test (internal)
        </h2>
        <p className="mt-1 text-left text-sm text-muted-foreground">
          Prepares a controlled private input asset for future asset-to-asset workflows. PNG, JPEG or
          WebP, up to {formatBytes(ASSET_MAX_BYTES)}, max 4096 x 4096. Uploads go straight to private
          storage under a short-lived authorization; the API validates and finalizes them.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={inputRef}
            type="file"
            accept={ASSET_ACCEPT_ATTRIBUTE}
            onChange={onPick}
            disabled={busy}
            aria-label="Choose a PNG, JPEG or WebP image to upload as a staging asset"
            className="block text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-2 file:text-sm file:font-medium file:text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-60"
          />
          {state.phase !== "idle" && !busy ? (
            <Button variant="outline" size="sm" onClick={reset}>
              Clear
            </Button>
          ) : null}
        </div>

        {busy ? (
          <p role="status" className="mt-3 text-sm text-muted-foreground">
            {PHASE_LABEL[state.phase] ?? "Working…"}
          </p>
        ) : null}

        {(state.phase === "error" || state.phase === "rejected") && state.errorMessage ? (
          <div
            role="alert"
            className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            <p className="font-medium">
              {state.phase === "rejected" ? "Asset rejected" : "Upload failed"}
            </p>
            <p className="mt-1">{state.errorMessage}</p>
            {canRetry ? (
              <Button variant="outline" size="sm" className="mt-3" onClick={() => void retry()}>
                Retry
              </Button>
            ) : null}
          </div>
        ) : null}

        {state.phase === "ready" && state.asset ? (
          <div className="mt-4">
            <p className="mb-2 text-sm font-medium text-foreground">
              Ready: {state.fileName}
            </p>
            <AssetCard asset={state.asset} />
          </div>
        ) : null}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-left text-sm font-semibold text-foreground">
            Your recent ready staging assets
          </h3>
          <Button variant="ghost" size="sm" onClick={() => void refreshRecent()} disabled={loadingRecent}>
            {loadingRecent ? "Refreshing…" : "Refresh"}
          </Button>
        </div>

        {recentError ? (
          <div
            role="alert"
            className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
          >
            {recentError}
          </div>
        ) : recent.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            No staging assets yet. Upload an image above to create your first one.
          </div>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2">
            {recent.map((asset) => (
              <li key={asset.asset_id}>
                <AssetCard asset={asset} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
