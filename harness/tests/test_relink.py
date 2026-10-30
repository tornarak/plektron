"""Rule-applied links added to a page that was already collated.

The asymmetry this closes: `validate` re-derives every `#mz` link a page *has*
and had nothing to say about the ones it lacks. A page is collated after it is
generated, so an entry ratified afterwards leaves its form sitting in plain text
— and from outside that is indistinguishable from a page whose text never
printed the form.
"""
from __future__ import annotations

from conftest import write_project
from test_entities import entry

from harness import entities, relink

HEAD = "<TEI><text><body>"
FOOT = "</body></text></TEI>"


def store(tmp_path, *, status="ratified", auto=True, form="Markova"):
    entry(tmp_path, "place:markovo", status=status, canonical="Markovo",
          aliases=[(form, auto)])
    return entities.load(tmp_path)


def test_a_form_in_plain_prose_is_linked(tmp_path):
    s = store(tmp_path)
    got, applied, _ = relink.relink(f"{HEAD}<p>He left Markova in June.</p>{FOOT}", s)
    assert ('<name type="toponym" ref="place:markovo" resp="#mz">Markova</name>'
            in got)
    assert applied == [{"form": "Markova", "id": "place:markovo"}]


def test_everything_the_rule_did_not_touch_comes_back_byte_identical(tmp_path):
    """A signed page's diff has to be exactly the links, or the one thing that
    must be reviewable is buried. That is why this rewrites the source text
    rather than round-tripping a parse tree, which would re-indent and re-quote
    the whole file."""
    s = store(tmp_path)
    src = (f'{HEAD}\n  <p rend="odd"   n=\'3\'>He left Markova in June.</p>\n'
           f"  <!-- a note with a > in it, and the word Markova -->\n{FOOT}")
    got, _a, _sk = relink.relink(src, s)
    assert got.replace(
        '<name type="toponym" ref="place:markovo" resp="#mz">', "").replace(
        "</name>", "") == src


def test_a_comment_is_not_page_text(tmp_path):
    """The generator writes prose into its comments, and one holds a `>`. A naive
    `<[^>]*>` ends the tag there and reads the rest of the comment as text, which
    would put an `<rs>` inside a comment — invisible, and invalid the moment
    anyone deleted the comment around it."""
    s = store(tmp_path)
    got, applied, _ = relink.relink(
        f"{HEAD}<p>x</p><!-- 3 > 2, and Markova is here -->{FOOT}", s)
    assert applied == []
    assert "<rs" not in got


def test_an_already_linked_form_is_left_alone(tmp_path):
    s = store(tmp_path)
    src = (f'{HEAD}<p><rs ref="place:markovo" resp="#mz">Markova</rs></p>{FOOT}')
    got, applied, _ = relink.relink(src, s)
    assert got == src and applied == []


def test_a_tier1_handle_is_enclosed_and_never_pierced(tmp_path):
    """A reference encloses a handle and never reaches inside it. That is an
    edit to the element's *markup*, and this module rewrites text — so it used
    to do nothing at all, and, worse, said nothing while doing it, in a module
    whose docstring promises every refusal is reported. A ratified entity whose
    only form on a page was Tier-1 therefore linked on regeneration and never on
    a page a collator had signed."""
    entry(tmp_path, "place:uelen", status="ratified", canonical="Uelen",
          aliases=[("Uelen", True)])
    s = entities.load(tmp_path)
    src = f'{HEAD}<p><foreign index="1">Uelen</foreign></p>{FOOT}'
    got, applied, _ = relink.relink(src, s)
    assert ('<name type="toponym" ref="place:uelen" resp="#mz">'
            '<foreign index="1">Uelen</foreign></name>') in got
    assert [a["id"] for a in applied] == ["place:uelen"]
    # The handle's own text is untouched — enclosed, not pierced.
    assert '<foreign index="1">Uelen</foreign>' in got


def test_the_innermost_handle_is_enclosed_and_not_its_wrapper(tmp_path):
    """`tei generate` writes `<term><rs><name>…</name></rs></term>`, and a page
    already collated has to end up with the same shape rather than a second,
    outer wrapping of the `<term>`.

    The reference stays an `<rs>` though the class is geographic: the span the
    page already marked `<name>` carries its own witness that a proper noun
    stands here, and a `#mz` `<name>` round it would restate that from the store
    where the two could disagree."""
    entry(tmp_path, "place:uelen", status="ratified", canonical="Uelen",
          aliases=[("Uelen", True)])
    s = entities.load(tmp_path)
    src = (f'{HEAD}<p><term xml:id="t1"><name xml:lang="ckt">Uelen</name>'
           f'</term></p>{FOOT}')
    got, _applied, _ = relink.relink(src, s)
    assert '<term xml:id="t1"><rs ref="place:uelen" resp="#mz">' \
        '<name xml:lang="ckt">Uelen</name></rs></term>' in got
    assert got.count("<rs ") == 1


