// @vitest-environment node
import { beforeEach, describe, it, expect, vi } from "vitest";
import { api, initCsrf, ApiError, encryptConnection } from "./client";
import { generateKeyPair, exportJWK, compactDecrypt } from "jose";
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});
function reply(status: number, data: unknown) {
  return new Response(status === 204 ? null : JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
describe("API transport", () => {
  it("refreshes csrf on mutation, handles JSON and empty success", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(reply(200, { csrf: "bound" }) as Response)
      .mockResolvedValueOnce(reply(201, { id: "p" }) as Response);
    expect(await api("/projects", "POST", { name: "P" })).toEqual({ id: "p" });
    expect(fetch).toHaveBeenLastCalledWith(
      "/api/projects",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "X-CSRF-Token": "bound" }),
        body: '{"name":"P"}',
      }),
    );
    vi.mocked(fetch).mockResolvedValueOnce(reply(204, null) as Response);
    expect(await api("/empty")).toBeUndefined();
  });
  it("reports public errors without leaking arbitrary payload", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      reply(403, { detail: "Denied" }) as Response,
    );
    await expect(api("/denied")).rejects.toMatchObject({
      message: "Denied",
      status: 403,
    });
    vi.mocked(fetch).mockResolvedValueOnce(
      reply(500, { detail: { private: "secret" } }) as Response,
    );
    await expect(api("/failed")).rejects.toBeInstanceOf(ApiError);
    vi.mocked(fetch).mockResolvedValueOnce({
      ok: false,
      status: 502,
      json: () => Promise.reject(Error("invalid")),
    } as unknown as Response);
    await expect(api("/bad")).rejects.toThrow("Не удалось выполнить запрос");
    vi.mocked(fetch).mockResolvedValueOnce(reply(503, null) as Response);
    await expect(initCsrf()).rejects.toThrow(
      "Не удалось установить соединение",
    );
  });
  it("encrypts a session-bound JWE readable only with private key", async () => {
    const { privateKey, publicKey } = await generateKeyPair("RSA-OAEP-256");
    const key = { ...(await exportJWK(publicKey)), kid: "key1" };
    vi.mocked(fetch).mockResolvedValueOnce(
      reply(200, { key, nonce: "one-use" }) as Response,
    );
    const connection = {
      host: "example.com",
      username: "deploy",
      method: "password" as const,
      password: "private-secret",
      port: 22,
      private_key: "",
      certificate: "",
      passphrase: "",
      fingerprint: "SHA256:test",
    };
    const result = await encryptConnection(connection);
    expect(result).not.toContain("private-secret");
    const decrypted = await compactDecrypt(result, privateKey);
    expect(JSON.parse(new TextDecoder().decode(decrypted.plaintext))).toEqual({
      nonce: "one-use",
      connection,
    });
  });
});
