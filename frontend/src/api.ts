export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  retryable: boolean;
  requestId?: string;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: unknown,
    retryable = false,
    requestId?: string,
  ) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryable = retryable;
    this.requestId = requestId;
  }
}

interface ApiOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }
  headers.set("Accept", "application/json");
  const response = await fetch(path, {
    ...options,
    headers,
    body,
    credentials: "include",
  });
  if (!response.ok) {
    let parsed: any = null;
    try {
      parsed = await response.json();
    } catch {
      // no JSON error body
    }
    const error = parsed?.error;
    throw new ApiError(
      response.status,
      error?.code || "request_failed",
      error?.message || `Request failed (HTTP ${response.status}).`,
      error?.details,
      Boolean(error?.retryable),
      error?.request_id,
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}
