"""The `mz/` provenance record: what it refuses, what it round-trips, what it
declines to guess.

The load-bearing assertion in this file is not that a producer serializes — it is
that a **legacy block reads back as `None`**. Everything the backfill claims
rests on it: if `read_producer` scraped `model:` out of the old free-text
description, the census would report every store fully witnessed before a single
file had been rewritten, the backfill would be indistinguishable from a no-op,
and the one instrument built to prove the change would have been the thing that
concealed it.
"""
from __future__ import annotations

import pytest
from lxml import etree

from harness import provenance as P
from harness.ns import ALTO_NS, TEI_NS

MODEL = {"step": "harness zones predict --decode dp",
         "label": "region segmentation", "kind": "model",
         "version": "kraken 7.0.3",
         "model": "models/bogoras-seg/zones-seg.safetensors",
         "sha256": "deadbeef", "device": "cuda:0"}


def test_a_model_producer_must_name_its_model_and_hash():
    """The refusal `zones.predict` already made for its own callers, moved to
    where every writer meets it. `sha256: ""` is provenance that is present,
    well-formed and says nothing — worse than absent, because it reads as
    recorded."""
    for missing in ("model", "sha256"):
        with pytest.raises(ValueError, match="cannot be told"):
            P.Producer(**{**MODEL, missing: None})


def test_a_rule_producer_must_not_carry_a_checkpoint():
    """The other direction, and the one `train score fig --model M` exploited: a rule
    that names a model is exactly the confusion `kind` exists to prevent."""
    with pytest.raises(ValueError, match="no model and no sha256"):
        P.Producer(step="harness fig propose", label="embedded-image placement",
                   kind="rule", version="harness 1", model="something.safetensors")


def test_an_unknown_kind_is_refused():
    with pytest.raises(ValueError, match="kind must be"):
        P.Producer(**{**MODEL, "kind": "guess"})


def test_the_record_round_trips_through_the_settings_string():
    """Including the inputs, and including a non-string input value: everything on
    the wire is text, so a record built with `paragraph_cuts=3` and the same record
    read back off disk must *be* the same record. Otherwise the obvious repair to a
    failing round-trip test is to weaken the comparison."""
    p = P.Producer(**MODEL, inputs={"raster": "scans/x.png", "paragraph_cuts": 3})
    assert P._decode(P._encode(p)) == p
    assert p.inputs["paragraph_cuts"] == "3"


def test_a_legacy_free_text_block_reads_as_unwitnessed():
    """**The assertion the backfill rests on.** These are the exact strings the
    six writers used before the record existed; not one may reconstruct."""
    for legacy in (
        "model: models/bogoras-seg/zones-seg.safetensors; sha256: ab; device: cpu",
        "models/bogoras-fig/fig-seg.safetensors sha256:abcd device:cuda:0",
        "data/pdf_images.json embedded-image placement",
        "region segmentation, harness zones predict --decode raw",
        "",
    ):
        assert P._decode(legacy) is None, f"{legacy!r} must not reconstruct"


def test_a_block_that_opens_with_the_marker_but_will_not_parse_is_unwitnessed():
    """Corrupt is not legacy, and the answer is the same either way. A
    half-parsed producer reported as present is the failure mode this module
    exists against."""
    assert P._decode("harness: 1; kind: model; step: x") is None
    assert P._decode("harness: 99; kind: rule; step: x; label: y; version: 1") is None


def test_a_value_holding_the_field_separator_is_refused_not_escaped():
    """It would parse back as two fields, and provenance that reads back wrong is
    worse than none. Refused at serialization, where it names the day the
    assumption stops holding."""
    p = P.Producer(**MODEL, inputs={"raster": "a; b"})
    with pytest.raises(ValueError, match="field separator"):
        p.settings()


def test_the_description_is_the_string_the_writers_already_wrote():
    """The six call sites are being replaced, and a description that changed
    shape would make every `mz/` file differ for a reason unrelated to the
    change. `label, step` reproduces all four of the prose ones exactly."""
    assert P.Producer(**MODEL).description == \
        "region segmentation, harness zones predict --decode dp"


def test_alto_and_kraken_paths_write_the_same_settings_string():
    """Two writers reach these stores — a hand-built tree and kraken's own ALTO
    template — and one parser has to serve both. kraken renders `settings` as
    `k: v` joined by '; '; `alto_processing` matches it field for field."""
    p = P.Producer(**MODEL)
    el = P.alto_processing(p)
    hand = el.find(f"{{{ALTO_NS}}}processingStepSettings").text
    assert hand == "; ".join(f"{k}: {v}" for k, v in p.settings().items())
    assert P._decode(hand) == p


def test_reading_an_alto_file_back(tmp_path):
    p = P.Producer(**MODEL)
    root = etree.Element(f"{{{ALTO_NS}}}alto")
    desc = etree.SubElement(root, f"{{{ALTO_NS}}}Description")
    desc.append(P.alto_processing(p))
    f = tmp_path / "page.xml"
    f.write_bytes(etree.tostring(root))
    assert P.read_producer(f) == p
    assert P.witnessed(f)


