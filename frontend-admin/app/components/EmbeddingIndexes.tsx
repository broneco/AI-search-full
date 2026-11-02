"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { requestJson, chooseIndexSelection } from "../lib/apiRequest";
import { ProcessingProgress, ProcessingFile } from "./ProcessingProgress";

type Index = { index_id: string; model: string; dimensions: number; embedding_profile: string | null;
  embedding_location?: "local" | "cloud" | null;
  valid_chunks: number; total_chunks: number; ready: boolean; ingestion_default: boolean };
type Catalog = { indexes: Index[]; profiles: { id: string; model: string; dimensions: number }[];
  documents: number; can_prepare: boolean; preparation_unavailable_reason?: string; job?: Job | null };
type Job = {job_id: string; index_id: string | null; embedding_profile: string; action: "create" | "backfill";
  state: string; processed_chunks: number; valid_chunks: number; total_chunks: number; error_code: string | null;
  updated_at?: string; activity?: {phase: string; document_ids: string[]} | null};
const activeJob = (job?: Job | null) => Boolean(job && ["queued", "running", "cancelling"].includes(job.state));

export function useEmbeddingIndexes(url: string, token: string | null, scope: string, enabled: boolean) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [progressOpen, setProgressOpen] = useState(false);
  const [files, setFiles] = useState<ProcessingFile[]>([]);
  const [filesError, setFilesError] = useState("");
  const generation = useRef(0);
  const pending = useRef(false);
  const identity = `${url}:${scope}:${token || ""}:${enabled}`;
  const identityRef = useRef(identity);
  identityRef.current = identity;
  useEffect(() => { setProgressOpen(false); setFiles([]); setFilesError(""); }, [identity]);
  useEffect(() => { if (activeJob(job)) setProgressOpen(true); }, [job?.job_id]);
  useEffect(() => {
    setFiles([]); setFilesError("");
    if (!progressOpen || !job || !token) return;
    const owner = identity;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const abort = new AbortController();
    const poll = async () => {
      try {
        const body = await requestJson(`${url}/api/search-indexes/jobs/${job.job_id}/files`, {signal:abort.signal,headers:{Authorization:`Bearer ${token}`}});
        if (stopped || owner !== identityRef.current) return;
        setFiles(body.files); setFilesError("");
      } catch(e) { if (!stopped && owner === identityRef.current) setFilesError(e instanceof Error?e.message:String(e)); }
      if (!stopped && activeJob(job)) timer=setTimeout(poll,4000);
    };
    void poll();
    return () => { stopped=true; clearTimeout(timer); abort.abort(); };
  }, [progressOpen, job?.job_id, job?.state, identity, url, token]);
  const load = useCallback(async (initial = false) => {
    const ticket = ++generation.current;
    if (!enabled || !token || !scope) { setCatalog(null); setSelectedId(""); setError(""); setLoading(false); return; }
    setLoading(true);
    try {
      const body = await requestJson(`${url}/api/search-indexes`, { headers: { Authorization: `Bearer ${token}` } });
      if (ticket !== generation.current) return;
      setCatalog(body); setJob(body.job || null); setError("");
      setSelectedId(current => chooseIndexSelection(current, body.indexes, initial));
      // Refresh never silently replaces an explicit choice, even when it became invalid.
    } catch (e) { if (ticket === generation.current) { setError(e instanceof Error ? e.message : String(e)); setCatalog(null); } }
    finally { if (ticket === generation.current) setLoading(false); }
  }, [url, token, scope, enabled]);
  useEffect(() => { setCatalog(null); setJob(null); setSubmitting(false); pending.current=false; setSelectedId(""); void load(true); return () => { generation.current++; }; }, [load]);
  useEffect(() => {
    const refresh = () => { void load(false); };
    window.addEventListener("indexes-changed", refresh);
    return () => window.removeEventListener("indexes-changed", refresh);
  }, [load]);
  useEffect(() => {
    if (!enabled || !token || !activeJob(job)) return;
    const owner = identity;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const abort = new AbortController();
    const poll = async () => {
      try {
        const body = await requestJson(`${url}/api/search-indexes/jobs/current`, {signal:abort.signal,headers:{Authorization:`Bearer ${token}`}});
        if (stopped || owner !== identityRef.current) return;
        setJob(body.job);
        if (!activeJob(body.job)) { window.dispatchEvent(new Event("indexes-changed")); return; }
      } catch(e) { if (!stopped && owner === identityRef.current) setError(e instanceof Error ? e.message : String(e)); }
      if (!stopped) timer = setTimeout(poll, 2500);
    };
    timer = setTimeout(poll, 1500);
    return () => { stopped=true; clearTimeout(timer); abort.abort(); };
  }, [url, token, scope, enabled, job?.job_id, job?.state, identity]);
  const start = async (action: "create" | "backfill", profile: string, indexId?: string) => {
    if (!token || identity !== identityRef.current || pending.current || activeJob(job)) return false;
    pending.current = true; setSubmitting(true); setError("");
    const owner = identity;
    try {
      const body = await requestJson(`${url}/api/search-indexes/jobs`, { method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ action, embedding_profile: profile, index_id: indexId }) });
      if (owner !== identityRef.current) return false;
      setJob(body.job);
      setProgressOpen(true);
      await load(false);
      return true;
    } catch (e) {
      if (owner === identityRef.current) setError(e instanceof Error ? e.message : String(e));
      return false;
    } finally { if (owner === identityRef.current) { pending.current=false; setSubmitting(false); } }
  };
  const cancel = async () => {
    if (!token || !job || pending.current) return;
    const owner=identity;
    pending.current=true; setSubmitting(true);
    try {
      const body=await requestJson(`${url}/api/search-indexes/jobs/${job.job_id}/cancel`, {method:"POST",headers:{Authorization:`Bearer ${token}`}});
      if (owner === identityRef.current) setJob(body.job);
    } catch(e) { if (owner === identityRef.current) setError(e instanceof Error ? e.message : String(e)); }
    finally { if (owner === identityRef.current) { pending.current=false; setSubmitting(false); } }
  };
  const selected = catalog?.indexes.find(i => i.index_id === selectedId);
  return { catalog, selectedId, select: setSelectedId, selected, error, loading, job, preparing:submitting || activeJob(job),
    progressOpen, openProgress:()=>setProgressOpen(true), closeProgress:()=>setProgressOpen(false), files, filesError,
    canQuery: !enabled || Boolean(selected?.ready && !loading),
    create: (profile:string) => start("create",profile),
    prepare: (profile:string,indexId?:string) => start("backfill",profile,indexId), cancel, reload: () => load(false) };
}

