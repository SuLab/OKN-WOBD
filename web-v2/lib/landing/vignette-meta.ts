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
      "Explore disease mechanisms, related genes, and candidate datasets for diabetic nephropathy across Proto-OKN graphs.",
    icon: Stethoscope,
    iconColor: "text-rose-600 dark:text-rose-400",
  },
  {
    slug: "pfas-compounds",
    tag: "PFAS compounds",
    title: "PFAS compounds",
    description:
      "Trace per- and polyfluoroalkyl substances from chemical identifiers through environmental exposure and health outcome graphs.",
    icon: FlaskConical,
    iconColor: "text-sky-600 dark:text-sky-400",
  },
  {
    slug: "terpene-biosynthesis",
    tag: "Terpene biosynthesis",
    title: "Terpene biosynthesis",
    description:
      "Walk biosynthetic pathways, enzymes, and source organisms for terpene production across knowledge graphs.",
    icon: Leaf,
    iconColor: "text-emerald-600 dark:text-emerald-400",
  },
];

const META_BY_SLUG = Object.fromEntries(VIGNETTE_META.map((v) => [v.slug, v]));

export function getVignetteMeta(slug: string): VignetteMetaItem | undefined {
  return META_BY_SLUG[slug];
}
