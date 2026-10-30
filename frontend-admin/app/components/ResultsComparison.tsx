"use client";
import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { ModelOption, ModelPicker } from "./ModelPicker";
import { useEmbeddingIndexes } from "./EmbeddingIndexes";

type Source = {document_id:string; chunk_id:string; title:string; content:string; section_title:string|null;
  page_number:number|null; freshness_status:string; score:number};
type Answer = {role:"assistant";content:string;sources:Source[];model_name?:string;embedding_model?:string;search_index_id?:string};
type Options = {modelId:string;indexId:string;strategy:string;freshness:string;language:string;folder:string};
type Turn = {question:string; options:Options; answer?:Answer; error?:string; elapsed?:number; retrieval?:string;queued?:boolean};
type Pane = {options:Options;threadId?:string;turns:Turn[];busy:boolean;settingsOpen:boolean};
const emptyOptions = ():Options => ({modelId:"",indexId:"",strategy:"hybrid",freshness:"all",language:"all",folder:"all"});

export function ResultsComparison({url,token,locale,models,defaultModel,indexes,folders,renderAnswer,reloadModels}: {
  url:string;token:string;locale:"cs"|"en";models:ModelOption[];defaultModel:string;
  indexes:ReturnType<typeof useEmbeddingIndexes>;folders:string[];
  renderAnswer:(answer:Answer)=>ReactNode;reloadModels:()=>Promise<void>;
}) {
  const [panes,setPanes] = useState<Pane[]>([0,1].map(()=>({options:emptyOptions(),turns:[],busy:false,settingsOpen:true})));
  const [query,setQuery] = useState("");
  const initialized = useRef([false,false]);
  const initialIndex = useRef([false,false]);
  const running = useRef(false);
  const requests = useRef<AbortController[]>([]);
  const mounted = useRef(true);
  const cs = locale === "cs";
  useEffect(() => { mounted.current=true; return () => { mounted.current=false; requests.current.forEach(request=>request.abort()); }; },[]);
  useEffect(() => {
    if (!models.length) return;
    const first = initialized.current.map(value => !value);
    initialized.current = [true,true];
    setPanes(previous=>previous.map((pane,i)=>{
      if (first[i]) {
        return {...pane,options:{...pane.options,modelId:models.some(m=>m.id===defaultModel && m.available)?defaultModel:""}};
      }
      return models.some(m=>m.id===pane.options.modelId && m.available)?pane:{...pane,options:{...pane.options,modelId:""}};
    }));
  },[models,defaultModel]);
  useEffect(()=>{
    if (!indexes.catalog) return;
    const available=indexes.catalog.indexes;
    const first = initialIndex.current.map(value => !value);
    initialIndex.current = [true,true];
    setPanes(previous=>previous.map((pane,i)=>{
      if (first[i]) {
        return {...pane,options:{...pane.options,indexId:available.find(index=>index.ingestion_default && index.ready)?.index_id || ""}};
      }
      return available.some(index=>index.index_id===pane.options.indexId && index.ready)?pane:{...pane,options:{...pane.options,indexId:""}};
    }));
  },[indexes.catalog]);
  const busy=panes.some(p=>p.busy);
  const edit=(i:number,patch:Partial<Options>)=>setPanes(previous=>previous.map((pane,n)=>n===i?{...pane,options:{...pane.options,...patch}}:pane));
  const valid=(pane:Pane)=>models.some(m=>m.id===pane.options.modelId && m.available) && (pane.options.strategy==="keyword" || Boolean(indexes.catalog?.indexes.some(index=>index.index_id===pane.options.indexId && index.ready)));
  const submit=async (event:FormEvent)=>{
    event.preventDefault();
    if (running.current || !query.trim() || !panes.every(valid)) return;
    running.current=true;
    const question=query.trim(); setQuery("");
    const snapshots=panes.map(pane=>({...pane.options}));
    // Inference and embeddings share the single JHU slot. Queue whole variants
    // when both use it; unknown older index metadata is treated conservatively.
    const localPair=snapshots.every(option=>models.find(model=>model.id===option.modelId)?.location==="local"
      || (option.strategy!=="keyword" && indexes.catalog?.indexes.find(index=>index.index_id===option.indexId)?.embedding_location!=="cloud"));
    setPanes(previous=>previous.map((pane,i)=>({...pane,busy:true,settingsOpen:false,turns:[...pane.turns,{question,options:snapshots[i],queued:localPair && i===1}]})));
    const runVariant=async (pane:Pane,i:number)=>{
      if (!mounted.current) return;
      setPanes(previous=>previous.map((current,n)=>n===i?{...current,turns:current.turns.map((turn,j)=>j===current.turns.length-1?{...turn,queued:false}:turn)}:current));
      const controller=new AbortController();requests.current[i]=controller;
      const started=performance.now();
      let threadId=pane.threadId;
      let result:Partial<Turn>;
      try {
        const selected=snapshots[i];
        const response=await fetch(`${url}/api/chat`,{method:"POST",signal:controller.signal,
          headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},
          body:JSON.stringify({query:question,model_id:selected.modelId,
            search_index_id:selected.strategy!=="keyword"?selected.indexId:undefined,
            thread_id:threadId,locale,search_strategy:selected.strategy,freshness_filter:selected.freshness,
            filters:{...(selected.language!=="all"?{language:selected.language}:{}),...(selected.folder!=="all"?{source_folder:selected.folder}:{})},include_sources:true})});
        const body=await response.json();
        if (!response.ok) {
          if ([403,404,409,422,503].includes(response.status)) { void reloadModels();void indexes.reload(); }
          throw new Error(body.detail || `HTTP ${response.status}`);
        }
        threadId=body.thread_id;
        result={answer:{role:"assistant",content:body.answer,sources:body.sources || [],model_name:body.metadata?.model_name,
          embedding_model:body.metadata?.embedding_model,search_index_id:body.metadata?.search_index_id},retrieval:body.metadata?.retrieval_strategy};
      } catch(error) {
        if (controller.signal.aborted) return;
        result={error:error instanceof Error?error.message:String(error)};
      }
      if (controller.signal.aborted) return;
      setPanes(previous=>previous.map((current,n)=>n===i?{...current,busy:false,threadId,
        turns:current.turns.map((turn,j)=>j===current.turns.length-1?{...turn,...result,elapsed:Math.round(performance.now()-started)}:turn)}:current));
    };
    if (localPair) {
      await runVariant(panes[0],0);
      await runVariant(panes[1],1);
    } else {
      await Promise.allSettled(panes.map(runVariant));
    }
    running.current=false;
  };
  const selectClass="w-full rounded-lg border border-white/15 bg-slate-900 p-2 text-xs";
  return <div className="flex flex-col h-full min-h-0 p-5 gap-4">
    <div className="flex justify-between gap-4"><div><h2 className="text-xl font-bold">{cs?"Porovnání výsledků":"Compare results"}</h2><p className="text-xs text-zinc-400 mt-2">{cs?"Jedna otázka, dvě samostatné konverzace. Každá strana používá jeden model a jeden index. Měněné nastavení platí pro další otázku; historie zůstává oddělená. Souběžná volání sdílejí kapacitu služby, uvedené časy nejsou výkonový benchmark.":"One question, two independent conversations. Each side uses one model and one index. Changes apply to the next question; histories stay separate. Concurrent calls share service capacity; timings are not a performance benchmark."}</p></div>
      <button type="button" disabled={busy} onClick={()=>setPanes(previous=>previous.map(pane=>({...pane,threadId:undefined,turns:[],settingsOpen:true})))} className="rounded-lg border border-white/20 px-4 py-2 text-xs shrink-0 disabled:opacity-40">{cs?"Nové porovnání":"New comparison"}</button></div>
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 flex-1 min-h-0 overflow-auto">
      {panes.map((pane,i)=><section aria-label={`${cs?"Varianta":"Variant"} ${i===0?"A":"B"}`} key={i} className="rounded-2xl border border-white/10 bg-[#0c1222] flex flex-col min-h-0">
        <div className="p-4 border-b border-white/10 space-y-3"><div className="flex items-start justify-between gap-3"><div><h3 className="font-bold text-indigo-300">{cs?"Varianta":"Variant"} {i===0?"A":"B"} · {models.find(model=>model.id===pane.options.modelId)?.name}</h3>
          <p className="text-xs text-zinc-500 mt-1">{pane.options.strategy === "keyword" ? "keyword" : indexes.catalog?.indexes.find(index=>index.index_id===pane.options.indexId)?.model}</p></div>
          <button type="button" aria-expanded={pane.settingsOpen} className="text-xs rounded-lg border border-white/20 px-3 py-2" onClick={()=>setPanes(previous=>previous.map((current,n)=>n===i?{...current,settingsOpen:!current.settingsOpen}:current))}>{cs?"Nastavení varianty":"Variant settings"}</button></div>
          {!valid(pane) && <p role="alert" className="text-xs text-amber-300">{cs?"V nastavení vyberte dostupný model a úplný index. Jiná volba se nepoužije automaticky.":"Select an available model and complete index in settings. No alternative is selected automatically."}</p>}
          {pane.settingsOpen && <div className="space-y-3">
          <ModelPicker locale={locale} disabled={busy} label={`${cs?"Model":"Model"} ${i===0?"A":"B"}`} catalog={{models,modelId:pane.options.modelId,select:id=>edit(i,{modelId:id}),error:"",loading:false,reload:reloadModels}}/>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <label>{cs?"Strategie":"Strategy"}<select aria-label={`Strategy ${i}`} disabled={busy} className={selectClass} value={pane.options.strategy} onChange={e=>edit(i,{strategy:e.target.value})}>{["hybrid","vector","keyword"].map(s=><option key={s}>{s}</option>)}</select></label>
            <label>{cs?"Aktuálnost":"Freshness"}<select aria-label={`Freshness ${i}`} disabled={busy} className={selectClass} value={pane.options.freshness} onChange={e=>edit(i,{freshness:e.target.value})}>{["all","this_year","latest"].map(s=><option key={s} value={s}>{cs?({all:"Vše",this_year:"Tento rok",latest:"Nejnovější"}[s]):s}</option>)}</select></label>
            <label>{cs?"Jazyk dokumentů":"Document language"}<select aria-label={`Language ${i}`} disabled={busy} className={selectClass} value={pane.options.language} onChange={e=>edit(i,{language:e.target.value})}>{["all","cs","en"].map(s=><option key={s}>{s}</option>)}</select></label>
            <label>{cs?"Zdrojová složka":"Source folder"}<select aria-label={`Folder ${i}`} disabled={busy} className={selectClass} value={pane.options.folder} onChange={e=>edit(i,{folder:e.target.value})}><option value="all">{cs?"Vše":"All"}</option>{folders.map(folder=><option key={folder}>{folder}</option>)}</select></label>
          </div>
          <label className="block text-xs">{cs?"Embeddingový index":"Embedding index"}<select aria-label={`Index ${i}`} disabled={busy || pane.options.strategy==="keyword"} className={selectClass} value={pane.options.indexId} onChange={e=>edit(i,{indexId:e.target.value})}>
            <option value="" disabled>{cs?"Vyberte připravený index":"Select a prepared index"}</option>{indexes.catalog?.indexes.map(index=><option key={index.index_id} disabled={!index.ready} value={index.index_id}>{index.model} · {index.dimensions} dim · {index.index_id.slice(0,8)}{!index.ready?" · incomplete":""}</option>)}</select></label>
          {indexes.error && <p role="alert" className="text-amber-300 text-xs">{indexes.error}</p>}
          </div>}
        </div>
        <div className="p-4 space-y-5 overflow-y-auto flex-1 min-h-72" aria-live="polite">
          {!pane.turns.length && <p className="text-zinc-500 text-sm">{cs?"Nastavte variantu a zadejte společnou otázku dole.":"Configure this variant and enter the shared question below."}</p>}
          {pane.turns.map((turn,j)=><article key={j} className="space-y-3 text-sm"><p className="rounded-lg bg-indigo-500/20 p-3 font-semibold">{turn.question}</p>
            <p className="text-[10px] text-zinc-500 break-all">{turn.options.strategy} · {turn.options.language} · {turn.options.freshness} · {turn.options.folder}{turn.options.strategy!=="keyword"?` · ${turn.options.indexId}`:""}</p>
            {turn.error?<p role="alert" className="text-amber-300">{turn.error}</p>:turn.answer?<>{renderAnswer(turn.answer)}<p className="text-xs text-zinc-400">{turn.answer.model_name || turn.options.modelId} · {turn.answer.embedding_model || turn.retrieval} · {turn.elapsed} ms</p><p className="text-[10px] text-zinc-500 break-all">{turn.answer.search_index_id}</p></>:<p role="status" className="text-indigo-300">{turn.queued?(cs?"Čeká na dokončení varianty A…":"Waiting for variant A…"):(cs?"Zpracovávám…":"Processing…")}</p>}
          </article>)}
        </div>
      </section>)}
    </div>
    <form onSubmit={submit} className="flex items-end gap-3"><label className="flex-1 text-xs">{cs?"Společná otázka":"Shared question"}<textarea aria-label={cs?"Společná otázka":"Shared question"} disabled={busy} value={query} onChange={e=>setQuery(e.target.value)} rows={2} className="w-full rounded-xl border border-indigo-500/50 bg-slate-900 p-3 text-sm mt-1"/></label>
      <button disabled={busy || !query.trim() || !panes.every(valid)} className="rounded-xl bg-indigo-600 px-5 py-3 text-sm disabled:opacity-40">{busy?(cs?"Čekám na výsledky…":"Waiting for results…"):(cs?"Porovnat obě varianty":"Compare both variants")}</button></form>
  </div>;
}
