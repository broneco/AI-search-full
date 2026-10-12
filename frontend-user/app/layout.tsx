import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Firemní AI Vyhledávač",
  description: "Inteligentní firemní vyhledávání v dokumentech s podloženými citacemi",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="cs" suppressHydrationWarning>
      <body className="antialiased" suppressHydrationWarning>{children}</body>
    </html>
  );
}
