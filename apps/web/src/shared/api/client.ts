import { CompactEncrypt, importJWK } from "jose";
import type { components } from "./schema";
export type Project = components["schemas"]["Project"];
export type Server = components["schemas"]["Server"];
export type AuthState = components["schemas"]["AuthState"];
export type Connection = components["schemas"]["Connection"];
export type CheckResult = components["schemas"]["CheckResult"];
export type ServerInput = components["schemas"]["ServerInput"];
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
let csrf = "";
export async function initCsrf() {
  const response = await fetch("/api/auth/csrf", {
    credentials: "same-origin",
  });
  if (!response.ok)
    throw new ApiError("Не удалось установить соединение", response.status);
  csrf = (await response.json()).csrf;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  if (method !== "GET") await initCsrf();
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    throw new ApiError(
      data &&
        typeof data === "object" &&
        "detail" in data &&
        typeof data.detail === "string"
        ? data.detail
        : "Не удалось выполнить запрос. Повторите позже",
      response.status,
    );
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export async function encryptConnection(
  connection: Connection,
): Promise<string> {
  const data =
    await api<components["schemas"]["EncryptionKey"]>("/encryption-key");
  const key = await importJWK(data.key, "RSA-OAEP-256");
  return new CompactEncrypt(
    new TextEncoder().encode(JSON.stringify({ nonce: data.nonce, connection })),
  )
    .setProtectedHeader({
      alg: "RSA-OAEP-256",
      enc: "A256GCM",
      kid: data.key.kid,
    })
    .encrypt(key);
}
