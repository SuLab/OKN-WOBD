import { QueryCards } from "@/components/landing/QueryCards";

export default function LandingPage() {
  return (
    <div
      className="min-h-[calc(100vh-80px)] px-4 py-8 sm:py-12"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex flex-col items-center">
        <div className="text-center mb-8">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Web of Biological Data
          </h1>
          <p className="mt-2 text-slate-600 dark:text-slate-400">
            Find biomedical datasets and gene expression results with template-based search
          </p>
        </div>

        <QueryCards />
      </div>
    </div>
  );
}
