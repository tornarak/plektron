# land:kamchatka — Kamchatka

- status: ratified
- within: land:northeast-siberia
- area: region:kamchatka

## aliases

| form | lang | auto | note |
|---|---|---|---|
| Kamchatka | | yes | |

## gloss

**The entry is the region and the shape is the peninsula, and they are not the
same size.** `area: region:kamchatka` is Natural Earth's `KAMCHATKA PENINSULA`,
which stops at the isthmus; the book's Kamchatka reaches well north of it —
1-359's own section heading is "Northern Kamchatka and Adjacent Pacific Shore",
and Bogoras files Tiličiki, Olyutorka and the Olyutorsky capes under it.

So a dozen children sit outside their parent's polygon and `geo verify` says so:
[[river:pakhacha]] measures 0.0 against it, and [[place:cape-olutorsky]] 2.097°
outside. **Those rows are correct and are not defects.** Refiling the northern
half under [[land:northeast-siberia]] would make the geometry quiet at the cost
of contradicting the page, and inventing a boundary for "Kamchatka the region"
is the one thing this atlas refuses to do. The disagreement is the honest state:
one authored fact is the book's scope, the other is a source's polygon, and the
check names the pair rather than a culprit.

[[land:karaginsky-island]] and [[water:karaginsky-gulf]] used to be filed here
for the same reason and have been moved to where they actually are — an island
in its gulf, a gulf in its sea. Both still report, because Natural Earth's
marine polygons tile the ocean instead of nesting inside one another.
