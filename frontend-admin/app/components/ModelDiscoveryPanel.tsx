"use client";
import { useRef, useState } from "react";

type Registration = {id: string; model: string; digest: string; user_visible: boolean; revision: number};
type DiscoveredModel = {
  name: string; digest: string; kind: string; capabilities: string[];
  dimensions?: number | null; context_length?: number | null; size_bytes?: number | null;
  parameter_size?: string | null; quantization_level?: string | null;
  configured_chat_ids: string[]; configured_embedding_ids: string[];
  registration?: Registration | null; registration_error?: string | null;
  candidate_id?: string;
};
type Inventory = { scanned_at: string; models: DiscoveredModel[] };

export function ModelDiscoveryPanel({ url, token, locale }: { url: string; token: string; locale: "cs" | "en" }) {
  const [inventory, setInventory] = useState<Inventory | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [search, setSearch] = useState("");
  const pending = useRef(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const cs = locale === "cs";
  const mergeRegistrations = (rows: Registration[]) => {
    setInventory(previous => previous && ({...previous, models: previous.models.map(model => ({...model,
      registration: rows.find(row => model.candidate_id ? row.id === model.candidate_id : row.model === model.name && row.digest === model.digest) || model.registration}))}));
    window.dispatchEvent(new Event("models-changed"));
    window.dispatchEvent(new Event("model-registry-changed"));
    window.dispatchEvent(new Event("indexes-changed"));
  };
  const register = async (models: DiscoveredModel[]) => {
    if (!models.length || pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try {
      const res = await fetch(`${url}/api/models/registry`, {method:"POST",
        headers:{Authorization:`Bearer ${token}`, "Content-Type":"application/json"},
        body:JSON.stringify({models:models.map(model => ({name:model.name,digest:model.digest}))})});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Registration failed");
      mergeRegistrations(body.models);
    } catch(e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { pending.current = false; setBusy(false); }
  };
  const publish = async (row: Registration, visible: boolean) => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try {
      const res = await fetch(`${url}/api/models/registry/${row.id}`, {method:"PUT",
        headers:{Authorization:`Bearer ${token}`, "Content-Type":"application/json"},
        body:JSON.stringify({revision:row.revision,user_visible:visible})});
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Publication failed");
      mergeRegistrations([body]);
    } catch(e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { pending.current = false; setBusy(false); }
  };
  const load = async () => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try {
      const response = await fetch(`${url}/api/models/discovery`, { headers: { Authorization: `Bearer ${token}` } });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Discovery failed");
      setInventory(body);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { pending.current = false; setBusy(false); }
  };
  const kinds: Record<string, string> = cs
    ? { chat_candidate: "Kandidát pro chat", embedding: "Embedding", reranker: "Reranker", unsupported: "Nepodporovaný účel", unverified: "Metadata neověřena" }
    : { chat_candidate: "Chat candidate", embedding: "Embedding", reranker: "Reranker", unsupported: "Unsupported purpose", unverified: "Metadata unverified" };
  return <>
    <button type="button" onClick={() => { dialog.current?.showModal(); void load(); }} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white">{cs ? "Obnovit z API" : "Refresh from API"}</button>
    <dialog ref={dialog} aria-label={cs ? "Modely dostupné na JHU API" : "Models available on JHU API"}
      className="fixed inset-0 m-auto w-[min(1100px,95vw)] max-h-[90vh] overflow-auto rounded-2xl border border-white/20 bg-slate-950 text-zinc-300 p-6 text-xs backdrop:bg-black/75">
    <div className="flex justify-between items-center mb-4 gap-4"><h3 className="text-lg font-bold text-white">{cs ? "Modely dostupné na JHU API" : "Models available on JHU API"}</h3>
      <button type="button" onClick={() => dialog.current?.close()} className="rounded-lg border border-white/20 px-4 py-2">{cs ? "Zavřít" : "Close"}</button></div>
    <p className="my-2">{cs
      ? "Načtení z API zobrazí inventář. Přidejte modely pro testování v administraci; checkboxem je povolíte v uživatelské aplikaci. Embeddingový model vyžaduje následnou přípravu indexu. Rerankery se nenabízejí pro chat ani embeddingy. Modely se na server nestahují."
      : "Scan the inventory, add models for admin testing and publish them to users with the checkbox. Embedding models also need a prepared index. Rerankers are excluded. No model downloads are performed."}</p>
    <button type="button" disabled={busy} onClick={() => void load()} className="px-3 py-1 rounded bg-indigo-600 disabled:opacity-50">
      {busy ? (cs ? "Načítám…" : "Loading…") : (cs ? "Obnovit z API" : "Refresh from API")}
    </button>
    {error && <p role="alert" className="my-2 text-amber-300">{error}</p>}
    {inventory && <>
      <div className="my-3 flex flex-wrap gap-3">
        <input aria-label={cs ? "Hledat model" : "Find model"} placeholder={cs ? "Hledat podle názvu modelu…" : "Find a model…"} value={search}
          onChange={e => setSearch(e.target.value)} className="bg-slate-900 border border-white/20 rounded-lg px-3 py-2" />
        <button type="button" disabled={busy || !inventory.models.some(m => !m.registration && m.registration_error === null)}
          onClick={() => void register(inventory.models.filter(m => !m.registration && m.registration_error === null))}
          className="px-3 py-2 rounded-lg bg-indigo-600 disabled:opacity-50">{cs ? "Přidat všechny kompatibilní modely pro testování" : "Add all compatible models for testing"}</button>
      </div>
      <p className="my-2">{cs ? "Poslední načtení" : "Last scan"}: {inventory.scanned_at} · {inventory.models.length} {cs ? "modelů" : "models"}</p>
      <div className="overflow-auto max-h-96"><table className="w-full text-left">
        <thead><tr><th className="p-2">Model</th><th className="p-2">{cs ? "Účel / parametry" : "Purpose / parameters"}</th><th className="p-2">{cs ? "Konfigurace aplikace" : "App configuration"}</th></tr></thead>
        <tbody>{inventory.models.filter(model => model.name.toLowerCase().includes(search.toLowerCase())).map(model => <tr key={model.name} className="border-t border-white/10">
          <td className="p-2"><strong>{model.name}</strong><div className="text-zinc-500">{model.digest.slice(0, 12)}</div></td>
          <td className="p-2">{kinds[model.kind] || model.kind}<div className="text-zinc-400">
            {[model.dimensions && `${model.dimensions} dim`, model.parameter_size, model.quantization_level,
              model.context_length && `${cs ? "kontext" : "context"}: ${model.context_length.toLocaleString()}`,
              model.size_bytes != null && `${(model.size_bytes / 1073741824).toFixed(2)} GiB`].filter(Boolean).join(" · ")}
          </div></td>
          <td className="p-2 space-y-2">
            {model.registration ? <>
              <p className="text-emerald-300">{cs ? "Přidán pro testování" : "Available for testing"}</p>
              <label className="flex gap-2 items-center"><input type="checkbox" disabled={busy} checked={model.registration.user_visible}
                onChange={e => void publish(model.registration!, e.target.checked)} />{cs ? "Zobrazit v uživatelské aplikaci" : "Show in user app"}</label>
            </> : model.registration_error === null ? <button type="button" disabled={busy} onClick={() => void register([model])}
              className="underline text-indigo-300">{cs ? "Přidat pro testování" : "Add for testing"}</button> : <p className="text-zinc-400">{model.registration_error}</p>}
            <p className="text-zinc-500">{[...model.configured_chat_ids, ...model.configured_embedding_ids].join(", ")}</p>
          </td>
        </tr>)}</tbody>
      </table></div>
      {!inventory.models.length && <p>{cs ? "Služba nevrátila žádné modely." : "The service returned no models."}</p>}
    </>}
    </dialog>
  </>;
}
