/* Results workspace: company tree (default) or flat tabs, with a detail pane. State keyed by entity key. */
(function () {
  const { esc, icon } = CC, D = DATA, S = CC.state;
  const cos = D.companies, jobs = D.jobs, ppl = D.people;
  const mobile = window.matchMedia('(max-width:860px)');
  const $ = (id) => document.getElementById(id);
  const kindOf = k => k.startsWith('company') ? 'company' : k.startsWith('job') ? 'job' : 'person';
  const byKey = k => cos.concat(jobs, ppl).find(x => x.key === k);
  const coByName = n => cos.find(c => c.name === n);
  const kidsJ = c => jobs.filter(j => j.company === c.name).sort((a, b) => b.score - a.score);
  const kidsP = c => ppl.filter(p => p.company === c.name);
  const isPinned = k => !!S.pins[k];
  const isOn = x => !!(x.key.startsWith('job') ? S.applied[x.key] : S.connected[x.key]);
  const band = s => s >= 80 ? '' : s >= 70 ? 'mid' : 'low';
  const initials = n => n.split(' ').filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  const firstSentence = t => (t.match(/^.*?[.!?](\s|$)/) || [t])[0].trim();
  const nm = x => x.name || x.title;
  const plural = (n, w) => n + ' ' + w + (n === 1 ? '' : 's');
  const TABS = [['company', 'Companies', 'building'], ['job', 'Jobs', 'briefcase'], ['person', 'People', 'user']];

  const ui = {
    view: CC.ls.get('cnt-view') || 'tree', tab: 'company', sel: cos[0].key, focus: cos[0].key,
    open: new Set([cos[0].key]), chips: new Set(), sort: 'fit', q: '', summaryOpen: false,
    cardOpen: new Set(), finding: {}, extra: {}
  };
  document.body.dataset.density = CC.ls.get('cnt-density') || 'comfortable';

  /* ---------- filters ---------- */
  const CHIPS = [['pinned', 'Pinned'], ['todo', 'Not applied'], ['fresh', 'Not connected'], ['strong', 'Fit 75+']];
  const pk = (c) => kidsJ(c).concat(peopleOf(c));
  function peopleOf(c) { return kidsP(c).concat(ui.extra[c.key] || []); }
  const F = {
    pinned: { co: c => isPinned(c.key) || pk(c).some(k => isPinned(k.key)), kid: k => isPinned(k.key) },
    todo: { co: c => kidsJ(c).some(j => !S.applied[j.key]), kid: k => !k.key.startsWith('job') || !S.applied[k.key] },
    fresh: { co: c => peopleOf(c).length === 0 || peopleOf(c).some(p => !S.connected[p.key]), kid: k => !k.key.startsWith('person') || !S.connected[k.key] },
    strong: { co: c => c.score >= 75, kid: k => k.key.startsWith('person') || k.score >= 75 }
  };
  const active = () => [...ui.chips].map(k => F[k]);
  const qm = (s) => !ui.q || s.toLowerCase().includes(ui.q.toLowerCase());
  const kidMatch = (k, c) => qm(c.name) || qm(nm(k)) || qm(k.title || '') || qm(k.location || '');

  function sortedCompanies() {
    const arr = cos.slice();
    const s = ui.sort;
    arr.sort((a, b) => s === 'name' ? a.name.localeCompare(b.name) : s === 'jobs' ? kidsJ(b).length - kidsJ(a).length || b.score - a.score :
      s === 'pinned' ? (isPinned(b.key) - isPinned(a.key)) || b.score - a.score : b.score - a.score);
    return arr;
  }
  /* returns [{co, jobs, people}] after filters */
  function treeModel() {
    const fs = active(), out = [];
    sortedCompanies().forEach((c, i) => {
      const rank = cos.slice().sort((a, b) => b.score - a.score).indexOf(c) + 1;
      const kj = kidsJ(c).filter(k => fs.every(f => f.kid(k)) && kidMatch(k, c));
      const kp = peopleOf(c).filter(k => fs.every(f => f.kid(k)) && kidMatch(k, c));
      const coOk = fs.every(f => f.co(c)) && (qm(c.name) || kj.length || kp.length);
      if (!coOk) return;
      out.push({ co: c, rank, jobs: kj, people: kp });
    });
    return out;
  }
  function flatModel(t) {
    const fs = active();
    if (t === 'company') return treeModel().map(m => m.co);
    const src = t === 'job' ? jobs : ppl;
    return src.filter(k => fs.every(f => f.kid(k)) && kidMatch(k, coByName(k.company))).sort((a, b) => t === 'job' ? b.score - a.score : 0);
  }

  /* visible node list (in display order) */
  function visibleNodes() {
    if (ui.view === 'flat') return flatModel(ui.tab).map(x => ({ x, level: 1, kind: kindOf(x.key) }));
    const list = [], force = !!ui.q;
    treeModel().forEach(m => {
      list.push({ x: m.co, level: 1, kind: 'company', rank: m.rank, m });
      if (force || ui.open.has(m.co.key)) {
        m.jobs.forEach(j => list.push({ x: j, level: 2, kind: 'job', parent: m.co.key }));
        m.people.forEach(p => list.push({ x: p, level: 2, kind: 'person', parent: m.co.key }));
      }
    });
    return list;
  }

  /* ---------- header ---------- */
  function renderCtx() {
    const S0 = D.search, ap = jobs.filter(j => S.applied[j.key]).length, cn = ppl.filter(p => S.connected[p.key]).length;
    $('ctx').innerHTML =
      '<div class="crumbs"><a href="search.html">Search</a>' + icon('right') + '<span>Results</span></div>' +
      '<div class="ctx-row"><div style="min-width:0"><h1>' + esc(S0.title) + '</h1></div>' +
      '<div class="ctx-actions"><a class="btn sm" href="search.html">' + icon('edit') + 'Edit &amp; re-run</a></div></div>' +
      '<div class="ctx-mid"><div class="stats">' +
      '<div class="stat c-company"><b class="num">' + cos.length + '</b><span>companies</span></div>' +
      '<div class="stat c-job"><b class="num">' + jobs.length + '</b><span>jobs · ' + ap + ' applied</span></div>' +
      '<div class="stat c-person"><b class="num">' + ppl.length + '</b><span>people · ' + cn + ' connected</span></div></div>' +
      '<p class="summary' + (ui.summaryOpen ? '' : ' clamp') + '" id="sum">' + esc(S0.summary) + '</p></div>' +
      '<div class="ctx-sub"><span class="tag">' + icon('clock') + esc(S0.created) + '</span><span class="tag">' + esc(S0.location) + '</span><span class="tag">Boards: ' + esc(S0.boards.join(', ')) + '</span>' +
      '<button class="link-btn" id="sumBtn" aria-expanded="' + ui.summaryOpen + '">' + (ui.summaryOpen ? 'Show less' : 'Read full summary') + '</button></div>';
    $('sumBtn').onclick = () => { ui.summaryOpen = !ui.summaryOpen; renderCtx(); };
  }

  /* ---------- toolbar ---------- */
  function renderToolbar() {
    const tree = ui.view === 'tree';
    $('toolbar').innerHTML =
      '<div class="search-in">' + icon('search') + '<input id="q" placeholder="Filter by name, title, place" aria-label="Filter results" value="' + esc(ui.q) + '"><kbd>/</kbd></div>' +
      '<div class="seg" role="group" aria-label="View"><button data-view="tree" aria-pressed="' + tree + '" title="Company tree">' + icon('tree') + 'Tree</button>' +
      '<button data-view="flat" aria-pressed="' + !tree + '" title="Flat lists">' + icon('rows') + 'Flat</button></div>' +
      (tree ? '<button class="btn sm" id="expAll" aria-label="Expand all companies" title="Expand all (E)">' + icon('chevs') + '<span class="lbl-t">Expand all</span></button><button class="btn sm" id="colAll" aria-label="Collapse all companies" title="Collapse all (E)">' + icon('chevsin') + '<span class="lbl-t">Collapse all</span></button>' +
        '<label class="sr-only" for="sort">Sort companies</label><select class="sel" id="sort">' +
        [['fit', 'Sort: Fit'], ['name', 'Sort: Name'], ['jobs', 'Sort: Most jobs'], ['pinned', 'Sort: Pinned first']].map(o => '<option value="' + o[0] + '"' + (ui.sort === o[0] ? ' selected' : '') + '>' + o[1] + '</option>').join('') + '</select>'
        : '<div class="seg tabs-flat" role="tablist" aria-label="List">' + TABS.map(t => '<button role="tab" data-tab="' + t[0] + '" aria-selected="' + (ui.tab === t[0]) + '" class="c-' + t[0] + '">' + icon(t[2]) + t[1] + ' <span class="count num">' + flatModel(t[0]).length + '</span></button>').join('') + '</div>');
    const q = $('q'); q.oninput = () => { ui.q = q.value; renderList(); renderChips(); };
    $('toolbar').querySelectorAll('[data-view]').forEach(b => b.onclick = () => setView(b.dataset.view));
    $('toolbar').querySelectorAll('[data-tab]').forEach(b => b.onclick = () => { ui.tab = b.dataset.tab; const f = flatModel(ui.tab); ui.sel = f.length ? f[0].key : null; ui.focus = ui.sel; renderAll(); });
    if (tree) { $('expAll').onclick = () => expandAll(true); $('colAll').onclick = () => expandAll(false); $('sort').onchange = e => { ui.sort = e.target.value; renderList(); }; }
  }
  function setView(v) {
    if (ui.view === v) return; ui.view = v; CC.ls.set('cnt-view', v);
    const k = ui.sel && byKey(ui.sel);
    if (v === 'flat') { ui.tab = k ? kindOf(k.key) : 'company'; } else if (k && kindOf(k.key) !== 'company') { ui.open.add(coByName(k.company).key); }
    renderAll();
  }
  function expandAll(on) {
    if (on) cos.forEach(c => ui.open.add(c.key)); else { ui.open.clear(); const k = ui.sel && byKey(ui.sel); if (k && kindOf(k.key) !== 'company') { ui.sel = coByName(k.company).key; ui.focus = ui.sel; } }
    renderList(); renderDetail(); CC.toast(on ? 'Expanded all companies' : 'Collapsed all companies');
  }
  function renderChips() {
    $('chips').innerHTML = CHIPS.map(c => '<button class="fchip" data-chip="' + c[0] + '" aria-pressed="' + ui.chips.has(c[0]) + '">' + c[1] + '</button>').join('') +
      (ui.chips.size || ui.q ? '<button class="fchip clear" data-chip="__clear">Clear</button>' : '');
    $('chips').querySelectorAll('[data-chip]').forEach(b => b.onclick = () => {
      const k = b.dataset.chip; if (k === '__clear') { ui.chips.clear(); ui.q = ''; renderToolbar(); } else ui.chips.has(k) ? ui.chips.delete(k) : ui.chips.add(k);
      renderChips(); renderList();
    });
  }

  /* ---------- tree / list rows ---------- */
  const pinBtn = (x) => '<button class="icon-btn pin" tabindex="-1" data-act="pin" data-key="' + x.key + '" aria-pressed="' + isPinned(x.key) + '" aria-label="Pin ' + esc(nm(x)) + '" title="Pin">' + icon('pin') + '</button>';
  const stBtn = (x) => { const job = x.key.startsWith('job'), on = isOn(x), l = job ? 'Applied' : 'Connected';
    return '<button class="pill st ' + (job ? 's-applied' : 's-connected') + (on ? ' on' : ' off') + '" tabindex="-1" data-act="st" data-key="' + x.key + '" aria-pressed="' + on + '" aria-label="' + (job ? 'Applied to ' : 'Connected with ') + esc(nm(x)) + '">' + (on ? icon('check') : '') + l + '</button>'; };
  const meter = (s) => '<span class="fit"><b class="num">' + s + '</b><span class="meter ' + band(s) + '"><i style="width:' + s + '%"></i></span></span>';

  function nodeHTML(n, idx, total) {
    const x = n.x, k = n.kind, sel = ui.sel === x.key, pin = isPinned(x.key);
    const flat = ui.view === 'flat', hasKids = k === 'company' && !flat && (n.m ? (n.m.jobs.length + n.m.people.length) > 0 || (kidsJ(x).length + peopleOf(x).length) > 0 : false);
    const open = ui.q || ui.open.has(x.key);
    let lead, body, right;
    if (k === 'company') {
      const nj = kidsJ(x).length, np = peopleOf(x).length;
      lead = (flat ? '' : '<span class="tw' + (hasKids ? '' : ' none') + '" data-act="tog" data-key="' + x.key + '">' + (hasKids ? icon('right') : '') + '</span>') +
        (n.rank && !flat ? '<span class="rank num">' + n.rank + '</span>' : '') + '<span class="chip-icon c-company">' + icon('building') + '</span>';
      body = '<span class="n-title">' + esc(x.name) + '</span><span class="n-sub">' + esc(x.loc) + '</span>';
      right = '<span class="counts"><span class="cnt c-job" title="' + plural(nj, 'job') + '">' + icon('briefcase') + '<span class="num">' + nj + '</span></span><span class="cnt c-person" title="' + plural(np, 'person') + '">' + icon('user') + '<span class="num">' + np + '</span></span></span>' + meter(x.score) + pinBtn(x);
    } else if (k === 'job') {
      lead = '<span class="chip-icon c-job sm">' + icon('briefcase') + '</span>';
      body = '<span class="n-title">' + esc(x.title) + '</span><span class="n-sub">' + (flat ? esc(x.company) + ' · ' : '') + esc(x.salary || 'Salary not listed') + ' · ' + esc(x.location) + '</span>';
      right = '<span class="fit sm"><b class="num">' + x.score + '</b></span>' + stBtn(x) + pinBtn(x);
    } else {
      lead = '<span class="avatar c-person sm">' + esc(initials(x.name)) + '</span>';
      body = '<span class="n-title">' + esc(x.name) + '</span><span class="n-sub">' + (flat ? esc(x.company) + ' · ' : '') + esc(x.title || 'Title not listed') + '</span>';
      right = stBtn(x) + pinBtn(x);
    }
    return '<div class="node lvl' + n.level + (sel ? ' sel' : '') + (pin ? ' pinned' : '') + ' k-' + k + '" role="' + (flat ? 'option' : 'treeitem') + '" id="n-' + idx + '" data-key="' + x.key + '"' +
      ' tabindex="' + (ui.focus === x.key ? 0 : -1) + '" aria-selected="' + sel + '"' +
      (flat ? '' : ' aria-level="' + n.level + '"' + (k === 'company' && hasKids ? ' aria-expanded="' + !!open + '"' : '')) + '>' + lead +
      '<span class="n-text">' + body + '</span><span class="n-right">' + right + '</span></div>';
  }

  function renderList() {
    const nodes = visibleNodes();
    if (ui.sel && !nodes.some(n => n.x.key === ui.sel) && nodes.length && !ui.keepSel) { /* keep detail on the selection even when filtered out */ }
    if (!nodes.some(n => n.x.key === ui.focus)) ui.focus = nodes.some(n => n.x.key === ui.sel) ? ui.sel : (nodes[0] && nodes[0].x.key);
    const had = $('rows').contains(document.activeElement) && document.activeElement.classList.contains('node');
    const sc = $('listScroll').scrollTop;
    const flat = ui.view === 'flat';
    $('rows').innerHTML = nodes.length ?
      '<div class="tree" role="' + (flat ? 'listbox' : 'tree') + '" aria-label="' + (flat ? 'Flat list' : 'Companies with their jobs and people') + '" aria-multiselectable="false">' + nodes.map((n, i) => nodeHTML(n, i, nodes.length)).join('') + '</div>' :
      '<div class="empty"><h3>No matching ' + (flat ? TABS.find(t => t[0] === ui.tab)[1].toLowerCase() : 'companies') + '</h3><p>Nothing fits those filters. Try clearing them.</p><button class="btn sm" id="clr">Clear filters</button></div>';
    const c = $('clr'); if (c) c.onclick = () => { ui.chips.clear(); ui.q = ''; renderToolbar(); renderChips(); renderList(); };
    $('listScroll').scrollTop = sc;
    if (had) { const f = $('rows').querySelector('.node[tabindex="0"]'); f && f.focus({ preventScroll: true }); }
    const cc = treeModel().length;
    $('listFoot').innerHTML = (flat ? '<span>' + plural(nodes.length, TABS.find(t => t[0] === ui.tab)[1].slice(0, -1).replace('Compani', 'Company').replace('Peopl', 'Person')).replace('Companys', 'Companies').replace('Persons', 'People') + '</span>' : '<span>' + plural(cc, 'company').replace('companys', 'companies') + ' shown</span>') +
      '<span class="kb"><kbd>↑</kbd><kbd>↓</kbd> move' + (flat ? '' : ' <kbd>←</kbd><kbd>→</kbd> collapse / expand') + ' <kbd>P</kbd> pin <kbd>X</kbd> ' + (ui.view === 'tree' ? 'mark' : 'mark') + ' <kbd>E</kbd> ' + (flat ? 'view' : 'expand all') + '</span>';
    if (flat) { const t = $('toolbar').querySelectorAll('[data-tab] .count'); TABS.forEach((tb, i) => { if (t[i]) t[i].textContent = flatModel(tb[0]).length; }); }
  }

  /* ---------- detail ---------- */
  const factPill = (ic, t, c) => '<span class="tag">' + (ic ? icon(ic) : '') + esc(t) + '</span>';
  const ring = s => '<div class="ring-wrap"><div class="ring ' + band(s) + '" style="--p:' + s + '" role="img" aria-label="Fit ' + s + ' of 100"><span>' + s + '</span></div>Fit</div>';
  const pinAct = x => '<button class="btn ' + (isPinned(x.key) ? 'on s-pinned' : '') + '" data-act="pin" data-key="' + x.key + '" aria-pressed="' + isPinned(x.key) + '">' + icon('pin') + (isPinned(x.key) ? 'Pinned' : 'Pin') + '</button>';
  const stAct = x => { const job = x.key.startsWith('job'), on = isOn(x);
    return '<button class="btn ' + (on ? 'on ' + (job ? 's-applied' : 's-connected') : '') + '" data-act="st" data-key="' + x.key + '" aria-pressed="' + on + '">' + icon('check') + (job ? (on ? 'Applied' : 'Mark applied') : (on ? 'Connected' : 'Mark connected')) + '</button>'; };

  function jobCard(j) {
    const open = ui.cardOpen.has(j.key);
    return '<article class="mc c-job' + (ui.sel === j.key ? ' cur' : '') + '"><div class="mc-h"><button class="mc-t" data-sel="' + j.key + '"><span class="mc-n">' + esc(j.title) + '</span><span class="mc-s">' + esc(j.salary || 'Salary not listed') + ' · ' + esc(j.location) + '</span></button>' +
      '<span class="fit sm"><b class="num">' + j.score + '</b></span>' + pinBtnD(j) + '</div>' +
      '<div class="mc-f">' + stBtn2(j) + '<button class="link-btn" data-act="card" data-key="' + j.key + '" aria-expanded="' + open + '">' + (open ? 'Hide why' : 'Why it fits') + '</button></div>' +
      (open ? '<p class="mc-b">' + esc(j.alignment) + '</p>' : '') + '</article>';
  }
  function personCard(p) {
    const open = ui.cardOpen.has(p.key);
    return '<article class="mc c-person' + (ui.sel === p.key ? ' cur' : '') + '"><div class="mc-h"><span class="avatar sm">' + esc(initials(p.name)) + '</span><button class="mc-t" data-sel="' + p.key + '"><span class="mc-n">' + esc(p.name) + '</span><span class="mc-s">' + esc(p.title || 'Title not listed') + '</span></button>' + pinBtnD(p) + '</div>' +
      '<div class="mc-f">' + stBtn2(p) + '<button class="link-btn" data-act="card" data-key="' + p.key + '" aria-expanded="' + open + '">' + (open ? 'Hide why' : 'Why connect') + '</button></div>' +
      (open ? '<p class="mc-b">' + esc(p.alignment) + '</p>' : '') + '</article>';
  }
  const pinBtnD = x => '<button class="icon-btn pin" data-act="pin" data-key="' + x.key + '" aria-pressed="' + isPinned(x.key) + '" aria-label="Pin ' + esc(nm(x)) + '">' + icon('pin') + '</button>';
  const stBtn2 = x => { const job = x.key.startsWith('job'), on = isOn(x);
    return '<button class="pill st ' + (job ? 's-applied' : 's-connected') + (on ? ' on' : ' off') + '" data-act="st" data-key="' + x.key + '" aria-pressed="' + on + '" aria-label="' + (job ? 'Applied to ' : 'Connected with ') + esc(nm(x)) + '">' + (on ? icon('check') : '') + (job ? 'Applied' : 'Connected') + '</button>'; };

  function findBox(c) {
    const f = ui.finding[c.key], np = peopleOf(c).length;
    if (f === 'loading') return '<div class="find-box">' + icon('loader', 'spin') + ' Searching LinkedIn for people at ' + esc(c.name) + '...</div>';
    if (f === 'error') return '<div class="find-box err"><p>Could not reach LinkedIn. Nothing was lost.</p><button class="btn sm" data-act="find" data-key="' + c.key + '">' + icon('refresh') + 'Retry</button></div>';
    return '<div class="find-box"><p>' + (np ? 'Want more names?' : 'No current employees found yet.') + '</p><button class="btn sm" data-act="find" data-key="' + c.key + '">' + icon('search') + (np ? 'Find more people' : 'Find people to connect with') + '</button></div>';
  }

  function renderDetail(keepScroll) {
    const el = $('detail'), x = ui.sel && byKey(ui.sel), sc = keepScroll ? el.scrollTop : 0;
    if (!x) { el.innerHTML = '<div class="d-inner"><div class="empty"><h3>Nothing selected</h3><p>Pick a company, job or person.</p></div></div>'; return; }
    const k = kindOf(x.key), back = '<button class="btn sm d-back" data-act="back">' + icon('back') + 'Back to list</button>';
    let h = '';
    if (k === 'company') {
      const js = kidsJ(x), ps = peopleOf(x);
      h = back + '<div class="d-grid"><div><div class="d-head"><span class="chip-icon lg c-company">' + icon('building') + '</span><div><div class="d-kind c-company">Company · rank ' + (cos.slice().sort((a, b) => b.score - a.score).indexOf(x) + 1) + ' of ' + cos.length + '</div>' +
        '<h2><a href="' + esc(x.url) + '" target="_blank" rel="noopener">' + esc(x.name) + '</a></h2><div class="d-sub">' + esc(x.description) + '</div></div></div>' +
        '<div class="d-facts">' + factPill('', x.loc) + factPill('briefcase', plural(js.length, 'job')) + factPill('user', plural(ps.length, 'contact')) + '</div>' +
        '<div class="d-actions">' + pinAct(x) + '<a class="btn" href="' + esc(x.url) + '" target="_blank" rel="noopener">' + icon('external') + 'Company page</a></div></div>' + ring(x.score) + '</div>' +
        '<div class="panel why"><div class="panel-h">' + icon('sparkle') + 'Why this company fits you</div><div class="panel-b">' + esc(x.alignment) + '</div></div>' +
        '<div class="two"><section aria-label="Jobs"><div class="sec-h c-job"><h3>' + icon('briefcase') + 'Jobs <span class="n num">' + js.length + '</span></h3></div>' +
        (js.length ? js.map(jobCard).join('') : '<div class="find-box"><p>No open roles found for ' + esc(x.name) + ' in this search.</p></div>') + '</section>' +
        '<section aria-label="People"><div class="sec-h c-person"><h3>' + icon('user') + 'People <span class="n num">' + ps.length + '</span></h3></div>' +
        ps.map(personCard).join('') + findBox(x) + '</section></div>';
    } else if (k === 'job') {
      const c = coByName(x.company);
      h = back + '<div class="d-grid"><div><div class="d-head"><span class="chip-icon lg c-job">' + icon('briefcase') + '</span><div><div class="d-kind c-job">Job</div>' +
        '<h2><a href="' + esc(x.url) + '" target="_blank" rel="noopener">' + esc(x.title) + '</a></h2><div class="d-sub"><button class="mini-link" data-sel="' + c.key + '">' + esc(c.name) + '</button> · ' + esc(x.location) + '</div></div></div>' +
        '<div class="d-facts">' + factPill('', x.salary || 'Salary not listed') + factPill('', x.location) + '</div>' +
        '<div class="d-actions">' + stAct(x) + pinAct(x) + '<a class="btn" href="' + esc(x.url) + '" target="_blank" rel="noopener">' + icon('external') + 'Open posting</a>' +
        '<button class="btn" data-sel="' + c.key + '">' + icon('building') + 'Show in company</button></div></div>' + ring(x.score) + '</div>' +
        '<div class="panel why"><div class="panel-h">' + icon('sparkle') + 'Why it fits you</div><div class="panel-b">' + esc(x.alignment) + '</div></div>' +
        '<div class="sec-h c-person"><h3>' + icon('user') + 'People at ' + esc(c.name) + ' <span class="n num">' + peopleOf(c).length + '</span></h3></div><div class="one">' +
        peopleOf(c).slice(0, 3).map(personCard).join('') + (peopleOf(c).length ? '' : findBox(c)) + (peopleOf(c).length > 3 ? '<button class="show-all" data-sel="' + c.key + '">See all ' + peopleOf(c).length + ' in company view</button>' : '') + '</div>';
    } else {
      const c = coByName(x.company), msg = x.connect_message || '';
      h = back + '<div class="d-head"><span class="avatar lg c-person">' + esc(initials(x.name)) + '</span><div><div class="d-kind c-person">Person</div>' +
        '<h2><a href="' + esc(x.profile_url) + '" target="_blank" rel="noopener">' + esc(x.name) + '</a></h2><div class="d-sub">' + esc(x.title || 'Title not listed') + ' at <button class="mini-link" data-sel="' + c.key + '">' + esc(c.name) + '</button></div></div></div>' +
        '<div class="d-actions">' + stAct(x) + pinAct(x) + '<a class="btn" href="' + esc(x.profile_url) + '" target="_blank" rel="noopener">' + icon('external') + 'LinkedIn</a><button class="btn" data-sel="' + c.key + '">' + icon('building') + 'Show in company</button></div>' +
        '<div class="panel why"><div class="panel-h">' + icon('sparkle') + 'Why connect</div><div class="panel-b">' + esc(x.alignment) + '</div></div>' +
        '<div class="sec-h c-person"><h3>' + icon('send') + 'Example LinkedIn message</h3></div><div class="msg"><div class="msg-t" id="msgT">' + esc(msg) + '</div>' +
        '<div class="msg-f"><span class="num ' + (msg.length > 300 ? 'over' : '') + '">' + msg.length + ' / 300 characters</span><button class="btn sm" data-act="copy" id="copyBtn">' + icon('copy') + 'Copy</button></div></div>' +
        '<p class="hint">Edit before sending. Personalise the first line.</p>';
    }
    el.innerHTML = '<div class="d-inner">' + h + '</div>'; el.scrollTop = sc;
  }

  /* ---------- selection ---------- */
  function select(key, opts) {
    opts = opts || {}; const k = byKey(key); if (!k) return;
    ui.sel = key; ui.focus = key;
    if (ui.view === 'tree' && kindOf(key) !== 'company') ui.open.add(coByName(k.company).key);
    if (ui.view === 'flat' && ui.tab !== kindOf(key)) { ui.tab = kindOf(key); renderToolbar(); }
    renderList(); renderDetail();
    const n = $('rows').querySelector('.node[data-key="' + CSS.escape(key) + '"]');
    if (n) { if (opts.focus) n.focus({ preventScroll: true }); n.scrollIntoView({ block: 'nearest' }); }
    if (opts.open && mobile.matches) $('detail').classList.add('open');
  }
  const toggleOpen = (ck, on) => { on === undefined ? (ui.open.has(ck) ? ui.open.delete(ck) : ui.open.add(ck)) : (on ? ui.open.add(ck) : ui.open.delete(ck)); };

  function toggle(map, key, label) { map[key] ? delete map[key] : map[key] = 1; CC.persist(); refresh(); CC.toast(label + (map[key] ? '' : ' removed')); }
  function refresh() { renderCtx(); renderList(); renderDetail(true); renderToolbarCounts(); }
  function renderToolbarCounts() { if (ui.view === 'flat') { const t = $('toolbar').querySelectorAll('[data-tab] .count'); TABS.forEach((tb, i) => { if (t[i]) t[i].textContent = flatModel(tb[0]).length; }); } }

  /* ---------- events ---------- */
  document.addEventListener('click', e => {
    const a = e.target.closest('[data-act]'), s = e.target.closest('[data-sel]');
    if (a) {
      const act = a.dataset.act, key = a.dataset.key;
      if (act === 'tog') { e.stopPropagation(); toggleOpen(key); const n = byKey(key); renderList(); return; }
      if (act === 'pin') { e.stopPropagation(); const x = byKey(key); toggle(S.pins, key, isPinned(key) ? 'Unpinned ' + nm(x) : 'Pinned ' + nm(x)); if (!isPinned(key)) return; return; }
      if (act === 'st') { e.stopPropagation(); const x = byKey(key), job = key.startsWith('job'); toggle(job ? S.applied : S.connected, key, (job ? 'Marked applied: ' : 'Marked connected: ') + nm(x)); return; }
      if (act === 'card') { ui.cardOpen.has(key) ? ui.cardOpen.delete(key) : ui.cardOpen.add(key); renderDetail(true); return; }
      if (act === 'back') { $('detail').classList.remove('open'); return; }
      if (act === 'find') { findPeople(key); return; }
      if (act === 'copy') { copyMsg(a); return; }
    }
    if (s) { select(s.dataset.sel, { open: true }); return; }
    const n = e.target.closest('.node');
    if (n) { select(n.dataset.key, { open: true, focus: true }); }
  });
  document.addEventListener('dblclick', e => { const n = e.target.closest('.node.k-company'); if (n && !e.target.closest('[data-act]')) { toggleOpen(n.dataset.key); renderList(); } });

  function copyMsg(btn) {
    const t = $('msgT').textContent;
    try { navigator.clipboard && navigator.clipboard.writeText(t); } catch (err) {}
    btn.classList.add('copied'); btn.innerHTML = icon('check') + 'Copied'; CC.toast('Message copied to clipboard');
    setTimeout(() => { if (btn.isConnected) { btn.classList.remove('copied'); btn.innerHTML = icon('copy') + 'Copy'; } }, 1800);
  }
  function findPeople(ck) {
    const c = byKey(ck), had = ui.finding[ck + ':tries'] || 0; ui.finding[ck] = 'loading'; renderDetail(true);
    setTimeout(() => {
      ui.finding[ck + ':tries'] = had + 1;
      if (had === 0) { ui.finding[ck] = 'error'; }
      else { ui.finding[ck] = null; ui.extra[ck] = (ui.extra[ck] || []).concat([
        { key: 'person:linkedin:new-' + c.name.toLowerCase() + '-1', company: c.name, name: 'Morgan Ellis', title: 'Engineering Manager', profile_url: 'https://www.linkedin.com/in/morgan-ellis', alignment: 'Found by the second search. Manages an engineering team at ' + c.name + ' and can speak to hiring.', connect_message: 'Hi Morgan, I build agentic chat interfaces with self-hosted LLMs at Dover and ' + c.name + ' is high on my list. I would love to connect and hear about your team.' },
        { key: 'person:linkedin:new-' + c.name.toLowerCase() + '-2', company: c.name, name: 'Dana Ortiz', title: 'Senior Software Engineer', profile_url: 'https://www.linkedin.com/in/dana-ortiz', alignment: 'A senior engineer who can describe day-to-day work and how the team interviews.', connect_message: 'Hi Dana, I am a software engineer at Dover building LLM tooling and I am exploring roles at ' + c.name + '. I would appreciate a short chat about the team.' }]); CC.toast('Found 2 people at ' + c.name); }
      renderList(); renderDetail(true);
    }, 1100);
  }

  /* keyboard: tree navigation */
  $('rows').addEventListener('keydown', e => {
    const nodeEl = e.target.closest('.node'); if (!nodeEl) return;
    const nodes = visibleNodes(), i = nodes.findIndex(n => n.x.key === nodeEl.dataset.key), n = nodes[i]; if (!n) return;
    const go = (j) => { j = Math.max(0, Math.min(nodes.length - 1, j)); select(nodes[j].x.key, { focus: true }); e.preventDefault(); };
    const open = ui.q || ui.open.has(n.x.key), hasKids = n.kind === 'company' && ui.view === 'tree' && nodeEl.hasAttribute('aria-expanded');
    switch (e.key) {
      case 'ArrowDown': go(i + 1); break;
      case 'ArrowUp': go(i - 1); break;
      case 'Home': go(0); break;
      case 'End': go(nodes.length - 1); break;
      case 'ArrowRight':
        if (hasKids && !open) { toggleOpen(n.x.key, true); renderList(); select(n.x.key, { focus: true }); }
        else if (hasKids && open && nodes[i + 1] && nodes[i + 1].parent === n.x.key) go(i + 1);
        e.preventDefault(); break;
      case 'ArrowLeft':
        if (hasKids && open && !ui.q) { toggleOpen(n.x.key, false); renderList(); select(n.x.key, { focus: true }); }
        else if (n.parent) { select(n.parent, { focus: true }); }
        e.preventDefault(); break;
      case 'Enter': case ' ':
        if (n.kind === 'company' && ui.view === 'tree' && hasKids) { toggleOpen(n.x.key); renderList(); }
        select(n.x.key, { open: true, focus: true }); e.preventDefault(); break;
    }
  });
  document.addEventListener('keydown', e => {
    const t = e.target, typing = t && (/INPUT|TEXTAREA|SELECT/.test(t.tagName) || t.isContentEditable);
    if (typing || e.ctrlKey || e.metaKey || e.altKey) { if (typing && e.key === 'Escape') t.blur(); return; }
    const k = e.key.toLowerCase(), nodes = visibleNodes(), i = nodes.findIndex(n => n.x.key === ui.sel);
    if (k === '/') { e.preventDefault(); $('q').focus(); }
    else if (k === 'j' || k === 'k') { if (nodes.length) { const j = Math.max(0, Math.min(nodes.length - 1, i + (k === 'j' ? 1 : -1))); select(nodes[j].x.key, { focus: true }); } }
    else if (k === 'p' && ui.sel) { const x = byKey(ui.sel); toggle(S.pins, ui.sel, isPinned(ui.sel) ? 'Unpinned ' + nm(x) : 'Pinned ' + nm(x)); }
    else if (k === 'x' && ui.sel && kindOf(ui.sel) !== 'company') { const job = kindOf(ui.sel) === 'job'; toggle(job ? S.applied : S.connected, ui.sel, (job ? 'Marked applied: ' : 'Marked connected: ') + nm(byKey(ui.sel))); }
    else if (k === 'e') { if (ui.view === 'tree') expandAll(!(ui.open.size === cos.length)); else setView('tree'); }
    else if (k === 'v') setView(ui.view === 'tree' ? 'flat' : 'tree');
    else if (e.key === 'Escape') $('detail').classList.remove('open');
  });
  mobile.addEventListener && mobile.addEventListener('change', () => $('detail').classList.remove('open'));

  /* command palette entries */
  CC.addCommands(() => {
    const cmds = [
      { g: 'Tree', label: 'Expand all companies', icon: 'chevs', hint: 'E', run: () => { if (ui.view !== 'tree') setView('tree'); expandAll(true); } },
      { g: 'Tree', label: 'Collapse all companies', icon: 'chevsin', run: () => { if (ui.view !== 'tree') setView('tree'); expandAll(false); } },
      { g: 'Tree', label: 'Switch to ' + (ui.view === 'tree' ? 'flat tabs' : 'company tree') + ' view', icon: ui.view === 'tree' ? 'rows' : 'tree', hint: 'V', run: () => setView(ui.view === 'tree' ? 'flat' : 'tree') }
    ];
    return cmds.concat(cos.map(c => ({ g: 'Companies', label: c.name, icon: 'building', run: () => select(c.key, { open: true, focus: true }) })),
      jobs.map(j => ({ g: 'Jobs', label: j.title + ' · ' + j.company, icon: 'briefcase', run: () => select(j.key, { open: true, focus: true }) })),
      ppl.map(p => ({ g: 'People', label: p.name + ' · ' + p.company, icon: 'user', run: () => select(p.key, { open: true, focus: true }) })));
  });

  function renderAll() { renderCtx(); renderToolbar(); renderChips(); renderList(); renderDetail(); }
  function init() { renderAll(); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
