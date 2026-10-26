#!/usr/bin/env python3
"""Integration tests for the rebase helper, using disposable local repositories."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("rebase-fork.py").resolve()


class RebaseForkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="librera-rebase-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.upstream = self.root / "foobnix" / "LibreraReader"
        self.upstream.mkdir(parents=True)
        self.env = os.environ.copy()
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_AUTHOR_NAME="Fork test", GIT_AUTHOR_EMAIL="fork@example.invalid",
                        GIT_COMMITTER_NAME="Fork test", GIT_COMMITTER_EMAIL="fork@example.invalid",
                        GIT_EDITOR="true", GIT_ALLOW_PROTOCOL="file")
        self.git(self.upstream, "init", "-b", "master")
        (self.upstream / "shared.txt").write_text("base\n")
        self.save(self.upstream, "Upstream base")
        self.base = self.sha(self.upstream)
        self.git(self.upstream, "tag", "release-old")
        self.fork = self.root / "fork"
        self.git(self.root, "clone", str(self.upstream), str(self.fork))
        self.git(self.fork, "branch", "-m", "main")
        self.git(self.fork, "remote", "rename", "origin", "upstream")
        self.git(self.fork, "remote", "add", "origin", str(self.root / "vm75" / "LibreraReader"))
        self.git(self.fork, "config", "branch.main.remote", "origin")
        self.git(self.fork, "config", "branch.main.merge", "refs/heads/main")
        (self.fork / "codecs.txt").write_text("Native MuPDF and JXL integration\n")
        tests = self.fork / "Builder/tests"
        tests.mkdir(parents=True)
        (tests / "test_fork_build.py").write_text(
            "import os\n"
            "with open(os.environ['FORK_TEST_CALLS'], 'a') as out: out.write('check\\n')\n"
            "raise SystemExit(1 if os.environ.get('FORK_TEST_FAIL') else 0)\n")
        for name in ("link_to_mupdf_fork.sh", "build-nomupdf.sh", "all-release.sh", "build-librera-beta.sh"):
            (self.fork / "Builder" / name).write_text("#!/bin/bash\ntrue\n")
        self.save(self.fork, "Fork extensions")
        self.before = self.sha(self.fork)
        self.state = self.fork / ".git" / "fork-rebase.json"
        self.calls = self.root / "check-calls"
        self.env["FORK_TEST_CALLS"] = str(self.calls)

    def git(self, cwd, *args, check=True):
        result = subprocess.run(["git", *args], cwd=cwd, env=self.env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def save(self, repo, message):
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-m", message)

    def sha(self, repo, ref="HEAD"):
        return self.git(repo, "rev-parse", ref)

    def advance(self):
        (self.upstream / "new-upstream.txt").write_text("upstream update\n")
        self.save(self.upstream, "Upstream update")
        return self.sha(self.upstream)

    def helper(self, *args, ok=True, use_default=False):
        if not use_default and not any(arg in args for arg in ("--base", "--continue", "--abort")):
            args = ("--base", "upstream/master", *args)
        result = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.fork,
                                env=self.env, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def successful(self, base):
        self.assertFalse(self.state.exists())
        self.assertEqual(self.sha(self.fork, "refs/fork/upstream-base"), base)
        self.assertEqual(self.git(self.fork, "rev-list", "--count", base + "..HEAD"), "1")
        self.assertEqual((self.fork / "codecs.txt").read_text(), "Native MuPDF and JXL integration\n")
        self.assertEqual(self.git(self.fork, "status", "--porcelain"), "")
        backups = self.git(self.fork, "for-each-ref", "--format=%(objectname)", "refs/heads/backup/")
        self.assertIn(self.before, backups.splitlines())

    def check_calls(self):
        return self.calls.read_text().splitlines()

    def conflict(self):
        (self.fork / "shared.txt").write_text("fork value\n")
        self.git(self.fork, "add", "shared.txt")
        self.git(self.fork, "commit", "--amend", "--no-edit")
        self.before = self.sha(self.fork)
        (self.upstream / "shared.txt").write_text("new upstream value\n")
        self.save(self.upstream, "Conflicting upstream update")
        output = self.helper(ok=False)
        self.assertIn("CONFLICT", output)
        self.assertTrue(self.state.exists())

    def test_dry_run_uses_cached_refs_and_changes_nothing(self):
        self.advance()
        refs = self.git(self.fork, "show-ref")
        output = self.helper("--dry-run")
        self.assertIn("cached refs only", output)
        self.assertEqual(self.git(self.fork, "show-ref"), refs)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.calls.exists())

    def test_rebase_preserves_patch_backup_and_runs_checks(self):
        target = self.advance()
        self.git(self.fork, "config", "rebase.updateRefs", "true")
        self.helper()
        self.successful(target)
        self.assertEqual(self.check_calls(), ["check"])

    def test_dirty_worktree_refused_before_fetch(self):
        self.advance()
        (self.fork / "untracked.txt").write_text("do not touch\n")
        output = self.helper(ok=False)
        self.assertIn("uncommitted changes", output)
        self.assertEqual(self.sha(self.fork), self.before)
        self.assertEqual(self.sha(self.fork, "upstream/master"), self.base)
        self.assertFalse(self.state.exists())

    def test_wrong_branch_refused(self):
        self.git(self.fork, "switch", "-c", "work")
        self.assertIn("on main", self.helper(ok=False))
        self.assertEqual(self.sha(self.fork), self.before)

    def test_conflict_continue(self):
        self.conflict()
        (self.fork / "shared.txt").write_text("resolved with both changes\n")
        self.git(self.fork, "add", "shared.txt")
        self.helper("--continue")
        self.successful(self.sha(self.upstream))
        self.assertEqual((self.fork / "shared.txt").read_text(), "resolved with both changes\n")

    def test_conflict_abort_restores_original_main(self):
        self.conflict()
        self.helper("--abort")
        self.assertFalse(self.state.exists())
        self.assertEqual(self.sha(self.fork), self.before)
        self.assertEqual((self.fork / "shared.txt").read_text(), "fork value\n")
        self.assertEqual(self.git(self.fork, "status", "--porcelain"), "")
        self.assertFalse(self.calls.exists())

    def test_failed_checks_can_be_retried_without_another_rebase(self):
        target = self.advance()
        self.env["FORK_TEST_FAIL"] = "1"
        self.helper(ok=False)
        rebased = self.sha(self.fork)
        self.assertTrue(self.state.exists())
        self.assertEqual(self.git(self.fork, "show-ref", "--verify", "refs/fork/upstream-base", check=False), "")
        self.env.pop("FORK_TEST_FAIL")
        self.helper("--continue")
        self.assertEqual(self.sha(self.fork), rebased)
        self.successful(target)
        self.assertEqual(self.check_calls(), ["check", "check"])

    def test_skip_tests_is_explicit(self):
        target = self.advance()
        self.assertIn("Tests skipped", self.helper("--skip-tests"))
        self.successful(target)
        self.assertFalse(self.calls.exists())

    def test_tagged_fork_can_supply_its_base_explicitly(self):
        self.git(self.fork, "tag", "fork-release")
        target = self.advance()
        self.assertIn("--from-base", self.helper(ok=False))
        self.helper("--from-base", "release-old")
        self.successful(target)

    def test_continue_refuses_a_different_active_rebase(self):
        self.conflict()
        state = json.loads(self.state.read_text())
        state["new_base"] = self.base
        self.state.write_text(json.dumps(state))
        self.assertIn("does not match", self.helper("--continue", ok=False))
        self.assertTrue((self.fork / ".git/rebase-merge").exists())

    def test_abort_cancels_a_plan_when_git_refused_to_start(self):
        self.advance()
        hook = self.fork / ".git/hooks/pre-rebase"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        self.helper(ok=False)
        self.assertTrue(self.state.exists())
        self.assertEqual(self.sha(self.fork), self.before)
        self.assertIn("plan cancelled", self.helper("--abort"))
        self.assertFalse(self.state.exists())
        self.assertFalse(self.calls.exists())

    def test_stable_bases_require_explicit_initial_base_then_are_remembered(self):
        self.git(self.upstream, "switch", "-c", "stable")
        (self.upstream / "stable.txt").write_text("stable fix\n")
        self.save(self.upstream, "Stable-only fix")
        self.git(self.upstream, "tag", "stable-old")
        stable_old = self.sha(self.upstream)
        self.git(self.fork, "fetch", "--tags", "upstream")
        self.git(self.fork, "rebase", "--onto", stable_old, self.base, "main")
        self.git(self.fork, "config", "remote.upstream.fetch", "+refs/heads/master:refs/remotes/upstream/master")
        self.git(self.fork, "update-ref", "-d", "refs/remotes/upstream/stable")
        self.before = self.sha(self.fork)
        (self.upstream / "stable-next.txt").write_text("next stable fix\n")
        self.save(self.upstream, "Next stable fix")
        self.git(self.upstream, "tag", "stable-next")
        self.assertIn("--from-base", self.helper("--base", "stable-next", ok=False))
        self.helper("--from-base", "stable-old", "--base", "stable-next")
        self.successful(self.sha(self.upstream))
        (self.upstream / "stable-last.txt").write_text("later stable fix\n")
        self.save(self.upstream, "Later stable fix")
        self.git(self.upstream, "tag", "stable-last")
        self.helper("--base", "stable-last")
        self.successful(self.sha(self.upstream))
        self.assertTrue((self.fork / "stable.txt").exists())

    def test_latest_stable_uses_upstream_tags_and_ignores_fork_and_prerelease_tags(self):
        self.git(self.upstream, "tag", "10.0.7")
        self.git(self.upstream, "tag", "10.0.9")
        target = self.advance()
        self.git(self.upstream, "tag", "10.0.10")
        self.git(self.upstream, "tag", "11.0.0-rc1")
        self.git(self.fork, "tag", "99.0.0")
        self.git(self.fork, "tag", "10.0.10")
        fork_tag = self.sha(self.fork, "10.0.10")
        self.helper("--from-base", "release-old", use_default=True)
        self.successful(target)
        self.assertEqual(self.sha(self.fork, "10.0.10"), fork_tag)
        self.assertEqual(self.sha(self.fork, "refs/fork/upstream-tags/10.0.10"), target)

    def test_dry_run_latest_stable_requires_cached_upstream_tags(self):
        self.assertIn("No cached stable upstream tags", self.helper("--base", "latest-stable", "--dry-run", ok=False))
        self.assertFalse(self.state.exists())

    def test_numeric_base_prefers_fetched_upstream_tag(self):
        target = self.advance()
        self.git(self.upstream, "tag", "10.0.8")
        self.git(self.fork, "tag", "10.0.8")
        self.helper("--base", "10.0.8", "--from-base", "release-old")
        self.successful(target)

    def test_merge_in_fork_stack_is_refused(self):
        self.git(self.fork, "switch", "-c", "topic", self.base)
        (self.fork / "topic.txt").write_text("topic\n")
        self.save(self.fork, "Topic")
        self.git(self.fork, "switch", "main")
        self.git(self.fork, "merge", "--no-ff", "topic", "-m", "Merge topic")
        before = self.sha(self.fork)
        self.assertIn("merge commits", self.helper("--from-base", self.base, ok=False))
        self.assertEqual(self.sha(self.fork), before)
        self.assertFalse(self.state.exists())

    def test_abort_after_completed_rebase_does_not_reset_history(self):
        self.advance()
        self.env["FORK_TEST_FAIL"] = "1"
        self.helper(ok=False)
        before = self.sha(self.fork)
        self.assertIn("Git has already finished", self.helper("--abort", ok=False))
        self.assertEqual(self.sha(self.fork), before)
        self.assertTrue(self.state.exists())


if __name__ == "__main__":
    unittest.main()
