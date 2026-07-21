"use client";

import { useState, useEffect, useRef, useMemo } from "react";

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

interface SearchConfig {
  search_strategy: "hybrid" | "vector" | "keyword";
  hybrid_strategy: "rrf" | "score_addition" | "union";
  vector_weight: number;
  keyword_weight: number;
  rrf_k: number;
  vector_limit: number;
  keyword_limit: number;
  final_limit: number;
  vector_final_limit: number;
  keyword_final_limit: number;
  score_threshold: number;
  freshness_boost: number;
  context_expansion: "none" | "siblings" | "page" | "section";
  context_expansion_size: number;
  context_max_tokens: number;
  chunk_size: number;
  chunk_overlap: number;
  chunk_cross_page: boolean;
  chunk_splitter_type: "recursive" | "character";
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
  suggestions = ["Management", "HR", "Finance", "User"],
  locale = "cs"
}: {
  allowedGroups: string[];
  onChange: (groups: string[]) => void;
  suggestions?: string[];
  locale?: "cs" | "en";
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
          placeholder={allowedGroups.length === 0 ? (locale === "cs" ? "Přidejte skupinu (stiskněte Enter)..." : "Add group (press Enter)...") : ""}
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
              {locale === "cs" ? "➕ Přidat" : "➕ Add"} {g}
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
                {locale === "cs" ? `✨ Vytvořit "${inputValue.trim()}"` : `✨ Create "${inputValue.trim()}"`}
              </button>
            )}
        </div>
      )}
    </div>
  );
}

