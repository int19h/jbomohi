# Corpus size at M1, and whether mail moves to a companion repository

SPEC.md 2.7 sets the budget and says the companion-repository question is
decided at M1 with numbers rather than in advance. These are the numbers, from
the first complete seven-source corpus.

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

Measured at the tip of the publication build, `70f706ddb5bec04b1e08a53a582c8b011d565ea7`.

| top level | files | bytes at the tip |
|---|---:|---:|
| `mail/` | 139,822 | 1,185.1 MiB |
| `_meta/` | 14,718 | 103.1 MiB |
| `wiki/` | 14,144 | 52.9 MiB |
| `dict/` | 92,817 | 31.7 MiB |
| `tiki/` | 2,948 | 20.3 MiB |
| `cll/` | 247 | 13.0 MiB |
| `grammars/` | 112 | 3.1 MiB |
| instruction files | 7 | under 0.1 MiB |
| **total** | **264,815** | **≈1,409 MiB** |

Mail is 84% of the bytes at the tip, which is what SPEC.md 2.7 anticipated when
it named mail as the source that would decide the question.

## Against the limits

**Single file.** The largest object in the tree is
`_meta/mail/lojban-list/messages.csv` at 21.39 MiB, followed by two individual
mail messages at 14.38 and 11.45 MiB and
`_meta/mail/lojban-list/duplicates.csv` at 13.19 MiB. Nothing is within a
factor of four of the 100 MB limit. The two large messages are genuine: single
posts carrying long quoted digests.

**Repository size.** **992.50 MiB** (988,636,654 bytes) packed with git's default settings, against
the 5 GB recommendation. That is 0.99 GB decimal, inside the 0.6 to 1.2 GB the specification predicted before anything was measured, and about a fifth of the recommendation. There is no reading of the limit, decimal or binary, under which this corpus is close to it.

Two numbers are recorded, because the difference between them is a finding in
its own right:

| repack | settings | packed |
|---|---|---|
| bounded | `pack.windowMemory=256m`, `pack.threads=2` | 4.89 GiB (5,253,197,474 bytes) |
| default | git's own window and thread defaults | **992.50 MiB** (988,636,654 bytes) |

The first was run that way to protect a shared machine that had already lost
two builds to memory exhaustion. Bounding the delta window is exactly the
setting that costs compression on a corpus of a hundred thousand similar mail
messages, so it is not the figure this decision rests on. It is, however, what
anyone rebuilding this corpus on a small machine should expect their local pack
to cost, which is why it stays in the record rather than being discarded.

**Push.** The initial push runs in commit ranges under `jbomohi build --push`,
which fast-forwards `main` in 5,000-commit steps and publishes the snapshot tag
last, so no single push approaches the 2 GB limit regardless of total size.

## Why the as-built figure is not the one that decides

A `fast-import` build writes objects with minimal delta compression, so the pack
it leaves is larger than the same history repacked. The build left 10.33 GiB
across three packs, of which one was the previous history the build replaced
and one the history retired by the corpus migration; only after the collection
does a single pack describe this corpus alone, at 1,859,713 objects.
The figure that matters is what a server stores and a clone transfers, which is the repacked one.

## Provenance of these numbers

Measured on the publication build: `tools` at
`02e67f6e38dfdc7c56a5f49545976b8368f4acf1`, corpus head
`70f706ddb5bec04b1e08a53a582c8b011d565ea7`, 293,095 commits from 293,093
source events, with the utf8mb4 Tiki export in the archive. `jbomohi verify`
was run three times against it: after the build, after the collection, and
again after the default repack, with identical results each time, 293,095
commits over 264,799 files and 112,300 mail messages.

Build wall time 105.9 minutes at a peak of 11.78 GiB; collection 17.1 minutes
at 6.46 GiB; default repack 32.8 minutes at 8.6 GiB.

## What would change this

Mail grows by roughly the volume of new list traffic, which is small. The
decision would need revisiting if a future milestone added a source of
comparable size to mail, or if media were ever admitted, which SPEC.md 2.7
excludes. Recorded at M1; not revisited unless one of those happens.
