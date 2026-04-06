import Link from "next/link";

export function Header() {
    return (
        <header className="border-b border-slate-200 px-6 py-4 flex items-center justify-between bg-white">
            <div className="flex items-center gap-2">
                <Link
                    href="/"
                    className="text-base font-medium text-slate-700 hover:text-[var(--niaid-link)] hover:underline transition-colors"
                >
                    Home
                </Link>
                <span aria-hidden className="text-slate-400">|</span>
                <Link
                    href="/about"
                    className="text-base font-medium text-slate-700 hover:text-[var(--niaid-link)] hover:underline transition-colors"
                >
                    About
                </Link>
            </div>
        </header>
    );
}

