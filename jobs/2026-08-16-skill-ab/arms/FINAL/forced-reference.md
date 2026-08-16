# Jujutsu (jj) 0.44 operational reference

Everything below is jj 0.44 behaviour. Examples use a mapmaking repository
(`coastline.geojson`, `atlas/plate-07.svg`, bookmarks `trunk`/`winter-tiles`, remote
`upstream`) and placeholder revisions `P`, `Q`, `R`.

## The model

- Every commit has a **change ID** (12 letters in the k–z range, stable across rewrites)
  and a **commit ID** (hex, new on every rewrite). Rewriting a commit — redescribing,
  rebasing, changing its content — yields a new commit ID under the same change ID.
- `@` is the working-copy commit **of the current workspace**; it is a real commit, not a
  staging area. `@-` is its parent, `@--` its grandparent, `<workspace>@` another
  workspace's working-copy commit.
- **Almost every jj command first snapshots the working copy** into `@` as a new operation.
  There is no add/stage step: edit a file, run any jj command, and the edit is already in `@`.
- **New files are tracked automatically** (`snapshot.auto-track` defaults to `all()`) and
  deleting a file untracks it. `.gitignore`d files are never auto-tracked, but
  `jj file track --include-ignored <paths>` tracks them anyway; `jj file untrack <paths>`
  accepts only paths that are already ignored.
- Descendants of a rewritten commit are **rebased automatically** — no follow-up rebase
  after amending something mid-stack.
- `jj status` gives `A`/`M`/`D` per path for the working copy; `jj diff --summary` (`-s`)
  gives the same letters for any revision. A deletion shows as a `D` entry.
- **A mutation that matches nothing succeeds.** `jj abandon -r 'none()'`, `jj squash --from
  'none()'`, a `jj git push` with an empty bookmark selection (which adds a `Warning:` line),
  and a `jj describe -m` whose text is already in place all **exit 0**, printing only
  `Nothing changed.` or a command-specific variant of it — `No revisions to abandon.`,
  `No revisions to rebase.`, `No revisions to duplicate.`, `No bookmarks to update.`. A zero
  exit status therefore means the command was well-formed, not that the repository changed;
  only re-reading the state shows that. Unknown flags and unparsable revsets do exit non-zero.

## No terminal, no editor

There is no TTY. A command that opens a diff or description editor will fail or hang, so
always use the non-interactive form: `jj describe -m "…"` or `--stdin`;
`jj split <filesets> -m "…"`; `jj squash -u` or `-m "…"`; `jj resolve --tool :ours` /
`:theirs`, or edit the conflict markers directly. `jj diffedit`, `jj arrange` and
`jj absorb -i` have no non-interactive mode. `--editor` on `describe`/`commit`/`squash`/
`split` forces an editor open; never use it.

## Describing and creating commits

- `jj describe [-r <rev>] -m "…"` rewrites a description **in place**; `@` does not move.
  Default revision `@`; several revisions all get the same text.
- `jj commit -m "…"` is `describe` followed by `new`: it sets the description of `@` and
  then **advances `@`** onto a fresh empty child. Use `describe` to reword, `commit` to
  finish this change and start the next. `jj commit` never moves bookmarks forward;
  `jj split` (without `-o/-A/-B`) does.
- `jj new [<parents>…]` creates an empty change on the given parents (default `@`) and
  edits it. `jj new P Q` makes a **merge**. `--no-edit` leaves `@` alone.
  `-A/--insert-after` and `-B/--insert-before` splice it in and rebase affected children.
- `jj edit <rev>` moves `@` onto an existing commit so edits land there directly.

## Moving changes between commits

### `jj squash` — move changes from one revision into another

- Bare `jj squash` moves everything in `@` into `@-`, abandons the now-empty `@`, and
  leaves a fresh empty working-copy commit on top.
- `-r <rev>` squashes that one revision into **its parent**; it fails on a merge, and
  takes a single revision only.
- `--from <revs>` / `--into <rev>` (alias `--to`) work between arbitrary revisions; the
  one you omit defaults to `@`, as in `jj squash --from R --into P`.
