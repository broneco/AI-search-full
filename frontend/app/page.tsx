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
  allowed_groups?: string[];
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
  created_at?: string;
  security_acl?: {
    allowed_groups: string[];
  };
  metadata_json?: {
    department?: string;
    replaces_document_title?: string;
    replaced_by_document_title?: string;
    modifies_document_title?: string;
    [key: string]: any;
  };
}

interface Category {
  key: string;
  label: string;
  description: string;
  allowed_groups: string[];
  role_name?: string;
}

interface Config {
  categories: Category[];
  analysis_rules: string;
}

// Interactive pill selector component for allowed_groups
function CategoryTagInput({
  allowedGroups,
  onChange,
  suggestions = ["Management", "HR", "Finance", "User"]
}: {
  allowedGroups: string[];
  onChange: (groups: string[]) => void;
  suggestions?: string[];
}) {
  const [inputValue, setInputValue] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const predefinedGroups = suggestions;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const val = inputValue.trim();
      if (val && !allowedGroups.includes(val)) {
        onChange([...allowedGroups, val]);
        setInputValue("");
      }
    }
  };

  const addGroup = (group: string) => {
    if (!allowedGroups.includes(group)) {
      onChange([...allowedGroups, group]);
    }
    setInputValue("");
    setShowSuggestions(false);
  };

  const removeGroup = (group: string) => {
    onChange(allowedGroups.filter((g) => g !== group));
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (suggestionsRef.current && !suggestionsRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredSuggestions = predefinedGroups.filter(
    (g) => g.toLowerCase().includes(inputValue.toLowerCase()) && !allowedGroups.includes(g)
  );

  return (
    <div className="relative space-y-1.5">
      <div className="flex flex-wrap gap-1.5 p-2 rounded-xl bg-black/40 border border-white/[0.08] min-h-[40px] items-center">
        {allowedGroups.map((group) => (
          <span
            key={group}
            className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-indigo-900/60 border border-indigo-500/20 text-xs text-indigo-300 font-bold"
          >
            {group}
            <button
              type="button"
              onClick={() => removeGroup(group)}
              className="hover:text-red-400 font-bold ml-1 transition-colors text-[10px]"
            >
              ✕
            </button>
          </span>
        ))}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value);
            setShowSuggestions(true);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => setShowSuggestions(true)}
          placeholder={allowedGroups.length === 0 ? "Přidejte skupinu (stiskněte Enter)..." : ""}
          className="flex-1 min-w-[120px] bg-transparent border-none focus:outline-none text-xs text-zinc-200 placeholder-zinc-600"
        />
      </div>
      {showSuggestions && (inputValue || filteredSuggestions.length > 0) && (
        <div
          ref={suggestionsRef}
          className="absolute z-10 w-full mt-1 bg-[#0f172a] border border-white/[0.08] rounded-xl shadow-xl max-h-36 overflow-y-auto divide-y divide-white/5"
        >
          {filteredSuggestions.map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => addGroup(g)}
              className="w-full text-left px-3 py-2 text-xs text-zinc-300 hover:bg-white/[0.03] hover:text-white transition-all font-semibold"
            >
              ➕ Přidat {g}
            </button>
          ))}
          {inputValue &&
            !allowedGroups.includes(inputValue.trim()) &&
            !predefinedGroups.includes(inputValue.trim()) && (
              <button
                type="button"
                onClick={() => addGroup(inputValue.trim())}
                className="w-full text-left px-3 py-2 text-xs text-zinc-400 hover:bg-white/[0.03] hover:text-white transition-all font-mono"
              >
                ✨ Vytvořit "{inputValue.trim()}"
              </button>
            )}
        </div>
      )}
    </div>
  );
}

