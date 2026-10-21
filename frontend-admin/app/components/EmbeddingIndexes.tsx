"use client";
import { useCallback, useEffect, useRef, useState } from "react";

type Index = { index_id: string; model: string; dimensions: number; embedding_profile: string | null;
  embedding_location?: "local" | "cloud" | null;
  valid_chunks: number; total_chunks: number; ready: boolean; ingestion_default: boolean };
type Catalog = { indexes: Index[]; profiles: { id: string; model: string; dimensions: number }[];
  documents: number; can_prepare: boolean };

export function useEmbeddingIndexes(url: string, token: string | null, scope: string, enabled: boolean) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");
  const [preparing, setPreparing] = useState(false);
  const [loading, setLoading] = useState(false);
  const generation = useRef(0);
  const pending = useRef(false);
  const identity = `${url}:${scope}:${token || ""}:${enabled}`;
  const identityRef = useRef(identity);
  identityRef.current = identity;
  const load = useCallback(async (initial = false) => {
    const ticket = ++generation.current;
    if (!enabled || !token || !scope) { setCatalog(null); setSelectedId(""); return; }
    setLoading(true);
    try {
      const res = await fetch(`${url}/api/search-indexes`, { headers: { Authorization: `Bearer ${token}` } });
      const body = await res.json();
      if (ticket !== generation.current) return;
      if (!res.ok) throw new Error(body.detail || "Index catalog unavailable");
      setCatalog(body); setError("");
      if (initial) setSelectedId(body.indexes.find((i: Index) => i.ingestion_default && i.ready)?.index_id || "");
      // Refresh never silently replaces an explicit choice, even when it became invalid.
    } catch (e) { if (ticket === generation.current) { setError(e instanceof Error ? e.message : String(e)); setCatalog(null); } }
    finally { if (ticket === generation.current) setLoading(false); }
  }, [url, token, scope, enabled]);
  useEffect(() => { setCatalog(null); setSelectedId(""); void load(true); return () => { generation.current++; }; }, [load]);
  useEffect(() => {
    const refresh = () => { void load(false); };
    window.addEventListener("indexes-changed", refresh);
    return () => window.removeEventListener("indexes-changed", refresh);
  }, [load]);
  const prepare = async (profile: string, indexId?: string) => {
    if (!token || pending.current) return;
    pending.current = true; setPreparing(true); setError("");
    const owner = identity;
    try {
      const res = await fetch(`${url}/api/search-indexes/prepare`, { method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ embedding_profile: profile, index_id: indexId }) });
      const body = await res.json();
      if (owner !== identityRef.current) return;
      await load(false);
      if (owner !== identityRef.current) return;
      if (!res.ok) throw new Error(body.detail || "Index preparation failed");
    } catch (e) {
      if (owner === identityRef.current) setError(e instanceof Error ? e.message : String(e));
    } finally { pending.current = false; setPreparing(false); }
  };
  const selected = catalog?.indexes.find(i => i.index_id === selectedId);
  return { catalog, selectedId, select: setSelectedId, selected, error, loading, preparing,
    canQuery: !enabled || Boolean(selected?.ready && !preparing && !loading),
    prepare, reload: () => load(false) };
}

type Controller = ReturnType<typeof useEmbeddingIndexes>;

export function EmbeddingIndexPicker({ controller: c, locale, disabled }: { controller: Controller; locale: "cs" | "en"; disabled: boolean }) {
  const cs = locale === "cs";
  return <div className="text-xs text-zinc-300">
    <label>{cs ? "Embeddingový index pro tento dotaz" : "Embedding index for this query"}
      <select aria-label={cs ? "Embeddingový index" : "Embedding index"} value={c.selectedId}
        onChange={e => c.select(e.target.value)} disabled={disabled || c.loading || c.preparing}
        className="ml-2 bg-slate-900 border border-white/20 rounded-lg px-2 py-2 max-w-full">
        <option value="" disabled>{cs ? "Vyberte připravený index" : "Select a prepared index"}</option>
        {c.selectedId && !c.selected && <option value={c.selectedId} disabled>{cs ? "Vybraný index již není dostupný" : "Selected index unavailable"}</option>}
        {c.catalog?.indexes.map(i => <option key={i.index_id} value={i.index_id} disabled={!i.ready}>
          {i.model} · {i.dimensions} dim · {i.index_id.slice(0, 8)} · {i.valid_chunks}/{i.total_chunks}{!i.ready ? (cs ? " · nepřipravený" : " · not ready") : ""}
        </option>)}
      </select>
    </label>
    {c.error && <p role="alert" className="text-amber-300">{c.error}</p>}
  </div>;
}

