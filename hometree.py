#!/usr/bin/env python3
"""HomeTree — dependency-free, preview-first Linux filesystem explorer/organizer."""
from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Iterator, TextIO

VERSION = "0.2.1"
MAX_SCAN_ENTRIES = 1500
ALLOWED_CACHE = ("pip", "thumbnails")
IMAGE = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".avif", ".heic"}
VIDEO = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}
AUDIO = {".mp3", ".flac", ".wav", ".m4a", ".ogg", ".opus", ".aac"}
DOCUMENT = {".pdf", ".doc", ".docx", ".txt", ".md", ".odt", ".ppt", ".pptx", ".xls", ".xlsx", ".ods", ".csv", ".epub"}
ARCHIVE = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".zst", ".tgz"}
# Do not infer that files in these categories are disposable or safe to relocate.
REVIEW_SUFFIXES = {".iso", ".img", ".vmdk", ".vdi", ".qcow2", ".efi", ".ovpn", ".pem", ".key", ".p12", ".db", ".sqlite", ".sqlite3", ".py", ".sh", ".exe", ".appimage", ".desktop", ".part", ".aria2"}
REVIEW_WORDS = ("screenshot", "screencast", "screen-record", "recording", "capture", "evidence", "backup", "recovery", "secret", "token", "credential", "password", "private", "keyfile", "2fa", "otp", "vault", "auth", "api-key", "ssh", "account", "codes", "flag", "hash", "session", "profile", "login")
PROTECTED_TOP = {".git", ".venv", "venv", "node_modules", ".config", ".local", ".cache", ".ssh", ".gnupg", ".mozilla", "Documents", "Downloads", "Desktop", "Pictures", "Videos", "Music", "Projects", "Websites", "Cybersecurity", "Archives", "Review", "Games", "FusionShare", "Applications"}


def pretty_size(n: int) -> str:
    amount = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if amount < 1024 or unit == "TiB":
            return f"{int(amount)} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{n} B"


def color(s: str, ansi: str) -> str:
    return f"\033[{ansi}m{s}\033[0m" if sys.stdout.isatty() and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb" else s


def banner() -> None:
    """Readable DEV32 header; uses text characters supported by typical terminals."""
    width = shutil.get_terminal_size((80, 24)).columns
    n = min(65, max(28, width - 3))
    print("\n" + color("╭" + "─" * (n - 2) + "╮", "36"))
    print("  " + color("SPES_MEA_IN_DEO_EST#32", "1;36") + "   " + color("#DEV32#", "1;32"))
    print("  " + color("HomeTree", "1;37") + color("  /  File Explorer & Safe Organizer", "2;37"))
    print(color("├" + "─" * (n - 2) + "┤", "36"))


def footer() -> None:
    """A dedicated, visible developer contact section."""
    width = shutil.get_terminal_size((80, 24)).columns
    n = min(65, max(28, width - 3))
    print("\n" + color("├" + "─" * (n - 2) + "┤", "36"))
    print("  " + color("DEVELOPER & SUPPORT", "1;36"))
    print("  " + color("✉  dev32@apex32-secure.com", "1;32"))
    print("  " + color("Feedback · Bug reports · Support", "2;37"))
    print(color("╰" + "─" * (n - 2) + "╯", "36"))


def home_path() -> Path:
    return Path.home().resolve()


def within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def path_is_free_of_symlinks(path: Path) -> bool:
    """Check all existing components (but never dereference them)."""
    raw = Path(os.path.abspath(path))
    components = raw.parts
    cursor = Path(components[0])
    for part in components[1:]:
        cursor = cursor / part
        try:
            mode = cursor.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError:
            return False
        if stat.S_ISLNK(mode):
            return False
    return True


def ensure_user_location(path: Path, home: Path, *, must_exist: bool = True) -> Path:
    p = Path(os.path.abspath(path.expanduser()))
    if not within(p, home):
        raise ValueError("Organizer operates only within your home directory")
    if not path_is_free_of_symlinks(p):
        raise ValueError("Symlinked paths are excluded from relocation")
    if must_exist and not p.is_dir():
        raise ValueError(f"Not a readable directory: {p}")
    return p


