export interface UserAppTranslations {
  title: string;
  subtitle: string;
  searchPlaceholder: string;
  searchBtn: string;
  clearChatBtn: string;
  apiOnlineStatus: string;
  apiOfflineStatus: string;
  userRoleLabel: string;
  initialGreeting: string;
  citationsTitle: string;
  citationsSubtitle: string;
  sourceDocHeader: string;
  citedPassageLabel: string;
  securityAuditLabel: string;
  freshnessLabel: string;
  aclGroupsLabel: string;
  pageLabel: string;
  pageNumberLabel: string;
  chapterSectionLabel: string;
  openPdfBtn: string;
  openPdfModalTitle: string;
  closeModalBtn: string;
  zoomInBtn: string;
  zoomOutBtn: string;
  pageNavLabel: string;
  downloadPdfBtn: string;
  suggestedQuestionsTitle: string;
  suggestedQ1: string;
  suggestedQ2: string;
  suggestedQ3: string;
  suggestedQ4: string;
  disclaimer: string;
  thinkingMessage: string;
  noCitationsFound: string;
}

export const TRANSLATIONS: Record<"cs" | "en", UserAppTranslations> = {
  cs: {
    title: "Firemní AI Vyhledávač",
    subtitle: "Chytré vyhledávání v dokumentech Dolphin Consulting s ověřenými citacemi",
    searchPlaceholder: "Zadejte dotaz (např. 'Jaká jsou pravidla pro pracovní cesty a cestovní náhrady?')...",
    searchBtn: "Vyhledat",
    clearChatBtn: "Vymazat konverzaci",
    apiOnlineStatus: "API: Online",
    apiOfflineStatus: "API: Offline",
    userRoleLabel: "Uživatel:",
    initialGreeting: "Dobrý den! Jsem Váš firemní AI vyhledávací asistent. Zadejte libovolný dotaz a já vyhledám odpověď v nahraných směrnicích a dokumentech Dolphin Consulting. Odpověď bude podložená přímými citacemi a přizpůsobí se Vašim přístupovým právům.",
    citationsTitle: "Zdroje a citace",
    citationsSubtitle: "Ověření podkladů a audit přístupu",
    sourceDocHeader: "Zdrojový dokument",
    citedPassageLabel: "Citovaná pasáž z dokumentu",
    securityAuditLabel: "Bezpečnost & Čerstvost",
    freshnessLabel: "Stav dokumentu",
    aclGroupsLabel: "Přístupové skupiny",
    pageLabel: "Strana",
    pageNumberLabel: "Číslo strany",
    chapterSectionLabel: "Sekce / Kapitola",
    openPdfBtn: "📄 Otevřít plně formátovaný PDF náhled",
    openPdfModalTitle: "Plně formátovaný PDF prohlížeč",
    closeModalBtn: "Zavřít",
    zoomInBtn: "Zvětšit",
    zoomOutBtn: "Zmenšit",
    pageNavLabel: "Stránka {current} z {total}",
    downloadPdfBtn: "Stáhnout PDF",
    suggestedQuestionsTitle: "Často kladené dotazy:",
    suggestedQ1: "Jaká jsou pravidla pro schvalování služebních cest?",
    suggestedQ2: "Jaký je postup při nahlášení bezpečnostního incidentu?",
    suggestedQ3: "Jak fungují pravidla pro prémie a hodnocení?",
    suggestedQ4: "Jaké jsou zásady ochrany osobních údajů?",
    disclaimer: "Odpovědi jsou generovány na základě nahraných směrnic. Pro ověření klikněte na citace v textu.",
    thinkingMessage: "AI asistent vyhledává v dokumentech a připravuje odpověď s citacemi...",
    noCitationsFound: "Pro tuto odpověď nebyly použity žádné přímé citace.",
  },
  en: {
    title: "Corporate AI Search",
    subtitle: "Intelligent search in Dolphin Consulting documents with verified citations",
    searchPlaceholder: "Ask anything (e.g. 'What are the travel reimbursement guidelines?')...",
    searchBtn: "Search",
    clearChatBtn: "Clear conversation",
    apiOnlineStatus: "API: Online",
    apiOfflineStatus: "API: Offline",
    userRoleLabel: "User:",
    initialGreeting: "Hello! I am your corporate AI search assistant. Ask any question and I will retrieve answers backed by citations from uploaded Dolphin Consulting documents, adapted to your access rights.",
    citationsTitle: "Sources & Citations",
    citationsSubtitle: "Source verification & access audit",
    sourceDocHeader: "Source Document",
    citedPassageLabel: "Cited Passage Content",
    securityAuditLabel: "Security & Freshness",
    freshnessLabel: "Document Status",
    aclGroupsLabel: "ACL Security Groups",
    pageLabel: "Page",
    pageNumberLabel: "Page Number",
    chapterSectionLabel: "Section / Chapter",
    openPdfBtn: "📄 Open Fully Formatted PDF Preview",
    openPdfModalTitle: "Fully Formatted PDF Viewer",
    closeModalBtn: "Close",
    zoomInBtn: "Zoom In",
    zoomOutBtn: "Zoom Out",
    pageNavLabel: "Page {current} of {total}",
    downloadPdfBtn: "Download PDF",
    suggestedQuestionsTitle: "Suggested questions:",
    suggestedQ1: "What are the rules for approving business trips?",
    suggestedQ2: "What is the procedure for reporting a security incident?",
    suggestedQ3: "How do bonus rules and performance reviews work?",
    suggestedQ4: "What are the personal data protection policies?",
    disclaimer: "Answers are synthesized from verified internal policies. Click inline citations to inspect source documents.",
    thinkingMessage: "AI assistant is searching documents and preparing answer with citations...",
    noCitationsFound: "No direct source citations were referenced for this response.",
  }
};
