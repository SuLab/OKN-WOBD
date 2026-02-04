import "./globals.css";
import type { ReactNode } from "react";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";
import { Header } from "@/components/layout/Header";

export const metadata = {
  title: "WOBD Web v2",
  description: "Exa-style chat UI for WOBD with template-based, LLM-generated, and user-generated SPARQL querying"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-white dark:bg-slate-950 text-gray-900 dark:text-slate-100">
        <ThemeProvider>
          <div className="flex min-h-screen flex-col">
            <Header />
            <main className="flex-1">{children}</main>
          </div>
        </ThemeProvider>
      </body>
    </html>
  );
}



