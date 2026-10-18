# HomeTree

**Lightweight filesystem explorer, preview-first organizer, and cautious cache manager for Linux.**

`SPES_MEA_IN_DEO_EST#32` · `#DEV32#`

HomeTree is a small, local-only Python CLI inspired by the compact cyan/green terminal presentation of WiFi Password Studio. It is **not** a replacement for the excellent `tree`, `eza`, or `broot` tools. Its focus is helping users understand their home folder, preview conservative file organization, and clean a narrowly defined set of regenerable caches.

> **Local beta (v0.2.1)** — Test on a disposable directory before organizing real downloads. Nothing is published or transmitted automatically. Directory migrations for Git repositories and running applications are **not supported**.

## What you get

- **Compact tree** — bounded output with configurable depth, maximum entries, hidden-file visibility, and directory-only mode.
- **Styled terminal menu** — cyan/green developer signature and numbered actions when launched interactively.
- **Smart file organization** — preview individual ordinary files to be placed in `Documents/Imported`, `Pictures/Imported`, `Videos/Imported`, `Music/Imported`, or (only if opted in) `Archives/Compressed`.
- **Safer execution** — explicitly opt in with `--apply`, then type an exact confirmation. No overwriting, no symbolic link traversal, no cross-filesystem copying, and no `sudo`.
- **Rollback manifest** — private per-run move records saved under `~/.local/state/hometree/`; undo checks that the target file is unchanged and the original path is free.
- **Project-folder review** — lists ungrouped top-level directories and hints about Git, Node, Rust, or Python dependencies **without moving them**.
- **Cache preview/cleanup** — considers only old, regular files in your user's **pip download cache** and **thumbnail cache**; skips pip self-check metadata and follows no symlink directories.

HomeTree uses only the **Python standard library** and Linux's `renameat2(RENAME_NOREPLACE)` mechanism for safe, no-replace moves.

## Requirements

- Linux, preferably Kali, Debian, or another modern distribution providing `renameat2`
- Python **3.10+**
- User-level access to the directories you want to inspect
- No packages, accounts, network connections, or subscriptions

## Installation on Kali Linux

**Recommended source location:** `~/Tools/Utilities/HomeTree/` (source) with a small command installed to `~/.local/bin/hometree`.

1. Extract the downloaded project ZIP somewhere in your home directory.
2. Place the `HomeTree` project folder into `~/Tools/Utilities/`.
3. Install the command:

```bash
mkdir -p "$HOME/.local/bin"
install -m 755 "$HOME/Tools/Utilities/HomeTree/hometree.py" "$HOME/.local/bin/hometree"
```

Check the command:

```bash
command -v hometree
hometree --version
hometree --help
```

If your terminal says `command not found`, temporarily use:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

For persistent Zsh setup, add this line to `~/.zshrc` **only if your PATH doesn't already include it**:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

You can alternatively run the script directly without installing it:

```bash
python3 "$HOME/Tools/Utilities/HomeTree/hometree.py" --help
```

## Terminal interface

Launching `hometree` interactively shows a menu based on WiFi Password Studio's compact style:

```text
─────────────────────────────────────────────────────────
  SPES_MEA_IN_DEO_EST#32
  #DEV32#
─────────────────────────────────────────────────────────
  HomeTree  ·  File Explorer & Safe Organizer

  1  Browse compact home tree
  2  Analyze & preview Downloads organization
  3  Review ungrouped home-root projects
  4  Preview old pip/thumbnail caches
  5  Clean approved old caches
  6  Command help
  7  Exit

  DEV32 · Local-first · No telemetry
```

Use subcommands for scripting and direct terminal access.

## Commands and examples

### Compact trees

```bash
hometree tree ~ --depth 2 --dirs-only
hometree tree ~/Cybersecurity --depth 3
hometree tree / --depth 2 --dirs-only
hometree tree ~ --depth 4 --max-entries 2000
```

The default limit is **1,500 printed entries** and a depth of **2**. This avoids accidentally producing enormous terminal output. Hidden files are excluded unless you explicitly request them.

To write a private export:

```bash
hometree tree ~ --depth 3 --dirs-only --output ~/home-structure.txt
```

The output is created with permission `0600` and refuses to overwrite an existing file. **Tree exports can include personal or sensitive file names; never upload them to a public repository without inspection.**

### Preview file organization

```bash
hometree organize ~/Downloads
hometree organize ~/Downloads --show-skipped
hometree organize ~/Downloads --include-archives
```

These commands are **read-only**. HomeTree scans **only immediate ordinary files** inside the chosen directory. It never walks into or moves its subdirectories. It skips hidden files, symlinks, unknown formats, scripts, sensitive-looking filenames, VM images and installer/boot images.

A typical preview might show:

