"""An imputed IPA string to a WAV, through espeak-ng's phoneme input.

Lifted from `scratch/chukchi/web/tts.py`, which was built against the Moll
dictionary and is the reason none of the decisions below are re-argued here.
What changed is the phoneme table: Bogoras's notation is a different inventory
from the 1957 Cyrillic, so the rows `ipa.RULES` can emit are what this maps.

A pure function of the string it is given: the same IPA always produces the
same bytes, nothing about the corpus is consulted, and no state survives a
call except the cache.

WHAT IS BEING SPOKEN, AND BY WHAT. Two guesses deep, and the button says so.
The IPA is this edition's own imputation from a keyed form (`ipa.py`), and
espeak-ng then reads those phonemes with no Chukchi voice behind it, because
there is none. It is a pronunciation sketch and is evidence of nothing.

WHY THE CLI AND NOT A BINDING. `espeak-ng-python`'s retrieval callback hands
back a `bytes` whose length equals the *sample* count where espeak's PCM is
16-bit, so reading it as int16 gives half the audio, misaligned -- a rattle,
not speech. `espeakng` is a subprocess wrapper with no `stdout=PIPE`, so no
path returns bytes, and it is GPLv3: invoking the espeak-ng *binary* as a
separate process is arm's length, `import`ing a GPLv3 module is not. The full
account, with the measurements, is `scratch/chukchi/web/README.md`.

WHY THE PHONEME TABLE IS OURS. `gruut-ipa` emits *correct Kirshenbaum* --
`s<lat>` for `ɬ` -- and espeak's `[[...]]` reads its own mnemonics instead; its
parser stops at the `<` and discards the rest of the word. Nothing raises; the
audio just ends early.

EVERY ROW CARRIES ITS OWN READBACK. espeak will say what it thinks a phoneme
string is -- `espeak-ng -v en -q --ipa "[[tS]]"` prints `tʃ` -- so `TABLE`
records that answer beside the mnemonic and `test_speech.py` compares the two
against the installed espeak. It is the check the Moll pass wanted and did not
have: `gruut-ipa`'s truncation was found by *timing the audio*, where asking
espeak to read its own string back shows the missing segments outright. Two
rows were caught by it here -- a bare `r` is the English approximant ɹ before
any vowel, and `r^` renders while swallowing whatever follows.
"""

from __future__ import annotations

import io
import shutil
import struct
import subprocess
import unicodedata
import wave
from functools import lru_cache

#: The system binary, driven as `espeak-ng --stdout`. Absent is a supported
#: state: the speaker buttons return 400 and everything else works.
ESPEAK = "espeak-ng"
#: Named rather than left implicit, because the voice decides how a phoneme is
#: realized -- a default would make the audio depend on how the host's espeak
#: was configured. It is the voice every row below was verified against.
VOICE = "en"
#: Words per minute, 80-500. espeak's own default is 175, a reading speed for a
#: language you already know; this is a pronunciation aid for one nobody here
#: speaks, so it is slower.
SPEED = 120
PITCH = 50        # 0-99
AMPLITUDE = 100   # 0-200
TIMEOUT = 10      # seconds, per synthesis
#: Pure function of the string, so the cache keys on the string alone.
CACHE = 256
#: A bound on how much one URL can ask for, not a security boundary. The
#: longest form in the corpus is far under it.
MAX_CHARS = 120

#: `Uweˊlen`. Synthesized by `probe`, so a broken install is reported rather
#: than discovered the first time someone presses a speaker.
PROBE = "uːweːleːn"

# --------------------------------------------------------------------------
# imputed IPA -> espeak-ng phoneme mnemonics
#
# Longest match wins, which is what makes the tie-barred affricates work:
# `t͡ɕ` has to beat `t͡ʃ`'s prefix and both have to beat `t`.

#: The frame every readback below was measured in, and the frame decides the
#: answer: a bare mnemonic is not what a word contains. `d;` reads back as
#: plain `d` in isolation and as `dʲ` only before a vowel, so the frame has to
#: carry one; and `n` between two `k`s assimilates to `ŋ`, so the leading side
#: has to be a stop and the trailing side must not. `k … aːk` is what asks the
#: question cleanly, and the final `k` is what a swallowed row loses.
FRAME_BEFORE = "k"
FRAME_AFTER = "a:k"

