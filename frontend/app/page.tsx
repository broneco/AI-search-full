"use client";

import { useState, useEffect, useRef } from "react";

// Interface definitions matching the backend schemas
interface ChatSource {
  document_id: string;
  chunk_id: string;
  title: string;
  content: string;
  section_title: string | null;
  page_number: number | null;
  freshness_status: string;
  score: number;
}

interface Message {
  role: "system" | "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  latency_ms?: number;
  strategy?: string;
}

interface IngestedDocument {
  document_id: string;
  title: string;
  source_uri: string;
  source_type: string;
  document_type: string;
  language: string;
  freshness_status: string;
  ingested_at: string;
  chunk_count: number;
}

export default function Home() {
  // Application State
  const [query, setQuery] = useState("");
  const [searchStrategy, setSearchStrategy] = useState<"hybrid" | "vector" | "keyword">("hybrid");
  const [chatMode, setChatMode] = useState<"flash" | "thinking">("flash");
  
  // Interactive testing states for security & freshness
  const [userRole, setUserRole] = useState<"management" | "hr" | "finance" | "user">("management");
  const [freshnessFilter, setFreshnessFilter] = useState<"all" | "this_year" | "latest">("all");

  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Dobrý den! Jsem Váš firemní vyhledávací asistent. Zadejte libovolný dotaz a já vyhledám odpověď v nahraných směrnicích a dokumentech Jihočeské univerzity. Odpověď bude podložená citacemi a přizpůsobí se Vašim přístupovým právům.",
    }
  ]);
  const [loading, setLoading] = useState(false);
  const [activeSource, setActiveSource] = useState<ChatSource | null>(null);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [documents, setDocuments] = useState<IngestedDocument[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Chat message container ref for auto-scrolling
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Backend API URL Base
  const BACKEND_URL = "http://localhost:8000";

  // Map visual roles to dynamic Entra ID headers
  const getHeaders = () => {
    const headers: Record<string, string> = {};
    if (userRole === "management") {
      headers["X-User-Id"] = "ondrej.bronec";
      headers["X-User-Groups"] = "Management";
    } else if (userRole === "hr") {
      headers["X-User-Id"] = "eva.hr";
      headers["X-User-Groups"] = "HR";
    } else if (userRole === "finance") {
      headers["X-User-Id"] = "jan.finance";
      headers["X-User-Groups"] = "Finance";
    } else {
      headers["X-User-Id"] = "public.guest";
      headers["X-User-Groups"] = "User";
    }
    return headers;
  };

  // Helper to generate native PDF search highlights on the cited page
  const getSearchHash = (source: ChatSource) => {
    if (!source.page_number) return "";
    
    let hash = `#page=${source.page_number}`;
    
    if (source.content) {
      // 1. Clean up newlines and control characters
      let cleanText = source.content.replace(/[\r\n\t]+/g, " ");
      
      // 2. Strip single/double quotes, brackets, and backslashes to avoid syntax issues in the PDF search query
      cleanText = cleanText.replace(/["'\\()\[\]]/g, "");
      
      // 3. Clean up multiple spaces
      cleanText = cleanText.replace(/\s+/g, " ").trim();
      
      // 4. Split into words
      const words = cleanText.split(" ").filter(w => w.length > 0);
      
      // 5. Take a short 5-word unique prefix to ensure high search match reliability in the PDF text layer
      const phrase = words.slice(0, 5).join(" ");
      
      if (phrase) {
        hash += `&search="${encodeURIComponent(phrase)}"`;
      }
    }
    
    return hash;
  };

  // Check backend health status on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/health`);
        if (res.ok) {
          setApiOnline(true);
        } else {
          setApiOnline(false);
        }
      } catch (err) {
        setApiOnline(false);
      }
    };

    checkHealth();
    
    // Periodically check API health
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // Fetch documents list whenever userRole changes to demonstrate live dynamic ACL hiding
  useEffect(() => {
    fetchDocuments();
  }, [userRole]);

  // Auto-scroll chat window when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Load ingested documents list based on current active user groups
  const fetchDocuments = async () => {
    setLoadingDocs(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/list`, {
        headers: getHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (err) {
      console.error("Failed to fetch documents list", err);
    } finally {
      setLoadingDocs(false);
    }
  };

  // Submit Query to FastAPI RAG endpoint
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userQuery = query.trim();
    setQuery("");
    
    // Add user message to screen
    const userMsg: Message = { role: "user", content: userQuery };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getHeaders(),
        },
        body: JSON.stringify({
          query: userQuery,
          mode: chatMode,
          search_strategy: searchStrategy,
          freshness_filter: freshnessFilter,
          include_sources: true,
        }),
      });

      if (!res.ok) {
        throw new Error(`Server returned error code: ${res.status}`);
      }

      const data = await res.json();
      
      // Add AI response to screen
      const assistantMsg: Message = {
        role: "assistant",
        content: data.answer,
        sources: data.sources,
        latency_ms: data.metadata.latency_ms,
        strategy: data.metadata.retrieval_strategy,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      
      // Refresh documents list
      fetchDocuments();
    } catch (err: any) {
      console.error(err);
      const errMsg: Message = {
        role: "assistant",
        content: `Chyba při komunikaci se serverem: ${err.message || err}. Ujistěte se, že Váš FastAPI server běží na portu 8000.`,
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  // Handle clicking on inline citation button
  const handleCitationClick = (sourceIndex: number, sourcesList?: ChatSource[]) => {
    if (!sourcesList || sourcesList.length < sourceIndex) return;
    const clickedSource = sourcesList[sourceIndex - 1];
    if (clickedSource) {
      setActiveSource(clickedSource);
      setWorkspaceOpen(true);
    }
  };

  // Render text containing [Source 1], [Source 2] as interactive React buttons
  const renderMessageContent = (msg: Message) => {
    const text = msg.content;
    if (!text) return null;
    if (msg.role !== "assistant") return <p style={{ whiteSpace: "pre-wrap" }}>{text}</p>;

    const regex = /(\[Source \d+\])/g;
    const parts = text.split(regex);

    return (
      <p style={{ whiteSpace: "pre-wrap" }}>
        {parts.map((part, index) => {
          const match = part.match(/\[Source (\d+)\]/);
          if (match) {
            const sourceNum = parseInt(match[1], 10);
            return (
              <button
                key={index}
                onClick={() => handleCitationClick(sourceNum, msg.sources)}
                className="citation-badge"
                title={`Zobrazit podrobnosti o zdroji ${sourceNum}`}
              >
                📄 Zdroj {sourceNum}
              </button>
            );
          }
          return <span key={index}>{part}</span>;
        })}
      </p>
    );
  };

  return (
    <div className="flex flex-col flex-1 h-screen overflow-hidden bg-[#090d16] font-sans">
      
      {/* 1. Global Navigation Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/[0.05] bg-[#0c1220]/80 backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 text-white font-extrabold text-lg shadow-lg shadow-indigo-500/20">
            AI
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white bg-clip-text bg-gradient-to-r from-white to-zinc-400">
              Firemní AI Vyhledávač
            </h1>
            <p className="text-xs text-zinc-500">
              Inteligentní vyhledávání v dokumentech JU s citacemi
            </p>
          </div>
        </div>

        {/* Real-time system states */}
        <div className="flex items-center gap-6">
          {/* Dynamic Active User Role Selection (SSO Handshake Mockup) */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.02] border border-white/[0.05]">
            <span className="text-xs text-zinc-400 font-medium">Uživatel:</span>
            <select
              value={userRole}
              onChange={(e) => setUserRole(e.target.value as any)}
              className="bg-black/60 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
            >
              <option value="management">👑 Rektorát (Management)</option>
              <option value="hr">💼 Personální (HR Specialist)</option>
              <option value="finance">📊 Finanční (Finance Auditor)</option>
              <option value="user">👤 Zaměstnanec (Standard User)</option>
            </select>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.05] text-xs">
            <span className={`pulse-dot ${apiOnline === false ? "bg-red-500 shadow-red-500/50" : ""}`} />
            <span className="text-zinc-300 font-medium">
              {apiOnline === null ? "Připojování..." : apiOnline ? "FastAPI: Online" : "FastAPI: Odpojeno"}
            </span>
          </div>
        </div>
      </header>

      {/* 2. Main Workspace Layout Grid */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* Left Sidebar: Live Ingested Documents List */}
        <aside className="hidden lg:flex flex-col w-80 border-r border-white/[0.05] bg-[#070b13]/40 overflow-y-auto p-4 gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold tracking-wide text-zinc-400 uppercase">
              Přístupné soubory
            </h3>
            <button 
              onClick={fetchDocuments}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium transition-colors"
              title="Obnovit seznam souborů"
            >
              🔄 Obnovit
            </button>
          </div>

          {loadingDocs ? (
            <div className="flex flex-col gap-3 py-4 text-center text-xs text-zinc-500">
              Načítám databázi...
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col gap-2 py-8 text-center text-xs text-zinc-500 border border-dashed border-white/5 rounded-xl">
              Žádné soubory v databázi.
              <span className="text-[10px] text-zinc-600">Pro zvolenou roli nejsou dostupné žádné dokumenty.</span>
            </div>
          ) : (
            <div className="flex flex-col gap-2.5">
              {documents.map((doc) => (
                <div 
                  key={doc.document_id}
                  className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] transition-all hover:bg-white/[0.04] flex flex-col gap-1.5"
                >
                  <div className="flex items-start gap-1">
                    <a
                      href={`${BACKEND_URL}/api/documents/view/${doc.document_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-semibold text-zinc-300 hover:text-indigo-400 hover:underline truncate block flex-1"
                      title={`Kliknutím otevřete PDF: ${doc.title}`}
                    >
                      📄 {doc.title}
                    </a>
                  </div>
                  <div className="flex items-center justify-between text-[10px] text-zinc-500">
                    <span>{doc.chunk_count} pasáží</span>
                    <span className={`px-1.5 py-0.5 rounded border uppercase font-semibold text-[8px] ${
                      doc.freshness_status === "current"
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                    }`}>
                      {doc.freshness_status === "current" ? "Platný" : "Archiv"}
                    </span>
                  </div>
                  <div className="text-[9px] text-zinc-600 truncate">
                    Seřazeno: {new Date(doc.ingested_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </aside>

        {/* Center Section: Conversational AI Grounded Search Screen */}
        <main className="flex flex-col flex-1 bg-[#090d16] relative overflow-hidden">
          
          {/* Top Search Controls Bar */}
          <div className="flex flex-wrap items-center justify-between gap-4 p-4 border-b border-white/[0.04] bg-[#0a0f1b]/50">
            <div className="flex items-center gap-3">
              <span className="text-xs text-zinc-400 font-medium">Vyhledávání:</span>
              <div className="flex rounded-lg p-0.5 bg-black/40 border border-white/[0.05]">
                <button
                  type="button"
                  onClick={() => setSearchStrategy("hybrid")}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    searchStrategy === "hybrid"
                      ? "bg-indigo-600 text-white shadow-md"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  Hybridní (RRF)
                </button>
                <button
                  type="button"
                  onClick={() => setSearchStrategy("vector")}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    searchStrategy === "vector"
                      ? "bg-indigo-600 text-white shadow-md"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  Sémantická (Vector)
                </button>
                <button
                  type="button"
                  onClick={() => setSearchStrategy("keyword")}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                    searchStrategy === "keyword"
                      ? "bg-indigo-600 text-white shadow-md"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  Lexikální (FTS)
                </button>
              </div>
            </div>

            {/* Freshness Filter Selector */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-zinc-400 font-medium">Platnost (Freshness):</span>
              <div className="flex rounded-lg p-0.5 bg-black/40 border border-white/[0.05]">
                <button
                  type="button"
                  onClick={() => setFreshnessFilter("all")}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                    freshnessFilter === "all"
                      ? "bg-emerald-600 text-white shadow-md"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  Všechny
                </button>
                <button
                  type="button"
                  onClick={() => setFreshnessFilter("this_year")}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                    freshnessFilter === "this_year"
                      ? "bg-emerald-600 text-white shadow-md"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  Jen 2026
                </button>
                <button
                  type="button"
                  onClick={() => setFreshnessFilter("latest")}
                  className={`px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                    freshnessFilter === "latest"
                      ? "bg-emerald-600 text-white shadow-md"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  Jen platné
                </button>
              </div>
            </div>
          </div>

          {/* Chat Messages Feed Area */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex gap-4 max-w-4xl ${msg.role === "user" ? "ml-auto flex-row-reverse" : "mr-auto"}`}
              >
                {/* Visual Avatar icons */}
                <div className={`flex items-center justify-center w-8 h-8 rounded-lg text-sm font-bold shrink-0 ${
                  msg.role === "user" 
                    ? "bg-zinc-800 text-zinc-200" 
                    : "bg-indigo-900/50 text-indigo-300 border border-indigo-500/20"
                }`}>
                  {msg.role === "user" ? "U" : "AI"}
                </div>

                <div className="flex flex-col gap-1.5">
                  <div className={`p-4 rounded-2xl text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-indigo-600/90 text-white rounded-tr-none"
                      : "glass-panel text-zinc-100 rounded-tl-none border-white/[0.03]"
                  }`}>
                    {renderMessageContent(msg)}
                  </div>
                  
                  {/* Message latency and metadata details */}
                  {msg.role === "assistant" && msg.latency_ms && (
                    <div className="flex items-center gap-3 px-2 text-[10px] text-zinc-500 font-medium">
                      <span>⚡ Latency: {msg.latency_ms} ms</span>
                      <span className="w-1 h-1 rounded-full bg-zinc-600" />
                      <span className="uppercase">Retriever: {msg.strategy}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Simulated generation loading visual status indicators */}
            {loading && (
              <div className="flex gap-4 mr-auto">
                <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-900/50 text-indigo-300 border border-indigo-500/20 text-sm font-bold animate-pulse">
                  AI
                </div>
                <div className="flex flex-col gap-2">
                  <div className="glass-panel p-4 rounded-2xl rounded-tl-none border-white/[0.03]">
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1">
                        <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="w-2 h-2 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                      <span className="text-xs text-indigo-400 font-medium">Vyhledávám v Azure PostgreSQL (filtry: {userRole}, {freshnessFilter}) a generuji odpověď...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Chat Input Form Bar */}
          <div className="p-4 border-t border-white/[0.04] bg-[#070b13]/60 backdrop-blur-md">
            <form onSubmit={handleSubmit} className="flex gap-3 max-w-4xl mx-auto relative">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Zadejte dotaz (např. 'Jaká jsou pravidla pro registr smluv?')..."
                className="flex-1 px-4 py-3 rounded-xl bg-black/40 border border-white/[0.06] text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm transition-all shadow-lg shadow-indigo-600/25 disabled:opacity-50 disabled:cursor-not-allowed hover:translate-y-[-1px] active:translate-y-[0px]"
              >
                Odeslat
              </button>
            </form>
            <div className="text-[10px] text-center text-zinc-600 mt-2">
              Podporováno hybridním retrievrem RRF (pgvector + full-text search)
            </div>
          </div>

        </main>

        {/* Right Sidebar: Grounded Citations Document Preview Workspace */}
        <aside className={`fixed inset-y-0 right-0 z-50 flex flex-col w-[450px] border-l border-white/[0.08] bg-[#0c1222] shadow-2xl transition-all duration-300 transform ${
          workspaceOpen ? "translate-x-0" : "translate-x-full"
        } lg:relative lg:translate-x-0 lg:z-0`}>
          
          {/* Citation Sidebar Header */}
          <div className="flex items-center justify-between p-4 border-b border-white/[0.05] bg-[#0f172a]">
            <div className="flex items-center gap-2">
              <span className="text-lg">📁</span>
              <div>
                <h3 className="text-sm font-bold text-white">Pracovní prostor citací</h3>
                <p className="text-[10px] text-zinc-500">Ověření groundedness a audit přístupu</p>
              </div>
            </div>
            <button
              onClick={() => setWorkspaceOpen(false)}
              className="lg:hidden text-zinc-400 hover:text-white text-lg transition-colors p-1"
              title="Zavřít panel"
            >
              ✕
            </button>
          </div>

          {/* Citation Workspace Body */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            {activeSource ? (
              <div className="space-y-4">
                
                {/* 1. Header Metadata Section */}
                <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.04]">
                  <span className="text-[9px] font-bold text-indigo-400 tracking-wider uppercase block mb-1">
                    Zdrojový dokument (Kliknutím otevřete)
                  </span>
                  <h4 className="text-sm font-bold text-white leading-snug">
                    <a
                      href={`${BACKEND_URL}/api/documents/view/${activeSource.document_id}${getSearchHash(activeSource)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-white hover:text-indigo-400 hover:underline transition-colors block"
                      title={activeSource.page_number ? `Kliknutím otevřete PDF na straně ${activeSource.page_number}` : "Kliknutím otevřete celý PDF dokument v nové záložce"}
                    >
                      📄 {activeSource.title} {activeSource.page_number ? `(strana ${activeSource.page_number})` : ""}
                    </a>
                  </h4>
                  <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                    <div>
                      <span className="text-zinc-500 block text-[10px]">Číslo strany</span>
                      <span className="font-semibold text-zinc-300">Strana {activeSource.page_number || "N/A"}</span>
                    </div>
                    <div>
                      <span className="text-zinc-500 block text-[10px]">Kapitola / Sekce</span>
                      <span className="font-semibold text-zinc-300 truncate block" title={activeSource.section_title || "Několik sekcí"}>
                        {activeSource.section_title || "Hlavní text"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 2. Text Segment Content */}
                <div className="p-4 rounded-2xl bg-white/[0.01] border border-white/[0.04] space-y-2">
                  <span className="text-[9px] font-bold text-cyan-400 tracking-wider uppercase block">
                    Citovaná pasáž
                  </span>
                  <div className="highlight-chunk">
                    <p className="text-xs text-zinc-300 leading-relaxed font-mono">
                      {activeSource.content}
                    </p>
                  </div>
                </div>

                {/* 3. Security, ACL and Governance parameters */}
                <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.04] space-y-3">
                  <span className="text-[9px] font-bold text-emerald-400 tracking-wider uppercase block">
                    Bezpečnost a auditovatelnost
                  </span>
                  
                  <div className="space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-zinc-500">Stav čerstvosti (Freshness):</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] border font-semibold uppercase ${
                        activeSource.freshness_status === "current"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      }`}>
                        {activeSource.freshness_status === "current" ? "Platný (Current)" : "Archivováno"}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-zinc-500">RRF Shoda (Fused score):</span>
                      <span className="font-mono text-zinc-300 font-semibold">{activeSource.score.toFixed(6)}</span>
                    </div>

                    <div className="w-full h-px bg-white/5 my-2" />

                    <div>
                      <span className="text-zinc-500 block mb-1">Povolené skupiny (Security ACL):</span>
                      <div className="flex flex-wrap gap-1.5">
                        <span className="px-2 py-0.5 rounded bg-zinc-800 border border-white/5 text-[10px] text-zinc-300">Management</span>
                        {activeSource.title.toLowerCase().includes("registr_smluv") && (
                          <span className="px-2 py-0.5 rounded bg-zinc-800 border border-white/5 text-[10px] text-zinc-300">HR</span>
                        )}
                        {activeSource.title.toLowerCase().includes("evidence_prac_doby") && (
                          <span className="px-2 py-0.5 rounded bg-zinc-800 border border-white/5 text-[10px] text-zinc-300">HR</span>
                        )}
                        {activeSource.title.toLowerCase().includes("pokusna_zvirata") && (
                          <>
                            <span className="px-2 py-0.5 rounded bg-zinc-800 border border-white/5 text-[10px] text-zinc-300">HR</span>
                            <span className="px-2 py-0.5 rounded bg-zinc-800 border border-white/5 text-[10px] text-zinc-300">User</span>
                          </>
                        )}
                        {activeSource.title.toLowerCase().includes("rozpoctu") && (
                          <span className="px-2 py-0.5 rounded bg-zinc-800 border border-white/5 text-[10px] text-zinc-300">Finance</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            ) : (
              <div className="flex flex-col items-center justify-center h-96 text-center text-zinc-600 gap-3 border border-dashed border-white/5 rounded-2xl p-6">
                <span className="text-3xl">🗂️</span>
                <div>
                  <h4 className="text-xs font-bold text-zinc-500">Prázdný pracovní prostor</h4>
                  <p className="text-[10px] text-zinc-600 mt-1 max-w-[250px] mx-auto">
                    Klikněte na libovolnou citaci <span className="citation-badge">📄 Zdroj X</span> v odpovědi asistenta pro zobrazení podrobných informací a zobrazení celého dokumentu.
                  </p>
                </div>
              </div>
            )}
          </div>

        </aside>

      </div>
    </div>
  );
}