export function EmbeddingIndexPanel({ controller: c, locale }: { controller: Controller; locale: "cs" | "en" }) {
  const cs = locale === "cs";
  const [profile, setProfile] = useState("");
  const chosenProfile = profile || c.catalog?.profiles[0]?.id || "";
  return <details className="text-xs text-zinc-300 border border-white/15 rounded-lg p-2">
    <summary className="cursor-pointer">{cs ? "Embeddingové indexy — příprava a porovnání" : "Embedding indexes — preparation and comparison"}</summary>
    <p className="my-2">{cs
      ? "Připravte další embeddingy stejných dokumentů a vyberte index u otázky. Texty a původní vektory zůstanou zachované. Výběr nemění ingestaci; jedna otázka používá jeden index."
      : "Prepare another embedding space over the same documents, then select it for a question. Text and existing vectors are preserved. Selection does not change ingestion; one question uses one index."}</p>
    <button type="button" disabled={c.preparing || c.loading} onClick={() => void c.reload()} className="underline">{cs ? "Obnovit přehled" : "Refresh"}</button>
    <p className="my-2">{c.catalog?.documents ?? "—"} {cs ? "dokumentů v tomto tenantu" : "documents in this tenant"}</p>
    {c.catalog?.indexes.map(i => <div key={i.index_id} className="flex flex-wrap gap-3 py-2 border-t border-white/10">
      <span>{i.model} · {i.dimensions} dim · {i.index_id.slice(0, 8)}</span>
      <span>{i.valid_chunks}/{i.total_chunks} {cs ? "chunků" : "chunks"} · {i.ready ? (cs ? "připravený" : "ready") : (cs ? "nepřipravený" : "not ready")}</span>
      {i.ingestion_default && <span>{cs ? "Výchozí pro ingestaci" : "Ingestion default"}</span>}
      {c.catalog?.can_prepare && i.embedding_profile && <button type="button" disabled={c.preparing}
        className="underline" onClick={() => void c.prepare(i.embedding_profile!, i.index_id)}>{cs ? "Doplnit embeddingy" : "Complete embeddings"}</button>}
    </div>)}
    {c.catalog?.can_prepare ? <div className="flex gap-3 items-center flex-wrap mt-3">
      <select aria-label={cs ? "Profil k přípravě" : "Profile to prepare"} value={chosenProfile} disabled={c.preparing}
        onChange={e => setProfile(e.target.value)} className="bg-slate-900 border border-white/20 rounded-lg p-2">
        {c.catalog.profiles.map(p => <option key={p.id} value={p.id}>{p.model} · {p.dimensions} dim</option>)}
      </select>
      <button type="button" disabled={c.preparing || !chosenProfile || !c.catalog.documents}
        onClick={() => void c.prepare(chosenProfile)} className="bg-indigo-600 rounded-lg px-3 py-2 disabled:opacity-50">
        {c.preparing ? (cs ? "Připravuji…" : "Preparing…") : (cs ? "Připravit / doplnit index" : "Prepare / complete index")}
      </button>
      <p>{cs ? "Zpracují se všechny existující chunky tohoto tenantu. Během porovnávání dokumenty neměňte." : "Processes all existing tenant chunks. Keep documents unchanged during comparison."}</p>
    </div> : <p className="mt-2">{cs ? "Příprava z konzole je dostupná v lokálním SQL prostředí. Cloudové indexy vyžadují řízenou migraci." : "Console preparation is available for local SQL. Cloud indexes require a controlled migration."}</p>}
    {c.error && <p role="alert" className="text-amber-300 mt-2">{c.error}</p>}
  </details>;
}