const TRANSLATIONS = {
  cs: {
    title: "Firemní AI Vyhledávač",
    subtitle: "Inteligentní vyhledávání v dokumentech Dolphin Consulting s citacemi",
    searchTab: "💬 Vyhledávání",
    ingestTab: "📁 Správa souborů",
    categoriesTab: "📂 Kategorie",
    configTab: "⚙️ Konfigurace vyhledávání",
    chunkingTab: "🧩 Chunkování",
    userLabel: "Uživatel:",
    apiOnline: "API ONLINE",
    apiOffline: "API OFFLINE",
    databaseTitle: "Databáze směrnic",
    databaseSubtitle: "Přehled nahraných firemních dokumentů",
    loadingDb: "Načítám databázi...",
    noFiles: "Žádné soubory v databázi.",
    noFilesSub: "Pro zvolenou roli nejsou dostupné žádné dokumenty.",
    noFilesFilter: "Žádné soubory neodpovídají filtru.",
    passages: "pasáží",
    valid: "Platný",
    archived: "Archiv",
    replaces: "Nahrazuje:",
    replacedBy: "Nahrazen:",
    modifies: "Upravuje:",
    created: "Vytvořeno:",
    ingested: "Načteno:",
    reindexBtn: "🔄 Přestavět celou DB",
    reindexing: "Přestavuji...",
    searchPlaceholder: "Zadejte dotaz (např. 'Jaká jsou pravidla pro whistleblowing?')...",
    searchBtn: "Vyhledat",
    searching: "Vyhledávám v Azure PostgreSQL (filtry: {userRole}, {freshnessFilter}) a generuji odpověď...",
    poweredBy: "Podporováno hybridním retrievrem RRF (pgvector + full-text search)",
    citationsTitle: "Pracovní prostor citací",
    citationsSubtitle: "Ověření groundedness a audit přístupu",
    activeSourceTitle: "Aktivní zdroj",
    activeSourcePlaceholder: "Klikněte na jakékoli číslo citace v odpovědi výše pro zobrazení zdrojového textu a ověření jeho obsahu v pravém panelu.",
    allowedGroups: "Povolené skupiny (ACL)",
    metadataHeader: "Metadata a audit",
    checksum: "Kontrolní součet SHA-256",
    replacesTitle: "Nahrazuje dokument",
    modifiesTitle: "Upravuje dokument",
    replacedByTitle: "Nahrazen dokumentem",
    freshnessLabel: "Stav platnosti",
    validityRange: "Období platnosti",
    validFrom: "Platnost od:",
    validTo: "Platnost do:",
    ingestHeader: "Nahrát a otagovat nový dokument",
    editHeader: "Upravit metadata dokumentu",
    dropzoneText: "Přetáhněte sem PDF nebo DOCX dokument, nebo klikněte pro výběr",
    dropzoneSub: "LLM automaticky zanalyzuje obsah a navrhne datum, kategorii a vazby",
    selectedFile: "Vybraný soubor:",
    cancelBtn: "Zrušit",
    docNameLabel: "Název směrnice",
    releaseDateLabel: "Datum vydání",
    categoryLabel: "Kategorie (Bezpečnostní ACL)",
    docLanguageLabel: "Jazyk dokumentu",
    docLanguageCS: "🇨🇿 Čeština",
    docLanguageEN: "🇬🇧 English",
    relationshipsLabel: "Vztah k ostatním dokumentům",
    relationshipType: "Typ vztahu",
    relNone: "Žádný - zcela nová směrnice",
    relReplaces: "Nahrazuje starší směrnici (původní bude archivována)",
    relModifies: "Upravuje/doplňuje stávající směrnici (obě zůstanou platné)",
    targetDocLabel: "Cílový dokument z databáze",
    confirmIngestBtn: "Potvrdit a uložit do databáze",
    saveChangesBtn: "Uložit změny",
    ingesting: "Ukládám do databáze a generuji embeddings...",
    saving: "Ukládám změny...",
    configurationTitle: "Konfigurace kategorií a AI pravidel",
    configurationSubtitle: "Měňte názvy kategorií, popisy pro LLM klasifikátor a bezpečnostní role. Změna se projeví v celé aplikaci.",
    searchConfigTitle: "Konfigurace vyhledávání a RAG",
    searchConfigSubtitle: "Upravujte chování hybridního vyhledávače, váhy, RRF konstanty, thresholdy a rozšiřování kontextu.",
    searchStrategyLabel: "Výchozí strategie vyhledávání",
    hybridStrategyLabel: "Metoda hybridního slučování",
    vectorWeightLabel: "Váha sémantického vyhledávání (Vektor)",
    keywordWeightLabel: "Váha textového vyhledávání (FTS)",
    vectorLimitLabel: "Limit kandidátů z DB (Vektor)",
    keywordLimitLabel: "Limit kandidátů z DB (FTS)",
    finalLimitLabel: "Finální počet výsledků k LLM",
    thresholdLabel: "Práh shody (Score Threshold)",
    boostLabel: "Zvýhodnění čerstvosti (Freshness Boost)",
    expansionLabel: "Rozšíření kontextu (Parent-Child)",
    expansionNone: "Žádné (Vypnuto)",
    expansionSiblings: "Sousední pasáže (Siblings)",
    expansionPage: "Celá stránka (Page)",
    expansionSection: "Celá sekce (Section)",
    expansionSizeLabel: "Počet sousedních chunků (N)",
    addCategoryBtn: "➕ Přidat novou kategorii",
    saveConfigBtn: "Uložit konfiguraci a pravidla",
    savingConfig: "Ukládám...",
    analysisRulesLabel: "Pravidla pro LLM analýzu a auto-tagování",
    analysisRulesSub: "Tyto instrukce řídí chování AI při rozřazování nově nahraných dokumentů.",
    activeFilters: "Aktivní filtry",
    adjustFiltersBtn: "Nastavení hledání",
    all: "Vše",
    searchMethodLabel: "Metoda hledání",
    freshnessFilterLabel: "Časová platnost",
    docLanguageFilterLabel: "Jazyk dokumentů",
    strategyHybrid: "Hybridní (RRF)",
    strategyVector: "Sémantická (Vector)",
    strategyKeyword: "Lexikální (FTS)",
    freshnessAll: "Všechny",
    freshnessThisYear: "Jen 2026",
    freshnessLatest: "Jen platné",
    langFilterAll: "Všechny jazyky",
    langFilterCS: "Čeština",
    langFilterEN: "English",
    sourceFilterLabel: "Zdroj dat",
    sourceFilterAll: "Všechny zdroje",

    // New keys
    accessibleFiles: "Přístupné soubory",
    refreshBtn: "Obnovit",
    refreshTooltip: "Obnovit seznam souborů",
    releasedLabel: "Vydáno:",
    editMetadataBtn: "Upravit metadata",
    sourceDocHeader: "Zdrojový dokument (Kliknutím otevřete)",
    pageNumberLabel: "Číslo strany",
    chapterSectionLabel: "Kapitola / Sekce",
    mainTextLabel: "Hlavní text",
    citedPassageLabel: "Citovaná pasáž",
    securityAuditLabel: "Bezpečnost a auditovatelnost",
    rrfScoreLabel: "RRF Shoda (Fused score):",
    securityAclLabel: "Povolené skupiny (Security ACL):",
    emptyWorkspaceTitle: "Prázdný pracovní prostor",
    emptyWorkspaceDesc: "Klikněte na libovolnou citaci 📄 Zdroj X v odpovědi asistenta pro zobrazení podrobných informací a zobrazení celého dokumentu.",
    closePanelTitle: "Zavřít panel",
    clickToOpenPdf: "Kliknutím otevřete PDF na straně {page}",
    clickToOpenEntire: "Kliknutím otevřete celý PDF dokument",
    pageLabel: "strana",
    pageLabelCapitalized: "Strana",
    editModeBanner: "Režim úprav:",
    editModeSub: "Upravujete metadata existujícího dokumentu",
    cancelEditBtn: "Zrušit úpravy",
    dropzoneDragText: "Sem přetáhněte soubor směrnice",
    dropzoneBrowseText: "nebo klikněte pro vyhledání (PDF, TXT, max 20 MB)",
    removeFileTitle: "Odebrat soubor",
    selectCategoryPlaceholder: "-- Vyberte kategorii --",
    selectDocumentPlaceholder: "-- Vyberte dokument --",
    relationshipNoneOption: "Nemá vztah",
    relationshipReplacesOption: "🔄 Nahrazuje původní",
    relationshipModifiesOption: "✏️ Upravuje / Doplňuje",
    relationshipWarning: "⚠️ Upozornění: Po dokončení bude cílový dokument automaticky označen jako 'archivní' (včetně jeho vyhledávacích pasáží) a bude ve výchozím nastavení skryt z vyhledávání.",
    processingChangesText: "Zpracovávám změny...",
    categoriesListLabel: "Seznam kategorií (Readjustuje celou aplikaci)",
    deleteBtn: "Odebrat",
    keyLabel: "Klíč (ID)",
    labelLabel: "Název (Štítek)",
    roleNameLabel: "Skupina (role_name)",
    categoryDescriptionLabel: "Popis kategorie pro AI (Určuje chování LLM klasifikátoru)",
    securityGroupsLabel: "Bezpečnostní skupiny (Pills pro ACL)",
    generalRulesLabel: "Obecná pravidla pro analýzu dokumentů",
    savingConfigText: "Uklám a rekonfiguruji...",
    loadingConfigText: "Načítám konfigurační soubory...",
    noRoleLabel: "bez role",
    migrationModalTitle: "Převod dokumentů před smazáním",
    migrationModalDesc: "Chystáte se smazat kategorii",
    migrationSafetyWarn: "Z bezpečnostních důvodů vyberte, do které zbývající kategorie se mají tyto dokumenty bezpečně převést, aby se zabránilo jejich zneveřejnění (úniku dat do veřejné zóny):",
    migrationTargetLabel: "Cílová kategorie pro dokumenty",
    confirmAndTransferBtn: "Potvrdit a převést",
    reindexProgressTitle: "Probíhá reindexace dokumentů",
    reindexSuccessTitle: "Reindexace úspěšně dokončena",
    reindexFailedTitle: "Reindexace selhala",
    reindexProgressDesc: "Během reindexace dochází k pročištění databáze a novému spárování a ohodnocení všech dokumentů dle upravených pravidel.",
    reindexProgressDescFast: "Chunky všech dokumentů jsou přerozdělovány a přeceňovány podle nových parametrů bez změny metadat.",
    reindexPhaseClearing: "Pročišťování starých záznamů...",
    reindexPhaseScanning: "Hledání souborů...",
    reindexPhaseAnalyzing: "Fáze 1/2: Analýza metadat (AI)...",
    reindexPhaseIngesting: "Fáze 2/2: Ingestování a tvorba embeddingů...",
    reindexPhaseIngestingFast: "Přepočítávání chunků a embeddingů...",
    reindexPhaseWorking: "Pracuji...",
    reindexSuccessMsg: "Všechny dokumenty byly úspěšně reindexovány.",
    reindexErrorMsg: "Během zpracování nastala chyba.",
    reindexSubphaseAnalyzing: "Analýza metadat a vztahů",
    reindexSubphaseIngesting: "Indexace obsahu",
    reindexProgressFile: "Soubor {current} z {total}",
    errorMessageTitle: "Chybová zpráva",
    closeBtn: "Zavřít",
    reindexPromptDeletion: "Kategorie byla úspěšně smazána a dokumenty byly bezpečně převedeny do náhradních kategorií.\n\nChcete nyní spustit celkovou reindexaci všech dokumentů na pozadí?\n\nUPOZORNĚNÍ: Při reindexaci AI znovu klasifikuje všechny soubory na základě nově definovaných kategorií a jejich popisů, což může změnit jejich přístupová práva.",
    reindexPromptUpdate: "Konfigurace byla úspěšně uložena a existující dokumenty byly bezpečně rekonfigurovány.\n\nChcete nyní spustit celkovou reindexaci všech dokumentů na pozadí?\n\nUPOZORNĚNÍ: Při reindexaci AI znovu klasifikuje všechny soubory na základě nově definovaných kategorií a jejich popisů, což může změnit jejich přístupová práva.",
    apiConnecting: "Připojování...",
    errorServerCommunication: "Chyba při komunikaci se serverem: {error}. Ujistěte se, že Váš FastAPI server běží na portu 8000.",
    alertOnlyPdfTxt: "Podporovány jsou pouze soubory PDF a TXT.",
    errorDraftAnalysis: "Chyba při analýze dokumentu: {error}",
    errorIngestFailed: "Chyba při dokončení importu: {error}",
    errorEditFailed: "Úprava selhala: {status} ({detail})",
    errorSaveFailed: "Chyba při ukládání změn: {error}",
    alertAtLeastOneCategory: "Musíte ponechat alespoň jednu kategorii.",
    errorReindexingTrigger: "Spuštění znovunačtení selhalo na serveru.",
    errorReindexingComm: "Chyba při komunikaci se serverem: {error}",
    alertChangesSaved: "Změny byly uloženy. Seznam dokumentů byl aktualizován.",
    alertSaveConfigFailed: "Selhalo ukládání konfigurace.",
    alertServerConnError: "Chyba při připojování k serveru.",
    roleVedení: "👑 Vedení (Management)",
    rolePersonální: "💼 Personální (HR Specialist)",
    roleFinanční: "📊 Finanční (Finance Auditor)",
    roleZaměstnanec: "👤 Zaměstnanec (Standard User)",
    newCategoryLabel: "Nová kategorie",
    newCategoryDesc: "Popis této kategorie pro LLM klasifikátor.",
    initialGreeting: "Dobrý den! Jsem Váš firemní vyhledávací asistent. Zadejte libovolný dotaz a já vyhledám odpověď v nahraných směrnicích a dokumentech Dolphin Consulting. Odpověď bude podložená citacemi a přizpůsobí se Vašim přístupovým právům.",
    clickToOpenPdfTitle: "Kliknutím otevřete PDF: {title}",
    multipleSections: "Několik sekcí",
  },
  en: {
    title: "Corporate AI Search",
    subtitle: "Intelligent search in Dolphin Consulting documents with citations",
    searchTab: "💬 Search",
    ingestTab: "📁 File Management",
    categoriesTab: "📂 Categories",
    configTab: "⚙️ Search Settings",
    chunkingTab: "🧩 Chunking",
    userLabel: "User:",
    apiOnline: "API ONLINE",
    apiOffline: "API OFFLINE",
    databaseTitle: "Policies Database",
    databaseSubtitle: "Overview of uploaded corporate documents",
    loadingDb: "Loading database...",
    noFiles: "No files in database.",
    noFilesSub: "No documents available for the selected role.",
    noFilesFilter: "No files match the active filters.",
    passages: "passages",
    valid: "Active",
    archived: "Archived",
    replaces: "Replaces:",
    replacedBy: "Replaced by:",
    modifies: "Modifies:",
    created: "Created:",
    ingested: "Ingested:",
    reindexBtn: "🔄 Rebuild entire DB",
    reindexing: "Reindexing...",
    searchPlaceholder: "Enter your query (e.g. 'What are the rules for whistleblowing?')...",
    searchBtn: "Search",
    searching: "Searching in Azure PostgreSQL (filters: {userRole}, {freshnessFilter}) and generating response...",
    poweredBy: "Powered by Weighted RRF hybrid retriever (pgvector + full-text search)",
    citationsTitle: "Citations Workspace",
    citationsSubtitle: "Groundedness validation and access auditing",
    activeSourceTitle: "Active Source",
    activeSourcePlaceholder: "Click any citation bracket in the AI response above to inspect the source text and verify its contents in this panel.",
    allowedGroups: "Allowed Groups (ACL)",
    metadataHeader: "Metadata & Auditing",
    checksum: "SHA-256 Checksum",
    replacesTitle: "Replaces Document",
    modifiesTitle: "Modifies Document",
    replacedByTitle: "Replaced by Document",
    freshnessLabel: "Validity Status",
    validityRange: "Validity Period",
    validFrom: "Valid From:",
    validTo: "Valid To:",
    ingestHeader: "Upload and Tag New Document",
    editHeader: "Edit Document Metadata",
    dropzoneText: "Drag and drop a PDF or DOCX file here, or click to browse",
    dropzoneSub: "LLM will automatically extract the date, category, and document relations",
    selectedFile: "Selected file:",
    cancelBtn: "Cancel",
    docNameLabel: "Document Title",
    releaseDateLabel: "Release Date",
    categoryLabel: "Category (Security ACL)",
    docLanguageLabel: "Document Language",
    docLanguageCS: "🇨🇿 Czech",
    docLanguageEN: "🇬🇧 English",
    relationshipsLabel: "Relation to Other Documents",
    relationshipType: "Relation Type",
    relNone: "None - completely new policy",
    relReplaces: "Replaces an older policy (the original will be archived)",
    relModifies: "Modifies/extends an existing policy (both will remain active)",
    targetDocLabel: "Target Document in Database",
    confirmIngestBtn: "Confirm & Ingest to Database",
    saveChangesBtn: "Save Changes",
    ingesting: "Ingesting to database and generating embeddings...",
    saving: "Saving changes...",
    configurationTitle: "AI Search Settings",
    configurationSubtitle: "Manage categories and configuration rules for LLM metadata tagging",
    searchConfigTitle: "Search & RAG Configuration",
    searchConfigSubtitle: "Tune hybrid search strategies, weights, RRF constants, thresholds, and context expansions.",
    searchStrategyLabel: "Default Search Strategy",
    hybridStrategyLabel: "Hybrid Fusion Strategy",
    vectorWeightLabel: "Semantic Search Weight (Vector)",
    keywordWeightLabel: "Lexical Search Weight (FTS)",
    vectorLimitLabel: "DB Candidate Limit (Vector)",
    keywordLimitLabel: "DB Candidate Limit (FTS)",
    finalLimitLabel: "Final Results to LLM",
    thresholdLabel: "Score Threshold",
    boostLabel: "Freshness Boost",
    expansionLabel: "Context Expansion (Parent-Child)",
    expansionNone: "None (Disabled)",
    expansionSiblings: "Sibling Chunks",
    expansionPage: "Entire Page",
    expansionSection: "Entire Section",
    expansionSizeLabel: "Sibling Window Size (N)",
    addCategoryBtn: "➕ Add Category",
    saveConfigBtn: "Save Configuration",
    savingConfig: "Saving...",
    analysisRulesLabel: "Rules for LLM Analysis & Auto-tagging",
    analysisRulesSub: "These instructions steer the AI's behavior when analyzing new document uploads.",
    activeFilters: "Active Filters",
    adjustFiltersBtn: "Search Settings",
    all: "All",
    searchMethodLabel: "Search Method",
    freshnessFilterLabel: "Time Validity",
    docLanguageFilterLabel: "Doc Language",
    strategyHybrid: "Hybrid (RRF)",
    strategyVector: "Semantic (Vector)",
    strategyKeyword: "Lexical (FTS)",
    freshnessAll: "All",
    freshnessThisYear: "Only 2026",
    freshnessLatest: "Only Active",
    langFilterAll: "All languages",
    langFilterCS: "Czech",
    langFilterEN: "English",
    sourceFilterLabel: "Data Source",
    sourceFilterAll: "All sources",

    // New keys
    accessibleFiles: "Accessible Files",
    refreshBtn: "Refresh",
    refreshTooltip: "Refresh files list",
    releasedLabel: "Released:",
    editMetadataBtn: "Edit Metadata",
    sourceDocHeader: "Source Document (Click to open)",
    pageNumberLabel: "Page Number",
    chapterSectionLabel: "Chapter / Section",
    mainTextLabel: "Main Text",
    citedPassageLabel: "Cited Passage",
    securityAuditLabel: "Security & Auditability",
    rrfScoreLabel: "RRF Score (Fused score):",
    securityAclLabel: "Allowed Groups (Security ACL):",
    emptyWorkspaceTitle: "Empty Workspace",
    emptyWorkspaceDesc: "Click any 📄 Source X citation badge in the AI assistant's response to view detailed information and read the full document.",
    closePanelTitle: "Close Panel",
    clickToOpenPdf: "Click to open PDF on page {page}",
    clickToOpenEntire: "Click to open entire PDF document",
    pageLabel: "page",
    pageLabelCapitalized: "Page",
    editModeBanner: "Edit Mode:",
    editModeSub: "You are editing metadata of an existing document",
    cancelEditBtn: "Cancel Editing",
    dropzoneDragText: "Drop policy file here",
    dropzoneBrowseText: "or click to browse (PDF, TXT, max 20 MB)",
    removeFileTitle: "Remove File",
    selectCategoryPlaceholder: "-- Select Category --",
    selectDocumentPlaceholder: "-- Select Document --",
    relationshipNoneOption: "None",
    relationshipReplacesOption: "🔄 Replaces original",
    relationshipModifiesOption: "✏️ Modifies / Extends",
    relationshipWarning: "⚠️ Note: Once saved, the target document will automatically be marked as 'archived' (including its search passages) and will be hidden from default searches.",
    processingChangesText: "Processing changes...",
    categoriesListLabel: "Categories List (Readjusts entire application)",
    deleteBtn: "Remove",
    keyLabel: "Key (ID)",
    labelLabel: "Name (Label)",
    roleNameLabel: "Group (role_name)",
    categoryDescriptionLabel: "Category description for AI (Guides the LLM classifier)",
    securityGroupsLabel: "Security groups (Pills for ACL)",
    generalRulesLabel: "General rules for document analysis",
    savingConfigText: "Saving and reconfiguring...",
    loadingConfigText: "Loading configuration files...",
    noRoleLabel: "no role",
    migrationModalTitle: "Transfer Documents Before Deletion",
    migrationModalDesc: "You are about to delete category",
    migrationSafetyWarn: "For safety reasons, choose which remaining category to securely transfer these documents to, avoiding accidental disclosure (data leakage to public zones):",
    migrationTargetLabel: "Target category for documents",
    confirmAndTransferBtn: "Confirm & Transfer",
    reindexProgressTitle: "Document Re-indexing In Progress",
    reindexSuccessTitle: "Re-indexing Completed Successfully",
    reindexFailedTitle: "Re-indexing Failed",
    reindexProgressDesc: "During re-indexing, the database is cleared, and all documents are re-paired and scored according to the updated rules.",
    reindexProgressDescFast: "All document chunks are being re-segmented and re-embedded according to new parameters without metadata changes.",
    reindexPhaseClearing: "Clearing old records...",
    reindexPhaseScanning: "Scanning files...",
    reindexPhaseAnalyzing: "Phase 1/2: Metadata analysis (AI)...",
    reindexPhaseIngesting: "Phase 2/2: Ingesting and embedding...",
    reindexPhaseIngestingFast: "Re-chunking and generating embeddings...",
    reindexPhaseWorking: "Working...",
    reindexSuccessMsg: "All documents were successfully re-indexed.",
    reindexErrorMsg: "An error occurred during processing.",
    reindexSubphaseAnalyzing: "Metadata and relationship analysis",
    reindexSubphaseIngesting: "Content indexing",
    reindexProgressFile: "File {current} of {total}",
    errorMessageTitle: "Error Message",
    closeBtn: "Close",
    reindexPromptDeletion: "The category was successfully deleted and documents were safely transferred.\n\nDo you want to trigger a full document re-indexing on the background now?\n\nWARNING: The AI will re-classify all files based on the newly defined categories and descriptions, which may alter their access rights.",
    reindexPromptUpdate: "Configuration saved successfully and existing documents were safely reconfigured.\n\nDo you want to trigger a full document re-indexing on the background now?\n\nWARNING: The AI will re-classify all files based on the newly defined categories and descriptions, which may alter their access rights.",
    apiConnecting: "Connecting...",
    errorServerCommunication: "Error communicating with server: {error}. Make sure your FastAPI server is running on port 8000.",
    alertOnlyPdfTxt: "Only PDF and TXT files are supported.",
    errorDraftAnalysis: "Error analyzing document: {error}",
    errorIngestFailed: "Error completing import: {error}",
    errorEditFailed: "Editing failed: {status} ({detail})",
    errorSaveFailed: "Error saving changes: {error}",
    alertAtLeastOneCategory: "You must keep at least one category.",
    errorReindexingTrigger: "Triggering reindexing failed on the server.",
    errorReindexingComm: "Error communicating with server: {error}",
    alertChangesSaved: "Changes saved. File list updated.",
    alertSaveConfigFailed: "Failed to save configuration.",
    alertServerConnError: "Error connecting to the server.",
    roleVedení: "👑 Management",
    rolePersonální: "💼 HR Specialist",
    roleFinanční: "📊 Finance Auditor",
    roleZaměstnanec: "👤 Standard User",
    newCategoryLabel: "New category",
    newCategoryDesc: "Description of this category for the LLM classifier.",
    initialGreeting: "Hello! I am your corporate search assistant. Enter any query and I will find the answer in the uploaded Dolphin Consulting policies and documents. The answer will be supported by citations and matches your access permissions.",
    clickToOpenPdfTitle: "Click to open PDF: {title}",
    multipleSections: "Multiple sections",
  }
};

