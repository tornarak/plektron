// One map per entity for its link preview — the composition is
// `static/js/geomap.js`'s and nowhere else, so the picture is that function's
// output and not a second drawing of it.
//
// **The entity alone, framed on what holds it.** The viewport is the extent of
// what it is `within`, given to `compose` as the one input that sets a frame
// without selecting anything: a declared `frame:` on a single subject. Selecting
// the parent instead would draw everything the parent holds, which a live pane
// can hide and a picture cannot. An entity's own declared frame still wins, and
// with no parent extent it keeps the frame it would get alone. The context
// layers `compose` adds around a single subject — its siblings, the tree's root
// outline — are left unpainted by the sheet (`mapshots._sheet`).
//
// stdin:  {"atlas": <atlas.json>, "shapes": {sid: geojson}, "ids": [ident, …]}
// stdout: {ident: svg}; an entity `compose` draws nothing for is left out.
import { compose } from './static/js/geomap.js';

const chunks = [];
for await (const c of process.stdin) chunks.push(c);
const { atlas, shapes, ids } = JSON.parse(Buffer.concat(chunks).toString('utf8'));
const E = atlas.entities;
const shape = sid => shapes[sid] || {};
const out = {};
for (const id of ids) {
  const rec = E[id];
  const up = rec && E[rec.parent];
  const framed = rec && !rec.frame && up && up.own
    ? { ...atlas, entities: { ...E, [id]: { ...rec, frame: up.own } } }
    : atlas;
  const svg = compose(framed, shape, [id]).svg;
  if (svg) out[id] = svg;
}
process.stdout.write(JSON.stringify(out));
