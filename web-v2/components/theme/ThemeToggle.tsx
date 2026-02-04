"use client";

import { useTheme } from "@/lib/theme/ThemeProvider";

export function ThemeToggle() {
    const { theme, resolvedTheme, setTheme } = useTheme();

    const cycleTheme = () => {
        if (theme === "dark") {
            setTheme("light");
        } else if (theme === "light") {
            setTheme("system");
        } else {
            setTheme("dark");
        }
    };

    const getIcon = () => {
        if (resolvedTheme === "dark") {
            // Moon icon
            return (
                <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
                    />
                </svg>
            );
        } else {
            // Sun icon
            return (
                <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
                    />
                </svg>
            );
        }
    };

    return (
        <button
            onClick={cycleTheme}
            className="flex items-center gap-2 px-3 py-2 rounded-md bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 transition-colors"
            title={`Theme: ${theme === "system" ? "System" : theme === "dark" ? "Dark" : "Light"} (click to cycle)`}
        >
            {getIcon()}
            <span className="text-xs font-medium hidden sm:inline">
                {theme === "system" ? "System" : theme === "dark" ? "Dark" : "Light"}
            </span>
        </button>
    );
}