# Conservative boundaries: local application state and project trees require expert review.
PROTECTED_PROJECT_NAMES = {"apex32-secure", "apex_dashboard", "SNIP", "snip 2", "APEX32-Boot-Manager"}
PROJECT_MARKERS = (".git", ".venv", "venv", "node_modules", "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "CMakeLists.txt")
PROTECTED_HOME_PARTS = {".config", ".local", ".cache", ".ssh", ".gnupg", ".mozilla", ".var", ".wine", ".steam", "FusionShare", "Games"}


def organizer_boundary(folder: Path, home: Path) -> str | None:
    """Refuse file moves from known sensitive/application/project directories."""
    folder = ensure_user_location(folder, home)
    relative = folder.relative_to(home)
    if any(part in PROTECTED_PROJECT_NAMES for part in relative.parts):
        return "Protected active project"
    if any(part in PROTECTED_HOME_PARTS for part in relative.parts):
        return "Application-managed or sensitive directory"
    for current in (home / Path(*relative.parts[:i]) for i in range(1, len(relative.parts) + 1)):
        for marker in PROJECT_MARKERS:
            if os.path.lexists(current / marker):
                return f"Project dependency marker ({marker}) at {current}"
    return None


def dependency_review(home: Path, *, max_items: int = 120) -> None:
    """Read-only inventory; deliberately does not guess service path migrations."""
    scanned = 0
    print("\nDependency awareness: directories listed here are NOT approved for relocation.")
    with os.scandir(home) as it:
        dirs = sorted((entry for entry in it if entry.is_dir(follow_symlinks=False) and not entry.name.startswith('.')), key=lambda e:e.name.casefold())
    for entry in dirs:
        if entry.name in PROTECTED_TOP:
            continue
        folder = Path(entry.path)
        markers = [marker for marker in PROJECT_MARKERS if os.path.lexists(folder / marker)]
        if not markers:
            continue
        print(f"  {entry.name}/ — detected: {', '.join(markers)}; path-dependent references may exist")
        scanned += 1
        if scanned >= max_items:
            print("  … output capped")
            break
    print("Read-only. No automated rewriting of services, launchers, environments, or build artifacts.")


def tree_display(root: Path, out: TextIO, *, depth: int, dirs_only: bool,
                 hidden: bool, max_entries: int) -> tuple[int, int, bool]:
    if depth < 0 or max_entries < 1:
        raise ValueError("Depth must be >= 0 and max entries must be >= 1")
    stats = [0, 0]
    count = 0
    truncated = False
    out.write(f"{root}/\n")

    def walk(directory: Path, pad: str, level: int) -> None:
        nonlocal count, truncated
        if level >= depth or truncated:
            return
        try:
            with os.scandir(directory) as scan:
                entries = [ent for ent in scan if hidden or not ent.name.startswith(".")]
            if dirs_only:
                entries = [e for e in entries if e.is_dir(follow_symlinks=False)]
            entries.sort(key=lambda x: (not x.is_dir(follow_symlinks=False), x.name.casefold()))
        except OSError as exc:
            out.write(pad + f"[unreadable: {type(exc).__name__}]\n")
            return
        for idx, ent in enumerate(entries):
            if count >= max_entries:
                out.write(pad + "└── … truncated (use --max-entries to expand)\n")
                truncated = True
                return
            last = idx == len(entries) - 1
            d = ent.is_dir(follow_symlinks=False)
            link = ent.is_symlink()
            desc = ent.name + ("/" if d else "@" if link else "")
            out.write(pad + ("└── " if last else "├── ") + desc + "\n")
            count += 1
            stats[0 if d else 1] += 1
            if d:
                walk(Path(ent.path), pad + ("    " if last else "│   "), level + 1)
                if truncated:
                    return
    walk(root, "", 0)
    return stats[0], stats[1], truncated


def candidate_category(name: str, *, archives: bool) -> tuple[str | None, str]:
    low = name.casefold()
    if low.startswith(".") or any(t in low for t in REVIEW_WORDS):
        return None, "Hidden, potential evidence, backup, or sensitive filename"
    suffix = Path(low).suffix
    if suffix in REVIEW_SUFFIXES or low.endswith((".tar.part", ".zip.part", ".tar.gz.part")):
        return None, "Executable, script, sensitive, VM, or state file"
    if suffix in IMAGE:
        return "Pictures/Imported", "Image"
    if suffix in VIDEO:
        return "Videos/Imported", "Video"
    if suffix in AUDIO:
        return "Music/Imported", "Audio"
    if suffix in DOCUMENT:
        return "Documents/Imported", "Document"
    if suffix in ARCHIVE:
        return ("Archives/Compressed", "Compressed archive") if archives else (None, "Archive requires --include-archives")
    return None, "Unknown type — review manually"


@dataclass(frozen=True)
class Move:
    source: str
    target: str
    category: str
    reason: str
    size: int
    inode: int
    device: int
    mtime_ns: int


def plan_organization(folder: Path, home: Path, *, archives: bool = False) -> tuple[list[Move], list[tuple[str, str]]]:
    folder = ensure_user_location(folder, home)
    boundary = organizer_boundary(folder, home)
    if boundary:
        raise ValueError(f"Organizer refused this directory: {boundary}")
    # Only direct ordinary files; never recurse into project / application directories.
    if folder == home:
        print("INFO: Home-root organization considers loose files only, not directories.", file=sys.stderr)
    items: list[Move] = []
    skipped: list[tuple[str, str]] = []
    with os.scandir(folder) as it:
        entries = sorted(it, key=lambda e: e.name.casefold())
    for ent in entries:
        src = Path(ent.path)
        if ent.is_symlink():
            skipped.append((ent.name, "Symbolic link"))
            continue
        try:
            st = ent.stat(follow_symlinks=False)
        except OSError:
            skipped.append((ent.name, "Not accessible"))
            continue
        if not stat.S_ISREG(st.st_mode):
            skipped.append((ent.name, "Directory/device; protected from automatic moves"))
            continue
        if st.st_uid != os.getuid():
            skipped.append((ent.name, "Different owner"))
            continue
        cat, why = candidate_category(ent.name, archives=archives)
        if cat is None:
            skipped.append((ent.name, why))
            continue
        dest = home / cat / ent.name
        if src == dest or not path_is_free_of_symlinks(dest.parent):
            skipped.append((ent.name, "Already organized or symlinked destination"))
            continue
        if os.path.lexists(dest):
            skipped.append((ent.name, "Destination already exists (never overwrite)"))
            continue
        items.append(Move(str(src), str(dest), cat, why, st.st_size,
                          st.st_ino, st.st_dev, st.st_mtime_ns))
    return items, skipped


def print_plan(moves: list[Move], skipped: list[tuple[str, str]], *, home: Path | None = None, show_skipped: bool = False) -> None:
    home = home or home_path()
    print("\n" + color("Organization preview — NO CHANGES", "1;36"))
    for m in moves:
        print(f"  {Path(m.source).name}  →  ~/{Path(m.target).relative_to(home)}  ({pretty_size(m.size)})")
    print(f"\nEligible: {len(moves)} file(s), {pretty_size(sum(m.size for m in moves))}; skipped: {len(skipped)}")
    if show_skipped:
        for n, reason in skipped[:200]:
            print(f"  SKIP {n} — {reason}")
        if len(skipped) > 200:
            print(f"  ... {len(skipped)-200} more skipped entries")
    print("Project directories, executable scripts, symlinks, hidden files and VM media are never moved automatically.")


def atomic_rename_no_replace(src: Path, dest: Path) -> None:
    """Linux renameat2(RENAME_NOREPLACE) prevents clobbering target and cross-device copies."""
    libc = ctypes.CDLL(None, use_errno=True)
    if not hasattr(libc, "renameat2"):
        raise OSError(errno.ENOSYS, "Linux renameat2 unavailable; refusing unsafe fallback")
    libc.renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    libc.renameat2.restype = ctypes.c_int
    rv = libc.renameat2(-100, os.fsencode(src), -100, os.fsencode(dest), 1)
    if rv != 0:
        e = ctypes.get_errno()
        raise OSError(e, os.strerror(e), str(src), str(dest))


def check_fingerprint(path: Path, m: Move) -> bool:
    try:
        s = path.lstat()
    except OSError:
        return False
    return (stat.S_ISREG(s.st_mode) and not path.is_symlink()
            and s.st_ino == m.inode and s.st_dev == m.device
            and s.st_size == m.size and s.st_mtime_ns == m.mtime_ns)


def state_root(home: Path) -> Path:
    return home / ".local" / "state" / "hometree"


def write_private_json(path: Path, data: dict) -> None:
    if not path_is_free_of_symlinks(path.parent):
        raise ValueError("State directory may not contain symlinks")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)
        fp.write("\n")
        fp.flush()
        os.fsync(fp.fileno())