export default function Home() {
  // Application Navigation
  const [activeTab, setActiveTab] = useState<"chat" | "ingest" | "config">("chat");

  // Dynamic Categories and Config
  const [config, setConfig] = useState<Config | null>(null);
  const [editingConfig, setEditingConfig] = useState<Config | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);

  // Category migrations state (keeps track of where to migrate documents of deleted categories)
  const [categoryMigrations, setCategoryMigrations] = useState<Record<string, string>>({});
  const [showMigrationModal, setShowMigrationModal] = useState(false);
  const [deletingCatIndex, setDeletingCatIndex] = useState<number | null>(null);
  const [migrationTargetKey, setMigrationTargetKey] = useState<string>("");

  // Application State
  const [query, setQuery] = useState("");
  const [searchStrategy, setSearchStrategy] = useState<"hybrid" | "vector" | "keyword">("hybrid");
  const [chatMode, setChatMode] = useState<"flash" | "thinking">("flash");
  
  // Interactive testing states for security & freshness
  const [userRole, setUserRole] = useState<string>("management");
  const [freshnessFilter, setFreshnessFilter] = useState<"all" | "this_year" | "latest">("all");

  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content: "Dobrý den! Jsem Váš firemní vyhledávací asistent. Zadejte libovolný dotaz a já vyhledám odpověď v nahraných směrnicích a dokumentech Dolphin Consulting. Odpověď bude podložená citacemi a přizpůsobí se Vašim přístupovým právům.",
    }
  ]);
  const [loading, setLoading] = useState(false);
  const [activeSource, setActiveSource] = useState<ChatSource | null>(null);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [documents, setDocuments] = useState<IngestedDocument[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);

  // Ingestion Form State
  const [fileToUpload, setFileToUpload] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [analyzingDraft, setAnalyzingDraft] = useState(false);
  const [draftResult, setDraftResult] = useState<{
    title: string;
    suggested_date: string;
    suggested_category: string;
    relationship: {
      relationship_type: string;
      target_document_id: string | null;
      target_document_title: string | null;
    };
    temp_file_path: string;
    original_filename: string;
  } | null>(null);

  const [confirmedTitle, setConfirmedTitle] = useState("");
  const [confirmedDate, setConfirmedDate] = useState("");
  const [confirmedCategory, setConfirmedCategory] = useState("");
  const [confirmedRelType, setConfirmedRelType] = useState("none");
  const [confirmedRelTargetId, setConfirmedRelTargetId] = useState("");
  const [ingestingConfirmed, setIngestingConfirmed] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<{ type: "success" | "error"; message: string } | null>(null);
  
  // Existing Document Editing State
  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  const [confirmedFreshnessStatus, setConfirmedFreshnessStatus] = useState<"current" | "archived">("current");

  // Chat message container ref for auto-scrolling
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Backend API URL Base
  const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Re-indexing progress state
  const [showReindexModal, setShowReindexModal] = useState(false);
  const [reindexProgress, setReindexProgress] = useState<{
    status: "idle" | "running" | "completed" | "failed";
    total_files: number;
    processed_files: number;
    current_file: string | null;
    phase: "clearing_db" | "scanning_files" | "analyzing" | "ingesting" | null;
    error: string | null;
  } | null>(null);

  // Polling handler for re-indexing progress
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  const startPollingProgress = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/documents/reindex-progress`);
        if (res.ok) {
          const data = await res.json();
          setReindexProgress(data);
          if (data.status === "completed" || data.status === "failed") {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            // Refresh documents when complete
            fetchDocuments();
          }
        }
      } catch (err) {
        console.error("Error polling re-index progress:", err);
      }
    }, 1000);
  };

  // Clean up interval on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const getReindexPercentage = () => {
    if (!reindexProgress) return 0;
    const { status, phase, total_files, processed_files } = reindexProgress;
    if (status === "completed") return 100;
    if (status === "idle") return 0;
    
    if (phase === "clearing_db" || phase === "scanning_files") {
      return 5;
    }
    if (phase === "analyzing") {
      if (!total_files) return 10;
      return Math.round((processed_files / total_files) * 50);
    }
    if (phase === "ingesting") {
      if (!total_files) return 60;
      return Math.round(50 + (processed_files / total_files) * 50);
    }
    return 0;
  };

  // Helper to resolve category label from key/UUID
  const getCategoryLabel = (catKey?: string) => {
    if (!catKey || !config?.categories) return "Obecné";
    const cat = config.categories.find((c) => c.key === catKey);
    return cat ? cat.label : "Obecné";
  };

  // Helper to format date in Czech style
  const formatReleaseDate = (dateStr?: string) => {
    if (!dateStr) return null;
    try {
      return new Date(dateStr).toLocaleDateString("cs-CZ");
    } catch {
      return dateStr;
    }
  };

  // Fetch dynamic categories config
  const fetchConfig = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/categories`);
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
        setEditingConfig(data);
        
        // Match default user role dynamically to first category key
        if (data.categories && data.categories.length > 0) {
          const keys = data.categories.map((c: Category) => c.key.toLowerCase());
          setUserRole((prev) => (keys.includes(prev.toLowerCase()) ? prev.toLowerCase() : keys[0]));
        }
      }
    } catch (err) {
      console.error("Failed to fetch categories config", err);
    }
  };

  // Map visual roles to dynamic Entra ID headers based on dynamic config
  const getHeaders = () => {
    const headers: Record<string, string> = {};
    if (config?.categories) {
      const activeCat = config.categories.find(
        (cat) => cat.key.toLowerCase() === userRole.toLowerCase()
      );
      if (activeCat) {
        headers["X-User-Id"] = `${userRole.toLowerCase()}.user`;
        let resolvedRole = activeCat.role_name;
        if (!resolvedRole) {
          if (activeCat.key.toLowerCase() === "management") {
            resolvedRole = "Management";
          } else if (activeCat.key.toLowerCase() === "user") {
            resolvedRole = "User";
          } else {
            const groups = activeCat.allowed_groups.filter(
              (g) => g.toLowerCase() !== "management"
            );
            resolvedRole = groups.length > 0 ? groups[0] : activeCat.key;
          }
        }
        headers["X-User-Groups"] = resolvedRole;
        return headers;
      }
    }
    // Fallback defaults
    headers["X-User-Id"] = "public.guest";
    headers["X-User-Groups"] = "User";
    return headers;
  };

  // Helper to generate dynamic backend PDF highlighting query + page scroll hash
  const getSearchHash = (source: ChatSource) => {
    let urlParams = "";
    if (source.chunk_id) {
      urlParams += `?highlight_chunk_id=${source.chunk_id}`;
    }
    if (source.page_number) {
      urlParams += `#page=${source.page_number}`;
    }
    return urlParams;
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
    fetchConfig();
    
    // Periodically check API health
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // Fetch documents list whenever userRole changes to demonstrate live dynamic ACL hiding
  useEffect(() => {
    fetchDocuments();
  }, [userRole, config]);

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

  // Ingestion File Upload Handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.type === "application/pdf" || file.name.endsWith(".pdf") || file.name.endsWith(".txt")) {
        triggerDraftAnalysis(file);
      } else {
        alert("Podporovány jsou pouze soubory PDF a TXT.");
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      triggerDraftAnalysis(e.target.files[0]);
    }
  };

  // Call Analyze endpoint to get suggested metadata
  const triggerDraftAnalysis = async (file: File) => {
    setFileToUpload(file);
    setAnalyzingDraft(true);
    setDraftResult(null);
    setIngestStatus(null);
    
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/analyze-draft`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Analýza konceptu selhala: ${res.status}`);
      }

      const data = await res.json();
      setDraftResult(data);
      
      // Seed editable form with suggested values
      setConfirmedTitle(data.title);
      setConfirmedDate(data.suggested_date || new Date().toISOString().split("T")[0]);
      setConfirmedCategory(data.suggested_category);
      setConfirmedRelType(data.relationship.relationship_type);
      setConfirmedRelTargetId(data.relationship.target_document_id || "");
    } catch (err: any) {
      console.error(err);
      setIngestStatus({
        type: "error",
        message: `Chyba při analýze dokumentu: ${err.message || err}`,
      });
      setFileToUpload(null);
    } finally {
      setAnalyzingDraft(false);
    }
  };

  // Submit confirmed metadata to complete RAG ingestion
  const handleConfirmIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!draftResult || ingestingConfirmed) return;

    setIngestingConfirmed(true);
    setIngestStatus(null);

    const targetDoc = documents.find((doc) => doc.document_id === confirmedRelTargetId);

    const payload = {
      title: confirmedTitle,
      date: confirmedDate,
      category: confirmedCategory,
      relationship: {
        relationship_type: confirmedRelType,
        target_document_id: confirmedRelType !== "none" ? confirmedRelTargetId : null,
        target_document_title: confirmedRelType !== "none" && targetDoc ? targetDoc.title : null,
      },
      temp_file_path: draftResult.temp_file_path,
      original_filename: draftResult.original_filename,
    };

    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/ingest-confirmed`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || `Ingest selhal: ${res.status}`);
      }

      const data = await res.json();
      setIngestStatus({
        type: "success",
        message: data.message,
      });
      
      // Reset form states
      setDraftResult(null);
      setFileToUpload(null);
      
      // Refresh accessible documents list
      fetchDocuments();
    } catch (err: any) {
      console.error(err);
      setIngestStatus({
        type: "error",
        message: `Chyba při dokončení importu: ${err.message || err}`,
      });
    } finally {
      setIngestingConfirmed(false);
    }
  };

  // Submit updated metadata for an existing document
  const handleSaveDocEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingDocId || ingestingConfirmed) return;

    setIngestingConfirmed(true);
    setIngestStatus(null);

    const payload = {
      document_id: editingDocId,
      title: confirmedTitle,
      date: confirmedDate,
      category: confirmedCategory,
      freshness_status: confirmedFreshnessStatus,
    };

    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/update-metadata`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || `Úprava selhala: ${res.status}`);
      }

      const data = await res.json();
      setIngestStatus({
        type: "success",
        message: data.message,
      });

      // Clear edit state
      setEditingDocId(null);
      
      // Refresh accessible documents list
      fetchDocuments();
    } catch (err: any) {
      console.error(err);
      setIngestStatus({
        type: "error",
        message: `Chyba při ukládání změn: ${err.message || err}`,
      });
    } finally {
      setIngestingConfirmed(false);
    }
  };

  const handleStartEditDoc = (doc: IngestedDocument) => {
    // Reset ingestion states first
    setFileToUpload(null);
    setDraftResult(null);
    setIngestStatus(null);
    
    // Set edit states
    setEditingDocId(doc.document_id);
    setConfirmedTitle(doc.title);
    
    let dateStr = "";
    if (doc.metadata_json?.created_at) {
      dateStr = doc.metadata_json.created_at.split("T")[0];
    } else if (doc.created_at) {
      dateStr = doc.created_at.split("T")[0];
    }
    setConfirmedDate(dateStr);
    setConfirmedCategory(doc.metadata_json?.department || "");
    setConfirmedFreshnessStatus(doc.freshness_status as "current" | "archived" || "current");
  };

  // Config Editor Handlers
  const handleCategoryFieldChange = (index: number, field: string, value: string) => {
    if (!editingConfig) return;
    const updated = [...editingConfig.categories];
    updated[index] = {
      ...updated[index],
      [field]: value
    };
    setEditingConfig({ ...editingConfig, categories: updated });
  };

  const handleAllowedGroupsChange = (index: number, groups: string[]) => {
    if (!editingConfig) return;
    const updated = [...editingConfig.categories];
    updated[index] = {
      ...updated[index],
      allowed_groups: groups
    };
    setEditingConfig({ ...editingConfig, categories: updated });
  };

  const handleRulesChange = (value: string) => {
    if (!editingConfig) return;
    setEditingConfig({ ...editingConfig, analysis_rules: value });
  };

  const handleAddCategory = () => {
    if (!editingConfig) return;
    
    const newUuid = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });

    const newCat: Category = {
      key: newUuid,
      label: "Nová kategorie",
      description: "Popis této kategorie pro LLM klasifikátor.",
      allowed_groups: ["Management"],
      role_name: "NewRole"
    };

    setEditingConfig({
      ...editingConfig,
      categories: [...editingConfig.categories, newCat]
    });
  };

  const handleDeleteCategory = (index: number) => {
    if (!editingConfig) return;
    if (editingConfig.categories.length <= 1) {
      alert("Musíte ponechat alespoň jednu kategorii.");
      return;
    }
    
    setDeletingCatIndex(index);
    const remaining = editingConfig.categories.filter((_, idx) => idx !== index);
    if (remaining.length > 0) {
      setMigrationTargetKey(remaining[0].key);
    }
    setShowMigrationModal(true);
  };

  const saveConfigToServer = async (
    configToSave: Config,
    migrationsToSave: Record<string, string>,
    isDeletion = false
  ) => {
    setSavingConfig(true);
    try {
      const payload = {
        ...configToSave,
        category_migrations: migrationsToSave
      };

      const res = await fetch(`${BACKEND_URL}/api/documents/categories`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        setCategoryMigrations({});
        await fetchConfig();
        // Always refresh the documents list from DB so any migrated/updated document ACLs are loaded
        fetchDocuments();

        const promptMsg = isDeletion
          ? "Kategorie byla úspěšně smazána a dokumenty byly bezpečně převedeny do náhradních kategorií.\n\n" +
            "Chcete nyní spustit celkovou reindexaci všech dokumentů na pozadí?\n\n" +
            "UPOZORNĚNÍ: Při reindexaci AI znovu klasifikuje všechny soubory na základě nově definovaných kategorií a jejich popisů, což může změnit jejich přístupová práva."
          : "Konfigurace byla úspěšně uložena a existující dokumenty byly bezpečně rekonfigurovány.\n\n" +
            "Chcete nyní spustit celkovou reindexaci všech dokumentů na pozadí?\n\n" +
            "UPOZORNĚNÍ: Při reindexaci AI znovu klasifikuje všechny soubory na základě nově definovaných kategorií a jejich popisů, což může změnit jejich přístupová práva.";

        const runReindex = confirm(promptMsg);
        if (runReindex) {
          try {
            setReindexProgress({
              status: "running",
              total_files: 0,
              processed_files: 0,
              current_file: null,
              phase: "clearing_db",
              error: null
            });
            setShowReindexModal(true);

            const reindexRes = await fetch(`${BACKEND_URL}/api/documents/reindex-all`, {
              method: "POST"
            });
            if (reindexRes.ok) {
              startPollingProgress();
            } else {
              setReindexProgress({
                status: "failed",
                total_files: 0,
                processed_files: 0,
                current_file: null,
                phase: null,
                error: "Spuštění znovunačtení selhalo na serveru."
              });
            }
          } catch (err) {
            console.error("Failed to trigger re-indexing", err);
            setReindexProgress({
              status: "failed",
              total_files: 0,
              processed_files: 0,
              current_file: null,
              phase: null,
              error: "Chyba při komunikaci se serverem: " + (err instanceof Error ? err.message : String(err))
            });
          }
        } else {
          alert("Změny byly uloženy. Seznam dokumentů byl aktualizován.");
        }
      } else {
        alert("Selhalo ukládání konfigurace.");
      }
    } catch (err) {
      console.error(err);
      alert("Chyba při připojování k serveru.");
    } finally {
      setSavingConfig(false);
    }
  };

  const handleConfirmCategoryDeletion = async () => {
    if (!editingConfig || deletingCatIndex === null) return;
    
    const catToDelete = editingConfig.categories[deletingCatIndex];
    const updatedCategories = editingConfig.categories.filter((_, idx) => idx !== deletingCatIndex);
    const updatedConfig = { ...editingConfig, categories: updatedCategories };
    
    const newMigrations = {
      ...categoryMigrations,
      [catToDelete.key]: migrationTargetKey
    };
    
    setCategoryMigrations({});
    setEditingConfig(updatedConfig);
    setShowMigrationModal(false);
    setDeletingCatIndex(null);
    
    await saveConfigToServer(updatedConfig, newMigrations, true);
  };

  const handleSaveConfig = async () => {
    if (!editingConfig) return;
    await saveConfigToServer(editingConfig, categoryMigrations, false);
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

  // Dynamic list of all category group names for suggestions in tag input
  const uniqueGroups = (editingConfig || config)
    ? Array.from(new Set(
        (editingConfig || config)!.categories
          .map(c => c.role_name || c.key)
          .filter(Boolean) as string[]
      ))
    : ["Management", "HR", "User"];

  return (
    <div className="flex flex-col flex-1 h-screen overflow-hidden bg-[#090d16] font-sans text-zinc-200">
      
      {/* 1. Global Navigation Header */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/[0.05] bg-[#0c1220]/80 backdrop-blur-md shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-cyan-500 text-white font-extrabold text-lg shadow-lg shadow-indigo-500/20">
            AI
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight text-white bg-clip-text bg-gradient-to-r from-white to-zinc-400">
              Firemní AI Vyhledávač
            </h1>
            <p className="text-xs text-zinc-500">
              Inteligentní vyhledávání v dokumentech Dolphin Consulting s citacemi
            </p>
          </div>
        </div>

        {/* Dynamic Tab Switcher */}
        <div className="flex rounded-lg p-0.5 bg-black/40 border border-white/[0.05]">
          <button
            type="button"
            onClick={() => setActiveTab("chat")}
            className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "chat"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/10"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            💬 Vyhledávání
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("ingest")}
            className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "ingest"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/10"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            📁 Editování/Přidání Souborů
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("config")}
            className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "config"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/10"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            ⚙️ Nastavení (Config)
          </button>
        </div>

        {/* Real-time system states */}
        <div className="flex items-center gap-6">
          {/* Dynamic Active User Role Selection (Switches permissions immediately) */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.02] border border-white/[0.05]">
            <span className="text-xs text-zinc-400 font-medium">Uživatel:</span>
            <select
              value={userRole}
              onChange={(e) => setUserRole(e.target.value)}
              className="bg-black/60 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
            >
              {config?.categories.map((cat) => (
                <option key={cat.key} value={cat.key.toLowerCase()}>
                  👑 {cat.label}
                </option>
              ))}
              {(!config || config.categories.length === 0) && (
                <>
                  <option value="management">👑 Vedení (Management)</option>
                  <option value="hr">💼 Personální (HR Specialist)</option>
                  <option value="finance">📊 Finanční (Finance Auditor)</option>
                  <option value="user">👤 Zaměstnanec (Standard User)</option>
                </>
              )}
            </select>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.05] text-xs">
            <span className={`pulse-dot ${apiOnline === false ? "bg-red-500 shadow-red-500/50" : ""}`} />
            <span className="text-zinc-300 font-medium font-mono">
              {apiOnline === null ? "Připojování..." : apiOnline ? "API: Online" : "API: Odpojeno"}
            </span>
          </div>
        </div>
      </header>

      {/* 2. Main Workspace Layout Grid */}
      <div className="flex flex-1 overflow-hidden">
        
        {/* Left Sidebar: Live Ingested Documents List */}
        <aside className="hidden lg:flex flex-col w-80 border-r border-white/[0.05] bg-[#070b13]/40 overflow-y-auto p-4 gap-4 shrink-0">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">
              Přístupné soubory
            </h3>
            <button 
              onClick={fetchDocuments}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold transition-colors flex items-center gap-1"
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
              {(() => {
                const filteredDocs = documents.filter((doc) => {
                  if (freshnessFilter === "latest") {
                    return doc.freshness_status === "current";
                  }
                  if (freshnessFilter === "this_year") {
                    const docDate = doc.metadata_json?.created_at || doc.created_at || "";
                    return docDate.startsWith("2026");
                  }
                  return true;
                });
                if (filteredDocs.length === 0) {
                  return (
                    <div className="text-center py-8 text-xs text-zinc-500 border border-dashed border-white/5 rounded-xl">
                      Žádné soubory neodpovídají filtru.
                    </div>
                  );
                }
                return filteredDocs.map((doc) => (
                  <div 
                    key={doc.document_id}
                    className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] transition-all hover:bg-white/[0.04] flex flex-col gap-1.5"
                  >
                    <div className="flex items-start gap-1">
                      <a
                        href={`${BACKEND_URL}/api/documents/view/${doc.document_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs font-bold text-zinc-300 hover:text-indigo-400 hover:underline truncate block flex-1"
                        title={`Kliknutím otevřete PDF: ${doc.title}`}
                      >
                        📄 {doc.title}
                      </a>
                    </div>

                    {/* Resolved Category Label */}
                    <div className="text-[9px] text-indigo-400 font-semibold uppercase flex items-center gap-1">
                      <span>📁</span>
                      <span>{getCategoryLabel(doc.metadata_json?.department)}</span>
                    </div>

                    <div className="flex items-center justify-between text-[10px] text-zinc-500">
                      <span className="font-medium font-mono">{doc.chunk_count} pasáží</span>
                      <span className={`px-1.5 py-0.5 rounded border uppercase font-extrabold text-[8px] tracking-wider ${
                        doc.freshness_status === "current"
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                          : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                      }`}>
                        {doc.freshness_status === "current" ? "Platný" : "Archiv"}
                      </span>
                    </div>

                    {/* Allowed security groups (ACL badges) */}
                    {doc.security_acl?.allowed_groups && doc.security_acl.allowed_groups.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {doc.security_acl.allowed_groups.map((g: string) => (
                          <span key={g} className="px-1.5 py-0.5 bg-zinc-800 text-[8px] text-zinc-400 rounded border border-white/[0.03] font-mono leading-none">
                            {g}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Relationship Badges */}
                    {doc.metadata_json?.replaces_document_title && (
                      <div className="text-[9px] text-amber-500 font-medium flex items-center gap-1 mt-0.5">
                        <span>🔄 Nahrazuje:</span>
                        <span className="truncate block max-w-[170px]" title={doc.metadata_json.replaces_document_title}>
                          {doc.metadata_json.replaces_document_title}
                        </span>
                      </div>
                    )}
                    {doc.metadata_json?.replaced_by_document_title && (
                      <div className="text-[9px] text-zinc-500 font-medium flex items-center gap-1 mt-0.5">
                        <span>⬇️ Nahrazen:</span>
                        <span className="truncate block max-w-[170px]" title={doc.metadata_json.replaced_by_document_title}>
                          {doc.metadata_json.replaced_by_document_title}
                        </span>
                      </div>
                    )}
                    {doc.metadata_json?.modifies_document_title && (
                      <div className="text-[9px] text-cyan-500 font-medium flex items-center gap-1 mt-0.5">
                        <span>✏️ Upravuje:</span>
                        <span className="truncate block max-w-[170px]" title={doc.metadata_json.modifies_document_title}>
                          {doc.metadata_json.modifies_document_title}
                        </span>
                      </div>
                    )}

                    <div className="flex flex-col gap-0.5 text-[9px] text-zinc-600 font-medium border-t border-white/[0.03] pt-1">
                      {doc.created_at && (
                        <div>Vydáno: {formatReleaseDate(doc.created_at)}</div>
                      )}
                    </div>

                    {activeTab === "ingest" && (
                      <button
                        type="button"
                        onClick={() => handleStartEditDoc(doc)}
                        className="text-[10px] text-indigo-400 hover:text-indigo-300 font-bold flex items-center gap-1 mt-1.5 bg-indigo-500/10 hover:bg-indigo-500/20 px-2 py-1 rounded-md self-start transition-all cursor-pointer"
                      >
                        ✏️ Upravit metadata
                      </button>
                    )}
                  </div>
                ));
              })()}
            </div>
          )}
        </aside>

        {/* 3. Render content depending on activeTab */}
        {activeTab === "chat" && (
          <>
            {/* Center Section: Conversational Search */}
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
                  <span className="text-xs text-zinc-400 font-medium">Platnost:</span>
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
                    <div className={`flex items-center justify-center w-8 h-8 rounded-lg text-xs font-bold shrink-0 ${
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
                        <div className="flex items-center gap-3 px-2 text-[10px] text-zinc-500 font-semibold font-mono">
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
                    <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-900/50 text-indigo-300 border border-indigo-500/20 text-xs font-bold animate-pulse">
                      AI
                    </div>
                    <div className="flex flex-col gap-2">
                      <div className="glass-panel p-4 rounded-2xl rounded-tl-none border-white/[0.03]">
                        <div className="flex items-center gap-3">
                          <div className="flex gap-1">
                            <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                            <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                            <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "300ms" }} />
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
                    placeholder="Zadejte dotaz (např. 'Jaká jsou pravidla pro whistleblowing?')..."
                    className="flex-1 px-4 py-3 rounded-xl bg-black/40 border border-white/[0.06] text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all"
                    disabled={loading}
                  />
                  <button
                    type="submit"
                    disabled={loading || !query.trim()}
                    className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-sm transition-all shadow-lg shadow-indigo-600/25 disabled:opacity-50 disabled:cursor-not-allowed hover:translate-y-[-1px] active:translate-y-[0px]"
                  >
                    Vyhledat
                  </button>
                </form>
                <div className="text-[10px] text-center text-zinc-600 mt-2 font-medium">
                  Podporováno hybridním retrievrem RRF (pgvector + full-text search)
                </div>
              </div>

            </main>

            {/* Right Sidebar: Citations drawer */}
            <aside className={`fixed inset-y-0 right-0 z-50 flex flex-col w-[450px] border-l border-white/[0.08] bg-[#0c1222] shadow-2xl transition-all duration-300 transform ${
              workspaceOpen ? "translate-x-0" : "translate-x-full"
            } lg:relative lg:translate-x-0 lg:z-0 shrink-0`}>
              
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

              <div className="flex-1 overflow-y-auto p-5 space-y-5">
                {activeSource ? (
                  <div className="space-y-4">
                    
                    {/* Source Document Section */}
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
                          title={activeSource.page_number ? `Kliknutím otevřete PDF na straně ${activeSource.page_number}` : "Kliknutím otevřete celý PDF dokument"}
                        >
                          📄 {activeSource.title} {activeSource.page_number ? `(strana ${activeSource.page_number})` : ""}
                        </a>
                      </h4>
                      <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                        <div>
                          <span className="text-zinc-500 block text-[10px]">Číslo strany</span>
                          <span className="font-semibold text-zinc-300 font-mono">Strana {activeSource.page_number || "N/A"}</span>
                        </div>
                        <div>
                          <span className="text-zinc-500 block text-[10px]">Kapitola / Sekce</span>
                          <span className="font-semibold text-zinc-300 truncate block" title={activeSource.section_title || "Několik sekcí"}>
                            {activeSource.section_title || "Hlavní text"}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Cited Passage */}
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

                    {/* Security Metrics */}
                    <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.04] space-y-3">
                      <span className="text-[9px] font-bold text-emerald-400 tracking-wider uppercase block">
                        Bezpečnost a auditovatelnost
                      </span>
                      
                      <div className="space-y-2 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-zinc-500">Stav platnosti:</span>
                          <span className={`px-2 py-0.5 rounded text-[10px] border font-bold uppercase tracking-wide ${
                            activeSource.freshness_status === "current"
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                              : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                          }`}>
                            {activeSource.freshness_status === "current" ? "Platný" : "Archivováno"}
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
                            {activeSource.allowed_groups && activeSource.allowed_groups.length > 0 ? (
                              activeSource.allowed_groups.map((group, idx) => (
                                <span 
                                  key={idx} 
                                  className="px-2 py-0.5 rounded bg-zinc-800 border border-white/5 text-[10px] text-zinc-300 font-semibold"
                                >
                                  {group}
                                </span>
                              ))
                            ) : (
                              <span className="px-2 py-0.5 rounded bg-zinc-800 border border-white/5 text-[10px] text-zinc-300">
                                Management
                              </span>
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
                      <p className="text-[10px] text-zinc-600 mt-1 max-w-[250px] mx-auto leading-relaxed">
                        Klikněte na libovolnou citaci <span className="citation-badge">📄 Zdroj X</span> v odpovědi asistenta pro zobrazení podrobných informací a zobrazení celého dokumentu.
                      </p>
                    </div>
                  </div>
                )}
              </div>

            </aside>
          </>
        )}

        {activeTab === "ingest" && (
          <div className="flex-1 overflow-y-auto p-6 bg-[#090d16] flex justify-center">
            {/* Ingestion drag & drop with review form */}
            <div className="glass-panel p-6 flex flex-col gap-6 w-full max-w-3xl self-start border-white/[0.04]">
              <div>
                <h2 className="text-md font-bold text-white flex items-center gap-2">
                  <span>{editingDocId ? "✏️" : "📤"}</span> {editingDocId ? "Upravit metadata dokumentu" : "Nahrát a otagovat nový dokument"}
                </h2>
                <p className="text-xs text-zinc-500 mt-1">
                  {editingDocId 
                    ? "Upravte název, datum vydání, kategorii a stav platnosti pro vybraný dokument."
                    : "Vložte PDF/TXT soubor. Umělá inteligence navrhne datum vydání, kategorii a vazby na archivní verze."}
                </p>
              </div>

              {/* Upload Drop Zone / Editing Banner */}
              {!fileToUpload && !editingDocId ? (
                <div
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`flex flex-col items-center justify-center py-12 px-6 border-2 border-dashed rounded-2xl cursor-pointer transition-all duration-200 text-center ${
                    isDragOver 
                      ? "border-indigo-500 bg-indigo-500/5 text-zinc-200" 
                      : "border-white/10 hover:border-white/20 bg-black/10 hover:bg-black/20 text-zinc-400"
                  }`}
                  onClick={() => document.getElementById("file-input-id")?.click()}
                >
                  <span className="text-3xl mb-3">📄</span>
                  <p className="text-sm font-semibold text-zinc-300">
                    Sem přetáhněte soubor směrnice
                  </p>
                  <p className="text-[10px] text-zinc-500 mt-1">
                    nebo klikněte pro vyhledání (PDF, TXT, max 20 MB)
                  </p>
                  <input
                    id="file-input-id"
                    type="file"
                    accept=".pdf,.txt"
                    onChange={handleFileChange}
                    className="hidden"
                  />
                </div>
              ) : fileToUpload ? (
                <div className="flex items-center justify-between p-4 bg-white/[0.02] border border-white/[0.05] rounded-xl">
                  <div className="flex items-center gap-2.5 truncate">
                    <span className="text-2xl shrink-0">📄</span>
                    <div className="truncate">
                      <p className="text-xs font-bold text-zinc-300 truncate">{fileToUpload.name}</p>
                      <p className="text-[10px] text-zinc-500 font-mono">{(fileToUpload.size / 1024).toFixed(1)} kB</p>
                    </div>
                  </div>
                  {!analyzingDraft && !ingestingConfirmed && (
                    <button
                      onClick={() => { setFileToUpload(null); setDraftResult(null); }}
                      className="text-zinc-500 hover:text-red-400 text-sm font-bold p-1"
                      title="Odebrat soubor"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-between p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-xl">
                  <div className="flex items-center gap-2.5 truncate">
                    <span className="text-2xl shrink-0">✏️</span>
                    <div className="truncate">
                      <p className="text-xs font-bold text-indigo-300 truncate">Režim úprav: {confirmedTitle}</p>
                      <p className="text-[10px] text-indigo-400 font-medium">Upravujete metadata existujícího dokumentu</p>
                    </div>
                  </div>
                  <button
                    onClick={() => { setEditingDocId(null); setIngestStatus(null); }}
                    className="text-zinc-400 hover:text-red-400 text-xs font-bold bg-white/5 hover:bg-white/10 px-2.5 py-1.5 rounded-xl transition-all cursor-pointer"
                  >
                    Zrušit úpravy
                  </button>
                </div>
              )}

              {/* Loader while LLM parses document draft */}
              {analyzingDraft && (
                <div className="flex flex-col items-center justify-center py-10 gap-3 border border-indigo-500/10 rounded-2xl bg-indigo-500/[0.01] animate-pulse">
                  <div className="flex gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                  <span className="text-xs text-indigo-400 font-bold">LLM analyzuje dokument (kategorie, data, vazby)...</span>
                </div>
              )}

              {/* Editable form for BOTH Ingest and Edit modes */}
              {(draftResult || editingDocId) && (
                <form onSubmit={editingDocId ? handleSaveDocEdit : handleConfirmIngest} className="space-y-4">
                  <div className="h-px bg-white/5 my-2" />
                  
                  <div className="space-y-1">
                    <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">Název směrnice</label>
                    <input
                      type="text"
                      value={confirmedTitle}
                      onChange={(e) => setConfirmedTitle(e.target.value)}
                      className="w-full bg-black/40 border border-white/[0.08] text-xs text-white rounded-xl px-3 py-2.5 focus:outline-none focus:border-indigo-500"
                      required
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1">
                      <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">Datum vydání</label>
                      <input
                        type="date"
                        value={confirmedDate}
                        onChange={(e) => setConfirmedDate(e.target.value)}
                        className="w-full bg-black/40 border border-white/[0.08] text-xs text-white rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500 font-mono"
                        required
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">Kategorie (Bezpečnostní ACL)</label>
                      <select
                        value={confirmedCategory}
                        onChange={(e) => setConfirmedCategory(e.target.value)}
                        className="w-full bg-black/60 border border-white/[0.08] text-xs text-white rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
                        required
                      >
                        <option value="">-- Vyberte kategorii --</option>
                        {config?.categories.map((cat) => (
                          <option key={cat.key} value={cat.key}>
                            {cat.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Freshness selection (Only for Editing Mode) */}
                  {editingDocId && (
                    <div className="space-y-1">
                      <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">Stav platnosti</label>
                      <select
                        value={confirmedFreshnessStatus}
                        onChange={(e) => setConfirmedFreshnessStatus(e.target.value as "current" | "archived")}
                        className="w-full bg-black/60 border border-white/[0.08] text-xs text-white rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
                      >
                        <option value="current">🟢 Platný (Current)</option>
                        <option value="archived">🟡 Archivovaný (Archived)</option>
                      </select>
                    </div>
                  )}

                  {/* Replacement / Modification relationships (Only for Ingestion Mode) */}
                  {!editingDocId && (
                    <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-3">
                      <span className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                        Vztah k ostatním dokumentům
                      </span>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-[10px] text-zinc-500 block">Typ vztahu</label>
                          <select
                            value={confirmedRelType}
                            onChange={(e) => setConfirmedRelType(e.target.value)}
                            className="w-full bg-black/60 border border-white/[0.08] text-xs text-zinc-300 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 font-medium cursor-pointer"
                          >
                            <option value="none">Nemá vztah</option>
                            <option value="replaces">🔄 Nahrazuje původní</option>
                            <option value="modifies">✏️ Upravuje / Doplňuje</option>
                          </select>
                        </div>

                        {confirmedRelType !== "none" && (
                          <div className="space-y-1">
                            <label className="text-[10px] text-zinc-500 block">Cílový dokument</label>
                            <select
                              value={confirmedRelTargetId}
                              onChange={(e) => setConfirmedRelTargetId(e.target.value)}
                              className="w-full bg-black/60 border border-white/[0.08] text-xs text-zinc-300 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 font-medium cursor-pointer"
                              required
                            >
                              <option value="">-- Vyberte dokument --</option>
                              {documents.map((doc) => (
                                <option key={doc.document_id} value={doc.document_id}>
                                  {doc.title}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}
                      </div>
                      
                      {confirmedRelType === "replaces" && (
                        <p className="text-[9px] text-amber-500 font-semibold leading-relaxed">
                          ⚠️ Upozornění: Po dokončení bude cílový dokument automaticky označen jako 'archivní' (včetně jeho vyhledávacích pasáží) a bude ve výchozím nastavení skryt z vyhledávání.
                        </p>
                      )}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={ingestingConfirmed}
                    className="w-full py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-all shadow-lg shadow-indigo-600/20 disabled:opacity-50 disabled:cursor-not-allowed hover:translate-y-[-1px] active:translate-y-[0px] flex items-center justify-center gap-2 cursor-pointer"
                  >
                    {ingestingConfirmed ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Zpracovávám změny...
                      </>
                    ) : (
                      editingDocId ? "Uložit změny" : "Potvrdit metadata a naimportovat"
                    )}
                  </button>
                </form>
              )}

              {/* Status Alert logs */}
              {ingestStatus && (
                <div className={`p-4 rounded-xl border text-xs leading-relaxed ${
                  ingestStatus.type === "success" 
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" 
                    : "bg-red-500/10 text-red-400 border-red-500/20"
                }`}>
                  <p className="font-bold mb-1">{ingestStatus.type === "success" ? "✓ Úspěch:" : "❌ Chyba:"}</p>
                  <p>{ingestStatus.message}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "config" && (
          <div className="flex-1 overflow-y-auto p-6 bg-[#090d16] flex justify-center">
            {/* Right Box: Dynamic categories configuration manager */}
            <div className="glass-panel p-6 flex flex-col gap-6 w-full max-w-3xl self-start border-white/[0.04]">
              <div>
                <h2 className="text-md font-bold text-white flex items-center gap-2">
                  <span>⚙️</span> Konfigurace kategorií a AI pravidel
                </h2>
                <p className="text-xs text-zinc-500 mt-1">
                  Měňte názvy kategorií, popisy pro LLM klasifikátor a bezpečnostní role. Změna se projeví v celé aplikaci.
                </p>
              </div>

              {editingConfig ? (
                <div className="space-y-5">
                  <div className="space-y-3">
                    <span className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                      Seznam kategorií (Readjustuje celou aplikaci)
                    </span>

                    {editingConfig.categories.map((cat, idx) => (
                      <div 
                        key={cat.key}
                        className="p-4 rounded-xl bg-white/[0.01] border border-white/[0.04] space-y-3 relative"
                      >
                        <button
                          type="button"
                          onClick={() => handleDeleteCategory(idx)}
                          className="absolute top-3 right-3 text-zinc-500 hover:text-red-400 text-[10px] font-bold transition-all p-1.5 px-2.5 rounded bg-red-500/0 hover:bg-red-500/10 border border-transparent hover:border-red-500/10 cursor-pointer flex items-center gap-1"
                          title="Odebrat kategorii"
                        >
                          🗑️ Odebrat
                        </button>
                        <div className="grid grid-cols-3 gap-3">
                          <div>
                            <span className="text-[10px] text-zinc-600 block">Klíč (ID)</span>
                            <span className="text-xs font-mono font-bold text-zinc-500 block truncate" title={cat.key}>{cat.key}</span>
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-500 block">Název (Štítek)</label>
                            <input
                              type="text"
                              value={cat.label}
                              onChange={(e) => handleCategoryFieldChange(idx, "label", e.target.value)}
                              className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 focus:outline-none focus:border-indigo-500"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-zinc-500 block">Skupina (role_name)</label>
                            <input
                              type="text"
                              value={cat.role_name || ""}
                              onChange={(e) => handleCategoryFieldChange(idx, "role_name", e.target.value)}
                              placeholder="e.g. HR"
                              className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 focus:outline-none focus:border-indigo-500"
                            />
                          </div>
                        </div>

                        <div className="space-y-1">
                          <label className="text-[10px] text-zinc-500 block">Popis kategorie pro AI (Určuje chování LLM klasifikátoru)</label>
                          <textarea
                            value={cat.description}
                            onChange={(e) => handleCategoryFieldChange(idx, "description", e.target.value)}
                            className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-300 rounded px-2.5 py-1.5 h-14 resize-none focus:outline-none focus:border-indigo-500 leading-normal"
                          />
                        </div>

                        <div className="space-y-1">
                          <label className="text-[10px] text-zinc-500 block">Bezpečnostní skupiny (Pills pro ACL)</label>
                          <CategoryTagInput
                            allowedGroups={cat.allowed_groups}
                            onChange={(groups) => handleAllowedGroupsChange(idx, groups)}
                            suggestions={uniqueGroups}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Add Category Button */}
                  <div className="flex justify-start">
                    <button
                      type="button"
                      onClick={handleAddCategory}
                      className="px-4 py-2.5 rounded-xl border border-dashed border-zinc-800 hover:border-indigo-500 text-xs font-bold text-zinc-400 hover:text-indigo-400 bg-white/[0.01] hover:bg-indigo-500/5 transition-all flex items-center gap-1.5 cursor-pointer"
                    >
                      ➕ Přidat novou kategorii
                    </button>
                  </div>

                  {/* General LLM Analysis Rules */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                      Obecná pravidla pro analýzu dokumentů
                    </label>
                    <textarea
                      value={editingConfig.analysis_rules}
                      onChange={(e) => handleRulesChange(e.target.value)}
                      className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-300 rounded px-3 py-2.5 h-20 resize-none focus:outline-none focus:border-indigo-500 leading-normal"
                    />
                  </div>

                  <button
                    onClick={handleSaveConfig}
                    disabled={savingConfig}
                    className="w-full py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs transition-all shadow-lg shadow-cyan-600/10 disabled:opacity-50"
                  >
                    {savingConfig ? "Ukládám a rekonfiguruji..." : "Uložit konfiguraci a pravidla"}
                  </button>
                </div>
              ) : (
                <div className="text-xs text-zinc-500 text-center py-6">
                  Načítám konfigurační soubory...
                </div>
              )}
            </div>
          </div>
        )}

      </div>

      {/* Dynamic Category Migration Modal */}
      {showMigrationModal && deletingCatIndex !== null && editingConfig && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="glass-panel max-w-md w-full p-6 space-y-4 border-white/[0.08] shadow-2xl bg-[#0c1222]">
            <div>
              <h3 className="text-md font-bold text-white flex items-center gap-2">
                <span>⚠️</span> Převod dokumentů před smazáním
              </h3>
              <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                Chystáte se smazat kategorii <span className="font-bold text-indigo-400">"{editingConfig.categories[deletingCatIndex]?.label}"</span>.
                V databázi mohou existovat dokumenty spojené s touto kategorií. 
              </p>
              <p className="text-[11px] text-amber-500 font-semibold mt-2 leading-relaxed">
                Z bezpečnostních důvodů vyberte, do které zbývající kategorie se mají tyto dokumenty bezpečně převést, aby se zabránilo jejich zneveřejnění (úniku dat do veřejné zóny):
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                Cílová kategorie pro dokumenty
              </label>
              <select
                value={migrationTargetKey}
                onChange={(e) => setMigrationTargetKey(e.target.value)}
                className="w-full bg-[#090d16] border border-white/[0.08] text-xs text-white rounded-xl px-3 py-2.5 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
              >
                {editingConfig.categories
                  .filter((_, idx) => idx !== deletingCatIndex)
                  .map((cat) => (
                    <option key={cat.key} value={cat.key}>
                      {cat.label} ({cat.role_name || "bez role"})
                    </option>
                  ))}
              </select>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setShowMigrationModal(false);
                  setDeletingCatIndex(null);
                }}
                className="flex-1 py-2.5 rounded-xl border border-white/[0.08] text-zinc-400 hover:text-white hover:bg-white/5 text-xs font-bold transition-all cursor-pointer text-center"
              >
                Zrušit
              </button>
              <button
                type="button"
                onClick={handleConfirmCategoryDeletion}
                className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition-all cursor-pointer text-center"
              >
                Potvrdit a převést
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Dynamic Re-indexing Progress Modal */}
      {showReindexModal && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-fadeIn">
          <div className="glass-panel max-w-md w-full p-6 space-y-5 border-white/[0.08] shadow-2xl bg-[#0c1222]">
            <div className="text-center space-y-2">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-indigo-500/10 text-indigo-400 mb-1">
                {reindexProgress?.status === "running" && (
                  <svg className="animate-spin h-5 w-5 text-indigo-400" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                )}
                {reindexProgress?.status === "completed" && (
                  <span className="text-xl text-emerald-400">✓</span>
                )}
                {reindexProgress?.status === "failed" && (
                  <span className="text-xl text-red-400">✕</span>
                )}
              </div>
              <h3 className="text-md font-extrabold text-white tracking-wide">
                {reindexProgress?.status === "running" && "Probíhá reindexace dokumentů"}
                {reindexProgress?.status === "completed" && "Reindexace úspěšně dokončena"}
                {reindexProgress?.status === "failed" && "Reindexace selhala"}
              </h3>
              <p className="text-[11px] text-zinc-400 leading-relaxed max-w-xs mx-auto">
                Během reindexace dochází k pročištění databáze a novému spárování a ohodnocení všech dokumentů dle upravených pravidel.
              </p>
            </div>

            {/* Progress Bar Container */}
            <div className="space-y-2">
              <div className="flex justify-between text-[11px] font-semibold">
                <span className="text-indigo-400">
                  {reindexProgress?.status === "running" && (
                    reindexProgress.phase === "clearing_db" ? "Pročišťování starých záznamů..." :
                    reindexProgress.phase === "scanning_files" ? "Hledání souborů..." :
                    reindexProgress.phase === "analyzing" ? "Fáze 1/2: Analýza metadat (AI)..." :
                    reindexProgress.phase === "ingesting" ? "Fáze 2/2: Ingestování a tvorba embeddingů..." :
                    "Pracuji..."
                  )}
                  {reindexProgress?.status === "completed" && "Všechny dokumenty byly úspěšně reindexovány."}
                  {reindexProgress?.status === "failed" && "Během zpracování nastala chyba."}
                </span>
                <span className="text-indigo-300 font-bold">{getReindexPercentage()}%</span>
              </div>

              <div className="w-full h-2.5 rounded-full bg-white/[0.03] border border-white/[0.05] overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ease-out ${
                    reindexProgress?.status === "failed" 
                      ? "bg-red-600 shadow-[0_0_10px_rgba(220,38,38,0.4)]" 
                      : reindexProgress?.status === "completed"
                      ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]"
                      : "bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 shadow-[0_0_10px_rgba(99,102,241,0.4)] animate-pulse"
                  }`}
                  style={{ width: `${getReindexPercentage()}%` }}
                />
              </div>

              {/* Detail info */}
              {reindexProgress?.status === "running" && reindexProgress.total_files > 0 && (
                <div className="rounded-xl bg-black/40 border border-white/[0.05] p-3 text-[11px] font-semibold text-zinc-300 space-y-1 mt-2">
                  <div className="text-[9px] text-zinc-500 font-extrabold uppercase tracking-wider">
                    {reindexProgress.phase === "analyzing" ? "Analýza metadat a vztahů" : "Indexace obsahu"}
                  </div>
                  {reindexProgress.current_file && (
                    <div className="truncate text-white text-[11px]">
                      📁 {reindexProgress.current_file}
                    </div>
                  )}
                  <div className="text-indigo-400 text-[10px]">
                    Soubor {Math.min(reindexProgress.processed_files + 1, reindexProgress.total_files)} z {reindexProgress.total_files}
                  </div>
                </div>
              )}

              {reindexProgress?.status === "failed" && reindexProgress.error && (
                <div className="rounded-xl bg-red-950/20 border border-red-500/20 p-3 text-[11px] text-red-400 font-semibold leading-relaxed mt-2">
                  <div className="text-[9px] font-extrabold uppercase tracking-wider text-red-500 mb-1">
                    Chybová zpráva
                  </div>
                  {reindexProgress.error}
                </div>
              )}
            </div>

            {/* Close/Action buttons */}
            {(reindexProgress?.status === "completed" || reindexProgress?.status === "failed") && (
              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowReindexModal(false);
                    setReindexProgress(null);
                  }}
                  className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer text-center ${
                    reindexProgress?.status === "failed"
                      ? "bg-red-600 hover:bg-red-500 text-white"
                      : "bg-indigo-600 hover:bg-indigo-500 text-white"
                  }`}
                >
                  Zavřít
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
