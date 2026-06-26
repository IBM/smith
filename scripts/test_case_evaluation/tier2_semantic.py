# Copyright 2026 Smith authors
# SPDX-License-Identifier: Apache-2.0

import numpy as np
from dataclasses import dataclass
from typing import List, Dict
from sentence_transformers import SentenceTransformer, CrossEncoder
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class Tier2Result:
    predicted_label: str
    confidence: float
    reason: str
    nli_scores: Dict[str, float]
    embedding_similarity: float


class Tier2Evaluator:
    def __init__(
        self,
        embedding_model="all-MiniLM-L6-v2",
        nli_model="cross-encoder/nli-deberta-v3-base",
    ):
        print("Loading embedding model...")
        self.embed_model = SentenceTransformer(embedding_model)
        print("Loading NLI model...")
        self.nli_model = CrossEncoder(nli_model)

    def _embed(self, texts: List[str]) -> np.ndarray:
        return self.embed_model.encode(texts, show_progress_bar=False)

    def _nli_predict(
        self, premise_hypothesis_pairs: List[List[str]]
    ) -> List[Dict[str, float]]:
        if not premise_hypothesis_pairs:
            return []
        scores = self.nli_model.predict(premise_hypothesis_pairs, apply_softmax=True)
        results = []
        for score_row in scores:
            results.append(
                {
                    "contradiction": float(score_row[0]),
                    "entailment": float(score_row[1]),
                    "neutral": float(score_row[2]),
                }
            )
        return results

    def evaluate_generated(
        self,
        user_inputs: List[str],
        conditions: List[str],
        guidances: List[str],
        assigned_labels: List[str],
    ) -> List[Tier2Result]:
        """Evaluate generated cases using condition-based NLI.

        For generated cases, we check: does user_input entail its stated condition?
        High entailment = case is well-constructed, label is trustworthy.
        High contradiction = user_input doesn't match its condition, likely mislabeled.
        """
        input_embeddings = self._embed(user_inputs)
        guidance_embeddings = self._embed(guidances)
        embed_sims = []
        for i in range(len(user_inputs)):
            sim = cosine_similarity([input_embeddings[i]], [guidance_embeddings[i]])[0][
                0
            ]
            embed_sims.append(float(sim))

        # NLI: does user_input match its condition?
        nli_pairs = []
        for user_input, condition in zip(user_inputs, conditions):
            premise = f"The user asks: {user_input}"
            hypothesis = f"The request is about: {condition}"
            nli_pairs.append([premise, hypothesis])

        nli_results = self._nli_predict(nli_pairs)

        results = []
        for i in range(len(user_inputs)):
            entailment = nli_results[i]["entailment"]
            contradiction = nli_results[i]["contradiction"]
            neutral = nli_results[i]["neutral"]

            # High entailment: user_input matches its condition -> label is correct
            # High contradiction: user_input doesn't match condition -> likely mislabeled
            if entailment > 0.7:
                predicted_label = assigned_labels[i]
                confidence = 0.30 * max(embed_sims[i], 0) + 0.70 * entailment
                reason = f"User input entails condition '{conditions[i][:50]}' (ent={entailment:.3f})"
            elif contradiction > 0.5:
                # Condition doesn't match input — predict opposite label
                predicted_label = (
                    "disallow" if assigned_labels[i] == "allow" else "allow"
                )
                confidence = 0.30 * max(embed_sims[i], 0) + 0.70 * contradiction
                reason = f"User input contradicts condition '{conditions[i][:50]}' (contra={contradiction:.3f})"
            else:
                # Neutral — uncertain
                predicted_label = assigned_labels[i]
                confidence = 0.30 * max(embed_sims[i], 0) + 0.70 * 0.4
                reason = f"NLI uncertain for condition '{conditions[i][:50]}' (ent={entailment:.3f}, contra={contradiction:.3f}, neutral={neutral:.3f})"

            nli_scores = {
                "entailment": entailment,
                "contradiction": contradiction,
                "neutral": neutral,
            }

            results.append(
                Tier2Result(
                    predicted_label=predicted_label,
                    confidence=confidence,
                    reason=reason,
                    nli_scores=nli_scores,
                    embedding_similarity=embed_sims[i],
                )
            )

        return results

    def evaluate_promptfoo(
        self, user_inputs: List[str], guidances: List[str], assigned_labels: List[str]
    ) -> List[Tier2Result]:
        """Evaluate promptfoo cases using guidance-based NLI.

        Promptfoo cases are all malicious/disallow. Check if user_input clearly
        violates or is unrelated to the matched guidance.
        """
        input_embeddings = self._embed(user_inputs)
        guidance_embeddings = self._embed(guidances)
        embed_sims = []
        for i in range(len(user_inputs)):
            sim = cosine_similarity([input_embeddings[i]], [guidance_embeddings[i]])[0][
                0
            ]
            embed_sims.append(float(sim))

        # NLI: does user_input contradict the guidance?
        nli_pairs = []
        for user_input, guidance in zip(user_inputs, guidances):
            premise = f"The user asks: {user_input}"
            hypothesis = guidance
            nli_pairs.append([premise, hypothesis])

        nli_results = self._nli_predict(nli_pairs)

        results = []
        for i in range(len(user_inputs)):
            entailment = nli_results[i]["entailment"]
            contradiction = nli_results[i]["contradiction"]
            neutral = nli_results[i]["neutral"]

            # For promptfoo (all labeled disallow):
            # - High contradiction with guidance: clearly violates -> disallow is correct (high conf)
            # - High neutral: unrelated to guidance -> likely disallow (malicious/off-topic) but lower conf
            # - High entailment: aligns with guidance -> might be mislabeled? (low conf, escalate)
            if contradiction > 0.5:
                predicted_label = "disallow"
                confidence = 0.30 * max(embed_sims[i], 0) + 0.70 * contradiction
                reason = f"Clearly violates guidance (contra={contradiction:.3f})"
            elif neutral > 0.7 and embed_sims[i] < 0.4:
                # Unrelated to guidance + low embedding similarity = off-topic malicious
                predicted_label = "disallow"
                confidence = 0.30 * max(embed_sims[i], 0) + 0.70 * 0.75
                reason = f"Unrelated to guidance (neutral={neutral:.3f}, embed_sim={embed_sims[i]:.3f})"
            elif entailment > 0.5:
                # Seems to align with guidance — suspicious for a disallow case
                predicted_label = "allow"
                confidence = 0.30 * max(embed_sims[i], 0) + 0.70 * entailment
                reason = f"Entails guidance — may be mislabeled (ent={entailment:.3f})"
            else:
                # Ambiguous
                predicted_label = "disallow"
                confidence = 0.30 * max(embed_sims[i], 0) + 0.70 * 0.4
                reason = f"NLI ambiguous (ent={entailment:.3f}, contra={contradiction:.3f}, neutral={neutral:.3f})"

            nli_scores = {
                "entailment": entailment,
                "contradiction": contradiction,
                "neutral": neutral,
            }

            results.append(
                Tier2Result(
                    predicted_label=predicted_label,
                    confidence=confidence,
                    reason=reason,
                    nli_scores=nli_scores,
                    embedding_similarity=embed_sims[i],
                )
            )

        return results
