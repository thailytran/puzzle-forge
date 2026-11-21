"""AI layer: the AIGateway port + provider adapters (docs/SPEC.md §6, INTEGRATION_HALOSPARK.md §8).

Golden rule 1: AI writes words, clues, story and judgements — never a puzzle answer."""

from forge.ai.base import AIError, AIResult, BudgetExceeded, ProviderError
from forge.ai.gateway import AIGateway, RoutedGateway

__all__ = ["AIError", "AIGateway", "AIResult", "BudgetExceeded", "ProviderError", "RoutedGateway"]
