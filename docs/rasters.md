# Source rasters and the derived trees

Moved out of `CLAUDE.md` whole; headings kept verbatim so citations resolve.

# Source rasters

AMNH Digital Library PDFs (`M11Pt01–03`).

**`scans/` is derived, not source.** It is **`harness scans extract --all --rasters
DIR`** over `pdfs/`, then **`harness scans swap DIR`**, so it is regenerable and
stays out of git. Every page carries a PNG `tEXt` chunk naming the PDF it was cut
from and that file's sha256, and the manifest's `_sources` block digests the PDFs
themselves — `harness scans audit` re-reads them and says so if one has changed.
The PDFs are MRC-layered: a **1-bit JBIG2 master** for each page's type, plus
separate embedded JPEGs for the photographs. The rasters are cut from those layers
rather than rendered from the page.

**Every master is placed at scale 1.0 and is exactly 300 dpi.** Measured against its
own placement rather than the page box: 470 pages at (300.00, 300.00), 359 at
(300.00, 300.04), and the 3 masterless RGB pages at 150. An earlier version of this
file said part 1 was "295.5 dpi" and part 3 "308.4 against an A4 page box" — those
divided by the mediabox and were wrong. **The scans were always uniform; only the
page boxes the scans were wrapped in were arbitrary**, and that is the whole of what
went wrong for twenty months:

| part | mediabox | master | placement | `pdftoppm -r 300` gave |
|---|---|---|---|---|
| 1 body (358 pp) | 677.7 × 935.1 | 2781 × 3866 | centred, +5.13/+3.69 pt | 2824 × 3897 — white padding |
| 2 (268 pp) | 612 × 846 | 2550 × 3525 | (0, 0) | 2550 × 3525 — exact |
| 3 (202 pp) | 595.27 × 841.89 (A4) | 2550 × 3525 | −8.37/−2.05 pt | 2481 × 3508 — **cropped** |

So the parts differed only by a **translation**, and rendering resampled a master
that could have been copied. Part 1's offset is *fractional* — 5.13 pt is 21.375 px
— so poppler resampled every pixel of every page for a shift of three-eighths of
one. Part 2 was at (0, 0) with the right dimensions and poppler smeared it anyway:
247 grey values out of a 2-value source. And part 3's render **cropped ~35 px from
each side**, so that part was segmented and OCR'd below source resolution from the
beginning. Those 35 px are verified blank on all 202 pages; nothing was lost.

**The rasters are bitonal where the page holds no photograph** — 593 of 832 — and
8-bit `L` where it does, 236 of them. The remaining three are the RGB foldouts
this file describes below; 593 + 236 + 3 is the whole store. Photographs are pasted back **nearest at
their integral 2×**, so every native JPEG sample survives as an exact block and a
crop from the composite shows the same pixels as the embedded original.
**484 MB → 180 MB** over the page files.