```text
Organization preview — NO CHANGES
  holiday.jpg → ~/Pictures/Imported/holiday.jpg
  resume.pdf  → ~/Documents/Imported/resume.pdf

Eligible: 2 files; skipped: 31
Dry-run complete. No files moved.
```

To **request** a move, add `--apply`:

```bash
hometree organize ~/Downloads --apply
```

You must type `MOVE N` (where `N` is the number shown). The destination must not exist. Moves only work within the same filesystem. HomeTree records the proposed set before performing the first move and updates its private audit log after each move.

**Important:** A file can still be referenced by an external application even if its extension looks harmless. Review the move preview and do not approve active or path-dependent resources. Never treat file classification as a full dependency audit.

### Home-root project review

```bash
hometree review-projects
hometree review-projects --max-items 200
```

This is **read-only**. It points out top-level directories that deserve manual review; it does **not** relocate repositories, Python virtual environments, system-managed paths, desktop configuration, or live services.

### Undo an organization run

```bash
ls -1 ~/.local/state/hometree/moves-*.json
hometree undo ~/.local/state/hometree/moves-YYYYMMDDTHHMMSSffffffZ.json
```

Undo requires `UNDO N`. It restores only files whose inode, device, size, and modification timestamp match the move record. It never overwrites a path that is already occupied. If a moved file has been edited, HomeTree skips it and asks for manual attention. Empty destination folders may remain after undo.

The manifest contains absolute local paths. Do not add it to GitHub.

### Cache review and cleanup

```bash
hometree cache report --age 30
hometree cache report --age 60 --verbose
hometree cache clean --age 30
```

Cleanup is limited to user-owned regular files older than the age threshold under:

- `${XDG_CACHE_HOME:-~/.cache}/pip` (excluding `selfcheck` metadata)
- `${XDG_CACHE_HOME:-~/.cache}/thumbnails`

No browser profiles, package installations, active pnpm stores, virtual environments, project dependencies, or Git repositories are cleaned. Avoid cache cleanup while `pip` is running. You must type `CLEAN N` to confirm. Removed caches may be downloaded or regenerated later, and reported sizes are logical totals rather than guaranteed freed filesystem blocks.

## Safety model and limitations

See [docs/SAFETY.md](docs/SAFETY.md) for the exact scope.

HomeTree is intentionally **not** a full automatic desktop optimizer. It doesn't uninstall software, inspect file contents for classification, move entire repos, touch protected projects, or delete ordinary personal files. The built-in organizer handles simple single-file moves only. Any repository/service migration requires an independent dependency audit and separate tools.

This tool makes no promise to detect every hidden dependency. It assumes your home directory is not being modified by an adversary during cleanup. It isn't a security sandbox. Take a backup before reorganizing important files.

## Development and tests

```bash
cd ~/Tools/Utilities/HomeTree
python3 -m unittest discover -s tests -v
python3 hometree.py --help
python3 hometree.py tree . --depth 2
```

All tests use temporary directories; they do not reorganize your real home folder.

## Roadmap

- Safer directory-level migration planning with dependency scanning and interactive reviews
- Expandable TUI tree with search and filtering
- Optional duplicate hash analysis with no implicit deletion
- Per-category custom organization rules
- More detailed human-readable preflight reports

## Security & privacy

- No telemetry or internet calls
- No access keys required
- No source code or private filesystem inventories in the public repository
- Move logs stored as user-private local files
- Never run `hometree organize --apply` or `hometree cache clean` as root

**Please do not commit your `tree.txt`, exported filesystem inventory, SSH keys, recovery codes, VPN profiles, or application configuration.**

## License

MIT — see [LICENSE](LICENSE).

**DEV32** · `dev32@apex32-secure.com`

## v0.2 dependency-aware local beta

**Not published. Test locally before enabling write operations.**

HomeTree now includes a read-only dependency overview:

```bash
python3 hometree.py dependencies
python3 hometree.py review-projects
python3 hometree.py tree ~ --depth 2 --dirs-only --max-entries 200
python3 hometree.py organize ~/Downloads  # preview only
```

The organizer refuses to operate inside known active-project folders,
application-managed directories, or an ancestor containing `.git`, `.venv`,
`venv`, `node_modules`, `package.json`, `pyproject.toml`, `Cargo.toml`,
`go.mod`, or `CMakeLists.txt`. These checks are deliberately conservative,
**not a complete runtime dependency audit**. It does not rewrite systemd
services, Waybar paths, environments, deployment files, or build artifacts.

Do not publish filesystem inventory exports. They can disclose usernames,
project names, secret-related filenames, and local directory structure.

For a first real workstation test, only run read-only commands. All automated
write-operation tests run within temporary test directories.


### Developer contact

**DEV32** · Feedback, bug reports, and support: **dev32@apex32-secure.com**.
