# Synapse — Graph RAG vs Naive RAG evaluation

RAGAS-style metrics (faithfulness, answer relevancy, context precision, context recall), scored 0–1 (higher = better).

## Aggregate scores

| Split | System | Faithfulness | Answer Relevancy | Context Precision | Context Recall |
|-------|--------|--------------|------------------|-------------------|----------------|
| Overall | **Naive RAG** | 1.00 | 0.86 | 0.95 | 0.71 |
| Overall | **Graph RAG** | 0.96 | 0.89 | 0.56 | 0.92 |
| Multi-hop only | **Naive RAG** | 1.00 | 0.83 | 0.90 | 0.48 |
| Multi-hop only | **Graph RAG** | 1.00 | 0.88 | 0.54 | 0.92 |
| Single-hop only | **Naive RAG** | 1.00 | 0.90 | 1.00 | 0.93 |
| Single-hop only | **Graph RAG** | 0.93 | 0.90 | 0.58 | 0.93 |

## Per-question detail

### `mh01` (multi-hop) — Name AI models created by people who previously worked at OpenAI.

_Reference:_ Anthropic was founded by former OpenAI employees Dario Amodei and Daniela Amodei, and developed the Claude family of large language models (including Constitutional AI and Claude Gov).

**Naive RAG** — faith `1.00`, relev `0.77`, prec `0.80`, recall `0.17`

> Based on the provided context, I can identify the following AI models created by people who previously worked at OpenAI:
> 
> 1. Llama 2 - This model is developed by Meta, which is an active organization in the AI open-source community [Artificial intelligence].
> 2. Stable Diffusion - This model is also developed by an organization that is likely related to the AI open-source community, as it is mentioned alongside other open-weight models like Llama 2 and Mistral [Artificial intelligence].
> 
> Note that the context does not provide information on the specific AI models created by individuals who previously worked at OpenAI. However, it does mention that OpenAI's release of ChatGPT in November 2022 has been credited with catalyzing the AI boom, and widespread interest in generative AI [OpenAI].

**Graph RAG** — faith `1.00`, relev `0.85`, prec `0.18`, recall `0.83`

> Based on the KNOWLEDGE GRAPH FACTS and EXCERPTS, here are the AI models created by people who previously worked at OpenAI:
> 
> - Claude: Developed by Anthropic, which was founded by Dario Amodei and Daniela Amodei, both of whom worked at OpenAI. [Anthropic]
> - Claude Gov: Developed by Anthropic, which was founded by Dario Amodei and Daniela Amodei, both of whom worked at OpenAI. [Anthropic]
> - Constitutional AI: Developed by Anthropic, which was founded by Dario Amodei and Daniela Amodei, both of whom worked at OpenAI. [Anthropic]
> 
> Note that the KNOWLEDGE GRAPH FACTS state that Dario Amodei and Daniela Amodei worked at OpenAI, and the EXCERPTS do not provide information on the specific AI models developed by them. However, the KNOWLEDGE GRAPH FACTS do provide information on the AI models developed by Anthropic, which was founded by Dario Amodei and Daniela Amodei.

---

### `mh02` (multi-hop) — Where did Anthropic's founders previously work?

_Reference:_ Anthropic's co-founders Dario and Daniela Amodei previously worked at OpenAI, where Dario was Vice President of Research.

**Naive RAG** — faith `1.00`, relev `0.89`, prec `1.00`, recall `0.80`

> Anthropic's founders, the Amodei siblings (Dario and Daniela Amodei), previously worked at OpenAI [Anthropic].

**Graph RAG** — faith `1.00`, relev `0.91`, prec `0.90`, recall `1.00`

> Anthropic's founders, siblings Daniela Amodei and Dario Amodei, previously worked at OpenAI. [Anthropic]

---

### `sh01` (single-hop) — Who founded OpenAI?

_Reference:_ OpenAI was founded in 2015 by Elon Musk, Sam Altman, Ilya Sutskever, Greg Brockman, John Schulman, and others.

**Naive RAG** — faith `1.00`, relev `0.90`, prec `1.00`, recall `0.86`

> OpenAI was founded by Elon Musk, Sam Altman, Ilya Sutskever, Greg Brockman, Trevor Blackwell, Vicki Cheung, Andrej Karpathy, Durk Kingma, John Schulman, Pamela Vagata, and Wojciech Zaremba, with Elon Musk and Sam Altman as the co-chairs [OpenAI].

**Graph RAG** — faith `0.86`, relev `0.90`, prec `0.24`, recall `0.86`

> OpenAI was founded by Elon Musk, Sam Altman, Ilya Sutskever, Greg Brockman, Trevor Blackwell, Vicki Cheung, Andrej Karpathy, Durk Kingma, John Schulman, Pamela Vagata, and Wojciech Zaremba, with Elon Musk and Sam Altman as the co-chairs [OpenAI].

---

### `sh02` (single-hop) — Where is Anthropic headquartered?

_Reference:_ Anthropic is headquartered in San Francisco.

**Naive RAG** — faith `1.00`, relev `0.89`, prec `1.00`, recall `1.00`

> Anthropic is headquartered in San Francisco [Anthropic].

**Graph RAG** — faith `1.00`, relev `0.89`, prec `0.93`, recall `1.00`

> Anthropic is headquartered in San Francisco. 
> 
> [Anthropic]

---
