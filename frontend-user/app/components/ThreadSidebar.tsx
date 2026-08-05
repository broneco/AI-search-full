"use client";

import React, { useState, useMemo } from "react";

export interface ThreadItem {
  thread_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface ThreadSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  threads: ThreadItem[];
  activeThreadId: string | null;
  onSelectThread: (threadId: string) => void;
  onNewThread: () => void;
  onRenameThread: (threadId: string, newTitle: string) => void;
  onDeleteThread: (threadId: string) => void;
  documents?: any[];
  onSelectDocument?: (doc: any) => void;
  user: any | null;
  onLogout: () => void;
  language: "cs" | "en";
}

export const ThreadSidebar: React.FC<ThreadSidebarProps> = ({
  isOpen,
  onToggle,
  threads,
  activeThreadId,
  onSelectThread,
  onNewThread,
  onRenameThread,
  onDeleteThread,
  documents = [],
  onSelectDocument,
  user,
  onLogout,
  language,
}) => {
  const [activeSidebarTab, setActiveSidebarTab] = useState<"threads" | "documents">("threads");
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>("");
  const [docSearchQuery, setDocSearchQuery] = useState<string>("");

  const filteredDocuments = useMemo(() => {
    if (!docSearchQuery.trim()) return documents;
    const q = docSearchQuery.toLowerCase();
    return documents.filter((doc) => {
      const titleMatch = doc.title?.toLowerCase().includes(q);
      const catMatch = doc.document_type?.toLowerCase().includes(q);
      const folderMatch = (doc.metadata_json?.source_folder || doc.metadata_json?.["Zdroj dat"])?.toLowerCase().includes(q);
      return titleMatch || catMatch || folderMatch;
    });
  }, [documents, docSearchQuery]);

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="fixed top-3.5 left-4 z-40 p-2.5 rounded-xl bg-[#0d1322] border border-white/10 text-zinc-300 hover:text-white shadow-xl transition-all cursor-pointer flex items-center gap-2 text-xs font-semibold"
        title="Otevřít postranní panel"
      >
        <span>💬</span>
        <span className="hidden sm:inline">{language === "cs" ? "Menu & Dokumenty" : "Menu & Documents"}</span>
      </button>
    );
  }

  const handleStartRename = (thread: ThreadItem, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingThreadId(thread.thread_id);
    setEditingTitle(thread.title);
  };

  const handleSaveRename = (threadId: string) => {
    if (editingTitle.trim()) {
      onRenameThread(threadId, editingTitle.trim());
    }
    setEditingThreadId(null);
  };

  return (
    <aside className="w-80 bg-[#0a0f1c] border-r border-white/10 flex flex-col h-full shrink-0 z-40 transition-all shadow-2xl">
      {/* Sidebar Header */}
      <div className="p-4 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
        <div className="flex items-center gap-2">
          <span className="text-xl">✨</span>
          <span className="font-extrabold text-sm text-white tracking-tight">AI Search Console</span>
        </div>
        <button
          onClick={onToggle}
          className="text-zinc-400 hover:text-white p-1 text-base transition-colors cursor-pointer"
          title="Skrýt panel"
        >
          ◀
        </button>
      </div>

      {/* Main Tab Switcher: Chat History vs Document Library */}
      <div className="p-2 border-b border-white/10 bg-black/40 flex items-center gap-1">
        <button
          onClick={() => setActiveSidebarTab("threads")}
          className={`flex-1 py-2 px-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
            activeSidebarTab === "threads"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/25"
              : "text-zinc-400 hover:text-white hover:bg-white/5"
          }`}
        >
          <span>💬</span>
          <span>{language === "cs" ? "Konverzace" : "Chats"}</span>
          {threads.length > 0 && (
            <span className="text-[10px] bg-white/20 px-1.5 py-0.2 rounded-full font-mono">
              {threads.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveSidebarTab("documents")}
          className={`flex-1 py-2 px-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
            activeSidebarTab === "documents"
              ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/25"
              : "text-zinc-400 hover:text-white hover:bg-white/5"
          }`}
        >
          <span>📁</span>
          <span>{language === "cs" ? "Dokumenty" : "Docs"}</span>
          {documents.length > 0 && (
            <span className="text-[10px] bg-white/20 px-1.5 py-0.2 rounded-full font-mono">
              {documents.length}
            </span>
          )}
        </button>
      </div>

      {/* TAB 1: CONVERSATIONS / THREADS */}
      {activeSidebarTab === "threads" && (
        <>
          {/* New Chat Button */}
          <div className="p-3 border-b border-white/5">
            <button
              onClick={onNewThread}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-extrabold text-xs transition-all shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2 cursor-pointer border border-indigo-400/30"
            >
              <span className="text-sm">＋</span>
              <span>{language === "cs" ? "Nový chat" : "New Chat"}</span>
            </button>
          </div>

          {/* Threads List */}
          <div className="flex-1 overflow-y-auto p-3 space-y-1">
            <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider px-2 block mb-2">
              {language === "cs" ? "Uložené konverzace:" : "Saved Conversations:"}
            </span>

            {threads.length === 0 ? (
              <div className="text-center py-8 px-4 text-zinc-500 text-xs font-medium">
                {language === "cs" ? "Zatím žádná historie konverzací." : "No conversation history yet."}
              </div>
            ) : (
              threads.map((t) => {
                const isActive = t.thread_id === activeThreadId;
                const isEditing = t.thread_id === editingThreadId;

                return (
                  <div
                    key={t.thread_id}
                    onClick={() => onSelectThread(t.thread_id)}
                    className={`group relative p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-2 ${
                      isActive
                        ? "bg-indigo-600/25 border-indigo-500/50 text-white shadow-sm"
                        : "bg-white/[0.02] hover:bg-white/[0.06] border-white/5 text-zinc-300 hover:text-white"
                    }`}
                  >
                    <div className="flex items-center gap-2 overflow-hidden flex-1">
                      <span className="text-xs">💬</span>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editingTitle}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onBlur={() => handleSaveRename(t.thread_id)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleSaveRename(t.thread_id);
                          }}
                          autoFocus
                          className="bg-black/60 border border-indigo-400 text-white text-xs px-2 py-0.5 rounded focus:outline-none w-full font-medium"
                        />
                      ) : (
                        <span className="text-xs font-medium truncate block max-w-[170px]" title={t.title}>
                          {t.title}
                        </span>
                      )}
                    </div>

                    {/* Actions Icons */}
                    {!isEditing && (
                      <div className="hidden group-hover:flex items-center gap-1 shrink-0">
                        <button
                          onClick={(e) => handleStartRename(t, e)}
                          className="p-1 text-zinc-400 hover:text-indigo-300 text-xs transition-colors cursor-pointer"
                          title="Přejmenovat"
                        >
                          ✏️
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDeleteThread(t.thread_id);
                          }}
                          className="p-1 text-zinc-400 hover:text-red-400 text-xs transition-colors cursor-pointer"
                          title="Smazat"
                        >
                          🗑️
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </>
      )}

      {/* TAB 2: DOCUMENT LIBRARY */}
      {activeSidebarTab === "documents" && (
        <div className="flex-1 flex flex-col overflow-hidden p-3 gap-3">
          {/* Document Search Filter */}
          <div className="relative">
            <input
              type="text"
              value={docSearchQuery}
              onChange={(e) => setDocSearchQuery(e.target.value)}
              placeholder={language === "cs" ? "Hledat v dokumentech..." : "Search documents..."}
              className="w-full bg-black/50 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500 font-medium"
            />
            {docSearchQuery && (
              <button
                onClick={() => setDocSearchQuery("")}
                className="absolute right-2.5 top-2 text-zinc-400 hover:text-white text-xs"
              >
                ✕
              </button>
            )}
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {filteredDocuments.length === 0 ? (
              <div className="text-center py-8 px-4 text-zinc-500 text-xs font-medium">
                {language === "cs" ? "Žádné vyhovující dokumenty." : "No matching documents found."}
              </div>
            ) : (
              filteredDocuments.map((doc) => {
                const folderName = doc.metadata_json?.source_folder || doc.metadata_json?.["Zdroj dat"] || "";
                const isArchived = doc.freshness_status === "archived";

                return (
                  <div
                    key={doc.document_id}
                    onClick={() => onSelectDocument && onSelectDocument(doc)}
                    className="p-3 rounded-xl bg-[#0f1629]/70 hover:bg-indigo-950/40 border border-white/10 hover:border-indigo-500/50 transition-all cursor-pointer group space-y-2"
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-base shrink-0">📄</span>
                      <div className="overflow-hidden flex-1">
                        <h4 className="text-xs font-extrabold text-white group-hover:text-indigo-300 transition-colors line-clamp-2 leading-snug">
                          {doc.title}
                        </h4>
                      </div>
                    </div>

                    {/* Metadata Badges */}
                    <div className="flex flex-wrap items-center gap-1.5 text-[9px] pt-1 border-t border-white/5">
                      <span className="px-1.5 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold uppercase">
                        {doc.document_type || "OBECNÉ"}
                      </span>

                      {folderName && (
                        <span className="px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold truncate max-w-[130px]">
                          {folderName}
                        </span>
                      )}

                      <span className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
                        {doc.chunk_count || 0} pasáží
                      </span>

                      <span className={`px-1.5 py-0.5 rounded font-extrabold ml-auto ${
                        isArchived ? "bg-amber-500/20 text-amber-400 border border-amber-500/30" : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                      }`}>
                        {isArchived ? "ARCHIV" : "PLATNÝ"}
                      </span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Bottom User Profile Section */}
      <div className="p-4 border-t border-white/10 bg-black/40 flex items-center justify-between">
        {user ? (
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-indigo-600 border border-indigo-400 flex items-center justify-center text-xs font-extrabold text-white shrink-0">
              {user.username ? user.username.charAt(0).toUpperCase() : "U"}
            </div>
            <div className="overflow-hidden">
              <span className="text-xs font-bold text-white truncate block max-w-[130px]" title={user.username}>
                {user.username}
              </span>
              <span className="text-[10px] text-indigo-300 font-semibold block">
                {user.role}
              </span>
            </div>
          </div>
        ) : (
          <span className="text-xs text-zinc-400 font-semibold">Demo Uživatel</span>
        )}

        <button
          onClick={onLogout}
          className="p-2 text-zinc-400 hover:text-red-400 hover:bg-white/5 rounded-xl transition-colors cursor-pointer text-xs font-bold flex items-center gap-1"
          title={language === "cs" ? "Odhlásit se" : "Logout"}
        >
          <span>🚪</span>
        </button>
      </div>
    </aside>
  );
};
