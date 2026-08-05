"use client";

import React, { useState } from "react";

interface PdfViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string | null;
  documentTitle: string;
  pageNumber?: number;
  highlightChunkId?: string;
  backendUrl: string;
  language: "cs" | "en";
}

export const PdfViewerModal: React.FC<PdfViewerModalProps> = ({
  isOpen,
  onClose,
  documentId,
  documentTitle,
  pageNumber = 1,
  highlightChunkId,
  backendUrl,
  language,
}) => {
  const [zoom, setZoom] = useState<number>(100);

  if (!isOpen || !documentId) return null;

  // Build backend PDF URL with dynamic text highlight annotation and page target
  let pdfUrl = `${backendUrl}/api/documents/view/${documentId}`;
  const params = new URLSearchParams();
  if (highlightChunkId) {
    params.append("highlight_chunk_id", highlightChunkId);
  }
  
  const queryString = params.toString();
  if (queryString) {
    pdfUrl += `?${queryString}`;
  }
  
  // Add browser native PDF page anchor
  pdfUrl += `#page=${pageNumber || 1}&toolbar=1&navpanes=0`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-md transition-opacity">
      <div className="relative w-full max-w-6xl h-[90vh] glass-panel bg-[#0d1322] border border-white/10 flex flex-col overflow-hidden shadow-2xl rounded-2xl">
        
        {/* Header Toolbar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-white/[0.02]">
          <div className="flex items-center gap-3 overflow-hidden">
            <span className="text-xl">📄</span>
            <div>
              <h2 className="text-sm font-bold text-white truncate max-w-md sm:max-w-xl" title={documentTitle}>
                {documentTitle}
              </h2>
              <div className="flex items-center gap-2 text-[11px] text-zinc-400 mt-0.5">
                <span className="bg-indigo-500/20 text-indigo-300 font-semibold px-2 py-0.5 rounded border border-indigo-500/30">
                  {language === "cs" ? `Cílová strana: ${pageNumber}` : `Target Page: ${pageNumber}`}
                </span>
                {highlightChunkId && (
                  <span className="bg-emerald-500/20 text-emerald-300 font-semibold px-2 py-0.5 rounded border border-emerald-500/30">
                    {language === "cs" ? "✨ Žlutě zvýrazněno AI citací" : "✨ Highlighted by AI citation"}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Open in new window button */}
            <a
              href={`${backendUrl}/api/documents/view/${documentId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 bg-white/5 hover:bg-white/10 text-zinc-300 text-xs font-semibold rounded-lg border border-white/10 transition-colors"
              title={language === "cs" ? "Otevřít v novém okně" : "Open in new window"}
            >
              <span>↗️</span>
              <span>{language === "cs" ? "Otevřít v novém okně" : "Open in new window"}</span>
            </a>

            {/* Zoom Controls */}
            <div className="hidden md:flex items-center bg-black/40 border border-white/10 rounded-lg p-1 text-xs">
              <button
                onClick={() => setZoom((prev) => Math.max(50, prev - 15))}
                className="px-2 py-1 text-zinc-400 hover:text-white hover:bg-white/10 rounded transition-colors"
                title="Zoom out"
              >
                🔍 -
              </button>
              <span className="px-2 text-zinc-300 font-mono text-[11px]">{zoom}%</span>
              <button
                onClick={() => setZoom((prev) => Math.min(200, prev + 15))}
                className="px-2 py-1 text-zinc-400 hover:text-white hover:bg-white/10 rounded transition-colors"
                title="Zoom in"
              >
                🔍 +
              </button>
            </div>

            {/* Close Button */}
            <button
              onClick={onClose}
              className="p-2 text-zinc-400 hover:text-white hover:bg-white/10 rounded-xl transition-colors text-lg font-bold ml-2 cursor-pointer"
              title={language === "cs" ? "Zavřít prohlížeč" : "Close viewer"}
            >
              ✕
            </button>
          </div>
        </div>

        {/* PDF Embedded Canvas Container */}
        <div className="relative flex-1 bg-zinc-950/80 w-full h-full overflow-hidden flex items-center justify-center">
          <iframe
            src={pdfUrl}
            title={`PDF View - ${documentTitle}`}
            className="w-full h-full border-none transition-transform duration-200"
            style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
          />
        </div>

        {/* Footer info bar */}
        <div className="px-6 py-2.5 bg-black/60 border-t border-white/5 flex items-center justify-between text-[11px] text-zinc-400">
          <span>
            {language === "cs"
              ? "💡 Prohlížeč vykresluje originální PDF včetně písma, obrázků a grafů."
              : "💡 Renders actual original PDF including typography, graphics, and layout."}
          </span>
          <a
            href={pdfUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-indigo-400 hover:underline flex items-center gap-1 font-medium"
          >
            <span>↗️</span>
            <span>{language === "cs" ? "Otevřít v novém okně" : "Open in new window"}</span>
          </a>
        </div>
      </div>
    </div>
  );
};
