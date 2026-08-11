from pydantic import BaseModel


class CostBudget(BaseModel):
    max_tokens_per_run: int = 40_000
    max_usd_per_run: float = 2.00
    warn_at_ratio: float = 0.8


class CostBudgetExceeded(RuntimeError):
    pass


class RunCostTracker:
    """One instance per pipeline run (graph.py's RunState), not a global --
    a shared tracker across concurrent runs would let one brand's spend
    trip another's budget."""

    def __init__(self, budget: CostBudget | None = None):
        self.budget = budget or CostBudget()
        self.tokens_spent = 0
        self.usd_spent = 0.0

    def record(self, tokens: int, usd: float) -> None:
        self.tokens_spent += tokens
        self.usd_spent += usd
        if self.usd_spent >= self.budget.max_usd_per_run or self.tokens_spent >= self.budget.max_tokens_per_run:
            raise CostBudgetExceeded(
                f"run exceeded budget: ${self.usd_spent:.4f}/{self.budget.max_usd_per_run} usd, "
                f"{self.tokens_spent}/{self.budget.max_tokens_per_run} tokens"
            )
