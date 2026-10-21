"use client";
import { useCallback, useEffect, useState, useRef } from "react";

export interface ModelOption {
  id: string; name: string; description: { cs: string; en: string };
  location: "cloud" | "local"; available: boolean; unavailable_reason?: string;
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
  catalog: ReturnType<typeof useModelCatalog>; locale: "cs" | "en"; disabled?: boolean; label?: string;
}) {
  const selected = catalog.models.find(m => m.id === catalog.modelId);
  return <div className="text-xs text-zinc-300 min-w-0">
    <label className="flex items-center gap-2">{label}
      {catalog.models.length > 1 || !selected ? <select aria-label={label} value={catalog.modelId}
        disabled={disabled} onChange={e => catalog.select(e.target.value)}
        className="bg-slate-900 text-white border border-white/20 rounded-lg px-2 py-2 max-w-full">
        <option value="" disabled>{locale === "cs" ? "Vyberte model" : "Select model"}</option>
        {catalog.models.map(m => <option key={m.id} value={m.id} disabled={!m.available}>
          {m.name} · {m.location === "local" ? "JHU" : "Cloud"}{!m.available ? (locale === "cs" ? " · nedostupný" : " · unavailable") : ""}
        </option>)}
      </select> : <span>{selected.name}</span>}
    </label>
    {selected && <p className="mt-1 text-zinc-400 max-w-xl">{selected.description[locale]}</p>}
    {selected?.location === "local" && <p className="mt-1 text-amber-300">{locale === "cs" ? "První odpověď může být pomalejší kvůli načítání modelu. Velké modely mohou překročit časový limit." : "The first response may be slower while loading the model. Large models may exceed the timeout."}</p>}
    {catalog.error && <p role="alert" className="text-amber-300">{catalog.error}</p>}
  </div>;
}
