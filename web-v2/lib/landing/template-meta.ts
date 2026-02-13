import {
  Database,
  FlaskConical,
  List,
  Search,
  BarChart2,
  GitMerge,
  ArrowLeftRight,
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
    id: "gene_expression_experiments_for_gene",
    titlePart1: "Experiments",
    titlePart2: " for gene",
    description: "Find experiments where a gene is differentially expressed",
    icon: Search,
    iconColor: "text-[var(--niaid-link)]",
    blurb: "Find gene expression experiments or contrasts where a gene is differentially expressed.",
    buttonLabel: "Run query",
  },
  {
    id: "gene_expression_gene_cross_dataset_summary",
    titlePart1: "Gene summary",
    titlePart2: " across experiments",
    description: "Summarize a gene's DE evidence across experiments (per contrast)",
    icon: BarChart2,
    iconColor: "text-emerald-600 dark:text-emerald-400",
    blurb: "Summarize a gene's differential expression evidence across experiments.",
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