def execute_moves(moves: list[Move], home: Path, *, confirm: bool = True) -> tuple[Path | None, int]:
    if not moves:
        print("Nothing eligible to organize.")
        return None, 0
    if os.geteuid() == 0:
        raise ValueError("Refusing to organize files as root")
    if confirm:
        response = input(f"Type MOVE {len(moves)} to apply exactly these proposals: ").strip()
        if response != f"MOVE {len(moves)}":
            print("Cancelled; no moves performed.")
            return None, 0
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report = state_root(home) / f"moves-{run_id}.json"
    # Reserve log before first move: failure to create audit log means no moves.
    # Journal the entire planned set before moving anything. On process interruption,
    # a pending entry allows inspection/rollback of a move that reached disk but not the log.
    data = {"version": VERSION, "run_id": run_id, "created_utc": datetime.now(timezone.utc).isoformat(),
            "moves": [{**asdict(m), "status": "pending"} for m in moves], "skipped": []}
    write_private_json(report, data)
    done = 0
    for i, m in enumerate(moves):
        src, dest = Path(m.source), Path(m.target)
        try:
            ensure_user_location(src.parent, home)
            if organizer_boundary(src.parent, home):
                raise ValueError("Source is now under a protected application/project boundary")
            ensure_user_location(dest.parent, home, must_exist=False)
            if not check_fingerprint(src, m) or os.path.lexists(dest):
                raise ValueError("Source changed or destination occupied")
            dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not path_is_free_of_symlinks(dest.parent):
                raise ValueError("Destination parent has become a symlink")
            if src.stat().st_dev != dest.parent.stat().st_dev:
                raise ValueError("Cross-device move prohibited")
            atomic_rename_no_replace(src, dest)
        except (OSError, ValueError) as exc:
            data["moves"][i]["status"] = "skipped"
            data["skipped"].append({"source": m.source, "error": str(exc)})
            replace_json(report, data)
            print(f"SKIPPED {src.name}: {exc}", file=sys.stderr)
            continue
        data["moves"][i]["status"] = "moved"
        done += 1
        try:
            replace_json(report, data)
        except OSError as exc:
            # The initial pending entry remains in the audit log for recovery.
            print(f"STOP: moved {src.name}, but could not update audit log: {exc}", file=sys.stderr)
            print(f"Check {report} and the destination before retrying or undoing.", file=sys.stderr)
            break
    print(f"Moved {done} file(s); {len(data['skipped'])} skipped. Rollback manifest: {report}")
    return report, done


