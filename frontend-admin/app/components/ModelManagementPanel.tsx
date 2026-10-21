"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ModelDiscoveryPanel } from "./ModelDiscoveryPanel";
import { parameterText, ModelOption } from "./ModelPicker";

type RuntimeSettings = {revision:number;max_output_tokens:number|null;default_max_output_tokens:number;
  effective_max_output_tokens:number;effective_max_input_chars:number;minimum:number;maximum:number;context_tokens:number|null};
type Row = ModelOption & {kind: string; purposes: string[]; description_revision: number; runtime?:RuntimeSettings;
  access: {allowed_groups: string[] | null; revision: number};
  registration?: {user_visible: boolean; revision: number} | null};

export function ModelManagementPanel({url, token, locale}: {url: string; token: string; locale: "cs" | "en"}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [groups, setGroups] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const generation = useRef(0);
  const drafts = useRef(new Set<string>());
  const cs = locale === "cs";
  const load = useCallback(async () => {
    const ticket = ++generation.current;
    try {
      const res = await fetch(`${url}/api/models/management`, {headers:{Authorization:`Bearer ${token}`}});
      const body = await res.json();
      if (ticket !== generation.current) return;
      if (!res.ok) throw new Error(body.detail || "Model overview unavailable");
      setRows(previous => body.models.map((row: Row) => {
        const old = previous.find(item => item.id === row.id);
        return {...row, ...(old && drafts.current.has(`${row.id}:access`) ? {access:old.access} : {}),
          ...(old && drafts.current.has(`${row.id}:description`) ? {description:old.description,description_revision:old.description_revision} : {}),
          ...(old && drafts.current.has(`${row.id}:runtime`) ? {runtime:old.runtime} : {})};
      })); setGroups(body.groups); setError("");
    } catch(e) { if (ticket === generation.current) setError(e instanceof Error ? e.message : String(e)); }
  }, [url, token]);
  useEffect(() => { void load(); return () => { generation.current++; }; }, [load]);
  useEffect(() => {
    const refresh = () => { void load(); };
    window.addEventListener("model-registry-changed", refresh);
    return () => window.removeEventListener("model-registry-changed", refresh);
  }, [load]);
  const edit = (id: string, patch: Partial<Row>, draft = true) => {
    if (draft && patch.access) drafts.current.add(`${id}:access`);
    if (draft && patch.description) drafts.current.add(`${id}:description`);
    if (draft && patch.runtime) drafts.current.add(`${id}:runtime`);
    setRows(previous => previous.map(row => row.id === id ? {...row,...patch} : row));
  };
  const save = async (row: Row, kind: "access" | "description" | "publication" | "runtime", visible?: boolean, resetRuntime = false) => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError(""); setMessage("");
    const path = kind === "description" ? "descriptions" : kind === "publication" ? "registry" : kind;
    const request = kind === "description" ? {revision:row.description_revision,description:row.description}
      : kind === "publication" ? {revision:row.registration!.revision,user_visible:visible}
      : kind === "runtime" ? {revision:row.runtime!.revision,max_output_tokens:resetRuntime?null:row.runtime!.max_output_tokens}
      : {revision:row.access.revision,allowed_groups:row.access.allowed_groups};
    try {
      const res = await fetch(`${url}/api/models/${path}/${encodeURIComponent(row.id)}`, {method:"PUT",
        headers:{Authorization:`Bearer ${token}`,"Content-Type":"application/json"},body:JSON.stringify(request)});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Save failed");
      drafts.current.delete(`${row.id}:${kind}`);
      if (kind === "description") edit(row.id,{description_revision:body.revision, description:body.description},false);
      else if (kind === "access") edit(row.id,{access:{revision:body.revision,allowed_groups:body.allowed_groups}},false);
      else if (kind === "runtime") edit(row.id,{runtime:body.runtime,parameters:body.parameters},false);
      else edit(row.id,{registration:body},false);
      setMessage(`${row.name}: ${cs ? "uloženo" : "saved"}.`);
      window.dispatchEvent(new Event("models-changed"));
      window.dispatchEvent(new Event("indexes-changed"));
    } catch(e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { pending.current = false; setBusy(false); }
  };
  const purposeNames: Record<string,string> = cs ? {chat:"Odpovědi",summary:"Shrnutí",classification:"Klasifikace",embedding:"Embedding"} : {chat:"Answers",summary:"Summary",classification:"Classification",embedding:"Embedding"};
  return <div className="space-y-4 text-xs text-zinc-300">
    <div className="flex flex-wrap gap-3 items-center"><ModelDiscoveryPanel url={url} token={token} locale={locale}/>
      <input aria-label={cs ? "Hledat v přehledu modelů" : "Search model overview"} placeholder={cs ? "Hledat název nebo popis…" : "Search name or description…"} value={search} onChange={e => setSearch(e.target.value)} className="rounded-lg border border-white/20 p-2 bg-black/30 flex-1"/>
      <button type="button" disabled={busy} onClick={() => { if (drafts.current.size && !window.confirm(cs ? "Zahodit neuložené popisy, limity a oprávnění?" : "Discard unsaved descriptions, limits and access rules?")) return; drafts.current.clear(); void load(); }} className="underline">{cs ? "Znovu načíst přehled" : "Reload overview"}</button></div>
    <p className="text-zinc-400">{cs ? "API nabízí nové modely v samostatném okně. Tento přehled obsahuje konfiguraci aplikace. Publikace a členství v alespoň jedné povolené skupině řídí přístup uživatelů; prázdný výběr skupin zakazuje model všem. Popis nemění model ani embeddingový prostor." : "Discover new API models in the dialog. This overview shows app configuration. Publication and membership in any allowed group control user access; no groups denies everyone. Editing a description does not change the model or embedding space."}</p>
    {error && <p role="alert" className="text-amber-300">{error}</p>}
    {message && <p role="status" className="text-emerald-300">{message}</p>}
    <div className="overflow-x-auto"><table className="w-full min-w-[1000px] text-left align-top">
      <thead><tr>{["Model",cs?"Účel / parametry":"Purpose / parameters",cs?"Konfigurace aplikace":"App configuration",cs?"Oprávnění":"Access",cs?"Popis modelu":"Model description"].map(label => <th key={label} className="p-3">{label}</th>)}</tr></thead>
      <tbody>{rows.filter(row => `${row.name} ${row.description[locale]}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(row => <tr key={row.id} className="border-t border-white/10">
        <td className="p-3 align-top max-w-52 break-words"><strong className="text-white">{row.name}</strong><p>{row.location === "local" ? "JHU" : "Cloud"}</p><code className="block text-[10px] text-zinc-500 mt-2 break-all">{row.id}</code></td>
        <td className="p-3 align-top"><p>{row.purposes.map(p => purposeNames[p] || p).join(" · ")}</p><p className="text-zinc-400 mt-2">{parameterText(row.parameters)}</p></td>
        <td className="p-3 align-top space-y-2">{row.registration ? <label className="flex gap-2"><input type="checkbox" disabled={busy} checked={row.registration.user_visible}
          onChange={e => void save(row,"publication",e.target.checked)}/>{cs?"Zobrazit uživatelům":"Show to users"}</label> : <p>{cs?"Součást tenantové konfigurace":"Tenant configuration"}</p>}
          {row.kind === "embedding" ? <p className="text-zinc-400">{cs?"Pro dotazy je nutný připravený index.":"Queries require a prepared index."}</p> : <p className={row.available?"text-emerald-400":"text-amber-300"}>{row.available?(cs?"Připojení nastavené":"Connection configured"):row.unavailable_reason}</p>}
          {row.runtime && <div className="border-t border-white/10 pt-3 space-y-2 min-w-48">
            <label className="block">{cs?"Maximální délka výstupu (tokeny)":"Maximum output length (tokens)"}
              <input type="number" aria-label={`${row.name} — ${cs?"limit výstupu":"output limit"}`} min={row.runtime.minimum} max={row.runtime.maximum} step={1} disabled={busy}
                value={Number.isFinite(row.runtime.max_output_tokens ?? row.runtime.default_max_output_tokens) ? (row.runtime.max_output_tokens ?? row.runtime.default_max_output_tokens) : ""}
                onChange={e => edit(row.id,{runtime:{...row.runtime!,max_output_tokens:e.target.valueAsNumber}})}
                className="block w-full mt-1 rounded-lg border border-white/20 bg-black/30 px-3 py-2"/>
            </label>
            <p className="text-zinc-500">{row.runtime.minimum}–{row.runtime.maximum} · {cs?"Výchozí":"Default"}: {row.runtime.default_max_output_tokens}</p>
            {row.location === "local" && <p className="text-amber-200/80">{cs?"Vyšší limit ponechá méně prostoru pro vstup. Aplikace podklady neořízne.":"A higher limit leaves less room for input. The app does not truncate context."}</p>}
            <button type="button" disabled={busy || (row.runtime.max_output_tokens !== null && (!Number.isInteger(row.runtime.max_output_tokens) || row.runtime.max_output_tokens < row.runtime.minimum || row.runtime.max_output_tokens > row.runtime.maximum))}
              onClick={() => void save(row,"runtime")} className="rounded bg-indigo-600 px-3 py-2 disabled:opacity-40">{cs?"Uložit limit":"Save limit"}</button>
            <button type="button" disabled={busy || row.runtime.max_output_tokens === null} onClick={() => void save(row,"runtime",undefined,true)} className="block underline disabled:opacity-40">{cs?"Použít výchozí":"Use default"}</button>
            <p className="text-zinc-500">{cs?"Platí pro nové operace chatu, shrnutí a klasifikace tohoto modelu.":"Applies to new chat, summary and classification operations with this model."}</p>
          </div>}
        </td>
        <td className="p-3 align-top space-y-2"><label className="block"><input type="checkbox" disabled={busy} checked={row.access.allowed_groups === null} onChange={e => edit(row.id,{access:{...row.access,allowed_groups:e.target.checked?null:[]}})}/> {cs?"Všichni":"Everyone"}</label>
          {groups.map(group => <label key={group} className="block"><input type="checkbox" disabled={busy || row.access.allowed_groups === null} checked={row.access.allowed_groups?.includes(group) ?? false}
            onChange={e => edit(row.id,{access:{...row.access,allowed_groups:e.target.checked?[...(row.access.allowed_groups || []),group]:(row.access.allowed_groups || []).filter(g => g !== group)}})}/> {group}</label>)}
          <button type="button" disabled={busy} onClick={() => void save(row,"access")} className="rounded bg-indigo-600 px-3 py-2">{cs?"Uložit oprávnění":"Save access"}</button></td>
        <td className="p-3 align-top min-w-64 space-y-2">{(["cs","en"] as const).map(language => <label className="block" key={language}>{language.toUpperCase()}<textarea aria-label={`${row.name} — ${language} description`} maxLength={4000} rows={4} disabled={busy} value={row.description[language]} onChange={e => edit(row.id,{description:{...row.description,[language]:e.target.value}})} className="w-full mt-1 rounded border border-white/15 bg-black/30 p-2"/></label>)}
          <button type="button" disabled={busy} onClick={() => void save(row,"description")} className="rounded bg-indigo-600 px-3 py-2">{cs?"Uložit popis":"Save description"}</button></td>
      </tr>)}</tbody>
    </table></div>
  </div>;
}