- Trailing positional arguments are **filesets, not revisions**:
  `jj squash --from R --into P coastline.geojson` moves only that path.
- An emptied source is abandoned unless `-k/--keep-emptied`. If source and destination both
  have non-empty descriptions and the source is abandoned, jj prompts for a combined
  description — `-u` (`--use-destination-message`) or `-m "…"` avoids that prompt.

### `jj split` — split one revision in two

- `jj split <filesets> -m "…"` is the non-interactive form. The **listed paths go into the
  first (parent) commit** and everything else stays in a child on top. `-m` describes the
  commit holding the selected paths; the other keeps the original description.
- `-r <rev>` picks what to split (default `@`). `-p/--parallel` makes the halves siblings
  rather than parent and child. `-o/-A/-B` extract the selected changes elsewhere and leave
  the remainder in place. With no filesets and no `-o/-A/-B` it is interactive, and
  splitting an empty commit is rejected.

### `jj absorb` — push edits back into the commits that last modified those lines

- Each hunk of the source (`-f/--from`, default `@`) moves into the **closest mutable
  ancestor that last modified those lines**; hunks with no unambiguous destination stay in
  the source.
- `-t/--into <revs>` narrows the candidates (default `mutable()`), and only ancestors of
  the source are ever considered. Positional arguments are filesets. If every hunk is
  absorbed and the source has no description, the source is abandoned. Review the result
  with `jj op show -p`.

## Rebasing

`jj rebase` requires one of `-o/--onto` (aliases `-d`, `--destination`), `-A/--insert-after`, or
`-B/--insert-before`. Which revisions move is chosen by exactly one of:

- `-s/--source <revs>` — that revision **and all its descendants**; each `-s` argument
  becomes a direct child of the destination.
- `-b/--branch <revs>` — the whole branch; `jj rebase -b Q -o P` equals
  `jj rebase -s 'roots(P..Q)' -o P`.
- `-r/--revision <revs>` — **only** those revisions, with their descendants rebased onto
  the moved revisions' parents. `-r` may move a commit onto its own descendant.
- Default when none is given: `-b @`. `--skip-emptied` abandons commits the rebase would
  empty (ones already empty are kept). Also `--keep-divergent`, `--simplify-parents`.

## Undoing content, undoing commits

- `jj restore [<filesets>]` copies file **content** between revisions: `--from <src>`,
  `--into <dst>` (alias `--to`), each defaulting to `@`; with neither, it restores `@` from
  its parents. `jj restore --from P atlas/plate-07.svg` makes that path in `@` match `P`.
  `-c/--changes-in <rev>` undoes what `jj diff -r <rev>` shows, leaving the commit present
  with its description intact. `--restore-descendants` holds descendants' content fixed
  rather than replaying their diffs.
- `jj abandon [<revs>]` removes commits and rebases their descendants onto the parents.
  Bookmarks pointing at an abandoned commit are **deleted** unless `--retain-bookmarks`,
  which moves them to the parent instead. `--restore-descendants` keeps children's content
  unchanged. An abandoned `@` is replaced by a new empty commit. `jj revert -r <revs>
  (-o|-A|-B) <loc>` instead creates **new** commits applying the inverse; originals stay.
- `jj duplicate [<revs>]` copies commits, keeping content and description but issuing new
  change IDs. With none of `-o/--onto` (aliases `-d`, `--destination`), `-A/--insert-after`,
  `-B/--insert-before`, copies land on their existing parents; with one, the roots of the
  selected set land there and the rest stack on the copies. Several revisions keep their
  relative order; the positional revset argument also has the alias `-r`.

## The operation log

- Every command touching the repo records an operation — a second history, independent of
  the commit graph. `jj op log` lists them (`-n <N>` limits, `--no-graph` flattens, `-T`
  templates, `-p`/`--op-diff` shows what each changed); `@` is the current operation, `@-`
  its parent. `jj undo` reverses the last one and repeats further back; `jj redo` goes
  forward.
