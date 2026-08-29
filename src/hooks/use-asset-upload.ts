import { useCallback, useRef, useState } from "react";

import {
  AssetApiError,
  createUploadAuthorization,
  finalizeAsset,
  newAssetIdempotencyKey,
  uploadToAuthorization,
  validateFileLocally,
  type AssetErrorCode,
  type AssetMetadata,
} from "@/lib/assetsApi";

export type AssetUploadPhase =
  | "idle"
  | "authorizing"
  | "uploading"
  | "finalizing"
  | "ready"
  | "rejected"
  | "error";

export interface AssetUploadState {
  phase: AssetUploadPhase;
  fileName: string | null;
  asset: AssetMetadata | null;
  errorCode: AssetErrorCode | null;
  errorMessage: string | null;
}

const INITIAL: AssetUploadState = {
  phase: "idle",
  fileName: null,
  asset: null,
  errorCode: null,
  errorMessage: null,
};

/**
 * authorize -> direct-to-storage PUT -> finalize.
 *
 * The idempotency key is generated once per selected file and reused on retry, so
 * a retry re-authorizes the same pending asset instead of creating duplicates.
 * The signed upload URL never leaves this hook's local scope.
 */
export function useAssetUpload(getAccessToken: () => string | null | undefined) {
  const [state, setState] = useState<AssetUploadState>(INITIAL);
  const fileRef = useRef<File | null>(null);
  const keyRef = useRef<string | null>(null);
  const busy =
    state.phase === "authorizing" || state.phase === "uploading" || state.phase === "finalizing";

  const run = useCallback(
    async (file: File, idempotencyKey: string) => {
      const token = getAccessToken() ?? null;
      setState({
        phase: "authorizing",
        fileName: file.name,
        asset: null,
        errorCode: null,
        errorMessage: null,
      });
      try {
        validateFileLocally(file);
        const authorization = await createUploadAuthorization({
          file,
          idempotencyKey,
          accessToken: token,
        });

        if (!authorization.already_finalized) {
          setState((prev) => ({ ...prev, phase: "uploading" }));
          await uploadToAuthorization(authorization, file);
        }

        setState((prev) => ({ ...prev, phase: "finalizing" }));
        const asset = await finalizeAsset(authorization.asset_id, token);
        setState({
          phase: asset.status === "ready" ? "ready" : "rejected",
          fileName: file.name,
          asset,
          errorCode: null,
          errorMessage: null,
        });
      } catch (error) {
        const known = error instanceof AssetApiError ? error : null;
        const code: AssetErrorCode = known?.code ?? "server_error";
        setState({
          phase: code === "asset_validation_failed" ? "rejected" : "error",
          fileName: file.name,
          asset: null,
          errorCode: code,
          errorMessage:
            known?.message ?? "Something went wrong preparing this asset. Please retry.",
        });
      }
    },
    [getAccessToken],
  );

  const upload = useCallback(
    (file: File) => {
      fileRef.current = file;
      keyRef.current = newAssetIdempotencyKey();
      return run(file, keyRef.current);
    },
    [run],
  );

  const retry = useCallback(() => {
    const file = fileRef.current;
    const key = keyRef.current;
    if (!file || !key) return Promise.resolve();
    return run(file, key);
  }, [run]);

  const reset = useCallback(() => {
    fileRef.current = null;
    keyRef.current = null;
    setState(INITIAL);
  }, []);

  return { state, busy, upload, retry, reset, canRetry: Boolean(fileRef.current) };
}
