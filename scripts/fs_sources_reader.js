// fs_sources_reader.js — batch reader for FamilySearch attached sources (Recipe-S).
//
// Paste this file's contents into a Claude in Chrome `javascript_tool` call on ANY
// familysearch.org page in the operator's signed-in tab, then call:
//
//     await fsSources(['XXXX-XXX', 'YYYY-YYY'])        // returns a one-line summary
//     // then read the results with get_page_text (the reader renders them into <main>)
//     fsSourcesShow(2)                                  // next page, when the summary says >1
//     fsSourcesCitation('XXXX-XXX', 'SRCID')            // full citation text for one source
//
// WHY ENDPOINTS AND NOT THE SOURCES TAB DOM (23 NOV 2026). The earlier batch reader
// loaded /tree/person/sources/{PID} in an offscreen iframe and split its innerText.
// It returned EMPTY lists for profiles that have sources, silently: an offscreen frame
// in a driven tab is a backgrounded document, FamilySearch does not mount the source
// list there (the same suppression that keeps the Research Help card from rendering),
// and an unrendered list splits into zero rows exactly as an empty one does. The page
// itself is built from two same-origin JSON calls, which this reader makes directly:
//
//   /service/tree/tf/person/{PID}/entityref?version=2   -> entityRefs[], value.type SOURCE -> source ids
//   /service/tree/links/sources/{ids}?readExternalData=true -> sources[] (title, citation,
//        event, uri.uri = the record link / "Web Page (Link to the Record)")
//
// No Detail View toggle is needed: the record link is a field, not a DOM attribute.
//
// THE INSTRUMENT CHECKS ITSELF. Every person is read against the profile card's own
// `sourceCount`; a mismatch is printed as COUNT MISMATCH, never as a thin profile. A
// sign-in redirect (non-JSON) or a 401/403 is an AUTH failure, and two in a row abort
// the batch: uniform failures are an instrument diagnosis first (CLAUDE.method.md,
// "A zero is a claim about the instrument").
//
// READ-ONLY. It issues GETs only and attaches nothing. Living profiles (card.living)
// are skipped and reported, never read.
//
// The suggested OWN / NAMED-IN / OTHER grouping compares the persona name in each
// title with the profile name. It is a SUGGESTION for the reader, not a ruling:
// identity is still the test (rule 8 limb (g)), and a same-name son reads as OWN.
// Policy screens (book, memorial, reference work, obituary, analysis artifact) are NOT
// re-implemented here; their single home is harvest_sources.py. The report ends with
// the distinct collection titles to pipe through `harvest_sources.py --screen-titles`.

window.fsSources = async function (pids, opts) {
  opts = opts || {};
  const delayMs = opts.delayMs == null ? 350 : opts.delayMs;
  const withHints = opts.hints == null ? true : !!opts.hints;
  const CHUNK = 40;
  const H = { headers: { accept: 'application/json' }, credentials: 'include' };
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  async function get(url) {
    const r = await fetch(url, H);
    if (r.status === 401 || r.status === 403) throw { auth: 'HTTP ' + r.status };
    if (r.status === 204) return null;
    if (!r.ok) throw { http: r.status };
    const ct = r.headers.get('content-type') || '';
    if (!ct.includes('json')) throw { auth: 'non-JSON response (sign-in redirect?)' };
    return r.json();
  }
  function slim(o) {
    const ev = o.event || {};
    return {
      id: o.id,
      title: o.title || '',
      citation: o.citation || '',
      sourceType: o.sourceType || '',
      recordType: (o.fsRecordType || '').replace('http://gedcomx.org/', ''),
      collectionId: ((o.fsCollectionUri || '').match(/collections\/(\d+)/) || [])[1] || '',
      uri: (o.uri && o.uri.uri) || '',
      event: { type: ev.factType || '', date: ev.displayDate || '', place: ev.eventPlace || '', year: ev.sortYear || '' },
      tombstoned: !!o.tombstoned,
    };
  }

  const out = { reader: 'fs_sources_reader v1', readAt: new Date().toISOString(), aborted: null, people: [] };
  let authFails = 0;
  for (const pid of pids) {
    const p = { pid, status: 'ok', sources: [], hints: [], rejectedHints: [] };
    try {
      const card = await get('/service/tree/tree-data/v8/person/' + pid + '/card');
      p.name = (card && card.name) || '';
      p.lifespan = (card && card.lifespan) || '';
      p.cardId = (card && card.id) || '';
      p.cardSourceCount = card ? card.sourceCount : null;
      if (card && card.living) { p.status = 'skipped-living'; out.people.push(p); continue; }
      if (card && card.deleted) p.status = 'deleted-profile';
      const er = await get('/service/tree/tf/person/' + pid + '/entityref?version=2');
      const refs = (er && er.entityRefs) || [];
      const ids = refs.filter((r) => r.value && r.value.type === 'SOURCE').map((r) => r.value.uri);
      p.rejectedHints = refs.filter((r) => r.value && r.value.type === 'REJECTED_SOURCE_HINT').map((r) => r.value.uri);
      p.refIds = ids.length;
      for (let i = 0; i < ids.length; i += CHUNK) {
        const s = await get('/service/tree/links/sources/' + ids.slice(i, i + CHUNK).join(',') + '?readExternalData=true');
        for (const o of (s && s.sources) || []) p.sources.push(slim(o));
        if (i + CHUNK < ids.length) await wait(delayMs);
      }
      const got = new Set(p.sources.map((s) => s.id));
      p.missingIds = ids.filter((id) => !got.has(id));
      if (p.cardSourceCount != null && p.cardSourceCount !== ids.length) p.status = 'COUNT MISMATCH';
      if (p.missingIds.length) p.status = 'COUNT MISMATCH';
      if (withHints) {
        const m = await get('/service/tree/tree-data/record-matches/' + pid + '/all?hintsOnLiving=true');
        p.hints = ((m && m.data && m.data.matches) || []).map((h) => ({
          collection: h.collectionTitle || '', name: h.personName || '',
          uri: h.recordUrl || '', score: h.score, events: (h.events || []).map((e) => [e.type, e.date, e.place].filter(Boolean).join(' ')).join('; '),
        }));
      }
      authFails = 0;
    } catch (e) {
      if (e && e.auth) { p.status = 'AUTH FAILURE: ' + e.auth; authFails += 1; }
      else if (e && e.http) p.status = 'HTTP ' + e.http;
      else p.status = 'ERROR: ' + String((e && e.message) || e);
    }
    out.people.push(p);
    if (authFails >= 2) { out.aborted = 'two consecutive auth failures: sign in to FamilySearch and re-run'; break; }
    await wait(delayMs);
  }
  window.__fsSources = out;
  window.__fsSourcesPages = fsSourcesPaginate(out);
  fsSourcesShow(1);
  const n = out.people.length;
  const bad = out.people.filter((p) => p.status !== 'ok').map((p) => p.pid + ' ' + p.status);
  return 'fs_sources_reader: ' + n + ' of ' + pids.length + ' read, ' +
    out.people.reduce((a, p) => a + p.sources.length, 0) + ' sources, ' +
    window.__fsSourcesPages.length + ' page(s); read with get_page_text' +
    (bad.length ? '; NOT OK: ' + bad.join(', ') : '') + (out.aborted ? '; ABORTED: ' + out.aborted : '');
};

