# Plektron

> καὶ ὥσπερ ὄργανον πρὸ ὀργάνων πᾶς ὑπηρέτης· εἰ γὰρ ἠδύνατο ἕκαστον τῶν
> ὀργάνων κελευσθὲν ἢ προαισθανόμενον ἀποτελεῖν τὸ αὑτοῦ ἔργον, ὥσπερ τὰ
> Δαιδάλου φασὶν ἢ τοὺς τοῦ Ἡφαίστου τρίποδας, οὕς φησιν ὁ ποιητὴς αὐτομάτους
> θεῖον δύεσθαι ἀγῶνα, οὕτως **αἱ κερκίδες ἐκέρκιζον αὐταὶ καὶ τὰ πλῆκτρα
> ἐκιθάριζεν**, οὐδὲν ἂν ἔδει οὔτε τοῖς ἀρχιτέκτοσιν ὑπηρετῶν οὔτε τοῖς
> δεσπόταις δούλων.
>
> [E]very one that can minister of himself is more valuable than any other instrument; for if every instrument, at command, or from a preconception of its master's will, could accomplish its work (as the story goes of the statues of Daedalus; or what the poet tells us of the tripods of Vulcan, "that they moved of their own accord into the assembly of the gods"), **the shuttle would then weave, and the [plectrum](https://en.wikipedia.org/wiki/Plectrum) itself strike the [kithara](https://en.wikipedia.org/wiki/Kithara)**; nor would the architect want servants, or the master slaves.
>
> — [Aristotle, *Politics* 1253b (trans. William Ellis, adapted)](https://www.gutenberg.org/cache/epub/6762/pg6762-images.html#link2HCH0004)

Annotated digital editions of public-domain ethnographies:
the text reproduced as printed,
with its entities -
people, places, rivers, species, institutions -
identified and cross-referenced, native-language forms indexed,
and the whole linked outward to modern databases, taxonomies, and gazetteers.

In order to produce

1. Quality editions of the originals that read, spread, and index well on the Web,
providing inline all necessary context for their comprehension.
2. Proof-of-concept for an LLM-curated ethnographic graph database of similar shape to [D-PLACE](https://d-place.org/).

I suspect (or at least hope) that the end-product will have at least as many AI consumers as the tooling.
My aim is to dignify the primary sources in a world of increasingly mediated and interpolated knowledge.

Targets: Web, EPUB. Print is a reach.

## Getting Started

Everything is driven by one console script, `harness`, run from the repo root:

```
uv sync
uv run harness corpus state
```

### AI-First

The `harness` was written from the ground up for use & maintenance by agentic AI.

Its core interfaces are textual in nature,
designed to minimize redundant tool-calls
and hallucination surface.
[TOON](https://toonformat.dev/) is the default output format for non-interactive terminals.

While every step of [the pipeline](#the-pipeline) can *technically* be worked by
your slow, fallible human hands, I do not expect such Stakhanovism of Normal People
in our Age of Technological Upheaval.

You are encouraged to ask your agent[s] to
explain to you the tools at your disposal,
carry out rote tasks,
and modify the pipeline to fit the demands of your current project.

The first editions produced by this `harness` were [selected for difficulty](#the-first-title),
and the resulting pipeline & precedents are
the product of a lot of careful thought, iteration, and optimization on my part;
but if you find them a Procrustean bed then by all means change things up.

## The Principle

ALL text that goes into an edition is given a **provenance**,
either as metadata within a file, or implicitly by its containing directory.

There are four provenance levels:

- `#mz`: Produced mechanically by a "dumb" algorithm (regex, lookup table, OCR, CNN). Untracked. Regenerated *ad libitum*. Not expected to be stable; usually expected to be idempotent.
- `#gt`: Produced by a machine (a "dumb" `#mz` algorithm or heavily-restricted LLM subagent) as a reproduction of the "ground truth" of an artifact, such as the text, figures, or paragraph boundaries of a page. Reviewed and ratified by a human with access to the artifact, through their CLI, coding agent, and/or `harness` web interfaces. Tracked. All changes gated by explicit overwrite flags. Expected to be stable, and to converge on a "right answer" with successive review passes.
- `#llm`: Produced by an LLM explicitly instructed by a human to furnish the relevant information.
- `#ed`: Produced (or individually promoted from `#llm`) by a human editor.

## The First Title

Waldemar Bogoras, **_The Chukchee_** —
Memoirs of the American Museum of Natural History XI / Jesup North Pacific Expedition VII,
Parts 1–3 (Brill, 1904/1907/1909),
~730 pages.
[Public domain](https://digitallibrary.amnh.org/items/91a87fd0-5989-4f79-b2ff-a939ef5533aa).

Bogoras first, because it needs no translation layer,
and is otherwise a brutal stress-test of every stage of the pipeline:
dense, idiosyncratic phonetic transcription of eight languages -
Chukchi, Koryak, Yupik, Lamut (Even), Itelmen, Chuvan, Yukaghir, Inupiat -
several extinct or thinly attested in modern databases;
obsolete binomials;
toponyms absent from modern maps;
and a subject region straddling the antimeridian at subpolar latitudes,
where most map projections and bounding-boxes malfunction.

A pipeline that survives Bogoras can survive anything.

The rest of Jesup (or at the very least
[Jochelson](https://digitallibrary.amnh.org/items/adc6d4e0-f978-4e88-80b4-00e1cb98aced),
[Boas](https://digitallibrary.amnh.org/items/188e9ba1-f563-44be-8737-53a00d654d50), and
[Swanton](https://digitallibrary.amnh.org/items/e9f6bc84-6d1e-4129-a30c-f2112d8c0b54))
should follow in short order.

## The Pipeline

1. Create project. Insert source document[s] into `pdfs/`
2. Extract images from PDF[s] into `scans/`. It is important that scans are the original resolution. Tooling for this is currently limited but your agent should be able to analyze and extract the pages with typical command-line tools. DJVU, PS, PDF-with-nontrivial-text-layer TBD.
3. Ask your agent to parse important metadata pages from the front matter, such as the table of contents, list of figures, bibliography, notes, et al.; these are often specific to the document so the format is quite permissive.
4. Configure your project's zone types and start annotating the pages in `harness zones edit`. The editor is designed to be fast and frictionless to use; please modify it if it becomes a burden! After ~100 representative pages are labelled you'll have enough data to [train a small neural network](.claude/skills/train-zones/SKILL.md) to classify the remainder. The resulting `#mz` drafts can be approved at a glance, with the push of a button. Figures are annotated and [recognized](.claude/skills/train-figures/SKILL.md) by an identical track.
5. Generate `#mz` OCR, patch segmenter lacunae with `harness ocr edit`, then [deploy swarms](.claude/skills/rebuild-groundtruth/SKILL.md) of [groundtruth-reader](.claude/agents/groundtruth-reader.md) agents to refine it into adjudicated `#gt`. Difficult lines will be flagged for manual review. As the swarms progress through the document they will build up an internal lexicon and base of domain-knowledge that allow them to make fewer and fewer mistakes as the pass progresses. This is the most stressful, tedious, token- and attention-demanding stage of the pipeline, but if done up to a high standard gets you ~80% of the edition for free.
6. Generate `#mz` TEI draft. You will probably want document-specific code to exploit the full structure of your meticulously-worked OCR from the last step (ex. setting footnotes and figures, auto-linking to sources or intra-document citations).
7. Populate the encyclopedia. Read the drafts in `harness edition serve`, taking note of the most frequent references to things that require context or explanation, such as obscure places or peoples or recondite historical events. Ask your agent to produce entities from the most disproportionately common content-words in the text as produced by `harness lexicon misses [--common N]`. We're not writing XML schemas here - outside of basic top-level coherence checks (unique names, non-circular parent-child relations) the encyclopedia is quite liberal in what it can represent. Perhaps its most important function is its table of aliases that are auto-linked in the text.
8. Collate the TEI. This is another document-dependent pass. Collation is usually about the ambiguities & idiosyncrasies of formatting that can only be reconciled by an agent with actual comprehension of the content.
9. TBD

## Documentation

[`CLAUDE.md`](CLAUDE.md) is the authoritative, agent-facing statement of the project's
invariants and the router to every other document — each fact has exactly one
home, and a test holds the routing table to that. Start there.

## Status

A working proof of concept, in motion. The raster, segmentation, recognition
and ground-truth stages are built and in daily use; the corpus is being read
end to end; TEI collation and the encyclopedic stores (entities, lexicon) are
the active front. Counts are deliberately absent from prose everywhere in this
repo — `harness corpus state` answers, and stays current.

## Rights

The source text is in the public domain. The scans derive from the AMNH's own
digitization of the Memoirs.
