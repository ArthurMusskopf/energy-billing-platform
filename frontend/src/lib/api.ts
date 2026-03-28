import { env } from "./env";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    try {
      const parsed = JSON.parse(text);
      const detail = parsed?.detail;

      if (typeof detail === "string" && detail.trim()) {
        throw new Error(detail);
      }

      if (detail && typeof detail === "object") {
        const message = typeof detail.message === "string" ? detail.message : null;
        const fields = Array.isArray(detail.fields) ? detail.fields.filter(Boolean).join(", ") : "";
        const suffix = fields ? ` Campos: ${fields}.` : "";
        throw new Error(`${message ?? "Erro na requisicao."}${suffix}`);
      }
    } catch (error) {
      if (error instanceof Error) {
        throw error;
      }
    }

    throw new Error(text || "Erro na requisicao");
  }

  return response.json() as Promise<T>;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  return handleResponse<T>(response);
}

export async function getJson<T>(path: string): Promise<T> {
  return requestJson<T>(path);
}

export async function postFormData<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    method: "POST",
    body: formData,
  });

  return handleResponse<T>(response);
}

export async function postJson<T>(path: string, body?: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export async function patchJson<T>(path: string, body?: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "PATCH",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
