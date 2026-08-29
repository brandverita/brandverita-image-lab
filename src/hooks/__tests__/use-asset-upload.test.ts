import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAssetUpload } from "@/hooks/use-asset-upload";
import { AssetApiError } from "@/lib/assetsApi";

const authorize = vi.fn();
const uploadPut = vi.fn();
const finalize = vi.fn();

vi.mock("@/lib/assetsApi", async () => {
  const actual = await vi.importActual<typeof import("@/lib/assetsApi")>("@/lib/assetsApi");
  return {
    ...actual,
    createUploadAuthorization: (...args: unknown[]) => authorize(...args),
    uploadToAuthorization: (...args: unknown[]) => uploadPut(...args),
    finalizeAsset: (...args: unknown[]) => finalize(...args),
  };
});

const pngFile = () =>
  new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "shot.png", { type: "image/png" });

beforeEach(() => {
  authorize.mockReset();
  uploadPut.mockReset();
  finalize.mockReset();
});

describe("useAssetUpload", () => {
  it("walks authorize -> upload -> finalize to ready", async () => {
    authorize.mockResolvedValue({
      asset_id: "a1",
      upload_url: "https://signed",
      content_type: "image/png",
    });
    uploadPut.mockResolvedValue(undefined);
    finalize.mockResolvedValue({ asset_id: "a1", status: "ready", width: 10, height: 10 });

    const { result } = renderHook(() => useAssetUpload(() => "token"));
    await act(async () => {
      await result.current.upload(pngFile());
    });

    await waitFor(() => expect(result.current.state.phase).toBe("ready"));
    expect(result.current.state.asset?.asset_id).toBe("a1");
    expect(uploadPut).toHaveBeenCalledTimes(1);
  });

  it("surfaces a rejected asset when finalize fails validation", async () => {
    authorize.mockResolvedValue({ asset_id: "a2", upload_url: "u", content_type: "image/png" });
    uploadPut.mockResolvedValue(undefined);
    finalize.mockRejectedValue(new AssetApiError("asset_validation_failed"));

    const { result } = renderHook(() => useAssetUpload(() => "token"));
    await act(async () => {
      await result.current.upload(pngFile());
    });

    await waitFor(() => expect(result.current.state.phase).toBe("rejected"));
    expect(result.current.state.errorCode).toBe("asset_validation_failed");
  });

  it("reports an expired session", async () => {
    authorize.mockRejectedValue(new AssetApiError("unauthorized"));
    const { result } = renderHook(() => useAssetUpload(() => null));
    await act(async () => {
      await result.current.upload(pngFile());
    });
    await waitFor(() => expect(result.current.state.phase).toBe("error"));
    expect(result.current.state.errorMessage).toContain("Session expired");
  });

  it("reuses the same idempotency key when retrying after an expired authorization", async () => {
    authorize.mockResolvedValue({ asset_id: "a3", upload_url: "u", content_type: "image/png" });
    uploadPut.mockRejectedValueOnce(new AssetApiError("upload_failed"));
    finalize.mockResolvedValue({ asset_id: "a3", status: "ready" });

    const { result } = renderHook(() => useAssetUpload(() => "token"));
    await act(async () => {
      await result.current.upload(pngFile());
    });
    await waitFor(() => expect(result.current.state.phase).toBe("error"));

    uploadPut.mockResolvedValueOnce(undefined);
    await act(async () => {
      await result.current.retry();
    });
    await waitFor(() => expect(result.current.state.phase).toBe("ready"));

    const firstKey = authorize.mock.calls[0]?.[0]?.idempotencyKey;
    const retryKey = authorize.mock.calls[1]?.[0]?.idempotencyKey;
    expect(firstKey).toBeTruthy();
    expect(retryKey).toBe(firstKey);
  });

  it("skips the upload when the asset was already finalized", async () => {
    authorize.mockResolvedValue({
      asset_id: "a4",
      upload_url: "u",
      content_type: "image/png",
      already_finalized: true,
    });
    finalize.mockResolvedValue({ asset_id: "a4", status: "ready" });

    const { result } = renderHook(() => useAssetUpload(() => "token"));
    await act(async () => {
      await result.current.upload(pngFile());
    });
    await waitFor(() => expect(result.current.state.phase).toBe("ready"));
    expect(uploadPut).not.toHaveBeenCalled();
  });
});