def replace_json(path: Path, content: dict) -> None:
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        write_private_json(tmp, content)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def undo_moves(manifest: Path, home: Path, *, confirm: bool = True) -> tuple[int, int]:
    # Disallow arbitrary input paths as manifests; no escaping the designated state directory.
    manifest = Path(os.path.abspath(manifest.expanduser()))
    root = state_root(home)
    if not within(manifest, root) or not path_is_free_of_symlinks(manifest) or not re.fullmatch(r"moves-\d{8}T\d{12}Z\.json", manifest.name):
        raise ValueError("Use a HomeTree manifest under ~/.local/state/hometree")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data.get("moves"), list):
        raise ValueError("Invalid manifest")
    outstanding = [m for m in data["moves"] if m.get("status") in ("moved", "pending") and not m.get("undone")]
    print(f"Rollback preview: {len(outstanding)} move(s) from {manifest.name}")
    if not outstanding:
        return 0, 0
    if os.geteuid() == 0:
        raise ValueError("Refusing to undo as root")
    if confirm:
        response = input(f"Type UNDO {len(outstanding)} to restore unchanged moved files: ").strip()
        if response != f"UNDO {len(outstanding)}":
            print("Cancelled")
            return 0, len(outstanding)
    done = 0
    skipped = 0
    for record in reversed(outstanding):
        m = Move(**{k: record[k] for k in Move.__dataclass_fields__})
        src, dest = Path(m.source), Path(m.target)
        try:
            ensure_user_location(src.parent, home, must_exist=False)
            ensure_user_location(dest.parent, home)
            if os.path.lexists(src) or not check_fingerprint(dest, m):
                raise ValueError("Original occupied or moved file has changed")
            src.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            atomic_rename_no_replace(dest, src)
            record["undone"] = True
            done += 1
            replace_json(manifest, data)
        except (OSError, ValueError) as exc:
            skipped += 1
            print(f"SKIPPED rollback of {dest}: {exc}", file=sys.stderr)
    print(f"Restored: {done}; skipped: {skipped}")
    return done, skipped


