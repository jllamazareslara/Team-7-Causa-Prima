"""Check that a rules/<author> branch only changes rules/<author>/, so nobody overwrites someone else's work.

    python3 -m bench.guard                   # the current branch against origin/main
    python3 -m bench.guard rules/ana main    # any branch against any base

Exit code 1 lists the offending files. Branches not named rules/<author> are not checked.
"""
import subprocess
import sys


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def main():
    branch = sys.argv[1] if len(sys.argv) > 1 else git("rev-parse", "--abbrev-ref", "HEAD")
    base = sys.argv[2] if len(sys.argv) > 2 else "origin/main"
    if not branch.startswith("rules/"):
        print(f"{branch}: not a rules/<author> branch, nothing to check")
        return
    author = branch.split("/", 1)[1]
    fork = git("merge-base", base, branch)
    bad = [f for f in git("diff", "--name-only", f"{fork}..{branch}").splitlines() if f and not f.startswith(f"rules/{author}/")]
    if bad:
        print(f"{branch} changes files outside rules/{author}/:\n  " + "\n  ".join(bad))
        print("Move those changes to their own branch and pull request against main.")
        sys.exit(1)
    print(f"{branch}: only rules/{author}/ changed, ok")


if __name__ == "__main__":
    main()
