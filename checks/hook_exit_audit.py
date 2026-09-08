#!/usr/bin/env python3
"""Find explicit exit-code statements in shell hook scripts.

This is a narrow static check. It does not prove that a hook is discovered, invoked,
correctly configured, or complete.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

EXIT_RE = re.compile(r"(?:^|[;&|]\s*)exit\s+([0-9]+)(?:\s|$)")
SHELL_SUFFIXES = {".sh", ".bash", ".zsh"}


def inspect_text(text: str, source: str = "<memory>") -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for match in EXIT_RE.finditer(stripped):
            code = int(match.group(1))
            findings.append(
                {
                    "source": source,
                    "line": number,
                    "code": code,
                    "classification": "potential-fail-open" if code == 1 else "blocking-candidate" if code == 2 else "other",
                    "text": stripped,
                }
            )
    return findings


def candidate_files(paths: list[Path]) -> list[Path]:
    result: set[Path] = set()
    for path in paths:
        if path.is_file():
            result.add(path)
        elif path.is_dir():
            result.update(p for p in path.rglob("*") if p.is_file() and p.suffix in SHELL_SUFFIXES)
    return sorted(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, default=[Path.home() / ".claude" / "hooks"])
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    findings: list[dict[str, object]] = []
    for path in candidate_files(args.paths):
        findings.extend(inspect_text(path.read_text(encoding="utf-8", errors="replace"), str(path)))

    if args.as_json:
        print(json.dumps(findings, indent=2))
    else:
        for finding in findings:
            print(f"{finding['classification']}: {finding['source']}:{finding['line']}: exit {finding['code']}")
        if not findings:
            print("No explicit exit statements found in candidate shell hook files.")

    return 1 if any(item["classification"] == "potential-fail-open" for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
