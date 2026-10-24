/* `geomap.js`: the map composed in the page. `bun test harness/tests/js`.
 *
 * Inline fixtures: a few square shapes and hand-built atlas entries, in the
 * shape `edition_ui.atlas_data` emits. Whether that data is right is pytest's
 * question; these ask whether a selection is composed from it correctly. */
import {describe, expect, test} from 'bun:test';
import {Frame, PIN, compose, fixed, fmt, owned, paneHtml, project, render}
  from '../../web/static/js/geomap.js';

const square = (w, s, e, n) => ({type: 'FeatureCollection', features: [{
  type: 'Feature', properties: {},
  geometry: {type: 'Polygon', coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}}]});

const SHAPES = {
  'watershed:big': square(160, 60, 180, 70),
  'watershed:small': square(165, 62, 168, 64),
  'region:far': square(100, 40, 101, 41),
  'langarea:folk': square(170, 64, 175, 66),
};
const shape = sid => SHAPES[sid] || {};

function ent(id, over = {}) {
  return {canonical: id.split(':')[1], cls: id.split(':')[0], parent: '',
          ancestors: [], children: [], relatives: [], own: null, frame: null,
          shapes: [], points: [], refs: [], members: [], extents: [],
          basis: {kind: 'framed'}, absent: '', ...over};
}

/* river:big holds river:small and the village place:v; people:folk names
   place:v as its own; place:lost has nowhere at all. */
const ATLAS = {geo_classes: ['place', 'land', 'water', 'river'], entities: {
  'river:big': ent('river:big', {own: [160, 60, 180, 70], shapes: ['watershed:big'],
    children: ['place:v', 'river:small'], relatives: ['place:v', 'river:small'],
    members: [['river:small', 'watershed:small']],
    basis: {kind: 'shape', id: 'watershed:big', km2: '', source: 'x', more: 0}}),
  'river:small': ent('river:small', {own: [165, 62, 168, 64], shapes: ['watershed:small'],
    parent: 'river:big', ancestors: ['river:big'], relatives: ['river:big']}),
  'place:v': ent('place:v', {own: [171.5, 64.5, 172.5, 65.5], points: [[172, 65]],
    parent: 'river:big', ancestors: ['river:big'], relatives: ['river:big']}),
  'people:folk': ent('people:folk', {own: [171.5, 64.5, 172.5, 65.5], refs: ['place:v'],
    basis: {kind: 'transcluded', id: 'place:v', more: 0}}),
  'place:lost': ent('place:lost', {absent: 'sought and not found'}),
  'land:framed': ent('land:framed', {own: [160, 60, 180, 70], frame: [150, 55, 190, 75]}),
  /* A subgroup with nothing of its own, framed on its people's extent. */
  'people:whole': ent('people:whole', {own: [170, 64, 175, 66], shapes: ['langarea:folk'],
    children: ['people:sub']}),
  'people:sub': ent('people:sub', {own: [170, 64, 175, 66], parent: 'people:whole',
    basis: {kind: 'inherited', id: 'people:whole'}}),
}};

