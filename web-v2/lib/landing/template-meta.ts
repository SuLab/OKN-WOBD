import {
  Database,
  FlaskConical,
  List,
  Layers,
  GitMerge,
  ArrowLeftRight,
  Pill,
  type LucideIcon,
} from "lucide-react";
import { DEFAULT_MONDO_DESCENDANT_EXPAND_CAP } from "@/lib/ontology/mondo-descendants-ols";

export interface TemplateMetaItem {
  id: string;
  titlePart1: string;
  titlePart2: string;
  /** One-line summary: query cards (landing) and /template/[id] page title + results label. */
  description: string;
  icon: LucideIcon;
  iconColor: string;
  /** Short blurb shown on the single-template page (e.g. "This query finds datasets in NDE that...") */
  blurb?: string;
  /** Button label (e.g. "Search Datasets" for dataset_search) */
  buttonLabel: string;
}

export const TEMPLATE_META: TemplateMetaItem[] = [
  {
    id: "dataset_search",
    titlePart1: "Datasets",
    titlePart2: " by keywords",
    description:
      "Find NDE datasets by keywords and/or filters for health condition, host species, and pathogen species.",
    icon: Database,
    iconColor: "text-blue-600 dark:text-blue-400",
    blurb: `Search the NDE graph: use keywords and/or open "Filters / Advanced" for health condition, pathogen species, and host species. Health condition matches the MONDO term(s) you pick exactly unless you enable "Include MONDO subclasses" (then OLS adds subclass IRIs and labels, up to a shared cap of ${DEFAULT_MONDO_DESCENDANT_EXPAND_CAP} for both the SPARQL filter and highlighting). Optionally limit to datasets whose metadata mentions a GEO series (GSE) or E-GEOD accession. You need to enter at least one keyword or a filter. All filled filters apply together (AND).`,
    buttonLabel: "Search Datasets",
  },
  {
    id: "gene_expression_gene_level_de_per_contrast",
    titlePart1: "Gene-level differential expression",
    titlePart2: " per contrast",
    description:
      "Across GXA experiments: gene(s), contrasts, direction (up/down), log2FC, and adjusted p-value in one result set",
    icon: Layers,
    iconColor: "text-cyan-600 dark:text-cyan-400",
    blurb: "One query for one or more genes: experiment and contrast identifiers, optional up/down filter, and a direction column alongside log2FC and adjusted p-value.",
    buttonLabel: "Run query",
  },
  {
    id: "drug_datasets",
    titlePart1: "Datasets",
    titlePart2: " for a drug",
    description:
      "Find NDE datasets for diseases treated by a drug and optionally limit to datasets with gene expression data.",
    icon: Pill,
    iconColor: "text-teal-600 dark:text-teal-400",
    blurb: "Enter a drug name (e.g. tocilizumab) to find NDE datasets for diseases treated by the drug.",
    buttonLabel: "Find datasets",
  },
  {
    id: "gene_expression_genes_agreement",
    titlePart1: "Genes",
    titlePart2: " in agreement",
    description: "Find genes DE in the same direction across multiple experiments",
    icon: GitMerge,
    iconColor: "text-violet-600 dark:text-violet-400",
    blurb: "Find genes that are differentially expressed in the same direction across multiple experiments.",
    buttonLabel: "Run query",
  },
  {
    id: "gene_expression_genes_discordance",
    titlePart1: "Genes",
    titlePart2: " in discordance",
    description: "Find genes DE in opposite directions across contrasts",
    icon: ArrowLeftRight,
    iconColor: "text-amber-600 dark:text-amber-400",
    blurb: "Find genes that are differentially expressed in opposite directions across contrasts.",
    buttonLabel: "Run query",
  },
];

/** Not shown on landing cards; kept for direct /template/... URLs and dashboard flows. */
const HIDDEN_TEMPLATE_META: TemplateMetaItem[] = [
  {
    id: "gene_expression_dataset_search",
    titlePart1: "Gene expression",
    titlePart2: " experiments",
    description: "List experiments (datasets) with differential expression results",
    icon: FlaskConical,
    iconColor: "text-purple-600 dark:text-purple-400",
    blurb: "List gene expression experiments that have differential expression results. Optionally filter by organism, tissue, or factor.",
    buttonLabel: "Run query",
  },
  {
    id: "gene_expression_genes_in_experiment",
    titlePart1: "Genes",
    titlePart2: " in experiment",
    description: "List differentially expressed genes for a given experiment (per contrast)",
    icon: List,
    iconColor: "text-slate-600 dark:text-slate-400",
    blurb: "List differentially expressed genes for a given gene expression experiment (e.g. E-GEOD-76).",
    buttonLabel: "Run query",
  },
  {
    id: "geo_dataset_search",
    titlePart1: "NCBI GEO",
    titlePart2: " datasets in NDE",
    description:
      "Find NCBI GEO datasets in NDE (GSE only), with optional keywords and filters for health condition, host species, and pathogen species.",
    icon: Database,
    iconColor: "text-emerald-600 dark:text-emerald-400",
    blurb:
      "Results are limited to GEO series (GSE identifiers). For the full NDE dataset search (including GEO when metadata matches), use Datasets by keywords from the home page.",
    buttonLabel: "Search GEO",
  },
];

const META_BY_ID = Object.fromEntries(
  [...TEMPLATE_META, ...HIDDEN_TEMPLATE_META].map((m) => [m.id, m])
);

export function getTemplateMeta(templateId: string): TemplateMetaItem | undefined {
  return META_BY_ID[templateId];
}
