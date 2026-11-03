"use client";
import {useEmbeddingIndexes} from "./EmbeddingIndexes";

export function IndexEditorHeader({controller:c,locale,mode,setMode,indexId,selectIndex,name,setName}: {
  controller:ReturnType<typeof useEmbeddingIndexes>;locale:"cs"|"en";mode:"existing"|"new";
  setMode:(mode:"existing"|"new")=>void;indexId:string;selectIndex:(id:string)=>void;name:string;setName:(name:string)=>void;
}) {
  const cs=locale==="cs";
  const selected=c.catalog?.indexes.find(i=>i.index_id===indexId);
  return <section className="w-full max-w-7xl glass-panel rounded-2xl border border-white/10 p-5 space-y-4">
    <div className="flex flex-wrap gap-3 justify-between items-center"><h2 className="font-bold text-white">{cs?"Chunkování indexu":"Index chunking"}</h2><button disabled={c.loading||c.preparing} onClick={()=>void(c.catalog?.can_manage_settings&&c.catalog.indexes.some(i=>!i.chunking)?c.initializeLegacy():c.reload())} className="text-xs text-indigo-300 underline">{cs?"Obnovit indexy":"Refresh indexes"}</button></div>
    <div role="group" aria-label={cs?"Způsob práce s indexem":"Index mode"} className="flex flex-wrap gap-2">
      {(["existing","new"] as const).map(value=><button type="button" key={value} aria-pressed={mode===value} disabled={c.preparing} onClick={()=>setMode(value)} className={`rounded-xl px-4 py-3 text-sm border ${mode===value?"border-indigo-400 bg-indigo-500/20 text-white":"border-white/10 text-zinc-400"}`}>{value==="existing"?(cs?"Upravuji existující":"Edit existing"):(cs?"Tvořím nové":"Create new")}</button>)}
    </div>
    {mode==="existing" && <label className="block text-xs text-zinc-300">{cs?"Vyberte index":"Choose index"}<select aria-label={cs?"Index k úpravě":"Index to edit"} value={indexId} disabled={c.loading||c.preparing} onChange={e=>selectIndex(e.target.value)} className="block w-full mt-2 rounded-lg border border-white/20 bg-slate-900 p-3"><option value="" disabled>{cs?"Vyberte existující index":"Choose an existing index"}</option>{c.catalog?.indexes.map(i=><option key={i.index_id} value={i.index_id}>{i.name||i.model} · {i.model} · {i.valid_chunks}/{i.total_chunks}{i.ingestion_default?(cs?" · výchozí":" · default"):""}</option>)}</select></label>}
    <div className="grid gap-4 md:grid-cols-2">
      <label className="text-xs text-zinc-300">{cs?"Název indexu":"Index name"}<input aria-label={cs?"Název indexu":"Index name"} maxLength={120} disabled={c.preparing||(mode==="existing"&&!selected)} value={name} onChange={e=>setName(e.target.value)} placeholder={cs?"Např. Nomic – kratší pasáže":"For example: Nomic – shorter passages"} className="block w-full mt-2 rounded-lg border border-white/20 bg-slate-900 p-3"/></label>
      {mode==="new" ? <label className="text-xs text-zinc-300">{cs?"Embeddingový model":"Embedding model"}<select aria-label={cs?"Embeddingový model nového indexu":"New index embedding model"} value={c.creationProfile} disabled={c.preparing} onChange={e=>c.setCreationProfile(e.target.value)} className="block w-full mt-2 rounded-lg border border-white/20 bg-slate-900 p-3">{c.catalog?.profiles.map(p=><option key={p.id} value={p.id}>{p.model} · {p.dimensions} dim</option>)}</select></label> : <div className="text-xs text-zinc-400">{cs?"Embeddingový model":"Embedding model"}<p className="mt-3 text-white">{selected?`${selected.model} · ${selected.dimensions} dim`:"—"}</p><p className="mt-1">{cs?"Model je u existujícího indexu pevný.":"The model of an existing index is fixed."}</p></div>}
    </div>
    {mode==="existing" && selected?.settings_origin==="assumed" && <p className="text-xs text-zinc-400">{cs?"U tohoto původního indexu jsme jako výchozí převzali současné parametry chunkování. Můžete je upravit a přepočítat.":"This legacy index starts with the current chunking parameters. You can edit them and rebuild it."}</p>}
    <p className="text-xs text-zinc-400">{cs?"Nastavení a náhled níže patří k tomuto indexu. Výpočet se spustí spodním tlačítkem; původní funkční verze zůstane dostupná do dokončení úpravy.":"The settings and preview below belong to this index. The bottom button starts processing; the working version remains available until its replacement is complete."}</p>
    {c.job && <button type="button" onClick={c.openProgress} className="text-xs text-indigo-300 underline">{cs?"Zobrazit průběh a soubory":"Show progress and files"}</button>}
    {c.job?.index_id && ["failed","cancelled","interrupted"].includes(c.job.state) && <button type="button" disabled={c.preparing} onClick={()=>void c.prepare(c.job!.embedding_profile,c.job!.index_id!)} className="ml-4 text-xs text-indigo-300 underline">{cs?"Pokračovat v nedokončeném výpočtu":"Resume unfinished build"}</button>}
    {!c.catalog?.can_manage_settings && !c.loading && <p role="alert" className="text-xs text-amber-200">{cs?"Editor čeká na databázovou migraci.":"The editor requires the database migration."}</p>}
    {c.error && <p role="alert" className="text-xs text-amber-200">{c.error}</p>}
  </section>;
}
