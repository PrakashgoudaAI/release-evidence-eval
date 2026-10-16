"""Bounded checks for known credential patterns in source and available Git blobs."""

import argparse
import os
from pathlib import Path
import re
import subprocess

from release_eval.__main__ import ROOT
from release_eval.contracts import MAX_BYTES, canonical

PATTERNS = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}"),
    "api-token": re.compile(rb"sk-[A-Za-z0-9_-]{24,}"),
    "aws-access-id": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "embedded-credential": re.compile(rb"(?i)(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_./+-]{24,}[\"']"),
}
EXCLUDED = {".git", "__pycache__", ".venv", "reports", "node_modules"}


def matches(data):
    return [name for name, pattern in PATTERNS.items() if pattern.search(data)]


def _git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, timeout=10)
    if result.returncode:
        raise RuntimeError("git_read_failed")
    return result.stdout


def scan(root, history=True):
    root = Path(root).resolve()
    findings, incomplete = [], []
    files = []
    if not root.exists():
        raise OSError("scan_path_missing")
    if root.is_file():
        files = [root]
    else:
        for directory, names, filenames in os.walk(root):
            for name in list(names):
                path = Path(directory) / name
                if path.is_symlink() and name not in EXCLUDED:
                    incomplete.append(path.relative_to(root).as_posix() + ":symlink_not_scanned")
            names[:] = [name for name in names if name not in EXCLUDED and not (Path(directory) / name).is_symlink()]
            files.extend(Path(directory) / name for name in filenames)
            if len(files) > 2000:
                break
        files.sort()
    if len(files) > 2000:
        return {"passed": False, "findings": [], "incomplete": ["file_limit_exceeded"], "history": "not_checked"}
    for path in files:
        label = path.name if root.is_file() else path.relative_to(root).as_posix()
        if path.is_symlink():
            incomplete.append(label + ":symlink_not_scanned")
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            findings.append({"location": label, "rule": "private-environment-file"})
            continue
        with path.open("rb") as handle:
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            incomplete.append(label + ":file_too_large")
            continue
        findings.extend({"location": label, "rule": rule} for rule in matches(data))
    history_status = "not_requested"
    if history and root.is_dir():
        try:
            repository = Path(_git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
        except (RuntimeError, FileNotFoundError):
            history_status = "unavailable_no_repository"
            if (root / ".git").exists():
                incomplete.append("git_history_unavailable")
        else:
            if repository != root:
                history_status = "not_scanned_parent_repository"
                incomplete.append("repository_root_mismatch")
            else:
                history_status = "scanned_reachable_objects"
                objects = _git(root, "rev-list", "--objects", "--all").splitlines()
                if len(objects) > 5000:
                    incomplete.append("history_object_limit_exceeded")
                else:
                    for entry in objects:
                        object_id = entry.split(b" ", 1)[0].decode("ascii")
                        if _git(root, "cat-file", "-t", object_id).strip() != b"blob":
                            continue
                        if int(_git(root, "cat-file", "-s", object_id)) > MAX_BYTES:
                            incomplete.append("git-object:" + object_id + ":too_large")
                            continue
                        findings.extend({"location": "git-object:" + object_id, "rule": rule}
                                        for rule in matches(_git(root, "cat-file", "blob", object_id)))
    return {"passed": not findings and not incomplete, "findings": findings,
            "incomplete": incomplete, "history": history_status,
            "scope": "known_patterns_only_not_a_security_audit"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check publication inputs without displaying matched credentials.")
    parser.add_argument("--path", type=Path, default=ROOT)
    parser.add_argument("--no-history", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = scan(args.path, history=not args.no_history)
        print(canonical(result))
        return 0 if result["passed"] else 1
    except (OSError, RuntimeError, UnicodeError, subprocess.TimeoutExpired):
        print('{"passed":false,"error":"scan_incomplete"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
