import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";

export const metadata: Metadata = {
  title: "WOBD",
  description:
    "Web of Biological Data (WOBD) - connecting datasets from the NIAID Data Ecosystem Portal to other resources within the Proto-OKN.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="light">
      <body className="min-h-dvh bg-white text-gray-900">
        <div className="flex min-h-dvh flex-col">
          <Header />
          <main className="flex min-h-0 flex-1 flex-col">{children}</main>
          <Footer />
        </div>
      </body>
    </html>
  );
}



