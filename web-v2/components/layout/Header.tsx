import Image from "next/image";
import Link from "next/link";

import { withBasePath } from "@/lib/base-path";

type OknNavLink = {
  label: string;
  href: string;
  /** Hide on mobile to keep the top band single-row. */
  desktopOnly?: boolean;
};

const OKN_HOME = "https://okn.us";
const OKN_NAV: OknNavLink[] = [
  { label: "Fabric", href: "https://registry.okn.us/" },
  { label: "Registry", href: "https://registry.okn.us/registry/" },
  { label: "SPARQL", href: "https://apps.okn.us/", desktopOnly: true },
  { label: "MCP", href: "https://okn.us/mcp" },
  { label: "About", href: "https://www.proto-okn.net/", desktopOnly: true },
];

export function Header() {
  return (
    <>
      {/* OKN parent band */}
      <div className="w-full bg-[var(--okn-navbar)] text-white">
        <div className="mx-auto flex h-14 w-full max-w-[1200px] items-center justify-between gap-4 px-4 sm:px-6">
          <a
            href={OKN_HOME}
            className="flex shrink-0 items-center gap-2 rounded outline-offset-4 transition hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-white"
            aria-label="Open Knowledge Network — okn.us"
          >
            <Image
              src={withBasePath("/okn-logo.svg")}
              alt=""
              width={32}
              height={32}
              priority
              className="h-8 w-auto"
              style={{ filter: "brightness(0) invert(1)" }}
            />
            <span className="hidden text-[18px] font-bold leading-none sm:inline">
              Open Knowledge Network
            </span>
            <span className="text-[18px] font-bold leading-none sm:hidden">OKN</span>
          </a>
          <nav
            className="flex items-center gap-1 text-[15px] font-medium"
            aria-label="OKN site"
          >
            {OKN_NAV.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className={`rounded-md px-2.5 py-1.5 text-white/90 transition hover:bg-white/15 hover:text-white${
                  link.desktopOnly ? " hidden md:inline-block" : ""
                }`}
              >
                {link.label}
              </a>
            ))}
            <a
              href={`${OKN_HOME}/login`}
              className="ml-1 rounded-md border border-white/30 px-3 py-1.5 text-[15px] font-medium text-white/90 transition hover:bg-white/15 hover:text-white"
            >
              Sign in
            </a>
          </nav>
        </div>
      </div>

      {/* WOBD subheader */}
      <header className="w-full border-b border-okn-border bg-white">
        <div className="mx-auto flex w-full max-w-[1200px] flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-2.5 sm:px-6">
          <Link
            href="/"
            className="flex shrink-0 items-center gap-2.5 rounded-md outline-offset-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--okn-primary)]"
          >
            <Image
              src={withBasePath("/wobd-logo.png")}
              alt="WOBD — Web of Biological Data"
              width={54}
              height={45}
              priority
              className="h-8 w-auto"
            />
            <span className="text-base font-semibold text-okn-textStrong">
              WOBD
              <span className="ml-1.5 hidden text-sm font-normal text-okn-textMuted sm:inline">
                · Web of Biological Data
              </span>
            </span>
          </Link>
          <nav
            className="flex flex-wrap items-center gap-x-1 gap-y-1 text-sm font-medium text-okn-textStrong sm:text-[15px]"
            aria-label="WOBD"
          >
            <Link
              href="/"
              className="rounded px-2 py-1 transition hover:bg-okn-primaryHoverBg hover:text-okn-primary"
            >
              Home
            </Link>
            <Link
              href="/queries"
              className="rounded px-2 py-1 transition hover:bg-okn-primaryHoverBg hover:text-okn-primary"
            >
              <span className="sm:hidden">Queries</span>
              <span className="hidden sm:inline">Guided queries</span>
            </Link>
            <Link
              href="/mcp"
              className="rounded px-2 py-1 transition hover:bg-okn-primaryHoverBg hover:text-okn-primary"
            >
              <span className="sm:hidden">MCP</span>
              <span className="hidden sm:inline">AI assistant access</span>
            </Link>
            <Link
              href="/about"
              className="rounded px-2 py-1 transition hover:bg-okn-primaryHoverBg hover:text-okn-primary"
            >
              <span className="sm:hidden">About</span>
              <span className="hidden sm:inline">Growth plan</span>
            </Link>
          </nav>
        </div>
      </header>
    </>
  );
}
