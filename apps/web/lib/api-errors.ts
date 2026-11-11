/** Browser-safe API error type + error parsing (shared by client and server). */

import { translateCode } from "./errors-fa";

export class ApiError extends Error {
  code: string;
  params: Record<string, unknown>;
  status: number;

  constructor(code: string, status: number, params: Record<string, unknown> = {}) {
    super(translateCode(code));
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.params = params;
  }
}

export function messageOf(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return translateCode("network");
  return translateCode("unknown");
}

export function toApiError(status: number, body: unknown): ApiError {
  if (body && typeof body === "object" && "error" in body) {
    const payload = (body as { error?: { code?: string; params?: Record<string, unknown> } }).error;
    return new ApiError(payload?.code ?? "unknown", status, payload?.params ?? {});
  }
  if (status === 401) return new ApiError("auth.missing_token", status);
  if (status === 403) return new ApiError("auth.forbidden", status);
  if (status === 404) return new ApiError("common.not_found", status);
  return new ApiError("unknown", status);
}