#: espeak's en voice inserts an English linking ɹ between a schwa and a
#: following vowel — `q@:u:` comes out `qəːɹuː`. Five forms in the corpus have
#: that shape, all of them the `-qäi`/`-qäu` ending, and a spurious English r
#: in the middle of a Chukchi word is exactly the plausible-sounding wrongness
#: this project is built against. `_` is a zero-length pause: it suppresses the
#: link and adds nothing audible. Nothing else in the table attracts one.
LINK_BREAK = "_"
_SCHWA = ("@", "@:")
_VOWEL_INITIAL = tuple("aeiouAEIOU@")

#: symbol -> (espeak mnemonic, what espeak reads that mnemonic back as inside
#: `FRAME`).
#:
#: **The second half is the witness, and it is in the table rather than in the
#: test on purpose.** espeak will say what it thinks a phoneme string is
#: (`spoken`), so each row records the answer it actually gave; the test
#: compares the table against the installed espeak instead of against a symbol
#: someone hoped it matched. Where the two halves differ the row is lossy or
#: merely notational, and the readback says which: `t͡ʃ` -> `tʃ` is espeak
#: writing the affricate without a tie bar, `ʉ̆` -> `u` is espeak's en voice
#: having neither a `ʉ` nor an extra-short.
TABLE: dict[str, tuple[str, str]] = {
    # -- affricates first: tie bar is U+0361, and the palatals are longer ---
    "t͡ɕ": ("tS;", "tɕ"),
    "d͡ʑ": ("dZ;", "dʑ"),
    "t͡ʃ": ("tS", "tʃ"),
    "d͡ʒ": ("dZ", "dʒ"),

    # -- diphthongs, before their first elements --------------------------
    # espeak writes the off-glide as a lax vowel where this edition writes it
    # non-syllabic; same two segments, two notations.
    "e̯iˀ": ("eI?", "eɪʔ"),   # the rising diphthong, always glottalized
    "ai̯": ("aI", "aɪ"),
    "ei̯": ("eI", "eɪ"),
    "ɔi̯": ("OI", "ɔɪ"),
    "au̯": ("aU", "aʊ"),

    # -- vowels -----------------------------------------------------------
    # The plain five are long in this notation, so the length is in the row.
    "aː": ("a:", "aː"),
    "eː": ("e:", "eː"),
    "iː": ("i:", "iː"),
    "uː": ("u:", "uː"),
    "ɔ": ("O", "ɔ"),
    "əː": ("@:", "əː"),
    "ɛː": ("E:", "ɛː"),
    "o̝ː": ("o:", "oː"),    # ɵ -- espeak has no raised o, so the raising is lost
    "ə": ("@", "ə"),       # ᴀ ᴇ ɪ, the obscure series, all one vowel
    "ʉ": ("u", "u"),       # ŭ -- espeak's en has no ʉ; nearest rounded high

    # -- consonants -------------------------------------------------------
    "ʔ": ("?", "ʔ"),
    "ɣ": ("Q", "ɣ"),
    "ŋ": ("N", "ŋ"),
    "q": ("q", "q"),
    "β": ("B", "β"),          # v is bilabial here, not labiodental
    "ɬʲ": ("l#", "ɬ"),        # ʟ -- espeak's Welsh `ll`; palatalization lost
    "ɮʲ": ("l", "l"),         # ʟ̣ -- no voiced lateral fricative in this voice
    "ɡ": ("g", "ɡ"),          # the p. 10 key's plain g, a loanword sort
    "dʲ": ("d;", "dʲ"),
    "tʲ": ("t;", "tʲ"),
    "nʲ": ("n;", "nʲ"),
    "sʲ": ("s", "s"),         # espeak's `s;` is ʂ in this voice, a different
                              # claim; the plain s drops the palatalization
    "xʲ": ("C", "ç"),         # the *ich* of the p. 10 key
    # `R` and not `r`. espeak's en voice reads a bare `r` as the English
    # approximant ɹ the moment a vowel follows it, which is most of the
    # corpus; in isolation it reads back as `r` and looks fine. `r^` is the
    # other near-miss and is worse: it renders, and swallows what comes after.
    "r": ("R", "r"),
    "r̪": ("R", "r"),         # ř -- the dental articulation is lost
    "ʃ": ("S", "ʃ"),
    "ʒ": ("Z", "ʒ"),
    "b": ("b", "b"), "d": ("d", "d"), "h": ("h", "h"), "j": ("j", "j"),
    "k": ("k", "k"), "l": ("l", "l"), "m": ("m", "m"), "n": ("n", "n"),
    "p": ("p", "p"), "s": ("s", "s"), "t": ("t", "t"), "w": ("w", "w"),
    "x": ("x", "x"),

    # -- aspiration on the preceding segment (`ipa.ASPIRATE`) --------------
    # **A lossy row, and deliberately the lossy direction.** espeak has no
    # aspiration diacritic, so this is a full `h` after the segment it belongs
    # to: `lʰ` comes out as l + h rather than as a voiceless l. That is what
    # Bogoras wrote — `lh`, `čh`, `th` — where dropping it would have the
    # speaker say a word the page does not spell.
    "ʰ": ("h", "h"),

    # -- standing length, from a macron over an already-long vowel ---------
    # espeak has no overlong, so this adds nothing audible and reads back as
    # nothing. Kept as a row anyway: dropping it would put the macron in
    # `to_espeak`'s dropped list, reporting a loss where the audio is the same.
    "ː": (":", "ː"),
}

