import "./globals.css";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { withBasePath } from "@/lib/base-path";

const SITE_TITLE = "WOBD — Web of Biological Data";
const SITE_DESCRIPTION =
  "Federated queries across biomedical knowledge graphs and dataset metadata. WOBD connects the NIAID Data Ecosystem with 30+ Proto-OKN knowledge graphs, queryable via a templated UI or your AI assistant. NSF-funded.";

export const metadata: Metadata = {
  title: {
    default: SITE_TITLE,
    template: "%s · WOBD",
  },
  description: SITE_DESCRIPTION,
  icons: {
    icon: [{ url: withBasePath("/okn-favicon.png"), type: "image/png" }],
  },
  openGraph: {
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    type: "website",
    locale: "en_US",
    siteName: "WOBD · OKN",
    images: [
      {
        url: "/wobd-logo.png",
        alt: "WOBD — Web of Biological Data",
      },
    ],
  },
  twitter: {
    card: "summary",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: ["/wobd-logo.png"],
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="light">
      <body className="min-h-dvh bg-okn-bgSoft text-okn-textStrong">
        <div className="flex min-h-dvh flex-col">
          <Header />
          <main className="flex min-h-0 flex-1 flex-col">{children}</main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
