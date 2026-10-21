"use client";
import {useCallback, useEffect, useRef, useState} from "react";

type IndexOption = {index_id: string; model: string; dimensions: number; ingestion_default: boolean};

export function useQueryIndexes(url: string, token: string | null, scope: string) {
  const [indexes, setIndexes] = useState<IndexOption[]>([]);
  const [selectedId, select] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  const load = useCallback(async (initial = false) => {
    const ticket = ++generation.current;
    if (!token || !scope) {setIndexes([]); select(""); setError(""); return;}
    setLoading(true);
    try {
      const response = await fetch(`${url}/api/search-indexes/available`, {headers:{Authorization:`Bearer ${token}`}});
      const body = await response.json();
      if (ticket !== generation.current) return;
      if (!response.ok) throw new Error(body.detail || "Index catalog unavailable");
      setIndexes(body.indexes); setError("");
      if (initial) select(body.indexes.find((i: IndexOption) => i.ingestion_default)?.index_id || "");
    } catch(e) {
      if (ticket === generation.current) {setIndexes([]); setError(e instanceof Error ? e.message : String(e));}
    } finally {if (ticket === generation.current) setLoading(false);}
  }, [url, token, scope]);
  useEffect(() => {setIndexes([]); select(""); void load(true); return () => {generation.current++;};}, [load]);
  const selected = indexes.find(i => i.index_id === selectedId);
  return {indexes, selectedId, select, selected, error, loading, canQuery:Boolean(selected && !loading), reload:() => load(false)};
}

export function EmbeddingIndexPicker({catalog:c, locale, disabled}: {
  catalog:ReturnType<typeof useQueryIndexes>; locale:"cs"|"en"; disabled:boolean;
}) {
  const cs = locale === "cs";
  return <div className="text-xs text-zinc-300">
    <label className="flex flex-wrap gap-2 items-center">{cs ? "Embeddingový index" : "Embedding index"}
      <select aria-label={cs ? "Embeddingový index" : "Embedding index"} value={c.selectedId}
        disabled={disabled || c.loading} onChange={e => c.select(e.target.value)}
        className="bg-slate-900 text-white border border-white/20 rounded-lg px-2 py-2 max-w-full">
        <option value="" disabled>{cs ? "Vyberte připravený index" : "Select a prepared index"}</option>
        {c.selectedId && !c.selected && <option value={c.selectedId} disabled>{cs ? "Vybraný index již není dostupný" : "Selected index is unavailable"}</option>}
        {c.indexes.map(index => <option key={index.index_id} value={index.index_id}>{index.model} · {index.dimensions} dim · {index.index_id.slice(0,8)}</option>)}
      </select>
    </label>
    {c.error && <p role="alert" className="text-amber-300">{c.error}</p>}
    {!c.loading && !c.error && !c.indexes.length && <p>{cs ? "Není dostupný připravený index. Kontaktujte správce." : "No prepared index is available. Contact your administrator."}</p>}
    <button type="button" disabled={disabled || c.loading} onClick={() => void c.reload()} className="mt-1 underline text-indigo-300">{cs ? "Obnovit indexy" : "Refresh indexes"}</button>
  </div>;
}
