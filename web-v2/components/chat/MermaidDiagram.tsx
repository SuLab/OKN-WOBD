"use client";

import { useEffect, useRef, useState } from "react";

interface MermaidDiagramProps {
  code: string;
  id: string;
}

export function MermaidDiagram({ code, id }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [svg, setSvg] = useState<string | null>(null);

  useEffect(() => {
    if (!code?.trim()) {
      setSvg(null);
      setError(null);
      return;
    }

    let cancelled = false;

    (async () => {
      setError(null);
      setSvg(null);
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "neutral",
          securityLevel: "loose",
          suppressErrorRendering: true,
        });

        const uid = `mermaid-${id.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
        const { svg: out } = await mermaid.render(uid, code);
        if (!cancelled) {
          setSvg(out);
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        if (!cancelled) setError(msg);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [code, id]);

  if (!code?.trim()) return null;

  if (error) {
    return (
      <div className="mt-2 p-3 rounded-lg bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-sm">
        <p className="text-amber-600 dark:text-amber-400 mb-2">
          Diagram could not be rendered: {error}
        </p>
        <pre className="text-xs font-mono text-slate-600 dark:text-slate-400 whitespace-pre-wrap break-words overflow-x-auto">
          {code}
        </pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className="mt-2 py-4 text-slate-500 dark:text-slate-400 text-sm">
        Rendering diagram…
      </div>
    );
  }

  return (
    <div
      className="mermaid-diagram mt-2 flex justify-center overflow-x-auto rounded-lg bg-white dark:bg-slate-900/50 p-3"
      style={{ transform: 'scale(1.5)', transformOrigin: 'top center' }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
