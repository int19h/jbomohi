# Corpus size at M1, and whether mail moves to a companion repository

SPEC.md 2.7 sets the budget and says the companion-repository question is
decided at M1 with numbers rather than in advance. These are the numbers, from
the first corpus that carries every source, IRC included.

## Decision

**Mail stays in `main`. No companion repository.**

`jbomohi-mail` remains available if a later milestone changes the shape, but
nothing measured here calls for it.

## The budget

| limit | source | value |
|---|---|---|
| repository size | GitHub recommendation | 5 GB |
| single file | GitHub hard limit | 100 MB |
| expected packed | SPEC.md 2.7, written before measurement | 0.6–1.2 GB |
| per push | GitHub | 2 GB |

## What the corpus actually contains

Measured at the tip of the publication build,
`5b21f473e01c1db6839d0465d5b1d6a1d3ae0a97`.

| top level | files | bytes at the tip |
|---|---:|---:|
| `mail/` | 139,822 | 1,185.1 MiB |
| `_meta/` | 25,595 | 107.7 MiB |
| `wiki/` | 14,144 | 52.9 MiB |
| `irc/` | 10,536 | 51.6 MiB |
| `dict/` | 92,817 | 31.7 MiB |
| `tiki/` | 2,948 | 20.3 MiB |
| `cll/` | 246 | 13.0 MiB |
| `grammars/` | 97 | 3.1 MiB |
| instruction files | 7 | under 0.1 MiB |
| **total** | **286,212** | **1,465.5 MiB** |

Counts are blobs; the tip also holds 16 gitlinks, the vendored grammar
submodules, which are references rather than content.

Mail is 81% of the bytes at the tip, which is what SPEC.md 2.7 anticipated when
it named mail as the source that would decide the question.

IRC is the source added between the two builds this record measures: 10,536
day files, 51.6 MiB of text, and 10,871 archive manifests, which is where the
`_meta/` growth went.

## Against the limits

**Single file.** The largest object in the tree is
`_meta/mail/lojban-list/messages.csv` at 21.39 MiB, followed by two individual
mail messages at 14.38 and 11.45 MiB and
`_meta/mail/lojban-list/duplicates.csv` at 13.19 MiB. Nothing is within a
factor of four of the 100 MB limit. The two large messages are genuine: single
posts carrying long quoted digests.

**Repository size.** **997.80 MiB**, against the 5 GB recommendation: about a
fifth of it, and inside the 0.6 to 1.2 GB the specification predicted before
anything was measured. There is no reading of the limit, decimal or binary,
under which this corpus is close to it.

Four measurements are recorded, because the difference between them was
misread once and the misreading is worth preventing. `size-pack` is git's own
figure and counts the pack together with its index; the byte column is the
pack file alone, which is why the two differ by about 28 bytes per object.

| corpus | collection | pack bytes | `size-pack` | wall |
|---|---|---:|---:|---:|
| 70f706dd | `gc --prune=now`, `pack.windowMemory=256m`, `pack.threads=2` | 5,253,197,474 | — | 1,029 s |
| 70f706dd | `repack -a -d -f`, git's defaults | 988,636,654 | 992.50 MiB | 1,971 s |
| 5b21f473 | `gc --prune=now`, git's defaults | 5,416,809,204 | 5.10 GiB | 525 s |
| 5b21f473 | `repack -a -d -f`, git's defaults | 992,125,874 | **997.80 MiB** | 1,984 s |

**The cause is the command, not the settings.** `gc` reuses the deltas already
in the pack, and a `fast-import` build writes poor ones because it optimises
for speed. `repack -f` discards them and recomputes. The last two rows are the
proof, and they are the ones to read together: the same 1,933,818 objects, the
same git defaults — no memory bound, no thread cap — and a factor of 5.2
between them. (The first two rows are the earlier corpus. An earlier version
of this table set the bounded run beside a default one from the other build,
which changed two things at once in the other direction; the same-corpus pair
settles it without that.)

An earlier version of this record said the difference was the delta window,
and that a bounded window is what a memory-constrained machine should expect
its local pack to cost. Both claims were wrong. Two variables changed between
the first two runs measured — the command and the window — and the result was
attributed to the window. A memory-constrained machine running `repack -f`
gets the small pack as well; it only takes longer.

What this does not change is the decision. Section 2.7 asks whether the corpus
fits, and 992.50 MiB answers it whichever knob produced that number. The
correction is to the explanation, not to the conclusion.

**Push.** The initial push runs in commit ranges under `jbomohi build --push`,
which fast-forwards `main` in 5,000-commit steps and publishes the snapshot tag
last, so no single push approaches the 2 GB limit regardless of total size.

## Why the as-built figure is not the one that decides

A `fast-import` build writes objects with minimal delta compression, so the
pack it leaves is larger than the same history repacked. This build left
6.07 GiB before any collection, part of it the history it replaced; only after
the collection does a single pack describe this corpus alone, at 1,933,818
objects.
The figure that matters is what a server stores and a clone transfers, which is
the force-repacked one. Collecting alone is not enough: it drops what is
unreachable but keeps fast-import's deltas, so it leaves a pack several times
larger than the history needs.

## Provenance of these numbers

Measured on the publication build: corpus head
`5b21f473e01c1db6839d0465d5b1d6a1d3ae0a97`, 303,631 commits from 303,629
source events, with IRC and the utf8mb4 Tiki export in the archive. `jbomohi
verify` against that head, run with tools `1bf4747`:

```
verify: commits=303631 files=286212 sources=28 csv_indexes=84 mail_messages=112300
verify_wall_seconds=493.53 verify_maxrss_kb=820136
```

Build wall time 100.4 minutes at a peak of 11.97 GiB; `gc` 8.7 minutes at
5.97 GiB; `repack -a -d -f` 33.1 minutes at 8.54 GiB. The corpus this replaced,
`70f706dd`, was 293,095 commits over 264,799 files and repacked in 32.8 minutes
at 8.62 GiB: the collection costs what the whole history costs, not what was
added to it.

The heads move on. These figures describe the build they name; a later `update`
appends to it without re-measuring anything here.

## Commits that record an event and change nothing

Of the 303,631 commits, **11,997 (3.95%) have their parent's tree**. They are
real source events that altered no bytes: an edit that saved a page unchanged,
a page move that left the file where it was, a rename that changed only a
letter's case, a Tiki `@current` row equal to the last history version.

| source | commits with their parent's tree |
|---|---:|
| wiki | 9,856, of which 4,768 are page moves |
| tiki | 2,136: 1,839 `@current` rows, 297 numbered versions |
| dict | 5 |
| **total** | **11,997** |

Measured with `git log --format='%H %T %P'` over the whole history, comparing
each commit's tree with its single parent's.

The shape is specified — SPEC.md 3.3 rule (4b) calls a tree equal to its
parent's a legitimate commit — but `git log -- <path>` lists only commits that
changed the path, so it prunes exactly these. A librarian agent reading the
rendered instructions reported a Tiki page version as missing on that basis
when the version was present at every layer. `main`'s `AGENTS.md` says so since
tools `df3b1a8`.

## What would change this

Mail grows by roughly the volume of new list traffic, which is small. The
decision would need revisiting if a future milestone added a source of
comparable size to mail, or if media were ever admitted, which SPEC.md 2.7
excludes. Recorded at M1; not revisited unless one of those happens.
