"use client";

export async function openAuthenticatedPdf(url: string, token: string | null) {
  const viewer = window.open("", "_blank");
  if (viewer) viewer.opener = null;
  try {
    if (!token) throw new Error("Přihlášení vyžadováno / Sign in required.");
    const response = await fetch(url.split("#")[0], { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) throw new Error("PDF není dostupné / PDF unavailable.");
    const objectUrl = URL.createObjectURL(await response.blob());
    if (!viewer) { URL.revokeObjectURL(objectUrl); throw new Error("Povolte nové okno / Allow the popup."); }
    viewer.location.href = objectUrl + (url.includes("#") ? "#" + url.split("#")[1] : "");
    const cleanup = window.setInterval(() => {
      if (viewer.closed) { URL.revokeObjectURL(objectUrl); window.clearInterval(cleanup); }
    }, 1000);
  } catch (error) {
    viewer?.close();
    window.alert(error instanceof Error ? error.message : "PDF unavailable.");
  }
}
