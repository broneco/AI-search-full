"use client";

import React, { useState } from "react";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (token: string, user: any) => void;
  backendUrl: string;
  language: "cs" | "en";
}

export const AuthModal: React.FC<AuthModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  backendUrl,
  language,
}) => {
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${backendUrl}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (res.ok) {
        const data = await res.json();
        onSuccess(data.access_token, data.user);
        onClose();
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || (language === "cs" ? "Nesprávný e-mail nebo heslo." : "Invalid email or password."));
      }
    } catch {
      setError(language === "cs" ? "Nepodařilo se připojit k autentizačnímu serveru." : "Failed to connect to authentication server.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md">
      <div className="relative w-full max-w-md glass-panel bg-[#0d1322] border border-white/10 p-6 shadow-2xl rounded-2xl">
        
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-5">
          <div className="flex items-center gap-2.5">
            <span className="text-2xl">🔐</span>
            <div>
              <h2 className="text-base font-extrabold text-white">
                {language === "cs" ? "Přihlášení do AI Search" : "Sign in to AI Search"}
              </h2>
              <p className="text-[11px] text-zinc-400">
                {language === "cs" ? "Zadejte své firemní přihlašovací údaje" : "Enter your corporate credentials"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-white p-1 text-lg transition-colors cursor-pointer"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-500/20 border border-red-500/40 text-red-300 text-xs font-medium">
            ⚠️ {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          <div>
            <label className="block text-zinc-400 font-semibold mb-1">
              {language === "cs" ? "E-mailový účet" : "Email Address"}
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-black/50 border border-white/15 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-indigo-500 font-medium"
              placeholder="vas.email@firma.cz"
            />
          </div>

          <div>
            <label className="block text-zinc-400 font-semibold mb-1">
              {language === "cs" ? "Heslo" : "Password"}
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full bg-black/50 border border-white/15 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-indigo-500 font-medium"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-indigo-600/25 cursor-pointer disabled:opacity-50 mt-2"
          >
            {loading ? (language === "cs" ? "Zpracovávám..." : "Signing in...") : (language === "cs" ? "Přihlásit se" : "Sign In")}
          </button>
        </form>
      </div>
    </div>
  );
};
