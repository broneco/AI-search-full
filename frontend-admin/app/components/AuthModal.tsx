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
  const [tab, setTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState<string>("user@dolphin.cz");
  const [password, setPassword] = useState<string>("password123");
  const [username, setUsername] = useState<string>("");
  const [role, setRole] = useState<string>("Admin");
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const endpoint = tab === "login" ? "/api/auth/login" : "/api/auth/register";
      const payload = tab === "login" 
        ? { email, password }
        : { email, username: username || email.split("@")[0], password, role };

      const res = await fetch(`${backendUrl}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        onSuccess(data.access_token, data.user);
        onClose();
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || "Chyba přihlášení.");
      }
    } catch {
      setError("Nepodařilo se připojit k autentizačnímu serveru.");
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setEmail("user@dolphin.cz");
    setPassword("password123");
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${backendUrl}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "user@dolphin.cz", password: "password123" }),
      });

      if (res.ok) {
        const data = await res.json();
        onSuccess(data.access_token, data.user);
        onClose();
      } else {
        const errData = await res.json().catch(() => ({}));
        setError(errData.detail || "Demo účet nebyl nalezen.");
      }
    } catch {
      setError("Chyba přihlášení k demo účtu.");
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
            <span className="text-2xl">🐬</span>
            <div>
              <h2 className="text-base font-extrabold text-white">
                {language === "cs" ? "Administrativní Konzole - Přihlášení" : "Admin Console - Sign In"}
              </h2>
              <p className="text-[11px] text-zinc-400">
                Dolphin Consulting Tenant Scope
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

        {/* Tab Switcher */}
        <div className="flex bg-black/40 border border-white/10 rounded-xl p-1 mb-5 text-xs font-bold">
          <button
            onClick={() => { setTab("login"); setError(""); }}
            className={`flex-1 py-2 rounded-lg transition-colors cursor-pointer ${
              tab === "login" ? "bg-indigo-600 text-white shadow-md" : "text-zinc-400 hover:text-white"
            }`}
          >
            {language === "cs" ? "Přihlášení" : "Sign In"}
          </button>
          <button
            onClick={() => { setTab("register"); setError(""); }}
            className={`flex-1 py-2 rounded-lg transition-colors cursor-pointer ${
              tab === "register" ? "bg-indigo-600 text-white shadow-md" : "text-zinc-400 hover:text-white"
            }`}
          >
            {language === "cs" ? "Nová registrace" : "Register"}
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
              placeholder="user@dolphin.cz"
            />
          </div>

          {tab === "register" && (
            <>
              <div>
                <label className="block text-zinc-400 font-semibold mb-1">
                  {language === "cs" ? "Jméno a příjmení" : "Full Name"}
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="w-full bg-black/50 border border-white/15 rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-indigo-500 font-medium"
                  placeholder="Jan Novák"
                />
              </div>

              <div>
                <label className="block text-zinc-400 font-semibold mb-1">
                  {language === "cs" ? "Přístupová role (ACL)" : "Access Role (ACL)"}
                </label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full bg-zinc-900 border border-white/15 rounded-xl px-3.5 py-2.5 text-indigo-300 font-bold focus:outline-none"
                >
                  <option value="Admin">👑 Admin (Administrátor)</option>
                  <option value="Management">🎖️ Management (Manažer)</option>
                  <option value="User">👤 User (Standardní zaměstnanec)</option>
                </select>
              </div>
            </>
          )}

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
            {loading ? "Zpracovávám..." : tab === "login" ? (language === "cs" ? "Přihlásit se" : "Sign In") : (language === "cs" ? "Vytvořit účet" : "Create Account")}
          </button>
        </form>

        {/* 1-Click Fast Demo Login */}
        <div className="mt-5 pt-4 border-t border-white/10 text-center">
          <button
            onClick={handleDemoLogin}
            disabled={loading}
            className="w-full py-2.5 px-4 bg-white/5 hover:bg-white/10 text-indigo-300 hover:text-white rounded-xl border border-white/10 font-bold text-xs transition-colors flex items-center justify-center gap-2 cursor-pointer"
          >
            <span>⚡</span>
            <span>{language === "cs" ? "Rychlé přihlášení (Demo Účet)" : "1-Click Fast Demo Login"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
