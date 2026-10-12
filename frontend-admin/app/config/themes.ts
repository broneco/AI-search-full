export interface ClientTheme {
  id: string;
  name: string;
  appName: string;
  appTitle: string;
  appTagline: string;
  appDescription: string;
  tenantScope: string;
  loginTitle: string;
  loginAdminTitle: string;
  demoEmail: string;
  logoUrl: string;
  logoHeight: number;
  colors: {
    primary: string;
    primaryHover: string;
    secondary: string;
    gradient: string;
    topBarBg: string;
    sidebarBg: string;
    cardBg: string;
    userBubbleBg: string;
    userBubbleText: string;
    aiBubbleBg: string;
    badgeBg: string;
    badgeText: string;
  };
}

export const CLIENT_THEMES: Record<string, ClientTheme> = {
  default: {
    id: "default",
    name: "Default AI Search",
    appName: "AI Search Assistant",
    appTitle: "AI Search Assistant",
    appTagline: "Podnikový vyhledávač znalostí",
    appDescription: "Podnikový vyhledávač znalostí",
    tenantScope: "Default Tenant Scope",
    loginTitle: "AI Search - Přihlášení",
    loginAdminTitle: "Administrativní Konzole - Přihlášení",
    demoEmail: "user@example.com",
    logoUrl: "/logos/logo-dolphin-symbol.png",
    logoHeight: 32,
    colors: {
      primary: "#06b6d4",
      primaryHover: "#0891b2",
      secondary: "#3b82f6",
      gradient: "linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)",
      topBarBg: "#0f172a",
      sidebarBg: "#0f172a",
      cardBg: "#1e293b",
      userBubbleBg: "#2563eb",
      userBubbleText: "#ffffff",
      aiBubbleBg: "#0f172a",
      badgeBg: "rgba(6, 182, 212, 0.2)",
      badgeText: "#38bdf8",
    },
  },
  alzbeta: {
    id: "alzbeta",
    name: "Nemocnice sv. Alžběty",
    appName: "Nemocnice sv. Alžběty AI Search",
    appTitle: "Nemocnice sv. Alžběty AI Search",
    appTagline: "AI vyhledávač ve zdravotnických směrnicích a SOP",
    appDescription: "AI vyhledávač ve zdravotnických směrnicích a SOP Nemocnice sv. Alžběty",
    tenantScope: "Nemocnice sv. Alžběty Tenant Scope",
    loginTitle: "Nemocnice sv. Alžběty - Přihlášení",
    loginAdminTitle: "Nemocnice sv. Alžběty Konzole - Přihlášení",
    demoEmail: "user@alzbeta.cz",
    logoUrl: "/logos/logo-nemocnice-alzbeta-2023.png",
    logoHeight: 38,
    colors: {
      primary: "#00965e",
      primaryHover: "#007a4c",
      secondary: "#b59659",
      gradient: "linear-gradient(135deg, #00965e 0%, #a38244 100%)",
      topBarBg: "#a38244",
      sidebarBg: "#17231c",
      cardBg: "#1e2c24",
      userBubbleBg: "#007a4c",
      userBubbleText: "#ffffff",
      aiBubbleBg: "#16231b",
      badgeBg: "rgba(0, 150, 94, 0.2)",
      badgeText: "#4ade80",
    },
  },
  dolphin: {
    id: "dolphin",
    name: "Dolphin Consulting",
    appName: "Dolphin AI Search",
    appTitle: "Dolphin AI Search",
    appTagline: "Podnikový vyhledávač znalostí s přesnými citacemi",
    appDescription: "Inteligentní firemní vyhledávání v dokumentech Dolphin Consulting s podloženými citacemi",
    tenantScope: "Dolphin Consulting Tenant Scope",
    loginTitle: "Dolphin AI Search - Přihlášení",
    loginAdminTitle: "Dolphin Administrativní Konzole - Přihlášení",
    demoEmail: "user@dolphin.cz",
    logoUrl: "/logos/logo-dolphin-symbol.png",
    logoHeight: 32,
    colors: {
      primary: "#06b6d4",
      primaryHover: "#0891b2",
      secondary: "#3b82f6",
      gradient: "linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)",
      topBarBg: "#0f172a",
      sidebarBg: "#0f172a",
      cardBg: "#1e293b",
      userBubbleBg: "#2563eb",
      userBubbleText: "#ffffff",
      aiBubbleBg: "#0f172a",
      badgeBg: "rgba(6, 182, 212, 0.2)",
      badgeText: "#38bdf8",
    },
  },
  jhu: {
    id: "jhu",
    name: "Jihočeská Univerzita v Českých Budějovicích",
    appName: "JCU AI Search",
    appTitle: "JCU AI Search",
    appTagline: "AI vyhledávač ve studijních řádech, opatřeních a předpisech JČU",
    appDescription: "Inteligentní vyhledávání ve studijních řádech a předpisech JCU s podloženými citacemi",
    tenantScope: "JCU Tenant Scope",
    loginTitle: "JCU AI Search - Přihlášení",
    loginAdminTitle: "JCU Administrativní Konzole - Přihlášení",
    demoEmail: "user@jcu.cz",
    logoUrl: "/logos/logo-JHU.webp",
    logoHeight: 36,
    colors: {
      primary: "#c8102e",
      primaryHover: "#9b001c",
      secondary: "#e10600",
      gradient: "linear-gradient(135deg, #c8102e 0%, #9b001c 100%)",
      topBarBg: "#18181b",
      sidebarBg: "#18181b",
      cardBg: "#27272a",
      userBubbleBg: "#c8102e",
      userBubbleText: "#ffffff",
      aiBubbleBg: "#18181b",
      badgeBg: "rgba(200, 16, 46, 0.2)",
      badgeText: "#f87171",
    },
  },
  showcase: {
    id: "showcase",
    name: "Showcase AI Search",
    appName: "Showcase AI Search",
    appTitle: "Showcase AI Search",
    appTagline: "Ukázkový vyhledávač znalostí s přesnými citacemi",
    appDescription: "Ukázkový vyhledávač znalostí v firemních dokumentech",
    tenantScope: "Showcase Tenant Scope",
    loginTitle: "Showcase AI Search - Přihlášení",
    loginAdminTitle: "Showcase Admin Konzole - Přihlášení",
    demoEmail: "user@showcase.cz",
    logoUrl: "/logos/logo-dolphin-symbol.png",
    logoHeight: 32,
    colors: {
      primary: "#6366f1",
      primaryHover: "#4f46e5",
      secondary: "#06b6d4",
      gradient: "linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)",
      topBarBg: "#0f172a",
      sidebarBg: "#0f172a",
      cardBg: "#1e293b",
      userBubbleBg: "#4f46e5",
      userBubbleText: "#ffffff",
      aiBubbleBg: "#0f172a",
      badgeBg: "rgba(99, 102, 241, 0.2)",
      badgeText: "#818cf8",
    },
  },
};

export const DEFAULT_THEME_ID = "dolphin";
