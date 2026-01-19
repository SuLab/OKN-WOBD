"use client";

import Link from "next/link";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

export function Header() {
    return (
        <header className="border-b border-slate-200 dark:border-slate-800 px-6 py-4 flex items-center justify-between bg-white dark:bg-slate-950">
            <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity cursor-pointer">
                <span className="h-2 w-2 rounded-full bg-accent" />
                <span className="font-semibold tracking-tight">WOBD Web v2</span>
            </Link>
            <div className="flex items-center gap-4">
                <span className="text-xs text-slate-600 dark:text-slate-400 hidden md:inline">
                    FRINK + OKN graphs · Template-based / LLM-generated / User-generated SPARQL
                </span>
                <ThemeToggle />
            </div>
        </header>
    );
}

