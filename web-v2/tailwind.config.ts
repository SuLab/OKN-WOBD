import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        // Match okn.us system stack — no webfont
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "'Segoe UI'",
          "Roboto",
          "'Helvetica Neue'",
          "Arial",
          "sans-serif",
          "'Apple Color Emoji'",
          "'Segoe UI Emoji'",
          "'Segoe UI Symbol'",
        ],
        mono: [
          "'SF Mono'",
          "Monaco",
          "'Cascadia Code'",
          "'Roboto Mono'",
          "Consolas",
          "'Courier New'",
          "monospace",
        ],
      },
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
        },
        // OKN (parent site) palette — okn.us
        okn: {
          navbar: "#2f204a",       // dark eggplant header/footer accent
          primary: "#6B4C9A",      // brand purple (links, hover)
          primaryLight: "#9659FF",
          primaryHoverBg: "#F5F0FA",
          borderPurple: "#D4C5E8",
          bgSoft: "#FAFAFA",       // page background
          bgMuted: "#F5F5F5",      // section / footer background
          border: "#E0E0E0",
          textStrong: "#333333",
          textMuted: "#666666",
          textLight: "#999999",
        },
        // NIAID Data Discovery Portal palette (kept for NIAID-sourced result cards)
        niaid: {
          header: "#20558A",
          link: "#0071bc",
          button: "#28A745",
          cardBg: "#ffffff",
          pageBg: "#f5f5f5",
          badgePositive: "#E0F2E6",
          badgePositiveText: "#1e7e34",
          badgeNeutral: "#F0F0F0",
          badgeNeutralText: "#333333",
          tagSpecies: "#EBF7EE",
          tagHealthCondition: "#FAE8EB",
          tagMeasurement: "#EFECF6",
          tagFunding: "#FCF2E6",
          tagLicense: "#E6F3F9",
          tagTopic: "#F0F0F0",
          /* Pagination (NIAID Dataset Discovery Portal teal) */
          paginationActive: "#0d9488",
          paginationBorder: "#14b8a6",
          paginationText: "#0f766e",
        },
      },
    },
  },
  plugins: []
};

export default config;
