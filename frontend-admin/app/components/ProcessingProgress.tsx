"use client";
import { useEffect, useId, useRef, useState } from "react";

export type ProcessingFile = { id: string; name: string; state: string; valid?: number; total?: number };
export function ProcessingProgress({ open, close, title, phase, state, files, value, total, error, locale, updatedAt, children }: {
  open: boolean; close: () => void; title: string; phase: string; state: string; files: ProcessingFile[];
  value: number; total: number; error?: string | null; locale: "cs" | "en"; updatedAt?: string; children?: React.ReactNode;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [query, setQuery] = useState("");
  const cs = locale === "cs";
  const titleId = useId();
  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal();
    if (!open && dialog.current?.open) dialog.current?.close();
  }, [open]);
  const labels: Record<string,string> = {pending:cs?"Čeká":"Pending", running:cs?"Zpracovává se":"Processing",
    analyzing:cs?"Analýza metadat":"Analyzing metadata", analyzed:cs?"Metadata připravena":"Metadata ready",
    extracting:cs?"Načítání textu":"Extracting text", splitting:cs?"Rozdělování textu":"Splitting text",
    embedding:cs?"Výpočet embeddingů":"Computing embeddings", saving:cs?"Ukládání":"Saving",
    completed:cs?"Hotovo":"Completed", failed:cs?"Chyba":"Failed", empty:cs?"Bez chunků":"No chunks"};
  const completed = files.filter(f => f.state === "completed").length;
  return <dialog ref={dialog} onCancel={close} onClose={close}
    aria-labelledby={titleId} className="m-auto w-[min(900px,94vw)] max-h-[88vh] rounded-2xl border border-indigo-400/30 bg-[#0c1222] text-zinc-200 p-0 shadow-2xl backdrop:bg-black/75">
    <div className="p-6 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div><h2 id={titleId} className="text-xl font-bold text-white">{title}</h2>
          <p role="status" className="mt-2 text-indigo-300">{phase}</p></div>
        <button type="button" autoFocus onClick={close} className="rounded-lg border border-white/20 px-3 py-2">{cs?"Zavřít":"Close"}</button>
      </div>
      <progress aria-label={title} className="w-full h-3 accent-indigo-500" value={value} max={total || 1}/>
      <div className="flex flex-wrap justify-between gap-2 text-sm">
        <span>{value} / {total || "—"} · {state}</span><span>{completed} / {files.length} {cs?"souborů hotovo":"files complete"}</span>
      </div>
      {updatedAt && <p className="text-xs text-zinc-400">{cs?"Poslední změna úlohy":"Last job update"}: {new Date(updatedAt).toLocaleTimeString(cs?"cs-CZ":"en-GB")}</p>}
      {error && <p role="alert" className="rounded-lg bg-amber-900/20 p-3 text-amber-200">{error}</p>}
      <label className="block text-xs text-zinc-400">{cs?"Najít soubor":"Find a file"}
        <input value={query} onChange={e=>setQuery(e.target.value)} className="block w-full mt-1 rounded-lg bg-black/30 border border-white/20 p-2 text-sm text-white"/>
      </label>
      <div className="max-h-[38vh] overflow-auto rounded-lg border border-white/10">
        <table className="w-full text-sm text-left"><thead className="sticky top-0 bg-slate-900"><tr>
          <th className="p-3">{cs?"Soubor":"File"}</th><th className="p-3">{cs?"Stav":"Status"}</th><th className="p-3">{cs?"Chunky":"Chunks"}</th>
        </tr></thead><tbody>{files.filter(f=>f.name.toLocaleLowerCase().includes(query.toLocaleLowerCase())).map(f=><tr key={f.id} className={`border-t border-white/5 ${["running","embedding","saving","analyzing","splitting","extracting"].includes(f.state)?"bg-indigo-500/10":""}`}>
          <td className="p-3 break-words max-w-sm">{f.name}</td><td className={`p-3 ${f.state === "failed"?"text-amber-300":f.state === "completed"?"text-emerald-300":"text-zinc-300"}`}>{labels[f.state] || f.state}</td>
          <td className="p-3 whitespace-nowrap">{f.total === undefined?"—":`${f.valid || 0} / ${f.total}`}</td>
        </tr>)}</tbody></table>
        {!files.length && <p className="p-4 text-zinc-400">{cs?"Připravuji přehled souborů…":"Preparing file overview…"}</p>}
      </div>
      <div className="flex flex-wrap gap-3 items-center">{children}<p className="text-xs text-zinc-400">{cs?"Zavření okna nezastaví zpracování.":"Closing this window does not stop processing."}</p></div>
    </div>
  </dialog>;
}
