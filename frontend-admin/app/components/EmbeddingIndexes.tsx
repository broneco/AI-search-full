"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { requestJson, chooseIndexSelection } from "../lib/apiRequest";
import { ChunkingSettingsView } from "./ChunkingSettingsView";
import { ProcessingProgress, ProcessingFile } from "./ProcessingProgress";

export type EmbeddingIndex = { index_id: string; model: string; dimensions: number; embedding_profile: string | null;
  name?: string; chunking?: Record<string, any> | null; settings_revision?: number;
  settings_origin?: string; current_index_id?: string;
  embedding_location?: "local" | "cloud" | null;
  valid_chunks: number; total_chunks: number; ready: boolean; ingestion_default: boolean };
type Index = EmbeddingIndex;
type Catalog = { indexes: Index[]; profiles: { id: string; model: string; dimensions: number }[];
  documents: number; can_prepare: boolean; can_manage_settings?: boolean; preparation_unavailable_reason?: string; job?: Job | null };
type Job = {job_id: string; index_id: string | null; embedding_profile: string; action: "create" | "backfill";
  logical_index_id?: string | null;
  state: string; processed_chunks: number; valid_chunks: number; total_chunks: number; error_code: string | null;
  updated_at?: string; activity?: {phase: string; document_ids: string[]} | null};
const activeJob = (job?: Job | null) => Boolean(job && ["queued", "running", "cancelling"].includes(job.state));

export function useEmbeddingIndexes(url: string, token: string | null, scope: string, enabled: boolean, snapshot: Record<string, any> | null = null) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [progressOpen, setProgressOpen] = useState(false);
  const [creationProfile, setCreationProfile] = useState("");
  const [creationName, setCreationName] = useState("");
  const [files, setFiles] = useState<ProcessingFile[]>([]);
  const [filesError, setFilesError] = useState("");
  const generation = useRef(0);
  const pending = useRef(false);
  const identity = `${url}:${scope}:${token || ""}:${enabled}`;
  const identityRef = useRef(identity);
  identityRef.current = identity;
  useEffect(() => { setProgressOpen(false); setFiles([]); setFilesError(""); setCreationProfile(""); setCreationName(""); }, [identity]);
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
    if (action === "create" && !snapshot) { setError("Nejdříve načtěte nastavení v menu Chunkování."); return false; }
    pending.current = true; setSubmitting(true); setError("");
    const owner = identity;
    try {
      const body = await requestJson(`${url}/api/search-indexes/jobs`, { method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ action, embedding_profile: profile, index_id: indexId,
          ...(action === "create" ? {chunking:snapshot, name:creationName.trim() || undefined} : {}) }) });
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
  const initializeLegacy = async () => {
    if (!token || pending.current) return false;
    const owner=identity; pending.current=true;setSubmitting(true);setError("");
    try {
      await requestJson(`${url}/api/search-indexes/initialize-settings`,{method:"POST",headers:{Authorization:`Bearer ${token}`}});
      if (owner!==identityRef.current) return false;
      await load(false);return true;
    } catch(e) {if(owner===identityRef.current)setError(e instanceof Error?e.message:String(e));return false;}
    finally {if(owner===identityRef.current){pending.current=false;setSubmitting(false);}}
  };
  const saveEditor = async (values:{index_id?:string;expected_revision?:number;embedding_profile?:string;name?:string;chunking:Record<string,any>}) => {
    if (!token || pending.current || activeJob(job)) return null;
    const owner=identity;pending.current=true;setSubmitting(true);setError("");
    try {
      const body=await requestJson<{job:Job}>(`${url}/api/search-indexes/editor`,{method:"POST",headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},body:JSON.stringify(values)});
      if(owner!==identityRef.current)return null;
      setJob(body.job);setProgressOpen(true);await load(false);return body.job;
    } catch(e) {if(owner===identityRef.current)setError(e instanceof Error?e.message:String(e));return null;}
    finally {if(owner===identityRef.current){pending.current=false;setSubmitting(false);}}
  };
  const mutate = async (index: Index, method: "PATCH" | "DELETE", name?: string) => {
    if (!token || pending.current || activeJob(job)) return false;
    const owner=identity;
    pending.current=true; setSubmitting(true); setError("");
    try {
      await requestJson(`${url}/api/search-indexes/${index.index_id}${method === "DELETE" ? `?expected_revision=${index.settings_revision || 0}` : ""}`, {
        method, headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},
        ...(method === "PATCH" ? {body:JSON.stringify({name,expected_revision:index.settings_revision || 0})} : {})});
      if (owner !== identityRef.current) return false;
      await load(false); return true;
    } catch(e) { if (owner === identityRef.current) setError(e instanceof Error?e.message:String(e)); return false; }
    finally { if (owner === identityRef.current) {pending.current=false;setSubmitting(false);} }
  };
  return { catalog, selectedId, select: setSelectedId, selected, error, loading, job, preparing:submitting || activeJob(job),
    creationProfile:catalog?.profiles.some(p=>p.id===creationProfile) ? creationProfile : catalog?.profiles[0]?.id || "", setCreationProfile, creationName, setCreationName,
    snapshot, rename:(index:Index,name:string)=>mutate(index,"PATCH",name), remove:(index:Index)=>mutate(index,"DELETE"),
    initializeLegacy, saveEditor,
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
    phase={c.job.action === "create" && c.job.state === "completed" ? (cs?"Index vytvořen. Pro přípravu chunků a vektorů použijte Doplnit embeddingy.":"Index created. Use Complete embeddings to prepare chunks and vectors.") : activeJob(c.job)?({extracting:cs?"Načítám originál dokumentu.":"Reading the original document.",splitting:cs?"Připravuji vlastní chunky indexu podle uloženého nastavení.":"Preparing index chunks using its recorded settings.",...phases} as Record<string,string>)[c.job.activity?.phase || ""] || (cs?"Připravuji index a kontroluji korpus…":"Preparing the index and checking the corpus…"):states[c.job.state] || c.job.state}
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
          {i.name || i.model} · {i.dimensions} dim · {i.index_id.slice(0, 8)} · {i.valid_chunks}/{i.total_chunks}{!i.ready ? (cs ? " · nepřipravený" : " · not ready") : ""}
        </option>)}
      </select>
    </label>
    {c.error && <p role="alert" className="text-amber-300">{c.error}</p>}
  </div>;
}