# NFD both sides, for the reason `ipa.py` normalizes its own table: the corpus
# is NFD and a source file is whatever the keyboard emitted.
TABLE = {unicodedata.normalize("NFD", k):
         (m, unicodedata.normalize("NFD", said))
         for k, (m, said) in TABLE.items()}

#: The hot path wants only the mnemonic.
PHONEMES = {k: m for k, (m, _said) in TABLE.items()}

_KEYS_MAX = max(len(k) for k in PHONEMES)


class Unspeakable(ValueError):
    """The string is not something espeak can be asked to say."""


def to_espeak(ipa: str) -> tuple[str, list[str]]:
    """IPA to an espeak phoneme string, plus whatever was dropped.

    Anything not in the table is dropped rather than passed through. An
    imputation of a partial form carries the characters it could not resolve --
    `ipa.py` marks those forms partial -- so what arrives here can hold a
    diaeresis, a hyphen or a stray box. Passing them to espeak's phoneme parser
    is how a word gets truncated; dropping them speaks what is known.

    It is also what makes the subprocess call safe without quoting: the string
    handed to espeak is assembled only from values in `PHONEMES`, so nothing
    from the URL reaches the command line uninspected.
    """
    ipa = unicodedata.normalize("NFD", ipa)
    out: list[str] = []
    dropped: list[str] = []
    i = 0
    while i < len(ipa):
        for n in range(min(_KEYS_MAX, len(ipa) - i), 0, -1):
            if (key := ipa[i:i + n]) in PHONEMES:
                mnemonic = PHONEMES[key]
                if out and out[-1] in _SCHWA \
                        and mnemonic.startswith(_VOWEL_INITIAL):
                    out.append(LINK_BREAK)
                out.append(mnemonic)
                i += n
                break
        else:
            if not ipa[i].isspace():
                dropped.append(ipa[i])
            i += 1
    return "".join(out), dropped


def _riff_pcm(raw: bytes) -> tuple[bytes, int, int, int]:
    """The samples out of espeak's streaming WAV, with the format it declares.

    `--stdout` cannot know the length in advance, so it writes placeholder
    sizes -- the RIFF field comes out as 2147479588 and `wave` reads it as a
    48695-second file. The chunks are walked here and the data run is taken as
    "everything to EOF" rather than trusting the declared size.
    """
    if raw[:4] != b"RIFF" or raw[8:12] != b"WAVE":
        raise Unspeakable("espeak-ng did not return a WAV")
    channels = sampwidth = rate = None
    pos = 12
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack("<I", raw[pos + 4:pos + 8])[0]
        body = pos + 8
        if cid == b"fmt ":
            _fmt, channels, rate, _bps, _align, bits = struct.unpack(
                "<HHIIHH", raw[body:body + 16])
            sampwidth = bits // 8
        elif cid == b"data":
            data = raw[body:]
            if channels is None:
                raise Unspeakable("WAV had no fmt chunk before its data")
            usable = len(data) - len(data) % (channels * sampwidth)
            return data[:usable], channels, sampwidth, rate
        pos = body + size + (size & 1)
    raise Unspeakable("WAV had no data chunk")


