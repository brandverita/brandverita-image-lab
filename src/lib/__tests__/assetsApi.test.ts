import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ASSET_MAX_BYTES,
  AssetApiError,
  createUploadAuthorization,
  finalizeAsset,
  formatBytes,
  isAllowedAssetType,
  shortHash,
  validateFileLocally,
} from "@/lib/assetsApi";

const file = (name: string, type: string, size: number) => ({ name, type, size });

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn(async () =>
    new Response(typeof body === "string" ? body : JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe("local validation", () => {
  it("allows only png, jpeg and webp", () => {
    expect(isAllowedAssetType("image/png")).toBe(true);
    expect(isAllowedAssetType("image/gif")).toBe(false);
    expect(isAllowedAssetType("image/svg+xml")).toBe(false);
    expect(isAllowedAssetType("application/pdf")).toBe(false);
  });

  it.each(["image/gif", "image/svg+xml", "application/pdf", "image/avif", "image/tiff"])(
    "rejects %s with invalid_file_type",
    (type) => {
      expect(() => validateFileLocally(file("x.png", type, 100))).toThrowError(
        expect.objectContaining({ code: "invalid_file_type" }),
      );
    },
  );

  it("rejects an extension that does not match the declared type", () => {
    expect(() => validateFileLocally(file("photo.png", "image/jpeg", 100))).toThrowError(
      expect.objectContaining({ code: "invalid_file_type" }),
    );
    expect(() => validateFileLocally(file("photo.jpeg", "image/jpeg", 100))).not.toThrow();
  });

  it("rejects files over 10 MB", () => {
    expect(() => validateFileLocally(file("a.png", "image/png", ASSET_MAX_BYTES + 1))).toThrowError(
      expect.objectContaining({ code: "file_too_large" }),
    );
    expect(() => validateFileLocally(file("a.png", "image/png", ASSET_MAX_BYTES))).not.toThrow();
  });

  it("rejects an empty file", () => {
    expect(() => validateFileLocally(file("a.png", "image/png", 0))).toThrowError(AssetApiError);
  });
});

describe("error mapping", () => {
  it("maps structured API error codes", async () => {
    mockFetch(422, { detail: { error_code: "asset_validation_failed", error_message: "nope" } });
    await expect(finalizeAsset("abc", "token")).rejects.toMatchObject({
      code: "asset_validation_failed",
      status: 422,
    });
  });

  it("maps 401 to a session-expired error", async () => {
    mockFetch(401, "Unauthorized");
    await expect(finalizeAsset("abc", null)).rejects.toMatchObject({ code: "unauthorized" });
  });

  it("maps 404 and 503", async () => {
    mockFetch(404, "");
    await expect(finalizeAsset("abc", "t")).rejects.toMatchObject({ code: "asset_not_found" });
    mockFetch(503, { error_code: "storage_unavailable" });
    await expect(finalizeAsset("abc", "t")).rejects.toMatchObject({ code: "storage_unavailable" });
  });

  it("never leaks the upload credential in an error message", async () => {
    const secret = "https://example.supabase.co/storage/v1/object/upload/sign/x?token=SECRET";
    mockFetch(200, { asset_id: "a1", upload_url: secret, content_type: "image/png" });
    const authorization = await createUploadAuthorization({
      file: file("a.png", "image/png", 10),
      idempotencyKey: "11111111-1111-4111-8111-111111111111",
      accessToken: "t",
    });
    expect(authorization.upload_url).toBe(secret);

    mockFetch(503, { error_code: "storage_unavailable" });
    const error = await finalizeAsset("a1", "t").catch((e: AssetApiError) => e);
    expect(String((error as AssetApiError).message)).not.toContain("SECRET");
  });

  it("does not call the API when local validation fails", () => {
    const fetchMock = mockFetch(200, {});
    expect(() =>
      createUploadAuthorization({
        file: file("a.gif", "image/gif", 10),
        idempotencyKey: "k",
      }),
    ).toThrowError(expect.objectContaining({ code: "invalid_file_type" }));
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("formatters", () => {
  it("formats bytes and hashes safely", () => {
    expect(formatBytes(0)).toBe("—");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.00 MB");
    expect(shortHash(null)).toBe("—");
    expect(shortHash("a".repeat(64))).toBe(`${"a".repeat(12)}…`);
  });
});
