import Image from "next/image";
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
import { withBasePath } from "@/lib/base-path";

const RENCI_URL = "https://renci.org/";
const ONAI_URL = "https://www.onai.com/";

export function Footer() {
  return (
    <footer className="border-t border-okn-border bg-okn-bgMuted">
      <div className="mx-auto flex w-full max-w-[1100px] flex-col items-center gap-5 px-6 py-6 md:flex-row md:items-center md:justify-between md:gap-6">
        <div className="text-center text-sm text-okn-textMuted md:text-left">
          Powered by{" "}
          <a
            href={RENCI_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-okn-textStrong transition hover:text-okn-primary hover:underline"
          >
            UNC Chapel Hill / RENCI
          </a>{" "}
          and{" "}
          <a
            href={ONAI_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium text-okn-textStrong transition hover:text-okn-primary hover:underline"
          >
            Onai Inc.
          </a>
        </div>

        <a
          href={NSF_AWARD_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3 text-sm text-okn-textMuted transition hover:text-okn-primary"
        >
          <Image
            src={withBasePath("/nsf-logo.png")}
            alt="National Science Foundation"
            width={120}
            height={40}
            className="h-10 w-auto"
          />
          <span className="font-medium">NSF Award #{NSF_AWARD_NUMBER}</span>
        </a>

        <nav
          className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-sm text-okn-textMuted md:justify-end"
          aria-label="WOBD footer links"
        >
          <Link
            href="/about"
            className="transition hover:text-okn-primary hover:underline"
          >
            About
          </Link>
          <a
            href={GITHUB_REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="transition hover:text-okn-primary hover:underline"
          >
            GitHub
          </a>
          <a
            href={GITHUB_ISSUES_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="transition hover:text-okn-primary hover:underline"
          >
            Issues
          </a>
          <a
            href={FRINK_OKN_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="transition hover:text-okn-primary hover:underline"
          >
            FRINK OKN
          </a>
          <a
            href={FRINK_REGISTRY_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="transition hover:text-okn-primary hover:underline"
          >
            FRINK Registry
          </a>
          <a
            href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(CONTACT_SUBJECT)}`}
            className="transition hover:text-okn-primary hover:underline"
          >
            Contact
          </a>
        </nav>
      </div>
    </footer>
  );
}