type Controller = ReturnType<typeof useEmbeddingIndexes>;

export function IndexProgress({controller:c,locale}:{controller:Controller;locale:"cs"|"en"}) {
  const cs=locale === "cs";
  if (!c.job) return null;
  const states:Record<string,string>={queued:cs?"Čeká":"Queued",running:cs?"Běží":"Running",cancelling:cs?"Zastavuje se":"Cancelling",cancelled:cs?"Zastaveno":"Cancelled",completed:cs?"Dokončeno":"Completed",failed:cs?"Selhalo":"Failed",interrupted:cs?"Přerušeno":"Interrupted"};
  const phases:Record<string,string>={embedding:cs?"Model počítá embeddingy aktuální dávky. První požadavek může načítat model.":"The model is computing the current batch. The first request may load the model.",saving:cs?"Ukládám ověřené vektory do indexu.":"Saving validated vectors to the index.",scanning:cs?"Kontroluji další dávku chunků.":"Checking the next batch of chunks."};
  return <ProcessingProgress open={c.progressOpen} close={c.closeProgress} locale={locale}
    title={cs?"Příprava embeddingového indexu":"Embedding index preparation"} state={states[c.job.state] || c.job.state}
    phase={activeJob(c.job)?phases[c.job.activity?.phase || ""] || (cs?"Připravuji index a kontroluji korpus…":"Preparing the index and checking the corpus…"):states[c.job.state] || c.job.state}
    files={c.files} value={c.job.valid_chunks} total={c.job.total_chunks} updatedAt={c.job.updated_at}
    error={c.filesError || c.job.error_code || c.error}>
    <span className="text-xs">{c.job.embedding_profile} · {c.job.index_id?.slice(0,8) || "…"} · {c.job.processed_chunks} {cs?"nově dopočtených chunků":"chunks computed in this run"}</span>
    {activeJob(c.job) && <button type="button" disabled={c.job.state === "cancelling"} onClick={()=>void c.cancel()} className="rounded-lg border border-amber-400/40 px-3 py-2 text-sm">{cs?"Zastavit po požadavku":"Stop after current request"}</button>}
  </ProcessingProgress>;
}

