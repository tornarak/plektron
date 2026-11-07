"""Which text a store belongs to, and what its page files are called.

**One text, one stem, in kebab-case**: `chukchi`, `chukchi-mythology`, `koryak`,
`yukaghir`. A page's files are `<stem>-PP-NNN.*` in every store, and the stem is
declared once, in the `project.json` at the top of the text's stores. Nothing
derives it from the folder and nothing guesses it: a store with no manifest
refuses, because a default stem would be one book's name wearing the clothes of a
fact about every book.

**Imports nothing from this package but `refs.py` and `langs.py`, leaves**, so it
cannot join a cycle. `refs.py` holds the readings that need nothing but their
argument; a stem needs the manifest, so everything that has to spell a file name
comes here.

**What else a manifest declares, and why each is declared rather than found.**
`lang` is the language the book's prose is in, which nothing on a page states
and every reader of a page needs (`<html lang>`, the lexicon a detector asks).
`notation` names the transcription system its native forms are printed in, so
the inventory tables a gate applies are the ones that book's key licenses.
`dpi` is the resolution the source PDFs place their masters at, which `scans`
refuses a page against and every raster-pixel threshold is scaled by.
`witnesses` are second copies of the book, never cut into `scans/`, read only
as a second reading. `omit` names the leaves the *digitizer* added — a QR code,
a usage notice — which are no part of the book or the copy, so they are never
cut and the extract counts them instead of refusing them on every run. A
library's own cover or flyleaf is the copy's, and is `masterless` instead. Each has a default that is what *The Chukchee* has always
meant, so a manifest that says nothing about them means what it meant before.
"""
from __future__ import annotations

import json
import os
import re
from functools import cache
from pathlib import Path

from .langs import is_known, is_tier1
from .refs import REF_RE, norm_ref, parse_ref

#: The name of the manifest, and of what makes a directory a text's.
PROJECT_JSON = "project.json"
WORKSPACE_JSON = "workspace.json"

STEM_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*$")

#: What a manifest may say about going public: `drafts` shows `mz/tei/` beside
#: `tei/`, `collated` shows `tei/` alone, and absent keeps the text off the site.
PUBLISH = frozenset({"drafts", "collated", None})
#: A figure by its leaf and the zone's suffix, as `/fig/{ref}/{key}.png` names one.
FIG_RE = re.compile(r"^\d+-\d+/\w+$")

#: What a manifest that says nothing about these means: what *The Chukchee* has
#: always been, so the first text's manifest needs no edit to keep its meaning.
DEFAULT_LANG = "en"
DEFAULT_NOTATION = "jesup"
DEFAULT_DPI = 300

#: The notations a text may name. A literal here until `notation.py` holds their
#: tables, and then derived from it — a name with no tables behind it would be a
#: manifest choosing rules that do not exist.
NOTATIONS = frozenset({"jesup", "kolyma-1900"})

#: A witness's id: one lowercase letter, as `--witness b` spells it.
WITNESS_ID_RE = re.compile(r"^[a-z]$")
#: Where a witness's PDF lives: under `pdfs/witness/`, so `scans`' non-recursive
#: glob of `pdfs/*.pdf` can never cut it into `scans/` by a substring match.
WITNESS_DIR = "pdfs/witness/"


def _refuse(p: Path, msg: str) -> None:
    raise ProjectError(f"{p}: {msg}")


