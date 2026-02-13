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
        // NIAID Data Discovery Portal palette (dashboard and result cards)
        niaid: {
          header: "#184260",
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



