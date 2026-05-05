import { FlaskConical, Leaf, Stethoscope, type LucideIcon } from "lucide-react";

export interface VignetteMetaItem {
  slug: string;
  tag: string;
  title: string;
  description: string;
  icon: LucideIcon;
  iconColor: string;
}

export const VIGNETTE_META: VignetteMetaItem[] = [
  {
    slug: "diabetic-nephropathy",
    tag: "Diabetic nephropathy",
    title: "Diabetic nephropathy",
    description:
      "End-to-end differential expression from one chat — ontology resolution, ARCHS4 sample classification, and a method comparison that surfaced an interferon signaling signal pooled analysis missed.",
    icon: Stethoscope,
    iconColor: "text-rose-600 dark:text-rose-400",
  },
  {
    slug: "pfas-compounds",
    tag: "PFAS compounds",
    title: "PFAS compounds",
    description:
      "Convergent evidence across seven knowledge graphs that 'safer' replacement PFAS chemicals (GenX, ADONA) hit the same molecular target as the legacy compounds they replaced.",
    icon: FlaskConical,
    iconColor: "text-sky-600 dark:text-sky-400",
  },
  {
    slug: "terpene-biosynthesis",
    tag: "Terpene biosynthesis",
    title: "Terpene biosynthesis",
    description:
      "Federated discovery across plant pathway evidence, organism-spanning expression coverage, and microbial host-engineering datasets — starting material for a synthetic biology team within minutes.",
    icon: Leaf,
    iconColor: "text-emerald-600 dark:text-emerald-400",
  },
];

const META_BY_SLUG = Object.fromEntries(VIGNETTE_META.map((v) => [v.slug, v]));

export function getVignetteMeta(slug: string): VignetteMetaItem | undefined {
  return META_BY_SLUG[slug];
}
