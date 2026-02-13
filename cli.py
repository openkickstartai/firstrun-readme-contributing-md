#!/usr/bin/env python3
"""FirstRun CLI — Verify contributor onboarding documentation."""
import argparse
import json
import sys
from firstrun import scan, format_sarif


def cmd_scan(args):
    """Execute the scan command."""
    result = scan(args.path, check_urls_flag=args.check_links)
    if args.format == "sarif":
        output = json.dumps(format_sarif(result), indent=2)
    elif args.format == "json":
        output = json.dumps({"score": result.score, "issues": [
            {"file": i.file, "line": i.line, "category": i.category,
             "message": i.message} for i in result.issues
        ]}, indent=2)
    else:
        lines = [f"\n\U0001f3c1 FirstRun Contributor Readiness Score: {result.score}/100\n"]
        if not result.issues:
            lines.append("\u2705 No issues found! Your onboarding docs look great.")
        else:
            lines.append(f"Found {len(result.issues)} issue(s):\n")
            for i in result.issues:
                icon = "\u274c" if i.category in ("command", "missing") else "\u26a0\ufe0f"
                lines.append(f"  {icon} [{i.category}] {i.file}:{i.line} \u2014 {i.message}")
        lines.append("")
        output = "\n".join(lines)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report written to {args.output}")
    else:
        print(output)
    if result.score < args.min_score:
        print(f"\n\u274c Score {result.score} is below minimum threshold {args.min_score}")
        sys.exit(1)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="firstrun", description="Verify contributor onboarding docs")
    sub = parser.add_subparsers(dest="cmd")
    sc = sub.add_parser("scan", help="Scan repository documentation")
    sc.add_argument("path", nargs="?", default=".", help="Repository root path")
    sc.add_argument("--check-links", action="store_true", help="Also verify URL reachability")
    sc.add_argument("--min-score", type=int, default=0, help="Minimum passing score (0-100)")
    sc.add_argument("--format", choices=["text", "sarif", "json"], default="text", help="Output format")
    sc.add_argument("-o", "--output", help="Write report to file")
    args = parser.parse_args()
    if args.cmd == "scan":
        cmd_scan(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