def review_directories(home: Path, *, max_items: int = 100) -> None:
    """Read-only hints; do not guess which app/repository folders may be moved."""
    interesting = []
    with os.scandir(home) as scan:
        for ent in scan:
            if ent.name.startswith(".") or ent.name in PROTECTED_TOP or not ent.is_dir(follow_symlinks=False):
                continue
            p = Path(ent.path)
            hints = []
            if (p / ".git").exists():
                hints.append("Git checkout")
            if (p / "node_modules").exists() or (p / "package.json").exists():
                hints.append("Node/project dependencies")
            if (p / "venv").exists() or (p / ".venv").exists():
                hints.append("Python environment")
            if (p / "Cargo.toml").exists():
                hints.append("Rust project")
            if not hints and (p / "README.md").exists():
                hints.append("Source/tool candidate")
            interesting.append((ent.name, ", ".join(hints) if hints else "Review purpose and dependencies"))
    print("\nHome-root directories for MANUAL review (nothing will be moved):")
    for name, hint in sorted(interesting)[:max_items]:
        print(f"  {name}/  —  {hint}")
    if len(interesting) > max_items:
        print(f"  … {len(interesting)-max_items} more (increase --max-items)")
    print(f"Candidates listed: {len(interesting)}. Git/venv/service migrations require separate manual planning.")


@dataclass(frozen=True)
class CacheFile:
    path: Path
    category: str
    size: int
    inode: int
    device: int
    mtime_ns: int


def cache_roots(home: Path) -> dict[str, Path | None]:
    configured = os.environ.get("XDG_CACHE_HOME")
    base = Path(os.path.abspath(Path(configured).expanduser())) if configured else home / ".cache"
    result = {}
    for category in ALLOWED_CACHE:
        p = base / category
        result[category] = p if within(p, home) and p.is_dir() and path_is_free_of_symlinks(p) else None
    return result


