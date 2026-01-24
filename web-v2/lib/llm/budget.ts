// Shared API key budget tracker ($20/mo cap for OpenAI and Anthropic)

interface BudgetRecord {
  month: string; // "2025-01"
  spent_usd: number;
  calls: Array<{
    timestamp: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    lane: string;
  }>;
}

// In-memory store (in production, use a database)
let budgetStore: BudgetRecord | null = null;

// Price table (USD per 1K tokens) - update as needed
const PRICE_TABLE: Record<string, { input: number; output: number }> = {
  // OpenAI models
  "gpt-4o": { input: 0.0025, output: 0.01 },
  "gpt-4o-mini": { input: 0.00015, output: 0.0006 },
  "gpt-4-turbo": { input: 0.01, output: 0.03 },
  "gpt-4": { input: 0.03, output: 0.06 },
  "gpt-3.5-turbo": { input: 0.0005, output: 0.0015 },
  "gpt-4.1": { input: 0.0025, output: 0.01 }, // Assuming same as gpt-4o
  // Anthropic models
  "claude-sonnet-4-5": { input: 0.003, output: 0.015 }, // $3/$15 per 1M tokens
  "claude-3-5-sonnet-20241022": { input: 0.003, output: 0.015 },
  "claude-3-haiku-20240307": { input: 0.00025, output: 0.00125 },
};

const SHARED_BUDGET_USD = parseFloat(process.env.SHARED_BUDGET_USD || "1");
const SHARED_BUDGET_STOP_USD = parseFloat(process.env.SHARED_BUDGET_STOP_USD || "0.95");

function getCurrentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function getBudget(): BudgetRecord {
  const currentMonth = getCurrentMonth();

  if (!budgetStore || budgetStore.month !== currentMonth) {
    // Reset for new month
    budgetStore = {
      month: currentMonth,
      spent_usd: 0,
      calls: [],
    };
  }

  return budgetStore;
}

function calculateCost(
  model: string,
  inputTokens: number,
  outputTokens: number
): number {
  const prices = PRICE_TABLE[model] || PRICE_TABLE["gpt-3.5-turbo"];
  const inputCost = (inputTokens / 1000) * prices.input;
  const outputCost = (outputTokens / 1000) * prices.output;
  return inputCost + outputCost;
}

export function checkBudget(): { allowed: boolean; remaining?: number; error?: string } {
  const budget = getBudget();

  if (budget.spent_usd >= SHARED_BUDGET_STOP_USD) {
    return {
      allowed: false,
      error: `SHARED_BUDGET_EXCEEDED: Shared quota has been reached ($${budget.spent_usd.toFixed(2)} of $${SHARED_BUDGET_USD}). Add your own key to continue.`,
    };
  }

  return {
    allowed: true,
    remaining: SHARED_BUDGET_USD - budget.spent_usd,
  };
}

export function recordUsage(
  model: string,
  inputTokens: number,
  outputTokens: number,
  lane: string
): { cost: number; remaining: number } {
  const budget = getBudget();
  const cost = calculateCost(model, inputTokens, outputTokens);

  budget.spent_usd += cost;
  budget.calls.push({
    timestamp: new Date().toISOString(),
    model,
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    cost_usd: cost,
    lane,
  });

  return {
    cost,
    remaining: Math.max(0, SHARED_BUDGET_USD - budget.spent_usd),
  };
}

export function getBudgetStatus(): { spent: number; limit: number; remaining: number; month: string } {
  const budget = getBudget();
  return {
    spent: budget.spent_usd,
    limit: SHARED_BUDGET_USD,
    remaining: Math.max(0, SHARED_BUDGET_USD - budget.spent_usd),
    month: budget.month,
  };
}






