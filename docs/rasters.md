# Source rasters and the derived trees

Moved out of `CLAUDE.md` whole; headings kept verbatim so citations resolve.

# Source rasters

AMNH Digital Library PDFs (`M11Pt01–03`).

**`scans/` is derived, not source.** It is `pdftoppm -r <dpi>` over `pdfs/` —
verified pixel-identical — **then `tools/greyscale_scans.py --commit`**, so it is
regenerable and stays out of git. The PDFs carry a **bitonal JBIG2 text master at
~300 dpi** (part 1 2781×3866 at 295.5 dpi, part 2 2550×3525 at 300, part 3
2550×3525 at 308.4 against an A4 page box; the covers `1-001`/`1-002` and the
foldout `1-361` have no master and are RGB at 150). The figure *photographs* are
separate embedded JPEGs already at 150 dpi, so nothing is recoverable there —
only the text gains.

**The rasters are greyscale, and the three that are not are named.** poppler
writes RGB, but `pdfimages -list` over the three PDFs reports exactly three
non-gray embedded images in the whole volume — `1-001`, `1-002` and `1-361`,
the covers and part 1's appended foldout map. Every other page's source is
`gray 1 1 jbig2`, i.e. one grey value written three times, so converting is
lossless by arithmetic (PIL's luma weights sum to 1, so R=G=B=v gives L=v) and
was checked per page against the ink mask besides. **829 converted, 3 kept,
0 skipped.** 913 MB → 604 MB, and a page decodes in ~0.03 s where it took ~0.11 s.
All three colour pages are `exempt`, so the segmenter still sees a uniform corpus.

Converted **in place rather than re-rendered**, and that is the safety argument:
`Image.convert("L")` cannot change dimensions, where a re-render that came back a
pixel different would silently invalidate every coordinate in `gt/zones/`,
`gt/ocr/` and `gt/fig/` — which is the cost `tools/migrate_coords.py` exists to
record. A rebuild from `pdfs/` must run the converter afterwards or every raster
sweep quietly goes back to costing three times what it should.

Rendering at 300 dpi is **not** a clean ×2 of the old 150 dpi rasters — across the
832 pages, **none** is exactly double, and most are a pixel short on one axis. So
anything mapping between the two spaces must **take the ratio from the two rasters,
per page and per axis**. Computing it as `ceil(pt/72*dpi)` fails too, on float
error: it predicts 2782 for the covers where poppler renders 2781.

## The tools/ scripts

`tools/` is where work against something outside the repository lives — the
harness is offline and deterministic over what is committed. None of it is part
of a loop.

`greyscale_scans.py` is live but **only after a re-render**: it converts `scans/`
to greyscale, is idempotent (a page already in mode `L` is left alone), and has
to run whenever poppler has written the tree afresh.
`build_geo.py` compiles `data/geo/` from three sources in `scratch/` and is
`docs/edition.md`'s; `wikidata.py` proposes identities for unlocated entities
against a live API and derives `geo:` from the ones a human adopted, and is
`docs/edition.md`'s too.
`migrate_coords.py` (150→300 dpi) and `migrate_fig_bboxes.py` (which reduced
`gt/fig/` to bounding boxes and re-keyed `data/readings.md` with it) are **spent
one-shot migrations**, kept for the reasoning in their docstrings; re-running
either would corrupt what it already converted, and both say so at the top.

The METS manifest is `harness fig mets --out DIR` now, not a script — and it
writes only where you point it, because the one that used to sit tracked in
`gt/fig/` was an export artifact describing a store that has since been
rewritten under it. The two `strip_*_lines.py`, which produced the line-free
`gt/fig/`, are gone: `git log -- tools/strip_lines.py` has them, and the tag-ID
lesson one of them recorded is quoted where it is load-bearing.

# The derived trees

Seven directories are **derived**: git carries none of them and a fresh clone has
none of them. `harness/farms.py` is the one declaration — `harness views check`
reports them, `harness views build` rebuilds them. **Both name their farms and
neither has a default**: `views build --all` is a corpus-level sweep costing 252
repainted page composites, and nothing at the call site said so, so the caller
who wanted one view relinked after a `restore` was the one paying for it. In a
per-page loop reach for the per-domain spelling — `ocr link`, `zones link` —
the same way a per-page normalize names its page rather than sweeping the corpus.
(That "everything" was spelled `all`, a *value* of the FARM positional, until the
CLI settled on `--all` for every corpus form; the old spelling is trapped.)

    ocr/  zones/                 the read views over the paired stores
    scans/w-figs-blotted/        the segmenter's training rasters
    scans/w-figs/  scans/w-ocr/  selections over scans/, by criterion
    scans/                       reported, never built here: pdftoppm over pdfs/
                                 (symlinks outside the repo), then
                                 tools/greyscale_scans.py --commit
    train/bogoras-seg/           reported, never built here: assemble's scratch

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
  exactly what `exempt` exists to prevent in `gt/zones/`.

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
