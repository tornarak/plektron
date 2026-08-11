"""The phoneme table, checked against espeak rather than against an ear.

The Moll pass found `gruut-ipa`'s truncation by timing the audio, which is a
symptom. espeak will read a phoneme string back as IPA, so a row can be checked
against the thing it claims — and that is what runs here, over the whole table.
Skipped where espeak-ng is not installed, which is a supported state.
"""
from __future__ import annotations

import shutil
import wave
from io import BytesIO

import pytest

from harness import ipa, speech

espeak = pytest.mark.skipif(shutil.which(speech.ESPEAK) is None,
                            reason="espeak-ng is not installed")


@espeak
@pytest.mark.parametrize("symbol", sorted(speech.TABLE))
def test_every_row_still_reads_back_as_the_table_says(symbol):
    """The installed espeak against the readback recorded in the row.

    Not against the symbol: espeak writes `tʃ` where this edition writes
    `t͡ʃ`, and demanding identity would fail on notation while passing the
    rows that are actually lossy. The recorded readback distinguishes them —
    and pins the lossy ones too, so a row that quietly starts rendering
    something else fails here rather than in someone's ear.
    """
    mnemonic, expected = speech.TABLE[symbol]
    said = speech.spoken(speech.framed(mnemonic))
    assert said.startswith(speech.FRAME_BEFORE) and said.endswith("aːk"), \
        f"{symbol} swallowed the frame: {said!r}"
    assert said[len(speech.FRAME_BEFORE):-3] == expected


@espeak
def test_a_row_that_swallows_what_follows_it_is_caught():
    """The gruut failure in its general form — espeak's parser stopping
    mid-string, dropping the tail and raising nothing.

    `r^` is a real mnemonic that renders `r` and then eats the next phoneme,
    which is why `r` maps to `R`. Pinned as a live negative, because the frame
    assertion above is only load-bearing if something can actually trip it.
    """
    assert speech.spoken("kr^k") == "kr"


@espeak
def test_a_schwa_before_a_vowel_gets_no_english_linking_r():
    """`rɪteˊqäu` and four others put a schwa straight before a vowel, and
    espeak's en voice links them with an ɹ that belongs to English. The break
    is inserted by `to_espeak`, so this checks the real path rather than the
    frame."""
    phonemes, _ = speech.to_espeak(ipa.impute("rɪteˊqäu").ipa)
    assert speech.LINK_BREAK in phonemes
    assert "ɹ" not in speech.spoken(phonemes)


@espeak
def test_a_form_synthesizes_to_audible_audio():
    data = speech.wav_for(ipa.impute("Uweˊlen").ipa)
    w = wave.open(BytesIO(data))
    assert w.getnframes() / w.getframerate() > 0.2


def test_unmappable_characters_are_dropped_not_passed_through():
    """A partial imputation carries its unresolved characters, and they must
    not reach espeak's parser — passing one is how the rest of the word is
    lost."""
    phonemes, dropped = speech.to_espeak("nɔrdeːnskiːɔ̈ld")
    assert dropped == ["̈"]
    assert "̈" not in phonemes


def test_a_string_with_nothing_speakable_in_it_refuses():
    with pytest.raises(speech.Unspeakable):
        speech.wav_for("□□□")


def test_an_overlong_string_refuses_before_spawning_anything():
    with pytest.raises(speech.Unspeakable):
        speech.wav_for("a" * (speech.MAX_CHARS + 1))


@pytest.mark.parametrize("form", [r["form"] for r in ipa.rows(
    ["Uweˊlen", "Kavraˊlɪt", "Nɵˊɵkalɪt", "Luˊᵋren", "Telqäˊp", "Kuluˊči"])])
def test_every_complete_imputation_maps_to_phonemes(form):
    """Coverage in the direction that matters: a form the rule table resolved
    completely must also be one the phoneme table can say. A gap between the
    two would show as a card offering a speaker that returns nothing."""
    r = ipa.impute(form)
    assert r.complete
    phonemes, dropped = speech.to_espeak(r.ipa)
    assert phonemes and not dropped