**The 3 with no master are written at their own size**, not the page's. `1-001` and
`1-002` (the covers) and `1-361` (part 1's appended foldout map) are each one RGB
photograph of a whole leaf at 150 ppi; rendering the page at 300 doubled them for
nothing, turning 796 KB of source into 26.5 MB of PNG and visibly costing the
foldout. They are 1391×1933, 1391×1933 and 1833×1994 now — **the only three pages
whose two spaces differ by a scale rather than a translation**, which is safe only
because all three carry a leaf kind and so no coordinate at all. `harness/migrate.py`
checks that rather than assuming it, and refuses a masterless page that holds one.

`tools/greyscale_scans.py` is spent: poppler's RGB output is no longer what `scans/`
holds. `tools/migrate_coords.py` is spent too, and its successor is
`harness scans swap` — whose logic lives in `harness/migrate.py` where the
tests reach it. **The move was a translation, not a rescale**, taken as one rounded
integer per page from `data/pdf_images.json`: 1942 files migrated, 903 already in
the target space (part 2 and the four unmoved pages), 0 aborted, 24 coordinates
clamped and every one of them in `mz/`. `data/_migrated.json` is the receipt, and it
exists because part 2's dimensions are identical before and after — no size check
can tell "correctly untouched" from "not yet reached".

## The tools/ scripts

`tools/` is where work against something outside the repository lives — the
harness is offline and deterministic over what is committed. None of it is part
of a loop.

**`extract_scans.py` is gone, and the cut is `harness scans` now.** It declared
`pymupdf` inline (PEP 723) and the isolation was argued for here as a firewall: an
environment with no harness in it, so a script that *cannot* import the package
cannot drift into a loop. What the isolation actually bought was a cut no test
could reach and a manifest no verb read back, and part 3 was read below source
resolution for twenty months underneath it. `harness scans extract` cuts,
`harness scans swap` installs the tree together with every coordinate keyed to it,
and `harness/tests/test_scans.py` holds the arithmetic. `pymupdf` is a declared
dependency; what keeps a PDF out of the passes is that no pass calls the one verb
that opens one. The group is `harness/VERBS.md`'s.

`build_leaf_layers.py` is the live one now, and the only script here whose
input is *tracked*: it splits an editor's leaf in `gt/page-img/` into the two
layers the reading view serves, into the derived `mz/page-img/`. Same PEP 723
isolation and the same reason. It runs over every master by default and takes
refs to scope it, so a leaf is a file drop plus one command rather than a
special case — which matters because Jochelson's *Koryak*, the sibling Jesup
volume, reproduces this same map. The image processing and what it deliberately
drops are `docs/apparatus.md`'s.
`build_geo.py` compiles `data/geo/` from three sources in `scratch/` and is
`docs/edition.md`'s; `gazetteer.py` proposes identities for unlocated entities
against a live API and derives `geo:` from the ones a human adopted, and is
`docs/edition.md`'s too.
`migrate_to_master.py` is gone with it: it was the driver for `harness/migrate.py`
and `harness scans swap` is that driver now — which is also the generalisation, from
"the legacy render into the master" to any manifest into any other. The rule it was
written under stands and is why the logic never lived in the script: "a migration
whose correctness argument sits in a script that is run once and never imported is a
migration nobody can check afterwards".
`greyscale_scans.py` (poppler wrote RGB and the JBIG2 master is grey),
`migrate_coords.py` (150→300 dpi) and `migrate_fig_bboxes.py` (which reduced
`gt/fig/` to bounding boxes and re-keyed `data/readings.md` with it) are **spent
one-shot migrations**, kept for the reasoning in their docstrings; re-running any
would corrupt what it already converted, and each says so at the top.

The METS manifest is `harness corpus mets STORE --out DIR` now, not a script,
and it serves any ALTO store rather than `gt/fig/` alone — it was `fig mets`
while that was the only caller, though the builder never read a figure. It
writes only where you point it, because both manifests that ever sat tracked in
a store described a store that had been rewritten under them: `gt/fig/METS.xml`,
and `gt/ocr/METS.xml`, which outlived the first removal and manifested 20 files
against a store of 663. The two `strip_*_lines.py`, which produced the line-free
`gt/fig/`, are gone: `git log -- tools/strip_lines.py` has them, and the tag-ID
lesson one of them recorded is quoted where it is load-bearing.

# The derived trees

Seven directories are **derived**: git carries none of them and a fresh clone has
none of them. `harness/farms.py` is the one declaration — `harness views check`
reports them, `harness views build` rebuilds them. **Both name their farms and
neither has a default**: `views build --all` is a corpus-level sweep costing 252
repainted page composites, and nothing at the call site said so, so the caller
who wanted one view relinked after a `restore` was the one paying for it. In a
per-page loop name the farm — `views build ocr`, `views build zones` —
the same way a per-page normalize names its page rather than sweeping the corpus.
(That "everything" was spelled `all`, a *value* of the FARM positional, until the
CLI settled on `--all` for every corpus form; the old spelling is trapped.)

    ocr/  zones/                 the read views over the paired stores
    scans/w-figs-blotted/        the segmenter's training rasters
    scans/w-figs/  scans/w-ocr/  selections over scans/, by criterion
    scans/fig-crops/             the figures themselves, cut out: one PNG per
                                 GraphicZone in gt/fig/, for the edition and
                                 whatever builds an epub. `harness fig crops`
    scans/                       reported, never built here: harness scans extract
                                 over pdfs/ (symlinks outside the repo), then swap
    train/bogoras-seg/data/      reported, never built here: assemble's scratch —
                                 the laid-out set; the checkpoints go to model/

**Two more trees under `scans/` are deliberately *not* farms**, and saying so is the
point: `scans/w-blotted/` (`ocr blot`, pink and blue for a human to read) and
`scans/w-blotted-edit/` (the line editor's per-session cache). Both are built on
demand and are legitimately absent until someone asks, so registering them would
make `views check` report a fault for a cache nobody has needed yet — and `absent`
in that table means "should be here and is not". They went with the old raster tree
in the master-space rebuild and neither was missed, which is the argument confirming
itself. Anything that must survive a rebuild belongs in `farms.FARMS`; these do not.

Three things this settled, each of which had been true and unnoticed:

- **Two of them had no builder at all.** `scans/w-figs/` and `scans/w-ocr/` were
  made by hand, and this file said so. A hand-made farm drifts, and had: `w-ocr`
  was missing `1-060` the day it was restored. **`w-ocr`'s membership is `gt/ocr/`,
  not the `ocr/` view** — the farm itself settled that, holding the gt pages and
  none of the mz-only ones. View membership would also self-destruct, since after a
  corpus `ocr predict` every page has OCR and the selection becomes all 832.
- **Nothing relinks a view automatically** after `restore` or `save_zones`, so
  `views check` reporting `stale` is the normal way to find that out.
- **`.gitkeep` was considered and is wrong**, which is worth recording because it is
  the obvious fix. A tracked placeholder makes a directory *exist and be empty*,
  converting a loud absence into a silent one — the worse of the two states, and
  exactly what the leaf kinds exist to prevent in `gt/zones/`, where a page with
  no zones and no kind is refused rather than saved as an empty record.

**An absent derived tree refuses; an absent store does not.** This is the fresh-clone
rule and the line matters. `Path.glob()` on a missing directory returns empty
silently, so `harness ocr pages` on a clone used to print an empty table and exit 0.
Now `context._refs_under` asks the registry: a **farm** that was never built raises,
naming the command that builds it; a **store** that holds nothing stays a silent
empty, because "nothing has been predicted" is a true statement about the corpus and
the ordinary state of a clone. `harness ocr pages --store mz` on a clone still
answers `[0]`, exit 0. The two halves are pinned together over one function in
`test_farms.py`, since read alone either looks like an inconsistency worth tidying.

**`views check` says how deep it looked, and that is the `verified` column.** For
`scans/w-figs-blotted/` it reads `membership`, because nothing there opens pixel data
or the timestamps behind it — so `state: ok` may not be read as "up to date".

**That column used to be justified by a claim that was simply false**, and the
correction is worth keeping because the false version had been restated in four
places and read as rigour. It said content freshness there was not merely unchecked
but *uncheckable*, on the grounds that a figure ALTO corrected after the blot leaves
a raster still showing the figure and an mtime test would pass it. It would not: a
corrected ALTO is **newer** than the blot, so a test against both its inputs —
`scans/` and `gt/fig/` — catches exactly that case. (Against the scan alone it would
be blind, the scan never changing; that is an argument for naming the right inputs.)
What no mtime test can see is a **deleted** figure ALTO — a page whose zones were
withdrawn should go back to being a link, and the stale painted PNG is still newer
than the scan, absence having no timestamp. That is a membership question, not a
content one. So `zones blot` repaints unconditionally **because skip policy here is
undecided** — it belongs with the dependency graph, which is a sprint of its own and
has not run — and not because freshness is unknowable. `membership` remains the
honest word for what `views check` actually did.

Worth naming, because this entry has now been wrong twice in the same shape: the
first version said freshness was *uncheckable*, and the correction replaced it with
*cost* — "252 composites take seconds, an incremental path would add a way to be
wrong for very little". That reads as a design decision taken, where the truth is a
decision deferred. A confident reason standing in for an open question is the same
failure as a confident reading standing in for an unread glyph.

The fourth state `?`
means no verdict was available at all (`scans/`, `train/`), and does not gate; nor
does the gate cover farms `build` cannot fix, since an exit code demanding a repair
the named command does not perform teaches a reader to ignore it.
