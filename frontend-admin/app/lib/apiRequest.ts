export class ApiRequestError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function requestJson<T = any>(url: string, init: RequestInit = {},
  options: { timeoutMs?: number; language?: "cs" | "en" } = {}): Promise<T> {
  const cs = options.language !== "en";
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (init.signal?.aborted) controller.abort();
  else init.signal?.addEventListener("abort", abort, { once: true });
  let timedOut = false;
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, options.timeoutMs ?? 15000);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    const text = await response.text();
    let data: any = null;
    try { data = JSON.parse(text); } catch { /* Proxy failures may return plain text or HTML. */ }
    if (!response.ok) {
      const message = response.status >= 500
        ? (cs ? `Server je dočasně nedostupný (HTTP ${response.status}). Zkuste načtení znovu.` : `The server is temporarily unavailable (HTTP ${response.status}). Retry loading.`)
        : typeof data?.detail === "string" ? data.detail
        : (cs ? `Požadavek selhal (HTTP ${response.status}).` : `Request failed (HTTP ${response.status}).`);
      throw new ApiRequestError(response.status, message);
    }
    if (data === null || typeof data !== "object") {
      throw new ApiRequestError(response.status, cs ? "Server vrátil neplatnou odpověď. Zkuste načtení znovu." : "The server returned an invalid response. Retry loading.");
    }
    return data as T;
  } catch (error) {
    if (timedOut) throw new ApiRequestError(0, cs ? "Server neodpověděl včas. Zkuste načtení znovu." : "The server did not respond in time. Retry loading.");
    if (error instanceof ApiRequestError || controller.signal.aborted) throw error;
    throw new ApiRequestError(0, cs ? "Server není dostupný. Ověřte připojení a zkuste načtení znovu." : "The server is unavailable. Check your connection and retry loading.");
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener("abort", abort);
  }
}

export function chooseIndexSelection(current: string, indexes: { index_id: string; ingestion_default: boolean; ready?: boolean }[], initial = false): string {
  // Preserve an explicit selection even if it became invalid: never replace it silently.
  if (!initial && current) return current;
  return indexes.find(index => index.ingestion_default && index.ready !== false)?.index_id || "";
}

export function chooseModelSelection(current: string, models: { id: string; available: boolean }[], defaultId: string, initialCandidate?: string): string {
  const candidate = initialCandidate ?? current;
  if (models.some(model => model.id === candidate && model.available)) return candidate;
  // A failed initial load leaves no choice; a successful retry may select the declared default.
  if ((initialCandidate !== undefined || !current) && models.some(model => model.id === defaultId && model.available)) return defaultId;
  return current;
}

export function isExpiredSession(error: unknown, requestToken: string, currentToken: string | null): boolean {
  return error instanceof ApiRequestError && error.status === 401 && requestToken === currentToken;
}

export function pollHealth(url: string, onStatus: (online: boolean) => void,
  options: { intervalMs?: number; timeoutMs?: number } = {}): () => void {
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let active: AbortController | undefined;
  const check = async () => {
    active = new AbortController();
    try {
      await requestJson(url, { signal: active.signal }, { timeoutMs: options.timeoutMs ?? 5000 });
      if (!stopped) onStatus(true);
    } catch { if (!stopped) onStatus(false); }
    finally { if (!stopped) timer = setTimeout(check, options.intervalMs ?? 15000); }
  };
  void check();
  return () => { stopped = true; clearTimeout(timer); active?.abort(); };
}