def cache_candidates(home: Path, age: int) -> list[CacheFile]:
    threshold = time.time() - age * 86400
    result = []
    for category, root in cache_roots(home).items():
        if root is None:
            continue
        for base, dirs, files in os.walk(root, followlinks=False):
            # pip selfcheck is metadata, not a download/wheel cache.
            if category == "pip":
                dirs[:] = [d for d in dirs if d != "selfcheck" and not (Path(base)/d).is_symlink()]
            else:
                dirs[:] = [d for d in dirs if not (Path(base)/d).is_symlink()]
            for name in files:
                p = Path(base)/name
                try:
                    s = p.lstat()
                    if stat.S_ISREG(s.st_mode) and s.st_mtime < threshold and s.st_uid == os.getuid():
                        result.append(CacheFile(p, category, s.st_size, s.st_ino, s.st_dev, s.st_mtime_ns))
                except OSError:
                    pass
    return result


def cache_action(home: Path, *, clean: bool, age: int, confirm: bool = True, verbose: bool = False) -> tuple[int, int]:
    if age < 1:
        raise ValueError("Age must be at least 1 day")
    if clean and os.geteuid() == 0:
        raise ValueError("Refusing cache cleanup as root")
    selected = cache_candidates(home, age)
    print(f"Cache preview (regular files older than {age} days):")
    for cat in ALLOWED_CACHE:
        matches = [c for c in selected if c.category == cat]
        print(f"  {cat:12} {len(matches):>6} files   {pretty_size(sum(c.size for c in matches))}")
    print(f"Total: {len(selected)} files / {pretty_size(sum(c.size for c in selected))}")
    if verbose:
        for f in selected:
            print(f"  {f.path}")
    if not clean:
        print("Preview only. Cache cleaning requires `hometree cache clean` and typed confirmation.")
        return 0, 0
    if not selected:
        return 0, 0
    if confirm:
        response = input(f"Type CLEAN {len(selected)} to delete ONLY these old thumbnail/pip cache files: ").strip()
        if response != f"CLEAN {len(selected)}":
            print("Cancelled")
            return 0, len(selected)
    roots = cache_roots(home)
    threshold = time.time() - age * 86400
    done = skip = bytes_removed = 0
    for c in selected:
        root = roots[c.category]
        if root is None or not within(c.path, root) or not path_is_free_of_symlinks(c.path.parent):
            skip += 1
            continue
        try:
            s = c.path.lstat()
            if (not stat.S_ISREG(s.st_mode) or s.st_ino != c.inode or s.st_dev != c.device or
                s.st_size != c.size or s.st_mtime_ns != c.mtime_ns or s.st_mtime >= threshold):
                skip += 1
                continue
            c.path.unlink()
            done += 1
            bytes_removed += c.size
        except OSError:
            skip += 1
    print(f"Removed {done} cache files / {pretty_size(bytes_removed)} logical size; skipped {skip}.")
    print("Real disk recovery may differ; no other caches or project folders were cleaned.")
    return done, skip