- `jj op restore <op-id>` creates a **new** operation restoring the whole repo to the state
  at `<op-id>`. `jj op revert <op>` inverts one operation without discarding later ones.
- In 0.44 the `jj op` subcommands are `abandon`, `diff`, `integrate`, `log`, `restore`,
  `revert`, `show`. There is **no `jj op undo`** — the spelling is the top-level `jj undo`.
- `--at-op=<op-id>` is a top-level flag on any command, loading the repo as it was at that
  operation; under it the working copy is **not** snapshotted.

## Bookmarks and Git remotes

- Bookmarks are named pointers with no notion of "checked out"; they move automatically
  when the commit they point at is rewritten. `<name>@<remote>` (e.g.
  `winter-tiles@upstream`) is the last-seen remote position.
- `jj bookmark set <name> -r <rev>` creates or moves by name; `-B/--allow-backwards` is
  needed to move one backwards or sideways. `jj bookmark move` only moves existing ones
  and can select by `--from <revs>`; `jj bookmark create` only creates. Also `delete`,
  `rename`, `forget`, `track`, `untrack`, `list`.
- `jj git fetch` updates remote positions and propagates to tracked local bookmarks.
  Commits no longer reachable on the remote are abandoned locally unless
  `git.abandon-unreachable-commits = false`.
- `jj git push` defaults to pushing **tracking bookmarks in
  `remote_bookmarks(remote=<remote>)..@`**. `-b/--bookmark <name>` pushes one and starts
  tracking it, `--all` pushes everything, `--change <rev>` invents a name from a change ID,
  `--remote <name>` selects the remote (tracking does **not**). It is force-with-lease-like,
  proceeding only if the remote still matches the last fetch, and pushes only the range up
  to the bookmark's target, not descendants beyond it.
- In 0.44 `jj git init` and `jj git clone` are **colocated by default**: a `.git` directory
  sits beside `.jj` and jj imports/exports Git refs on every command; `--no-colocate` opts out.

## Revsets

- Operators, strongest binding first: `x-` parents, `x+` children, `::x` ancestors
  inclusive, `x::` descendants inclusive, `x::y` descendants of x that are ancestors of y,
  `x..y` ancestors of y that are not ancestors of x, `~x`, `x & y`, `x ~ y` (difference),
  `x | y`. `..` alone is every visible commit except the root.
- Functions: `all()`, `none()`, `root()`, `heads(x)`, `roots(x)`, `parents(x[,n])`,
  `children(x[,n])`, `ancestors(x[,n])`, `descendants(x[,n])`, `latest(x[,n])`, `merges()`,
  `empty()`, `conflicts()`, `divergent()`, `description(p)`, `author(p)`, `files(<fileset>)`,
  `bookmarks(p)`, `remote_bookmarks([p],[remote=p])`, `tags(p)`, `visible_heads()`,
  `mutable()`, `immutable()`, `working_copies()`, `at_operation(op,x)`.
- **A bare string in a pattern position is a glob, not a substring.** `description("relief")`
  matches only that exact text; use `description(substring:"relief")` or
  `description(glob:"*relief*")`. Kinds: `exact:`, `glob:`, `regex:`, `substring:`, each
  with an `-i` suffix for case-insensitivity. Symbols resolve as tag name, then bookmark
  name, then commit/change ID; force the last with `commit_id(…)` / `change_id(…)`.
- A divergent or hidden change ID needs a **change offset**: `xyz/0` is the most recent
  commit for that change, `xyz/1` the one before.
- `jj log` defaults to mutable revisions plus context; `jj log -r '::'` shows everything.

## Filesets

- Positional path arguments to `jj diff`, `jj log`, `jj squash`, `jj split`, `jj absorb`,
  `jj restore` and `jj status` are fileset expressions with `~`, `&`, `|`, parentheses.
- **The default pattern kind in 0.44 is `prefix-glob:`, resolved relative to the current
  working directory.** Resolve against the workspace root instead with `root:"path"`
  (prefix), `root-file:"path"` (that exact file), `root-glob:`, `root-prefix-glob:`. The
  cwd-relative kinds are `cwd:`, `file:`/`cwd-file:`, `glob:`, `prefix-glob:`.
