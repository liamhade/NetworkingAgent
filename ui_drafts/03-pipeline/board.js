/* Pipeline board + list + drawer. Shared by results.html and running.html. */
(function () {
  const COLS = [
    { id: 'new', label: 'New', cls: 'ch-new', icon: 'spark' },
    { id: 'short', label: 'Shortlisted', cls: 'ch-short', icon: 'pin' },
    { id: 'done', label: 'Applied / Connected', cls: 'ch-done', icon: 'check' },
    { id: 'follow', label: 'Following up', cls: 'ch-follow', icon: 'clock', proposed: true }
  ];
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const fmtSal = s => s ? '$' + s.replace('-', '–') : '';

  const S = { view: 'board', filters: new Set(), type: 'all', sort: 'fit', collapsed: new Set(), items: {}, cos: [], arrive: new Set(), finding: new Set(), openKey: null, running: false };
  const root = () => document.getElementById('root');
  const colOf = it => it.follow ? 'follow' : it.done ? 'done' : it.pinned ? 'short' : 'new';

  function build() {
    S.cos = NA.COMPANIES.map((c, i) => {
      const co = Object.assign({ idx: i, key: 'c' + i, searched: true, vis: { lane: true, jobs: true, people: true } }, c);
      co.jobs = c.jobs.map((j, k) => mk(co, 'job', j, 'j' + k));
      co.people = c.people.map((p, k) => mk(co, 'person', p, 'p' + k));
      co.moreLeft = c.more.slice();
      return co;
    });
  }
  function mk(co, kind, d, id) {
    const it = {
      key: co.key + id + (S.items[co.key + id] ? 'x' : ''), kind, co, pinned: !!d.pinned, done: !!d.done, follow: !!d.follow,
      title: kind === 'job' ? d.title : d.name,
      meta: kind === 'job' ? [d.loc, fmtSal(d.sal)].filter(Boolean).join(' · ') : d.title,
      score: kind === 'job' ? d.score : null, alignment: d.alignment, url: d.url, msg: d.msg
    };
    S.items[it.key] = it; return it;
  }
  const visItems = co => [].concat(co.vis.jobs ? co.jobs : [], co.vis.people ? co.people : []);

  function fitPill(n, label) {
    const c = n >= 75 ? 'hi' : n >= 65 ? 'mid' : 'lo';
    return '<span class="fit ' + c + '" title="Fit score ' + n + ' out of 100">' + (label ? label + ' ' : '') + n + '</span>';
  }
  function passes(it) {
    if (S.type === 'jobs' && it.kind !== 'job') return false;
    if (S.type === 'people' && it.kind !== 'person') return false;
    if (S.filters.has('pinned') && !it.pinned) return false;
    if (S.filters.has('todo') && it.done) return false;
    if (S.filters.has('strong') && (it.kind === 'job' ? it.score : it.co.score) < 75) return false;
    return true;
  }
  function statusLabel(it) { return it.kind === 'job' ? 'applied' : 'connected'; }

  /* ---------- rendering ---------- */
  function cardHTML(it) {
    const on = it.done, lbl = statusLabel(it);
    return '<article class="card ' + it.kind + (on ? ' done-dim' : '') + (S.arrive.has(it.key) ? ' arrive' : '') + '" draggable="true" data-key="' + it.key + '">' +
      '<div class="card-top"><span class="ico ' + it.kind + '">' + ic(it.kind === 'job' ? 'briefcase' : 'user') + '</span><div>' +
      '<button class="card-title" data-act="open" data-key="' + it.key + '" data-fid="open:' + it.key + '">' + esc(it.title) + '</button>' +
      '<p class="card-meta" title="' + esc(it.meta) + '">' + esc(it.meta || 'Location not listed') + '</p></div></div>' +
      '<div class="card-foot">' + (it.kind === 'job' && it.score ? fitPill(it.score, 'Fit') : '') +
      (it.follow ? '<span class="tag-follow">Follow up</span>' : '') + '<span class="grow"></span>' +
      '<button class="st ' + it.kind + '" data-act="status" data-key="' + it.key + '" data-fid="status:' + it.key + '" aria-pressed="' + on + '" aria-label="' + (on ? 'Marked ' : 'Mark ') + lbl + ': ' + esc(it.title) + '">' +
      (on ? ic('check') + ' ' + lbl[0].toUpperCase() + lbl.slice(1) : 'Mark ' + lbl) + '</button>' +
      '<button class="pin" data-act="pin" data-key="' + it.key + '" data-fid="pin:' + it.key + '" aria-pressed="' + it.pinned + '" aria-label="Pin ' + esc(it.title) + '" title="Pin to shortlist">' + ic('pin') + '</button></div></article>';
  }
  function rowHTML(it) {
    const col = COLS.find(c => c.id === colOf(it));
    const on = it.done, lbl = statusLabel(it);
    return '<div class="row" data-key="' + it.key + '"><span class="ico ' + it.kind + '">' + ic(it.kind === 'job' ? 'briefcase' : 'user') + '</span><div style="min-width:0">' +
      '<button class="t" data-act="open" data-key="' + it.key + '" data-fid="open:' + it.key + '">' + esc(it.title) + '</button>' +
      '<div class="m">' + esc(it.meta) + '</div></div><div class="acts">' +
      (it.kind === 'job' && it.score ? fitPill(it.score, 'Fit') : '') +
      (col.id === 'done' ? '' : '<span class="pill ' + ({ new: 'p-alt', short: 'p-pinned', follow: 'p-conn' }[col.id]) + '">' + col.label + '</span>') +
      '<button class="st ' + it.kind + '" data-act="status" data-key="' + it.key + '" data-fid="status:' + it.key + '" aria-pressed="' + on + '">' + (on ? ic('check') + ' ' + lbl[0].toUpperCase() + lbl.slice(1) : 'Mark ' + lbl) + '</button>' +
      '<button class="pin" data-act="pin" data-key="' + it.key + '" data-fid="pin:' + it.key + '" aria-pressed="' + it.pinned + '" aria-label="Pin ' + esc(it.title) + '">' + ic('pin') + '</button></div></div>';
  }
  function laneHTML(co, n) {
    const col = S.collapsed.has(co.key);
    const all = visItems(co), shown = all.filter(passes);
    const jobs = co.jobs.length, ppl = co.people.length;
    const waiting = S.running && (!co.vis.jobs || !co.vis.people);
    let body;
    if (S.view === 'board') {
      body = '<div class="lane-grid">' + COLS.map(c => {
        const cards = shown.filter(it => colOf(it) === c.id);
        let inner = cards.map(cardHTML).join('');
        if (!cards.length && c.id === 'new' && waiting && !co.vis.jobs) inner = '<div class="skel"></div><div class="skel" style="opacity:.6"></div>';
        else if (!cards.length) inner = '<div class="empty" aria-hidden="true">' + (c.id === 'follow' ? 'Nothing to chase yet' : '—') + '</div>';
        return '<div class="cell" data-co="' + co.key + '" data-col="' + c.id + '" role="group" aria-label="' + esc(co.name) + ': ' + c.label + '">' + inner + '</div>';
      }).join('') + '</div>';
    } else {
      const j = shown.filter(i => i.kind === 'job'), p = shown.filter(i => i.kind === 'person');
      body = '<div class="rows">' + (j.length ? '<div class="row-group">Jobs</div>' + j.map(rowHTML).join('') : '') +
        (p.length ? '<div class="row-group">People</div>' + p.map(rowHTML).join('') : '') +
        (!shown.length ? '<div class="empty">' + (waiting ? 'Looking for openings…' : 'Nothing here matches the filters.') + '</div>' : '') + '</div>';
    }
    const busy = S.finding.has(co.key);
    return '<section class="lane' + (co.pinned ? ' pinned' : '') + (col ? ' collapsed' : '') + '" id="lane-' + co.key + '" aria-labelledby="h-' + co.key + '">' +
      '<div class="lane-head"><button class="lane-toggle" data-act="lane" data-key="' + co.key + '" data-fid="lane:' + co.key + '" aria-expanded="' + !col + '" aria-label="' + (col ? 'Expand ' : 'Collapse ') + esc(co.name) + '">' + ic('chev') + '</button>' +
      '<span class="rank" aria-label="Rank ' + (n + 1) + '">' + (n + 1) + '</span>' +
      '<div class="lane-title"><h2 id="h-' + co.key + '"><a href="' + co.url + '" target="_blank" rel="noopener">' + esc(co.name) + '</a>' + fitPill(co.score, 'Fit') + '</h2><p>' + esc(co.desc) + '</p></div>' +
      '<div class="lane-actions"><span class="pill p-job">' + ic('briefcase') + jobs + (jobs === 1 ? ' job' : ' jobs') + '</span><span class="pill p-person">' + ic('user') + ppl + (ppl === 1 ? ' person' : ' people') + '</span>' +
      '<button class="btn btn-ghost btn-sm" data-act="why-co" data-key="' + co.key + '" data-fid="why:' + co.key + '">Why it fits</button>' +
      '<button class="btn btn-ghost btn-sm" data-act="find" data-key="' + co.key + '" data-fid="find:' + co.key + '"' + (busy || S.running && !co.vis.people ? ' disabled' : '') + '>' +
      (busy ? ic('loader', 'spin') + ' Searching…' : ic('search') + ' Find more people') + '</button>' +
      '<button class="pin" data-act="pin-co" data-key="' + co.key + '" data-fid="pinco:' + co.key + '" aria-pressed="' + !!co.pinned + '" aria-label="Pin ' + esc(co.name) + '">' + ic('pin') + '</button></div></div>' +
      '<div class="lane-body">' + body + '</div></section>';
  }

  function render(opts) {
    opts = opts || {};
    const act = document.activeElement, fid = act && act.dataset ? act.dataset.fid : null;
    const cos = S.cos.filter(c => c.vis.lane);
    const sorted = cos.slice().sort((a, b) => S.sort === 'name' ? a.name.localeCompare(b.name) : S.sort === 'pinned' ? (b.pinned - a.pinned) || b.score - a.score : b.score - a.score);
    const all = [].concat.apply([], cos.map(visItems));
    const doneN = all.filter(i => i.done).length, pinN = all.filter(i => i.pinned).length;
    const shownAll = all.filter(passes);
    const count = id => shownAll.filter(i => colOf(i) === id).length;
    const jobsN = all.filter(i => i.kind === 'job').length, pplN = all.length - jobsN;
    const filt = (id, label) => '<button class="chip" data-act="filter" data-f="' + id + '" aria-pressed="' + S.filters.has(id) + '">' + label + '</button>';
    const typeBtn = (id, label) => '<button data-act="type" data-t="' + id + '" aria-pressed="' + (S.type === id) + '">' + label + '</button>';
    const visible = sorted.filter(co => !S.filters.size && S.type === 'all' ? true : visItems(co).some(passes));
    const html =
      '<div class="sticky"><div class="toolbar" role="toolbar" aria-label="Board controls">' +
      '<div class="progress" aria-live="polite"><span class="tnum">' + doneN + ' of ' + all.length + ' actions done</span><span class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="' + all.length + '" aria-valuenow="' + doneN + '"><i style="width:' + (all.length ? doneN / all.length * 100 : 0) + '%"></i></span></div>' +
      '<div class="filters" role="group" aria-label="Filters">' + filt('pinned', ic('pin') + ' Pinned ' + pinN) + filt('todo', 'To do') + filt('strong', 'Strong fit 75+') + '</div>' +
      '<div class="seg" role="group" aria-label="Show">' + typeBtn('all', 'All ' + all.length) + typeBtn('jobs', 'Jobs ' + jobsN) + typeBtn('people', 'People ' + pplN) + '</div>' +
      '<span class="grow"></span>' +
      '<label class="sr" for="sort">Sort companies</label><select class="sel" id="sort" data-act="sort"><option value="fit"' + (S.sort === 'fit' ? ' selected' : '') + '>Sort: Best fit</option><option value="pinned"' + (S.sort === 'pinned' ? ' selected' : '') + '>Sort: Pinned first</option><option value="name"' + (S.sort === 'name' ? ' selected' : '') + '>Sort: Name A–Z</option></select>' +
      '<div class="seg view" role="group" aria-label="View"><button data-act="view" data-v="board" aria-pressed="' + (S.view === 'board') + '">' + ic('board') + ' Board</button><button data-act="view" data-v="list" aria-pressed="' + (S.view === 'list') + '">' + ic('list') + ' List</button></div></div>' +
      (S.view === 'board' ? '<div class="col-heads" aria-hidden="true">' + COLS.map(c => '<div class="col-head ' + c.cls + '">' + ic(c.icon) + c.label + (c.proposed ? '<span class="prop" title="Proposed feature: needs a new status field">Proposed</span>' : '') + '<span class="n">' + count(c.id) + '</span></div>').join('') + '</div>' : '') +
      '</div>' +
      '<div class="board-scroll"><div class="board-inner board' + (S.dragging ? ' dragging' : '') + '" id="board">' +
      (visible.length ? visible.map(co => laneHTML(co, sorted.indexOf(co))).join('') :
        '<div class="wait">' + (S.running ? 'Waiting for the first companies to arrive…' : 'No cards match these filters. <button class="linkbtn" data-act="clear">Clear filters</button>') + '</div>') +
      '</div></div>';
    root().className = S.view === 'list' ? 'list-view' : '';
    root().innerHTML = html;
    S.arrive = new Set();
    if (fid) { const el = root().querySelector('[data-fid="' + fid + '"]'); if (el) el.focus({ preventScroll: true }); }
    document.dispatchEvent(new CustomEvent('na-render', { detail: { total: all.length, done: doneN, jobs: jobsN, people: pplN, companies: cos.length } }));
  }

  /* ---------- state changes ---------- */
  function setCol(it, col) {
    if (col === 'new') { it.pinned = false; it.done = false; it.follow = false; }
    if (col === 'short') { it.pinned = true; it.done = false; it.follow = false; }
    if (col === 'done') { it.done = true; it.follow = false; }
    if (col === 'follow') { it.done = true; it.follow = true; }
  }
  function toggleStatus(it) {
    it.done = !it.done; if (!it.done) it.follow = false;
    toast(it.done ? (it.kind === 'job' ? 'Marked applied: ' : 'Marked connected: ') + it.title : 'Status cleared');
  }
  function find(co) {
    S.finding.add(co.key); render();
    setTimeout(() => {
      S.finding.delete(co.key);
      const p = co.moreLeft.shift();
      if (p) { const it = mk(co, 'person', p, 'p' + (co.people.length + 9)); co.people.push(it); S.arrive.add(it.key); toast('Found ' + p.name + ' at ' + co.name + '. Added to New.'); }
      else toast('No more people found at ' + co.name + ' right now');
      render(); refreshDrawer();
    }, 1500);
  }

  /* ---------- drawer ---------- */
  let lastFocus = null;
  function drawerEl() { return document.getElementById('drawer'); }
  function open(key) {
    lastFocus = document.activeElement; S.openKey = key; refreshDrawer();
    drawerEl().classList.add('open'); document.getElementById('scrim-d').classList.add('open'); drawerEl().setAttribute('aria-hidden', 'false');
    drawerEl().querySelector('.d-x').focus();
  }
  function close() {
    drawerEl().classList.remove('open'); document.getElementById('scrim-d').classList.remove('open'); drawerEl().setAttribute('aria-hidden', 'true');
    S.openKey = null; if (lastFocus) lastFocus.focus({ preventScroll: true });
  }
  function refreshDrawer() {
    const k = S.openKey; if (!k) return;
    const d = drawerEl(); let h;
    if (k.indexOf('co:') === 0) {
      const co = S.cos.find(c => c.key === k.slice(3));
      h = head('company', co.name, co.desc, fitPill(co.score, 'Fit'), co.url, 'Open company page') +
        '<div class="d-body"><div class="d-meta"><span class="pill p-job">' + co.jobs.length + ' jobs</span><span class="pill p-person">' + co.people.length + ' people</span></div>' +
        '<div class="d-sec"><h3>Why it fits you</h3><p>' + esc(co.alignment) + '</p></div>' +
        '<div class="d-actions"><button class="btn btn-ghost" data-act="pin-co" data-key="' + co.key + '" aria-pressed="' + !!co.pinned + '">' + ic('pin', co.pinned ? 'fill' : '') + (co.pinned ? ' Pinned' : ' Pin company') + '</button>' +
        '<button class="btn btn-primary" data-act="find" data-key="' + co.key + '">' + ic('search') + ' Find more people</button></div></div>';
    } else {
      const it = S.items[k], isJob = it.kind === 'job', lbl = statusLabel(it), cur = colOf(it);
      h = head(it.kind, it.title, it.meta, isJob && it.score ? fitPill(it.score, 'Fit') : '', it.url, isJob ? 'View posting' : 'Open LinkedIn profile') +
        '<div class="d-body"><div class="d-meta"><span class="pill p-company">' + ic('building') + esc(it.co.name) + '</span>' + fitPill(it.co.score, 'Company fit') + '</div>' +
        '<div class="d-sec"><h3>' + (isJob ? 'Why it fits you' : 'Why connect') + '</h3><p>' + esc(it.alignment) + '</p></div>' +
        (isJob ? '' : '<div class="d-sec"><h3>Example LinkedIn message</h3><div class="msg" id="msgtxt">' + esc(it.msg || '') + '</div><div class="msg-foot"><span class="tnum">' + (it.msg || '').length + ' characters</span><span class="grow"></span>' +
          '<button class="btn btn-primary btn-sm" data-act="copy">' + ic('copy') + ' <span id="copylbl">Copy message</span></button></div></div>') +
        '<div class="d-sec"><h3>Status</h3><div class="d-actions"><button class="btn btn-ghost" data-act="status" data-key="' + it.key + '" aria-pressed="' + it.done + '" style="' + (it.done ? 'background:var(--applied-bg);border-color:var(--applied);color:var(--applied-ink)' : '') + '">' + ic('check') + (it.done ? ' ' + lbl[0].toUpperCase() + lbl.slice(1) : ' Mark ' + lbl) + '</button>' +
        '<button class="btn btn-ghost" data-act="pin" data-key="' + it.key + '" aria-pressed="' + it.pinned + '">' + ic('pin', it.pinned ? 'fill' : '') + (it.pinned ? ' Pinned' : ' Pin') + '</button></div></div>' +
        '<div class="d-sec"><h3>Move to column</h3><div class="moveto" role="group" aria-label="Move to column">' + COLS.map(c => '<button class="chip" data-act="moveto" data-key="' + it.key + '" data-col="' + c.id + '" aria-pressed="' + (cur === c.id) + '">' + c.label + (c.proposed ? ' (proposed)' : '') + '</button>').join('') + '</div></div></div>';
    }
    d.innerHTML = h;
  }
  function head(kind, title, meta, pill, url, linkLbl) {
    const label = { company: 'Company', job: 'Job', person: 'Person' }[kind];
    return '<div class="d-head"><span class="ico ' + kind + '" style="width:40px;height:40px">' + ic(kind === 'job' ? 'briefcase' : kind === 'person' ? 'user' : 'building', '') + '</span><div style="min-width:0"><p class="pill p-' + kind + '" style="margin-bottom:6px">' + label + '</p><h2 id="d-title">' + esc(title) + '</h2>' +
      '<p class="d-meta" style="margin-top:4px">' + esc(meta) + '</p><div style="display:flex;gap:8px;align-items:center;margin-top:8px">' + pill + '<a href="' + (url || '#') + '" target="_blank" rel="noopener" class="linkbtn">' + linkLbl + ' ↗</a></div></div>' +
      '<button class="d-x" aria-label="Close details">' + ic('x') + '</button></div>';
  }

  /* ---------- events ---------- */
  function init(opts) {
    opts = opts || {};
    S.running = !!opts.running;
    build();
    if (opts.running) S.cos.forEach(c => { c.vis = { lane: false, jobs: false, people: false }; });
    if (window.matchMedia('(max-width:820px)').matches) S.view = 'list';
    const r = root();
    r.addEventListener('click', e => {
      const t = e.target.closest('[data-act]');
      if (!t) { const card = e.target.closest('.card,.row'); if (card && !e.target.closest('a')) open(card.dataset.key); return; }
      act(t);
    });
    r.addEventListener('change', e => { if (e.target.dataset.act === 'sort') { S.sort = e.target.value; render(); } });
    r.addEventListener('dragstart', e => {
      const c = e.target.closest('.card'); if (!c) return;
      e.dataTransfer.setData('text/plain', c.dataset.key); e.dataTransfer.effectAllowed = 'move';
      c.classList.add('dragme'); document.getElementById('board').classList.add('dragging');
    });
    r.addEventListener('dragend', () => { document.getElementById('board').classList.remove('dragging'); r.querySelectorAll('.dragme,.over').forEach(x => x.classList.remove('dragme', 'over')); });
    r.addEventListener('dragover', e => { const c = e.target.closest('.cell'); if (c) { e.preventDefault(); r.querySelectorAll('.over').forEach(x => x !== c && x.classList.remove('over')); c.classList.add('over'); } });
    r.addEventListener('drop', e => {
      const c = e.target.closest('.cell'); if (!c) return; e.preventDefault();
      const it = S.items[e.dataTransfer.getData('text/plain')]; if (!it) return;
      if (it.co.key !== c.dataset.co) { toast('Cards can only move within their own company lane'); render(); return; }
      setCol(it, c.dataset.col); toast('Moved to ' + COLS.find(x => x.id === c.dataset.col).label); render(); refreshDrawer();
    });
    const d = drawerEl();
    d.addEventListener('click', e => {
      if (e.target.closest('.d-x')) return close();
      const t = e.target.closest('[data-act]'); if (t) act(t);
    });
    document.getElementById('scrim-d').addEventListener('click', close);
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && S.openKey) close();
      if (e.key === 'Tab' && S.openKey) {
        const f = d.querySelectorAll('button,a[href]'); if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    });
    const sm = document.getElementById('summary-toggle');
    if (sm) sm.onclick = () => { const p = document.getElementById('summary-p'); const c = p.classList.toggle('clamp'); sm.textContent = c ? 'Read more' : 'Show less'; sm.setAttribute('aria-expanded', !c); };
    document.querySelectorAll('[data-open]').forEach(b => b.onclick = () => open(b.dataset.open));
    render();
  }
  function act(t) {
    const a = t.dataset.act, k = t.dataset.key, it = k && S.items[k];
    if (a === 'open') open(k);
    else if (a === 'pin') { it.pinned = !it.pinned; if (!it.pinned && S.view === 'board' && !it.done) { } toast(it.pinned ? 'Pinned to Shortlisted' : 'Unpinned'); }
    else if (a === 'pin-co') { const co = S.cos.find(c => c.key === k); co.pinned = !co.pinned; toast(co.pinned ? co.name + ' pinned' : 'Unpinned'); }
    else if (a === 'status') toggleStatus(it);
    else if (a === 'moveto') { setCol(it, t.dataset.col); toast('Moved to ' + COLS.find(x => x.id === t.dataset.col).label); }
    else if (a === 'lane') { S.collapsed.has(k) ? S.collapsed.delete(k) : S.collapsed.add(k); }
    else if (a === 'why-co') return open('co:' + k);
    else if (a === 'find') return find(S.cos.find(c => c.key === k));
    else if (a === 'filter') { const f = t.dataset.f; S.filters.has(f) ? S.filters.delete(f) : S.filters.add(f); }
    else if (a === 'type') S.type = t.dataset.t;
    else if (a === 'view') S.view = t.dataset.v;
    else if (a === 'clear') { S.filters.clear(); S.type = 'all'; }
    else if (a === 'copy') {
      const txt = it ? it.msg : S.items[S.openKey].msg;
      const done = () => { const l = document.getElementById('copylbl'); l.textContent = 'Copied!'; toast('Message copied to clipboard'); setTimeout(() => { const x = document.getElementById('copylbl'); if (x) x.textContent = 'Copy message'; }, 1800); };
      (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(done, () => { const ta = document.createElement('textarea'); ta.value = txt; document.body.appendChild(ta); ta.select(); try { document.execCommand('copy'); } catch (e) { } ta.remove(); done(); });
      return;
    }
    else return;
    render(); refreshDrawer();
  }

  NA.board = { init, render, state: S, refreshDrawer, cos: () => S.cos };
})();