def menu(home: Path) -> None:
    while True:
        banner()
        print("\n" + color("  1  [DIR]", "1;36") + "  Show my home folders")
        print(color("  2  [SORT]", "1;36") + " Preview Downloads organization")
        print(color("  3  [PROJ]", "1;36") + " Find unorganized projects")
        print(color("  4  [SCAN]", "1;36") + " Show old cache files")
        print(color("  5  [CLEAN]", "1;33") + " Clean approved cache files")
        print(color("  6  [SAFE]", "1;36") + " Check project move risks")
        print(color("  7  [?]", "1;36") + "    Help and commands")
        print("  8  [X]    Exit")
        footer()
        try:
            answer = input("\nChoose [1-8]: ").strip()
            if answer == "1":
                d, f, truncated = tree_display(home, sys.stdout, depth=2, dirs_only=True, hidden=False, max_entries=350)
                print(f"{d} directories; {f} files/links" + (" (limited)" if truncated else ""))
            elif answer == "2":
                moves, skips = plan_organization(home / "Downloads", home)
                print_plan(moves, skips, home=home)
                print("To apply intentionally: hometree organize ~/Downloads --apply")
            elif answer == "3":
                review_directories(home)
            elif answer == "4":
                cache_action(home, clean=False, age=30)
            elif answer == "5":
                cache_action(home, clean=True, age=30)
            elif answer == "6":
                dependency_review(home)
            elif answer == "7":
                print("Use `hometree --help` or `hometree <command> --help`.")
            elif answer == "8":
                break
            else:
                print("Choose a number from 1 to 8.")
            input("\nPress Enter to return to the menu…")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye")
            return
        except (OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hometree", description="Styled tree viewer, preview-first file organization, and cautious cache manager")
    p.add_argument("--version", action="version", version=f"HomeTree {VERSION}")
    cmd = p.add_subparsers(dest="command")
    tree = cmd.add_parser("tree", help="Compact, bounded directory tree")
    tree.add_argument("path", nargs="?", type=Path, default=Path.home())
    tree.add_argument("--depth", type=int, default=2)
    tree.add_argument("--dirs-only", action="store_true")
    tree.add_argument("--hidden", action="store_true", help="Include hidden files (may expose sensitive names)")
    tree.add_argument("--max-entries", type=int, default=MAX_SCAN_ENTRIES)
    tree.add_argument("--output", type=Path, help="Write tree to a new file; never overwrite")

    org = cmd.add_parser("organize", help="Preview simple file moves; never move directories")
    org.add_argument("path", nargs="?", type=Path, default=Path.home() / "Downloads")
    org.add_argument("--apply", action="store_true", help="Request typed confirmation and apply eligible moves")
    org.add_argument("--include-archives", action="store_true", help="Include non-executable compressed archives")
    org.add_argument("--show-skipped", action="store_true")

    deps = cmd.add_parser("dependencies", help="Read-only project dependency warnings (no automatic moves)")
    deps.add_argument("--max-items", type=int, default=120)

    review = cmd.add_parser("review-projects", help="Read-only list of top-level directories requiring manual classification")
    review.add_argument("--max-items", type=int, default=100)

    undo = cmd.add_parser("undo", help="Restore unchanged files using a HomeTree manifest")
    undo.add_argument("manifest", type=Path)

    cache = cmd.add_parser("cache", help="Preview or clean old pip and thumbnail caches")
    cache.add_argument("action", choices=("report", "clean"))
    cache.add_argument("--age", type=int, default=30)
    cache.add_argument("--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    home = home_path()
    try:
        if args.command is None:
            if sys.stdin.isatty():
                menu(home)
            else:
                parser().print_help()
            return 0
        if args.command == "tree":
            root = Path(os.path.abspath(args.path.expanduser()))
            if not root.is_dir():
                raise ValueError("Directory does not exist")
            if args.output:
                outfile = Path(os.path.abspath(args.output.expanduser()))
                if not outfile.parent.is_dir():
                    raise ValueError("Output parent directory does not exist")
                fd = os.open(outfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as out:
                    dirs, files, truncated = tree_display(root, out, depth=args.depth, dirs_only=args.dirs_only,
                                                         hidden=args.hidden, max_entries=args.max_entries)
                print(f"Saved: {outfile}")
                print("Private file: tree exports may reveal personal filenames or directory names. Do not publish without review.")
            else:
                dirs, files, truncated = tree_display(root, sys.stdout, depth=args.depth, dirs_only=args.dirs_only,
                                                     hidden=args.hidden, max_entries=args.max_entries)
            print(f"{dirs} directories, {files} files/links" + (" (output capped)" if truncated else ""))
        elif args.command == "organize":
            folder = ensure_user_location(args.path, home)
            moves, skipped = plan_organization(folder, home, archives=args.include_archives)
            print_plan(moves, skipped, home=home, show_skipped=args.show_skipped)
            if args.apply:
                execute_moves(moves, home)
            else:
                print("Dry-run complete. No files moved. Add --apply to request confirmation.")
        elif args.command == "dependencies":
            dependency_review(home, max_items=args.max_items)
        elif args.command == "review-projects":
            review_directories(home, max_items=args.max_items)
        elif args.command == "undo":
            undo_moves(args.manifest, home)
        elif args.command == "cache":
            cache_action(home, clean=args.action == "clean", age=args.age, verbose=args.verbose)
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"HomeTree error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
