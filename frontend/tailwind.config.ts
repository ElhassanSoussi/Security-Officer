import type { Config } from "tailwindcss";

const config: Config = {
    content: [
        "./app/**/*.{js,ts,jsx,tsx,mdx}",
        "./components/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        container: {
            center: true,
            padding: "2rem",
            screens: {
                "2xl": "1400px",
            },
        },
        extend: {
            colors: {
                border: "hsl(var(--border))",
                input: "hsl(var(--input))",
                ring: "hsl(var(--ring))",
                background: "hsl(var(--background))",
                foreground: "hsl(var(--foreground))",
                primary: {
                    DEFAULT: "hsl(var(--primary))",
                    foreground: "hsl(var(--primary-foreground))",
                },
                secondary: {
                    DEFAULT: "hsl(var(--secondary))",
                    foreground: "hsl(var(--secondary-foreground))",
                },
                destructive: {
                    DEFAULT: "hsl(var(--destructive))",
                    foreground: "hsl(var(--destructive-foreground))",
                },
                muted: {
                    DEFAULT: "hsl(var(--muted))",
                    foreground: "hsl(var(--muted-foreground))",
                },
                accent: {
                    DEFAULT: "hsl(var(--accent))",
                    foreground: "hsl(var(--accent-foreground))",
                },
                popover: {
                    DEFAULT: "hsl(var(--popover))",
                    foreground: "hsl(var(--popover-foreground))",
                },
                card: {
                    DEFAULT: "hsl(var(--card))",
                    foreground: "hsl(var(--card-foreground))",
                },
                /* Semantic tokens from design system */
                success: {
                    DEFAULT: "hsl(var(--success))",
                    bg: "hsl(var(--color-success-bg))",
                },
                warning: {
                    DEFAULT: "hsl(var(--warning))",
                    bg: "hsl(var(--color-warning-bg))",
                },
                danger: {
                    DEFAULT: "hsl(var(--color-danger))",
                    bg: "hsl(var(--color-danger-bg))",
                },
                surface: {
                    DEFAULT: "hsl(var(--color-surface))",
                    alt: "hsl(var(--color-surface-alt))",
                },
            },
            borderRadius: {
                lg: "var(--radius-lg)",
                md: "var(--radius-md)",
                sm: "var(--radius-sm)",
            },
            boxShadow: {
                sm: "var(--shadow-sm)",
                md: "var(--shadow-md)",
            },
            fontSize: {
                xs: ["var(--text-xs)", { lineHeight: "1rem" }],
                sm: ["var(--text-sm)", { lineHeight: "1.25rem" }],
                base: ["var(--text-base)", { lineHeight: "1.5rem" }],
                lg: ["var(--text-lg)", { lineHeight: "1.75rem" }],
                xl: ["var(--text-xl)", { lineHeight: "1.75rem" }],
                "2xl": ["var(--text-2xl)", { lineHeight: "2rem" }],
            },
        },
    },
    plugins: [],
};
export default config;
