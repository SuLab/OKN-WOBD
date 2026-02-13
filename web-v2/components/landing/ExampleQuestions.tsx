"use client";

import { useRouter } from "next/navigation";

const EXAMPLES = [
  "Show datasets related to influenza vaccines.",
  "Find datasets with RNA-seq data for human blood samples.",
  "Find datasets that use an experimental system that might be useful for studying the drug Tocilizumab.",
  "Find experiments where Dusp2 is upregulated.",
];

export function ExampleQuestions() {
  const router = useRouter();

  function handleClick(question: string) {
    const searchParams = new URLSearchParams({ q: question });
    router.push(`/?${searchParams.toString()}`);
  }

  return (
    <div className="space-y-2">
      <p className="text-sm text-slate-600 dark:text-slate-400">Example questions:</p>
      <div className="flex flex-wrap gap-2">
        {EXAMPLES.map((q, i) => (
          <button
            key={i}
            onClick={() => handleClick(q)}
            className="px-4 py-2 text-sm bg-slate-100 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-md hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors text-left text-slate-900 dark:text-slate-100"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}



