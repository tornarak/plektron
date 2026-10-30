"""`zones_ui.list_context` reads the split lists and the ink cache once, not per row.

`/zones/list?scope=all` renders 832 rows. `validate_page` builds `load_splits`
whenever it is not handed one — seven `.lst` files re-read, every name re-parsed
through `norm_ref` — and `cached_ink` parsed the whole cache file to look up a
single entry. Profiled: **9.9s and 2.0s of a 5.0s response**, with 700,000
`norm_ref` calls. Hoisting both took the page to 0.6s.

Neither value changes per ref inside one render, so this is a loop hoisting its
own invariant and not a cache: nothing is remembered across calls.

**The property most worth pinning is the one a hoist could plausibly break.**
`cached_ink` returns `None` for a page whose stamp no longer matches, and the
whole discipline of that function is that a stale verdict must never render
beside a live one. Hoisting the *read* must not hoist the *verdict* — the stamp
is still compared per ref against live mtimes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness import zones as zn

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
PROJECT = Path(__file__).parent.parent.parent / "jesup" / "bogoras-chukchi"


@pytest.fixture
def cfg() -> dict:
    from harness import zones_config as zc
    return zc.load_config(PROJECT)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    # The real zone config, copied the way `test_lookup.py` copies the marks
    # config: `validate_page` and `list_context` both refuse without one, and a
    # tree lacking it would exercise the refusal rather than the hoist.
    (tmp_path / "config").mkdir(parents=True)
    (tmp_path / "config" / "zones.json").write_text(
        (PROJECT / "config" / "zones.json").read_text(encoding="utf-8"),
        encoding="utf-8")
    d = tmp_path / "gt" / "zones"
    d.mkdir(parents=True)
    for ref in ("1-001", "1-002"):
        (d / f"chukchi-{ref}.xml").write_text(
            f'<alto xmlns="{ALTO_NS}"><Layout><Page><PrintSpace>'
            '<TextBlock ID="z1" TAGREFS="T1" HPOS="100" VPOS="100" '
            'WIDTH="800" HEIGHT="200"/></PrintSpace></Page></Layout>'
            '<Tags><OtherTag ID="T1" TYPE="type" LABEL="MainZone-P"/></Tags>'
            "</alto>", encoding="utf-8")
    # `list_context` reaches `scans/`, and `validate_page` opens the raster to
    # measure the column — so these are real images rather than empty files.
    # `farms.require` refuses an absent tree outright rather than treating it as
    # empty, which is the check being satisfied rather than dodged.
    from PIL import Image
    (tmp_path / "scans").mkdir(parents=True)
    for ref in ("1-001", "1-002"):
        Image.new("1", (1000, 1400), 1).save(
            tmp_path / "scans" / f"chukchi-{ref}.png")
    return tmp_path


class TestASuppliedSplitMapIsUsed:
    def test_it_matches_the_map_built_internally(self, repo, cfg):
        splits = zn.load_splits(repo)
        for ref in ("1-001", "1-002"):
            assert zn.validate_page(ref, repo, cfg, ink=False, splits=splits) == \
                zn.validate_page(ref, repo, cfg, ink=False)

    def test_the_split_column_still_reports_what_the_lists_say(self, repo, cfg):
        (repo / "gt" / "zones" / "_plate.lst").write_text(
            "chukchi-1-002.xml\n", encoding="utf-8")
        splits = zn.load_splits(repo)
        assert splits["1-002"] == "plate"
        assert zn.validate_page("1-002", repo, cfg, ink=False,
                                splits=splits)["split"] == "plate"

    def test_it_is_not_remembered_between_calls(self, repo, cfg):
        """A hoist, not a cache: a caller that does not pass one gets a fresh
        read, so a list written after the first render is seen by the second."""
        assert zn.validate_page("1-002", repo, cfg, ink=False)["split"] != "plate"
        (repo / "gt" / "zones" / "_plate.lst").write_text(
            "chukchi-1-002.xml\n", encoding="utf-8")
        assert zn.validate_page("1-002", repo, cfg, ink=False)["split"] == "plate"


class TestASuppliedInkCacheIsUsed:
    def _cache(self, repo: Path, ref: str, stamp) -> None:
        p = zn.zone_dir(repo) / zn.INK_CACHE_JSON
        p.write_text(json.dumps(
            {ref: {"state": "clean", "bands": 0, "ruled": 0, "stale": 0,
                   "note": "", "stamp": stamp}}), encoding="utf-8")

    def test_a_live_entry_reads_the_same_either_way(self, repo):
        self._cache(repo, "1-001", zn.ink_stamp("1-001", repo))
        cache = zn.load_ink_cache(repo)
        assert zn.cached_ink("1-001", repo, cache) == zn.cached_ink("1-001", repo)
        assert zn.cached_ink("1-001", repo, cache)["state"] == "clean"

    def test_a_stale_entry_is_still_refused_from_a_hoisted_cache(self, repo):
        """The property the hoist could have broken. The stamp is compared per
        ref against live mtimes, so passing the cache in hoists the read and
        never the verdict."""
        self._cache(repo, "1-001", [1, 1])          # a stamp from another era
        cache = zn.load_ink_cache(repo)
        assert zn.cached_ink("1-001", repo, cache) is None
        assert zn.cached_ink("1-001", repo) is None

    def test_a_page_absent_from_the_cache_is_unknown_either_way(self, repo):
        self._cache(repo, "1-001", zn.ink_stamp("1-001", repo))
        cache = zn.load_ink_cache(repo)
        assert zn.cached_ink("1-002", repo, cache) is None

    def test_an_empty_dict_is_not_taken_for_absent(self, repo):
        """`{}` is a cache holding nothing, `None` is no cache supplied. The
        distinction matters because the first must not silently re-read the
        file — that would put the per-row parse back without changing a line."""
        self._cache(repo, "1-001", zn.ink_stamp("1-001", repo))
        assert zn.cached_ink("1-001", repo, {}) is None
        assert zn.cached_ink("1-001", repo) is not None


class TestTheListItself:
    def test_it_reads_each_invariant_once(self, repo, cfg, monkeypatch):
        """Spying on the work, since the rendered rows are identical either way."""
        splits_built: list[int] = []
        cache_read: list[int] = []
        real_splits, real_cache = zn.load_splits, zn.load_ink_cache

        monkeypatch.setattr(zn, "load_splits",
                            lambda root=Path("."): (splits_built.append(1),
                                                    real_splits(root))[1])
        monkeypatch.setattr(zn, "load_ink_cache",
                            lambda root=Path("."): (cache_read.append(1),
                                                    real_cache(root))[1])

        from harness import zones_ui
        ctx = zones_ui.list_context(repo, cfg, scope="stores")
        assert len(ctx["rows"]) == 2, "fixture produced no rows"
        assert len(splits_built) == 1, f"built the split map {len(splits_built)}x"
        assert len(cache_read) == 1, f"read the ink cache {len(cache_read)}x"
