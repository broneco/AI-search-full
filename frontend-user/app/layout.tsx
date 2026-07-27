import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Firemní AI Vyhledávač | Dolphin Consulting",
  description: "Inteligentní firemní vyhledávání v dokumentech Dolphin Consulting s podloženými citacemi",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="cs">
      <body className="antialiased">{children}</body>
    </html>
  );
}
