"""Write dist/release-validation.json and dist/SHA256SUMS from the built distributions.

The record binds a tag to the exact tree, the wheel payload, the source archive
contents and a full test replay executed from the extracted source archive in an
isolated environment. It runs in the release workflow; it can also run locally
after `uv build`. Nothing here contacts PyPI or GitHub.
"""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from trailbun import __version__  # noqa: E402


def command(*argv, cwd=ROOT):
    return subprocess.run(argv, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replay_from_sdist(sdist):
    """Extract the source archive, install it in a fresh environment and run its tests."""
    with tempfile.TemporaryDirectory(prefix="trailbun-release-") as temporary:
        base = Path(temporary)
        with tarfile.open(sdist, "r:gz") as archive:
            archive.extractall(base, filter="data")
        source = base / f"trailbun-{__version__}"
        environment = base / "env"
        command("uv", "venv", "--python", sys.executable, str(environment), cwd=base)
        python = next(path for path in (environment / "bin" / "python", environment / "Scripts" / "python.exe") if path.exists())
        command("uv", "pip", "install", "--python", str(python), f"{source}[test]", cwd=base)
        xml = base / "pytest-replay.xml"
        argv = [str(python), "-m", "pytest", "-ra", "-m", "not windows_acl", "--junitxml=" + str(xml)]
        started = datetime.now(UTC).isoformat()
        process = subprocess.run(argv, cwd=source, capture_output=True, text=True)
        suite = ET.parse(xml).getroot()
        suite = suite.find("testsuite") if suite.tag == "testsuites" else suite
        return {"python": platform.python_version(), "platform": platform.platform(),
                "environment": "isolated environment installed from the extracted source archive",
                "working_directory": "extracted source archive", "started_at": started,
                "finished_at": datetime.now(UTC).isoformat(), "exit_code": process.returncode,
                "tests": int(suite.attrib["tests"]), "skipped": int(suite.attrib["skipped"]),
                "errors": int(suite.attrib["errors"]), "failures": int(suite.attrib["failures"]),
                "seconds": float(suite.attrib["time"]), "xml_sha256": sha(xml.read_bytes()),
                "tail": process.stdout[-2000:]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True, help="Release tag, for example v0.2.1")
    parser.add_argument("--run-url", default=None, help="URL of the workflow run that produced the distributions")
    args = parser.parse_args()
    if args.tag != f"v{__version__}":
        raise SystemExit(f"Tag {args.tag} does not match trailbun.__version__ {__version__}")
    head = command("git", "rev-parse", "HEAD")
    if command("git", "status", "--porcelain"):
        raise SystemExit("The worktree must be clean")
    wheel = ROOT / f"dist/trailbun-{__version__}-py3-none-any.whl"
    sdist = ROOT / f"dist/trailbun-{__version__}.tar.gz"
    payload = list((ROOT / "src/trailbun").glob("*.py")) + list((ROOT / "src/trailbun").glob("skills/*/SKILL.md"))
    with zipfile.ZipFile(wheel) as archive:
        for path in payload:
            if archive.read(path.relative_to(ROOT / "src").as_posix()) != path.read_bytes():
                raise SystemExit(f"Wheel payload differs from the tree: {path}")
    required = [ROOT / name for name in ("README.md", "CHANGELOG.md", "LICENSE", "pyproject.toml", "MANIFEST.in")]
    for pattern in ("tests/*.py", "benchmarks/*.py", "scripts/*.py"):
        required.extend(ROOT.glob(pattern))
    required.extend(payload)
    with tarfile.open(sdist, "r:gz") as archive:
        for path in required:
            member = f"trailbun-{__version__}/" + path.relative_to(ROOT).as_posix()
            if archive.extractfile(member).read() != path.read_bytes():
                raise SystemExit(f"Source archive differs from the tree: {member}")
    replay = replay_from_sdist(sdist)
    if replay["exit_code"] != 0 or replay["errors"] or replay["failures"]:
        raise SystemExit("The source archive replay failed:\n" + replay["tail"])
    record = {
        "schema_version": 2, "measured_at": datetime.now(UTC).isoformat(),
        "release": args.tag, "channel": "preview", "tested_commit": head,
        "tested_tree": command("git", "rev-parse", "HEAD^{tree}"), "workflow_run": args.run_url,
        "generator": "scripts/release_validation.py", "generator_sha256": sha(Path(__file__).read_bytes()),
        "source_archive_replay": replay,
        "distributions": [{"name": path.name, "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}
                          for path in (wheel, sdist)],
        "source_files_compared_to_tree": len(required) + len(payload),
        "limits": ["Windows ACL tests run in the CI job, not in this replay",
                   "Claude Code live behavior has no receipt; see docs/EVIDENCE.md",
                   "No agent-effectiveness percentage is claimed"],
    }
    target = ROOT / "dist/release-validation.json"
    target.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    with (ROOT / "dist/SHA256SUMS").open("w", encoding="ascii") as stream:
        for path in (wheel, sdist, target):
            stream.write(f"{sha(path.read_bytes())}  {path.name}\n")
    print(json.dumps({"record": str(target), "tests": replay["tests"], "skipped": replay["skipped"]}))


if __name__ == "__main__":
    main()
