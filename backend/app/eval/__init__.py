"""RAGAS-style evaluation of Naive RAG vs Graph RAG.

Implements faithfulness, answer relevancy, context precision, and context
recall using our existing LLM provider as the judge. The methodology follows
the RAGAS paper (Es et al. 2023) — we don't depend on the `ragas` package so
the project stays light and the metric logic is fully transparent for review.
"""
from .dataset import EVAL_SET, EvalQuestion
from .metrics import compute_metrics

__all__ = ["EVAL_SET", "EvalQuestion", "compute_metrics"]
