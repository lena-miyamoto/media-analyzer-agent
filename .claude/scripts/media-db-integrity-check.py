#!/usr/bin/env python3
"""Validate structural and data integrity of a media-db archive.

Designed for reliable agent handoff: every finding includes a severity level,
a human-readable description, the exact filesystem location, and a concrete
fix hint.  Use ``--json`` for machine-parseable output consumable by subagents.

Thin CLI wrapper around the shared check library in ``utils.py``.  The same
checks also run automatically at the end of every script that modifies media-db/
(media-db.py, media-db-setup-dsm5.py, media-db-setup-therapy-methods.py,
media-db-download-icd11.py).
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import utils

from utils import (
    CATEGORY_STRUCTURAL,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    finding,
    run_integrity_check,
)

# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_human(findings):
    """Return a human-readable report string."""
    lines = []
    errors = [f for f in findings if f["severity"] == SEVERITY_ERROR]
    warnings = [f for f in findings if f["severity"] == SEVERITY_WARNING]

    if not findings:
        lines.append("✓ media-db integrity check passed — no issues found.")
        return "\n".join(lines)

    # Errors first, then warnings
    for severity, group, label in [
        (SEVERITY_ERROR, errors, "ERRORS"),
        (SEVERITY_WARNING, warnings, "WARNINGS"),
    ]:
        if not group:
            continue
        lines.append(f"{'='*72}")
        lines.append(f"  {label} ({len(group)})")
        lines.append(f"{'='*72}")
        lines.append("")

        # Group by category
        by_cat = {}
        for f in group:
            by_cat.setdefault(f["category"], []).append(f)

        for cat in sorted(by_cat):
            cat_findings = by_cat[cat]
            lines.append(f"  [{cat}] ({len(cat_findings)} issue{'s' if len(cat_findings) != 1 else ''})")
            lines.append(f"  {'-'*66}")
            for i, f in enumerate(cat_findings, 1):
                lines.append(f"  #{i} {f['location']}")
                lines.append(f"     Problem : {f['description']}")
                lines.append(f"     Fix     : {f['fix']}")
                lines.append("")
        lines.append("")

    # Summary
    lines.append(f"{'='*72}")
    lines.append(f"  SUMMARY")
    lines.append(f"{'='*72}")
    lines.append(f"  Errors  : {len(errors)}")
    lines.append(f"  Warnings: {len(warnings)}")

    by_cat = Counter(f["category"] for f in findings)
    for cat in sorted(by_cat):
        lines.append(f"    {cat}: {by_cat[cat]}")

    return "\n".join(lines)


def _format_json(findings):
    """Return a JSON report string."""
    errors = [f for f in findings if f["severity"] == SEVERITY_ERROR]
    warnings = [f for f in findings if f["severity"] == SEVERITY_WARNING]
    report = {
        "status": "clean" if not errors else "errors_found",
        "counts": {
            "errors": len(errors),
            "warnings": len(warnings),
            "total": len(findings),
        },
        "by_category": {
            cat: len([f for f in findings if f["category"] == cat])
            for cat in sorted({f["category"] for f in findings})
        },
        "findings": findings,
    }
    return json.dumps(report, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args():
    parser = argparse.ArgumentParser(
        description="Validate structural and data integrity of a media-db archive.",
    )
    parser.add_argument(
        "--media-db",
        default="media-db",
        help="Target media-db directory. Defaults to ./media-db.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit findings as machine-parseable JSON instead of human-readable text.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    root = Path(args.media_db)

    if not root.is_dir():
        print(f"ERROR: media-db directory not found: {root}", file=sys.stderr)
        if args.json_output:
            print(
                json.dumps(
                    {
                        "status": "fatal",
                        "counts": {"errors": 1, "warnings": 0, "total": 1},
                        "findings": [
                            finding(
                                SEVERITY_ERROR,
                                CATEGORY_STRUCTURAL,
                                str(root),
                                f"media-db directory not found: {root}",
                                "Create the directory or check the --media-db path.",
                            )
                        ],
                    },
                    indent=2,
                )
            )
        return 1

    findings = run_integrity_check(root)

    if args.json_output:
        print(_format_json(findings))
    else:
        print(_format_human(findings))

    has_errors = any(f["severity"] == SEVERITY_ERROR for f in findings)
    has_warnings = any(f["severity"] == SEVERITY_WARNING for f in findings)

    if has_errors:
        return 1
    if has_warnings:
        return 2
    return 0


if __name__ == "__main__":
    utils.run_cli(main)
