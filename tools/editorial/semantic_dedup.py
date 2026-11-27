"""3-layer semantic anti-repetition engine (CPU-only transformers/ST embeddings + TF-IDF fallback)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .memory_store import EditorialMemoryStore, slugify

DEFAULT_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_CACHE_VERSION = f"{DEFAULT_MODEL_NAME}#v2"
BLOCK_THRESHOLD = 0.72
WARN_THRESHOLD = 0.55

_ENCODER_CACHE: dict[str, tuple[Any | None, str]] = {}

_SYNONYM_REPLACEMENTS = (
    (r"\b(\d+)\s*milh[oõ]es\b", r"\1m"),
    (r"\bplacas?\s+de\s+v[ií]deo\b", "gpu"),
    (r"\btreine\b|\btreinando\b|\btreinamento\b", "treino"),
    (r"\bintelig[eê]ncia\s+artificial\b|\bm[oó]delos?\s+de\s+linguagem\b", "ia llm"),
    (r"\bcompacto\b|\bpequeno\b", "mini"),
    (r"\bgrafos?\b", "graph"),
)


def _normalize_text(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"https?://\S+", " ", lowered)
    for pat, repl in _SYNONYM_REPLACEMENTS:
        lowered = re.sub(pat, repl, lowered)
    lowered = re.sub(r"[^a-z0-9à-ÿ/_\-\s]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _extract_tokens(text: str, entities: list[str] | None = None, keywords: list[str] | None = None) -> set[str]:
    tokens: set[str] = set()
    for val in (entities or []) + (keywords or []):
        norm = _normalize_text(val)
        if len(norm) >= 3:
            tokens.add(norm)
            if "/" in norm:
                tokens.add(norm.split("/")[-1])
    for m in re.findall(r"[a-z0-9][a-z0-9\-_]{2,}/[a-z0-9][a-z0-9\-_.]{1,}", (text or "").lower()):
        tokens.add(m)
        tokens.add(m.split("/")[-1])
    for w in _normalize_text(text).split():
        if len(w) >= 5 and w not in {"inteligencia", "artificial", "modelo", "modelos", "codigo", "aberto", "projeto", "sistema"}:
            tokens.add(w)
    return tokens


class _TransformersCPUEncoder:
    """Zero-VRAM CPU encoder using transformers AutoModel + mean pooling (avoids datasets dependency)."""

    def __init__(self, model_name: str):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to("cpu")
        self.model.eval()

    def encode(self, texts: list[str], convert_to_numpy: bool = True, normalize_embeddings: bool = True) -> np.ndarray:
        encoded = self.tokenizer(texts, padding=True, truncation=True, max_length=256, return_tensors="pt")
        with self.torch.no_grad():
            out = self.model(**encoded)
            mask = encoded["attention_mask"].unsqueeze(-1).expand(out.last_hidden_state.size()).float()
            summed = self.torch.sum(out.last_hidden_state * mask, 1)
            counts = self.torch.clamp(mask.sum(1), min=1e-9)
            emb = summed / counts
            if normalize_embeddings:
                emb = self.torch.nn.functional.normalize(emb, p=2, dim=1)
        arr = emb.cpu().numpy().astype(np.float32)
        return arr


def _load_dense_encoder(model_name: str = DEFAULT_MODEL_NAME) -> tuple[Any | None, str]:
    """Load dense encoder strictly on CPU (0 GPU VRAM). Returns (encoder, backend_label)."""
    if os.environ.get("EDITORIAL_NO_ST") == "1":
        return None, "tfidf_fallback"
    if model_name in _ENCODER_CACHE:
        return _ENCODER_CACHE[model_name]
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        model = SentenceTransformer(model_name, device="cpu")
        _ENCODER_CACHE[model_name] = (model, f"st_cpu:{model_name}")
        return _ENCODER_CACHE[model_name]
    except Exception:
        pass
    try:
        enc = _TransformersCPUEncoder(model_name)
        _ENCODER_CACHE[model_name] = (enc, f"transformers_cpu:{model_name}")
        return _ENCODER_CACHE[model_name]
    except Exception:
        _ENCODER_CACHE[model_name] = (None, "tfidf_fallback")
        return None, "tfidf_fallback"


def _build_doc_text(title: str, summary: str = "", entities: list[str] | None = None, keywords: list[str] | None = None) -> str:
    clean_title = re.sub(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+:\s*", "", title.strip())
    clean_summary = summary.strip()
    if clean_summary.startswith("Publicado em "):
        clean_summary = ""
    parts = [clean_title or title.strip()]
    if clean_summary:
        parts.append(clean_summary)
    elif keywords:
        parts.append(", ".join(keywords[:6]))
    return " — ".join(parts)


class SemanticDeduplicator:
    """Checks novelty of a candidate topic against published/active editorial items."""

    def __init__(self, store: EditorialMemoryStore, model_name: str = DEFAULT_MODEL_NAME):
        self.store = store
        self.model_name = model_name

    def _compute_embedding(self, text: str) -> tuple[np.ndarray | None, str]:
        encoder, backend = _load_dense_encoder(self.model_name)
        if encoder is None:
            return None, backend
        vec = encoder.encode([text], convert_to_numpy=True, normalize_embeddings=True)[0]
        return vec.astype(np.float32), backend

    def check_candidate(
        self,
        *,
        title: str,
        summary: str = "",
        entities: list[str] | None = None,
        keywords: list[str] | None = None,
        allow_update: bool = False,
        supersedes_id: int | None = None,
        compare_states: tuple[str, ...] = (
            "publicado",
            "produzido",
            "roteirizado",
            "aprovado",
            "apresentado",
            "selecionado",
        ),
    ) -> dict[str, Any]:
        rows = list(self.store.fetch_raw_embeddings(states=compare_states))
        cand_slug = slugify(title)
        cand_tokens = _extract_tokens(f"{title} {summary}", entities, keywords)
        cand_doc = _build_doc_text(title, summary, entities, keywords)

        exact_hits: list[dict[str, Any]] = []
        existing_docs: list[str] = []

        for r in rows:
            try:
                r_entities = json.loads(r["entities_json"] or "[]")
                r_keywords = json.loads(r["keywords_json"] or "[]")
            except Exception:
                r_entities, r_keywords = [], []
            existing_docs.append(_build_doc_text(r["title"], r["summary"], r_entities, r_keywords))

            r_tokens = _extract_tokens(f"{r['title']} {r['summary']}", r_entities, r_keywords)
            shared_entities = sorted(tok for tok in cand_tokens if "/" in tok and tok in r_tokens)
            slug_match = cand_slug == r["slug"]
            exact_entity_match = bool(shared_entities) or any(
                _normalize_text(e) in {_normalize_text(x) for x in r_entities}
                for e in (entities or [])
                if len(_normalize_text(e)) >= 4
            )
            if slug_match or exact_entity_match:
                exact_hits.append(
                    {
                        "id": r["id"],
                        "slug": r["slug"],
                        "title": r["title"],
                        "state": r["state"],
                        "video_id": r["video_id"],
                        "score": 1.0,
                        "layer": "L1_exact_entity",
                        "shared_entities": shared_entities or entities or [],
                    }
                )

        # Layer 2: Dense CPU embeddings (preferred) with cached SQLite float32 blobs, else synonym-normalized TF-IDF
        semantic_hits: list[dict[str, Any]] = []
        backend_used = "tfidf_fallback"
        cand_vec, backend = self._compute_embedding(cand_doc)
        max_dense_sim = 0.0

        if rows and cand_vec is not None:
            backend_used = backend
            encoder, _ = _load_dense_encoder(self.model_name)
            cache_key = EMBEDDING_CACHE_VERSION
            uncached_indices = [
                idx
                for idx, r in enumerate(rows)
                if r["embedding_blob"] is None or r["embedding_model"] != cache_key
            ]
            if uncached_indices:
                batch_vecs = encoder.encode(
                    [existing_docs[i] for i in uncached_indices],
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
                for pos, idx in enumerate(uncached_indices):
                    vec = batch_vecs[pos].astype(np.float32)
                    self.store.save_embedding(int(rows[idx]["id"]), vec.tobytes(), cache_key)

            refetched = {int(r["id"]): r["embedding_blob"] for r in self.store.fetch_raw_embeddings(states=compare_states)}
            for r in rows:
                blob = refetched.get(int(r["id"]))
                if not blob:
                    continue
                vec = np.frombuffer(blob, dtype=np.float32)
                if vec.shape == cand_vec.shape:
                    sim = float(np.dot(cand_vec, vec))
                    if sim > max_dense_sim:
                        max_dense_sim = sim
                    if sim >= WARN_THRESHOLD:
                        semantic_hits.append(
                            {
                                "id": r["id"],
                                "slug": r["slug"],
                                "title": r["title"],
                                "state": r["state"],
                                "video_id": r["video_id"],
                                "score": round(sim, 4),
                                "layer": "L2_dense_cpu",
                            }
                        )
        elif rows:
            norm_cand = _normalize_text(cand_doc)
            norm_docs = [_normalize_text(d) for d in existing_docs]
            vec_word = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, lowercase=True)
            vec_char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, lowercase=True)
            corpus = [norm_cand] + norm_docs
            m_w = vec_word.fit_transform(corpus)
            m_c = vec_char.fit_transform(corpus)
            sims_w = cosine_similarity(m_w[0:1], m_w[1:])[0]
            sims_c = cosine_similarity(m_c[0:1], m_c[1:])[0]
            for idx, r in enumerate(rows):
                sim = float(0.45 * sims_w[idx] + 0.55 * sims_c[idx])
                if sim > max_dense_sim:
                    max_dense_sim = sim
                if sim >= 0.34:
                    semantic_hits.append(
                        {
                            "id": r["id"],
                            "slug": r["slug"],
                            "title": r["title"],
                            "state": r["state"],
                            "video_id": r["video_id"],
                            "score": round(sim, 4),
                            "layer": "L2_tfidf_fallback",
                        }
                    )

        merged: dict[int, dict[str, Any]] = {}
        for h in semantic_hits + exact_hits:
            iid = int(h["id"])
            prev = merged.get(iid)
            if prev is None or h["score"] > prev["score"]:
                merged[iid] = h

        matches = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        top_score = max(matches[0]["score"] if matches else 0.0, max_dense_sim)

        effective_block = BLOCK_THRESHOLD if backend_used != "tfidf_fallback" else 0.46
        effective_warn = WARN_THRESHOLD if backend_used != "tfidf_fallback" else 0.34
        is_exact = any(m["layer"] == "L1_exact_entity" for m in matches)
        blocked = bool(is_exact or top_score >= effective_block)
        warning = bool((not blocked) and (top_score >= effective_warn))

        decision = "NOVO"
        if blocked:
            if allow_update and supersedes_id is not None:
                decision = "ATUALIZACAO_SUBSTANCIAL"
                blocked = False
            else:
                decision = "BLOQUEADO_DUPLICATA"
        elif warning:
            decision = "ALERTA_SEMELHANCA"

        return {
            "decision": decision,
            "blocked": blocked,
            "warning": warning,
            "allow_update_applied": bool(allow_update and supersedes_id is not None),
            "supersedes_id": supersedes_id,
            "backend": backend_used,
            "top_similarity": round(top_score, 4),
            "novelty_score": round(max(0.0, 1.0 - top_score), 4),
            "matches": matches[:5],
        }