def _check_texts_fields(p: Path, rec: dict) -> None:
    """The fields a second text added: each optional, each checked when present.

    Checked here rather than at the reader because a manifest is read once and
    trusted everywhere after; a bad `dpi` found by `scans` would be found after
    the manifest had already been believed by everything that ran before it.
    """
    lang = rec.get("lang", DEFAULT_LANG)
    if not is_known(lang):
        _refuse(p, f"`lang` {lang!r} is not in langs.LANGS — add it there, with "
                   "the evidence, before a text may be written in it")
    if is_tier1(lang):
        _refuse(p, f"`lang` {lang!r} is Tier-1: the base language of a book's "
                   "prose is never a transcribed language, and a Tier-1 base "
                   "would exempt every unmarked span from the firewall")
    if rec.get("notation", DEFAULT_NOTATION) not in NOTATIONS:
        _refuse(p, f"`notation` must be one of {sorted(NOTATIONS)}; "
                   f"got {rec.get('notation')!r}")
    dpi = rec.get("dpi", DEFAULT_DPI)
    if not isinstance(dpi, int) or isinstance(dpi, bool) or dpi <= 0:
        _refuse(p, f"`dpi` must be a positive integer; got {dpi!r}")
    seen = set()
    for w in rec.get("witnesses", ()):
        if not (isinstance(w, dict) and isinstance(w.get("id"), str)
                and WITNESS_ID_RE.match(w["id"]) and isinstance(w.get("pdf"), str)
                and w["pdf"].startswith(WITNESS_DIR) and w["pdf"].endswith(".pdf")
                and isinstance(w.get("label"), str) and w["label"]):
            _refuse(p, f"a witness is {{\"id\": one letter, \"pdf\": "
                       f"\"{WITNESS_DIR}….pdf\", \"label\": …}}; got {w!r}")
        if w["id"] in seen:
            _refuse(p, f"witness id {w['id']!r} is declared twice")
        seen.add(w["id"])
    for field_ in ("masterless", "omit"):
        for ref in rec.get(field_, ()):
            if not (isinstance(ref, str) and REF_RE.match(ref)):
                _refuse(p, f"`{field_}` holds page refs, PP-NNN; got {ref!r}")
    both = set(rec.get("masterless", ())) & set(rec.get("omit", ()))
    if both:
        _refuse(p, f"{sorted(both)} in both `masterless` and `omit`: a leaf is either "
                   "the book's, taken at its own size, or the digitizer's, never cut")


class ProjectError(ValueError):
    """A manifest that is missing or says something it may not."""


@cache
def _project(path: str) -> dict:
    p = Path(path) / PROJECT_JSON
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ProjectError(f"no {PROJECT_JSON} at {path}: not a text's stores") from None
    except json.JSONDecodeError as e:
        raise ProjectError(f"{p}: not JSON: {e}") from None
    stem = rec.get("stem") if isinstance(rec, dict) else None
    if not isinstance(stem, str) or not STEM_RE.match(stem):
        raise ProjectError(f"{p}: `stem` must be kebab-case, e.g. `chukchi-mythology`; "
                           f"got {stem!r}")
    if rec.get("publish") not in PUBLISH:
        raise ProjectError(f"{p}: `publish` must be one of "
                           f"{sorted(k for k in PUBLISH if k)}, or absent; "
                           f"got {rec['publish']!r}")
    image = rec.get("image")
    if image is not None and not (
            isinstance(image, dict) and isinstance(image.get("caption"), str)
            and image["caption"] and FIG_RE.match(str(image.get("fig")))
            and image.get("turn", 0) in (0, 90, 180, 270)):
        raise ProjectError(f"{p}: `image` must be {{\"fig\": \"PP-NNN/key\", \"caption\": "
                           f"…}} with an optional `turn` of 90, 180 or 270, or absent; "
                           f"got {image!r}")
    _check_texts_fields(p, rec)
    return rec


def project(root: Path) -> dict:
    """The manifest of the text whose stores sit at `root`."""
    return _project(str(Path(root).resolve()))


def stem(root: Path) -> str:
    """This text's file-name stem, without the joining hyphen."""
    return project(root)["stem"]


def lang(root: Path) -> str:
    """The language this text's prose is in, as `xml:lang` spells it."""
    return project(root).get("lang", DEFAULT_LANG)


def notation(root: Path) -> str:
    """The name of the transcription system this text's native forms are in."""
    return project(root).get("notation", DEFAULT_NOTATION)


def dpi(root: Path) -> int:
    """The resolution this text's masters are placed at in its PDFs."""
    return project(root).get("dpi", DEFAULT_DPI)


