"""The demo corpus: Wikipedia articles on the modern AI field.

These titles are chosen to be densely interconnected (researchers <-> labs <->
models <-> techniques) so that multi-hop questions have answers spread across
multiple articles — exactly where Graph RAG beats a vector-only baseline.

Edit this list to grow or focus the corpus. Titles must match Wikipedia page
titles (the loader will report any that don't resolve).
"""
from __future__ import annotations

CORPUS: list[str] = [
    # Core concepts
    "Artificial intelligence",
    "Machine learning",
    "Deep learning",
    "Artificial neural network",
    "Backpropagation",
    "Reinforcement learning",
    # Architectures / techniques
    "Transformer (deep learning architecture)",
    "Attention (machine learning)",
    "Convolutional neural network",
    "Recurrent neural network",
    "Generative adversarial network",
    # Models
    "Large language model",
    "Generative pre-trained transformer",
    "BERT (language model)",
    "AlphaGo",
    "ImageNet",
    # Organizations
    "OpenAI",
    "DeepMind",
    "Anthropic",
    "Google Brain",
    # People
    "Geoffrey Hinton",
    "Yann LeCun",
    "Yoshua Bengio",
    "Ilya Sutskever",
    "Demis Hassabis",
    "Andrew Ng",
    "Fei-Fei Li",
]