def test_a_form_already_inside_a_ruled_name_is_not_linked_again(tmp_path):
    """The guard that had only ever needed to know about `<rs>`. Now that a
    geographic rule link is a `<name ref>`, a module still testing the tag alone
    would read this page as unlinked and wrap a second reference round the
    first."""
    s = store(tmp_path)
    src = (f'{HEAD}<p><name type="toponym" ref="place:markovo" resp="#mz">'
           f"Markova</name></p>{FOOT}")
    got, applied, _ = relink.relink(src, s)
    assert got == src and applied == []


def test_a_once_form_first_linked_as_a_name_is_spent(tmp_path):
    """The `once` count reads the links a page already has, and it has to see
    both tags. Blind to `<name ref>`, it would find the second occurrence with
    the first hidden inside one, read it as the first, and turn once per page
    into twice — on exactly the pages this module exists to fix."""
    s = store(tmp_path, auto="once")
    src = (f'{HEAD}<p><name type="toponym" ref="place:markovo" resp="#mz">'
           f"Markova</name> and then Markova again.</p>{FOOT}")
    got, applied, _ = relink.relink(src, s)
    assert got == src and applied == []


def test_a_bare_name_is_still_a_handle_a_reference_may_enclose(tmp_path):
    """A `<name>` *without* a `@ref` is a proper noun a collator marked, not a
    link — so it is still enclosed. Treating every `<name>` as a reference would
    have silently stopped relinking those pages."""
    entry(tmp_path, "place:uelen", status="ratified", canonical="Uelen",
          aliases=[("Uelen", True)])
    s = entities.load(tmp_path)
    src = f'{HEAD}<p><name xml:lang="ckt">Uelen</name></p>{FOOT}'
    got, applied, _ = relink.relink(src, s)
    assert '<rs ref="place:uelen" resp="#mz"><name xml:lang="ckt">Uelen' \
        "</name></rs>" in got
    assert [a["id"] for a in applied] == ["place:uelen"]


def test_a_handle_that_is_only_part_of_its_element_is_refused_with_a_row(tmp_path):
    """Enclosure is offered only where the element's whole content is the form.
    A hit spanning the handle and the words after it — "Kuluˊči Bay" — crosses
    an element boundary, and picking where such a span ends is
    `generate._entity_spans`' judgement, not this module's. Reported, not
    silently dropped."""
    entry(tmp_path, "place:uelen", status="ratified", canonical="Uelen",
          aliases=[("Uelen", True)])
    s = entities.load(tmp_path)
    src = f'{HEAD}<p><foreign index="1">Uelen and beyond</foreign></p>{FOOT}'
    got, applied, skipped = relink.relink(src, s)
    assert got == src and applied == []
    assert [k["form"] for k in skipped] == ["Uelen"]
    assert "whole content" in skipped[0]["why"]


def test_an_unratified_entry_is_not_applied(tmp_path):
    """The whole licence: a rule may only apply a ratified entry. Ratifying is
    what turns this on, which is why `entity ratify` is where it runs."""
    s = store(tmp_path, status="proposed")
    got, applied, _ = relink.relink(f"{HEAD}<p>Markova</p>{FOOT}", s)
    assert applied == [] and "<rs" not in got


def test_an_auto_no_alias_is_not_applied(tmp_path):
    s = store(tmp_path, auto=False)
    _got, applied, _ = relink.relink(f"{HEAD}<p>Markova</p>{FOOT}", s)
    assert applied == []


def test_a_once_alias_takes_the_first_occurrence_and_leaves_the_rest(tmp_path):
    s = store(tmp_path, auto="once")
    got, applied, _ = relink.relink(
        f"{HEAD}<p>Markova, and again Markova, and Markova.</p>{FOOT}", s)
    assert got.count(' ref="place:markovo"') == 1 and len(applied) == 1


def test_a_once_alias_counts_the_links_the_page_already_has(tmp_path):
    """**The trap this module is uniquely exposed to.** Everything else here works
    on unlinked text, because linked text is done. Counting a `once` form that
    way finds the second occurrence with the first hidden inside an `<rs>`, reads
    it as the first, and links it — turning once per page into twice, on exactly
    the pages this module exists to fix."""
    s = store(tmp_path, auto="once")
    src = (f'{HEAD}<p><rs ref="place:markovo" resp="#mz">Markova</rs> and '
           f"then Markova again.</p>{FOOT}")
    got, applied, _ = relink.relink(src, s)
    assert got == src and applied == []


