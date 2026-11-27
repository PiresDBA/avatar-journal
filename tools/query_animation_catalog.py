"""Query the local Opus 5.5 703-prompt animation catalog & OpenMontage skills.

Mandatory Step 0 before authoring any animation in `avatar-journal`
(see `docs/ANIMATION_CONTRACT.md`).

Examples:
  python tools/query_animation_catalog.py --category explainer --tech threejs --top 5
  python tools/query_animation_catalog.py --search "bar chart" --top 8
  python tools/query_animation_catalog.py --slug 0xlangeai-178533 --show-prompt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

OPUS_DIR = Path(r"D:\Utilitarios\opus5-reference")
OPENMONTAGE_GALLERY = Path(r"D:\Utilitarios\OpenMontage\PROMPT_GALLERY.md")


def load_videos() -> list[dict]:
    vpath = OPUS_DIR / "videos.json"
    if not vpath.exists():
        raise FileNotFoundError(f"Catalog not found: {vpath}")
    return json.loads(vpath.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Search local 703-prompt Opus 5.5 animation catalog.")
    ap.add_argument("--category", choices=["motion", "3d", "explainer", "interactive"], help="Filter by category")
    ap.add_argument("--tech", help="Filter by tech tag (e.g. canvas, svg, threejs, gsap, shader, css, particles, physics)")
    ap.add_argument("--search", help="Keyword search across title, description, tags, and prompt text")
    ap.add_argument("--slug", help="Exact slug to inspect")
    ap.add_argument("--show-prompt", action="store_true", help="Print the full .md prompt content for matched slugs")
    ap.add_argument("--top", type=int, default=10, help="Max results to return (default: 10)")
    ap.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = ap.parse_args()

    videos = load_videos()
    prompts_dir = OPUS_DIR / "prompts"

    if args.slug:
        matches = [v for v in videos if v.get("slug") == args.slug]
    else:
        matches = []
        q = (args.search or "").strip().lower()
        tech_q = (args.tech or "").strip().lower()
        for v in videos:
            if args.category and v.get("category", "").lower() != args.category:
                continue
            tags = [t.lower() for t in v.get("tech_tags", [])]
            if tech_q and tech_q not in tags:
                continue
            score = 1
            if q:
                blob = " ".join([
                    str(v.get("slug", "")),
                    str(v.get("title", "")),
                    str(v.get("description", "")),
                    " ".join(tags),
                ]).lower()
                if q in blob:
                    score += 3
                else:
                    pfile = prompts_dir / f"{v.get('slug', '')}.md"
                    if pfile.exists():
                        ptxt = pfile.read_text(encoding="utf-8", errors="ignore").lower()
                        if q in ptxt:
                            score += 1
                        else:
                            continue
                    else:
                        continue
            matches.append((score, v))
        matches.sort(key=lambda x: x[0], reverse=True)
        matches = [v for _, v in matches[: args.top]]

    results = []
    for v in matches:
        slug = v.get("slug", "")
        pfile = prompts_dir / f"{slug}.md"
        item = {
            "slug": slug,
            "category": v.get("category"),
            "tech_tags": v.get("tech_tags", []),
            "title": v.get("title") or slug,
            "prompt_path": str(pfile) if pfile.exists() else None,
        }
        if args.show_prompt and pfile.exists():
            item["prompt"] = pfile.read_text(encoding="utf-8", errors="ignore")
        results.append(item)

    if args.json:
        print(json.dumps({"total_catalog": len(videos), "matched": len(results), "results": results}, ensure_ascii=False, indent=2))
    else:
        print(f"Opus 5.5 Catalog: {len(videos)} prompts | Matched: {len(results)}")
        if OPENMONTAGE_GALLERY.exists():
            print(f"OpenMontage Gallery: {OPENMONTAGE_GALLERY}")
        print("-" * 72)
        for r in results:
            tags_s = ", ".join(r["tech_tags"])
            print(f"[{r['category']}] {r['slug']} ({tags_s})")
            print(f"  Prompt: {r['prompt_path']}")
            if args.show_prompt and "prompt" in r:
                print("  ---")
                print(r["prompt"][:1200])
                print("  ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
