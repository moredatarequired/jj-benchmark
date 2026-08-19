# Jujutsu (jj) 0.44.0 — Working Reference

Jujutsu is a Git-compatible VCS with a different working model. In a jj repo, reach for `jj`, not `git`: jj stores its own operation history and bookmark state, and mixing in mutating Git commands raises the odds of misplaced bookmarks and divergent change IDs. Read-only `git` commands are fine.

## The core model

Three ideas explain most of the differences from Git.

**1. The working copy is a commit.** There is no index/staging area and no "dirty tree". The commit `@` *is* your working copy. Nearly every `jj` command starts by snapshotting the working directory into `@` automatically, so edits are committed continuously. New files are tracked automatically (subject to `.gitignore` and `snapshot.auto-track`), so there is no `git add`.

**2. Changes have stable IDs.** Every commit carries a *change ID* (rendered as letters in the k–z range, shown first in `jj log`) alongside the usual *commit ID* (a Git hash). Rewriting a commit — amending, rebasing, reordering — preserves the change ID and mints a new commit ID. Refer to work by change ID and it keeps resolving to the current version. Either ID can be abbreviated to a unique prefix.

**3. Rewriting is safe and automatic.** Rewriting a commit automatically rebases its descendants. Every operation is recorded in the operation log and can be undone.

```bash
jj st                 # status: @, its parents, changed files, conflicts
jj log                # graph; @ marks the working copy, ◆ immutable commits
jj log -r ::          # all visible revisions
jj show @-            # metadata + diff of the parent
jj diff --git         # diff of @ against its parent
```

`jj log` with no arguments shows a curated set (`revsets.log`, default `builtin_log()`), not all history.

## The everyday loop

Describe what you are doing, then start the next change. Two equivalent styles:

```bash
jj describe -m "add config loader"   # set the message of @ (alias: jj desc)
jj new                               # start a fresh empty child of @

jj commit -m "add config loader"     # describe @ and jj new, in one step
```

`jj describe` opens `$EDITOR` unless `-m`/`--stdin` is given; add `--editor` to edit a `-m` message before saving. It has no `--no-edit`; that was removed in 0.42.

Start work somewhere else:

```bash
jj new main                # new change on top of the main bookmark
jj new abcxyz             # on top of a change ID
jj new @ feature          # a merge commit with two parents
jj new -A abcxyz          # insert a change after abcxyz, rebasing its children
jj edit abcxyz            # make an existing commit the working copy
```

`jj edit` puts you *inside* an existing commit, so every save amends it. Prefer `jj new` + `jj squash` when you want a reviewable step.

## Revsets

Nearly every `-r` argument takes a revset expression. Essentials:

| Syntax | Meaning |
|---|---|
| `@` | working-copy commit (`name@` for another workspace) |
| `x-` / `x+` | parents / children |
| `::x` / `x::` | ancestors / descendants, inclusive |
| `x::y` | descendants of `x` that are ancestors of `y` |
| `x..y` | ancestors of `y` that are not ancestors of `x` (as in Git) |
| `x \| y`, `x & y`, `x ~ y` | union, intersection, difference; `~x` is negation |

Useful functions: `trunk()`, `bookmarks()`, `remote_bookmarks([name],[remote=])`, `tags()`, `heads(x)`, `roots(x)`, `description(pat)`, `author(pat)`, `mine()`, `empty()`, `conflicts()`, `files(fileset)`, `merges()`, `latest(x, n)`, `mutable()` / `immutable()`, `at_operation(op, x)`.

String-pattern arguments default to `glob:`; other kinds are `exact:`, `substring:`, `regex:`, each with an `-i` case-insensitive variant.

```bash
jj log -r 'trunk()..@'                     # your unmerged work
jj log -r 'remote_bookmarks()..'           # everything not yet on a remote
jj log -r 'mine() & description(substring:"cache")'
jj log -r '(trunk()..@)::'
```

Symbols resolve as tag, then bookmark, then commit/change ID; use `commit_id(abc)` or `change_id(abc)` in scripts to force the interpretation. Quote a symbol (`'"x-"'`) to stop it being parsed as an operator.

## Filesets and file commands

Positional path arguments are *filesets*. A bare `"path"` is a cwd-relative prefix glob; other kinds include `file:`, `glob:`, `root:` (workspace-relative), and `root-glob:`. Operators `~ & |` work as in revsets.

```bash
jj diff 'dsp ~ glob:"**/*.test.ts"'
jj file list -r @-              # files in a revision
jj file show -r abcxyz dsp/fft.py
jj file annotate dsp/fft.py     # git blame
jj file search -p 'TODO'        # 0.44: prints matching lines; --name-only for paths
jj file track path/to/file      # only needed if snapshot.auto-track is narrowed
jj file untrack path            # path must already be ignored
```

