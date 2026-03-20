import { env } from "./env";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
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