def test_two_producers_are_kept_and_the_last_one_wins(tmp_path):
    """`ocr predict` segments and then recognizes with two different models.
    Collapsing the pair would lose whichever a reader was not asking about;
    `read_producer` returns the recognizer because that is what shaped the text
    a consumer is holding."""
    seg = P.Producer(step="harness ocr predict", label="baseline segmentation",
                     kind="model", version="kraken 7.0.3", model="seg", sha256="a")
    rec = P.Producer(step="harness ocr predict", label="recognition",
                     kind="model", version="kraken 7.0.3", model="rec", sha256="b")
    root = etree.Element(f"{{{ALTO_NS}}}alto")
    desc = etree.SubElement(root, f"{{{ALTO_NS}}}Description")
    desc.append(P.alto_processing(seg, ident="OCR_1"))
    desc.append(P.alto_processing(rec, ident="OCR_2"))
    f = tmp_path / "page.xml"
    f.write_bytes(etree.tostring(root))
    assert P.read_producers(f) == [seg, rec]
    assert P.read_producer(f) == rec


def test_the_tei_appinfo_round_trips_and_uses_the_default_namespace(tmp_path):
    """`mz/tei/` recorded its producer as an XML comment, which no XPath reaches
    and no schema constrains. The element has to be readable by the same parser
    as the ALTO stores', and has to serialize without a generated prefix — it
    lands in a file people read."""
    p = P.Producer(step="harness tei generate", label="rule-built page",
                   kind="rule", version="5", inputs={"digest": "abc123"})
    xml = etree.tostring(P.tei_appinfo(p), encoding="unicode")
    assert "ns0:" not in xml
    f = tmp_path / "page.xml"
    f.write_text(f'<TEI xmlns="{TEI_NS}"><teiHeader><encodingDesc>{xml}'
                 f'</encodingDesc></teiHeader></TEI>')
    assert P.read_producer(f) == p


def test_the_tei_appinfo_validates_against_the_projects_own_schema(tmp_path):
    """`<label>` then `<p>`, which is TEI's content model for `application`. A
    `<note>` there does not validate, and the whole point of moving off a comment
    was to put the fact somewhere the schema constrains."""
    p = P.Producer(step="harness tei generate", label="rule-built page",
                   kind="rule", version="5", inputs={"digest": "abc123"})
    info = etree.tostring(P.tei_appinfo(p), encoding="unicode").replace(
        f' xmlns="{TEI_NS}"', "")
    doc = (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc>'
           "<titleStmt><title>t</title></titleStmt>"
           "<publicationStmt><p>p</p></publicationStmt>"
           "<sourceDesc><p>s</p></sourceDesc></fileDesc>"
           f"<encodingDesc>{info}</encodingDesc></teiHeader>"
           "<text><body><p>x</p></body></text></TEI>")
    rng = etree.RelaxNG(etree.parse("data/tei_all.rng"))
    assert rng.validate(etree.fromstring(doc.encode())), rng.error_log


def test_kraken_version_is_read_not_written_down():
    """`kraken.__version__` does not exist, so a `getattr(..., 'unknown')` reads
    `unknown` forever while looking like it works — which is the failure this
    module is against, and it turned up on the first call. From the installed
    distribution's metadata instead."""
    v = P.kraken_version()
    assert v.startswith("kraken ") and "unknown" not in v
    assert v.split()[1][0].isdigit()


def test_the_census_counts_a_legacy_file_as_unwitnessed(tmp_path):
    """The instrument, end to end. Before the backfill the old blocks must read
    unwitnessed, or the number cannot move and the backfill cannot be told from
    a no-op."""
    d = tmp_path / "mz" / "zones"
    d.mkdir(parents=True)
    root = etree.Element(f"{{{ALTO_NS}}}alto")
    desc = etree.SubElement(root, f"{{{ALTO_NS}}}Description")
    proc = etree.SubElement(desc, f"{{{ALTO_NS}}}Processing")
    etree.SubElement(proc, f"{{{ALTO_NS}}}processingStepSettings").text = \
        "model: m; sha256: a; device: cpu"
    (d / "chukchi-1-001.xml").write_bytes(etree.tostring(root))

    desc.append(P.alto_processing(P.Producer(**MODEL)))
    (d / "chukchi-1-002.xml").write_bytes(etree.tostring(root))

    row = next(r for r in P.census(tmp_path) if r["store"] == "mz/zones")
    assert (row["files"], row["witnessed"], row["unwitnessed"]) == (2, 1, 1)
    assert "harness zones predict --decode dp [model]" in row["producers"]


def test_the_census_reports_every_mz_store_even_when_absent(tmp_path):
    """A store this clone does not hold is a zero row, not a missing one — every
    `mz/` tree is derived and a fresh clone has none of them. A census that
    silently omitted them would read as a corpus with fewer stores."""
    rows = P.census(tmp_path)
    assert [r["store"] for r in rows] == [s for s, _ in P.MZ_STORES]
    assert all(r["files"] == 0 for r in rows)
