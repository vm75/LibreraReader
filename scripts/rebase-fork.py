#!/usr/bin/env python3
"""Rebase vm75/LibreraReader extensions onto upstream with a backup and checks."""

import argparse
import datetime
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys

BASE_REF = "refs/fork/upstream-base"
TAG_PREFIX = "refs/fork/upstream-tags/"
ROOT = None


def git(*args, check=True):
    result = subprocess.run(["git", *args], cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result


def run(*args):
    print("+ " + shlex.join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def commit(ref):
    return git("rev-parse", "--verify", "--end-of-options", ref + "^{commit}").stdout.strip()


def git_path(name):
    return ROOT / git("rev-parse", "--git-path", name).stdout.strip()


def rebasing():
    return git_path("rebase-merge").exists() or git_path("rebase-apply").exists()


def planned_rebase(state):
    directory = git_path("rebase-merge")
    if not directory.exists():
        directory = git_path("rebase-apply")
    expected = {"head-name": "refs/heads/main", "orig-head": state["old_head"],
                "onto": state["new_base"]}
    for name, value in expected.items():
        path = directory / name
        if not path.exists() or path.read_text().strip() != value:
            raise RuntimeError("The active Git rebase does not match the saved plan; inspect it with Git directly.")


def rebase(*args):
    # A user's updateRefs setting must never move the backup with the stack.
    run("git", "-c", "rebase.updateRefs=false", "-c", "submodule.recurse=false", "rebase", *args)


def clean():
    if git("status", "--porcelain").stdout:
        raise RuntimeError("Commit or move uncommitted changes before rebasing.")


def main_branch():
    if git("symbolic-ref", "--quiet", "--short", "HEAD", check=False).stdout.strip() != "main":
        raise RuntimeError("Run this helper on main.")


def target_base(requested):
    if requested == "latest-stable":
        tags = git("for-each-ref", "--format=%(refname)", TAG_PREFIX).stdout.splitlines()
        releases = []
        for ref in tags:
            match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", ref[len(TAG_PREFIX):])
            if match:
                releases.append((tuple(map(int, match.groups())), ref))
        if not releases:
            raise RuntimeError("No cached stable upstream tags; fetch with the helper first, or choose --base <ref>.")
        ref = max(releases)[1]
    elif git("show-ref", "--verify", "--quiet", TAG_PREFIX + requested, check=False).returncode == 0:
        ref = TAG_PREFIX + requested
    else:
        ref = requested
    return commit(ref), ref


def old_base(explicit):
    if explicit:
        base = target_base(explicit)[0]
    elif git("show-ref", "--verify", "--quiet", BASE_REF, check=False).returncode == 0:
        base = commit(BASE_REF)
    else:
        base = git("merge-base", "HEAD", "upstream/master").stdout.strip()
        proposed = set(git("rev-list", base + "..HEAD").stdout.splitlines())
        # Also exclude tags: an old stable release may have no surviving branch.
        # Fork-owned tags can make this conservative check require --from-base.
        fork_only = set(git("rev-list", base + "..HEAD", "--not", "--remotes=upstream", "--tags", "--glob=" + TAG_PREFIX + "*").stdout.splitlines())
        if proposed != fork_only:
            raise RuntimeError("Cannot infer the previous upstream base safely; use --from-base <previous-upstream-ref>.")
    if git("merge-base", "--is-ancestor", base, "HEAD", check=False).returncode:
        raise RuntimeError("The recorded upstream base is not an ancestor of main; use --from-base <previous-upstream-ref>.")
    if git("rev-list", "--merges", base + "..HEAD").stdout.strip():
        raise RuntimeError("The fork stack contains merge commits. Establish a linear fork stack before using this helper.")
    return base


def finish(state, path, skip_tests):
    main_branch()
    if git("merge-base", "--is-ancestor", state["new_base"], "HEAD", check=False).returncode:
        raise RuntimeError("main does not contain the planned upstream base; inspect the saved backup before continuing.")
    clean()
    if state["tests"] and not skip_tests:
        run(sys.executable, "Builder/tests/test_fork_build.py")
        run("bash", "-n", "Builder/link_to_mupdf_fork.sh", "Builder/build-nomupdf.sh",
            "Builder/all-release.sh", "Builder/build-librera-beta.sh")
        run("git", "diff", "--check")
        print("Lightweight checks passed. Run APK and native image checks before publishing.")
    else:
        print("Tests skipped. Run fork, APK and native image checks before publishing.")
    clean()
    run("git", "range-diff", state["old_base"] + ".." + state["old_head"],
        state["new_base"] + "..HEAD")
    run("git", "update-ref", BASE_REF, state["new_base"])
    path.unlink()
    print("Rebase complete. Review the range-diff above; backup: " + state["backup"])
    print("Publish main separately after reviewing the result (see FORK-README.md).")


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--continue", dest="resume", action="store_true", help="continue after resolving conflicts or retry failed checks")
    mode.add_argument("--abort", action="store_true", help="abort an active Git rebase and restore its original main")
    parser.add_argument("--base", default="latest-stable", help="new upstream tag/ref (default: highest stable numeric upstream tag)")
    parser.add_argument("--from-base", help="previous upstream base, for initial setup or repairing a stale local base marker")
    parser.add_argument("--dry-run", action="store_true", help="inspect cached refs without fetching or changing anything")
    parser.add_argument("--skip-tests", action="store_true", help="leave lightweight checks to a separate manual run")
    args = parser.parse_args()
    ROOT = Path(git("rev-parse", "--show-toplevel").stdout.strip())
    path = git_path("fork-rebase.json")

    if args.dry_run and (args.resume or args.abort):
        parser.error("--dry-run cannot be combined with --continue or --abort")
    if args.resume or args.abort:
        if not path.exists():
            raise RuntimeError("No saved fork rebase; use Git directly if this rebase was started elsewhere.")
        state = json.loads(path.read_text())
        if rebasing():
            planned_rebase(state)
        if args.abort:
            if not rebasing():
                if commit("HEAD") == state["old_head"]:
                    main_branch()
                    clean()
                    path.unlink()
                    print("Pending plan cancelled; main has not moved. Backup: " + state["backup"])
                    return
                raise RuntimeError("Git has already finished the rebase. Retry checks with --continue, or inspect backup " + state["backup"])
            rebase("--abort")
            path.unlink()
            print("Rebase aborted; original main restored. Backup: " + state["backup"])
        else:
            if rebasing():
                rebase("--continue")
            finish(state, path, args.skip_tests)
        return

    if path.exists():
        raise RuntimeError("A fork rebase is pending; use --continue or --abort.")
    main_branch()
    clean()
    for name in ["rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD"]:
        if git_path(name).exists():
            raise RuntimeError("Finish the existing Git operation before starting a fork rebase.")
    git("remote", "get-url", "upstream")
    if not args.dry_run:
        # Isolate upstream tags from any tags published by this fork. Never
        # overwrite local release tags or mistake a fork tag for an upstream base.
        run("git", "fetch", "--prune", "--no-tags", "upstream",
            "+refs/heads/*:refs/remotes/upstream/*", "+refs/tags/*:" + TAG_PREFIX + "*")
    base = old_base(args.from_base)
    head = commit("HEAD")
    target, target_ref = target_base(args.base)
    count = git("rev-list", "--count", base + "..HEAD").stdout.strip()
    if count == "0":
        raise RuntimeError("No committed fork patches to replay; commit the extensions on main first.")
    print("Fork stack: " + count + " commits; previous base: " + base + "; new base: " + target_ref + " (" + target + ")")
    if args.dry_run:
        print(git("log", "--oneline", "--reverse", base + "..HEAD").stdout, end="")
        print("Dry run: cached refs only; no fetch, backup, rebase, or tests performed.")
        return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = "backup/main-" + stamp
    run("git", "branch", backup, head)
    state = {"old_head": head, "old_base": base, "new_base": target,
             "backup": backup, "tests": not args.skip_tests}
    # Exclusive creation prevents another helper from replacing an active plan.
    with path.open("x") as stream:
        json.dump(state, stream)
        stream.flush()
        os.fsync(stream.fileno())
    print("Saved backup: " + backup, flush=True)
    rebase("--onto", target, base, "main")
    finish(state, path, args.skip_tests)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError) as error:
        print("fork rebase: " + str(error), file=sys.stderr)
        print("If a fork rebase is pending, resolve conflicts and run --continue; see FORK-README.md for recovery.", file=sys.stderr)
        sys.exit(1)
