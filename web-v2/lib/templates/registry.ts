import type { ContextPack } from "@/lib/context-packs/types";
import type { Intent } from "@/types";
import {
  DATASET_SEARCH_TEMPLATE_ID,
  datasetSearchTemplate,
  buildDatasetSearchQuery,
} from "./templates/dataset_search";
import {
  ENTITY_LOOKUP_TEMPLATE_ID,
  entityLookupTemplate,
  buildEntityLookupQuery,
} from "./templates/entity_lookup";
import {
  GENE_EXPRESSION_DATASET_SEARCH_TEMPLATE_ID,
  geneExpressionDatasetSearchTemplate,
  buildGeneExpressionDatasetSearchQuery,
} from "./templates/gene_expression_dataset_search";
import {
  GENE_EXPRESSION_GENES_IN_EXPERIMENT_TEMPLATE_ID,
  geneExpressionGenesInExperimentTemplate,
  buildGeneExpressionGenesInExperimentQuery,
} from "./templates/gene_expression_genes_in_experiment";
import {
  GENE_EXPRESSION_EXPERIMENTS_FOR_GENE_TEMPLATE_ID,
  geneExpressionExperimentsForGeneTemplate,
  buildGeneExpressionExperimentsForGeneQuery,
} from "./templates/gene_expression_experiments_for_gene";
import {
  GENE_EXPRESSION_GENE_CROSS_DATASET_SUMMARY_TEMPLATE_ID,
  geneExpressionGeneCrossDatasetSummaryTemplate,
  buildGeneExpressionGeneCrossDatasetSummaryQuery,
} from "./templates/gene_expression_gene_cross_dataset_summary";
import {
  GENE_EXPRESSION_GENES_AGREEMENT_TEMPLATE_ID,
  geneExpressionGenesAgreementTemplate,
  buildGeneExpressionGenesAgreementQuery,
} from "./templates/gene_expression_genes_agreement";
import {
  GENE_EXPRESSION_GENES_DISCORDANCE_TEMPLATE_ID,
  geneExpressionGenesDiscordanceTemplate,
  buildGeneExpressionGenesDiscordanceQuery,
} from "./templates/gene_expression_genes_discordance";

export type TemplateId =
  | typeof DATASET_SEARCH_TEMPLATE_ID
  | typeof ENTITY_LOOKUP_TEMPLATE_ID
  | typeof GENE_EXPRESSION_DATASET_SEARCH_TEMPLATE_ID
  | typeof GENE_EXPRESSION_GENES_IN_EXPERIMENT_TEMPLATE_ID
  | typeof GENE_EXPRESSION_EXPERIMENTS_FOR_GENE_TEMPLATE_ID
  | typeof GENE_EXPRESSION_GENE_CROSS_DATASET_SUMMARY_TEMPLATE_ID
  | typeof GENE_EXPRESSION_GENES_AGREEMENT_TEMPLATE_ID
  | typeof GENE_EXPRESSION_GENES_DISCORDANCE_TEMPLATE_ID;

type TemplateGenerator = (intent: Intent, pack: ContextPack) => string | Promise<string>;

interface RegisteredTemplate {
  id: TemplateId;
  generate: TemplateGenerator;
}

const TEMPLATE_REGISTRY: Record<string, RegisteredTemplate> = {
  [DATASET_SEARCH_TEMPLATE_ID]: {
    id: DATASET_SEARCH_TEMPLATE_ID,
    generate: buildDatasetSearchQuery,
  },
  [ENTITY_LOOKUP_TEMPLATE_ID]: {
    id: ENTITY_LOOKUP_TEMPLATE_ID,
    generate: buildEntityLookupQuery,
  },
  [GENE_EXPRESSION_DATASET_SEARCH_TEMPLATE_ID]: {
    id: GENE_EXPRESSION_DATASET_SEARCH_TEMPLATE_ID,
    generate: buildGeneExpressionDatasetSearchQuery,
  },
  [GENE_EXPRESSION_GENES_IN_EXPERIMENT_TEMPLATE_ID]: {
    id: GENE_EXPRESSION_GENES_IN_EXPERIMENT_TEMPLATE_ID,
    generate: buildGeneExpressionGenesInExperimentQuery,
  },
  [GENE_EXPRESSION_EXPERIMENTS_FOR_GENE_TEMPLATE_ID]: {
    id: GENE_EXPRESSION_EXPERIMENTS_FOR_GENE_TEMPLATE_ID,
    generate: buildGeneExpressionExperimentsForGeneQuery,
  },
  [GENE_EXPRESSION_GENE_CROSS_DATASET_SUMMARY_TEMPLATE_ID]: {
    id: GENE_EXPRESSION_GENE_CROSS_DATASET_SUMMARY_TEMPLATE_ID,
    generate: buildGeneExpressionGeneCrossDatasetSummaryQuery,
  },
  [GENE_EXPRESSION_GENES_AGREEMENT_TEMPLATE_ID]: {
    id: GENE_EXPRESSION_GENES_AGREEMENT_TEMPLATE_ID,
    generate: buildGeneExpressionGenesAgreementQuery,
  },
  [GENE_EXPRESSION_GENES_DISCORDANCE_TEMPLATE_ID]: {
    id: GENE_EXPRESSION_GENES_DISCORDANCE_TEMPLATE_ID,
    generate: buildGeneExpressionGenesDiscordanceQuery,
  },
};

export function getTemplateForIntent(intent: Intent): RegisteredTemplate | null {
  // Use intent.task directly; later this can use richer routing logic
  const id = intent.task as TemplateId;
  const entry = TEMPLATE_REGISTRY[id];
  return entry || null;
}

export function listTemplateDefinitionsForPack(pack: ContextPack) {
  // Combine pack.templates metadata with built-in ones if needed
  return pack.templates ?? [
    datasetSearchTemplate,
    entityLookupTemplate,
    geneExpressionDatasetSearchTemplate,
    geneExpressionGenesInExperimentTemplate,
    geneExpressionExperimentsForGeneTemplate,
    geneExpressionGeneCrossDatasetSummaryTemplate,
    geneExpressionGenesAgreementTemplate,
    geneExpressionGenesDiscordanceTemplate,
  ];
}