// Helper to find the longest overlapping text suffix of the previous chunk matching the prefix of the current chunk
const findOverlapText = (prevText: string, currentText: string, maxOverlap: number = 1000): string => {
  if (!prevText || !currentText) return "";
  const limit = Math.min(prevText.length, currentText.length, maxOverlap);
  for (let len = limit; len > 0; len--) {
    const suffix = prevText.slice(-len);
    if (currentText.startsWith(suffix)) {
      return suffix;
    }
  }
  return "";
};

export default function Home() {
  // Application Navigation
  const [activeTab, setActiveTab] = useState<"chat" | "ingest" | "categories" | "config" | "chunking">("chat");

  // Dynamic Categories and Config
  const [config, setConfig] = useState<Config | null>(null);
  const [editingConfig, setEditingConfig] = useState<Config | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);

  // Dynamic Search Configuration
  const [searchConfig, setSearchConfig] = useState<SearchConfig | null>(null);
  const [editingSearchConfig, setEditingSearchConfig] = useState<SearchConfig | null>(null);
  const [savingSearchConfig, setSavingSearchConfig] = useState(false);

  // Category migrations state (keeps track of where to migrate documents of deleted categories)
  const [categoryMigrations, setCategoryMigrations] = useState<Record<string, string>>({});
  const [showMigrationModal, setShowMigrationModal] = useState(false);
  const [deletingCatIndex, setDeletingCatIndex] = useState<number | null>(null);
  const [migrationTargetKey, setMigrationTargetKey] = useState<string>("");

  // Document Chunks Preview Modal State
  const [chunkPreviewDocTitle, setChunkPreviewDocTitle] = useState<string | null>(null);
  const [chunkPreviewDocId, setChunkPreviewDocId] = useState<string | null>(null);
  const [chunkPreviewList, setChunkPreviewList] = useState<any[] | null>(null);
  const [loadingChunks, setLoadingChunks] = useState<boolean>(false);

  const fetchAndShowChunks = async (docId: string, title: string) => {
    setChunkPreviewDocTitle(title);
    setChunkPreviewDocId(docId);
    setLoadingChunks(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/documents/${docId}/chunks`);
      if (res.ok) {
        const data = await res.json();
        setChunkPreviewList(data);
      } else {
        alert(appLanguage === "cs" ? "Nepodařilo se načíst chunky dokumentu." : "Failed to load document chunks.");
      }
    } catch (err) {
      console.error(err);
      alert(appLanguage === "cs" ? "Chyba při komunikaci se serverem." : "Error communicating with server.");
    } finally {
      setLoadingChunks(false);
    }
  };

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
      content: TRANSLATIONS.cs.initialGreeting,
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

  // Multi-lingual & Language Filter States
  const [appLanguage, setAppLanguage] = useState<"cs" | "en">("cs");
  const [documentLanguageFilter, setDocumentLanguageFilter] = useState<"all" | "cs" | "en">("all");
  const [sourceFolderFilter, setSourceFolderFilter] = useState<string>("all");
  
  // Dynamically compute the set of unique source folders from loaded documents
  const uniqueSourceFolders = useMemo(() => {
    const folders = new Set<string>();
    documents.forEach((doc) => {
      const folder = doc.metadata_json?.source_folder || doc.metadata_json?.["Zdroj dat"];
      if (folder) {
        folders.add(folder);
      }
    });
    return Array.from(folders).sort();
  }, [documents]);

  const [confirmedLanguage, setConfirmedLanguage] = useState<string>("cs");
  const [searchSettingsOpen, setSearchSettingsOpen] = useState<boolean>(false);

  // Chat message container ref for auto-scrolling
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Backend API URL Base
  const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  // Live Chunking Preview State
  const [selectedPreviewDocId, setSelectedPreviewDocId] = useState<string>("");
  const [previewChunks, setPreviewChunks] = useState<any[]>([]);
  const [loadingPreviewChunks, setLoadingPreviewChunks] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    if (activeTab === "chunking" && documents.length > 0 && !selectedPreviewDocId) {
      setSelectedPreviewDocId(documents[0].document_id);
    }
  }, [activeTab, documents, selectedPreviewDocId]);

  useEffect(() => {
    if (!selectedPreviewDocId || !editingSearchConfig) {
      setPreviewChunks([]);
      return;
    }

    const delayDebounceFn = setTimeout(async () => {
      setLoadingPreviewChunks(true);
      setPreviewError(null);
      try {
        const res = await fetch(`${BACKEND_URL}/api/documents/preview-chunks`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            document_id: selectedPreviewDocId,
            chunk_size: editingSearchConfig.chunk_size,
            chunk_overlap: editingSearchConfig.chunk_overlap,
            chunk_cross_page: editingSearchConfig.chunk_cross_page,
            chunk_splitter_type: editingSearchConfig.chunk_splitter_type,
          }),
        });

        if (res.ok) {
          const data = await res.json();
          setPreviewChunks(data);
        } else {
          const errData = await res.json().catch(() => ({}));
          setPreviewError(errData.detail || "Failed to load preview chunks.");
        }
      } catch (err) {
        console.error(err);
        setPreviewError("Network error loading preview chunks.");
      } finally {
        setLoadingPreviewChunks(false);
      }
    }, 450);

    return () => clearTimeout(delayDebounceFn);
  }, [
    selectedPreviewDocId,
    editingSearchConfig?.chunk_size,
    editingSearchConfig?.chunk_overlap,
    editingSearchConfig?.chunk_cross_page,
    editingSearchConfig?.chunk_splitter_type,
    activeTab
  ]);

  // Re-indexing progress state
  const [showReindexModal, setShowReindexModal] = useState(false);
  const [reindexProgress, setReindexProgress] = useState<{
    status: "idle" | "running" | "completed" | "failed";
    type?: "reindex_fast" | "reindex_full";
    total_files: number;
    processed_files: number;
    current_file: string | null;
    phase: "clearing_db" | "scanning_files" | "scanning" | "analyzing" | "ingesting" | null;
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
    const fallback = appLanguage === "cs" ? "Obecné" : "General";
    if (!catKey || !config?.categories) return fallback;
    const cat = config.categories.find((c) => c.key === catKey);
    return cat ? cat.label : fallback;
  };

  // Helper to format date in Czech style
  const formatReleaseDate = (dateStr?: string) => {
    if (!dateStr) return null;
    try {
      return new Date(dateStr).toLocaleDateString(appLanguage === "cs" ? "cs-CZ" : "en-US");
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

  // Fetch dynamic search retrieval configuration
  const fetchSearchConfig = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/config`);
      if (res.ok) {
        const data = await res.json();
        setSearchConfig(data);
        setEditingSearchConfig(data);
        if (data.search_strategy) {
          setSearchStrategy(data.search_strategy);
        }
      }
    } catch (err) {
      console.error("Failed to fetch search config", err);
    }
  };

  const saveSearchConfigToServer = async (updatedSearchConfig: SearchConfig) => {
    setSavingSearchConfig(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/chat/config`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(updatedSearchConfig),
      });

      if (res.ok) {
        setSearchConfig(updatedSearchConfig);
        setEditingSearchConfig(updatedSearchConfig);
        if (updatedSearchConfig.search_strategy) {
          setSearchStrategy(updatedSearchConfig.search_strategy);
        }
        alert(appLanguage === "cs" ? "Konfigurace vyhledávání byla úspěšně uložena." : "Search configuration saved successfully.");
      } else {
        alert(appLanguage === "cs" ? "Chyba při ukládání konfigurace vyhledávání." : "Failed to save search configuration.");
      }
    } catch (err) {
      console.error("Error saving search config", err);
      alert(appLanguage === "cs" ? "Chyba připojení k serveru." : "Error connecting to the server.");
    } finally {
      setSavingSearchConfig(false);
    }
  };

  const startReindexing = async (
    endpoint: "reindex-all" | "reindex-full",
    initialPhase: "clearing_db" | "scanning_files" | "scanning" | "analyzing" | "ingesting" | null
  ) => {
    try {
      setReindexProgress({
        status: "running",
        type: endpoint === "reindex-all" ? "reindex_fast" : "reindex_full",
        total_files: 0,
        processed_files: 0,
        current_file: null,
        phase: initialPhase,
        error: null
      });
      setShowReindexModal(true);

      const res = await fetch(`${BACKEND_URL}/api/documents/${endpoint}`, {
        method: "POST"
      });
      if (res.ok) {
        startPollingProgress();
      } else {
        setReindexProgress({
          status: "failed",
          type: endpoint === "reindex-all" ? "reindex_fast" : "reindex_full",
          total_files: 0,
          processed_files: 0,
          current_file: null,
          phase: null,
          error: TRANSLATIONS[appLanguage].errorReindexingTrigger
        });
      }
    } catch (err) {
      console.error(`Failed to trigger re-indexing on ${endpoint}`, err);
      setReindexProgress({
        status: "failed",
        type: endpoint === "reindex-all" ? "reindex_fast" : "reindex_full",
        total_files: 0,
        processed_files: 0,
        current_file: null,
        phase: null,
        error: TRANSLATIONS[appLanguage].errorReindexingComm.replace("{error}", String(err instanceof Error ? err.message : err))
      });
    }
  };

  const renderContentWithHighlights = (text?: string) => {
    if (!text) return null;
    if (!text.includes("\[\[MATCH_START\]\]")) {
      return <span>{text}</span>;
    }
    const parts = text.split(/(\[\[MATCH_START\]\]|\[\[MATCH_END\]\])/g);
    let isMatch = false;
    return parts.map((part, i) => {
      if (part === "[[MATCH_START]]") {
        isMatch = true;
        return null;
      }
      if (part === "[[MATCH_END]]") {
        isMatch = false;
        return null;
      }
      if (isMatch) {
        return (
          <span key={i} className="text-zinc-200 bg-indigo-500/10 border-l-2 border-indigo-500 pl-3.5 py-2 my-2.5 block rounded-r leading-relaxed font-mono font-bold">
            {part}
          </span>
        );
      }
      return (
        <span key={i} className="text-zinc-500 opacity-60 block leading-relaxed font-mono my-1 font-normal">
          {part}
        </span>
      );
    });
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
    fetchSearchConfig();
    
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

  // Update greeting message when appLanguage changes
  useEffect(() => {
    if (messages.length <= 1) {
      setMessages([
        {
          role: "assistant",
          content: TRANSLATIONS[appLanguage].initialGreeting,
        }
      ]);
    }
  }, [appLanguage]);

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
          locale: appLanguage,
          search_strategy: searchStrategy,
          freshness_filter: freshnessFilter,
          filters: {
            ...(documentLanguageFilter !== "all" ? { language: documentLanguageFilter } : {}),
            ...(sourceFolderFilter !== "all" ? { source_folder: sourceFolderFilter } : {}),
          },
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
        content: TRANSLATIONS[appLanguage].errorServerCommunication.replace("{error}", String(err.message || err)),
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
        alert(TRANSLATIONS[appLanguage].alertOnlyPdfTxt);
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
        throw new Error(appLanguage === "cs" ? `Analýza konceptu selhala: ${res.status}` : `Draft analysis failed: ${res.status}`);
      }

      const data = await res.json();
      setDraftResult(data);
      
      // Seed editable form with suggested values
      setConfirmedTitle(data.title);
      setConfirmedDate(data.suggested_date || new Date().toISOString().split("T")[0]);
      setConfirmedCategory(data.suggested_category);
      setConfirmedRelType(data.relationship.relationship_type);
      setConfirmedRelTargetId(data.relationship.target_document_id || "");
      setConfirmedLanguage(data.suggested_language || "cs");
    } catch (err: any) {
      console.error(err);
      setIngestStatus({
        type: "error",
        message: TRANSLATIONS[appLanguage].errorDraftAnalysis.replace("{error}", String(err.message || err)),
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
      language: confirmedLanguage,
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
        throw new Error(errData.detail || (appLanguage === "cs" ? `Ingest selhal: ${res.status}` : `Ingestion failed: ${res.status}`));
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
        message: TRANSLATIONS[appLanguage].errorIngestFailed.replace("{error}", String(err.message || err)),
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
      language: confirmedLanguage,
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
        throw new Error(errData.detail || TRANSLATIONS[appLanguage].errorEditFailed.replace("{status}", String(res.status)).replace("({detail})", "").trim());
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
        message: TRANSLATIONS[appLanguage].errorSaveFailed.replace("{error}", String(err.message || err)),
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
    setConfirmedLanguage(doc.language || "cs");
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
      label: TRANSLATIONS[appLanguage].newCategoryLabel,
      description: TRANSLATIONS[appLanguage].newCategoryDesc,
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
      alert(TRANSLATIONS[appLanguage].alertAtLeastOneCategory);
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
          ? TRANSLATIONS[appLanguage].reindexPromptDeletion
          : TRANSLATIONS[appLanguage].reindexPromptUpdate;

        const runReindex = confirm(promptMsg);
        if (runReindex) {
          startReindexing("reindex-full", "clearing_db");
        } else {
          alert(TRANSLATIONS[appLanguage].alertChangesSaved);
        }
      } else {
        alert(TRANSLATIONS[appLanguage].alertSaveConfigFailed);
      }
    } catch (err) {
      console.error(err);
      alert(TRANSLATIONS[appLanguage].alertServerConnError);
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
              {TRANSLATIONS[appLanguage].title}
            </h1>
            <p className="text-xs text-zinc-500">
              {TRANSLATIONS[appLanguage].subtitle}
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
            {TRANSLATIONS[appLanguage].searchTab}
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
            {TRANSLATIONS[appLanguage].ingestTab}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("categories")}
            className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "categories"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/10"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {TRANSLATIONS[appLanguage].categoriesTab}
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
            {TRANSLATIONS[appLanguage].configTab}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("chunking")}
            className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all ${
              activeTab === "chunking"
                ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/10"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {TRANSLATIONS[appLanguage].chunkingTab}
          </button>
        </div>

        {/* Real-time system states */}
        <div className="flex items-center gap-6">
          {/* Language Switcher */}
          <div className="flex items-center gap-1 px-2 py-1 rounded-xl bg-white/[0.02] border border-white/[0.05]">
            <button
              onClick={() => setAppLanguage("cs")}
              className={`px-2 py-0.5 rounded text-[10px] font-extrabold transition-all ${
                appLanguage === "cs"
                  ? "bg-indigo-600/30 text-indigo-400 border border-indigo-500/25"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              CZ
            </button>
            <button
              onClick={() => setAppLanguage("en")}
              className={`px-2 py-0.5 rounded text-[10px] font-extrabold transition-all ${
                appLanguage === "en"
                  ? "bg-indigo-600/30 text-indigo-400 border border-indigo-500/25"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              EN
            </button>
          </div>

          {/* Dynamic Active User Role Selection (Switches permissions immediately) */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.02] border border-white/[0.05]">
            <span className="text-xs text-zinc-400 font-medium">{TRANSLATIONS[appLanguage].userLabel}</span>
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
                  <option value="management">{TRANSLATIONS[appLanguage].roleVedení}</option>
                  <option value="hr">{TRANSLATIONS[appLanguage].rolePersonální}</option>
                  <option value="finance">{TRANSLATIONS[appLanguage].roleFinanční}</option>
                  <option value="user">{TRANSLATIONS[appLanguage].roleZaměstnanec}</option>
                </>
              )}
            </select>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.05] text-xs">
            <span className={`pulse-dot ${apiOnline === false ? "bg-red-500 shadow-red-500/50" : ""}`} />
            <span className="text-zinc-300 font-medium font-mono">
              {apiOnline === null ? TRANSLATIONS[appLanguage].apiConnecting : apiOnline ? "API: Online" : TRANSLATIONS[appLanguage].apiOffline}
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
              {TRANSLATIONS[appLanguage].accessibleFiles}
            </h3>
            <button 
              onClick={fetchDocuments}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-semibold transition-colors flex items-center gap-1"
              title={TRANSLATIONS[appLanguage].refreshTooltip}
            >
              🔄 {TRANSLATIONS[appLanguage].refreshBtn}
            </button>
          </div>

          {loadingDocs ? (
            <div className="flex flex-col gap-3 py-4 text-center text-xs text-zinc-500">
              {TRANSLATIONS[appLanguage].loadingDb}
            </div>
          ) : documents.length === 0 ? (
            <div className="flex flex-col gap-2 py-8 text-center text-xs text-zinc-500 border border-dashed border-white/5 rounded-xl">
              {TRANSLATIONS[appLanguage].noFiles}
              <span className="text-[10px] text-zinc-600">{TRANSLATIONS[appLanguage].noFilesSub}</span>
            </div>
          ) : (
            <div className="flex flex-col gap-2.5">
              {(() => {
                const filteredDocs = documents.filter((doc) => {
                  if (documentLanguageFilter !== "all" && doc.language !== documentLanguageFilter) {
                    return false;
                  }
                  if (sourceFolderFilter !== "all") {
                    const docFolder = doc.metadata_json?.source_folder || doc.metadata_json?.["Zdroj dat"];
                    if (docFolder !== sourceFolderFilter) {
                      return false;
                    }
                  }
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
                      {TRANSLATIONS[appLanguage].noFilesFilter}
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
                        title={TRANSLATIONS[appLanguage].clickToOpenPdfTitle.replace("{title}", doc.title)}
                      >
                        📄 {doc.title}
                      </a>
                    </div>

                    {/* Resolved Category Label */}
                    <div className="text-[9px] text-indigo-400 font-semibold uppercase flex items-center gap-1">
                      <span>📁</span>
                      <span>{getCategoryLabel(doc.metadata_json?.department)}</span>
                    </div>

                    {(doc.metadata_json?.source_folder || doc.metadata_json?.["Zdroj dat"]) && (
                      <div className="text-[9px] text-cyan-400 font-semibold uppercase flex items-center gap-1">
                        <span>📦</span>
                        <span>{TRANSLATIONS[appLanguage].sourceFilterLabel}: {doc.metadata_json.source_folder || doc.metadata_json["Zdroj dat"]}</span>
                      </div>
                    )}

                    <div className="flex items-center justify-between text-[10px] text-zinc-500">
                      <span className="font-medium font-mono">{doc.chunk_count} {TRANSLATIONS[appLanguage].passages}</span>
                      <div className="flex items-center gap-1.5">
                        <span className="px-1 py-0.5 rounded border uppercase font-bold text-[8px] bg-white/[0.03] text-zinc-400 border-white/[0.05]">
                          {doc.language === "cs" ? "CZ" : "EN"}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded border uppercase font-extrabold text-[8px] tracking-wider ${
                          doc.freshness_status === "current"
                            ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                            : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                        }`}>
                          {doc.freshness_status === "current" ? TRANSLATIONS[appLanguage].valid : TRANSLATIONS[appLanguage].archived}
                        </span>
                      </div>
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
                        <span>🔄 {TRANSLATIONS[appLanguage].replaces}</span>
                        <span className="truncate block max-w-[170px]" title={doc.metadata_json.replaces_document_title}>
                          {doc.metadata_json.replaces_document_title}
                        </span>
                      </div>
                    )}
                    {doc.metadata_json?.replaced_by_document_title && (
                      <div className="text-[9px] text-zinc-500 font-medium flex items-center gap-1 mt-0.5">
                        <span>⬇️ {TRANSLATIONS[appLanguage].replacedBy}</span>
                        <span className="truncate block max-w-[170px]" title={doc.metadata_json.replaced_by_document_title}>
                          {doc.metadata_json.replaced_by_document_title}
                        </span>
                      </div>
                    )}
                    {doc.metadata_json?.modifies_document_title && (
                      <div className="text-[9px] text-cyan-500 font-medium flex items-center gap-1 mt-0.5">
                        <span>✏️ {TRANSLATIONS[appLanguage].modifies}</span>
                        <span className="truncate block max-w-[170px]" title={doc.metadata_json.modifies_document_title}>
                          {doc.metadata_json.modifies_document_title}
                        </span>
                      </div>
                    )}

                    <div className="flex flex-col gap-0.5 text-[9px] text-zinc-600 font-medium border-t border-white/[0.03] pt-1">
                      {doc.created_at && (
                        <div>{TRANSLATIONS[appLanguage].releasedLabel} {formatReleaseDate(doc.created_at)}</div>
                      )}
                    </div>

                    {activeTab === "ingest" && (
                      <div className="flex gap-2 mt-1.5 flex-wrap">
                        <button
                          type="button"
                          onClick={() => handleStartEditDoc(doc)}
                          className="text-[10px] text-indigo-400 hover:text-indigo-300 font-bold flex items-center gap-1 bg-indigo-500/10 hover:bg-indigo-500/20 px-2 py-1 rounded-md transition-all cursor-pointer"
                        >
                          ✏️ {TRANSLATIONS[appLanguage].editMetadataBtn}
                        </button>
                        <button
                          type="button"
                          onClick={() => fetchAndShowChunks(doc.document_id, doc.title)}
                          className="text-[10px] text-cyan-400 hover:text-cyan-300 font-bold flex items-center gap-1 bg-cyan-500/10 hover:bg-cyan-500/20 px-2 py-1 rounded-md transition-all cursor-pointer"
                        >
                          🔍 {appLanguage === "cs" ? "Náhled chunků" : "Preview Chunks"}
                        </button>
                      </div>
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
              <div className="flex flex-col border-b border-white/[0.04] bg-[#0a0f1b]/50">
                <div className="flex items-center justify-between p-4 gap-4 flex-wrap">
                  <div className="flex items-center gap-2 flex-wrap text-xs text-zinc-400">
                    <span className="font-semibold uppercase tracking-wider text-[10px] text-zinc-500 mr-1">{TRANSLATIONS[appLanguage].activeFilters}:</span>
                    <span className="px-2.5 py-1 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
                      🔍 {searchStrategy === "hybrid" ? TRANSLATIONS[appLanguage].strategyHybrid : searchStrategy === "vector" ? TRANSLATIONS[appLanguage].strategyVector : TRANSLATIONS[appLanguage].strategyKeyword}
                    </span>
                    <span className="px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium">
                      📅 {freshnessFilter === "all" ? TRANSLATIONS[appLanguage].freshnessAll : freshnessFilter === "this_year" ? TRANSLATIONS[appLanguage].freshnessThisYear : freshnessFilter === "latest"}
                    </span>
                    <span className="px-2.5 py-1 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-medium">
                      🌐 {documentLanguageFilter === "all" ? TRANSLATIONS[appLanguage].langFilterAll : documentLanguageFilter === "cs" ? TRANSLATIONS[appLanguage].langFilterCS : TRANSLATIONS[appLanguage].langFilterEN}
                    </span>
                    {sourceFolderFilter !== "all" && (
                      <span className="px-2.5 py-1 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                        📦 {sourceFolderFilter}
                      </span>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => setSearchSettingsOpen(!searchSettingsOpen)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all hover:bg-white/[0.03] ${
                      searchSettingsOpen 
                        ? "bg-indigo-500/10 border-indigo-500/30 text-indigo-400" 
                        : "bg-white/[0.01] border-white/[0.05] text-zinc-300"
                    }`}
                  >
                    <span>🎛️</span>
                    <span>{TRANSLATIONS[appLanguage].adjustFiltersBtn}</span>
                    <span className={`text-[10px] transition-transform ${searchSettingsOpen ? "rotate-180" : ""}`}>▼</span>
                  </button>
                </div>

                {/* Collapsible Search Settings Panel */}
                {searchSettingsOpen && (
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-6 p-5 border-t border-white/[0.03] bg-black/30 backdrop-blur-md animate-fadeIn">
                    
                    {/* Strategy Column Info & Link */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                        {TRANSLATIONS[appLanguage].searchMethodLabel}
                      </label>
                      <div className="p-3 rounded-2xl bg-white/[0.01] border border-white/[0.04] space-y-2 flex flex-col justify-between min-h-[106px]">
                        <div className="text-[11px] text-zinc-300 font-semibold flex items-start gap-1.5 leading-relaxed">
                          <span className="text-sm">🧠</span>
                          <span>
                            {searchStrategy === "hybrid" && (searchConfig?.hybrid_strategy === "rrf" ? "Hybrid (RRF)" : searchConfig?.hybrid_strategy === "score_addition" ? "Hybrid (Score Addition)" : "Hybrid (Union)")}
                            {searchStrategy === "vector" && "Semantic (Vector)"}
                            {searchStrategy === "keyword" && "Lexical (FTS)"}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => setActiveTab("config")}
                          className="w-full text-center py-2 px-3 rounded-xl bg-indigo-600/10 hover:bg-indigo-600/20 border border-indigo-500/20 text-[10px] text-indigo-300 font-bold transition-all cursor-pointer"
                        >
                          ⚙️ {appLanguage === "cs" ? "Upravit v Nastavení" : "Configure in Settings"}
                        </button>
                      </div>
                    </div>

                    {/* Freshness Column */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-extrabold uppercase text-emerald-400 tracking-wider block">{TRANSLATIONS[appLanguage].freshnessFilterLabel}</label>
                      <div className="flex flex-col gap-1.5">
                        <button
                          type="button"
                          onClick={() => setFreshnessFilter("all")}
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                            freshnessFilter === "all"
                              ? "bg-emerald-600/15 border-emerald-500/40 text-emerald-300"
                              : "bg-black/30 border-white/[0.04] text-zinc-400 hover:bg-white/[0.01]"
                          }`}
                        >
                          🌍 {TRANSLATIONS[appLanguage].freshnessAll}
                        </button>
                        <button
                          type="button"
                          onClick={() => setFreshnessFilter("this_year")}
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                            freshnessFilter === "this_year"
                              ? "bg-emerald-600/15 border-emerald-500/40 text-emerald-300"
                              : "bg-black/30 border-white/[0.04] text-zinc-400 hover:bg-white/[0.01]"
                          }`}
                        >
                          📅 {TRANSLATIONS[appLanguage].freshnessThisYear}
                        </button>
                        <button
                          type="button"
                          onClick={() => setFreshnessFilter("latest")}
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                            freshnessFilter === "latest"
                              ? "bg-emerald-600/15 border-emerald-500/40 text-emerald-300"
                              : "bg-black/30 border-white/[0.04] text-zinc-400 hover:bg-white/[0.01]"
                          }`}
                        >
                          🟢 {TRANSLATIONS[appLanguage].freshnessLatest}
                        </button>
                      </div>
                    </div>

                    {/* Document Language Column */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-extrabold uppercase text-cyan-400 tracking-wider block">{TRANSLATIONS[appLanguage].docLanguageFilterLabel}</label>
                      <div className="flex flex-col gap-1.5">
                        <button
                          type="button"
                          onClick={() => setDocumentLanguageFilter("all")}
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                            documentLanguageFilter === "all"
                              ? "bg-cyan-600/15 border-cyan-500/40 text-cyan-300"
                              : "bg-black/30 border-white/[0.04] text-zinc-400 hover:bg-white/[0.01]"
                          }`}
                        >
                          🌍 {TRANSLATIONS[appLanguage].langFilterAll}
                        </button>
                        <button
                          type="button"
                          onClick={() => setDocumentLanguageFilter("cs")}
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                            documentLanguageFilter === "cs"
                              ? "bg-cyan-600/15 border-cyan-500/40 text-cyan-300"
                              : "bg-black/30 border-white/[0.04] text-zinc-400 hover:bg-white/[0.01]"
                          }`}
                        >
                          🇨🇿 {TRANSLATIONS[appLanguage].langFilterCS}
                        </button>
                        <button
                          type="button"
                          onClick={() => setDocumentLanguageFilter("en")}
                          className={`w-full text-left px-3 py-2 rounded-xl text-xs font-medium border transition-all ${
                            documentLanguageFilter === "en"
                              ? "bg-cyan-600/15 border-cyan-500/40 text-cyan-300"
                              : "bg-black/30 border-white/[0.04] text-zinc-400 hover:bg-white/[0.01]"
                          }`}
                        >
                          🇬🇧 {TRANSLATIONS[appLanguage].langFilterEN}
                        </button>
                      </div>
                    </div>

                    {/* Data Source Column */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-extrabold uppercase text-amber-400 tracking-wider block">
                        {TRANSLATIONS[appLanguage].sourceFilterLabel}
                      </label>
                      <div className="flex flex-col gap-1.5">
                        <select
                          value={sourceFolderFilter}
                          onChange={(e) => setSourceFolderFilter(e.target.value)}
                          className="w-full bg-black/60 border border-white/[0.08] text-xs text-zinc-300 rounded-xl px-3 py-2.5 focus:outline-none focus:border-amber-500 font-semibold cursor-pointer"
                        >
                          <option value="all" className="bg-[#0f172a] text-zinc-300">
                            📦 {TRANSLATIONS[appLanguage].sourceFilterAll}
                          </option>
                          {uniqueSourceFolders.map((folder) => (
                            <option key={folder} value={folder} className="bg-[#0f172a] text-zinc-300">
                              📁 {folder}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>

                  </div>
                )}
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
                          <span className="text-xs text-indigo-400 font-medium">
                            {TRANSLATIONS[appLanguage].searching.replace("{userRole}", userRole).replace("{freshnessFilter}", freshnessFilter)}
                          </span>
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
                    placeholder={TRANSLATIONS[appLanguage].searchPlaceholder}
                    className="flex-1 px-4 py-3 rounded-xl bg-black/40 border border-white/[0.06] text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 transition-all"
                    disabled={loading}
                  />
                  <button
                    type="submit"
                    disabled={loading || !query.trim()}
                    className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-sm transition-all shadow-lg shadow-indigo-600/25 disabled:opacity-50 disabled:cursor-not-allowed hover:translate-y-[-1px] active:translate-y-[0px]"
                  >
                    {TRANSLATIONS[appLanguage].searchBtn}
                  </button>
                </form>
                <div className="text-[10px] text-center text-zinc-600 mt-2 font-medium">
                  {TRANSLATIONS[appLanguage].poweredBy}
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
                    <h3 className="text-sm font-bold text-white">{TRANSLATIONS[appLanguage].citationsTitle}</h3>
                    <p className="text-[10px] text-zinc-500">{TRANSLATIONS[appLanguage].citationsSubtitle}</p>
                  </div>
                </div>
                <button
                  onClick={() => setWorkspaceOpen(false)}
                  className="lg:hidden text-zinc-400 hover:text-white text-lg transition-colors p-1"
                  title={TRANSLATIONS[appLanguage].closePanelTitle}
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
                        {TRANSLATIONS[appLanguage].sourceDocHeader}
                      </span>
                      <h4 className="text-sm font-bold text-white leading-snug">
                        <a
                          href={`${BACKEND_URL}/api/documents/view/${activeSource.document_id}${getSearchHash(activeSource)}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-white hover:text-indigo-400 hover:underline transition-colors block"
                          title={activeSource.page_number ? TRANSLATIONS[appLanguage].clickToOpenPdf.replace("{page}", String(activeSource.page_number)) : TRANSLATIONS[appLanguage].clickToOpenEntire}
                        >
                          📄 {activeSource.title} {activeSource.page_number ? `(${TRANSLATIONS[appLanguage].pageLabel} ${activeSource.page_number})` : ""}
                        </a>
                      </h4>
                      <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
                        <div>
                          <span className="text-zinc-500 block text-[10px]">{TRANSLATIONS[appLanguage].pageNumberLabel}</span>
                          <span className="font-semibold text-zinc-300 font-mono">{TRANSLATIONS[appLanguage].pageLabelCapitalized} {activeSource.page_number || "N/A"}</span>
                        </div>
                        <div>
                          <span className="text-zinc-500 block text-[10px]">{TRANSLATIONS[appLanguage].chapterSectionLabel}</span>
                          <span className="font-semibold text-zinc-300 truncate block" title={activeSource.section_title || TRANSLATIONS[appLanguage].multipleSections}>
                            {activeSource.section_title || TRANSLATIONS[appLanguage].mainTextLabel}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Cited Passage */}
                    <div className="p-4 rounded-2xl bg-white/[0.01] border border-white/[0.04] space-y-2">
                      <span className="text-[9px] font-bold text-cyan-400 tracking-wider uppercase block">
                        {TRANSLATIONS[appLanguage].citedPassageLabel}
                      </span>
                      <div className="highlight-chunk">
                        <div className="text-xs text-zinc-300 leading-relaxed font-mono">
                          {renderContentWithHighlights(activeSource.content)}
                        </div>
                      </div>
                    </div>

                    {/* Security Metrics */}
                    <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/[0.04] space-y-3">
                      <span className="text-[9px] font-bold text-emerald-400 tracking-wider uppercase block">
                        {TRANSLATIONS[appLanguage].securityAuditLabel}
                      </span>
                      
                      <div className="space-y-2 text-xs">
                        <div className="flex items-center justify-between">
                          <span className="text-zinc-500">{TRANSLATIONS[appLanguage].freshnessLabel}:</span>
                          <span className={`px-2 py-0.5 rounded text-[10px] border font-bold uppercase tracking-wide ${
                            activeSource.freshness_status === "current"
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                              : "bg-amber-500/10 text-amber-400 border-amber-500/20"
                          }`}>
                            {activeSource.freshness_status === "current" ? TRANSLATIONS[appLanguage].valid : TRANSLATIONS[appLanguage].archived}
                          </span>
                        </div>

                        <div className="flex items-center justify-between">
                          <span className="text-zinc-500">{TRANSLATIONS[appLanguage].rrfScoreLabel}</span>
                          <span className="font-mono text-zinc-300 font-semibold">{activeSource.score.toFixed(6)}</span>
                        </div>

                        <div className="w-full h-px bg-white/5 my-2" />

                        <div>
                          <span className="text-zinc-500 block mb-1">{TRANSLATIONS[appLanguage].securityAclLabel}</span>
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
                      <h4 className="text-xs font-bold text-zinc-500">{TRANSLATIONS[appLanguage].emptyWorkspaceTitle}</h4>
                      <p className="text-[10px] text-zinc-600 mt-1 max-w-[250px] mx-auto leading-relaxed">
                        {TRANSLATIONS[appLanguage].emptyWorkspaceDesc}
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
                  <span>{editingDocId ? "✏️" : "📤"}</span> {editingDocId ? TRANSLATIONS[appLanguage].editHeader : TRANSLATIONS[appLanguage].ingestHeader}
                </h2>
                <p className="text-xs text-zinc-500 mt-1">
                  {editingDocId 
                    ? (appLanguage === "cs" ? "Upravte název, datum vydání, kategorii a stav platnosti pro vybraný dokument." : "Edit the title, release date, category, and validity status for the selected document.")
                    : (appLanguage === "cs" ? "Vložte PDF/TXT soubor. Umělá inteligence navrhne datum vydání, kategorii a vazby na archivní verze." : "Insert a PDF/TXT file. AI will suggest release date, category, and relationships to archived versions.")}
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
                    {TRANSLATIONS[appLanguage].dropzoneDragText}
                  </p>
                  <p className="text-[10px] text-zinc-500 mt-1">
                    {TRANSLATIONS[appLanguage].dropzoneBrowseText}
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
                      title={TRANSLATIONS[appLanguage].removeFileTitle}
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
                      <p className="text-xs font-bold text-indigo-300 truncate">{TRANSLATIONS[appLanguage].editModeBanner} {confirmedTitle}</p>
                      <p className="text-[10px] text-indigo-400 font-medium">{TRANSLATIONS[appLanguage].editModeSub}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => { setEditingDocId(null); setIngestStatus(null); }}
                    className="text-zinc-400 hover:text-red-400 text-xs font-bold bg-white/5 hover:bg-white/10 px-2.5 py-1.5 rounded-xl transition-all cursor-pointer"
                  >
                    {TRANSLATIONS[appLanguage].cancelEditBtn}
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
                  <span className="text-xs text-indigo-400 font-bold">
                    {appLanguage === "cs" ? "LLM analyzuje dokument (kategorie, data, vazby)..." : "LLM is analyzing document (categories, dates, relationships)..."}
                  </span>
                </div>
              )}

              {/* Editable form for BOTH Ingest and Edit modes */}
              {(draftResult || editingDocId) && (
                <form onSubmit={editingDocId ? handleSaveDocEdit : handleConfirmIngest} className="space-y-4">
                  <div className="h-px bg-white/5 my-2" />
                  
                  <div className="space-y-1">
                    <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">{TRANSLATIONS[appLanguage].docNameLabel}</label>
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
                      <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">{TRANSLATIONS[appLanguage].releaseDateLabel}</label>
                      <input
                        type="date"
                        value={confirmedDate}
                        onChange={(e) => setConfirmedDate(e.target.value)}
                        className="w-full bg-black/40 border border-white/[0.08] text-xs text-white rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500 font-mono"
                        required
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">{TRANSLATIONS[appLanguage].categoryLabel}</label>
                      <select
                        value={confirmedCategory}
                        onChange={(e) => setConfirmedCategory(e.target.value)}
                        className="w-full bg-black/60 border border-white/[0.08] text-xs text-white rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
                        required
                      >
                        <option value="">{TRANSLATIONS[appLanguage].selectCategoryPlaceholder}</option>
                        {config?.categories.map((cat) => (
                          <option key={cat.key} value={cat.key}>
                            {cat.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Freshness & Language selections */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {editingDocId && (
                      <div className="space-y-1">
                        <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                          {TRANSLATIONS[appLanguage].freshnessLabel}
                        </label>
                        <select
                          value={confirmedFreshnessStatus}
                          onChange={(e) => setConfirmedFreshnessStatus(e.target.value as "current" | "archived")}
                          className="w-full bg-black/60 border border-white/[0.08] text-xs text-white rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
                        >
                          <option value="current">🟢 {TRANSLATIONS[appLanguage].valid} (Current)</option>
                          <option value="archived">🟡 {TRANSLATIONS[appLanguage].archived} (Archived)</option>
                        </select>
                      </div>
                    )}

                    <div className="space-y-1">
                      <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                        {TRANSLATIONS[appLanguage].docLanguageLabel}
                      </label>
                      <select
                        value={confirmedLanguage}
                        onChange={(e) => setConfirmedLanguage(e.target.value)}
                        className="w-full bg-black/60 border border-white/[0.08] text-xs text-white rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
                        required
                      >
                        <option value="cs">{TRANSLATIONS[appLanguage].docLanguageCS}</option>
                        <option value="en">{TRANSLATIONS[appLanguage].docLanguageEN}</option>
                      </select>
                    </div>
                  </div>

                  {/* Replacement / Modification relationships (Only for Ingestion Mode) */}
                  {!editingDocId && (
                    <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-3">
                      <span className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                        {TRANSLATIONS[appLanguage].relationshipsLabel}
                      </span>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-[10px] text-zinc-500 block">{TRANSLATIONS[appLanguage].relationshipType}</label>
                          <select
                            value={confirmedRelType}
                            onChange={(e) => setConfirmedRelType(e.target.value)}
                            className="w-full bg-black/60 border border-white/[0.08] text-xs text-zinc-300 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 font-medium cursor-pointer"
                          >
                            <option value="none">{TRANSLATIONS[appLanguage].relationshipNoneOption}</option>
                            <option value="replaces">{TRANSLATIONS[appLanguage].relationshipReplacesOption}</option>
                            <option value="modifies">{TRANSLATIONS[appLanguage].relationshipModifiesOption}</option>
                          </select>
                        </div>

                        {confirmedRelType !== "none" && (
                          <div className="space-y-1">
                            <label className="text-[10px] text-zinc-500 block">{TRANSLATIONS[appLanguage].targetDocLabel}</label>
                            <select
                              value={confirmedRelTargetId}
                              onChange={(e) => setConfirmedRelTargetId(e.target.value)}
                              className="w-full bg-black/60 border border-white/[0.08] text-xs text-zinc-300 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 font-medium cursor-pointer"
                              required
                            >
                              <option value="">{TRANSLATIONS[appLanguage].selectDocumentPlaceholder}</option>
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
                          {TRANSLATIONS[appLanguage].relationshipWarning}
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
                        {TRANSLATIONS[appLanguage].processingChangesText}
                      </>
                    ) : (
                      editingDocId ? TRANSLATIONS[appLanguage].saveChangesBtn : TRANSLATIONS[appLanguage].confirmIngestBtn
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
                  <p className="font-bold mb-1">
                    {ingestStatus.type === "success" 
                      ? (appLanguage === "cs" ? "✓ Úspěch:" : "✓ Success:") 
                      : (appLanguage === "cs" ? "❌ Chyba:" : "❌ Error:")}
                  </p>
                  <p>{ingestStatus.message}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "categories" && (
          <div className="flex-1 overflow-y-auto p-6 bg-[#090d16] flex justify-center">
            <div className="flex flex-col gap-6 w-full max-w-4xl items-start">
              {/* Left Column: Dynamic categories configuration manager */}
              <div className="glass-panel p-6 flex flex-col gap-6 w-full border-white/[0.04] self-start">
                <div>
                  <h2 className="text-md font-bold text-white flex items-center gap-2">
                    <span>📁</span> {TRANSLATIONS[appLanguage].configurationTitle}
                  </h2>
                  <p className="text-xs text-zinc-500 mt-1">
                    {TRANSLATIONS[appLanguage].configurationSubtitle}
                  </p>
                </div>

                {editingConfig ? (
                  <div className="space-y-5">
                    <div className="space-y-3">
                      <span className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                        {TRANSLATIONS[appLanguage].categoriesListLabel}
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
                            title={appLanguage === "cs" ? "Odebrat kategorii" : "Remove category"}
                          >
                            🗑️ {TRANSLATIONS[appLanguage].deleteBtn}
                          </button>
                          <div className="grid grid-cols-3 gap-3">
                            <div>
                              <span className="text-[10px] text-zinc-600 block">{TRANSLATIONS[appLanguage].keyLabel}</span>
                              <span className="text-xs font-mono font-bold text-zinc-500 block truncate" title={cat.key}>{cat.key}</span>
                            </div>
                            <div>
                              <label className="text-[10px] text-zinc-500 block">{TRANSLATIONS[appLanguage].labelLabel}</label>
                              <input
                                type="text"
                                value={cat.label}
                                onChange={(e) => handleCategoryFieldChange(idx, "label", e.target.value)}
                                className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 focus:outline-none focus:border-indigo-500"
                              />
                            </div>
                            <div>
                              <label className="text-[10px] text-zinc-500 block">{TRANSLATIONS[appLanguage].roleNameLabel}</label>
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
                            <label className="text-[10px] text-zinc-500 block">{TRANSLATIONS[appLanguage].categoryDescriptionLabel}</label>
                            <textarea
                              value={cat.description}
                              onChange={(e) => handleCategoryFieldChange(idx, "description", e.target.value)}
                              className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-300 rounded px-2.5 py-1.5 h-14 resize-none focus:outline-none focus:border-indigo-500 leading-normal"
                            />
                          </div>

                          <div className="space-y-1">
                            <label className="text-[10px] text-zinc-500 block">{TRANSLATIONS[appLanguage].securityGroupsLabel}</label>
                            <CategoryTagInput
                              allowedGroups={cat.allowed_groups}
                              onChange={(groups) => handleAllowedGroupsChange(idx, groups)}
                              suggestions={uniqueGroups}
                              locale={appLanguage}
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
                        {TRANSLATIONS[appLanguage].addCategoryBtn}
                      </button>
                    </div>

                    {/* General LLM Analysis Rules */}
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                        {TRANSLATIONS[appLanguage].generalRulesLabel}
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
                      className="w-full py-2.5 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs transition-all shadow-lg shadow-cyan-600/10 disabled:opacity-50 cursor-pointer"
                    >
                      {savingConfig ? TRANSLATIONS[appLanguage].savingConfigText : TRANSLATIONS[appLanguage].saveConfigBtn}
                    </button>
                  </div>
                ) : (
                  <div className="text-xs text-zinc-500 text-center py-6">
                    {TRANSLATIONS[appLanguage].loadingConfigText}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === "config" && (
          <div className="flex-1 overflow-y-auto p-6 bg-[#090d16] flex justify-center">
            <div className="flex flex-col gap-6 w-full max-w-4xl items-start">
              {/* Right Column: Search & Retrieval Config */}
              <div className="glass-panel p-6 flex flex-col gap-6 w-full border-white/[0.04] bg-[#0c1222] self-start">
                <div>
                  <h2 className="text-md font-bold text-white flex items-center gap-2">
                    <span>⚙️</span> {TRANSLATIONS[appLanguage].searchConfigTitle}
                  </h2>
                  <p className="text-xs text-zinc-500 mt-1">
                    {TRANSLATIONS[appLanguage].searchConfigSubtitle}
                  </p>
                </div>

                {editingSearchConfig ? (
                  <div className="space-y-6">
                    
                    {/* Section 1: Search Strategy */}
                    <div className="space-y-4 border-b border-white/5 pb-4">
                      <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-wide">
                        {appLanguage === "cs" ? "1. Strategie vyhledávání" : "1. Search Strategy"}
                      </h3>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                            {TRANSLATIONS[appLanguage].searchStrategyLabel}
                          </label>
                          <select
                            value={editingSearchConfig.search_strategy}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, search_strategy: e.target.value as any })}
                            className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer font-semibold"
                          >
                            <option value="hybrid">{TRANSLATIONS[appLanguage].strategyHybrid}</option>
                            <option value="vector">{TRANSLATIONS[appLanguage].strategyVector}</option>
                            <option value="keyword">{TRANSLATIONS[appLanguage].strategyKeyword}</option>
                          </select>
                        </div>

                        {editingSearchConfig.search_strategy === "hybrid" && (
                          <div className="space-y-1">
                            <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                              {TRANSLATIONS[appLanguage].hybridStrategyLabel}
                            </label>
                            <select
                              value={editingSearchConfig.hybrid_strategy}
                              onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, hybrid_strategy: e.target.value as any })}
                              className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer font-semibold"
                            >
                              <option value="rrf">Weighted RRF (Reciprocal Rank Fusion)</option>
                              <option value="score_addition">Weighted Score Addition (Vážený součet skóre)</option>
                              <option value="union">Union (Sjednocení TOP výsledků)</option>
                            </select>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Section 2: Fusion Settings (Dual Controls) */}
                    {editingSearchConfig.search_strategy === "hybrid" && editingSearchConfig.hybrid_strategy !== "union" && (
                      <div className="space-y-4 border-b border-white/5 pb-4">
                        <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-wide">
                          {appLanguage === "cs" ? "2. Váhy a parametry hybridního sloučení" : "2. Hybrid Fusion Parameters"}
                        </h3>
                        
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {/* Vector Weight */}
                          <div className="space-y-1.5">
                            <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                              {TRANSLATIONS[appLanguage].vectorWeightLabel}
                            </label>
                            <div className="flex items-center gap-3">
                              <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={editingSearchConfig.vector_weight}
                                onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, vector_weight: parseFloat(e.target.value) })}
                                className="flex-1 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                              />
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.05"
                                value={editingSearchConfig.vector_weight}
                                onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, vector_weight: parseFloat(e.target.value) || 0.0 })}
                                className="w-16 bg-black/45 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 text-center focus:outline-none focus:border-indigo-500 font-semibold"
                              />
                            </div>
                          </div>

                          {/* Keyword Weight */}
                          <div className="space-y-1.5">
                            <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                              {TRANSLATIONS[appLanguage].keywordWeightLabel}
                            </label>
                            <div className="flex items-center gap-3">
                              <input
                                type="range"
                                min="0"
                                max="1"
                                step="0.05"
                                value={editingSearchConfig.keyword_weight}
                                onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, keyword_weight: parseFloat(e.target.value) })}
                                className="flex-1 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                              />
                              <input
                                type="number"
                                min="0"
                                max="1"
                                step="0.05"
                                value={editingSearchConfig.keyword_weight}
                                onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, keyword_weight: parseFloat(e.target.value) || 0.0 })}
                                className="w-16 bg-black/45 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 text-center focus:outline-none focus:border-indigo-500 font-semibold"
                              />
                            </div>
                          </div>
                        </div>

                        {/* RRF smoothing k */}
                        {editingSearchConfig.hybrid_strategy === "rrf" && (
                          <div className="space-y-1.5 max-w-xs">
                            <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                              RRF Konstanta (k)
                            </label>
                            <div className="flex items-center gap-3">
                              <input
                                type="range"
                                min="10"
                                max="100"
                                step="1"
                                value={editingSearchConfig.rrf_k}
                                onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, rrf_k: parseInt(e.target.value) })}
                                className="flex-1 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                              />
                              <input
                                type="number"
                                min="10"
                                max="100"
                                step="1"
                                value={editingSearchConfig.rrf_k}
                                onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, rrf_k: parseInt(e.target.value) || 60 })}
                                className="w-16 bg-black/45 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 text-center focus:outline-none focus:border-indigo-500 font-semibold"
                              />
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Section 3: Limits & Thresholds */}
                    <div className="space-y-4 border-b border-white/5 pb-4">
                      <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-wide">
                        {appLanguage === "cs" ? "3. Limity a prahy relevance" : "3. Limits & Relevance Thresholds"}
                      </h3>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                            {TRANSLATIONS[appLanguage].thresholdLabel}
                          </label>
                          <div className="flex items-center gap-3">
                            <input
                              type="range"
                              min="0"
                              max="0.95"
                              step="0.05"
                              value={editingSearchConfig.score_threshold}
                              onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, score_threshold: parseFloat(e.target.value) })}
                              className="flex-1 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                            />
                            <input
                              type="number"
                              min="0"
                              max="0.95"
                              step="0.05"
                              value={editingSearchConfig.score_threshold}
                              onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, score_threshold: parseFloat(e.target.value) || 0.0 })}
                              className="w-16 bg-black/45 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 text-center focus:outline-none focus:border-indigo-500 font-semibold"
                            />
                          </div>
                        </div>

                        <div className="space-y-1.5">
                          <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                            {TRANSLATIONS[appLanguage].boostLabel}
                          </label>
                          <div className="flex items-center gap-3">
                            <input
                              type="range"
                              min="0"
                              max="0.5"
                              step="0.05"
                              value={editingSearchConfig.freshness_boost}
                              onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, freshness_boost: parseFloat(e.target.value) })}
                              className="flex-1 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                            />
                            <input
                              type="number"
                              min="0"
                              max="0.5"
                              step="0.05"
                              value={editingSearchConfig.freshness_boost}
                              onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, freshness_boost: parseFloat(e.target.value) || 0.0 })}
                              className="w-16 bg-black/45 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 text-center focus:outline-none focus:border-indigo-500 font-semibold"
                            />
                          </div>
                        </div>
                      </div>

                      {/* Candidate Pool Limits */}
                      <div className="grid grid-cols-2 gap-3 max-w-md">
                        <div className="space-y-1">
                          <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                            {TRANSLATIONS[appLanguage].vectorLimitLabel}
                          </label>
                          <input
                            type="number"
                            min="5"
                            max="200"
                            value={editingSearchConfig.vector_limit}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, vector_limit: parseInt(e.target.value) || 50 })}
                            className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                        <div className="space-y-1">
                          <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                            {TRANSLATIONS[appLanguage].keywordLimitLabel}
                          </label>
                          <input
                            type="number"
                            min="5"
                            max="200"
                            value={editingSearchConfig.keyword_limit}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, keyword_limit: parseInt(e.target.value) || 50 })}
                            className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                      </div>

                      {/* Final limitations */}
                      {editingSearchConfig.search_strategy === "hybrid" && editingSearchConfig.hybrid_strategy === "union" ? (
                        <div className="grid grid-cols-2 gap-3 max-w-md">
                          <div className="space-y-1">
                            <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                              Union Vector Limit
                            </label>
                            <input
                              type="number"
                              min="1"
                              max="20"
                              value={editingSearchConfig.vector_final_limit}
                              onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, vector_final_limit: parseInt(e.target.value) || 5 })}
                              className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500"
                            />
                          </div>
                          <div className="space-y-1">
                            <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                              Union Keyword Limit
                            </label>
                            <input
                              type="number"
                              min="1"
                              max="20"
                              value={editingSearchConfig.keyword_final_limit}
                              onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, keyword_final_limit: parseInt(e.target.value) || 5 })}
                              className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500"
                            />
                          </div>
                        </div>
                      ) : (
                        <div className="space-y-1 max-w-[216px]">
                          <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                            {TRANSLATIONS[appLanguage].finalLimitLabel}
                          </label>
                          <input
                            type="number"
                            min="1"
                            max="20"
                            value={editingSearchConfig.final_limit}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, final_limit: parseInt(e.target.value) || 5 })}
                            className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500"
                          />
                        </div>
                      )}
                    </div>

                    {/* Section 4: Context Expansion & Tokens */}
                    <div className="space-y-4 border-b border-white/5 pb-4">
                      <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-wide">
                        {appLanguage === "cs" ? "4. Rozšiřování kontextu a tokenové limity" : "4. Context Expansion & Token Limits"}
                      </h3>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                            {TRANSLATIONS[appLanguage].expansionLabel}
                          </label>
                          <select
                            value={editingSearchConfig.context_expansion}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, context_expansion: e.target.value as any })}
                            className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1.5 focus:outline-none focus:border-indigo-500 cursor-pointer font-semibold"
                          >
                            <option value="none">{TRANSLATIONS[appLanguage].expansionNone}</option>
                            <option value="siblings">{TRANSLATIONS[appLanguage].expansionSiblings}</option>
                            <option value="page">{TRANSLATIONS[appLanguage].expansionPage}</option>
                            <option value="section">{TRANSLATIONS[appLanguage].expansionSection}</option>
                          </select>
                        </div>
                        {editingSearchConfig.context_expansion === "siblings" && (
                          <div className="space-y-1 max-w-xs">
                            <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                              {TRANSLATIONS[appLanguage].expansionSizeLabel}
                            </label>
                            <input
                              type="number"
                              min="1"
                              max="3"
                              value={editingSearchConfig.context_expansion_size}
                              onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, context_expansion_size: parseInt(e.target.value) || 1 })}
                              className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded px-2.5 py-1 focus:outline-none focus:border-indigo-500"
                            />
                          </div>
                        )}
                      </div>

                      {/* Token limit budget */}
                      <div className="space-y-1.5">
                        <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                          {appLanguage === "cs" ? "Max. celková délka LLM kontextu (tokens)" : "Max. Total LLM Context Size (tokens)"}
                        </label>
                        <div className="flex items-center gap-3">
                          <input
                            type="range"
                            min="1000"
                            max="30000"
                            step="500"
                            value={editingSearchConfig.context_max_tokens}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, context_max_tokens: parseInt(e.target.value) })}
                            className="flex-1 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                          />
                          <input
                            type="number"
                            min="1000"
                            max="30000"
                            step="500"
                            value={editingSearchConfig.context_max_tokens}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, context_max_tokens: parseInt(e.target.value) || 4000 })}
                            className="w-20 bg-black/45 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 text-center focus:outline-none focus:border-indigo-500 font-semibold"
                          />
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => saveSearchConfigToServer(editingSearchConfig)}
                      disabled={savingSearchConfig}
                      className="w-full mt-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-all shadow-lg shadow-indigo-600/10 disabled:opacity-50 cursor-pointer"
                    >
                      {savingSearchConfig ? TRANSLATIONS[appLanguage].savingConfigText : TRANSLATIONS[appLanguage].saveConfigBtn}
                    </button>
                  </div>
                ) : (
                  <div className="text-xs text-zinc-500 text-center py-6">
                    {TRANSLATIONS[appLanguage].loadingConfigText}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === "chunking" && (
          <div className="flex-1 overflow-y-auto p-6 bg-[#090d16] flex justify-center">
            <div className="flex flex-col lg:flex-row gap-6 w-full max-w-7xl items-start">
              
              {/* Left Column: Settings & Triggers */}
              <div className="glass-panel p-6 flex flex-col gap-6 w-full lg:w-[380px] border-white/[0.04] bg-[#0c1222] self-start">
                <div>
                  <h2 className="text-md font-bold text-white flex items-center gap-2">
                    <span>🧩</span> {TRANSLATIONS[appLanguage].chunkingTab}
                  </h2>
                  <p className="text-xs text-zinc-500 mt-1">
                    {appLanguage === "cs" 
                      ? "Nastavte parametry segmentace a rozdělování textu dokumentů." 
                      : "Configure document text segmentation and chunking parameters."}
                  </p>
                </div>

                {editingSearchConfig ? (
                  <div className="space-y-6">
                    {/* Chunking Settings */}
                    <div className="space-y-4 pb-2">
                      {/* Chunk Size */}
                      <div className="space-y-1.5">
                        <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                          {appLanguage === "cs" ? "Velikost chunku (znaky)" : "Chunk Size (characters)"}
                        </label>
                        <div className="flex items-center gap-3">
                          <input
                            type="range"
                            min="200"
                            max="5000"
                            step="100"
                            value={editingSearchConfig.chunk_size}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, chunk_size: parseInt(e.target.value) })}
                            className="flex-1 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                          />
                          <input
                            type="number"
                            min="200"
                            max="5000"
                            step="100"
                            value={editingSearchConfig.chunk_size}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, chunk_size: parseInt(e.target.value) || 1500 })}
                            className="w-20 bg-black/45 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 text-center focus:outline-none focus:border-indigo-500 font-semibold"
                          />
                        </div>
                      </div>

                      {/* Chunk Overlap */}
                      <div className="space-y-1.5">
                        <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                          {appLanguage === "cs" ? "Překryv chunku (znaky)" : "Chunk Overlap (characters)"}
                        </label>
                        <div className="flex items-center gap-3">
                          <input
                            type="range"
                            min="0"
                            max="1000"
                            step="50"
                            value={editingSearchConfig.chunk_overlap}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, chunk_overlap: parseInt(e.target.value) })}
                            className="flex-1 h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-indigo-500"
                          />
                          <input
                            type="number"
                            min="0"
                            max="1000"
                            step="50"
                            value={editingSearchConfig.chunk_overlap}
                            onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, chunk_overlap: parseInt(e.target.value) || 250 })}
                            className="w-20 bg-black/45 border border-white/[0.08] text-xs text-zinc-200 rounded px-2 py-1 text-center focus:outline-none focus:border-indigo-500 font-semibold"
                          />
                        </div>
                      </div>

                      {/* Splitter Type */}
                      <div className="space-y-1.5">
                        <label className="text-[10px] text-zinc-500 block uppercase tracking-wider font-bold">
                          {appLanguage === "cs" ? "Typ splitteru" : "Splitter Type"}
                        </label>
                        <select
                          value={editingSearchConfig.chunk_splitter_type || "recursive"}
                          onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, chunk_splitter_type: e.target.value as any })}
                          className="w-full bg-[#111827] border border-white/[0.08] text-xs text-zinc-200 rounded-xl px-3 py-2.5 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
                        >
                          <option value="recursive">
                            {appLanguage === "cs" ? "Rekurzivní podle oddělovačů (Recursive)" : "Recursive character splitter"}
                          </option>
                          <option value="character">
                            {appLanguage === "cs" ? "Pevná velikost znaků (Character)" : "Fixed character splitter"}
                          </option>
                        </select>
                      </div>

                      {/* Allow page crossing */}
                      <div className="flex items-center justify-between bg-white/[0.02] p-3 rounded-xl border border-white/[0.04]">
                        <div className="flex flex-col gap-0.5">
                          <span className="text-[11px] text-zinc-200 font-semibold">
                            {appLanguage === "cs" ? "Povolit překryv stránek" : "Allow page boundaries crossing"}
                          </span>
                          <span className="text-[9px] text-zinc-500 max-w-[200px] leading-tight">
                            {appLanguage === "cs"
                              ? "Spojí stránky a vytvoří souvislé chunky i přes konec strany."
                              : "Merges page texts to split continuously without page limits."}
                          </span>
                        </div>
                        <input
                          type="checkbox"
                          checked={editingSearchConfig.chunk_cross_page || false}
                          onChange={(e) => setEditingSearchConfig({ ...editingSearchConfig, chunk_cross_page: e.target.checked })}
                          className="w-4 h-4 bg-zinc-800 accent-indigo-500 rounded border-zinc-700 cursor-pointer"
                        />
                      </div>

                      <p className="text-[10px] text-zinc-500 leading-normal italic mt-1 bg-white/[0.01] p-3 rounded-xl border border-white/[0.03]">
                        {appLanguage === "cs"
                          ? "💡 Poznámka: Změna se projeví na reálném vyhledávání až po spuštění reindexace."
                          : "💡 Note: Changing settings will only apply to active search index after running re-indexing."}
                      </p>
                    </div>

                    <button
                      onClick={() => saveSearchConfigToServer(editingSearchConfig)}
                      disabled={savingSearchConfig}
                      className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition-all shadow-lg shadow-indigo-600/10 disabled:opacity-50 cursor-pointer"
                    >
                      {savingSearchConfig ? TRANSLATIONS[appLanguage].savingConfigText : TRANSLATIONS[appLanguage].saveConfigBtn}
                    </button>

                    <div className="border-t border-white/5 pt-6 space-y-4">
                      <div>
                        <h3 className="text-xs font-bold text-indigo-400 uppercase tracking-wide">
                          {TRANSLATIONS[appLanguage].reindexBtn}
                        </h3>
                        <p className="text-[11px] text-zinc-500 mt-1 leading-normal">
                          {appLanguage === "cs"
                            ? "Spustí proces na pozadí, který přegeneruje chunky pro všechny nahrané dokumenty podle aktuálních parametrů."
                            : "Triggers a background process that re-splits and re-embeds all uploaded documents based on active settings."}
                        </p>
                      </div>

                      <button
                        onClick={async () => {
                          const conf = confirm(
                            appLanguage === "cs"
                              ? "Opravdu chcete spustit celkovou reindexaci (přerozdělení chunků) všech dokumentů na pozadí?\n\nTato operace může trvat několik minut."
                              : "Do you really want to trigger a background re-indexing of all documents?\n\nThis operation may take several minutes."
                          );
                          if (conf) {
                            // Automatically save first to ensure background task gets current sliders configuration
                            await saveSearchConfigToServer(editingSearchConfig);
                            startReindexing("reindex-all", "scanning");
                          }
                        }}
                        className="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs transition-all shadow-lg shadow-amber-600/10 cursor-pointer"
                      >
                        {TRANSLATIONS[appLanguage].reindexBtn}
                      </button>
                    </div>

                  </div>
                ) : (
                  <div className="text-xs text-zinc-500 text-center py-6">
                    {TRANSLATIONS[appLanguage].loadingConfigText}
                  </div>
                )}
              </div>

              {/* Right Column: Live Chunking Preview */}
              <div className="glass-panel p-6 flex flex-col gap-6 flex-1 w-full border-white/[0.04] bg-[#0c1222] self-stretch min-h-[500px]">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-white/5 pb-4">
                  <div>
                    <h2 className="text-md font-bold text-white flex items-center gap-2">
                      <span>👁️</span> {appLanguage === "cs" ? "Interaktivní náhled chunkování" : "Interactive Chunking Preview"}
                    </h2>
                    <p className="text-xs text-zinc-500 mt-1">
                      {appLanguage === "cs"
                        ? "Změna sliderů vlevo okamžitě simuluje rozdělení vybraného dokumentu v paměti backendu."
                        : "Adjusting sliders on the left immediately simulates text splitting in backend memory."}
                    </p>
                  </div>

                  <div className="w-full sm:w-[250px]">
                    <select
                      value={selectedPreviewDocId}
                      onChange={(e) => setSelectedPreviewDocId(e.target.value)}
                      className="w-full bg-black/40 border border-white/[0.08] text-xs text-zinc-200 rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500 font-semibold cursor-pointer"
                    >
                      <option value="" disabled>
                        {appLanguage === "cs" ? "-- Vyberte dokument --" : "-- Select a document --"}
                      </option>
                      {documents.map((doc) => (
                        <option key={doc.document_id} value={doc.document_id}>
                          {doc.title}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {loadingPreviewChunks ? (
                  <div className="flex-1 flex flex-col items-center justify-center py-12 text-zinc-500 gap-3">
                    <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-xs">{appLanguage === "cs" ? "Simuluji rozdělení a načítám chunky..." : "Simulating segmentation and loading chunks..."}</p>
                  </div>
                ) : previewError ? (
                  <div className="flex-1 flex items-center justify-center p-6 bg-red-950/20 border border-red-500/20 rounded-2xl text-xs text-red-400">
                    ⚠️ {previewError}
                  </div>
                ) : previewChunks.length > 0 ? (
                  <div className="flex-1 flex flex-col gap-4">
                    <div className="flex justify-between items-center text-xs bg-indigo-500/5 border border-indigo-500/10 rounded-xl px-4 py-2.5 text-zinc-300 font-medium">
                      <span>
                        {appLanguage === "cs" ? "Celkem vygenerováno chunků:" : "Total chunks generated:"}
                        <strong className="text-indigo-400 ml-1.5 text-sm">{previewChunks.length}</strong>
                      </span>
                      <span className="text-[10px] text-zinc-500">
                        {appLanguage === "cs" ? "Zobrazeno v pořadí indexu" : "Shown in index order"}
                      </span>
                    </div>

                    {/* PDF Formatting Explanation Banner */}
                    <div className="text-[10px] text-zinc-400 bg-white/[0.02] p-3.5 rounded-xl border border-white/[0.04] leading-normal flex gap-2">
                      <span className="text-sm">💡</span>
                      <span>
                        {appLanguage === "cs"
                          ? "Poznámka k formátování: Extrakce textu z PDF odstraňuje vizuální styly (písma, tabulky, sloupce, zarovnání). Zde vidíte surový text (raw text), který se indexuje pro AI model. Dotted amber zvýraznění indikuje textový překryv (overlap) s předchozím chunkem."
                          : "Formatting note: Text extraction from PDF strips visual styles (fonts, grids, tables, alignment). Here you inspect the raw plain text indexable by the search models. Dotted amber highlights show the character overlap with the preceding chunk."}
                      </span>
                    </div>

                    <div className="max-h-[500px] overflow-y-auto space-y-3 pr-1 custom-scrollbar">
                      {previewChunks.map((chunk, i) => {
                        // Alternate background and border colors for distinct segments
                        const bgColors = [
                          "bg-indigo-500/[0.03] border-indigo-500/10 hover:bg-indigo-500/[0.06] hover:border-indigo-500/20",
                          "bg-purple-500/[0.03] border-purple-500/10 hover:bg-purple-500/[0.06] hover:border-purple-500/20",
                          "bg-pink-500/[0.03] border-pink-500/10 hover:bg-pink-500/[0.06] hover:border-pink-500/20",
                          "bg-teal-500/[0.03] border-teal-500/10 hover:bg-teal-500/[0.06] hover:border-teal-500/20"
                        ];
                        const textColors = ["text-indigo-400", "text-purple-400", "text-pink-400", "text-teal-400"];
                        const colorIdx = i % bgColors.length;

                        // Compute overlap highlight with the previous chunk
                        const prevChunk = i > 0 ? previewChunks[i - 1] : null;
                        const overlapText = prevChunk ? findOverlapText(prevChunk.content, chunk.content, editingSearchConfig?.chunk_overlap || 1000) : "";
                        const remainingText = overlapText ? chunk.content.slice(overlapText.length) : chunk.content;

                        return (
                          <div
                            key={chunk.chunk_index}
                            className={`p-4 rounded-xl border transition-all ${bgColors[colorIdx]}`}
                          >
                            <div className="flex justify-between items-center mb-2 text-[10px] font-bold tracking-wide uppercase">
                              <span className={textColors[colorIdx]}>
                                Chunk #{chunk.chunk_index + 1}
                              </span>
                              <div className="flex gap-2 items-center">
                                {chunk.section_title && (
                                  <span className="bg-white/5 px-2 py-0.5 rounded text-zinc-400 max-w-[150px] truncate" title={chunk.section_title}>
                                    📂 {chunk.section_title}
                                  </span>
                                )}
                                <a
                                  href={`${BACKEND_URL}/api/documents/view/${selectedPreviewDocId}#page=${chunk.page_number}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="bg-indigo-500/10 hover:bg-indigo-500/25 border border-indigo-500/20 px-2 py-0.5 rounded text-indigo-300 transition-all font-semibold flex items-center gap-1 cursor-pointer normal-case text-[9px]"
                                  title={appLanguage === "cs" ? "Otevřít tuto stránku v originálním dokumentu" : "Open this page in the original document"}
                                >
                                  📄 {appLanguage === "cs" ? `Otevřít stranu ${chunk.page_number}` : `Open page ${chunk.page_number}`}
                                </a>
                              </div>
                            </div>
                            <p className="text-xs text-zinc-300 leading-relaxed font-mono whitespace-pre-wrap select-all">
                              {overlapText && (
                                <span
                                  className="border-b border-dashed border-amber-500/50 bg-amber-500/10 text-amber-300 font-semibold px-0.5 rounded cursor-help"
                                  title={appLanguage === "cs" ? "Překryv z předchozího chunku (overlap)" : "Overlap from previous chunk"}
                                >
                                  {overlapText}
                                </span>
                              )}
                              {remainingText}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center py-12 text-zinc-500 border-2 border-dashed border-white/5 rounded-2xl">
                    <span className="text-2xl mb-2">👁️</span>
                    <p className="text-xs">
                      {appLanguage === "cs"
                        ? "Vyberte dokument z dropdownu pro zobrazení simulace rozdělení."
                        : "Select a document from the dropdown to see the splitting simulation."}
                    </p>
                  </div>
                )}
              </div>

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
                <span>⚠️</span> {TRANSLATIONS[appLanguage].migrationModalTitle}
              </h3>
              <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                {TRANSLATIONS[appLanguage].migrationModalDesc} <span className="font-bold text-indigo-400">"{editingConfig.categories[deletingCatIndex]?.label}"</span>.
                {appLanguage === "cs" 
                  ? " V databázi mohou existovat dokumenty spojené s touto kategorií." 
                  : " There may be documents in the database associated with this category."}
              </p>
              <p className="text-[11px] text-amber-500 font-semibold mt-2 leading-relaxed">
                {TRANSLATIONS[appLanguage].migrationSafetyWarn}
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-extrabold uppercase text-indigo-400 tracking-wider block">
                {TRANSLATIONS[appLanguage].migrationTargetLabel}
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
                      {cat.label} ({cat.role_name || TRANSLATIONS[appLanguage].noRoleLabel})
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
                {TRANSLATIONS[appLanguage].cancelBtn}
              </button>
              <button
                type="button"
                onClick={handleConfirmCategoryDeletion}
                className="flex-1 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition-all cursor-pointer text-center"
              >
                {TRANSLATIONS[appLanguage].confirmAndTransferBtn}
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
                {reindexProgress?.status === "running" && TRANSLATIONS[appLanguage].reindexProgressTitle}
                {reindexProgress?.status === "completed" && TRANSLATIONS[appLanguage].reindexSuccessTitle}
                {reindexProgress?.status === "failed" && TRANSLATIONS[appLanguage].reindexFailedTitle}
              </h3>
              <p className="text-[11px] text-zinc-400 leading-relaxed max-w-xs mx-auto">
                {reindexProgress?.type === "reindex_fast"
                  ? TRANSLATIONS[appLanguage].reindexProgressDescFast
                  : TRANSLATIONS[appLanguage].reindexProgressDesc}
              </p>
            </div>

            {/* Progress Bar Container */}
            <div className="space-y-2">
              <div className="flex justify-between text-[11px] font-semibold">
                <span className="text-indigo-400">
                  {reindexProgress?.status === "running" && (
                    reindexProgress.phase === "clearing_db" ? TRANSLATIONS[appLanguage].reindexPhaseClearing :
                    reindexProgress.phase === "scanning_files" || reindexProgress.phase === "scanning" ? TRANSLATIONS[appLanguage].reindexPhaseScanning :
                    reindexProgress.phase === "analyzing" ? TRANSLATIONS[appLanguage].reindexPhaseAnalyzing :
                    reindexProgress.phase === "ingesting" ? (
                      reindexProgress.type === "reindex_fast" ? TRANSLATIONS[appLanguage].reindexPhaseIngestingFast : TRANSLATIONS[appLanguage].reindexPhaseIngesting
                    ) :
                    TRANSLATIONS[appLanguage].reindexPhaseWorking
                  )}
                  {reindexProgress?.status === "completed" && TRANSLATIONS[appLanguage].reindexSuccessMsg}
                  {reindexProgress?.status === "failed" && TRANSLATIONS[appLanguage].reindexErrorMsg}
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
                    {reindexProgress.phase === "analyzing"
                      ? TRANSLATIONS[appLanguage].reindexSubphaseAnalyzing
                      : (reindexProgress.type === "reindex_fast"
                         ? (appLanguage === "cs" ? "Rozdělování & přeceňování chunků" : "Re-chunking & re-embedding content")
                         : TRANSLATIONS[appLanguage].reindexSubphaseIngesting)}
                  </div>
                  {reindexProgress.current_file && (
                    <div className="truncate text-white text-[11px]">
                      📁 {reindexProgress.current_file}
                    </div>
                  )}
                  <div className="text-indigo-400 text-[10px]">
                    {TRANSLATIONS[appLanguage].reindexProgressFile
                      .replace("{current}", String(Math.min(reindexProgress.processed_files + 1, reindexProgress.total_files)))
                      .replace("{total}", String(reindexProgress.total_files))}
                  </div>
                </div>
              )}

              {reindexProgress?.status === "failed" && reindexProgress.error && (
                <div className="rounded-xl bg-red-950/20 border border-red-500/20 p-3 text-[11px] text-red-400 font-semibold leading-relaxed mt-2">
                  <div className="text-[9px] font-extrabold uppercase tracking-wider text-red-500 mb-1">
                    {TRANSLATIONS[appLanguage].errorMessageTitle}
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
                  {TRANSLATIONS[appLanguage].closeBtn}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Chunking Preview Modal */}
      {chunkPreviewDocTitle && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fadeIn">
          <div className="glass-panel max-w-4xl w-full p-6 space-y-4 border-white/[0.08] shadow-2xl bg-[#0c1222] max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-white/5 pb-3">
              <div>
                <h3 className="text-md font-bold text-white flex items-center gap-2">
                  <span>📄</span> {appLanguage === "cs" ? "Náhled chunkování dokumentu" : "Document Chunking Preview"}
                </h3>
                <p className="text-xs text-zinc-500 mt-0.5 truncate max-w-2xl" title={chunkPreviewDocTitle}>
                  {chunkPreviewDocTitle}
                </p>
              </div>
              <button
                onClick={() => {
                  setChunkPreviewDocTitle(null);
                  setChunkPreviewDocId(null);
                  setChunkPreviewList(null);
                }}
                className="text-zinc-500 hover:text-zinc-300 text-sm cursor-pointer p-1"
              >
                ✕ Close
              </button>
            </div>

            <div className="flex-1 overflow-y-auto pr-1 space-y-4 py-2">
              {loadingChunks ? (
                <div className="text-center py-12 text-zinc-500 text-xs animate-pulse">
                  {appLanguage === "cs" ? "Načítám chunky z databáze..." : "Loading chunks from database..."}
                </div>
              ) : chunkPreviewList && chunkPreviewList.length === 0 ? (
                <div className="text-center py-12 text-zinc-500 text-xs">
                  {appLanguage === "cs" ? "Dokument nemá žádné chunky." : "This document has no chunks."}
                </div>
              ) : chunkPreviewList ? (
                <div className="space-y-4">
                  {chunkPreviewList.map((chunk, index) => {
                    // Soft pastel color styles
                    const colorStyles = [
                      "bg-emerald-500/10 text-emerald-200 border-emerald-500/25",
                      "bg-sky-500/10 text-sky-200 border-sky-500/25",
                      "bg-purple-500/10 text-purple-200 border-purple-500/25",
                      "bg-amber-500/10 text-amber-200 border-amber-500/25",
                      "bg-rose-500/10 text-rose-200 border-rose-500/25",
                      "bg-indigo-500/10 text-indigo-200 border-indigo-500/25",
                    ];
                    const style = colorStyles[index % colorStyles.length];
                    
                    return (
                      <div key={chunk.chunk_id} className={`p-4 rounded-xl border ${style} space-y-2`}>
                        <div className="flex items-center justify-between text-[10px] font-bold tracking-wide uppercase opacity-75">
                          <span>Chunk #{chunk.chunk_index}</span>
                          <div className="flex items-center gap-2">
                            {chunk.page_number && (
                              <a
                                href={`${BACKEND_URL}/api/documents/view/${chunkPreviewDocId}?highlight_chunk_id=${chunk.chunk_id}#page=${chunk.page_number}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="bg-indigo-500/10 hover:bg-indigo-500/25 border border-indigo-500/20 px-2 py-0.5 rounded text-indigo-300 transition-all font-semibold flex items-center gap-1 cursor-pointer normal-case text-[9px]"
                                title={appLanguage === "cs" ? "Otevřít tuto stránku v originálním dokumentu" : "Open this page in the original document"}
                              >
                                📄 {appLanguage === "cs" ? `Otevřít stranu ${chunk.page_number}` : `Open page ${chunk.page_number}`}
                              </a>
                            )}
                            {chunk.section_title && (
                              <span className="truncate max-w-[200px]" title={chunk.section_title}>
                                Section: {chunk.section_title}
                              </span>
                            )}
                          </div>
                        </div>
                        <p className="text-xs leading-relaxed font-mono font-medium whitespace-pre-wrap">
                          {chunk.content}
                        </p>
                      </div>
                    );
                  })}
                </div>
              ) : null}
            </div>

            <div className="flex justify-end border-t border-white/5 pt-3">
              <button
                onClick={() => {
                  setChunkPreviewDocTitle(null);
                  setChunkPreviewDocId(null);
                  setChunkPreviewList(null);
                }}
                className="px-4 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-300 font-bold transition-all cursor-pointer"
              >
                {appLanguage === "cs" ? "Zavřít" : "Close"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
