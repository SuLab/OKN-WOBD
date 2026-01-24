"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";

type Theme = "light" | "dark" | "system";

interface ThemeContextType {
    theme: Theme;
    resolvedTheme: "light" | "dark";
    setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
    const [theme, setThemeState] = useState<Theme>("dark");
    const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("dark");
    const [mounted, setMounted] = useState(false);

    // Initialize theme from localStorage or system preference
    useEffect(() => {
        const stored = localStorage.getItem("theme") as Theme | null;
        const initialTheme = stored || "dark";
        setThemeState(initialTheme);
        setMounted(true);
    }, []);

    // Resolve theme based on system preference if theme is "system"
    useEffect(() => {
        if (!mounted) return;

        const resolveTheme = (): "light" | "dark" => {
            if (theme === "system") {
                return window.matchMedia("(prefers-color-scheme: dark)").matches
                    ? "dark"
                    : "light";
            }
            return theme;
        };

        const resolved = resolveTheme();
        setResolvedTheme(resolved);

        // Apply theme class to html element
        const root = document.documentElement;
        root.classList.remove("light", "dark");
        root.classList.add(resolved);

        // Store in localStorage
        if (theme !== "system") {
            localStorage.setItem("theme", theme);
        }
    }, [theme, mounted]);

    // Listen for system theme changes
    useEffect(() => {
        if (!mounted || theme !== "system") return;

        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const handleChange = () => {
            const resolved = mediaQuery.matches ? "dark" : "light";
            setResolvedTheme(resolved);
            document.documentElement.classList.remove("light", "dark");
            document.documentElement.classList.add(resolved);
        };

        mediaQuery.addEventListener("change", handleChange);
        return () => mediaQuery.removeEventListener("change", handleChange);
    }, [theme, mounted]);

    const setTheme = (newTheme: Theme) => {
        setThemeState(newTheme);
    };

    // Prevent flash of unstyled content
    // Always render the provider, but don't apply theme until mounted
    return (
        <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    const context = useContext(ThemeContext);
    if (context === undefined) {
        throw new Error("useTheme must be used within a ThemeProvider");
    }
    return context;
}

