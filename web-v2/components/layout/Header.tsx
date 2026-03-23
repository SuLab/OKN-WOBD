import Link from "next/link";

export function Header() {
    return (
        <header className="border-b border-slate-200 px-6 py-4 flex items-center justify-between bg-white">
            <div className="flex items-center gap-6">
                <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity cursor-pointer">
                    <span className="h-2 w-2 rounded-full bg-accent" />
                    <span className="font-semibold tracking-tight">WOBD Web</span>
                </Link>
                <Link
                    href="/about"
                    className="text-sm text-slate-600 hover:text-[var(--niaid-link)] hover:underline"
                >
                    About
                </Link>
            </div>
        </header>
    );
}

