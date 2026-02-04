import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        background: {
          DEFAULT: "#ffffff",
          dark: "#020617"
        },
        foreground: {
          DEFAULT: "#1f2937",
          dark: "#e5e7eb"
        },
        accent: "#4865E3",
        accentDark: "#3A52C7",
        accentMuted: {
          DEFAULT: "#F1F5F9",
          dark: "#1E293B"
        }
      }
    }
  },
  plugins: []
};

export default config;



