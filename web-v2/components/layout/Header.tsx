import Image from "next/image";
import Link from "next/link";

import { withBasePath } from "@/lib/base-path";

export function Header() {
    return (
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
            <Link
                href="/"
                className="flex shrink-0 items-center gap-3 rounded-md outline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--niaid-link)]"
            >
                <Image
                    src={withBasePath("/wobd-logo.png")}
                    alt="WOBD — Web of Biological Data"
                    width={54}
                    height={45}
                    priority
                    className="h-9 w-auto sm:h-10"
                />
                <span className="hidden text-base font-semibold text-slate-800 sm:inline">
                    WOBD
                </span>
            </Link>
            <nav className="flex items-center gap-2 text-base font-medium text-slate-700">
                <Link
                    href="/"
                    className="rounded px-1 py-0.5 hover:text-[var(--niaid-link)] hover:underline"
                >
                    Home
                </Link>
                <span aria-hidden className="text-slate-400">
                    |
                </span>
                <Link
                    href="/queries"
                    className="rounded px-1 py-0.5 hover:text-[var(--niaid-link)] hover:underline"
                >
                    Templated queries
                </Link>
                <span aria-hidden className="text-slate-400">
                    |
                </span>
                <Link
                    href="/mcp"
                    className="rounded px-1 py-0.5 hover:text-[var(--niaid-link)] hover:underline"
                >
                    Unified MCP
                </Link>
                <span aria-hidden className="text-slate-400">
                    |
                </span>
                <Link
                    href="/about"
                    className="rounded px-1 py-0.5 hover:text-[var(--niaid-link)] hover:underline"
                >
                    About
                </Link>
            </nav>
        </header>
    );
}

