export interface ClientTheme {
  id: string;
  name: string;
  appName: string;
  appTagline: string;
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
  alzbeta: {
    id: "alzbeta",
    name: "Nemocnice sv. Alžběty",
    appName: "Nemocnice sv. Alžběty",
    appTagline: "AI vyhledávač ve zdravotnických směrnicích a SOP",
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
    appTagline: "Podnikový vyhledávač znalostí s přesnými citacemi",
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
};

export const DEFAULT_THEME_ID = "alzbeta";
