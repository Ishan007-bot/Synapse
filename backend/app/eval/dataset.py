"""The evaluation question set.

We weight toward multi-hop questions — answers that require connecting facts
across multiple Wikipedia articles. That's where Graph RAG's structural
advantage should show up clearly versus the vector-only baseline. Single-hop
questions are included as a sanity check that the graph layer doesn't hurt
the easy cases.

Each entry has a short reference answer used for the **context recall** metric
(we ask the judge whether each atomic fact in the reference is covered by the
retrieved context). The references are intentionally concise — they list the
salient facts, not every nuance from the underlying article.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    question: str
    reference: str
    type: str  # "multi-hop" | "single-hop"


EVAL_SET: list[EvalQuestion] = [
    # ── Multi-hop ─────────────────────────────────────────────────────────
    # Graph RAG should outperform here: the answer requires chaining facts
    # across separate Wikipedia articles.
    EvalQuestion(
        id="mh01",
        type="multi-hop",
        question="Name AI models created by people who previously worked at OpenAI.",
        reference=(
            "Anthropic was founded by former OpenAI employees Dario Amodei and "
            "Daniela Amodei, and developed the Claude family of large language "
            "models (including Constitutional AI and Claude Gov)."
        ),
    ),
    EvalQuestion(
        id="mh02",
        type="multi-hop",
        question="Where did Anthropic's founders previously work?",
        reference=(
            "Anthropic's co-founders Dario and Daniela Amodei previously worked "
            "at OpenAI, where Dario was Vice President of Research."
        ),
    ),
    EvalQuestion(
        id="mh03",
        type="multi-hop",
        question="Which AI researchers received the 2018 Turing Award and what for?",
        reference=(
            "Yoshua Bengio, Geoffrey Hinton, and Yann LeCun jointly received the "
            "2018 Turing Award for their conceptual and engineering breakthroughs "
            "in deep neural networks."
        ),
    ),
    EvalQuestion(
        id="mh04",
        type="multi-hop",
        question="Which AI models has DeepMind been involved in developing?",
        reference=(
            "DeepMind has developed AlphaGo and AlphaZero (game-playing systems), "
            "AlphaFold (protein structure prediction), and Gemini (large language model)."
        ),
    ),
    EvalQuestion(
        id="mh05",
        type="multi-hop",
        question="Which research lab did Ilya Sutskever work at before OpenAI?",
        reference=(
            "Ilya Sutskever worked at Google Brain (after Google acquired "
            "DNNResearch) before co-founding OpenAI in 2015."
        ),
    ),
    EvalQuestion(
        id="mh06",
        type="multi-hop",
        question="Who is Demis Hassabis and what lab does he lead?",
        reference=(
            "Demis Hassabis is a British AI researcher and entrepreneur, "
            "co-founder and CEO of Google DeepMind."
        ),
    ),
    # ── Single-hop ────────────────────────────────────────────────────────
    # Answer lives in one article. Both systems should do well; included to
    # confirm graph retrieval doesn't degrade easy cases.
    EvalQuestion(
        id="sh01",
        type="single-hop",
        question="Who founded OpenAI?",
        reference=(
            "OpenAI was founded in 2015 by Elon Musk, Sam Altman, Ilya "
            "Sutskever, Greg Brockman, John Schulman, and others."
        ),
    ),
    EvalQuestion(
        id="sh02",
        type="single-hop",
        question="Where is Anthropic headquartered?",
        reference="Anthropic is headquartered in San Francisco.",
    ),
    EvalQuestion(
        id="sh03",
        type="single-hop",
        question="What is BERT?",
        reference=(
            "BERT (Bidirectional Encoder Representations from Transformers) is a "
            "transformer-based language model developed by Google."
        ),
    ),
]