def test_a_once_alias_sees_through_the_markup_of_an_existing_link(tmp_path):
    """The first occurrence may be a Tier-1 handle wrapped by the reference, which
    is what `tei generate` writes. The count is over what the element *says*, so
    the tags between do not hide it."""
    s = store(tmp_path, auto="once")
    src = (f'{HEAD}<p><rs ref="place:markovo" resp="#mz"><name>Markova</name>'
           f"</rs> and then Markova again.</p>{FOOT}")
    _got, applied, _ = relink.relink(src, s)
    assert applied == []


def test_nothing_outside_the_body_is_touched(tmp_path):
    """The header names the edition and its people; a title reading "Markova"
    is not a mention of the place."""
    s = store(tmp_path)
    src = f"<TEI><teiHeader><title>Markova</title></teiHeader>{HEAD}{FOOT}</TEI>"
    got, applied, _ = relink.relink(src, s)
    assert got == src and applied == []


def test_missing_is_the_worklist_and_writes_nothing(tmp_path):
    s = store(tmp_path)
    src = f"{HEAD}<p>Markova</p>{FOOT}"
    assert [r["form"] for r in relink.missing(src, s)] == ["Markova"]


def _page(root, ref, body):
    p = root / "tei" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/>'
                 f"<text><body>{body}</body></text></TEI>", encoding="utf-8")
    return p


def test_both_ways_of_ratifying_leave_the_corpus_in_one_state(tmp_path):
    """There are two: `harness entity ratify` and the click in the reading view.
    They were already two code paths for the status flip alone, so adding the
    page pass to one of them would have made the browser and the terminal
    disagree about what the corpus says — with nothing to notice it, since each
    is correct on its own terms."""
    from types import SimpleNamespace

    from harness import edition_ui
    from harness.cli import _entity

    def fresh(root):
        entry(root, "place:markovo", status="proposed", canonical="Markovo",
              aliases=[("Markova", True)])
        return _page(root, "1-021", "<p>He left Markova in June.</p>")

    cli_root = write_project(tmp_path / "cli")
    page = fresh(cli_root)
    _entity.run_ratify(SimpleNamespace(
        root=cli_root, idents=["place:markovo"], all=False, commit=True,
        json=False, toon=False, pager=False))
    by_cli = page.read_text(encoding="utf-8")

    web_root = write_project(tmp_path / "web")
    page = fresh(web_root)
    assert edition_ui._ratify("place:markovo", web_root)["ok"]
    by_web = page.read_text(encoding="utf-8")

    assert ('<name type="toponym" ref="place:markovo" resp="#mz">Markova</name>'
            in by_cli)
    assert by_cli == by_web


def test_a_report_only_ratify_writes_nothing(tmp_path):
    """"Report by default, `--commit` writes" has to hold on the disk and not
    only in the output: a run that wrote and then undid would leave the corpus
    edited if anything between the two raised."""
    from types import SimpleNamespace

    from harness.cli import _entity

    entry(tmp_path, "place:markovo", status="proposed", canonical="Markovo",
          aliases=[("Markova", True)])
    page = _page(tmp_path, "1-021", "<p>He left Markova in June.</p>")
    before = page.read_text(encoding="utf-8")
    _entity.run_ratify(SimpleNamespace(
        root=tmp_path, idents=["place:markovo"], all=False, commit=False,
        json=False, toon=False, pager=False))
    assert page.read_text(encoding="utf-8") == before


def test_the_endpoint_says_where_the_book_prints_it_and_not_only_what_it_linked(
        tmp_path):
    """`linked: []` was accurate and useless. `relink` runs over committed `tei/`
    alone, so an entry the collated pages do not print links nothing however
    often the book prints it — and the drafts, where a reader with `--drafts` is
    actually reading, went unmentioned. Three counts: what this act linked, what
    prints it at all, and the subset no rule has reached, which is the only one
    that names a command."""
    from harness import edition_ui

    entry(tmp_path, "place:markovo", status="proposed", canonical="Markovo",
          aliases=[("Markova", True)])
    _page(tmp_path, "1-021", "<p>nothing about it here.</p>")
    d = tmp_path / "mz" / "tei"
    d.mkdir(parents=True)
    (d / "chukchi-1-035.xml").write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body>'
        "<p>He left Markova in June.</p></body></text></TEI>", encoding="utf-8")

    got = edition_ui._ratify("place:markovo", tmp_path)
    assert got["ok"] and got["linked"] == [] and got["pages"] == []
    assert got["drafts"] == ["1-035"]
    # Still out of date, and reported as such rather than raising: the page has
    # no `gt/ocr/` to rebuild from, and ratifying an entry is not the act that
    # should fail because a derived file cannot be built.
    assert "<rs" not in (d / "chukchi-1-035.xml").read_text(encoding="utf-8")


