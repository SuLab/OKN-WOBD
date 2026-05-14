import Link from "next/link";
import type { ReactNode } from "react";

export interface BreadcrumbItem {
  label: ReactNode;
  href?: string;
}

export function Breadcrumbs({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav aria-label="Breadcrumb" className="self-start">
      <ol className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm text-slate-600 dark:text-slate-400">
        {items.map((item, i) => {
          const isLast = i === items.length - 1;
          const content =
            item.href && !isLast ? (
              <Link
                href={item.href}
                className="hover:text-okn-primary hover:underline"
              >
                {item.label}
              </Link>
            ) : (
              <span
                aria-current={isLast ? "page" : undefined}
                className={
                  isLast ? "font-medium text-slate-700 dark:text-slate-300" : ""
                }
              >
                {item.label}
              </span>
            );
          return (
            <li key={i} className="flex items-center gap-x-1.5">
              {content}
              {!isLast && (
                <span aria-hidden className="text-slate-400">
                  /
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
