"""RAGAS-style metrics.

Methodology (Es et al. 2023):

- **Faithfulness** — fraction of atomic claims in the answer that are supported
  by the retrieved context. Catches hallucinations.
- **Answer relevancy** — how on-topic the answer is. We back-generate plausible
  questions from the answer, embed them, and average their cosine similarity
  to the original question. Off-topic answers yield low-similarity questions.
- **Context precision** — fraction of retrieved context items judged relevant
  to the question. Measures retrieval quality.
- **Context recall** — fraction of reference-answer facts covered by the
  retrieved context. Requires a ground-truth answer.

Every score is in [0, 1]; higher is better.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..embeddings import Embedder
from .judge import Judge


@dataclass
class MetricResult:
    faithfulness: float
    answer_relevancy: float
    context_precision: float
    context_recall: float


def _cosine(a: list[float], b: list[float]) -> float:
    # Embedder normalizes vectors, so dot product == cosine similarity.
    return sum(x * y for x, y in zip(a, b))


def faithfulness(judge: Judge, answer: str, context_blob: str) -> float:
    claims = judge.extract_claims(answer)
    if not claims:
        return 0.0
    supported = sum(1 for c in claims if judge.claim_supported(c, context_blob))
    return supported / len(claims)


def answer_relevancy(judge: Judge, embedder: Embedder, question: str, answer: str, n: int = 3) -> float:
    generated = judge.generate_questions_for(answer, n=n)
    if not generated:
        return 0.0
    q_vec = embedder.embed_query(question)
    sims = [_cosine(q_vec, embedder.embed_query(g)) for g in generated]
    # Clamp to [0, 1] — normalized vectors give cosine in [-1, 1] but in practice
    # semantically related sentences land well above 0.
    return max(0.0, min(1.0, sum(sims) / len(sims)))


def context_precision(judge: Judge, question: str, contexts: list[str]) -> float:
    if not contexts:
        return 0.0
    hits = sum(1 for c in contexts if judge.context_relevant(question, c))
    return hits / len(contexts)


def context_recall(judge: Judge, reference: str, context_blob: str) -> float:
    facts = judge.extract_reference_facts(reference)
    if not facts:
        return 0.0
    covered = sum(1 for f in facts if judge.fact_covered(f, context_blob))
    return covered / len(facts)


def compute_metrics(
    judge: Judge,
    embedder: Embedder,
    *,
    question: str,
    answer: str,
    reference: str,
    contexts: list[str],
) -> MetricResult:
    """Run all four metrics for one (question, answer, contexts) triple."""
    context_blob = "\n\n".join(contexts) if contexts else ""
    return MetricResult(
        faithfulness=faithfulness(judge, answer, context_blob),
        answer_relevancy=answer_relevancy(judge, embedder, question, answer),
        context_precision=context_precision(judge, question, contexts),
        context_recall=context_recall(judge, reference, context_blob),
    )