def test_a_draft_is_regenerated_and_not_relinked(tmp_path, monkeypatch):
    """The distinction the two functions exist to keep. A draft carries the
    generator's own questions beside its text — "…, whose entry is still
    `proposed`" — so applying the link without answering the comment leaves a
    fresh `<rs>` next to a note saying no rule may write one. Two halves of one
    file contradicting each other, with neither marked as the stale one.
    `tei generate` rebuilds both from the same store in one pass."""
    from harness import relink as R

    entry(tmp_path, "place:markovo", status="ratified", canonical="Markovo",
          aliases=[("Markova", True)])
    d = tmp_path / "mz" / "tei"
    d.mkdir(parents=True)
    src = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body>'
           "<p>He left Markova in June.</p>"
           "<!-- entity candidate: 'Markova' — place:markovo, whose entry is "
           "still `proposed` -->"
           "</body></text></TEI>")
    (d / "chukchi-1-035.xml").write_text(src, encoding="utf-8")

    called = []
    monkeypatch.setattr("harness.generate.generate",
                        lambda ref, root=None, force=False: called.append(ref))
    assert R.refresh_drafts(tmp_path, entities.load(tmp_path),
                            ["place:markovo"]) == ["1-035"]
    assert called == ["1-035"]
    # Untouched by this function: the rebuild is the generator's, whole.
    assert (d / "chukchi-1-035.xml").read_text(encoding="utf-8") == src


def test_refresh_drafts_writes_nothing_when_asked_not_to(tmp_path, monkeypatch):
    from harness import relink as R

    entry(tmp_path, "place:markovo", status="ratified", canonical="Markovo",
          aliases=[("Markova", True)])
    d = tmp_path / "mz" / "tei"
    d.mkdir(parents=True)
    (d / "chukchi-1-035.xml").write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body>'
        "<p>Markova</p></body></text></TEI>", encoding="utf-8")
    called = []
    monkeypatch.setattr("harness.generate.generate",
                        lambda ref, root=None, force=False: called.append(ref))
    assert R.refresh_drafts(tmp_path, entities.load(tmp_path),
                            ["place:markovo"], write=False) == ["1-035"]
    assert called == []


# ---------------------------------- the other two verbs that move the licence

def _args(root, **kw):
    from types import SimpleNamespace

    return SimpleNamespace(root=root, json=False, toon=False, pager=False,
                           **{"commit": False, **kw})


def _alias(root, ident, form, **kw):
    from harness.cli import _entity

    _entity.run_alias(_args(root, ident=ident, form=form,
                            **{"lang": "", "auto": "yes", "note": "", **kw}))


def _draft(root, ref, body):
    p = root / "mz" / "tei" / f"chukchi-{ref}.xml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/>'
                 f"<text><body>{body}</body></text></TEI>", encoding="utf-8")
    return p


def test_an_auto_alias_on_a_ratified_entry_links_the_pages_it_licenses(tmp_path):
    """Ratifying is not the only act that widens what a rule may link. Adding a
    form at `auto: yes` to an entry already ratified is the same licensing
    event, and it used to reach no page at all — silently, since `validate` has
    nothing to say about a link a page *lacks*."""
    entry(tmp_path, "place:markovo", status="ratified", canonical="Markovo",
          aliases=[("Markova", True)])
    page = _page(tmp_path, "1-021", "<p>He left Markovo in June.</p>")
    _alias(tmp_path, "place:markovo", "Markovo", commit=True)
    assert ('<name type="toponym" ref="place:markovo" resp="#mz">Markovo</name>'
            in page.read_text(encoding="utf-8"))


def test_a_report_only_alias_writes_neither_the_entry_nor_a_page(tmp_path):
    p = entry(tmp_path, "place:markovo", status="ratified",
              canonical="Markovo", aliases=[("Markova", True)])
    page = _page(tmp_path, "1-021", "<p>He left Markovo in June.</p>")
    before = (p.read_text(encoding="utf-8"), page.read_text(encoding="utf-8"))
    _alias(tmp_path, "place:markovo", "Markovo")
    assert (p.read_text(encoding="utf-8"),
            page.read_text(encoding="utf-8")) == before