def px(root: Path, n: int) -> int:
    """A raster-pixel threshold calibrated at 300 dpi, at this text's resolution.

    Every such constant was measured on *The Chukchee*'s 300-dpi masters and says
    nothing in its name about it, so at 600 dpi each would silently be half the
    physical size it was tuned to — a speck reads as a band. Spelled through
    here at the use site, the constant keeps its measured value and its meaning.
    """
    return round(n * dpi(root) / DEFAULT_DPI)


def witnesses(root: Path) -> list[dict]:
    """This text's second copies, `[{id, pdf, label}]`, in manifest order."""
    return list(project(root).get("witnesses", ()))


def witness(root: Path, wid: str) -> dict:
    """One witness by its id, or an error naming the ones there are."""
    for w in witnesses(root):
        if w["id"] == wid:
            return w
    have = ", ".join(w["id"] for w in witnesses(root)) or "none"
    raise ProjectError(f"no witness {wid!r} in {PROJECT_JSON}; declared: {have}")


def stem_for(ref: str, root: Path) -> str:
    """The file-name stem of one page: `1-48` -> `chukchi-1-048`."""
    return f"{stem(root)}-{norm_ref(ref)}"


def ref_of(name: str, root: Path) -> str:
    """The page ref a file stem names, in this text. `chukchi-1-048` -> `1-048`.

    **Another text's stem is refused, not stripped**: `koryak-1-048` is not this
    book's 1-048, however much it looks like it. A bare ref names no book to
    disagree with, so it reads as this text's.
    """
    name = str(name).strip()
    if REF_RE.match(name):
        return norm_ref(name)
    own = f"{stem(root)}-"
    if name.startswith(own) and REF_RE.match(name[len(own):]):
        return norm_ref(name[len(own):])
    raise ValueError(f"{name!r} is not a page ref of `{stem(root)}`: expected "
                     f"{own}PP-NNN or a bare PP-NNN")


def page_files(directory: Path, suffix: str, root: Path) -> list[Path]:
    """The page files under `directory`, in (part, scan index) order.

    The whole name must be `<stem>-<ref><suffix>`, which a glob cannot say: a
    figure's crop `chukchi-1-048-a.png` and another text's `chukchi-mythology-1-048.png`
    both match `chukchi-*.png`. A directory that is not there holds no pages, as
    it does for a glob.
    """
    own = f"{stem(root)}-"
    found = []
    for p in Path(directory).glob(f"{own}*{suffix}"):
        rest = p.name[len(own):-len(suffix)] if suffix else p.name[len(own):]
        if REF_RE.match(rest):
            found.append((parse_ref(rest), p))
    return [p for _, p in sorted(found, key=lambda t: t[0])]


def repo_root() -> Path:
    """Where the code and its documents are, whichever text is being worked on."""
    return Path(__file__).resolve().parents[1]


def project_root(given: Path | None) -> Path:
    """The text's stores an invocation means.

    A directory named with `--root` is that text's or it is an error, **never a
    fallback to the cwd**: a mistyped root that quietly ran on whatever project the
    shell was in would write to the wrong book. Named nothing, the nearest ancestor
    of the cwd holding a manifest answers, spelled relative to the cwd, so what a
    run records stays free of this machine's paths.
    """
    if given is not None:
        if not (Path(given) / PROJECT_JSON).is_file():
            raise ProjectError(f"--root {given}: no {PROJECT_JSON} there, so it is no "
                               "text's stores")
        return Path(given)
    cwd = Path.cwd()
    for d in (cwd, *cwd.parents):
        if (d / PROJECT_JSON).is_file():
            return Path(os.path.relpath(d, cwd))
    found = sorted(str(p.parent.relative_to(repo_root()))
                   for p in repo_root().glob(f"*/*/{PROJECT_JSON}"))
    raise ProjectError(f"not inside a text's stores: name one with --root, or cd into "
                       f"it. Found: {', '.join(found) or 'none'}")


def workspace_root(root: Path = Path(".")) -> Path | None:
    """The nearest ancestor holding a `workspace.json`, if the text is in one."""
    for d in Path(root).resolve().parents:
        if (d / WORKSPACE_JSON).is_file():
            return d
    return None


