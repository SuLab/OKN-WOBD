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

export interface TemplateMetaItem {
  id: string;
  titlePart1: string;
  titlePart2: string;
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
    id: "drug_datasets",
    titlePart1: "Datasets",
    titlePart2: " for a drug",
    description: "Find NDE datasets for diseases treated by a drug",
    icon: Pill,
    iconColor: "text-teal-600 dark:text-teal-400",
    blurb: "Enter a drug name (e.g. tocilizumab). We look up diseases it treats in Wikidata, then find NDE datasets. Optionally restrict to GEO/gene expression and include GXA/SPOKE-GeneLab links for matching experiments.",
    buttonLabel: "Find datasets",
  },
  {
    id: "dataset_search",
    titlePart1: "Datasets",
    titlePart2: " by keywords",
    description: "Find datasets by keywords, disease, organism, or drugs",
    icon: Database,
    iconColor: "text-blue-600 dark:text-blue-400",
    blurb: "This query finds datasets in NDE that study a specific disease, organism, or other criteria.",
    buttonLabel: "Search Datasets",
  },
  {
    id: "geo_dataset_search",
    titlePart1: "NCBI GEO",
    titlePart2: " datasets in NDE",
    description: "Find NCBI GEO datasets in NDE by keywords, disease, or organism",
    icon: Database,
    iconColor: "text-emerald-600 dark:text-emerald-400",
    blurb: "Search only NCBI GEO datasets within the NDE graph. Same schema.org as other NDE resources; results are restricted to datasets with GSE identifiers or GEO URLs.",
    buttonLabel: "Search GEO",
  },
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

const META_BY_ID = Object.fromEntries(TEMPLATE_META.map((m) => [m.id, m]));

export function getTemplateMeta(templateId: string): TemplateMetaItem | undefined {
  return META_BY_ID[templateId];
}
