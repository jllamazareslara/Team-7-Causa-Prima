"""PreToolUse hook: on a rules/<author> branch, an agent may only edit files inside rules/<author>/.

Reads the tool call as JSON on stdin; exit code 2 blocks the call and tells the agent why.
On any other branch (main, infra/...) it allows everything: CLAUDE.md and the PR review govern those.
"""
import json
import os
import re
import subprocess
import sys

call = json.load(sys.stdin)
target = (call.get("tool_input") or {}).get("file_path") or (call.get("tool_input") or {}).get("notebook_path")
root = os.environ.get("CLAUDE_PROJECT_DIR") or call.get("cwd") or os.getcwd()
if not target:
    sys.exit(0)
branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, capture_output=True, text=True).stdout.strip()
if not branch.startswith("rules/"):
    sys.exit(0)
author = branch.split("/", 1)[1]
def norm(p):
    """Absolute, case-folded path; Git Bash style /c/Users/... becomes C:/Users/... on Windows."""
    if os.name == "nt" and re.match(r"^/[a-zA-Z]/", p):
        p = p[1] + ":" + p[2:]
    return os.path.normcase(os.path.abspath(os.path.join(root, p)))


rel = os.path.relpath(norm(target), norm(root)).replace(os.sep, "/")
if rel.startswith("../"):
    sys.exit(0)  # outside the repo: not ours to police
if rel.startswith(f"rules/{author.lower()}/"):
    sys.exit(0)
print(f"Bloqueado: en la rama {branch} solo se edita rules/{author}/ (intentabas {rel}). "
      "Ver CLAUDE.md: los cambios comunes van en una rama infra/<tema> con Pull Request.", file=sys.stderr)
sys.exit(2)