const vb = c => c.svg.match(/viewBox='([^']*)'/)[1].split(' ').map(Number);
const ents = c => new Set([...c.svg.matchAll(/data-ent='([^']*)'/g)].map(m => m[1]));
const flat = nodes => nodes.flatMap(n => [n, ...flat(n.children), ...flat(n.folded)]);

describe('the projection and the frame', () => {
  test('185 and −175 are one meridian', () => {
    const [a, b] = [project(185, 66, 176, 65), project(-175, 66, 176, 65)];
    expect(a[0]).toBeCloseTo(b[0], 12);
    expect(a[1]).toBeCloseTo(b[1], 12);
  });

  test('a lat/lon box projects to a rectangle', () => {
    const f = new Frame([128, 50.9, 192, 71.7]);
    expect(f.at(128, 50.9)[0]).toBeCloseTo(f.at(128, 71.7)[0], 9);
    expect(f.at(128, 50.9)[1]).toBeCloseTo(f.at(192, 50.9)[1], 9);
  });

  test('the viewBox takes the aspect of what it frames, SPAN on the longer side', () => {
    const wide = new Frame([100, 60, 200, 70]), tall = new Frame([176, 50, 178, 75]);
    expect(wide.width).toBe(1000);
    expect(wide.height).toBeLessThan(1000);
    expect(tall.height).toBe(1000);
    for (const [lon, lat] of [[150, 60], [200, 72], [165, 66]]) {
      const [x, y] = new Frame([150, 60, 200, 72]).at(lon, lat);
      expect(x >= -1 && x <= 1001 && y >= -1 && y <= 1001).toBe(true);
    }
  });

  test('a ring that cannot touch the frame is culled', () => {
    const f = new Frame([165, 62, 168, 64]);
    expect(f.paths(SHAPES['region:far'])).toEqual([]);
    expect(f.paths(SHAPES['watershed:small']).length).toBe(1);
  });

  test('numbers are written as Python wrote them: a tie rounds to even', () => {
    expect(fixed(0.25, 1)).toBe('0.2');
    expect(fixed(1.25, 1)).toBe('1.2');
    expect(fixed(0.75, 1)).toBe('0.8');
    expect(fixed(-0.25, 1)).toBe('-0.2');
    expect(fixed(0.15, 1)).toBe('0.1');      // not a tie: 0.1499999…
    expect(fixed(0.125, 2)).toBe('0.12');
    expect(fmt(-0.04)).toBe('0');
    expect(fmt(10.0)).toBe('10');
  });
});

describe('the picture', () => {
  const f = new Frame([150, 60, 200, 72]);

  test('a label is escaped and turns inward at the right edge', () => {
    const svg = render(f, {}, [[950, 500, '<script>', 'place:x'], [100, 500, 'V', 'place:v']]);
    expect(svg).not.toContain('<script>');
    expect(svg).toContain('&lt;script&gt;');
    expect(svg.match(/text-anchor='end'/g).length).toBe(1);
    expect(svg).toContain(`data-pin='${'{&quot;r&quot;: 0.012'}`);
    expect(PIN.flip).toBe(0.72);
  });

  test('a drawn path names its record and its kind, and the coastline neither', () => {
    const svg = render(f, {land: owned(['M0,0 L1,1']),
                           members: owned(['M0,0 L1,1'], 'river:small', 'watershed')});
    expect(svg).toContain("data-ent='river:small' data-kind='watershed'");
    expect(svg.match(/data-ent/g).length).toBe(1);
    expect(svg).not.toContain('px');
  });
});

describe('composition', () => {
  test('a basin is marked only when every live subject shape is a watershed', () => {
    expect(compose(ATLAS, shape, ['river:big']).svg).toContain("class='map basin'");
    const village = compose(ATLAS, shape, ['place:v']).svg;
    expect(village).toContain("<svg class='map'");    // no shapes at all: not vacuously a basin
  });

  test('the frame is the box of what is selected, not of what holds it', () => {
    const c = compose(ATLAS, shape, ['place:v']);
    expect(c.frames.own['place:v']).toBe(vb(c).map(v => fixed(v, 1)).join(' '));
  });

  test('a declared frame wins for a lone subject', () => {
    const c = compose(ATLAS, shape, ['land:framed']);
    expect(c.frames.order).toEqual(['land:framed']);
    expect(vb(c)[2]).toBeGreaterThan(Number(c.frames.own['land:framed'].split(' ')[2]));
  });

  test('hiding a subject tightens the frame, and it is still drawn', () => {
    const both = compose(ATLAS, shape, ['river:big', 'place:v']);
    const hid = compose(ATLAS, shape, ['river:big', 'place:v'], new Set(['river:big']));
    expect(vb(hid)[2]).toBeLessThan(vb(both)[2]);
    expect(ents(hid).has('river:big')).toBe(true);
    expect(flat(hid.tree).find(n => n.id === 'river:big').hidden).toBe(true);
  });

  test('a geo: member joins the selection, unless it was dropped', () => {
    const c = compose(ATLAS, shape, ['people:folk']);
    expect(c.subjects.map(s => s.id)).toEqual(['people:folk', 'place:v']);
    const d = compose(ATLAS, shape, ['people:folk'], new Set(), new Set(['place:v']));
    expect(d.subjects.map(s => s.id)).toEqual(['people:folk']);
  });

  test('only a chosen place gets a pin', () => {
    expect(compose(ATLAS, shape, ['river:big']).svg).not.toContain("class='pin'");
    expect(compose(ATLAS, shape, ['place:v']).svg).toContain("<circle class='pin' data-ent='place:v'");
  });

  test('the tree names what was drawn, and offers a chosen node its children', () => {
    const c = compose(ATLAS, shape, ['river:big']);
    expect(c.tree.map(n => n.id)).toEqual(['river:big']);
    const kids = c.tree[0];
    expect(kids.children.map(n => n.id)).toEqual(['river:small']);   // drawn: open
    expect(kids.folded.map(n => n.id)).toEqual(['place:v']);         // offered: folded
  });

  test('the tree ends at the common ancestor and a root climbs no further', () => {
    const c = compose(ATLAS, shape, ['river:small', 'place:v']);
    expect(c.tree.map(n => n.id)).toEqual(['river:big']);
    expect(c.parent.id).toBe('river:big');
    const solo = compose(ATLAS, shape, ['river:big']);
    expect(solo.parent).toBe(null);
  });

  test('a people sorts above the ground and is never folded', () => {
    const c = compose(ATLAS, shape, ['people:folk', 'river:big']);
    expect(c.tree[0].id).toBe('people:folk');
  });

  test('an inherited extent draws the outline it was inherited from, as context', () => {
    const c = compose(ATLAS, shape, ['people:sub']);
    const parent = c.svg.match(/<g class='parent'>.*?<\/g>/);
    expect(parent && parent[0]).toContain("data-ent='people:whole'");
    expect(c.svg).not.toContain("<g class='subject'>");   // a bound, not its boundary
    expect(c.tree.map(n => n.id)).toEqual(['people:whole']);
    expect(c.tree[0].children.map(n => n.id)).toEqual(['people:sub']);
    // Selected alongside, the people is a subject and is not drawn twice.
    const both = compose(ATLAS, shape, ['people:sub', 'people:whole']);
    expect(both.svg).not.toContain("<g class='parent'>");
  });

  test('a place with nowhere to put says so, and is still in the tree', () => {
    const c = compose(ATLAS, shape, ['place:lost']);
    expect(c.svg).toBe('');
    expect(c.drawn).toEqual([]);
    expect(c.tree.map(n => n.id)).toEqual(['place:lost']);
    expect(paneHtml(c, '/b')).toContain('Nothing to draw. ');
    expect(paneHtml(c, '/b')).toContain('sought and not found');
    expect(paneHtml(compose(ATLAS, shape, ['place:nobody']), '/b')).toContain('No entry for');
  });

  test('the pane links under the base and escapes what it is given', () => {
    const atlas = structuredClone(ATLAS);
    atlas.entities['place:v'].canonical = "V'<b>";
    const h = paneHtml(compose(atlas, shape, ['place:v']), '/b');
    expect(h).toContain("href='/b/entity/river:big'");
    expect(h).not.toContain('<b>');
    expect(h).toContain("data-sel='place:v'");
  });
});
