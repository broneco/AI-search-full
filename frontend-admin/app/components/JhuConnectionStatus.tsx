"use client";
import { useEffect, useRef, useState } from "react";
import { requestJson } from "../lib/apiRequest";

type Status = {mode:string;state:string;code:string|null;can_reconnect?:boolean;status_age_seconds?:number};

export function JhuConnectionStatus({url,token,tenant,manager,locale}: {url:string;token:string|null;tenant?:string;manager:boolean;locale:"cs"|"en"}) {
  const [status,setStatus]=useState<Status|null>(null);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [refresh,setRefresh]=useState(0);
  const owner=`${url}:${tenant}:${token}:${manager}`;
  const identity=useRef(owner); identity.current=owner;
  const cs=locale==="cs";
  useEffect(() => {
    setStatus(null);setError("");setBusy(false);
    if (!token || !/^(ju|jhu)(-|$)/i.test(tenant||"")) return;
    let stopped=false;
    let timer:ReturnType<typeof setTimeout>;
    const abort=new AbortController();
    const check=async()=>{
      let delay=15000;
      try {
        const body=await requestJson(`${url}/api/models/connection${manager?"":"/availability"}`, {signal:abort.signal,headers:{Authorization:`Bearer ${token}`}});
        if (stopped || owner!==identity.current) return;
        setStatus(body);setError("");
        if (body.state==="connecting") delay=2500;
      } catch(e) { if (!stopped && owner===identity.current) setError(e instanceof Error?e.message:String(e)); }
      if (!stopped) timer=setTimeout(check,delay);
    };
    void check();
    return ()=>{stopped=true;clearTimeout(timer);abort.abort();};
  },[url,token,tenant,manager,refresh,owner]);
  const reconnect=async()=>{
    if (!token || busy) return;
    setBusy(true);setError("");
    try {
      const body=await requestJson(`${url}/api/models/connection/reconnect`, {method:"POST",headers:{Authorization:`Bearer ${token}`}});
      if (owner!==identity.current) return;
      setStatus(body);setRefresh(value=>value+1);
      window.dispatchEvent(new Event("models-changed"));
    } catch(e) {if (owner===identity.current) setError(e instanceof Error?e.message:String(e));}
    finally {if (owner===identity.current) setBusy(false);}
  };
  if (!token || !/^(ju|jhu)(-|$)/i.test(tenant||"") || status?.mode==="direct") return null;
  const ready=status?.state==="ready";
  return <div className={`rounded-lg border px-3 py-2 text-xs ${ready?"border-emerald-500/30 text-emerald-300":"border-amber-500/30 text-amber-200"}`}>
    <span role="status">JHU: {error?(cs?"stav nedostupný":"status unavailable"):ready?(cs?"připojeno":"connected"):status?.state==="connecting"?(cs?"připojování…":"connecting…"):status?(cs?"modelová služba není dostupná":"model service unavailable"):(cs?"ověřuji…":"checking…")}</span>
    {!ready && status && <p className="mt-1">{cs?"Backend může být online, i když JHU modely neodpovídají. Dotaz nebyl automaticky přepnut na jiný model.":"The API can be online while JHU models are unavailable. Requests are not switched to another model automatically."}</p>}
    {manager && <div className="flex gap-3 mt-1"><button type="button" className="underline" disabled={busy} onClick={()=>setRefresh(value=>value+1)}>{cs?"Obnovit stav":"Refresh status"}</button>
      {status?.can_reconnect && <button type="button" className="underline" disabled={busy} onClick={()=>void reconnect()}>{busy?(cs?"Obnovuji…":"Reconnecting…"):(cs?"Znovupřipojit JHU":"Reconnect JHU")}</button>}</div>}
    {error && <p role="alert" className="mt-1">{error}</p>}
  </div>;
}
