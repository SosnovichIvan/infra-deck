"""Dependency-free bootstrap checks; expand with real CI when adding runtime."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = {".agents", ".agent-skills-lab", ".github", "docs", "scripts", "tests", "contracts", "deploy"}
ALLOWED_FILES = {"README.md", "AGENTS.md", "CONTRIBUTING.md", ".gitignore", "Makefile", "pyproject.toml", "uv.lock", ".env.example", ".python-version"}


def branch_policy(event, repository):
    pr = event.get("pull_request")
    if not pr:
        raise ValueError("Missing pull request metadata")
    base = pr["base"]["ref"]
    head = pr["head"]["ref"]
    source = (pr["head"].get("repo") or {}).get("full_name")
    if base == "develop" and head not in {"main", "develop"}:
        return
    if base == "main" and head == "develop" and source == repository:
        return
    raise ValueError("Only feature -> develop and same-repository develop -> main are allowed")


def inventory_errors(paths):
    return [f"Unregistered runtime/path: {p}; add component tests and update CI/matrix"
            for p in paths
            if Path(p).parts[0] not in ALLOWED_ROOTS and p not in ALLOWED_FILES
            and not p.startswith(("apps/web/", "services/control-plane/"))]


def check_repository(root):
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
    ).decode().split("\0")
    errors = inventory_errors([p for p in paths if p])
    manifest = json.loads((root / ".agents/skills/.agent-skills-lab.json").read_text())
    instructions = (root / "AGENTS.md").read_text()
    for name, record in manifest["skills"].items():
        digest = hashlib.sha256()
        skill_root = root / ".agents/skills" / name
        for path in sorted(p for p in skill_root.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
            relative = path.relative_to(skill_root).as_posix().encode()
            payload = path.read_bytes()
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
        if digest.hexdigest() != record["content_sha256"]:
            errors.append(f"Skill content differs from installation manifest: {name}")
        rel = f".agents/skills/{name}/SKILL.md"
        if not (root / rel).is_file() or rel not in instructions:
            errors.append(f"Skill missing or unregistered: {name}")
    own_docs = [root / p for p in ("README.md", "AGENTS.md", "CONTRIBUTING.md")]
    own_docs += list((root / "docs").rglob("*.md"))
    for doc in own_docs:
        # Approved upstream rule snapshots contain source-local examples; check our own intro.
        content = doc.read_text().split("# Agent instructions", 1)[0] if doc.name == "AGENTS.md" else doc.read_text()
        for target in re.findall(r"(?<!!)\[[^\]]*\]\(([^)]+)\)", content):
            if ":" in target or target.startswith("#"):
                continue
            resolved = doc.parent / unquote(target.split("#")[0])
            if not resolved.exists():
                errors.append(f"Broken local link: {doc.relative_to(root)} -> {target}")
    for relative in paths:
        if relative and relative.endswith(".json"):
            json.loads((root / relative).read_text())
    for path in paths:
        if path and (Path(path).name.startswith(".env") and path != ".env.example"
                     or Path(path).suffix in {".key", ".pem"}):
            errors.append(f"Sensitive file must not be tracked: {path}")
    if os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        base_sha = event["pull_request"]["base"]["sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", base_sha):
            raise ValueError("Invalid base commit")
        subprocess.run(["git", "diff", "--check", f"{base_sha}...HEAD", "--", ".", ":!.agents/skills/**"], cwd=root, check=True)
    if errors:
        raise ValueError("\n".join(errors))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch-policy", action="store_true")
    args = parser.parse_args()
    if args.branch_policy:
        event_name = os.environ.get("GITHUB_EVENT_NAME")
        if event_name == "workflow_dispatch":
            print("Manual verification; branch policy applies to pull_request")
            return
        if event_name != "pull_request":
            raise ValueError("Unsupported event")
        branch_policy(json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text()),
                      os.environ["GITHUB_REPOSITORY"])
    else:
        check_repository(ROOT)
    print("Bootstrap checks passed")


if __name__ == "__main__":
    main()
