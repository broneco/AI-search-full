"use client";

import React, { useState, useEffect, useRef } from "react";
import { TRANSLATIONS } from "./translations";
import { PdfViewerModal } from "./components/PdfViewerModal";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

interface CitationSource {
  document_id: string;
  chunk_id: string;
  title: string;
  source_type?: string;
  source_uri?: string;
  content: string;
  score?: number;
  page_number?: number;
  section_title?: string;
  freshness_status?: "current" | "outdated" | "unknown";
  allowed_groups?: string[];
}

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: CitationSource[];
}

export default function UserSearchPage() {
  const [appLanguage, setAppLanguage] = useState<"cs" | "en">("cs");
  const [userRole, setUserRole] = useState<string>("User");
  const [apiOnline, setApiOnline] = useState<boolean>(true);
  const [query, setQuery] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [activeSource, setActiveSource] = useState<CitationSource | null>(null);
  const [workspaceOpen, setWorkspaceOpen] = useState<boolean>(false);

  // PDF Viewer Modal State
  const [pdfModalOpen, setPdfModalOpen] = useState<boolean>(false);
  const [selectedPdfDocId, setSelectedPdfDocId] = useState<string | null>(null);
  const [selectedPdfTitle, setSelectedPdfTitle] = useState<string>("");
  const [selectedPdfPage, setSelectedPdfPage] = useState<number>(1);
  const [selectedPdfHighlightId, setSelectedPdfHighlightId] = useState<string | undefined>(undefined);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Periodic API Health check
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/health`, { method: "GET" });
        setApiOnline(res.ok);
      } catch {
        setApiOnline(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // Initialize greeting message
  useEffect(() => {
    if (messages.length === 0) {
      setMessages([
        {
          role: "assistant",
          content: TRANSLATIONS[appLanguage].initialGreeting,
        },
      ]);
    }
  }, [appLanguage]);

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Get Auth headers based on active role
  const getHeaders = () => {
    const roleGroupsMap: Record<string, string[]> = {
      User: ["User"],
      Management: ["User", "Management"],
      Admin: ["User", "Management", "Admin"],
    };

    const userGroups = roleGroupsMap[userRole] || ["User"];
    return {
      "Content-Type": "application/json",
      "X-User-Role": userRole,
      "X-User-Groups": userGroups.join(","),
    };
  };

  // Submit Query to Backend API
  const handleSubmit = async (userQuery: string) => {
    if (!userQuery.trim() || loading) return;

    const trimmedQuery = userQuery.trim();
    setQuery("");

    // Add user message
    const newMessages: Message[] = [
      ...messages,
      { role: "user", content: trimmedQuery },
    ];
    setMessages(newMessages);
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ query: trimmedQuery }),
      });

      if (res.ok) {
        const data = await res.json();
        const assistantMessage: Message = {
          role: "assistant",
          content: data.answer || "Odpověď nebyla nalezena.",
          sources: data.sources || [],
        };
        setMessages([...newMessages, assistantMessage]);

        // Auto-select first citation source if available
        if (data.sources && data.sources.length > 0) {
          setActiveSource(data.sources[0]);
        }
      } else {
        const errData = await res.json().catch(() => ({}));
        setMessages([
          ...newMessages,
          {
            role: "assistant",
            content: `⚠️ Chyba při zpracování dotazu: ${errData.detail || "Neznámá chyba serveru."}`,
          },
        ]);
      }
    } catch (err) {
      console.error(err);
      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content: "⚠️ Chyba přenosu: Nepodařilo se spojit s backend serverem.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // Open PDF Viewer Modal for a specific citation
  const openPdfViewer = (source: CitationSource) => {
    setSelectedPdfDocId(source.document_id);
    setSelectedPdfTitle(source.title);
    setSelectedPdfPage(source.page_number || 1);
    setSelectedPdfHighlightId(source.chunk_id);
    setPdfModalOpen(true);
  };

  // Render assistant response with interactive inline citations [1], [2]
  const renderMessageContent = (msg: Message) => {
    if (msg.role === "user") {
      return <p className="text-sm text-zinc-100 leading-relaxed font-medium">{msg.content}</p>;
    }

    let parsedContent = msg.content;

    if (msg.sources && msg.sources.length > 0) {
      const parts = parsedContent.split(/(\[\d+\])/g);
      return (
        <div className="space-y-3">
          <div className="text-sm text-zinc-200 leading-relaxed space-y-2">
            {parts.map((part, idx) => {
              const match = part.match(/\[(\d+)\]/);
              if (match) {
                const citeIndex = parseInt(match[1]) - 1;
                const source = msg.sources && msg.sources[citeIndex];

                if (source) {
                  return (
                    <button
                      key={idx}
                      onClick={() => {
                        setActiveSource(source);
                        setWorkspaceOpen(true);
                      }}
                      className="inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-md bg-indigo-500/20 hover:bg-indigo-500/35 text-indigo-300 hover:text-white border border-indigo-500/40 text-xs font-bold transition-all transform hover:scale-105 cursor-pointer shadow-sm"
                      title={`${source.title} (${TRANSLATIONS[appLanguage].pageLabel} ${source.page_number || "N/A"})`}
                    >
                      <span>📄</span>
                      <span>[{citeIndex + 1}]</span>
                    </button>
                  );
                }
              }
              return <span key={idx}>{part}</span>;
            })}
          </div>

          {/* Sources Quick Buttons Bar */}
          <div className="pt-3 border-t border-white/10 flex flex-wrap gap-2 items-center">
            <span className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider">
              {TRANSLATIONS[appLanguage].citationsTitle}:
            </span>
            {msg.sources.map((src, sIdx) => (
              <button
                key={sIdx}
                onClick={() => {
                  setActiveSource(src);
                  setWorkspaceOpen(true);
                }}
                className={`text-xs px-2.5 py-1 rounded-lg border transition-all flex items-center gap-1.5 cursor-pointer ${
                  activeSource?.chunk_id === src.chunk_id
                    ? "bg-indigo-600 text-white border-indigo-400 shadow-md font-bold"
                    : "bg-white/5 hover:bg-white/10 text-zinc-300 border-white/10"
                }`}
              >
                <span>[{sIdx + 1}]</span>
                <span className="truncate max-w-[160px]">{src.title}</span>
                <span className="text-[10px] opacity-75 font-mono">({TRANSLATIONS[appLanguage].pageLabel} {src.page_number || 1})</span>
              </button>
            ))}
          </div>
        </div>
      );
    }

    return <p className="text-sm text-zinc-200 leading-relaxed font-normal">{msg.content}</p>;
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#090d16] text-zinc-100 font-sans">
      
      {/* 1. Header Bar */}
      <header className="h-16 border-b border-white/10 bg-[#0d1322]/90 backdrop-blur-md px-6 flex items-center justify-between shrink-0 z-30 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 flex items-center justify-center text-xl shadow-lg shadow-indigo-500/20">
            🐬
          </div>
          <div>
            <h1 className="text-base font-extrabold tracking-tight text-white flex items-center gap-2">
              {TRANSLATIONS[appLanguage].title}
            </h1>
            <p className="text-[11px] text-zinc-400 font-medium">
              {TRANSLATIONS[appLanguage].subtitle}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* API Health Heartbeat */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.06] text-xs font-semibold text-zinc-300">
            <span className={apiOnline ? "pulse-dot" : "w-2 h-2 rounded-full bg-red-500"} />
            <span>{apiOnline ? TRANSLATIONS[appLanguage].apiOnlineStatus : TRANSLATIONS[appLanguage].apiOfflineStatus}</span>
          </div>

          {/* Language Switcher */}
          <div className="flex items-center bg-black/40 border border-white/10 rounded-lg p-0.5 text-xs font-bold">
            <button
              onClick={() => setAppLanguage("cs")}
              className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                appLanguage === "cs" ? "bg-indigo-600 text-white shadow-sm" : "text-zinc-400 hover:text-white"
              }`}
            >
              CZ
            </button>
            <button
              onClick={() => setAppLanguage("en")}
              className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                appLanguage === "en" ? "bg-indigo-600 text-white shadow-sm" : "text-zinc-400 hover:text-white"
              }`}
            >
              EN
            </button>
          </div>

          {/* User Role Selector */}
          <div className="flex items-center gap-2 bg-white/[0.03] border border-white/10 rounded-xl px-3 py-1.5 text-xs">
            <span className="text-zinc-400 font-semibold">{TRANSLATIONS[appLanguage].userRoleLabel}</span>
            <select
              value={userRole}
              onChange={(e) => setUserRole(e.target.value)}
              className="bg-transparent text-indigo-300 font-bold focus:outline-none cursor-pointer"
            >
              <option value="User" className="bg-zinc-900 text-white">👤 User</option>
              <option value="Management" className="bg-zinc-900 text-white">🎖️ Management</option>
              <option value="Admin" className="bg-zinc-900 text-white">👑 Admin</option>
            </select>
          </div>
        </div>
      </header>

      {/* 2. Main Workspace Layout */}
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* Main Search & Chat Panel */}
        <main className="flex-1 flex flex-col h-full overflow-hidden bg-[#090d16] relative">
          
          {/* Chat Messages Stream */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-5xl mx-auto w-full">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex gap-4 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {msg.role === "assistant" && (
                  <div className="w-8 h-8 rounded-xl bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-sm shrink-0 text-indigo-300">
                    AI
                  </div>
                )}

                <div
                  className={`p-4 rounded-2xl max-w-3xl leading-relaxed ${
                    msg.role === "user"
                      ? "bg-indigo-600/90 text-white rounded-tr-none shadow-lg shadow-indigo-600/20"
                      : "glass-panel bg-[#111827]/80 border-white/10 text-zinc-200 rounded-tl-none"
                  }`}
                >
                  {renderMessageContent(msg)}
                </div>

                {msg.role === "user" && (
                  <div className="w-8 h-8 rounded-xl bg-zinc-800 border border-zinc-700 flex items-center justify-center text-xs shrink-0 text-zinc-300 font-bold">
                    Vy
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex gap-4 justify-start items-center">
                <div className="w-8 h-8 rounded-xl bg-indigo-600/30 border border-indigo-500/40 flex items-center justify-center text-sm shrink-0 text-indigo-300 animate-pulse">
                  AI
                </div>
                <div className="glass-panel p-4 rounded-2xl border-white/10 text-xs text-zinc-400 flex items-center gap-3">
                  <div className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                  <span>{TRANSLATIONS[appLanguage].thinkingMessage}</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Questions Chips (if chat is fresh) */}
          {messages.length <= 1 && (
            <div className="px-6 py-2 max-w-5xl mx-auto w-full">
              <span className="text-[11px] font-bold text-zinc-400 uppercase tracking-wider block mb-2">
                {TRANSLATIONS[appLanguage].suggestedQuestionsTitle}
              </span>
              <div className="flex flex-wrap gap-2">
                {[
                  TRANSLATIONS[appLanguage].suggestedQ1,
                  TRANSLATIONS[appLanguage].suggestedQ2,
                  TRANSLATIONS[appLanguage].suggestedQ3,
                  TRANSLATIONS[appLanguage].suggestedQ4,
                ].map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSubmit(q)}
                    className="text-xs px-3 py-1.5 rounded-xl bg-white/[0.03] hover:bg-indigo-600/20 text-zinc-300 hover:text-indigo-200 border border-white/[0.06] hover:border-indigo-500/30 transition-all cursor-pointer text-left"
                  >
                    💡 {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Bottom Search Input Bar */}
          <div className="p-6 bg-[#0c1222]/90 border-t border-white/10 backdrop-blur-md shrink-0">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSubmit(query);
              }}
              className="max-w-5xl mx-auto w-full flex items-center gap-3 relative"
            >
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={TRANSLATIONS[appLanguage].searchPlaceholder}
                className="flex-1 bg-black/50 border border-white/15 text-sm text-white placeholder-zinc-500 rounded-2xl px-5 py-4 focus:outline-none focus:border-indigo-500 font-medium shadow-inner transition-all"
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="px-6 py-4 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-2xl font-bold text-sm transition-all shadow-lg shadow-indigo-600/20 flex items-center gap-2 cursor-pointer active:scale-95 shrink-0"
              >
                <span>🔍</span>
                <span>{TRANSLATIONS[appLanguage].searchBtn}</span>
              </button>
            </form>
            <p className="text-[10px] text-zinc-500 text-center mt-2 font-medium">
              {TRANSLATIONS[appLanguage].disclaimer}
            </p>
          </div>
        </main>

        {/* 3. Right Citation Source Inspector Drawer */}
        {(workspaceOpen || activeSource) && (
          <aside className="w-full lg:w-96 border-l border-white/10 bg-[#0d1322] flex flex-col h-full shrink-0 z-20 shadow-2xl transition-all">
            {/* Drawer Header */}
            <div className="px-5 py-4 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
              <div className="flex items-center gap-2">
                <span className="text-lg">📁</span>
                <div>
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                    {TRANSLATIONS[appLanguage].citationsTitle}
                  </h3>
                  <p className="text-[10px] text-zinc-400">
                    {TRANSLATIONS[appLanguage].citationsSubtitle}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setWorkspaceOpen(false)}
                className="text-zinc-400 hover:text-white text-lg p-1 transition-colors cursor-pointer"
              >
                ✕
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-5">
              {activeSource ? (
                <div className="space-y-4">
                  {/* Document Title Header */}
                  <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-2">
                    <span className="text-[9px] font-bold text-indigo-400 uppercase tracking-wider block">
                      {TRANSLATIONS[appLanguage].sourceDocHeader}
                    </span>
                    <h4 className="text-sm font-bold text-white leading-snug">
                      📄 {activeSource.title}
                    </h4>
                    <div className="grid grid-cols-2 gap-2 pt-2 text-xs border-t border-white/5 mt-2">
                      <div>
                        <span className="text-zinc-500 block text-[10px]">{TRANSLATIONS[appLanguage].pageNumberLabel}</span>
                        <span className="font-semibold text-indigo-300 font-mono">
                          {TRANSLATIONS[appLanguage].pageLabel} {activeSource.page_number || 1}
                        </span>
                      </div>
                      <div>
                        <span className="text-zinc-500 block text-[10px]">{TRANSLATIONS[appLanguage].chapterSectionLabel}</span>
                        <span className="font-semibold text-zinc-300 truncate block">
                          {activeSource.section_title || "Hlavní text"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* KEY FEATURE: PROMINENT FULLY FORMATTED PDF PREVIEW BUTTON */}
                  <button
                    onClick={() => openPdfViewer(activeSource)}
                    className="w-full py-3.5 px-4 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white rounded-2xl font-extrabold text-xs transition-all shadow-xl shadow-indigo-600/25 flex items-center justify-center gap-2 cursor-pointer active:scale-95 border border-indigo-400/30"
                  >
                    <span>📄</span>
                    <span>{TRANSLATIONS[appLanguage].openPdfBtn}</span>
                  </button>

                  {/* Cited Text Passage Snippet */}
                  <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.05] space-y-2">
                    <span className="text-[9px] font-bold text-cyan-400 uppercase tracking-wider block">
                      {TRANSLATIONS[appLanguage].citedPassageLabel}
                    </span>
                    <div className="text-xs text-zinc-300 leading-relaxed font-mono bg-black/40 p-3 rounded-xl border border-white/5 max-h-48 overflow-y-auto">
                      {activeSource.content}
                    </div>
                  </div>

                  {/* Security & Freshness Audit Metrics */}
                  <div className="p-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] space-y-3 text-xs">
                    <span className="text-[9px] font-bold text-emerald-400 uppercase tracking-wider block">
                      {TRANSLATIONS[appLanguage].securityAuditLabel}
                    </span>
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-400">{TRANSLATIONS[appLanguage].freshnessLabel}:</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                        PLATNÝ (Current)
                      </span>
                    </div>
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-zinc-400">{TRANSLATIONS[appLanguage].aclGroupsLabel}:</span>
                      <div className="flex gap-1">
                        {(activeSource.allowed_groups || ["User"]).map((grp, gIdx) => (
                          <span key={gIdx} className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-white/5 text-zinc-300 border border-white/10">
                            {grp}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-12 text-zinc-500 text-xs">
                  {TRANSLATIONS[appLanguage].noCitationsFound}
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* 4. Embedded Fully Formatted PDF Viewer Modal */}
      <PdfViewerModal
        isOpen={pdfModalOpen}
        onClose={() => setPdfModalOpen(false)}
        documentId={selectedPdfDocId}
        documentTitle={selectedPdfTitle}
        pageNumber={selectedPdfPage}
        highlightChunkId={selectedPdfHighlightId}
        backendUrl={BACKEND_URL}
        language={appLanguage}
      />
    </div>
  );
}
