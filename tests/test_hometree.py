"""Local regression tests; all filesystem mutations use temporary directories."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hometree as ht


class HomeTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        (self.home / "Downloads").mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_tree_is_compact_and_never_follows_symlinks(self):
        d = self.home / "Downloads"
        (d / "inside").mkdir()
        (d / "inside" / "a.txt").write_text("hello")
        (d / "jump").symlink_to(self.home, target_is_directory=True)
        out = io.StringIO()
        dirs, files, capped = ht.tree_display(d, out, depth=3, dirs_only=False, hidden=False, max_entries=100)
        self.assertEqual((dirs, files, capped), (1, 2, False))
        self.assertIn("jump@", out.getvalue())
        self.assertEqual(out.getvalue().count("a.txt"), 1)

    def test_tree_max_entries(self):
        for i in range(9):
            (self.home / "Downloads" / f"{i}.txt").write_text("x")
        out = io.StringIO()
        dirs, files, capped = ht.tree_display(self.home / "Downloads", out, depth=2,
                                                  dirs_only=False, hidden=False, max_entries=3)
        self.assertTrue(capped)
        self.assertEqual(files, 3)
        self.assertIn("truncated", out.getvalue())

    def test_plan_skips_projects_symlinks_private_filenames_and_vm_files(self):
        d = self.home / "Downloads"
        for name in ["holiday.jpg", "notes.pdf", "example.zip", "github-recovery-codes.txt",
                     "boot.iso", "secret.key", "run.sh", ".env", "Screenshot_01.png"]:
            (d / name).write_bytes(b"demo")
        (d / "my-project").mkdir()
        (d / "alias.jpg").symlink_to(d / "holiday.jpg")
        plan, skipped = ht.plan_organization(d, self.home)
        self.assertEqual({Path(x.source).name for x in plan}, {"holiday.jpg", "notes.pdf"})
        self.assertGreaterEqual(len(skipped), 8)
        plan_archives, _ = ht.plan_organization(d, self.home, archives=True)
        self.assertIn("example.zip", {Path(x.source).name for x in plan_archives})

    def test_dry_run_does_not_move_files_or_create_dirs(self):
        d = self.home / "Downloads"
        (d / "notes.pdf").write_bytes(b"doc")
        plan, _ = ht.plan_organization(d, self.home)
        self.assertEqual(len(plan), 1)
        self.assertTrue((d / "notes.pdf").exists())
        self.assertFalse((self.home / "Documents").exists())

    def test_collision_refused(self):
        d = self.home / "Downloads"
        (d / "notes.pdf").write_bytes(b"doc")
        target = self.home / "Documents" / "Imported"
        target.mkdir(parents=True)
        (target / "notes.pdf").write_bytes(b"different")
        plan, skipped = ht.plan_organization(d, self.home)
        self.assertEqual(plan, [])
        self.assertTrue(any("already exists" in why for _, why in skipped))

    def test_move_and_undo_exact_original(self):
        d = self.home / "Downloads"
        payload = b"My nonsecret example" * 100
        (d / "notes.pdf").write_bytes(payload)
        plan, _ = ht.plan_organization(d, self.home)
        with mock.patch.object(ht.os, "geteuid", return_value=1000):
            manifest, moved = ht.execute_moves(plan, self.home, confirm=False)
            self.assertEqual(moved, 1)
            self.assertFalse((d / "notes.pdf").exists())
            self.assertEqual((self.home / "Documents" / "Imported" / "notes.pdf").read_bytes(), payload)
            self.assertIsNotNone(manifest)
            restored, skipped = ht.undo_moves(manifest, self.home, confirm=False)
            self.assertEqual((restored, skipped), (1, 0))
            self.assertEqual((d / "notes.pdf").read_bytes(), payload)

    def test_undo_wont_overwrite_conflicting_original(self):
        d = self.home / "Downloads"
        (d / "notes.pdf").write_bytes(b"old")
        plan, _ = ht.plan_organization(d, self.home)
        with mock.patch.object(ht.os, "geteuid", return_value=1000):
            manifest, _ = ht.execute_moves(plan, self.home, confirm=False)
            (d / "notes.pdf").write_bytes(b"new")
            restored, skipped = ht.undo_moves(manifest, self.home, confirm=False)
        self.assertEqual((restored, skipped), (0, 1))
        self.assertEqual((d / "notes.pdf").read_bytes(), b"new")

    def test_undo_skips_modified_target(self):
        d = self.home / "Downloads"
        (d / "a.txt").write_bytes(b"old")
        plan, _ = ht.plan_organization(d, self.home)
        with mock.patch.object(ht.os, "geteuid", return_value=1000):
            manifest, _ = ht.execute_moves(plan, self.home, confirm=False)
            (self.home / "Documents" / "Imported" / "a.txt").write_bytes(b"changed data")
            restored, skipped = ht.undo_moves(manifest, self.home, confirm=False)
        self.assertEqual((restored, skipped), (0, 1))
        self.assertFalse((d / "a.txt").exists())

    def test_symlinked_destination_rejected(self):
        target = self.home / "Documents"
        target.symlink_to(self.home / "Downloads", target_is_directory=True)
        (self.home / "Downloads" / "a.pdf").write_bytes(b"hi")
        moves, skip = ht.plan_organization(self.home / "Downloads", self.home)
        self.assertEqual(moves, [])
        self.assertTrue(skip)

    def test_cache_only_considers_old_files_in_whitelist(self):
        from time import time
        old = time() - 70 * 86400
        pip = self.home / ".cache" / "pip" / "http"
        pip.mkdir(parents=True)
        (pip / "old.bin").write_bytes(b"cache")
        os.utime(pip / "old.bin", (old, old))
        (pip / "new.bin").write_bytes(b"cache")
        browser = self.home / ".cache" / "mozilla"
        browser.mkdir()
        (browser / "old.bin").write_bytes(b"private")
        os.utime(browser / "old.bin", (old, old))
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.home / ".cache")}):
            cands = ht.cache_candidates(self.home, 30)
        self.assertEqual({x.path.name for x in cands}, {"old.bin"})

    def test_root_organize_rejects_outside_home(self):
        with self.assertRaises(ValueError):
            ht.ensure_user_location(Path("/etc"), self.home)

    def test_file_names_not_sent_or_collected_by_default(self):
        self.assertTrue(ht.candidate_category("token.txt", archives=False)[0] is None)
        self.assertTrue(ht.candidate_category("account-recovery-codes.txt", archives=False)[0] is None)

    def test_cache_cleanup_does_not_touch_pip_selfcheck(self):
        from time import time
        old = time() - 70 * 86400
        root = self.home / ".cache" / "pip"
        (root / "http").mkdir(parents=True)
        (root / "selfcheck").mkdir()
        for sub in ["http", "selfcheck"]:
            p = root / sub / "meta.bin"
            p.write_bytes(b"test")
            os.utime(p, (old, old))
        with mock.patch.object(ht.os, "geteuid", return_value=1000), mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.home / ".cache")}), contextlib.redirect_stdout(io.StringIO()):
            done, skipped = ht.cache_action(self.home, clean=True, age=30, confirm=False)
        self.assertEqual((done, skipped), (1, 0))
        self.assertTrue((root / "selfcheck" / "meta.bin").exists())
        self.assertFalse((root / "http" / "meta.bin").exists())

    def test_symlink_cache_location_skipped(self):
        other = self.home / "safe"
        other.mkdir()
        (self.home / ".cache").symlink_to(other, target_is_directory=True)
        with mock.patch.dict(os.environ, {"XDG_CACHE_HOME": str(self.home / ".cache")}):
            self.assertEqual(ht.cache_candidates(self.home, 30), [])

    def test_updated_source_skipped_at_apply_time(self):
        d = self.home / "Downloads"
        p = d / "a.pdf"
        p.write_bytes(b"initial")
        plan, _ = ht.plan_organization(d, self.home)
        p.write_bytes(b"changed later")
        with mock.patch.object(ht.os, "geteuid", return_value=1000), contextlib.redirect_stdout(io.StringIO()):
            manifest, moved = ht.execute_moves(plan, self.home, confirm=False)
        self.assertEqual(moved, 0)
        self.assertTrue(p.exists())
        self.assertTrue(manifest.exists())


if __name__ == "__main__":
    unittest.main()

class DependencyProtectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_refuses_files_within_git_checkout(self):
        repo = self.home / 'workspace'
        (repo / '.git').mkdir(parents=True)
        (repo / 'assets').mkdir()
        (repo / 'assets' / 'photo.png').write_bytes(b'test')
        with self.assertRaisesRegex(ValueError, 'Project dependency'):
            ht.plan_organization(repo / 'assets', self.home)

    def test_refuses_active_named_project(self):
        project = self.home / 'Documents' / 'apex32-secure'
        project.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'Protected active project'):
            ht.plan_organization(project, self.home)

    def test_refuses_sensitive_application_directory(self):
        cache = self.home / '.config' / 'some-app'
        cache.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'Application-managed'):
            ht.plan_organization(cache, self.home)

    def test_dependency_scan_is_read_only(self):
        repo = self.home / 'random-tool'
        (repo / '.git').mkdir(parents=True)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ht.dependency_review(self.home)
        self.assertIn('random-tool/', out.getvalue())
        self.assertEqual(list(repo.iterdir()), [repo / '.git'])
