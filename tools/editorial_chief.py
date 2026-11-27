"""Unified CLI for the avatar-journal AI Editorial Intelligence (Editor-Chefe)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from editorial.creative_brief import build_creative_brief
from editorial.discover import discover_candidates
from editorial.env_loader import token_status
from editorial.export_pauta import export_pauta_json
from editorial.fact_checker import verify_item
from editorial.memory_store import EditorialMemoryStore, VALID_STATES
from editorial.programs import VALID_PROGRAMS, list_programs
from editorial.semantic_dedup import SemanticDeduplicator


def _print(obj: object) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser(description="AI Editorial Intelligence (Editor-Chefe) CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    # init
    sub.add_parser("init", help="Initialize SQLite editorial DB and migrate published_history.json")

    # programs
    sub.add_parser("programs", help="List all 7 weekly editorial program identities")

    # discover
    sp_disc = sub.add_parser("discover", help="Run live discovery across GitHub, arXiv, HuggingFace, and HN")
    sp_disc.add_argument("--program", default="auto", help="Program key (segunda..domingo or 'auto')")
    sp_disc.add_argument("--limit", type=int, default=6, help="Max ranked candidates to return")
    sp_disc.add_argument("--days", type=int, default=30, help="Lookback window in days")
    sp_disc.add_argument("--save", action="store_true", help="Save non-blocked candidates as 'pesquisado'")

    # check-dup
    sp_dup = sub.add_parser("check-dup", help="Run 3-layer semantic deduplication against editorial memory")
    sp_dup.add_argument("--title", required=True, help="Candidate topic title")
    sp_dup.add_argument("--summary", default="", help="Candidate summary")
    sp_dup.add_argument("--entities", nargs="*", default=[], help="Entity or repo names (e.g. owner/repo)")
    sp_dup.add_argument("--keywords", nargs="*", default=[], help="Topic keywords")
    sp_dup.add_argument("--allow-update", action="store_true", help="Allow substantial update override")
    sp_dup.add_argument("--supersedes-id", type=int, default=None, help="Existing item ID being updated")

    # verify
    sp_ver = sub.add_parser("verify", help="Verify primary URLs and classify technological maturity")
    sp_ver.add_argument("--item-id", required=True, help="Editorial item ID or slug")

    # transition
    sp_tr = sub.add_parser("transition", help="Transition an item across lifecycle states with audit log")
    sp_tr.add_argument("--item-id", required=True, help="Editorial item ID or slug")
    sp_tr.add_argument("--to", required=True, choices=list(VALID_STATES), help="Target lifecycle state")
    sp_tr.add_argument("--reason", default="", help="Editorial justification")
    sp_tr.add_argument("--video-id", default="", help="Associated YouTube video ID if published")
    sp_tr.add_argument("--force", action="store_true", help="Bypass transition guard (admin only)")

    # brief
    sp_br = sub.add_parser("brief", help="Generate Parte 11 (A-F) proposal + 7-field visual brief")
    sp_br.add_argument("--program", default="auto", help="Program key (segunda..domingo or 'auto')")
    sp_br.add_argument("--item-ids", nargs="*", type=int, default=None, help="Specific item IDs")

    # export-pauta
    sp_ex = sub.add_parser("export-pauta", help="Export factory-compatible pauta.json for pauta_to_plan.py")
    sp_ex.add_argument("--program", default="auto", help="Program key")
    sp_ex.add_argument("--item-ids", nargs="*", type=int, default=None, help="Specific item IDs")
    sp_ex.add_argument("--out", default="", help="Output pauta.json path")
    sp_ex.add_argument("--allow-unapproved", action="store_true", help="Allow exporting non-approved items (dry runs)")

    # history
    sp_hist = sub.add_parser("history", help="Inspect DB items, publications, insights, and transitions")
    sp_hist.add_argument("--state", default="", help="Filter items by state")
    sp_hist.add_argument("--program", default="", help="Filter items by program")
    sp_hist.add_argument("--item-id", type=int, default=None, help="Show full detail + transition history for one item")
    sp_hist.add_argument("--limit", type=int, default=30, help="Max items to return")

    # insight
    sp_ins = sub.add_parser("insight", help="Record an editorial/audience/production lesson into SQLite")
    sp_ins.add_argument("--category", required=True, help="e.g. visual, audience, fact_check, pacing")
    sp_ins.add_argument("--summary", required=True, help="Lesson summary")
    sp_ins.add_argument("--action-rule", default="", help="Actionable rule for future productions")
    sp_ins.add_argument("--video-id", default="", help="Related YouTube video ID")

    args = ap.parse_args()
    store = EditorialMemoryStore()

    if args.cmd == "init":
        mig = store.migrate_from_published_history()
        _print({
            "migration": mig,
            "stats": store.stats(),
            "github_token": token_status("GITHUB_TOKEN"),
        })
        return 0

    if args.cmd == "programs":
        _print({"count": len(VALID_PROGRAMS), "programs": list_programs()})
        return 0

    if args.cmd == "discover":
        res = discover_candidates(
            program_key=args.program,
            limit=args.limit,
            days=args.days,
            save=args.save,
            store=store,
        )
        _print(res)
        return 0

    if args.cmd == "check-dup":
        dedup = SemanticDeduplicator(store)
        res = dedup.check_candidate(
            title=args.title,
            summary=args.summary,
            entities=args.entities,
            keywords=args.keywords,
            allow_update=args.allow_update,
            supersedes_id=args.supersedes_id,
        )
        _print(res)
        return 0

    if args.cmd == "verify":
        res = verify_item(args.item_id, store=store)
        _print(res)
        return 0

    if args.cmd == "transition":
        updated = store.transition(
            args.item_id,
            args.to,
            reason=args.reason,
            video_id=args.video_id,
            force=args.force,
        )
        _print({
            "item": updated,
            "transitions": store.get_transitions(updated["id"]),
        })
        return 0

    if args.cmd == "brief":
        res = build_creative_brief(
            program_key=args.program,
            item_ids=args.item_ids,
            store=store,
        )
        _print(res)
        return 0

    if args.cmd == "export-pauta":
        out_path = Path(args.out) if args.out else None
        res = export_pauta_json(
            program_key=args.program,
            item_ids=args.item_ids,
            output_path=out_path,
            allow_unapproved=args.allow_unapproved,
            store=store,
        )
        _print(res)
        return 0

    if args.cmd == "history":
        if args.item_id is not None:
            item = store.get_item(args.item_id)
            _print({
                "item": item,
                "transitions": store.get_transitions(args.item_id) if item else [],
            })
            return 0
        states = (args.state,) if args.state else None
        _print({
            "stats": store.stats(),
            "items": store.list_items(states=states, program=args.program or None, limit=args.limit),
            "publications": store.list_publications(limit=10),
            "insights": store.list_insights(limit=10),
        })
        return 0

    if args.cmd == "insight":
        row = store.add_insight(
            category=args.category,
            summary=args.summary,
            action_rule=args.action_rule,
            video_id=args.video_id,
        )
        _print(row)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