- A directory name matches everything beneath it recursively: `atlas` matches
  `atlas/plate-07.svg` but not `atlasplate.svg`.

## Templates

- `-T/--template` is accepted by `jj log`, `jj show`, `jj op log`, `jj bookmark list` and
  others. The language is expressions, not printf: `++` concatenates and methods are called
  on values — `change_id.short(8)`, `change_id.shortest()`, `commit_id.short()`,
  `description.first_line()`, `description.lines()`, `author.email()`, `bookmarks`,
  `parents.map(|c| c.commit_id().short()).join(",")`, `if(c,a,b)`, `separate(" ",a,b)`.
- **A per-commit template emits no line break of its own.** Under `--no-graph` the
  per-revision output is concatenated with nothing between it: `-T 'description.first_line()'`
  over three commits prints `R: legendQ: atlasP: coastline` on a single line, so a template
  meant to give one line per commit must end with `++ "\n"`. Under the graph renderer the
  glyph column supplies the breaks and the trailing `"\n"` makes no difference.
- `.description()` usually ends with a trailing `\n` when non-blank; `.first_line()` does
  not. `--no-graph` drops the graph glyphs, wanted for machine-read output.
- `[template-aliases]` defines named and parameterised templates. A `jj config set` VALUE is
  parsed as TOML, so such a string needs quoting surviving both the shell and TOML.

## Conflicts

- Conflicts are **recorded in commits**: a rebase that conflicts still succeeds, and the
  conflict lands in the rebased commit and its descendants, to be resolved whenever.
- A conflicted file is materialised in the working copy as `<<<<<<< conflict N of M`, a
  `%%%%%%%` section holding a diff from the common ancestor, a `\\\\\\\` continuation label, a
  `+++++++` section holding one side verbatim, then `>>>>>>> conflict N of M ends`. To
  resolve, apply the `%%%%%%%` diff to the `+++++++` snapshot and replace the marked region.
- Resolve by editing the file, or `jj resolve --tool :ours` / `:theirs`. `jj resolve -l`
  lists conflicted paths; `-r <rev>` selects the revision (default `@`). To fix a conflict
  in an ancestor: `jj new <rev>`, resolve, then `jj squash` into it — or `jj edit <rev>`
  and resolve in place. Resolving at the commit where the conflict originated propagates
  the resolution to descendants automatically.

## Immutability and divergence

`immutable_heads()` defaults to `trunk() | tags() | untracked_remote_bookmarks()`, and the
immutable set is `::immutable_heads()`; commands refuse to rewrite anything in it. Change
what is immutable by redefining `immutable_heads()`, not the derived `immutable()` or
`mutable()` — e.g. `jj config set --repo revset-aliases.'immutable_heads()' 'none()'`.
Rewrite commands also take `--ignore-immutable`.

A change ID with more than one visible commit is **divergent** and is labelled `divergent`
in the log. It comes from rewriting the same change in two places, or from mixing `jj` and
`git` mutations in a colocated repo. Address one side by change offset (`xyz/0`, `xyz/1`)
or by commit ID; converge by abandoning the unwanted side, or by making one side's content
and position match the other.

## Workspaces

- `jj workspace add <path>` creates another working copy sharing one repo, named after the
  destination basename unless `--name` is given. `-r <revs>` sets the parents of its new
  working-copy commit; without `-r` it shares the current workspace's parents.
- Also `jj workspace list`, `root`, `rename`, `forget` (forgets it; files on disk stay).
- A workspace is **stale** when its working-copy commit was rewritten from elsewhere and
  its checkout never caught up. Fix with `jj workspace update-stale`, run from inside that
  workspace; commands there error out until you do.

## Reading state

`jj log -r <revset> -T <template> --no-graph -n <N>` (`--count` prints a count);
`jj diff -r <rev>` or `--from P --to Q` with `--summary`, `--name-only`, `--stat`, `--git`;
`jj evolog -r <rev>` for the commits a change previously pointed to. `jj <command> --help`
is authoritative for this build.
