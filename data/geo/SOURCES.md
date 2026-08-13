# `data/geo/` — where the shapes come from

Everything under this directory is **compiled**, by `tools/build_geo.py`, from
sources that live outside the repository. It is nonetheless **tracked**, and
that is deliberate: `scratch/` is gitignored and one source is a symlink into a
download directory, so a clone can neither rebuild this nor be told why the
atlas is empty. The same split `scans/` has — a `tools/` script builds from
what only this machine holds, the harness reads what is committed.

This file is authored by hand and is a **precondition of the build**, not a
by-product of it. A derived geometry with no provenance is a claim about the
world with nothing behind it, and two of the three sources below carry
conditions.

## The sources

| in the store | source | licence |
|---|---|---|
| `langarea/*.json` | Glottography `asher2007world`, "Traditional speaker areas derived from Asher & Moseley 2007" | **CC BY 4.0 — attribution required** |
| `watershed/*.json` | Global Watersheds (mghydro.com), over MERIT-Hydro and HydroSHEDS | **CC BY-NC 4.0 or ODbL 1.0 — see below, and it is a live question** |
| `base/*.json` | Natural Earth 1:50m `land` and `lakes` | public domain |
| `region/*.json` `marine/*.json` | Natural Earth 1:10m `geography_regions_polys` and `geography_marine_polys` | public domain |

### Asher & Moseley 2007, via Glottography

    Asher, R. E. & Christopher J. Moseley (eds.) 2007.
    Atlas of the World's Languages. 2nd edn. Routledge.
    Traditional speaker areas, CLDF: https://github.com/Glottography/asher2007world
    Licence: https://creativecommons.org/licenses/by/4.0/

**CC BY 4.0 obliges attribution wherever the shapes are published**, so the
citation above is carried in the corpus `teiHeader`'s rights statement beside
`entities/` — not only here, because this file ships with the repository and
the reading view does not.

Shapes are keyed by **glottocode** (`langarea:chuk1273`), which is the id the
source itself carries and the only stable one; a title can be re-spelled and a
family re-assigned.

**Four of this edition's seven Tier-1 codes have no polygon in it**, and
`index.json` carries them in the `absent` block (below) so the atlas can say the
source does not draw them rather than render a blank frame. Established against
the full title list of every Asher feature reaching north of 50°N, not against a
keyword guess:

- **Siberian Yupik** — the book's "Asiatic Eskimo", `ypk`. Asher draws Central
  Alaskan Yupik, Pacific Gulf Yupik and the two Inupiatun areas; no Asian
  Yupik area exists in the dataset. The American areas are its comparanda and
  are *not* substitutes for it.
- **Chuvan** (`xcv`), **Kerek**, and **Tundra (Northern) Yukaghir** — no
  polygon. Southern Yukaghir is the only Yukaghir area present.

**Chukchi is clipped at the antimeridian in the source.** `langarea:chuk1273`
has ten vertices sitting exactly on 180° and no counterpart west of it, so
East Cape and Uelen — Chukchi-speaking by every account including this book's —
are simply outside the polygon. The build reports this on every run and does
**not** close the shape up: extending a speaker area past where its publisher
drew it would be inventing evidence in the one place a reader would never
check. A map of Chukchi therefore stops at 180°, and that is the source's
statement, not this edition's.

**And that is still true**, now that the edition draws the land past it. What
closes the gap is not a redrawn polygon but a composite `area:` on the entity —
`langarea:chuk1273, base:chukotka-east-of-meridian` — whose second member is
Natural Earth land and says nothing whatever about speech. See
`base:chukotka-east-of-meridian` below: the geometry in this store stays
sourced, and the one inference lives in an entity file, under a `status:`, with
a name on it.

### The watersheds

    Global Watersheds — https://mghydro.com/watersheds/
    Matt Heberger (matt@mghydro.com), © 2022; the tool is open source.
    Delineated from MERIT-Hydro (2021) and HydroSHEDS (2013).

24 basins in `scratch/watersheds/`, delineated interactively — one file per
outlet, each carrying its own `wid`, `area_km2` and `retrieved` timestamp, and
several carrying the tool's own message about reverting to low-precision mode
above 50,000 km². Those properties are preserved into `index.json`, so every
basin can say when it was delineated and under which id. The timestamps are all
within one hour of 2026-08-07 — one session, one tool.

**A delineation is a model output, not a survey**, which is the whole reason
`geo verify` reports rather than gates: the Omolon basin is 25% outside the
Kolyma basin in these files, and the disagreement is between two runs of a
model, not between a river and a map.