@lru_cache(maxsize=CACHE)
def wav_for(ipa: str) -> bytes:
    """A complete RIFF/WAVE file for one imputed IPA string.

    Cached by the string, which is safe precisely because the function is
    pure. `lru_cache` is bounded, so a stream of distinct URLs evicts rather
    than growing.
    """
    ipa = ipa.strip().strip("/[]")
    if not ipa:
        raise Unspeakable("empty")
    if len(ipa) > MAX_CHARS:
        raise Unspeakable(f"longer than {MAX_CHARS} characters")

    phonemes, _dropped = to_espeak(ipa)
    if not phonemes:
        raise Unspeakable("nothing in it maps to a phoneme")

    exe = shutil.which(ESPEAK)
    if exe is None:
        raise Unspeakable(f"{ESPEAK} is not on PATH")
    # An argument list, never a shell string -- and `phonemes` is built from
    # the table, so nothing from the URL reaches the command line.
    cmd = [exe, "--stdout", "-v", VOICE, "-s", str(SPEED), "-p", str(PITCH),
           "-a", str(AMPLITUDE), f"[[{phonemes}]]"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT,
                              check=True)
    except subprocess.TimeoutExpired as exc:
        raise Unspeakable("espeak-ng timed out") from exc
    except subprocess.CalledProcessError as exc:
        raise Unspeakable(f"espeak-ng failed: {exc.stderr[:200]!r}") from exc

    pcm, channels, sampwidth, rate = _riff_pcm(proc.stdout)
    if not pcm:
        raise Unspeakable("espeak produced no audio")

    # Rewritten rather than passed through, so the file that reaches the
    # browser declares its real length instead of espeak's placeholder.
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def framed(mnemonic: str) -> str:
    """One mnemonic inside `FRAME`, ready to be read back.

    The link break goes in here too, so what the table's readback column
    records is the mnemonic under the same rule `to_espeak` applies rather than
    under a frame that happens to trigger a sandhi the real path suppresses.
    """
    link = LINK_BREAK if mnemonic in _SCHWA else ""
    return FRAME_BEFORE + mnemonic + link + FRAME_AFTER


def spoken(phonemes: str) -> str:
    """What espeak says a phoneme string is, in IPA. The round-trip witness.

    This is the check the Moll pass did not have and wanted: `gruut-ipa`'s
    truncation was found by timing the audio, where asking espeak to read its
    own phoneme string back would have shown the missing segments outright.
    """
    exe = shutil.which(ESPEAK)
    if exe is None:
        raise Unspeakable(f"{ESPEAK} is not on PATH")
    proc = subprocess.run(
        [exe, "-v", VOICE, "-q", "--ipa", f"[[{phonemes}]]"],
        capture_output=True, text=True, timeout=TIMEOUT, check=True)
    # espeak marks primary stress on a bare phoneme string; it is an artifact
    # of being asked to say one syllable, not part of the claim being checked.
    return unicodedata.normalize("NFD", proc.stdout.strip().replace("ˈ", ""))


def probe() -> str:
    """One line for a startup report. Synthesizes, so it also proves espeak-ng
    is installed and the phoneme path works."""
    try:
        data = wav_for(PROBE)
        w = wave.open(io.BytesIO(data))
        secs = w.getnframes() / w.getframerate()
    except Exception as exc:
        return f"unavailable — {type(exc).__name__}: {exc}"
    return (f"ok — {len(PHONEMES)} phonemes, {SPEED} wpm; /{PROBE}/ -> "
            f"{secs:.2f}s at {w.getframerate()} Hz, cache {CACHE}")