## Rewriting history

Most of these take a revision (`-r`), not just `@`, and descendants are rebased for you. `jj restore` and `jj absorb` are the exceptions: they use `--from`/`--into` instead.

```bash
jj squash                       # move @'s changes into its parent (amend)
jj squash -i                    # choose hunks interactively
jj squash dsp/fft.py            # move only these paths
jj squash -r abcxyz             # squash that change into its parent
jj squash --from abcxyz --into qrstuv
jj squash --into @--            # amend the grandparent
```

`--from`/`-f` and `--into`/`-t` default to `@`. If the source ends up empty it is abandoned unless you pass `-k`/`--keep-emptied`. Use `-u`/`--use-destination-message` to keep the destination's description.

```bash
jj split                        # interactively split @ into two commits
jj split -r abcxyz dsp/mix.py   # put these paths in the first commit
jj split -p                     # make the two parts siblings, not parent/child
jj absorb                       # distribute @'s hunks into the mutable ancestors
                                # that last touched those lines
jj abandon abcxyz               # drop a change, rebasing its descendants
jj restore dsp/fft.py           # discard working-copy edits to these paths
jj restore --from abcxyz --into qrstuv
jj duplicate abcxyz -o main     # like cherry-pick, keeps the original
jj revert -r abcxyz -o @        # apply the inverse of a commit
jj metaedit -r abcxyz --update-author
```

### Rebasing

In 0.44 the destination flag is `-o`/`--onto`, and a destination (`-o`, `-A`/`--insert-after`, or `-B`/`--insert-before`) is **required**. `-d`/`--destination` still works as a deprecated alias — prefer `-o`.

```bash
jj rebase -s abcxyz -o main     # move a commit and its descendants
jj rebase -b @ -o main          # move the whole branch containing @ (default -b @)
jj rebase -r abcxyz -o main     # move just this commit; its children keep their parent
jj rebase -r abcxyz -A qrstuv   # insert between qrstuv and its children
```

Add `--skip-emptied` to drop commits that become empty.

### Immutable commits

`jj` refuses to rewrite commits in `immutable()` — by default ancestors of `trunk() | tags() | untracked_remote_bookmarks()`. If you truly need to, pass the global `--ignore-immutable`, or redefine `revset-aliases."immutable_heads()"`.

## Conflicts

Conflicts are recorded *in commits*, so a rebase or merge never stops halfway and there is no `--continue`. A conflicted commit is a normal commit that happens to contain conflicted files; you resolve it whenever you like, and descendants get re-rebased automatically.

Conflicts are materialized in the working copy with markers. jj's default style shows one snapshot plus a diff to apply to it:

```text
<<<<<<< conflict 1 of 1
%%%%%%% diff from: <base>
\\\\\\\        to: <side 1>
 alpha
-beta
+beta-two
 gamma
+++++++ <side 2>
ALPHA
BETA
GAMMA
>>>>>>> conflict 1 of 1 ends
```

Set `ui.conflict-marker-style = "git"` (diff3-style) or `"snapshot"` if a tool needs it. Resolve by editing the file and deleting the markers, or:

```bash
jj resolve --list               # which files conflict
jj resolve                      # run the configured 3-way merge tool
jj resolve --tool :ours         # or :theirs
jj new abcxyz                   # resolve on top, then...
jj squash                       # ...fold the resolution into the conflicted commit
```

## The operation log and undo

Every command that touches the repo creates an operation.

```bash
jj op log                       # history of operations
jj undo                         # undo the last operation (repeat to go further back)
jj redo                         # counterpart of undo
jj op restore <op-id>           # reset the repo to the state at that operation
jj op revert <op-id>            # invert one specific operation
jj --at-op=<op-id> log          # inspect the repo as it was, without changing it
```

`jj undo` reverses repo state, not the filesystem contents of untracked files. Note that `jj op restore`/`revert` also restore remote-tracking state by default; use the experimental `--what repo` if you intend to push afterwards.

## Bookmarks (jj's branches)

Bookmarks are named pointers, but **there is no checked-out bookmark and bookmarks do not advance when you commit**. This is the single biggest surprise for Git users. They *do* follow commits that get rewritten, and they are deleted if their commit is abandoned (`jj abandon --retain-bookmarks` moves them to the parent instead).

```bash
jj bookmark list                # alias: jj b l; --all-remotes, --tracked, --conflicted
jj bookmark create feature -r @
jj bookmark set feature -r @    # create or move; -B to move backwards/sideways
jj bookmark move feature --to @
jj bookmark advance             # move the closest bookmark to @
jj bookmark rename old new
jj bookmark delete feature      # deletion propagates to remotes on next push
jj bookmark forget feature      # local-only: forget without pushing a deletion
jj bookmark track feature@origin
```

