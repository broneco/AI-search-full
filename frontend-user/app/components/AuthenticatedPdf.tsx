"use client";

import React, { useEffect, useState } from "react";

async function pdfBlob(url: string, token: string | null, signal?: AbortSignal): Promise<Blob> {
  if (!token) throw new Error("Přihlášení vyžadováno / Sign in required.");
  const response = await fetch(url.split("#")[0], {
    headers: { Authorization: `Bearer ${token}` }, signal,
  });
  if (!response.ok) throw new Error(`PDF není dostupné / PDF unavailable (${response.status}).`);
  return response.blob();
}

export async function openAuthenticatedPdf(url: string, token: string | null) {
  const viewer = window.open("", "_blank");
  if (viewer) viewer.opener = null;
  try {
    const objectUrl = URL.createObjectURL(await pdfBlob(url, token));
    const target = objectUrl + (url.includes("#") ? "#" + url.split("#")[1] : "");
    if (viewer) {
      viewer.location.href = target;
      const cleanup = window.setInterval(() => {
        if (viewer.closed) { URL.revokeObjectURL(objectUrl); window.clearInterval(cleanup); }
      }, 1000);
    } else {
      URL.revokeObjectURL(objectUrl);
      throw new Error("Povolte nové okno / Allow the popup.");
    }
  } catch (error) {
    viewer?.close();
    window.alert(error instanceof Error ? error.message : "PDF unavailable.");
  }
}

export function AuthenticatedPdf({ src, authToken, ...props }: Omit<React.IframeHTMLAttributes<HTMLIFrameElement>, "src"> & {
  src: string; authToken: string | null;
}) {
  const key = `${authToken || ""}|${src}`;
  const [resource, setResource] = useState<{ key: string; url?: string; error?: string } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl: string | undefined;
    pdfBlob(src, authToken, controller.signal).then((blob) => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      const hash = src.includes("#") ? "#" + src.split("#")[1] : "";
      setResource({ key, url: objectUrl + hash });
    }).catch((error) => {
      if (!controller.signal.aborted) setResource({ key, error: String(error.message) });
    });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [src, authToken, key]);
  if (resource?.key !== key || !resource.url) {
    return <p role="status" className="p-4 text-sm text-zinc-400">{resource?.key === key && resource.error ? resource.error : "Načítání PDF / Loading PDF…"}</p>;
  }
  return <iframe {...props} src={resource.url} />;
}
