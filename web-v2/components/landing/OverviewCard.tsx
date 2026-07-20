import Image from "next/image";
import { withBasePath } from "@/lib/base-path";

/**
 * Featured link to the one-page WOBD overview (PDF), shown beneath the
 * "How WOBD works" diagram in the hero. Thumbnail previews the poster and
 * opens the full PDF in a new tab.
 */
export function OverviewCard() {
  return (
    <a
      href={withBasePath("/wobd-overview.pdf")}
      target="_blank"
      rel="noopener noreferrer"
      className="group mt-3 flex items-center gap-4 rounded-2xl border border-okn-border bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:border-okn-borderPurple hover:shadow-md"
    >
      <Image
        src={withBasePath("/wobd-overview.png")}
        alt="WOBD one-page overview (PDF)"
        width={1515}
        height={1960}
        className="h-28 w-auto flex-shrink-0 rounded-md border border-okn-border shadow-sm"
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[15px] font-semibold text-okn-navbar">One-page overview</span>
          <span className="rounded-full border border-okn-border bg-okn-bgMuted px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-okn-textMuted">
            PDF
          </span>
        </div>
        <p className="mt-1.5 text-[13px] leading-relaxed text-okn-textMuted">
          The vision, how the federation is wired together, and three worked cross-domain examples.
        </p>
        <span className="mt-2 inline-flex items-center text-[13px] font-semibold text-okn-primary group-hover:underline">
          View the one-pager
          <span aria-hidden className="ml-1">&#8599;</span>
        </span>
      </div>
    </a>
  );
}
