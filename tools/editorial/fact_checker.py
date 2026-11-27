"""Live HTTP fact verification and technological maturity classification."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import requests

from .env_loader import load_project_env
from .memory_store import EditorialMemoryStore

HTTP_TIMEOUT = 15
USER_AGENT = "avatar-journal-fact-checker/1.0"

MATURITY_CLASSES: tuple[str, ...] = (
    "verified_release",
    "open_source_active",
    "peer_or_preprint_paper",
    "early_demo",
    "marketing_rumor",
    "benchmark_synthetic",
    "unverified",
)

AUTHORITATIVE_DOMAINS = (
    "github.com",
    "arxiv.org",
    "huggingface.co",
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "blog.google",
    "ai.meta.com",
    "microsoft.com",
    "nvidia.com",
    "pytorch.org",
    "nature.com",
    "science.org",
    "acm.org",
    "ieee.org",
)


def _check_url_live(url: str) -> dict[str, Any]:
    if not url or not url.startswith(("http://", "https://")):
        return {"url": url, "reachable": False, "status_code": 0, "error": "URL invalida"}
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
        )
        title_match = re.search(r"<title[^>]*>(.*?)</title>", resp.text[:8000], re.IGNORECASE | re.DOTALL)
        page_title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
        return {
            "url": url,
            "final_url": resp.url,
            "reachable": 200 <= resp.status_code < 400,
            "status_code": resp.status_code,
            "domain": urlparse(resp.url).netloc.lower(),
            "page_title": page_title[:140],
        }
    except Exception as exc:
        return {"url": url, "reachable": False, "status_code": 0, "error": str(exc)}


def _inspect_github_repo(url: str) -> dict[str, Any] | None:
    m = re.match(r"https?://github\.com/([^/]+/[^/#?]+)", url.strip())
    if not m:
        return None
    repo = m.group(1).removesuffix(".git")
    load_project_env()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    try:
        resp = requests.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=HTTP_TIMEOUT)
        if resp.status_code != 200:
            return {"repo": repo, "api_status": resp.status_code}
        d = resp.json()
        return {
            "repo": repo,
            "api_status": 200,
            "stars": int(d.get("stargazers_count") or 0),
            "forks": int(d.get("forks_count") or 0),
            "open_issues": int(d.get("open_issues_count") or 0),
            "archived": bool(d.get("archived")),
            "license": (d.get("license") or {}).get("spdx_id") or "NONE",
            "pushed_at": d.get("pushed_at", ""),
            "default_branch": d.get("default_branch", ""),
        }
    except Exception as exc:
        return {"repo": repo, "error": str(exc)}


def verify_item(item_id_or_slug: int | str, store: EditorialMemoryStore | None = None) -> dict[str, Any]:
    """Perform live HTTP verification + maturity classification + risk flags for an item."""
    db = store or EditorialMemoryStore()
    item = db.get_item(item_id_or_slug)
    if not item:
        raise KeyError(f"Item nao encontrado no banco editorial: {item_id_or_slug}")

    urls_to_check: list[str] = []
    if item.get("source_url"):
        urls_to_check.append(item["source_url"])
    for f in item.get("facts", []):
        u = str(f.get("source_url") or "").strip()
        if u and u not in urls_to_check:
            urls_to_check.append(u)

    url_checks = [_check_url_live(u) for u in urls_to_check[:5]]
    reachable_urls = [c for c in url_checks if c.get("reachable")]
    unique_domains = sorted({c.get("domain", "") for c in reachable_urls if c.get("domain")})

    gh_details = None
    for u in urls_to_check:
        if "github.com/" in u:
            gh_details = _inspect_github_repo(u)
            break

    # Maturity classification
    maturity = "unverified"
    title_low = (item.get("title") + " " + item.get("summary")).lower()
    if gh_details and gh_details.get("api_status") == 200:
        if gh_details.get("archived"):
            maturity = "early_demo"
        elif gh_details.get("stars", 0) >= 150 and not gh_details.get("archived"):
            maturity = "open_source_active"
        else:
            maturity = "early_demo"
    elif any("arxiv.org" in d for d in unique_domains) or any("huggingface.co/papers" in u for u in urls_to_check):
        maturity = "peer_or_preprint_paper"
    elif any("huggingface.co" in d for d in unique_domains) and reachable_urls:
        maturity = "verified_release"
    elif any(any(auth in d for auth in AUTHORITATIVE_DOMAINS) for d in unique_domains):
        maturity = "verified_release"
    elif reachable_urls:
        maturity = "early_demo"

    if any(k in title_low for k in ("benchmark", "leaderboard")) and not any(k in title_low for k in ("latency", "vram", "throughput", "ablation")):
        if maturity in {"early_demo", "unverified"}:
            maturity = "benchmark_synthetic"

    risk_flags: list[str] = []
    if not reachable_urls:
        risk_flags.append("NO_REACHABLE_PRIMARY_URL")
    if len(unique_domains) <= 1:
        risk_flags.append("SINGLE_SOURCE_NEEDS_SECOND_CONFIRMATION")
    if gh_details and gh_details.get("license") in {"NONE", "NOASSERTION", ""}:
        risk_flags.append("MISSING_EXPLICIT_OPEN_LICENSE")
    if gh_details and gh_details.get("archived"):
        risk_flags.append("ARCHIVED_REPOSITORY")
    if not item.get("facts"):
        risk_flags.append("MISSING_QUANTITATIVE_FACTS")

    verification_report = {
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "url_checks": url_checks,
        "reachable_count": len(reachable_urls),
        "unique_domains": unique_domains,
        "github": gh_details,
        "maturity": maturity,
        "risk_flags": risk_flags,
        "passed_minimum_bar": bool(reachable_urls) and maturity != "unverified",
    }

    updated = db.update_verification(item["id"], verification_report, maturity)
    return {
        "item_id": updated["id"],
        "slug": updated["slug"],
        "title": updated["title"],
        "state": updated["state"],
        "verification": verification_report,
    }