export function EmbeddingIndexPicker({ controller: c, locale, disabled }: { controller: Controller; locale: "cs" | "en"; disabled: boolean }) {
  const cs = locale === "cs";
  return <div className="text-xs text-zinc-300">
    <label>{cs ? "Embeddingový index pro tento dotaz" : "Embedding index for this query"}
      <select aria-label={cs ? "Embeddingový index" : "Embedding index"} value={c.selectedId}
        onChange={e => c.select(e.target.value)} disabled={disabled || c.loading}
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

export function EmbeddingIndexPanel({ controller: c, locale, expanded = false }: { controller: Controller; locale: "cs" | "en"; expanded?: boolean }) {
  const cs = locale === "cs";
  const [profile, setProfile] = useState("");
  const chosenProfile = profile || c.catalog?.profiles[0]?.id || "";
  return <details open={expanded || undefined} className="text-xs text-zinc-300 border border-white/15 rounded-lg p-2">
    <summary className="cursor-pointer">{cs ? "Embeddingové indexy — příprava a porovnání" : "Embedding indexes — preparation and comparison"}</summary>
    <p className="my-2">{cs
      ? "Připravte další embeddingy stejných dokumentů a vyberte index u otázky. Texty a původní vektory zůstanou zachované. Výběr nemění ingestaci; jedna otázka používá jeden index."
      : "Prepare another embedding space over the same documents, then select it for a question. Text and existing vectors are preserved. Selection does not change ingestion; one question uses one index."}</p>
    <button type="button" disabled={c.preparing || c.loading} onClick={() => void c.reload()} className="underline">{cs ? "Obnovit přehled" : "Refresh"}</button>
    <p className="my-2">{c.catalog?.documents ?? "—"} {cs ? "dokumentů v tomto tenantu" : "documents in this tenant"}</p>
    {c.job && <div role="status" className="my-3 p-3 border border-indigo-400/30 rounded-lg space-y-2">
      <button type="button" onClick={c.openProgress} className="rounded-lg bg-indigo-600 px-3 py-2">{cs?"Zobrazit průběh a soubory":"Show progress and files"}</button>
      <p>{cs ? "Poslední úloha" : "Latest operation"}: {c.job.action === "create" ? (cs ? "vytvoření indexu" : "create index") : (cs ? "dopočítání embeddingů" : "complete embeddings")} · {({queued:cs?"čeká":"queued",running:cs?"běží":"running",cancelling:cs?"zastavuje se":"cancelling",cancelled:cs?"zastavena":"cancelled",completed:cs?"dokončena":"completed",failed:cs?"chyba":"failed",interrupted:cs?"přerušena":"interrupted"} as Record<string,string>)[c.job.state] || c.job.state}</p>
      {c.job.action === "backfill" && <><progress className="w-full" value={c.job.valid_chunks} max={c.job.total_chunks || 1} aria-label={cs?"Průběh indexace":"Indexing progress"}/><p>{c.job.valid_chunks}/{c.job.total_chunks} {cs?"platných chunků":"current chunks"} · {c.job.processed_chunks} {cs?"dopočteno v této úloze":"written in this operation"}</p></>}
      {c.job.error_code && <p role="alert" className="text-amber-300">{cs?"Důvod":"Reason"}: {c.job.error_code}. {cs?"Hotové dávky jsou zachované. Po odstranění příčiny použijte Doplnit embeddingy.":"Completed batches are preserved. Resolve the cause and resume with Complete embeddings."}</p>}
      {c.preparing && <button type="button" disabled={c.job.state === "cancelling"} className="underline" onClick={() => void c.cancel()}>{cs?"Zastavit po probíhajícím požadavku":"Stop after current request"}</button>}
    </div>}
    {c.catalog?.indexes.map(i => <div key={i.index_id} className="flex flex-wrap gap-3 py-2 border-t border-white/10">
      <span>{i.model} · {i.dimensions} dim · {i.index_id.slice(0, 8)}</span>
      <span>{i.valid_chunks}/{i.total_chunks} {cs ? "chunků" : "chunks"} · {i.ready ? (cs ? "připravený" : "ready") : (cs ? "nepřipravený" : "not ready")}</span>
      {i.ingestion_default && <span>{cs ? "Výchozí pro ingestaci" : "Ingestion default"}</span>}
      {c.catalog?.can_prepare && i.embedding_profile && !i.ingestion_default && <button type="button" disabled={c.preparing}
        className="underline" onClick={() => void c.prepare(i.embedding_profile!, i.index_id)}>{cs ? "Doplnit embeddingy" : "Complete embeddings"}</button>}
    </div>)}
    {c.loading ? <p>{cs ? "Načítám přehled indexů…" : "Loading indexes…"}</p> : !c.catalog ? <p>{cs ? "Přehled indexů není načtený. Použijte Obnovit přehled." : "The index catalog is not loaded. Refresh the catalog."}</p> : c.catalog.can_prepare ? <div className="flex gap-3 items-center flex-wrap mt-3">
      <select aria-label={cs ? "Profil k přípravě" : "Profile to prepare"} value={chosenProfile} disabled={c.preparing}
        onChange={e => setProfile(e.target.value)} className="bg-slate-900 border border-white/20 rounded-lg p-2">
        {c.catalog.profiles.map(p => <option key={p.id} value={p.id}>{p.model} · {p.dimensions} dim</option>)}
      </select>
      <button type="button" disabled={c.preparing || !chosenProfile}
        onClick={() => void c.create(chosenProfile)} className="bg-indigo-600 rounded-lg px-3 py-2 disabled:opacity-50">
        {c.preparing ? (cs ? "Zpracovávám…" : "Working…") : (cs ? "Přidat index" : "Add index")}
      </button>
      <p>{cs ? "Přidání indexu zachová již existující index stejného profilu. Embeddingy dopočítáte tlačítkem u konkrétního indexu. Výchozí index ingestace je chráněný. Během výpočtu neměňte dokumenty ani chunky." : "Adding reuses an existing index of the same profile. Complete embeddings on the chosen index. The ingestion default is protected. Keep documents and chunks unchanged during the operation."}</p>
    </div> : <p className="mt-2">{cs ? "Správa indexů není v tomto prostředí aktivovaná nebo chybí databázová migrace." : "Index management is not enabled in this environment or its database migration is missing."} {c.catalog?.preparation_unavailable_reason}</p>}
    {c.error && <p role="alert" className="text-amber-300 mt-2">{c.error}</p>}
  </details>;
}
