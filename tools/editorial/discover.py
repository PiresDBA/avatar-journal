"""Multi-source live discovery across GitHub, arXiv, Hugging Face, and Hacker News."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .env_loader import load_project_env, token_status
from .memory_store import EditorialMemoryStore, slugify
from .programs import EditorialProgram, get_program
from .semantic_dedup import SemanticDeduplicator

HTTP_TIMEOUT = 15
USER_AGENT = "avatar-journal-editorial-chief/1.0 (https://github.com/)"


def _github_headers() -> dict[str, str]:
    load_project_env()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_github(program: EditorialProgram, limit: int, days: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    since_date = (datetime.now(timezone.utc) - timedelta(days=max(7, days))).strftime("%Y-%m-%d")
    items: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"ok": True, "auth": bool(os.environ.get("GITHUB_TOKEN", "").strip()), "errors": []}
    headers = _github_headers()

    for raw_q in program.github_queries:
        query = re.sub(r"pushed:>=\d{4}-\d{2}-\d{2}", f"pushed:>={since_date}", raw_q)
        try:
            resp = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": query, "sort": "stars", "order": "desc", "per_page": min(limit + 3, 15)},
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
            meta["rate_remaining"] = resp.headers.get("X-RateLimit-Remaining")
            if resp.status_code != 200:
                meta["errors"].append(f"GitHub HTTP {resp.status_code}: {resp.text[:160]}")
                continue
            data = resp.json()
            for repo in data.get("items", []):
                full_name = repo.get("full_name", "")
                desc = repo.get("description") or ""
                stars = int(repo.get("stargazers_count") or 0)
                forks = int(repo.get("forks_count") or 0)
                topics = list(repo.get("topics") or [])[:6]
                lang = repo.get("language") or ""
                items.append(
                    {
                        "slug": slugify(full_name),
                        "title": f"{full_name}: {desc[:110]}" if desc else full_name,
                        "summary": f"{desc} | {stars:,} estrelas, {forks:,} forks, linguagem {lang or 'N/A'}.".strip(),
                        "program": program.key,
                        "category": program.category_label,
                        "primary_source": "github",
                        "source_url": repo.get("html_url", ""),
                        "entities": [full_name] + ([full_name.split("/")[-1]] if "/" in full_name else []),
                        "keywords": topics + ([lang.lower()] if lang else []),
                        "metrics": {
                            "stars": stars,
                            "forks": forks,
                            "language": lang,
                            "updated_at": repo.get("pushed_at", ""),
                        },
                        "raw_score": min(100.0, (stars / 250.0) + (forks / 60.0)),
                    }
                )
        except Exception as exc:
            meta["errors"].append(f"GitHub exception: {exc}")
    if meta["errors"] and not items:
        meta["ok"] = False
    return items, meta


def _fetch_arxiv(program: EditorialProgram, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"ok": True, "errors": []}
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for q in program.arxiv_queries:
        try:
            resp = requests.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": q,
                    "start": 0,
                    "max_results": min(limit + 2, 10),
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
                headers={"User-Agent": USER_AGENT},
                timeout=HTTP_TIMEOUT,
            )
            if resp.status_code != 200:
                meta["errors"].append(f"arXiv HTTP {resp.status_code}")
                continue
            root = ET.fromstring(resp.text)
            for entry in root.findall("atom:entry", ns):
                raw_title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                title = re.sub(r"\s+", " ", raw_title)
                raw_summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()
                summary = re.sub(r"\s+", " ", raw_summary)[:320]
                url = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()
                published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
                arxiv_id = url.rstrip("/").split("/")[-1]
                authors = [
                    (a.findtext("atom:name", default="", namespaces=ns) or "").strip()
                    for a in entry.findall("atom:author", ns)[:3]
                ]
                if not title or not url:
                    continue
                items.append(
                    {
                        "slug": slugify(f"arxiv-{arxiv_id}-{title[:48]}"),
                        "title": title,
                        "summary": summary,
                        "program": program.key,
                        "category": program.category_label,
                        "primary_source": "arxiv",
                        "source_url": url,
                        "entities": [f"arXiv:{arxiv_id}"] + authors[:2],
                        "keywords": [c.strip() for c in q.split() if "cat:" in c] or ["arxiv", "research"],
                        "metrics": {"arxiv_id": arxiv_id, "published": published, "authors": authors},
                        "raw_score": 55.0,
                    }
                )
        except Exception as exc:
            meta["errors"].append(f"arXiv exception: {exc}")
    if meta["errors"] and not items:
        meta["ok"] = False
    return items, meta


def _fetch_huggingface(program: EditorialProgram, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"ok": True, "errors": []}

    if program.hf_include_papers:
        try:
            resp = requests.get(
                "https://huggingface.co/api/daily_papers",
                params={"limit": min(limit + 3, 12)},
                headers={"User-Agent": USER_AGENT},
                timeout=HTTP_TIMEOUT,
            )
            if resp.status_code == 200:
                for row in resp.json()[: limit + 2]:
                    paper = row.get("paper") or {}
                    pid = paper.get("id") or ""
                    title = (paper.get("title") or row.get("title") or "").strip()
                    summary = re.sub(r"\s+", " ", (paper.get("summary") or "").strip())[:300]
                    upvotes = int(paper.get("upvotes") or row.get("numComments") or 0)
                    if not title:
                        continue
                    items.append(
                        {
                            "slug": slugify(f"hf-paper-{pid or title[:48]}"),
                            "title": title,
                            "summary": summary or f"Hugging Face Daily Paper ({upvotes} upvotes).",
                            "program": program.key,
                            "category": program.category_label,
                            "primary_source": "huggingface_papers",
                            "source_url": f"https://huggingface.co/papers/{pid}" if pid else "https://huggingface.co/papers",
                            "entities": [f"hf:{pid}"] if pid else [],
                            "keywords": ["huggingface", "paper", "research"],
                            "metrics": {"upvotes": upvotes, "paper_id": pid},
                            "raw_score": min(95.0, 45.0 + upvotes),
                        }
                    )
            else:
                meta["errors"].append(f"HF papers HTTP {resp.status_code}")
        except Exception as exc:
            meta["errors"].append(f"HF papers exception: {exc}")

    if program.hf_include_models:
        try:
            resp = requests.get(
                "https://huggingface.co/api/models",
                params={"sort": "trendingScore", "direction": "-1", "limit": min(limit + 3, 12)},
                headers={"User-Agent": USER_AGENT},
                timeout=HTTP_TIMEOUT,
            )
            if resp.status_code == 200:
                for m in resp.json()[: limit + 2]:
                    mid = m.get("id") or m.get("modelId") or ""
                    if not mid:
                        continue
                    likes = int(m.get("likes") or 0)
                    downloads = int(m.get("downloads") or 0)
                    pipeline = m.get("pipeline_tag") or "model"
                    tags = list(m.get("tags") or [])[:5]
                    items.append(
                        {
                            "slug": slugify(mid),
                            "title": f"{mid} ({pipeline})",
                            "summary": f"Modelo em alta no Hugging Face ({pipeline}) | {likes} likes, {downloads:,} downloads.",
                            "program": program.key,
                            "category": program.category_label,
                            "primary_source": "huggingface_models",
                            "source_url": f"https://huggingface.co/{mid}",
                            "entities": [mid, mid.split("/")[-1]],
                            "keywords": [pipeline] + [str(t).lower() for t in tags[:4]],
                            "metrics": {"likes": likes, "downloads": downloads, "pipeline_tag": pipeline},
                            "raw_score": min(95.0, 40.0 + likes / 5.0),
                        }
                    )
            else:
                meta["errors"].append(f"HF models HTTP {resp.status_code}")
        except Exception as exc:
            meta["errors"].append(f"HF models exception: {exc}")

    if meta["errors"] and not items:
        meta["ok"] = False
    return items, meta


def _fetch_hackernews(program: EditorialProgram, limit: int, days: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    meta: dict[str, Any] = {"ok": True, "errors": []}
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=max(14, days))).timestamp())

    for q in program.hn_queries:
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={
                    "query": q,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff_ts}",
                    "hitsPerPage": min(limit + 3, 10),
                },
                headers={"User-Agent": USER_AGENT},
                timeout=HTTP_TIMEOUT,
            )
            if resp.status_code != 200:
                meta["errors"].append(f"HN HTTP {resp.status_code}")
                continue
            for hit in resp.json().get("hits", []):
                title = (hit.get("title") or "").strip()
                url = (hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}").strip()
                points = int(hit.get("points") or 0)
                comments = int(hit.get("num_comments") or 0)
                if not title or points < 15:
                    continue
                items.append(
                    {
                        "slug": slugify(f"hn-{hit.get('objectID')}-{title[:48]}"),
                        "title": title,
                        "summary": f"Discussao tecnica no Hacker News ({points} pts, {comments} comentarios).",
                        "program": program.key,
                        "category": program.category_label,
                        "primary_source": "hackernews",
                        "source_url": url,
                        "entities": [],
                        "keywords": ["hackernews"] + [w.lower() for w in q.split()[:3]],
                        "metrics": {
                            "hn_points": points,
                            "hn_comments": comments,
                            "hn_discussion": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                        },
                        "raw_score": min(92.0, (points / 8.0) + (comments / 10.0)),
                    }
                )
        except Exception as exc:
            meta["errors"].append(f"HN exception: {exc}")
    if meta["errors"] and not items:
        meta["ok"] = False
    return items, meta


def discover_candidates(
    *,
    program_key: str | None = None,
    limit: int = 8,
    days: int = 30,
    save: bool = False,
    store: EditorialMemoryStore | None = None,
) -> dict[str, Any]:
    """Run live multi-source discovery, score novelty vs DB, and optionally persist candidates."""
    load_project_env()
    program = get_program(program_key)
    db = store or EditorialMemoryStore()
    dedup = SemanticDeduplicator(db)

    all_raw: list[dict[str, Any]] = []
    source_health: dict[str, Any] = {}

    if "github" in program.preferred_sources:
        gh_items, gh_meta = _fetch_github(program, limit=limit, days=days)
        all_raw.extend(gh_items)
        source_health["github"] = gh_meta
    if "arxiv" in program.preferred_sources:
        ax_items, ax_meta = _fetch_arxiv(program, limit=limit)
        all_raw.extend(ax_items)
        source_health["arxiv"] = ax_meta
    if "huggingface_papers" in program.preferred_sources or "huggingface_models" in program.preferred_sources:
        hf_items, hf_meta = _fetch_huggingface(program, limit=limit)
        all_raw.extend(hf_items)
        source_health["huggingface"] = hf_meta
    if "hackernews" in program.preferred_sources:
        hn_items, hn_meta = _fetch_hackernews(program, limit=limit, days=days)
        all_raw.extend(hn_items)
        source_health["hackernews"] = hn_meta

    # Deduplicate intra-run by source_url / slug
    seen_urls: set[str] = set()
    unique_raw: list[dict[str, Any]] = []
    for item in all_raw:
        key = (item.get("source_url") or item.get("slug") or "").lower().rstrip("/")
        if not key or key in seen_urls:
            continue
        seen_urls.add(key)
        unique_raw.append(item)

    evaluated: list[dict[str, Any]] = []
    saved_ids: list[int] = []
    blocked_count = 0

    for item in unique_raw:
        dup_result = dedup.check_candidate(
            title=item["title"],
            summary=item["summary"],
            entities=item.get("entities", []),
            keywords=item.get("keywords", []),
        )
        novelty_score = float(dup_result["novelty_score"])
        editorial_score = round((0.55 * item.get("raw_score", 50.0)) + (45.0 * novelty_score), 2)
        enriched = {
            **item,
            "dedup": dup_result,
            "novelty_score": novelty_score,
            "editorial_score": editorial_score,
        }
        if dup_result["blocked"]:
            blocked_count += 1
        evaluated.append(enriched)

    # Sort non-blocked first by editorial_score
    evaluated.sort(key=lambda x: (0 if not x["dedup"]["blocked"] else 1, -x["editorial_score"]))
    selected_slice = evaluated[:limit]

    if save:
        for cand in selected_slice:
            if cand["dedup"]["blocked"]:
                continue
            facts = [
                {
                    "claim": cand["title"],
                    "metrics": cand.get("metrics", {}),
                    "source_name": cand["primary_source"],
                    "source_url": cand["source_url"],
                }
            ]
            stored = db.upsert_item(
                slug=cand["slug"],
                title=cand["title"],
                summary=cand["summary"],
                program=cand["program"],
                category=cand["category"],
                primary_source=cand["primary_source"],
                source_url=cand["source_url"],
                entities=cand.get("entities", []),
                keywords=cand.get("keywords", []),
                facts=facts,
                novelty_score=cand["novelty_score"],
                initial_state="pesquisado",
                actor="discover",
                reason=f"Live discovery ({cand['primary_source']}, program={program.key})",
            )
            cand["db_id"] = stored["id"]
            saved_ids.append(stored["id"])

    return {
        "program": program.to_dict(),
        "github_token": token_status("GITHUB_TOKEN"),
        "source_health": source_health,
        "total_fetched": len(unique_raw),
        "blocked_duplicates": blocked_count,
        "saved_ids": saved_ids,
        "candidates": selected_slice,
    }