**Which precision is which dataset is not stated.** The tool offers "lower
precision (faster)" and "higher precision (slower)" and does not say that the
first is HydroSHEDS and the second MERIT-Hydro, though the resolutions make it
the obvious reading. It is left unstated here rather than inferred, because
`geo verify`'s whole account of why a true tributary measures 0.70–0.87 rests
on it and an inferred premise would make that account fluent nonsense. What
*is* established, and is enough for the check, is that the tool declares the
fallback per basin and this store records the declaration.

#### The licence is a live question, not a settled row

**MERIT Hydro is dual-licensed CC BY-NC 4.0 *or* ODbL 1.0** — and both branches
have teeth for a published edition:

    Yamazaki, D., Ikeshima, D., Sosa, J., Bates, P. D., Allen, G. H., &
    Pavelsky, T. M. (2019). MERIT Hydro: A high-resolution global hydrography
    map based on latest topography datasets. Water Resources Research, 55,
    5053–5073. https://doi.org/10.1029/2019WR024873

- **CC BY-NC 4.0** forbids commercial use. This edition is not commercial, but
  the licence travels with the shapes to anyone who clones the repository.
- **ODbL 1.0** is share-alike on the *database*: a derivative database must be
  offered under ODbL, and `data/geo/watershed/` is a derivative database.
  A rendered map is a "Produced Work" and needs only the notice.

HydroSHEDS states no single licence — "all data products come with specific
license terms, specified on the product pages and technical documentation" —
and asks for `Source: [page title], [url] downloaded on [date] © HydroSHEDS`.

**So this row is unfinished, and it is the only place in this repository where
the obligation is heavier than the content.** Three things want deciding, by a
human, before the atlas is published anywhere but a loopback port: which of the
two MERIT branches this edition takes; whether `data/geo/watershed/` therefore
has to carry ODbL rather than the corpus's CC BY; and whether the basins should
be re-derived from a single, plainly-licensed source instead. Nothing here is
blocked in the meantime — the server is loopback and the repository is not a
distribution — but a rights statement that quietly said "CC BY" over these
files would be a claim this project has no basis for.

### Natural Earth

    Natural Earth, 1:50m physical vectors — `ne_50m_land`, `ne_50m_lakes`
    https://www.naturalearthdata.com/  ·  public domain, no attribution required
    Fetched as GeoJSON from https://github.com/nvkelso/natural-earth-vector

Kept in `scratch/naturalearth/`, which is gitignored; the URLs above are what
re-fetching needs. 1:50m rather than 1:10m is the ruling: at the widths this
edition draws a map, the finer set costs several times the bytes for detail no
reader can see, and the coastline here is context rather than subject.

#### The 1:10m gazetteer, and why the ruling above does not apply to it

    Natural Earth, 1:10m cultural/physical labels —
    `ne_10m_geography_regions_polys`, `ne_10m_geography_marine_polys`
    https://www.naturalearthdata.com/  ·  public domain

**The 50m ruling was about context and these are subjects.** A coastline is
seen only at whole-region scale, so detail below a pixel is waste; a reader who
opens `water:chaun-bay` has come to look at Chaun Bay, and the frame is the bay.
So these two layers are taken at 1:10m and simplified at the language-area
tolerance rather than the base one.

Eleven features, and **each is named in a declared table** in
`tools/build_geo.py` exactly as the source spells it — `LANGAREAS`'s rule, for
`LANGAREAS`'s reason. Searching this file for "Chukchi" returns a sea, a range
and a peninsula, and choosing among them is a human's act, not a match:

| shape | NE layer | NE `NAME` | `FEATURECLA` |
|---|---|---|---|
| `region:chukchi-peninsula` | regions | `CHUKCHI PENINSULA` | Pen/cape |
| `region:st-lawrence-island` | regions | `St. Lawrence I.` | Island |
| `region:kamchatka` | regions | `KAMCHATKA PENINSULA` | Pen/cape |
| `region:wrangel-island` | regions | `Wrangel I.` | Island |
| `region:karagha-island` | regions | `Karaginskiy I.` | Island |
| `region:bear-islands` | regions | `Bear Is.` | Island group |
| `marine:chaun-bay` | marine | `Chaun Bay` | bay |
| `marine:bering-sea` | marine | `Bering Sea` | sea |
| `marine:okhotsk-sea` | marine | `Sea of Okhotsk` | sea |
| `marine:anadyr-bay` | marine | `Gulf of Anadyr'` | gulf |
| `marine:karagha-bay` | marine | `Karaginskiy Gulf` | gulf |