def test_an_alias_that_licenses_nothing_runs_no_pass(tmp_path, monkeypatch):
    """The trigger is `auto_forms`' answer, so a proposed entry — or a form two
    entities claim — leaves every page alone, and does it by asking the rule
    rather than by restating its three conditions."""
    from harness import relink as R

    entry(tmp_path, "place:markovo", status="proposed", canonical="Markovo",
          aliases=[("Markova", True)])
    _page(tmp_path, "1-021", "<p>He left Markovo in June.</p>")
    called = []
    monkeypatch.setattr(R, "apply_to_corpus",
                        lambda *a, **k: called.append(1) or ([], [], []))
    _alias(tmp_path, "place:markovo", "Markovo", commit=True)
    assert called == []


def test_an_auto_alias_regenerates_the_drafts_that_print_it(tmp_path,
                                                            monkeypatch):
    entry(tmp_path, "place:markovo", status="ratified", canonical="Markovo",
          aliases=[("Markova", True)])
    _draft(tmp_path, "1-035", "<p>He left Markovo in June.</p>")
    called = []
    monkeypatch.setattr("harness.generate.generate",
                        lambda ref, root=None, force=False: called.append(ref))
    _alias(tmp_path, "place:markovo", "Markovo", commit=True)
    assert called == ["1-035"]


def test_a_rename_rebuilds_the_drafts_holding_the_old_ref(tmp_path,
                                                          monkeypatch):
    """Naming them and stopping was a hand-off with no receiver: nothing ran the
    regeneration the `stale refs` table implied, so the drafts went on carrying
    a ref resolving to an identity that no longer existed."""
    from harness.cli import _entity

    entry(tmp_path, "place:markovo", status="ratified", canonical="Markovo")
    _draft(tmp_path, "1-035",
           '<p><rs ref="place:markovo" resp="#mz">Markova</rs></p>')
    called = []
    monkeypatch.setattr("harness.generate.generate",
                        lambda ref, root=None, force=False: called.append(ref))
    _entity.run_rename(_args(tmp_path, old="place:markovo", new="place:markovo-1",
                             canonical="", commit=True))
    assert called == ["1-035"]


def test_a_report_only_rename_rebuilds_nothing(tmp_path, monkeypatch):
    from harness.cli import _entity

    entry(tmp_path, "place:markovo", status="ratified", canonical="Markovo")
    _draft(tmp_path, "1-035",
           '<p><rs ref="place:markovo" resp="#mz">Markova</rs></p>')
    called = []
    monkeypatch.setattr("harness.generate.generate",
                        lambda ref, root=None, force=False: called.append(ref))
    _entity.run_rename(_args(tmp_path, old="place:markovo",
                             new="place:markovo-1", canonical=""))
    assert called == []


def test_a_draft_the_generator_will_not_build_does_not_fail_the_rename(
        tmp_path, monkeypatch):
    """Renaming is a judgement about the entity store; a draft whose ground
    truth was withdrawn is a fact about another one. The row says the page is
    still out of date."""
    from harness.cli import _entity
    from harness.generate import Unready

    entry(tmp_path, "place:markovo", status="ratified", canonical="Markovo")
    _draft(tmp_path, "1-035",
           '<p><rs ref="place:markovo" resp="#mz">Markova</rs></p>')

    def unready(ref, root=None, force=False):
        raise Unready(f"{ref}: no gt/ocr/")

    monkeypatch.setattr("harness.generate.generate", unready)
    _entity.run_rename(_args(tmp_path, old="place:markovo",
                             new="place:markovo-1", canonical="", commit=True))
    assert (tmp_path / "edition" / "entities" / "place" / "markovo-1.md").exists()


def test_an_alias_row_has_no_double_space_in_any_cell(tmp_path):
    """§2.9 reads two spaces as sentence spacing, so `|  |` is a normalizer
    error in a file that was written correctly by every other measure. The rule
    was applied to the language cell and not to the note, and an alias added
    without a note failed `corpus normalize` from the moment it was written —
    on a defect no rendering of the table shows."""
    p = entry(tmp_path, "place:markovo", status="ratified", canonical="Markovo")
    for form, kw in (("Markova", {"lang": "ckt", "auto": "yes", "note": ""}),
                     ("Markovskoye", {"lang": "", "auto": "no", "note": ""}),
                     ("Markovo", {"lang": "ru", "auto": "no", "note": "1-021"})):
        _alias(tmp_path, "place:markovo", form, commit=True, **kw)
    text = p.read_text(encoding="utf-8")
    assert "|  |" not in text
    assert "| Markova | ckt | yes | |" in text
    assert "| Markovskoye | | no | |" in text
    assert "| Markovo | ru | no | 1-021 |" in text
