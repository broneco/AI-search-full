"use client";
import { useCallback, useEffect, useState, useRef } from "react";

export interface ModelOption {
  id: string; name: string; description: { cs: string; en: string };
  location: "cloud" | "local"; available: boolean; unavailable_reason?: string;
  purposes?: string[];
  parameters?: Record<string, string | number | null>;
}

export function parameterText(parameters?: ModelOption["parameters"]) {
  const labels: Record<string, string> = {context_tokens:"context", max_input_chars:"input chars", max_output_tokens:"output tokens", timeout_seconds:"timeout s", dimensions:"dim"};
  return Object.entries(parameters || {}).filter(([key, value]) => key !== "model" && value != null)
    .map(([key, value]) => `${labels[key] || key}: ${value}`).join(" · ");
}

export function useModelCatalog(url: string, token: string | null, purpose: string, scope: string) {
  const [models, setModels] = useState<ModelOption[]>([]);
  const [modelId, setModelId] = useState("");
  const [error, setError] = useState("");
  const generation = useRef(0);
  const key = `ai-model:${scope}:${purpose}`;
  const load = useCallback(async (initial = false) => {
    const request = ++generation.current;
    if (!token || !scope) { setModels([]); setModelId(""); return; }
    try {
      const res = await fetch(`${url}/api/models?purpose=${purpose}`, { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (request !== generation.current) return;
      if (!res.ok) throw new Error(data.detail || "Model catalog unavailable");
      setModels(data.models);
      setError("");
      setModelId(current => {
        const candidate = initial ? (localStorage.getItem(key) || data.default_model_id) : current;
        if (data.models.some((m: ModelOption) => m.id === candidate && m.available)) return candidate;
        if (initial && data.models.some((m: ModelOption) => m.id === data.default_model_id && m.available)) return data.default_model_id;
        return "";
      });
    } catch (e) { if (request !== generation.current) return; setError(String(e instanceof Error ? e.message : e)); setModels([]); setModelId(""); }
  }, [url, token, purpose, scope, key]);
  useEffect(() => { setModelId(""); void load(true); return () => { generation.current++; }; }, [load]);
  useEffect(() => {
    const refresh = () => { void load(false); };
    window.addEventListener("models-changed", refresh);
    return () => window.removeEventListener("models-changed", refresh);
  }, [load]);
  const select = (id: string) => { setModelId(id); localStorage.setItem(key, id); };
  return { models, modelId, select, error, reload: () => load(false) };
}

export function ModelPicker({ catalog, locale, disabled = false, label = "Model" }: {
  catalog: Pick<ReturnType<typeof useModelCatalog>, "models" | "modelId" | "select" | "error">; locale: "cs" | "en"; disabled?: boolean; label?: string;
}) {
  const selected = catalog.models.find(m => m.id === catalog.modelId);
  const [search, setSearch] = useState("");
  const menu = useRef<HTMLDetailsElement>(null);
  return <div className="text-xs text-zinc-300 min-w-0">
    <div className="mb-2 font-semibold">{label}</div>
    <details ref={menu} className="rounded-xl border border-white/20 bg-slate-900" onToggle={() => { if (!menu.current?.open) setSearch(""); }}>
      <summary aria-label={label} className="cursor-pointer p-3 text-white">{selected?.name || (locale === "cs" ? "Vyberte model" : "Select model")} <span className="text-zinc-400">{selected?.location === "local" ? " · JHU" : selected ? " · Cloud" : ""}</span></summary>
      <div className="p-3 border-t border-white/10">
        <input aria-label={`${label} — ${locale === "cs" ? "hledat" : "search"}`} placeholder={locale === "cs" ? "Hledat podle názvu, popisu nebo parametrů…" : "Search name, description or parameters…"}
          value={search} onChange={e => setSearch(e.target.value)} className="w-full rounded-lg border border-white/20 bg-black/30 p-2 mb-2" />
        <div className="max-h-72 overflow-auto space-y-2">
          {catalog.models.filter(m => `${m.name} ${m.description[locale]} ${parameterText(m.parameters)}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(m => <button
            key={m.id} type="button" disabled={disabled || !m.available} aria-pressed={m.id === catalog.modelId}
            onClick={() => { catalog.select(m.id); if (menu.current) menu.current.open = false; }}
            className={`block text-left w-full rounded-lg border p-3 disabled:opacity-40 ${m.id === catalog.modelId ? "border-indigo-400 bg-indigo-500/20" : "border-white/10 hover:bg-white/5"}`}>
            <strong>{m.name}</strong> · {m.location === "local" ? "JHU" : "Cloud"}
            <p className="text-zinc-400 mt-1">{parameterText(m.parameters)}</p>
            <p className="mt-1">{m.description[locale] || (locale === "cs" ? "Popis není vyplněný." : "No description yet.")}</p>
            {!m.available && <p>{m.unavailable_reason || (locale === "cs" ? "Nedostupný" : "Unavailable")}</p>}
          </button>)}
          {!catalog.models.some(m => `${m.name} ${m.description[locale]} ${parameterText(m.parameters)}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())) && <p>{locale === "cs" ? "Žádný odpovídající model." : "No matching models."}</p>}
        </div>
      </div>
    </details>
    {selected && <p className="mt-2 text-zinc-500">{parameterText(selected.parameters)}</p>}
    {selected && <p className="mt-1 text-zinc-400 max-w-xl">{selected.description[locale]}</p>}
    {selected?.location === "local" && <p className="mt-1 text-amber-300">{locale === "cs" ? "První odpověď může být pomalejší kvůli načítání modelu. Velké modely mohou překročit časový limit." : "The first response may be slower while loading the model. Large models may exceed the timeout."}</p>}
    {catalog.error && <p role="alert" className="text-amber-300">{catalog.error}</p>}
  </div>;
}
