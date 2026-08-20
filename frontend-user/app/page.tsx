"use client";

import React, { useState, useEffect, useRef } from "react";
import { TRANSLATIONS } from "./translations";
import { CLIENT_THEMES, DEFAULT_THEME_ID } from "./config/themes";
import { PdfViewerModal } from "./components/PdfViewerModal";
import { AuthModal } from "./components/AuthModal";
import { ThreadSidebar, ThreadItem } from "./components/ThreadSidebar";

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
  const [drawerZoom, setDrawerZoom] = useState<number>(100);

  // Client Theme State
  const [currentThemeId, setCurrentThemeId] = useState<string>("dolphin");

  // Read saved theme on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem("dolphin_client_theme") || process.env.NEXT_PUBLIC_CLIENT_THEME || DEFAULT_THEME_ID;
    if (CLIENT_THEMES[savedTheme]) {
      setCurrentThemeId(savedTheme);
    }
  }, []);

  const currentTheme = CLIENT_THEMES[currentThemeId] || CLIENT_THEMES.dolphin;

  // Apply dynamic CSS variables when theme changes
  useEffect(() => {
    if (currentTheme) {
      document.documentElement.style.setProperty("--brand-primary", currentTheme.colors.primary);
      document.documentElement.style.setProperty("--brand-primary-hover", currentTheme.colors.primaryHover);
      document.documentElement.style.setProperty("--brand-secondary", currentTheme.colors.secondary);
      document.documentElement.style.setProperty("--brand-gradient", currentTheme.colors.gradient);
      document.documentElement.style.setProperty("--brand-topbar-bg", currentTheme.colors.topBarBg);
      document.documentElement.style.setProperty("--brand-sidebar-bg", currentTheme.colors.sidebarBg);
      document.documentElement.style.setProperty("--brand-user-bubble", currentTheme.colors.userBubbleBg);
    }
  }, [currentTheme]);

  const handleThemeChange = (themeId: string) => {
    setCurrentThemeId(themeId);
    localStorage.setItem("dolphin_client_theme", themeId);
  };

  // Authentication State
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<any | null>(null);
  const [authModalOpen, setAuthModalOpen] = useState<boolean>(false);

  // Thread History State & Document Library State
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true);
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [documents, setDocuments] = useState<any[]>([]);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);

  // PDF Viewer Modal State (Full screen expansion)
  const [pdfModalOpen, setPdfModalOpen] = useState<boolean>(false);
  const [selectedPdfDocId, setSelectedPdfDocId] = useState<string | null>(null);
  const [selectedPdfTitle, setSelectedPdfTitle] = useState<string>("");
  const [selectedPdfPage, setSelectedPdfPage] = useState<number>(1);
  const [selectedPdfHighlightId, setSelectedPdfHighlightId] = useState<string | undefined>(undefined);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Read saved auth token on mount & verify session
  useEffect(() => {
    const savedToken = localStorage.getItem("dolphin_auth_token");
    if (savedToken) {
      setAuthToken(savedToken);
      fetchUserProfile(savedToken);
    } else {
      setAuthModalOpen(true);
    }
  }, []);

  // Fetch logged in user profile
  const fetchUserProfile = async (token: string) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setUserProfile(data);
        setUserRole(data.role || "User");
        fetchUserThreads(token);
        fetchDocuments(token);
      } else {
        localStorage.removeItem("dolphin_auth_token");
        setAuthToken(null);
        setUserProfile(null);
        setThreads([]);
        setDocuments([]);
        setAuthModalOpen(true);
      }
    } catch {
      console.error("Auth check failed");
    }
  };

  // Fetch threads list
  const fetchUserThreads = async (token?: string) => {
    try {
      const headers: Record<string, string> = {};
      const tok = token !== undefined ? token : authToken;
      if (tok) headers["Authorization"] = `Bearer ${tok}`;
      
      const res = await fetch(`${BACKEND_URL}/api/threads`, { headers });
      if (res.ok) {
        const data = await res.json();
        setThreads(data);
      }
    } catch {
      console.error("Threads fetch failed");
    }
  };

  // Fetch accessible documents list
  const fetchDocuments = async (token?: string) => {
    try {
      const headers: Record<string, string> = {};
      const tok = token !== undefined ? token : authToken;
      if (tok) headers["Authorization"] = `Bearer ${tok}`;

      const res = await fetch(`${BACKEND_URL}/api/documents/list`, { headers });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch {
      console.error("Documents fetch failed");
    }
  };

  const handleSelectDocument = (doc: any) => {
    const docSource: CitationSource = {
      document_id: doc.document_id,
      chunk_id: "",
      title: doc.title,
      content: `Dokument: ${doc.title}`,
      section_title: undefined,
      page_number: 1,
      freshness_status: doc.freshness_status || "current",
      score: 1.0,
    };
    setActiveSource(docSource);
    setWorkspaceOpen(true);
  };

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

  // Initialize greeting message when no active thread is selected
  useEffect(() => {
    if (!activeThreadId && messages.length === 0) {
      setMessages([
        {
          role: "assistant",
          content: TRANSLATIONS[appLanguage].initialGreeting,
        },
      ]);
    }
  }, [appLanguage, activeThreadId]);

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Load thread detail (messages & citations)
  const handleSelectThread = async (threadId: string) => {
    setActiveThreadId(threadId);
    setLoading(true);

    try {
      const headers: Record<string, string> = {};
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      const res = await fetch(`${BACKEND_URL}/api/threads/${threadId}`, { headers });
      if (res.ok) {
        const data = await res.json();
        const formattedMsgs: Message[] = (data.messages || []).map((m: any) => ({
          role: m.role,
          content: m.content,
          sources: m.sources || [],
        }));

        setMessages(
          formattedMsgs.length > 0
            ? formattedMsgs
            : [{ role: "assistant", content: TRANSLATIONS[appLanguage].initialGreeting }]
        );

        // Auto-select latest citation source from last assistant message
        const lastAsst = formattedMsgs.filter((m) => m.role === "assistant" && m.sources && m.sources.length > 0).pop();
        if (lastAsst && lastAsst.sources && lastAsst.sources.length > 0) {
          setActiveSource(lastAsst.sources[0]);
          setWorkspaceOpen(true);
        } else {
          setActiveSource(null);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Create New Chat (Reset local state lazily without DB auto-creation)
  const handleNewThread = () => {
    setActiveThreadId(null);
    setActiveSource(null);
    setMessages([
      {
        role: "assistant",
        content: TRANSLATIONS[appLanguage].initialGreeting,
      },
    ]);
  };

  // Rename Thread Title
  const handleRenameThread = async (threadId: string, newTitle: string) => {
    if (!authToken) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/threads/${threadId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${authToken}`,
        },
        body: JSON.stringify({ title: newTitle }),
      });
      if (res.ok) {
        fetchUserThreads(authToken);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Delete Thread
  const handleDeleteThread = async (threadId: string) => {
    if (!authToken) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/threads/${threadId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        setThreads((prev) => prev.filter((t) => t.thread_id !== threadId));
        if (activeThreadId === threadId) {
          handleNewThread();
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Handle Auth Login Success
  const handleAuthSuccess = (token: string, user: any) => {
    localStorage.setItem("dolphin_auth_token", token);
    setAuthToken(token);
    setUserProfile(user);
    setUserRole(user.role || "User");
    fetchUserThreads(token);
    fetchDocuments(token);
  };

  // Logout
  const handleLogout = () => {
    localStorage.removeItem("dolphin_auth_token");
    setAuthToken(null);
    setUserProfile(null);
    setThreads([]);
    setDocuments([]);
    handleNewThread();
    setAuthModalOpen(true);
  };

  // Get Auth headers based on active session
  const getHeaders = () => {
    const roleGroupsMap: Record<string, string[]> = {
      User: ["User"],
      Management: ["User", "Management"],
      Admin: ["User", "Management", "Admin"],
    };

    const userGroups = roleGroupsMap[userRole] || ["User"];
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-User-Role": userRole,
      "X-User-Groups": userGroups.join(","),
    };

    if (authToken) {
      headers["Authorization"] = `Bearer ${authToken}`;
    }
    return headers;
  };

  // Submit Query to Backend API
  const handleSubmit = async (userQuery: string) => {
    if (!userQuery.trim() || loading) return;

    if (!authToken) {
      setAuthModalOpen(true);
      return;
    }

    const trimmedQuery = userQuery.trim();
    setQuery("");

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
        body: JSON.stringify({
          query: trimmedQuery,
          thread_id: activeThreadId,
          locale: appLanguage,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const assistantMessage: Message = {
          role: "assistant",
          content: data.answer || "Odpověď nebyla nalezena.",
          sources: data.sources || [],
        };
        setMessages([...newMessages, assistantMessage]);

        if (data.thread_id) {
          setActiveThreadId(data.thread_id);
          if (authToken) fetchUserThreads(authToken);
        }

        // Auto-select first citation source if available and open PDF drawer
        if (data.sources && data.sources.length > 0) {
          setActiveSource(data.sources[0]);
          setWorkspaceOpen(true);
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

  // Open Full-screen PDF Viewer Modal
  const openPdfViewerModal = (source: CitationSource) => {
    setSelectedPdfDocId(source.document_id);
    setSelectedPdfTitle(source.title);
    setSelectedPdfPage(source.page_number || 1);
    setSelectedPdfHighlightId(source.chunk_id);
    setPdfModalOpen(true);
  };

  // Helper to format raw markdown text (**bold**, *italic*, - bullet lists)
  const renderFormattedMarkdown = (text: string) => {
    if (!text) return null;
    const lines = text.split("\n");

    return (
      <span className="inline">
        {lines.map((line, lineIdx) => {
          const trimmed = line.trim();
          const isBullet = trimmed.startsWith("- ") || trimmed.startsWith("* ");
          const contentText = isBullet ? trimmed.substring(2) : line;

          // Parse bold **text** and italic *text*
          const tokens = contentText.split(/(\*\*.*?\*\*|\*.*?\*)/g);

          const formattedLine = tokens.map((token, tIdx) => {
            if (token.startsWith("**") && token.endsWith("**") && token.length > 4) {
              return (
                <strong key={tIdx} className="font-extrabold text-white bg-white/5 px-1 py-0.5 rounded border border-white/10">
                  {token.slice(2, -2)}
                </strong>
              );
            }
            if (token.startsWith("*") && token.endsWith("*") && token.length > 2) {
              return (
                <em key={tIdx} className="italic text-indigo-300">
                  {token.slice(1, -1)}
                </em>
              );
            }
            return <span key={tIdx}>{token}</span>;
          });

          if (isBullet) {
            return (
              <div key={lineIdx} className="flex items-start gap-2 my-1 pl-2 font-medium">
                <span className="text-indigo-400 font-extrabold select-none mt-0.5">•</span>
                <span className="flex-1">{formattedLine}</span>
              </div>
            );
          }

          return (
            <React.Fragment key={lineIdx}>
              {formattedLine}
              {lineIdx < lines.length - 1 && <br />}
            </React.Fragment>
          );
        })}
      </span>
    );
  };

  // Render assistant response with interactive inline document badges and Markdown formatting
  const renderMessageContent = (msg: Message) => {
    if (msg.role === "user") {
      return <p className="text-sm text-zinc-100 leading-relaxed font-medium">{msg.content}</p>;
    }

    let parsedContent = msg.content || "";

    if (msg.sources && msg.sources.length > 0) {
      const parts = parsedContent.split(/(\[(?:Source\s*)?\d+\])/gi);
      return (
        <div className="space-y-4">
          <div className="text-sm text-zinc-200 leading-relaxed space-y-2">
            {parts.map((part, idx) => {
              const match = part.match(/\[(?:Source\s*)?(\d+)\]/i);
              if (match) {
                const citeIndex = parseInt(match[1], 10) - 1;
                const source = msg.sources && msg.sources[citeIndex];

                if (source) {
                  return (
                    <button
                      key={idx}
                      onClick={() => {
                        setActiveSource(source);
                        setWorkspaceOpen(true);
                      }}
                      className={`inline-flex items-center gap-1 mx-1 px-2 py-0.5 rounded-md font-bold text-xs transition-all transform hover:scale-110 cursor-pointer shadow-sm ${
                        activeSource?.chunk_id === source.chunk_id
                          ? "bg-indigo-500 text-white border border-indigo-400 ring-2 ring-indigo-400/30"
                          : "bg-indigo-500/20 hover:bg-indigo-500/35 text-indigo-300 hover:text-white border border-indigo-500/40"
                      }`}
                      title={`${source.title} (${TRANSLATIONS[appLanguage].pageLabel} ${source.page_number || 1})`}
                    >
                      <span>📄</span>
                      <span>[{citeIndex + 1}]</span>
                    </button>
                  );
                }
              }
              return <React.Fragment key={idx}>{renderFormattedMarkdown(part)}</React.Fragment>;
            })}
          </div>

          {/* Bottom Summary List of Citations */}
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
                className={`text-xs px-3 py-1.5 rounded-xl border transition-all flex items-center gap-1.5 cursor-pointer ${
                  activeSource?.chunk_id === src.chunk_id
                    ? "bg-indigo-600 text-white border-indigo-400 shadow-lg font-bold"
                    : "bg-white/5 hover:bg-white/10 text-zinc-300 border-white/10"
                }`}
              >
                <span>📄</span>
                <span>[{sIdx + 1}]</span>
                <span className="truncate max-w-[180px]">{src.title}</span>
                <span className="text-[10px] opacity-80 font-mono">({TRANSLATIONS[appLanguage].pageLabel} {src.page_number || 1})</span>
              </button>
            ))}
          </div>
        </div>
      );
    }

    return <div className="text-sm text-zinc-200 leading-relaxed font-normal">{renderFormattedMarkdown(parsedContent)}</div>;
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#090d16] text-zinc-100 font-sans">
      
      {/* 1. Header Bar */}
      <header
        style={{ backgroundColor: currentTheme.colors.topBarBg }}
        className="h-16 border-b border-white/10 backdrop-blur-md px-6 flex items-center justify-between shrink-0 z-30 shadow-lg transition-colors duration-300"
      >
        <div className="flex items-center gap-3">
          <div className="h-11 px-2.5 py-1 bg-white/90 rounded-xl flex items-center justify-center border border-white/30 shadow-md">
            <img
              src={currentTheme.logoUrl}
              alt={currentTheme.name}
              style={{ height: `${currentTheme.logoHeight}px` }}
              className="object-contain max-w-[160px]"
            />
          </div>
          <div>
            <h1 className="text-base font-extrabold tracking-tight text-white flex items-center gap-2">
              {currentTheme.appName}
            </h1>
            <p className="text-[11px] text-white/80 font-medium">
              {currentTheme.appTagline}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 sm:gap-4">
          {/* API Health Heartbeat */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.08] border border-white/[0.12] text-xs font-semibold text-white">
            <span className={apiOnline ? "pulse-dot" : "w-2 h-2 rounded-full bg-red-500"} />
            <span>{apiOnline ? TRANSLATIONS[appLanguage].apiOnlineStatus : TRANSLATIONS[appLanguage].apiOfflineStatus}</span>
          </div>

          {/* Language Switcher */}
          <div className="flex items-center bg-black/40 border border-white/20 rounded-lg p-0.5 text-xs font-bold">
            <button
              onClick={() => setAppLanguage("cs")}
              className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                appLanguage === "cs" ? "bg-white/25 text-white shadow-sm font-extrabold" : "text-white/70 hover:text-white"
              }`}
            >
              CZ
            </button>
            <button
              onClick={() => setAppLanguage("en")}
              className={`px-2.5 py-1 rounded-md transition-colors cursor-pointer ${
                appLanguage === "en" ? "bg-white/25 text-white shadow-sm font-extrabold" : "text-white/70 hover:text-white"
              }`}
            >
              EN
            </button>
          </div>

          {/* User Auth Profile Button */}
          {userProfile ? (
            <div className="flex items-center gap-2 bg-white/15 border border-white/25 rounded-xl px-3 py-1.5 text-xs text-white">
              <span className="font-bold">👤 {userProfile.username}</span>
              <span className="text-[10px] bg-white/20 text-white px-1.5 py-0.2 rounded uppercase font-semibold">
                {userProfile.role}
              </span>
            </div>
          ) : (
            <button
              onClick={() => setAuthModalOpen(true)}
              className="px-3.5 py-1.5 bg-white/20 hover:bg-white/30 text-white border border-white/30 rounded-xl font-bold text-xs transition-all shadow-md cursor-pointer flex items-center gap-1.5"
            >
              <span>🔑</span>
              <span>{appLanguage === "cs" ? "Přihlásit se" : "Sign In"}</span>
            </button>
          )}
        </div>
      </header>

      {/* 2. Main Workspace Layout */}
      <div className="flex flex-1 overflow-hidden relative">
        
        {/* Left Thread History & Document Library Sidebar */}
        <ThreadSidebar
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          threads={threads}
          activeThreadId={activeThreadId}
          onSelectThread={handleSelectThread}
          onNewThread={handleNewThread}
          onRenameThread={handleRenameThread}
          onDeleteThread={handleDeleteThread}
          documents={documents}
          onSelectDocument={handleSelectDocument}
          user={userProfile}
          onLogout={handleLogout}
          language={appLanguage}
        />

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

        {/* 3. Direct Live Formatted PDF Page Inspector Drawer */}
        {(workspaceOpen || activeSource) && (
          <aside className="w-full lg:w-[480px] xl:w-[560px] border-l border-white/10 bg-[#0d1322] flex flex-col h-full shrink-0 z-20 shadow-2xl transition-all">
            {/* Drawer Header Toolbar */}
            <div className="px-5 py-3.5 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
              <div className="flex items-center gap-2.5 overflow-hidden">
                <span className="text-lg">📄</span>
                <div className="overflow-hidden">
                  <h3 className="text-xs font-bold text-white truncate max-w-[240px]" title={activeSource?.title}>
                    {activeSource?.title || "PDF Doklad"}
                  </h3>
                  <div className="flex items-center gap-2 text-[10px] text-zinc-400 mt-0.5">
                    <span className="bg-indigo-500/20 text-indigo-300 font-bold px-2 py-0.5 rounded border border-indigo-500/30 font-mono">
                      {TRANSLATIONS[appLanguage].pageLabel} {activeSource?.page_number || 1}
                    </span>
                    <span className="bg-emerald-500/20 text-emerald-300 font-bold px-2 py-0.5 rounded border border-emerald-500/30">
                      ✨ {appLanguage === "cs" ? "Zvýrazněná pasáž" : "Highlighted Passage"}
                    </span>
                  </div>
                </div>
              </div>

              {/* PDF Control Buttons */}
              <div className="flex items-center gap-1.5">
                {/* Zoom Controls */}
                <div className="flex items-center bg-black/40 border border-white/10 rounded-lg p-0.5 text-xs">
                  <button
                    onClick={() => setDrawerZoom((prev) => Math.max(50, prev - 15))}
                    className="px-2 py-1 text-zinc-400 hover:text-white hover:bg-white/10 rounded transition-colors cursor-pointer"
                    title="Zoom out"
                  >
                    🔍 -
                  </button>
                  <span className="px-1 text-zinc-300 font-mono text-[10px]">{drawerZoom}%</span>
                  <button
                    onClick={() => setDrawerZoom((prev) => Math.min(200, prev + 15))}
                    className="px-2 py-1 text-zinc-400 hover:text-white hover:bg-white/10 rounded transition-colors cursor-pointer"
                    title="Zoom in"
                  >
                    🔍 +
                  </button>
                </div>

                {/* Open in New Window */}
                {activeSource && (
                  <a
                    href={`${BACKEND_URL}/api/documents/view/${activeSource.document_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="p-2 text-zinc-400 hover:text-indigo-300 hover:bg-white/10 rounded-lg transition-colors cursor-pointer text-xs flex items-center justify-center font-bold"
                    title={appLanguage === "cs" ? "Otevřít na nové záložce" : "Open in new tab"}
                  >
                    <span>↗️</span>
                  </a>
                )}

                {/* Pop-out Modal */}
                {activeSource && (
                  <button
                    onClick={() => openPdfViewerModal(activeSource)}
                    className="p-2 text-zinc-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors cursor-pointer text-xs"
                    title={appLanguage === "cs" ? "Celoobrazovkový náhled" : "Full screen modal"}
                  >
                    ⛶
                  </button>
                )}

                {/* Close Drawer */}
                <button
                  onClick={() => {
                    setWorkspaceOpen(false);
                    setActiveSource(null);
                  }}
                  className="p-2 text-zinc-400 hover:text-white hover:bg-white/10 rounded-lg transition-colors text-base font-bold cursor-pointer ml-1"
                  title={appLanguage === "cs" ? "Zavřít panel" : "Close panel"}
                >
                  ✕
                </button>
              </div>
            </div>

            {/* Embedded Live Formatted PDF Page Canvas */}
            <div className="flex-1 bg-zinc-950/90 w-full h-full overflow-hidden flex items-center justify-center relative">
              {activeSource ? (
                <iframe
                  src={`${BACKEND_URL}/api/documents/view/${activeSource.document_id}?highlight_chunk_id=${activeSource.chunk_id}#page=${activeSource.page_number || 1}&toolbar=0&navpanes=0`}
                  title={`PDF Live View - ${activeSource.title}`}
                  className="w-full h-full border-none transition-transform duration-200"
                  style={{ transform: `scale(${drawerZoom / 100})`, transformOrigin: "top center" }}
                />
              ) : (
                <div className="text-center py-12 text-zinc-500 text-xs">
                  {TRANSLATIONS[appLanguage].noCitationsFound}
                </div>
              )}
            </div>

            {/* Security & Freshness Audit Footer */}
            {activeSource && (
              <div className="px-5 py-2.5 bg-black/60 border-t border-white/5 flex items-center justify-between text-[10px] text-zinc-400 shrink-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-zinc-300">Stav:</span>
                  <span className="px-2 py-0.5 rounded font-bold uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                    PLATNÝ (Current)
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="font-semibold text-zinc-300">ACL:</span>
                  {(activeSource.allowed_groups || ["User"]).map((grp, gIdx) => (
                    <span key={gIdx} className="px-1.5 py-0.5 rounded font-bold bg-white/5 text-zinc-300 border border-white/10">
                      {grp}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </aside>
        )}
      </div>

      {/* 4. Full-screen PDF Viewer Modal */}
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

      {/* 5. Auth Login/Register Modal */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={handleAuthSuccess}
        backendUrl={BACKEND_URL}
        language={appLanguage}
      />
    </div>
  );
}