def shared(root: Path, rel: str | Path) -> Path:
    """Where a store a text shares with its workspace is, for reading and writing.

    **The same relative path in both tiers**, so a text composes over its workspace
    as an object over its prototype: `rel` under the text if it is there, else under
    the workspace. A text with no workspace has only itself. Writing through this
    lands in the workspace unless the text already holds the store, which is why a
    text cannot start shadowing a whole store by adding one entry to it.
    """
    own = Path(root) / rel
    if own.exists():
        return own
    ws = workspace_root(root)
    return own if ws is None else ws / rel


def shared_rel(root: Path, rel: str | Path) -> str:
    """`shared`, spelled relative to the text, for a command printed to run there."""
    return os.path.relpath(shared(root, rel), root)


def refuse_another_texts(manifest: Path, root: Path, verb: str = "install over") -> None:
    """A workspace's model belongs to the text it was fitted to, which the others read.

    Reusing one needs nothing. **Installing over it, or scoring it, from another text
    is refused**: the first would destroy the only record of what it was trained on,
    and the second holds it to an eval list naming pages this text does not have, so
    it would answer with a number about nothing. The way out is for this text to hold
    its own `models/<track>/`, which `layout.shared` then finds first.
    """
    if not manifest.exists():
        return
    text = json.loads(manifest.read_text(encoding="utf-8")).get("text")
    if text and text != stem(root):
        raise ValueError(
            f"{manifest} was fitted to `{text}`, and this is `{stem(root)}`: refusing to "
            f"{verb} it. Give this text its own `models/<track>/` to train into.")


#: A page ref standing alone in prose, which is not one inside a word, a URL or a
#: qualified citation.
BARE_REF_RE = re.compile(r"(?<![\w/.:-])(\d+-\d{3})(?![\w-])")
#: A page ref naming its book: `chukchi-1-044`, `chukchi-mythology-1-044`.
CITED_REF_RE = re.compile(r"(?<![\w/.:-])([a-z][a-z0-9]*(?:-[a-z][a-z0-9]*)*)-(\d+-\d{3})(?![\w-])")


def workspace_stems(root: Path) -> list[str]:
    """Every text's stem in this text's workspace, one entry per text, so a stem two
    texts declare shows up twice. A text with no workspace has only its own."""
    ws = workspace_root(root)
    if ws is None:
        return [stem(root)]
    return [stem(p.parent) for p in sorted(ws.glob(f"*/{PROJECT_JSON}"))]


def citation_errors(text: str, root: Path) -> list[str]:
    """What is wrong with the page citations in a shared store's prose."""
    known = set(workspace_stems(root))
    out = [f"{ref} is bare: in a shared store a citation names its book, as "
           f"`{stem(root)}-{ref}`" for ref in BARE_REF_RE.findall(text)]
    out += [f"{s}-{ref} names `{s}`, which no text here declares"
            for s, ref in CITED_REF_RE.findall(text) if s not in known]
    return out


def bare_own_citations(text: str, own: str) -> str:
    """The served text's citations as its reader knows them: `chukchi-1-044` -> `1-044`.
    Another book's keep their stem, because to this reader they are the other book's."""
    return CITED_REF_RE.sub(lambda m: m[2] if m[1] == own else m[0], text)


def texts(repo: Path) -> list[Path]:
    """Every text's stores under `repo`, in path order."""
    return sorted(p.parent for p in Path(repo).glob(f"*/*/{PROJECT_JSON}"))


def publish(root: Path) -> str | None:
    """What the manifest says about putting this text on the public site. A text
    that says nothing stays off it, so going public is always a declared act."""
    return project(root).get("publish")


def image(root: Path) -> dict | None:
    """The picture that stands for this text on the landing page, `{fig, caption}` and
    `turn`, clockwise, for one the plate prints sideways: an editor's choice, so it is
    declared, and nothing infers one."""
    return project(root).get("image")


def site_base(root: Path) -> str:
    """The path a text's site is served under, from its folders: `/jesup/bogoras-chukchi`."""
    here = Path(root).resolve()
    ws = workspace_root(root)
    return f"/{ws.name}/{here.name}" if ws else f"/{here.name}"