**Two features the layer carries and this edition declines**, both recorded in
`build_geo.py` beside the table so the omission reads as a ruling rather than an
oversight. `Arctic Ocean` and `North Pacific Ocean` clip to a rectangle at this
window — the frame already says that much — and would be the store's two largest
shapes for it. `Smith Sound` is in Greenland, outside the window entirely; the
book names it once, quoting Kroeber, and a comparandum is not a subject.

**What the layer does not carry is most of what this edition wants.** Of the
eleven double-duty bays the encyclopedia now holds, the 1:10m marine gazetteer
draws four — Chaun, Anadyr, Karaginskiy and, as their parent, Shelikhov. It has
no Kolyuchin, Kresta, Provideniya, Lavrentiya, Tkachen, Konyam, Korf, Gizhiga or
Penzhina bay, and no cape at all. Those stay unlocated rather than being placed
from anywhere else.

A declared name the layer does not carry is a build **note**, not a silence: the
source may re-spell one, and a table that quietly matched nothing would leave an
entity pointing at a shape that was never built. Each row keeps the source's own
`ne_name`, `featurecla` and `WIKIDATAID` into `index.json`, which is what let the
store's `wikidata:` link for the Chukchi Peninsula be caught reading `Q193527` —
a facial bone — against Natural Earth's `Q1002`.

#### `base:chukotka-east-of-meridian` — sourced land, cut by a declared rule

Natural Earth 1:50m land again, and **nothing else is in it**. It exists so that
a human can join the land east of 180° to Asher's clipped Chukchi area without
anything redrawing that area, and it is emitted under `base:` because that is
what it is: coastline, not a speaker area.

The cut is topological, not a longitude window, and that is the whole of its
correctness. "Asia east of 180" is not expressible as a box — in the store's
shifted frame East Cape sits at 190.4, St. Lawrence Island at 190 and the Seward
Peninsula at 195, so any box wide enough for Chukotka's tip contains Alaska. The
rule is instead:

1. the prepared, **unsimplified** land, already welded across the meridian;
2. of its components, the **largest one intersecting `langarea:chuk1273`** — the
   Asian mainland by construction. Smaller components that also touch it are
   islands inside the speaker area (Ayon, in Chaun Bay, is the standing case)
   and are reported and excluded: they are not the continent;
3. intersected with the half-plane east of 180°, and simplified.

Alaska is a different component and the Bering Sea islands are components of
their own, so neither can enter however the longitudes fall. Measured on the
built shape: 180.0–190.271°E, 64.28–68.98°N.

### The `absent` block holds two kinds of absence

It began as one — "a Tier-1 code Asher 2007 draws no polygon for", the four
above — and now also holds **a feature no gazetteer in hand carries at all**.
Those are different claims. The first is about one atlas's coverage of
languages; the second is about every source this edition has. Read as the first,
the second would say Asher omitted a strait, which Asher was never asked about.

So a row carries `sought` and `source` — what was looked for, and where — and
`why` says only what is particular to it. The live second case is **Bering
Strait**: neither Natural Earth 10m layer carries it, the marine gazetteer names
32 straits worldwide and not this one, and hydrographic sources generally draw a
strait as a line between two capes rather than as an extent. `water:bering-strait`
therefore carries a `geo:` point (Wikidata Q11769) and no `area:`, which locates
it without claiming a boundary nothing in hand draws.

## What the compiled files are

One shape per file, a GeoJSON `FeatureCollection` with the properties every
feature shared **hoisted to the collection** — the sources repeat `name`,
`wid`, `area_km2` and `retrieved` on all 589 features of a basin — and only
`layer` and `sorder` left on a feature.

Coordinates are rounded to 3 decimals (~100 m) after simplification at 0.01°
(~1 km), an order of magnitude coarser, so the rounding costs nothing the
simplification has not already spent.

**Longitudes are normalized into [60, 420).** Anything greater than 180 is west
of the antimeridian: Chukotka runs continuously from about 160 to 195 rather
than tearing from +179 to −179. `index.json` records the window and the base.

`index.json` is the census, and `harness geo list` reads it. It carries the
`absent` block above, so a people this edition cannot draw is a **row** in the
store rather than a silence — an entity pointing at nothing and an entity
nobody has got to yet look identical from outside, and only one of them is
finished.
