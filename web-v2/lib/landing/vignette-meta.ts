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
      "A disease-genomics workflow that combines ontology resolution, sample discovery, differential expression, and enrichment in one auditable chat.",
    icon: Stethoscope,
    iconColor: "text-rose-600 dark:text-rose-400",
  },
  {
    slug: "pfas-compounds",
    tag: "PFAS compounds",
    title: "PFAS compounds",
    description:
      "A public-health synthesis across environmental monitoring, toxicology mechanisms, disease associations, and dataset metadata.",
    icon: FlaskConical,
    iconColor: "text-sky-600 dark:text-sky-400",
  },
  {
    slug: "terpene-biosynthesis",
    tag: "Terpene biosynthesis",
    title: "Terpene biosynthesis",
    description:
      "A translational-discovery workflow linking pathway evidence, expression coverage, and host-engineering datasets for biomanufacturing.",
    icon: Leaf,
    iconColor: "text-emerald-600 dark:text-emerald-400",
  },
];

const META_BY_SLUG = Object.fromEntries(VIGNETTE_META.map((v) => [v.slug, v]));

export function getVignetteMeta(slug: string): VignetteMetaItem | undefined {
  return META_BY_SLUG[slug];
}
