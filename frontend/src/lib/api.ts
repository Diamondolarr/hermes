const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

type ApiErrorPayload = {
  detail?: string | { msg?: string }[];
};

export class ApiError extends Error {
  status: number;
  payload?: ApiErrorPayload;

  constructor(status: number, message: string, payload?: ApiErrorPayload) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

type ApiRequestOptions = RequestInit & {
  accessToken?: string | null;
  skipJsonContentType?: boolean;
};

function normalizeErrorMessage(payload?: ApiErrorPayload, fallback = "Something went wrong.") {
  if (!payload?.detail) {
    return fallback;
  }

  if (typeof payload.detail === "string") {
    return payload.detail;
  }

  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join(" ");
  }

  return fallback;
}

export async function apiRequest<T>(path: string, init?: ApiRequestOptions): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(init?.skipJsonContentType ? {} : { "Content-Type": "application/json" }),
      ...(init?.accessToken
        ? { Authorization: `Bearer ${init.accessToken}` }
        : {}),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let payload: ApiErrorPayload | undefined;

    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      payload = undefined;
    }

    throw new ApiError(response.status, normalizeErrorMessage(payload), payload);
  }

  return (await response.json()) as T;
}

export { API_BASE_URL };