// Group and render one person's sources as plain text.
//
// One RECORD attached several times is ONE line (deduplicated on its locator, with
// every attachment id kept), because the census counts records, not attachments.
// Persona names are matched loosely: same given name, surname within edit distance 2
// (Haydon / Hayden / Heiden). Loose on purpose, and only a suggestion.
window.fsSourcesFormat = function (p) {
  const fold = (s) => (s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[^a-z ]/g, ' ').replace(/\s+/g, ' ').trim();
  const lev = (a, b) => {
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++)
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return d[a.length][b.length];
  };
  const me = fold(p.name).split(' ');
  const given = me[0] || '', sur = me.length > 1 ? me[me.length - 1] : '';
  const isMe = (name) => {
    const w = fold(name).split(' ').filter((x) => x && !['sr', 'jr', 'sen', 'jun'].includes(x));
    if (!given || !w.length || w[0] !== given) return false;
    if (w.length === 1 || !sur) return true;
    return w.slice(1).some((x) => x[0] === sur[0] && lev(x, sur) <= 2);
  };
  const L = [];
  const cnt = (v) => (v == null ? '?' : v);
  L.push('=== ' + p.pid + '  ' + (p.name || '?') + ' (' + (p.lifespan || '') + ')  status: ' + p.status +
    '  card sourceCount ' + cnt(p.cardSourceCount) + ', refs ' + cnt(p.refIds) + ', read ' + p.sources.length +
    (p.cardId && p.cardId !== p.pid ? '  [card id ' + p.cardId + ': merged or forwarded?]' : ''));
  if (p.missingIds && p.missingIds.length) L.push('  MISSING source ids (in refs, not returned): ' + p.missingIds.join(','));
  const ORDER = ['OWN', 'NAMED-IN', 'OTHER PERSONA', 'NO PERSONA IN TITLE', 'NO RECORD LINK'];
  const NOTE = {
    'OWN': ' — persona matches the profile name: the person\'s own record, or a same-name relative',
    'NAMED-IN': ' — appears in a relative\'s record: limb (g) once identity is shown',
    'OTHER PERSONA': ' — another person\'s record: sibling/household (limb h), a child naming him (limb g), or misattached; read before citing',
    'NO PERSONA IN TITLE': ' — title names only a collection (typically an external host): open it to see whose record it is',
    'NO RECORD LINK': ' — books, trees, notes; fsSourcesCitation(pid, src) for the full text',
  };
  const groups = {};
  ORDER.forEach((k) => (groups[k] = new Map()));
  const titles = new Set();
  for (const s of p.sources) {
    const q = s.title.match(/^(.*?),?\s*"([^"]+)"\s*$/);
    let descr = q ? q[1].trim() : s.title, coll = q ? q[2] : '';
    if (!q) {
      const inThe = s.title.match(/^(.*?)\s+in the\s+(.*)$/i);
      if (inThe) { descr = inThe[1]; coll = inThe[2]; }
      else if (/;/.test(s.title)) { coll = s.title.split(';')[0].trim(); descr = s.title.split(';').slice(1).join(';').trim(); }
      else { coll = s.title; descr = ''; }
    }
    titles.add(coll);
    const loc = (s.uri.match(/ark:\/61903\/((?:1:1|3:1|3:2):[A-Z0-9-]+)/) || [])[1];
    const locator = loc ? 'fs:' + loc : (s.uri ? 'EXT ' + s.uri.split('?')[0] : '');
    const inEntry = descr.match(/^(.*?)\s+in entry for\s+(.*)$/i);
    const persona = inEntry ? inEntry[1] : descr.replace(/^entry for\s+/i, '');
    const people = inEntry ? [persona] : persona.split(/\s+and\s+/i);
    let g;
    if (!s.uri) g = 'NO RECORD LINK';
    else if (!descr) g = 'NO PERSONA IN TITLE';
    else if (people.some(isMe)) g = inEntry && !isMe(inEntry[2]) ? 'NAMED-IN' : 'OWN';
    else g = 'OTHER PERSONA';
    const key = locator || ('src:' + s.id);
    const ev = [s.event.year, s.event.type, s.event.place].filter(Boolean).join(' ');
    const m = groups[g];
    if (!m.has(key)) m.set(key, { line: '[' + (ev || 'no event') + '] ' + (descr ? descr + ' | ' : '') + '"' + coll + '"' + (locator ? ' | ' + locator : ''), srcs: [] });
    m.get(key).srcs.push(s.id + (s.tombstoned ? ' TOMBSTONED' : ''));
  }
  let records = 0;
  for (const k of ORDER) {
    const m = groups[k];
    if (!m.size) continue;
    L.push(' ' + k + ' (' + m.size + ')' + NOTE[k]);
    const rows = [...m.values()].map((r) => '  - ' + r.line + ' | src ' + r.srcs.join(',') + (r.srcs.length > 1 ? '  (attached ' + r.srcs.length + 'x: ONE record)' : ''));
    L.push(...rows.sort());
    records += m.size;
  }
  if (p.sources.length) L.push(' ' + p.sources.length + ' attachments = ' + records + ' distinct locators (all groups, before any policy screen)');
  if (p.rejectedHints && p.rejectedHints.length) L.push(' REJECTED HINTS (someone already ruled not-a-match): ' + p.rejectedHints.map((u) => u.replace(/.*ark:\/61903\//, 'fs:')).join(', '));
  if (p.hints && p.hints.length) {
    L.push(' UNATTACHED HINTS (' + p.hints.length + ') — candidates, not records; attaching is operator-gated:');
    for (const h of p.hints) L.push('  - ' + h.name + ' | "' + h.collection + '" | ' + h.events + ' | ' + (h.uri || '').replace(/.*ark:\/61903\//, 'fs:') + ' | score ' + h.score);
  }
  p.__titles = [...titles];
  return L.join('\n');
};

window.fsSourcesPaginate = function (out, maxChars) {
  maxChars = maxChars || 30000;
  const blocks = out.people.map(fsSourcesFormat);
  const titles = new Set();
  out.people.forEach((p) => (p.__titles || []).forEach((t) => titles.add(t)));
  blocks.push('=== DISTINCT COLLECTION TITLES (' + titles.size + ') — screen them, never by eye:\n' +
    '    python3 scripts/harvest_sources.py --screen-titles <<\'EOF\'\n' + [...titles].sort().join('\n') + '\nEOF');
  if (out.aborted) blocks.unshift('!!! ABORTED: ' + out.aborted);
  const pages = [];
  let cur = '';
  for (const b of blocks) {
    if (cur && cur.length + b.length > maxChars) { pages.push(cur); cur = ''; }
    cur += (cur ? '\n\n' : '') + b;
  }
  if (cur) pages.push(cur);
  return pages.map((t, i) => 'fs_sources_reader page ' + (i + 1) + ' of ' + pages.length + ' (read ' + out.readAt + ')\n\n' + t);
};

window.fsSourcesShow = function (k) {
  const pages = window.__fsSourcesPages || ['no results: run fsSources([...]) first'];
  const t = pages[Math.max(0, Math.min(pages.length, k || 1) - 1)];
  let el = document.getElementById('fs-sources-out');
  if (!el) {
    document.open();
    document.write('<!doctype html><title>fs_sources_reader</title><main><pre id="fs-sources-out"></pre></main>');
    document.close();
    el = document.getElementById('fs-sources-out');
  }
  el.textContent = t;
  return 'showing page ' + (k || 1) + ' of ' + pages.length;
};

window.fsSourcesCitation = function (pid, sid) {
  const p = ((window.__fsSources || {}).people || []).find((x) => x.pid === pid);
  const s = p && p.sources.find((x) => x.id === sid);
  return s ? (s.title + '\n' + s.citation.replace(/<[^>]+>/g, '')) : 'not found';
};

'fs_sources_reader loaded: await fsSources([PIDs])';