export function EmbeddingIndexPanel({ controller: c, locale, expanded = false, onEdit, onNew }: { controller: Controller; locale: "cs" | "en"; expanded?: boolean; onEdit?:(id:string)=>void; onNew?:()=>void }) {
  const cs = locale === "cs";
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
      <span>{i.name || i.model} · {i.model} · {i.dimensions} dim · {i.index_id.slice(0, 8)}</span>
      <span>{i.valid_chunks}/{i.total_chunks} {cs ? "chunků" : "chunks"} · {i.ready ? (cs ? "připravený" : "ready") : (cs ? "nepřipravený" : "not ready")}</span>
      {i.ingestion_default && <span>{cs ? "Výchozí pro ingestaci" : "Ingestion default"}</span>}
      {onEdit && <button type="button" disabled={c.preparing} onClick={()=>onEdit(i.index_id)} className="text-indigo-300 underline">{cs?"Upravit chunkování":"Edit chunking"}</button>}
      {!onEdit && c.catalog?.can_prepare && i.embedding_profile && !i.ingestion_default && <button type="button" disabled={c.preparing}
        className="underline" onClick={() => void c.prepare(i.embedding_profile!, i.index_id)}>{cs ? "Doplnit embeddingy" : "Complete embeddings"}</button>}
      <IndexDetails key={`${i.index_id}:${i.settings_revision}`} index={i} controller={c} cs={cs}/>
    </div>)}
    {c.loading && <p>{cs?"Načítám indexy…":"Loading indexes…"}</p>}
    {onNew && <button type="button" disabled={c.preparing} onClick={onNew} className="mt-3 rounded-lg bg-indigo-600 px-3 py-2">{cs?"Vytvořit nový index":"Create a new index"}</button>}
    {c.error && <p role="alert" className="text-amber-300 mt-2">{c.error}</p>}
  </details>;
}

function IndexDetails({index:i,controller:c,cs}:{index:Index;controller:Controller;cs:boolean}) {
  const [name,setName]=useState(i.name || i.model);
  const [confirm,setConfirm]=useState(false);
  return <details className="w-full rounded-lg border border-white/10 p-3">
    <summary className="cursor-pointer">{cs?"Nastavení a správa indexu":"Index settings and management"}</summary>
    <p className="mt-3">{cs?"Embeddingový model":"Embedding model"}: {i.model} · {i.dimensions} dim · {i.embedding_profile}</p>
    {i.chunking ? <><p className="my-2">{cs?"Nastavení posledního výpočtu":"Settings used for the last build"}</p><ChunkingSettingsView value={i.chunking} cs={cs}/></> : <p className="my-3 text-amber-200">{cs?"Otevřete editor Chunkování; původnímu indexu se přiřadí současné výchozí parametry.":"Open the Chunking editor to initialize this legacy index with current defaults."}</p>}
    {c.catalog?.can_manage_settings && <div className="mt-3 space-y-3">
      <label>{cs?"Vlastní název":"Custom name"}<input value={name} onChange={e=>setName(e.target.value)} maxLength={120} className="mx-2 rounded bg-slate-900 border border-white/20 p-2"/></label>
      <button disabled={c.preparing || !name.trim() || name.trim() === i.name} onClick={()=>void c.rename(i,name.trim())} className="underline">{cs?"Uložit název":"Save name"}</button>
      {!i.ingestion_default && <div>{!confirm ? <button disabled={c.preparing} onClick={()=>setConfirm(true)} className="text-red-300 underline">{cs?"Smazat index…":"Delete index…"}</button> : <div className="p-3 border border-red-400/30 rounded-lg space-x-3"><p>{cs?`Smazat index „${i.name || i.model}“? Jeho vektory a nastavení budou odstraněny. Originály, historie a ostatní indexy zůstanou zachované.`:`Delete “${i.name || i.model}”? Its vectors and settings will be removed. Originals, history and other indexes are preserved.`}</p><button disabled={c.preparing} onClick={()=>void c.remove(i)} className="text-red-300 underline">{cs?"Potvrdit smazání":"Confirm deletion"}</button><button onClick={()=>setConfirm(false)}>{cs?"Zrušit":"Cancel"}</button></div>}</div>}
    </div>}
  </details>;
}
