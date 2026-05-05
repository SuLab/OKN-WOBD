import Link from "next/link";
import {
  FRINK_OKN_URL,
  FRINK_REGISTRY_URL,
  GITHUB_REPO_URL,
  GITHUB_ISSUES_URL,
  CONTACT_EMAIL,
  CONTACT_SUBJECT,
  NSF_AWARD_NUMBER,
  NSF_AWARD_URL,
} from "@/lib/site-config";

export function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white px-6 py-4">
      <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-2">
        <nav
          className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 text-sm text-slate-600"
          aria-label="Footer links"
        >
          <Link
            href="/about"
            className="hover:text-[var(--niaid-link)] hover:underline"
          >
            About
          </Link>
          <span aria-hidden className="text-slate-400">
            ·
          </span>
          <a
            href={GITHUB_REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--niaid-link)] hover:underline"
          >
            GitHub
          </a>
          <span aria-hidden className="text-slate-400">
            ·
          </span>
          <a
            href={GITHUB_ISSUES_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--niaid-link)] hover:underline"
          >
            Issues
          </a>
          <span aria-hidden className="text-slate-400">
            ·
          </span>
          <a
            href={FRINK_OKN_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--niaid-link)] hover:underline"
          >
            FRINK OKN
          </a>
          <span aria-hidden className="text-slate-400">
            ·
          </span>
          <a
            href={FRINK_REGISTRY_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--niaid-link)] hover:underline"
          >
            FRINK Registry
          </a>
          <span aria-hidden className="text-slate-400">
            ·
          </span>
          <a
            href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(CONTACT_SUBJECT)}`}
            className="hover:text-[var(--niaid-link)] hover:underline"
          >
            Contact
          </a>
        </nav>
        <p className="text-xs text-slate-500">
          Supported by NSF award{" "}
          <a
            href={NSF_AWARD_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-[var(--niaid-link)] hover:underline"
          >
            #{NSF_AWARD_NUMBER}
          </a>
          .
        </p>
      </div>
    </footer>
  );
}
