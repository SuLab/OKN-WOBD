"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export function HeroSearch() {
  const [value, setValue] = useState("");
  const router = useRouter();

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const q = value.trim();
    if (!q) return;
    const searchParams = new URLSearchParams();
    if (q) searchParams.set("q", q);
    router.push(searchParams.toString() ? `/?${searchParams.toString()}` : "/");
  }

  return (
    <form onSubmit={onSubmit} className="w-full">
      <div className="relative">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Ask WOBD..."
          className="w-full px-6 py-4 text-lg bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500"
        />
        <button
          type="submit"
          className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 bg-accent text-white rounded-md font-medium hover:bg-accentDark transition-colors"
        >
          Search
        </button>
      </div>
    </form>
  );
}



