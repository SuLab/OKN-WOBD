import { HeroSearch } from "@/components/landing/HeroSearch";
import { ExampleQuestions } from "@/components/landing/ExampleQuestions";

export default function LandingPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-80px)] px-4 bg-white dark:bg-slate-950">
      <div className="w-full max-w-3xl space-y-8">
        <div className="text-center space-y-4">
          <h1 className="text-5xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
            Ask WOBD...
          </h1>
          <p className="text-slate-600 dark:text-slate-400 text-lg">
            Query biomedical datasets with template-based, LLM-generated, or user-generated SPARQL
          </p>
        </div>

        <HeroSearch />

        <ExampleQuestions />
      </div>
    </div>
  );
}



