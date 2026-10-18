# HomeTree safety boundaries

HomeTree is intended for simple, transparent, local file-management assistance, not unattended system maintenance.

## Non-negotiable exclusions

- No project directory or application directory relocation. `review-projects` merely lists them.
- No symlink traversal when scanning or cleaning caches. `tree` reports links as link entries and does not recurse into them.
- No root or cross-filesystem moves. Only regular user-owned files are eligible.
- No overwrite of an existing destination. Linux `renameat2(RENAME_NOREPLACE)` fails if occupied.
- No implicit recursive deletion. Only selected regular files in a tiny cache allowlist can be removed after confirmation.
- No access to the network, package managers, Git remotes, or other accounts.
- No direct manipulation of repositories, virtual environments, installed packages, VM disks, or live services.

## What the organizer does

1. Inspect immediate ordinary files in a directory within your home.
2. Use a conservative extension mapping to propose their target XDG-style category.
3. Exclude names that look like evidence, screenshots, credentials, backup/recovery material or active state.
4. Display the proposed source and destination paths.
5. Require `--apply` and typed `MOVE N` confirmation.
6. Recheck file identity and target availability and use same-filesystem no-replace rename.
7. Keep private log records under `~/.local/state/hometree` for potential rollback.

### Limitations

Filename heuristics cannot determine whether a file is actively referenced by software. HomeTree deliberately does not change desktop shortcuts, systemd units, shell aliases, projects, venvs, or package config. Even a PDF may be referenced by absolute path; do not approve a move unless you know it is safe.

Moves are crash-resistant to the extent that the initial plan is journaled, but an interrupted run may require manual inspection and repair. Undo refuses to overwrite a modified or newly occupied source path. Manifest and state directories must be protected from untrusted writers. File metadata comparisons are not cryptographic integrity checks. Directory symlink checks minimize accidental traversal but are not a hardened defense against hostile concurrent processes or mutation of path components.

## Cache cleaning scope

The cleaner only considers regular user-owned files older than the requested age in `~/.cache/pip` and `~/.cache/thumbnails` (with XDG cache support). `pip/selfcheck` is excluded. Other caches are neither detected nor deleted. The exact age of a file and its cache origin do not guarantee it is safe to remove while an app is using it; review and close relevant applications first.

## Privacy

The repository contains no system inventory. **Your filenames and cached data stay local.** A tree saved to disk can nonetheless reveal file paths and sensitive names. Audit it carefully before sharing, and never add local move manifests to a public repository.
