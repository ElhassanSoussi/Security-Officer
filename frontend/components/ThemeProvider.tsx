"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

interface ThemeContextValue {
    theme: Theme;
    resolved: "light" | "dark";
    setTheme: (t: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
    theme: "system",
    resolved: "light",
    setTheme: () => {},
});

const STORAGE_KEY = "nyc-theme-preference";

function resolveSystem(): "light" | "dark" {
    if (typeof window === "undefined") return "light";
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(resolved: "light" | "dark") {
    if (typeof document === "undefined") return;
    const html = document.documentElement;
    html.setAttribute("data-theme", resolved);
    html.classList.remove("light", "dark");
    html.classList.add(resolved);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<Theme>("system");
    const [resolved, setResolved] = useState<"light" | "dark">("light");

    // On mount: read from localStorage
    useEffect(() => {
        const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
        if (stored && ["light", "dark", "system"].includes(stored)) {
            setThemeState(stored);
        }
    }, []);

    // Resolve and apply whenever theme changes
    useEffect(() => {
        const r = theme === "system" ? resolveSystem() : theme;
        setResolved(r);
        applyTheme(r);
    }, [theme]);

    // Listen for OS preference changes when theme is "system"
    useEffect(() => {
        if (theme !== "system") return;
        const mq = window.matchMedia("(prefers-color-scheme: dark)");
        const handler = (e: MediaQueryListEvent) => {
            const r = e.matches ? "dark" : "light";
            setResolved(r);
            applyTheme(r);
        };
        mq.addEventListener("change", handler);
        return () => mq.removeEventListener("change", handler);
    }, [theme]);

    const setTheme = useCallback((t: Theme) => {
        setThemeState(t);
        localStorage.setItem(STORAGE_KEY, t);
    }, []);

    return (
        <ThemeContext.Provider value={{ theme, resolved, setTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

export function useTheme() {
    return useContext(ThemeContext);
}
