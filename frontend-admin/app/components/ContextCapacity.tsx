"use client";
import {useEffect,useRef,useState} from "react";
import {requestJson} from "../lib/apiRequest";
import {ContextSample,estimateContextCapacity} from "../lib/contextCapacity";

export function ContextCapacity({url,token,indexId,indexRevision,indexName,modelId,modelRevision,resultCount,locale}:{
  url:string;token:string|null;indexId:string;indexRevision?:string;indexName?:string;modelId:string;modelRevision:string;resultCount:number;locale:"cs"|"en";
}) {
  const cs=locale==="cs";
  const identity=JSON.stringify([url,token,indexId,indexRevision,modelId,modelRevision]);
  const identityRef=useRef(identity);identityRef.current=identity;
  const [state,setState]=useState<{identity:string;data:ContextSample|null;error:string;loading:boolean}>({identity:"",data:null,error:"",loading:false});
  const [refresh,setRefresh]=useState(0);
  useEffect(()=>{
    const owner=identity;const abort=new AbortController();let stopped=false;
    setState({identity:owner,data:null,error:"",loading:Boolean(token&&indexId&&modelId)});
    if(!token||!indexId||!modelId)return;
    void requestJson<ContextSample>(`${url}/api/search-indexes/${encodeURIComponent(indexId)}/context-sample?model_id=${encodeURIComponent(modelId)}`,{
      signal:abort.signal,headers:{Authorization:`Bearer ${token}`}
    }).then(data=>{if(!stopped&&identityRef.current===owner)setState({identity:owner,data,error:"",loading:false});})
      .catch(e=>{if(!stopped&&identityRef.current===owner)setState({identity:owner,data:null,error:e instanceof Error?e.message:String(e),loading:false});});
    return()=>{stopped=true;abort.abort();};
  },[identity,refresh]);
  const current=state.identity===identity?state:null;
  const data=current?.data;
  const estimate=data?estimateContextCapacity(data,resultCount):null;
  const format=(n:number)=>n.toLocaleString(cs?"cs-CZ":"en-GB",{maximumFractionDigits:1});
  const basis=estimate?.basis==="context"?(cs?"vstupního tokenového rozpočtu modelu":"of the model input token budget")
    :estimate?.basis==="characters"?(cs?"vstupního limitu aplikace (přepočet ze znaků)":"of the application input limit (converted from characters)")
    :(cs?"ochranného vstupního limitu aplikace":"of the application input safety limit");
  return <div className="rounded-xl border border-indigo-400/20 bg-indigo-500/5 p-4 space-y-3 text-xs" aria-live="polite">
    <div className="flex justify-between gap-3"><h4 className="font-semibold text-white">{cs?"Odhad využití vstupní kapacity":"Estimated input capacity usage"}</h4><button type="button" disabled={current?.loading||!indexId||!modelId} onClick={()=>setRefresh(n=>n+1)} className="text-indigo-300 underline">{cs?"Obnovit vzorek":"Refresh sample"}</button></div>
    <p className="text-zinc-400">{indexName||indexId||"—"} · {data?.model.name||modelId||"—"}</p>
    {!token||!indexId||!modelId?<p>{cs?"Vyberte index a model pro odpovědi v sekci Modely a vyhledávání.":"Choose an index and answer model in Models and search."}</p>
      :current?.loading||!current?<p>{cs?"Počítám délku vzorku z vybraného indexu…":"Counting a sample from the selected index…"}</p>
      :current.error?<p role="alert" className="text-amber-200">{current.error}</p>
      :data&&(!data.sample||data.sample.tokens<=0)?<p>{cs?"Ve vybraném indexu není dostupný platný chunk pro odhad.":"No valid accessible chunk is available in this index."}</p>
      :estimate?<>
        <p><strong className="text-white">{format(estimate.count)} × {format(estimate.sampleTokens)} = {cs?"přibližně":"approximately"} {format(estimate.tokens)} {cs?"tokenů kontextu":"context tokens"}</strong></p>
        <p className={estimate.exceeds?"text-amber-200":"text-indigo-200"}>{estimate.percentage!==null?`${format(estimate.percentage)} %`:(cs?"Nulový vstupní rozpočet":"No input budget")} {basis} · {cs?"rozpočet":"budget"} {estimate.approximate?"≈ ":""}{format(estimate.budgetTokens)} {cs?"tokenů":"tokens"}</p>
        <progress aria-label={cs?"Odhad využití vstupu":"Estimated input usage"} value={Math.min(100,estimate.percentage??100)} max={100} className={`w-full ${estimate.exceeds?"accent-amber-500":"accent-indigo-500"}`}/>
        {estimate.applicationPercentage!==null&&<p className={estimate.applicationExceeded?"text-amber-200":"text-zinc-400"}>{cs?"Využití ochranného vstupního limitu aplikace":"Application input safety limit usage"}: {format(estimate.applicationPercentage)} %</p>}
        {estimate.exceeds&&<p className="text-amber-200">{cs?"Odhad překračuje vstupní limit modelu nebo nastavený ochranný limit aplikace. Snižte počet výsledků nebo velikost chunků.":"The estimate exceeds the model input limit or the application safety limit. Reduce the result count or chunk size."}</p>}
        {data?.model.context_tokens&&<p className="text-zinc-400">{cs?"Kontext modelu":"Model context"}: {format(data.model.context_tokens)} · {cs?"rezerva na odpověď":"answer reserve"}: {format(data.model.max_output_tokens)}</p>}
      </>:null}
    <p className="text-zinc-500">{cs?"Orientační odhad z jednoho uloženého chunku, nikoli měření celého požadavku. Nezahrnuje systémový prompt, otázku, historii ani sousední chunky. Použitá referenční tokenizace se u jiných modelů může lišit.":"An estimate from one stored chunk, not a measurement of the whole request. Excludes system prompt, question, history and neighboring chunks. Reference tokenization may differ from the selected model."}</p>
  </div>;
}