Remote positions are `name@remote` (`main@origin`); `name@git` is the local Git-tracking ref (a pseudo-remote called `git`), excluded from `remote_bookmarks()` unless you ask for `remote="git"`. A local bookmark with a different target on a remote shows as `main*`; a bookmark whose local and remote sides diverged is *conflicted* and shows as `main??` — fix it with `jj bookmark set`/`move` to the target you want.

## Git interop

Repos created by `jj git init` and `jj git clone` are **colocated by default** in 0.44: `.jj` and `.git` sit side by side and import/export happen automatically on every command. Pass `--no-colocate` (or set `git.colocate = false`) to hide the Git repo inside `.jj`.

```bash
jj git clone https://example.com/org/repo.git
jj git init                     # in an existing directory
jj git init --git-repo=../repo  # back onto an existing Git repo
jj git colocation status|enable|disable
```

`jj git import` / `jj git export` exist for non-colocated repos. In 0.44 they are disabled in colocated workspaces (they were no-ops with a race); force one with `--ignore-working-copy` if ever needed.

```bash
jj git fetch                    # --remote NAME; fetches bookmarks and tags
jj git push                     # tracking bookmarks/tags in remote_bookmarks(remote=..)..@
jj git push -b feature          # push one bookmark (auto-tracks it if new)
jj git push -c @                # create+push a bookmark named push-<change id>
jj git push --named fix=@-      # push a revision under a new bookmark name
jj git push --dry-run
```

There is no `--allow-new` (removed in 0.42): push a specific bookmark with `-b`, or configure `remotes.origin.auto-track-bookmarks = "glob:*"`. Pushes are safe like `--force-with-lease`; if the remote moved, `jj git fetch` and resolve the bookmark conflict. Commits with empty descriptions or conflicts are rejected unless you pass `--allow-empty-description` / `--allow-conflicts`.

Unsupported Git features include hooks, submodules, `.gitattributes`, sparse checkouts, LFS, and the index (jj ignores the staging area entirely).

## Workspaces

Multiple working copies over one repo — useful for running a long build while you keep editing.

```bash
jj workspace add ../repo-test
jj workspace list
jj workspace forget <name>
jj workspace update-stale        # after another workspace rewrote this one's @
```

Each workspace has its own `@`, shown as `<name>@` in `jj log`.

## Config, aliases, templates

```bash
jj config set --user user.name "Ada Lovelace"
jj config set --user user.email "you@example.com"
jj config edit --repo            # or --user / --workspace
jj config list
```

```toml
[aliases]
l = ["log", "-r", "trunk()..@"]

[revset-aliases]
"immutable_heads()" = "builtin_immutable_heads() | release@origin"

[fileset-aliases]
LOCK = '**/package-lock.json | **/uv.lock'
```

`-T`/`--template` renders output with jj's template language (`jj log -T` lists the built-ins); defaults come from `templates.log`, `templates.bookmark_list`, and friends.

## Git habits that misfire

- `git add` → nothing; files are snapshotted automatically.
- `git commit --amend` → `jj squash` (`-i` for hunks).
- `git stash` → `jj new @-`; the old commit stays as a sibling, resume with `jj edit`.
- `git checkout -b topic main` → `jj new main` (name it later with `jj bookmark create`).
- `git reset --hard` → `jj abandon` (start over) or `jj restore` (empty the change).
- `git reset --soft HEAD~` → `jj squash --from @-`.
- `git rebase --continue` → nothing; resolve the conflict and `jj squash`.
- `git blame` → `jj file annotate`.
- Anything gone wrong → `jj undo`.

## 0.44.0 specifics worth knowing

- Tag fetch/push is stabilized: tags fetch as `name@remote`, are tracked like bookmarks, and tracked tags push by default. `jj git push --all` now pushes tags too. `jj tag track`/`untrack` are new. Git's `tagOpt` is ignored; disable with `remotes.<name>.fetch-tags = '~*'`.
- `jj git clone --fetch-tags=...` was removed in favour of `--tag=PATTERN`.
- `jj file search` prints matching lines (use `--name-only` for the old path-only output) and gained `-n`/`--line-number`.
- `jj absorb` gained `-i`/`--interactive` and `--tool`.
- Repeating an argument is no longer an error; the last occurrence wins (`jj log -n 5 -n 10`), except for genuinely repeatable options like `--config` and `-r`.
- New `merge_point()` revset function and `builtin_log()` revset alias.
