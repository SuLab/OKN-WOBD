import { QueryCards } from "@/components/landing/QueryCards";

export default function LandingPage() {
  return (
    <div
      className="flex flex-1 flex-col items-center px-4 pb-8 sm:pb-10"
      style={{ backgroundColor: "var(--niaid-page-bg)" }}
    >
      <div className="flex w-full max-w-5xl flex-1 flex-col items-center gap-5 sm:gap-6 pt-[max(1.25rem,11dvh)] sm:pt-[max(1.5rem,14dvh)]">
        <div className="text-center">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Web of Biological Data
          </h1>
          <p className="mt-1.5 text-sm sm:text-base text-slate-600 dark:text-slate-400">
            Find biomedical datasets and gene expression results with template-based search
          </p>
        </div>

        <QueryCards />
      </div>
    </div>
  );
}
