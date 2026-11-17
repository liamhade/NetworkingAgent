/* Results workspace (Command - Harbor): master-detail logic (mock). Entity state is keyed by entity key, like the real app. */
(function () {
  const { esc, icon } = CC, D = DATA, S = CC.state;
  const cos = D.companies, jobs = D.jobs, ppl = D.people;
  const mobile = window.matchMedia('(max-width:860px)');
  const kindOf = k => k.startsWith('company') ? 'company' : k.startsWith('job') ? 'job' : 'person';
  const TAB = { company: 'companies', job: 'jobs', person: 'people' };
  const all = () => cos.concat(jobs, ppl);
  const byKey = k => all().find(x => x.key === k);
  const coByName = n => cos.find(c => c.name === n);
  const coJobs = n => jobs.filter(j => j.company === n);
  const coPeople = n => ppl.filter(p => p.company === n);
  const isPinned = k => !!S.pins[k];
  const isOn = x => !!(x.key.startsWith('job') ? S.applied[x.key] : S.connected[x.key]);
  const fitCls = s => s >= 80 ? 'strong' : s >= 70 ? 'good' : 'fair';
  const fitLab = s => s >= 80 ? 'Strong fit' : s >= 70 ? 'Good fit' : 'Possible fit';
  const first = n => n.split(' ')[0];
  const peopleFor = j => ppl.filter(p => D.about[p.key] === j.key);
  const jobFor = p => byKey(D.about[p.key]) || coJobs(p.company)[0];
  const initials = n => n.split(' ').filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();
  const firstSentence = t => (t.match(/^.*?[.!?](\s|$)/) || [t])[0].trim();
  const nm = x => x.name || x.title;

  const ui = { tab: 'companies', sel: { companies: cos[0].key, jobs: jobs[0].key, people: ppl[0].key },
    chips: { companies: new Set(), jobs: new Set(), people: new Set() }, sort: { companies: 'fit', jobs: 'score', people: 'company' },
    q: '', group: { jobs: false, people: true }, collapsed: new Set(), open: new Set([jobs.find(j => j.company === cos[0].name).key, ppl.find(p => p.company === cos[0].name).key]), showAll: new Set(), finding: {}, summaryOpen: false, lastDetail: null };
  const h = location.hash.replace('#', ''); if (TAB[h] || ['companies', 'jobs', 'people'].includes(h)) ui.tab = h;
  document.body.dataset.density = CC.ls.get('cch-density') || 'comfortable';

  const CHIPS = {
    companies: [['pinned', 'Pinned'], ['jobs', 'Has jobs'], ['contacts', 'Has contacts'], ['strong', 'Fit 75+']],
    jobs: [['pinned', 'Pinned'], ['todo', 'Not applied'], ['done', 'Applied'], ['strong', 'Match 75+']],
    people: [['pinned', 'Pinned'], ['todo', 'Not connected'], ['done', 'Connected']]
  };
  const SORTS = {
    companies: [['fit', 'Best fit'], ['name', 'Name A-Z'], ['jobs', 'Most jobs'], ['people', 'Most people'], ['pinned', 'Pinned first']],
    jobs: [['score', 'Best match'], ['company', 'Company'], ['title', 'Title A-Z'], ['todo', 'Not applied first'], ['pinned', 'Pinned first']],
    people: [['company', 'By company'], ['name', 'Name A-Z'], ['todo', 'Not connected first'], ['pinned', 'Pinned first']]
  };

  function listFor(tab) {
    let items = tab === 'companies' ? cos.slice() : tab === 'jobs' ? jobs.slice() : ppl.slice();
    const q = ui.q.trim().toLowerCase();
    if (q) items = items.filter(x => (nm(x) + ' ' + (x.company || '') + ' ' + (x.title || '') + ' ' + (x.location || '') + ' ' + x.alignment).toLowerCase().includes(q));
    ui.chips[tab].forEach(c => {
      items = items.filter(x => c === 'pinned' ? isPinned(x.key) : c === 'strong' ? x.score >= 75 : c === 'jobs' ? coJobs(x.name).length : c === 'contacts' ? coPeople(x.name).length
        : c === 'todo' ? !isOn(x) : c === 'done' ? isOn(x) : true);
    });
    const s = ui.sort[tab], cmp = {
      fit: (a, b) => b.score - a.score, score: (a, b) => b.score - a.score, name: (a, b) => nm(a).localeCompare(nm(b)), title: (a, b) => a.title.localeCompare(b.title),
      company: (a, b) => (a.company || '').localeCompare(b.company || '') || 0, jobs: (a, b) => coJobs(b.name).length - coJobs(a.name).length,
      people: (a, b) => coPeople(b.name).length - coPeople(a.name).length, pinned: (a, b) => (isPinned(b.key) - isPinned(a.key)), todo: (a, b) => (isOn(a) - isOn(b))
    }[s];
    if (s === 'company') { const order = cos.map(c => c.name); items.sort((a, b) => order.indexOf(a.company) - order.indexOf(b.company)); }
    else items.sort((a, b) => cmp(a, b) || (b.score || 0) - (a.score || 0));
    return items;
  }

  /* ---------- header + tabs ---------- */
  function renderCtx() {
    const s = D.search, ap = jobs.filter(j => S.applied[j.key]).length, cn = ppl.filter(p => S.connected[p.key]).length, pins = Object.keys(S.pins).length;
    const tabs = [['companies', 'building', 'company', 'Companies', cos.length], ['jobs', 'briefcase', 'job', 'Jobs', jobs.length], ['people', 'user', 'person', 'People', ppl.length]];
    const card = (cls, n, label, extra) => '<div class="stat ' + cls + '" role="listitem"><b class="num">' + n + '</b><span class="l">' + label + '</span>' + (extra || '') + '</div>';
    document.getElementById('ctx').innerHTML =
      '<div class="ctx-row"><div style="min-width:0"><div class="eyebrow">Search results · ' + esc(s.created) + '</div><h1 title="' + esc(s.title) + '">' + esc(s.title) + '</h1>' +
      '<div class="ctx-sub"><span class="tag">' + icon('clock') + esc(s.created) + '</span><span class="tag">' + esc(s.location) + '</span><span class="tag">Boards: ' + esc(s.boards.join(', ')) + '</span></div></div>' +
      '<div class="ctx-actions"><a class="btn" href="search.html">' + icon('edit') + '<span class="lbl-t">Edit &amp; re-run</span></a><a class="btn primary" href="search.html">' + icon('plus') + '<span class="lbl-t">New search</span></a></div></div>' +
      '<div class="ctx-mid"><div class="stats" role="list" aria-label="Search totals">' +
      card('c-company', cos.length, 'Companies') + card('c-job', jobs.length, 'Open jobs') + card('c-person', ppl.length, 'People') +
      card('s-applied', ap + ' <small>/ ' + jobs.length + '</small>', 'Applied', '<div class="bar"><i style="width:' + (ap / jobs.length * 100) + '%"></i></div>') +
      card('s-connected', cn + ' <small>/ ' + ppl.length + '</small>', 'Connected', '<div class="bar"><i style="width:' + (cn / ppl.length * 100) + '%"></i></div>') +
      card('s-pinned', pins, 'Pinned') + '</div>' +
      '<div class="summary' + (ui.summaryOpen ? '' : ' clamp') + '"><div style="display:flex;justify-content:space-between;gap:8px"><strong>Agent summary</strong><button class="link-btn" data-act="summary" aria-expanded="' + ui.summaryOpen + '">' + (ui.summaryOpen ? 'Show less' : 'Read more') + '</button></div><span class="t">' + esc(s.summary) + '</span></div></div>' +
      '<div class="tabs" role="tablist" aria-label="Result type">' + tabs.map(t => '<button class="tab c-' + t[2] + '" role="tab" id="tab-' + t[0] + '" aria-selected="' + (ui.tab === t[0]) + '" data-act="tab" data-val="' + t[0] + '">' + icon(t[1]) + t[3] + ' <span class="count num">' + t[4] + '</span></button>').join('') + '</div>';
  }

  /* ---------- toolbar / chips ---------- */
  function renderToolbar() {
    const t = ui.tab, grp = t !== 'companies';
    document.getElementById('toolbar').innerHTML =
      '<label class="search-in">' + icon('search') + '<span class="sr-only">Filter ' + t + '</span><input id="q" type="search" placeholder="Filter ' + t + '...  ( / )" value="' + esc(ui.q) + '"></label>' +
      '<label class="sr-only" for="sort">Sort</label><select class="sel" id="sort">' + SORTS[t].map(o => '<option value="' + o[0] + '"' + (ui.sort[t] === o[0] ? ' selected' : '') + '>Sort: ' + o[1] + '</option>').join('') + '</select>' +
      (grp ? '<button class="fchip" data-act="group" aria-pressed="' + ui.group[t] + '">Group by company</button>' : '') +
      '<div class="seg" role="group" aria-label="Row density"><button data-act="density" data-val="compact" aria-pressed="' + (document.body.dataset.density === 'compact') + '">Compact</button><button data-act="density" data-val="comfortable" aria-pressed="' + (document.body.dataset.density !== 'compact') + '">Comfortable</button></div>';
    document.getElementById('chips').innerHTML = CHIPS[t].map(c => '<button class="fchip" data-act="chip" data-val="' + c[0] + '" aria-pressed="' + ui.chips[t].has(c[0]) + '">' + c[1] + '</button>').join('');
    document.getElementById('q').oninput = e => { ui.q = e.target.value; renderRows(); };
    document.getElementById('sort').onchange = e => { ui.sort[t] = e.target.value; renderRows(); };
  }

  /* ---------- list rows ---------- */
  function statusBtn(x) {
    const job = x.key.startsWith('job'), on = isOn(x), on1 = job ? 'Applied' : 'Connected', off1 = job ? 'Mark applied' : 'Mark connected';
    return on ? '<button class="pill st on ' + (job ? 's-applied' : 's-connected') + '" data-act="status" data-key="' + x.key + '" aria-pressed="true" aria-label="' + on1 + ': ' + esc(nm(x)) + ' (click to undo)">' + icon('check') + on1 + '</button>'
      : '<button class="btn sm ghost st" data-act="status" data-key="' + x.key + '" aria-pressed="false" aria-label="' + off1 + ': ' + esc(nm(x)) + '">' + off1 + '</button>';
  }
  const pinBtn = x => '<button class="icon-btn pin" data-act="pin" data-key="' + x.key + '" aria-pressed="' + isPinned(x.key) + '" aria-label="Pin ' + esc(nm(x)) + '" title="Pin (p)">' + icon('pin') + '</button>';
  const fitHTML = (s, lg) => '<span class="fit ' + fitCls(s) + (lg ? ' lg' : '') + '" title="Fit score ' + s + ' of 100"><span class="top"><b class="num">' + s + '</b><small>' + fitLab(s) + '</small></span><span class="bar"><i style="width:' + s + '%"></i></span></span>';

  function rowHTML(x, tab) {
    const k = x.key, sel = ui.sel[tab] === k, k1 = kindOf(k);
    let lead, sub, right = '';
    if (k1 === 'company') {
      lead = '<span class="rank num">' + (cos.indexOf(x) + 1) + '</span><span class="chip-icon c-company">' + icon('building') + '</span>';
      const nj = coJobs(x.name).length; sub = nj + (nj === 1 ? ' job' : ' jobs') + ' · ' + coPeople(x.name).length + ' people · ' + x.loc; right = fitHTML(x.score);
    } else if (k1 === 'job') {
      lead = '<span class="chip-icon c-job">' + icon('briefcase') + '</span>';
      sub = x.company + ' · ' + x.location + (x.salary ? ' · ' + x.salary : ''); right = fitHTML(x.score) + statusBtn(x);
    } else {
      lead = '<span class="avatar c-person" aria-hidden="true">' + initials(x.name) + '</span>';
      sub = (x.title || 'Title not listed') + ' · ' + x.company; right = statusBtn(x);
    }
    return '<li class="row' + (sel ? ' sel' : '') + (isPinned(k) ? ' pinned' : '') + '" data-key="' + k + '"><button class="row-main" data-act="select" data-key="' + k + '"' + (sel ? ' aria-current="true"' : '') + '>' + lead +
      '<span class="row-text"><span class="row-title">' + esc(nm(x)) + '</span><span class="row-sub">' + esc(sub) + '</span><span class="row-why">' + esc(firstSentence(x.alignment)) + '</span></span></button>' +
      '<div class="row-actions">' + right + pinBtn(x) + '</div></li>';
  }

  function renderRows() {
    const t = ui.tab, items = listFor(t), el = document.getElementById('rows');
    const fid = focusId(); let html = '';
    if (!items.length) {
      html = '<div class="empty"><h3>Nothing matches these filters</h3><p>' + (ui.q || ui.chips[t].size ? 'Try removing a filter or widening your search text.' : 'No ' + t + ' yet.') + '</p><button class="btn" data-act="clear">Clear filters</button></div>';
    } else if (t !== 'companies' && ui.group[t] && ui.sort[t] !== 'pinned') {
      const names = []; items.forEach(i => { if (!names.includes(i.company)) names.push(i.company); });
      html = names.map(n => { const g = items.filter(i => i.company === n), col = ui.collapsed.has(t + n);
        return '<button class="group-h" data-act="collapse" data-val="' + t + n + '" aria-expanded="' + !col + '">' + icon('down') + '<span>' + esc(n) + '</span><span class="num" style="margin-left:auto">' + g.length + '</span></button>' +
          (col ? '' : '<ul class="rows">' + g.map(x => rowHTML(x, t)).join('') + '</ul>'); }).join('');
    } else html = '<ul class="rows">' + items.map(x => rowHTML(x, t)).join('') + '</ul>';
    el.innerHTML = html;
    const total = t === 'companies' ? cos.length : t === 'jobs' ? jobs.length : ppl.length;
    document.getElementById('listFoot').innerHTML = '<span class="num">' + items.length + ' of ' + total + ' ' + t + '</span><span class="hide-m"><kbd>j</kbd> <kbd>k</kbd> move</span><span class="hide-m"><kbd>p</kbd> pin</span><span class="hide-m"><kbd>a</kbd> done</span><span class="hide-m"><kbd>' + CC.mod + ' K</kbd></span>';
    restoreFocus(fid);
  }

  /* ---------- detail pane ---------- */
  const factPill = (txt, cls) => '<span class="tag' + (cls ? ' ' + cls : '') + '">' + txt + '</span>';
  function msgBox(p) {
    const n = p.connect_message.length;
    return '<div class="msg"><div class="msg-t">' + esc(p.connect_message) + '</div><div class="msg-f"><span class="num" title="LinkedIn invitation notes are limited to 300 characters">' + n + ' / 300 characters</span><button class="btn sm" data-act="copy" data-key="' + p.key + '">' + icon('copy') + 'Copy message</button></div></div>';
  }
  /* "Message X about Y" cross-links */
  function xlinkJob(j) {
    const ps = peopleFor(j), co = coByName(j.company);
    if (!ps.length) return '<button class="xlink" data-act="find" data-key="' + co.key + '">' + icon('user') + 'Find people at ' + esc(co.name) + ' to ask about this role' + icon('arrow') + '</button>';
    return '<button class="xlink" data-act="msg" data-key="' + ps[0].key + '">' + icon('send') + 'Message ' + esc(first(ps[0].name)) + (ps.length > 1 ? ' or ' + (ps.length - 1) + (ps.length > 2 ? ' others' : ' other') : '') + ' about this role' + icon('arrow') + '</button>';
  }
  function accJob(j) {
    const open = ui.open.has(j.key);
    return '<div class="acc c-job' + (open ? ' open' : '') + '"><div class="acc-h"><button class="acc-t" data-act="acc" data-key="' + j.key + '" aria-expanded="' + open + '">' + icon('right', 'chev') +
      '<span class="row-text"><span class="row-title">' + esc(j.title) + '</span><span class="row-sub">' + esc(j.location + (j.salary ? ' · ' + j.salary : '')) + '</span></span>' + fitHTML(j.score) + '</button>' + statusBtn(j) + pinBtn(j) + '</div>' +
      (open ? '<div class="acc-b"><div class="lbl">How you align</div><p>' + esc(j.alignment) + '</p>' + xlinkJob(j) + '<div class="d-actions"><a class="btn sm primary" href="' + j.url + '" target="_blank" rel="noopener">Open posting' + icon('external') + '</a><button class="btn sm" data-act="open" data-key="' + j.key + '">View details</button></div></div>' : '') + '</div>';
  }
  function accPerson(p) {
    const open = ui.open.has(p.key), j = jobFor(p);
    return '<div class="acc c-person' + (open ? ' open' : '') + '"><div class="acc-h"><button class="acc-t" data-act="acc" data-key="' + p.key + '" aria-expanded="' + open + '">' + icon('right', 'chev') +
      '<span class="avatar" aria-hidden="true">' + initials(p.name) + '</span><span class="row-text"><span class="row-title">' + esc(p.name) + '</span><span class="row-sub">' + esc(p.title || 'Title not listed') + '</span></span></button>' + statusBtn(p) + pinBtn(p) + '</div>' +
      (open ? '<div class="acc-b"><div class="lbl">Why connect</div><p>' + esc(p.alignment) + '</p><div class="lbl">Example LinkedIn message' + (j ? ' (about ' + esc(j.title) + ')' : '') + '</div>' + msgBox(p) + '<div class="d-actions"><a class="btn sm" href="' + p.profile_url + '" target="_blank" rel="noopener">Open LinkedIn' + icon('external') + '</a><button class="btn sm" data-act="open" data-key="' + p.key + '">View details</button></div></div>' : '') + '</div>';
  }
  /* job detail: a person row whose cross-link jumps to the message for this role */
  function personAbout(p, j) {
    return '<div class="acc c-person"><div class="acc-h"><div class="acc-t" style="cursor:default"><span class="avatar" aria-hidden="true">' + initials(p.name) + '</span><span class="row-text"><span class="row-title">' + esc(p.name) + '</span><span class="row-sub">' + esc(p.title || 'Title not listed') + '</span></span></div>' + statusBtn(p) + pinBtn(p) + '</div>' +
      '<div style="padding:0 10px 10px"><button class="xlink lone" data-act="msg" data-key="' + p.key + '">' + icon('send') + 'Message ' + esc(first(p.name)) + ' about ' + esc(j.title) + icon('arrow') + '</button></div></div>';
  }
  function findBox(c) {
    const has = coPeople(c.name).length, busy = ui.finding[c.key];
    const btn = '<button class="btn' + (has ? '' : ' primary') + '" data-act="find" data-key="' + c.key + '"' + (busy ? ' disabled' : '') + '>' + (busy ? icon('loader', 'spin') + 'Searching LinkedIn...' : icon('user') + (has ? 'Find more people' : 'Find people to connect with')) + '</button>';
    return has ? '<div style="margin-top:10px">' + btn + '<span class="hint" style="margin-left:10px">Takes about a minute. Searches for: ' + esc(c.keywords.join(', ')) + '</span></div>'
      : '<div class="find-box"><p>No current employees found yet for ' + esc(c.name) + '.</p>' + btn + '<div class="hint">Takes about a minute. Searches for: ' + esc(c.keywords.join(', ')) + '</div></div>';
  }
  const pinBtnL = (x, word) => '<button class="btn s-pinned' + (isPinned(x.key) ? ' on' : '') + '" data-act="pin" data-key="' + x.key + '" aria-pressed="' + isPinned(x.key) + '">' + icon('pin', isPinned(x.key) ? 'fill' : '') + (isPinned(x.key) ? 'Pinned' : (word || 'Pin')) + '</button>';
  const alignPanel = (x, h) => '<div class="panel why"><div class="panel-h">' + icon('sparkle') + h + '</div><div class="panel-b">' + esc(x.alignment) + '</div></div>';
  const dcard = (cls, n, l) => '<div class="stat ' + cls + '"><b class="num">' + n + '</b><span class="l">' + l + '</span></div>';

  function detailHTML(x) {
    const k = kindOf(x.key);
    const back = '<button class="btn sm d-back" data-act="back">' + icon('back') + 'Results</button>';
    if (k === 'company') {
      const js = coJobs(x.name), ps = coPeople(x.name), showAll = ui.showAll.has(x.key), vis = showAll ? ps : ps.slice(0, 3);
      const ap = js.filter(j => S.applied[j.key]).length, cn = ps.filter(p => S.connected[p.key]).length;
      return back + '<div class="d-grid"><div class="d-head c-company"><span class="chip-icon lg">' + icon('building') + '</span><div><div class="d-kind">Company · rank ' + (cos.indexOf(x) + 1) + ' of ' + cos.length + '</div><h2><a href="' + x.url + '" target="_blank" rel="noopener">' + esc(x.name) + '</a></h2><div class="d-sub">' + esc(x.description) + '</div></div></div>' + fitHTML(x.score, true) + '</div>' +
        '<div class="d-stats">' + dcard('c-job', js.length, (js.length === 1 ? 'open job' : 'open jobs') + ' · ' + ap + ' applied') + dcard('c-person', ps.length, 'people · ' + cn + ' connected') + dcard('c-company', '<span style="font-size:17px">' + esc(x.loc) + '</span>', 'location') + '</div>' +
        '<div class="d-actions"><a class="btn primary" href="' + x.url + '" target="_blank" rel="noopener">Company page' + icon('external') + '</a>' + pinBtnL(x, 'Pin company') + '</div>' +
        alignPanel(x, 'How you align') +
        '<div class="sec-h c-job"><h3>' + icon('briefcase') + 'Job openings <span class="n num">' + js.length + '</span></h3></div>' +
        (js.length ? js.map(accJob).join('') : '<div class="hint">No open jobs matched for this company.</div>') +
        '<div class="sec-h c-person"><h3>' + icon('user') + 'People to connect with <span class="n num">' + ps.length + '</span></h3></div>' +
        vis.map(accPerson).join('') + (ps.length > 3 ? '<button class="show-all" data-act="showall" data-key="' + x.key + '">' + (showAll ? 'Show fewer' : 'Show all ' + ps.length + ' people') + '</button>' : '') + findBox(x);
    }
    if (k === 'job') {
      const co = coByName(x.company), ps = peopleFor(x).length ? peopleFor(x) : coPeople(x.company).slice(0, 3);
      return back + '<div class="d-grid"><div class="d-head c-job"><span class="chip-icon lg">' + icon('briefcase') + '</span><div><div class="d-kind">Job</div><h2><a href="' + x.url + '" target="_blank" rel="noopener">' + esc(x.title) + '</a></h2><div class="d-sub">at <a class="mini-link" data-act="open" data-key="' + co.key + '" tabindex="0" role="link">' + esc(x.company) + '</a></div></div></div>' + fitHTML(x.score, true) + '</div>' +
        '<div class="d-facts">' + factPill(esc(x.location)) + (x.salary ? factPill(esc(x.salary) + ' / yr') : factPill('Salary not listed')) + '</div>' +
        '<div class="d-actions"><a class="btn primary" href="' + x.url + '" target="_blank" rel="noopener">Open posting' + icon('external') + '</a>' +
        '<button class="btn s-applied' + (isOn(x) ? ' on' : '') + '" data-act="status" data-key="' + x.key + '" aria-pressed="' + isOn(x) + '">' + icon('check') + (isOn(x) ? 'Applied' : 'Mark as applied') + '</button>' + pinBtnL(x) + '</div>' +
        alignPanel(x, 'How you align') +
        '<div class="sec-h c-person"><h3>' + icon('user') + 'Who to message about this role <span class="n num">' + ps.length + '</span></h3><button class="link-btn" data-act="open" data-key="' + co.key + '">Open company</button></div>' +
        (ps.length ? ps.map(p => personAbout(p, x)).join('') : '') + findBox(co);
    }
    const co = coByName(x.company), others = coPeople(x.company).filter(p => p.key !== x.key).slice(0, 3), j = jobFor(x);
    return back + '<div class="d-head c-person"><span class="avatar lg" aria-hidden="true">' + initials(x.name) + '</span><div><div class="d-kind">Person</div><h2><a href="' + x.profile_url + '" target="_blank" rel="noopener">' + esc(x.name) + '</a></h2><div class="d-sub">' + esc(x.title || 'Title not listed') + ' at <a class="mini-link" data-act="open" data-key="' + co.key + '" tabindex="0" role="link">' + esc(x.company) + '</a></div></div></div>' +
      '<div class="d-actions"><button class="btn primary" data-act="copy" data-key="' + x.key + '">' + icon('copy') + 'Copy message</button><a class="btn" href="' + x.profile_url + '" target="_blank" rel="noopener">Open LinkedIn' + icon('external') + '</a>' +
      '<button class="btn s-connected' + (isOn(x) ? ' on' : '') + '" data-act="status" data-key="' + x.key + '" aria-pressed="' + isOn(x) + '">' + icon('check') + (isOn(x) ? 'Connected' : 'Mark as connected') + '</button>' + pinBtnL(x) + '</div>' +
      alignPanel(x, 'Why connect') +
      (j ? '<button class="xlink job" data-act="open" data-key="' + j.key + '" style="margin-top:16px">' + icon('briefcase') + 'About: ' + esc(j.title) + (j.salary ? ' · ' + esc(j.salary) : '') + ' · open the role' + icon('arrow') + '</button>' : '') +
      '<div class="panel"><div class="panel-h">' + icon('send') + 'Message ' + esc(first(x.name)) + (j ? ' about ' + esc(j.title) : '') + '</div><div class="panel-b" style="padding-top:0">' + msgBox(x) + '<div class="hint">Edit before sending. A short, specific note gets more replies.</div></div></div>' +
      (others.length ? '<div class="sec-h c-person"><h3>' + icon('user') + 'Also at ' + esc(x.company) + '</h3><button class="link-btn" data-act="open" data-key="' + co.key + '">Open company</button></div>' + others.map(accPerson).join('') : '');
  }

  function renderDetail() {
    const x = byKey(ui.sel[ui.tab]), el = document.getElementById('detail'), fid = focusId();
    if (!x) { el.innerHTML = '<div class="empty"><h3>Select an item</h3><p>Details open here.</p></div>'; return; }
    const top = el.scrollTop; el.innerHTML = '<div class="d-inner">' + detailHTML(x) + '</div>';
    el.scrollTop = ui.lastDetail === x.key ? top : 0; ui.lastDetail = x.key; restoreFocus(fid);
  }

  /* ---------- focus preservation across re-renders ---------- */
  function focusId() { const a = document.activeElement; if (!a || !a.dataset || !a.dataset.act) return null; return [a.dataset.act, a.dataset.key || '', a.dataset.val || '', a.closest('#detail') ? 'd' : 'l'].join('|'); }
  function restoreFocus(id) {
    if (!id) return; const [act, key, val, zone] = id.split('|');
    const cand = [...document.querySelectorAll('[data-act="' + act + '"]')].find(e => (e.dataset.key || '') === key && (e.dataset.val || '') === val && (e.closest('#detail') ? 'd' : 'l') === zone);
    cand && cand.focus({ preventScroll: true });
  }
  const renderAll = () => { renderCtx(); renderToolbar(); renderRows(); renderDetail(); };
  const refresh = () => { renderCtx(); renderRows(); renderDetail(); };

  /* ---------- actions ---------- */
  function select(key, opts) {
    ui.sel[ui.tab] = key; renderRows(); renderDetail();
    if (mobile.matches && !(opts && opts.quiet)) document.getElementById('detail').classList.add('open');
  }
  function openEntity(key) {
    const t = TAB[kindOf(key)]; ui.tab = t; ui.chips[t].clear(); ui.q = ''; ui.sel[t] = key; ui.collapsed.clear();
    renderAll(); const r = document.querySelector('.row[data-key="' + key + '"]'); r && r.scrollIntoView({ block: 'center' });
    if (mobile.matches) document.getElementById('detail').classList.add('open');
  }
  function msgPerson(key) {
    openEntity(key);
    setTimeout(() => { const m = document.querySelector('#detail .msg'); if (m) { m.scrollIntoView({ block: 'center', behavior: 'smooth' }); m.classList.add('flash'); setTimeout(() => m.classList.remove('flash'), 1700); } }, 30);
  }
  function togglePin(key) {
    const x = byKey(key), was = isPinned(key);
    was ? delete S.pins[key] : (S.pins[key] = 1); CC.persist(); refresh();
    CC.toast((was ? 'Unpinned ' : 'Pinned ') + nm(x), 'Undo', () => { was ? (S.pins[key] = 1) : delete S.pins[key]; CC.persist(); refresh(); });
  }
  function toggleStatus(key) {
    const x = byKey(key), job = key.startsWith('job'), m = job ? S.applied : S.connected;
    m[key] ? delete m[key] : (m[key] = 1); CC.persist(); refresh();
    CC.toast((m[key] ? (job ? 'Marked applied: ' : 'Marked connected: ') : 'Cleared status: ') + nm(x));
  }
  function copyMsg(key, btn) {
    const p = byKey(key), done = () => { if (!btn) return; const old = btn.innerHTML; btn.classList.add('copied'); btn.innerHTML = icon('check') + 'Copied'; setTimeout(() => { btn.classList.remove('copied'); btn.innerHTML = old; }, 1800); };
    const fb = () => { const t = document.createElement('textarea'); t.value = p.connect_message; document.body.appendChild(t); t.select(); try { document.execCommand('copy'); } catch (e) {} t.remove(); done(); };
    (navigator.clipboard && window.isSecureContext) ? navigator.clipboard.writeText(p.connect_message).then(done, fb) : fb();
  }
  const POOL = [['Maya Chen', 'Engineering Manager'], ['Dev Patel', 'Senior Software Engineer'], ['Sam Ortiz', 'Head of Engineering'], ['Ana Rossi', 'Staff Engineer']];
  function findPeople(key) {
    const c = byKey(key); ui.finding[key] = true; renderDetail();
    setTimeout(() => {
      delete ui.finding[key]; const base = coPeople(c.name).length;
      POOL.slice(0, 3).forEach((pp, i) => { const slug = pp[0].toLowerCase().replace(' ', '-') + '-' + c.name.toLowerCase().replace(/\s/g, '') + (base + i);
        ppl.push({ key: 'person:linkedin:' + slug, company: c.name, name: pp[0], title: pp[1], profile_url: 'https://www.linkedin.com/in/' + slug,
          alignment: 'Found by the agent as a current ' + pp[1] + ' at ' + c.name + '. Reaching out can give you a direct view of the team and an introduction to the open role.',
          connect_message: 'Hi ' + pp[0].split(' ')[0] + ", I'm a software engineer building agentic chat interfaces with self-hosted LLMs at Dover, and " + c.name + "'s work caught my eye. I'd love to connect and learn more about your team." }); });
      refresh(); CC.toast('Found 3 people at ' + c.name);
    }, 2200);
  }

  document.addEventListener('click', e => {
    const b = e.target.closest('[data-act]'); if (!b) return; const a = b.dataset.act, key = b.dataset.key, val = b.dataset.val;
    if (a === 'select') select(key);
    else if (a === 'pin') togglePin(key);
    else if (a === 'status') toggleStatus(key);
    else if (a === 'copy') copyMsg(key, b);
    else if (a === 'open') openEntity(key);
    else if (a === 'msg') msgPerson(key);
    else if (a === 'acc') { ui.open.has(key) ? ui.open.delete(key) : ui.open.add(key); renderDetail(); }
    else if (a === 'showall') { ui.showAll.has(key) ? ui.showAll.delete(key) : ui.showAll.add(key); renderDetail(); }
    else if (a === 'find') findPeople(key);
    else if (a === 'tab') { ui.tab = val; history.replaceState(null, '', '#' + val); renderAll(); document.getElementById('detail').classList.remove('open'); }
    else if (a === 'chip') { const s = ui.chips[ui.tab]; s.has(val) ? s.delete(val) : s.add(val); renderToolbar(); renderRows(); }
    else if (a === 'group') { ui.group[ui.tab] = !ui.group[ui.tab]; renderToolbar(); renderRows(); }
    else if (a === 'collapse') { ui.collapsed.has(val) ? ui.collapsed.delete(val) : ui.collapsed.add(val); renderRows(); }
    else if (a === 'density') { document.body.dataset.density = val; CC.ls.set('cch-density', val); renderToolbar(); }
    else if (a === 'clear') { ui.q = ''; ui.chips[ui.tab].clear(); renderToolbar(); renderRows(); }
    else if (a === 'summary') { ui.summaryOpen = !ui.summaryOpen; renderCtx(); }
    else if (a === 'back') document.getElementById('detail').classList.remove('open');
  });

  /* ---------- keyboard ---------- */
  function move(d) {
    const rows = [...document.querySelectorAll('#rows .row')]; if (!rows.length) return;
    let i = rows.findIndex(r => r.dataset.key === ui.sel[ui.tab]); i = Math.max(0, Math.min(rows.length - 1, (i < 0 ? 0 : i + d)));
    const k = rows[i].dataset.key; select(k, { quiet: true });
    const btn = document.querySelector('.row[data-key="' + k + '"] .row-main'); btn && (btn.focus({ preventScroll: true }), btn.scrollIntoView({ block: 'nearest' }));
  }
  document.addEventListener('keydown', e => {
    const t = e.target; if (/INPUT|TEXTAREA|SELECT/.test(t.tagName) && e.key !== 'Escape') return;
    if (e.ctrlKey || e.metaKey || e.altKey || document.querySelector('.palette.open')) return;
    const cur = byKey(ui.sel[ui.tab]), inList = t.closest && (t.closest('#rows') || t === document.body);
    if (e.key === 'j' || (e.key === 'ArrowDown' && inList)) { move(1); e.preventDefault(); }
    else if (e.key === 'k' || (e.key === 'ArrowUp' && inList)) { move(-1); e.preventDefault(); }
    else if (e.key === 'p' && cur) togglePin(cur.key);
    else if (e.key === 'a' && cur && kindOf(cur.key) !== 'company') toggleStatus(cur.key);
    else if (e.key === 'c' && cur && kindOf(cur.key) === 'person') copyMsg(cur.key, document.querySelector('#detail [data-act="copy"]'));
    else if (e.key === 'o' && cur) window.open(cur.url || cur.profile_url, '_blank', 'noopener');
    else if (e.key === 'd') { document.body.dataset.density = document.body.dataset.density === 'compact' ? 'comfortable' : 'compact'; CC.ls.set('cch-density', document.body.dataset.density); renderToolbar(); }
    else if (['1', '2', '3'].includes(e.key)) { ui.tab = ['companies', 'jobs', 'people'][+e.key - 1]; renderAll(); }
    else if (e.key === '/') { e.preventDefault(); const q = document.getElementById('q'); q && q.focus(); }
    else if (e.key === 'Escape') { document.getElementById('detail').classList.remove('open'); }
  });

  CC.addCommands(() => {
    const cur = byKey(ui.sel[ui.tab]), cmds = [
      { g: 'This search', label: 'Show companies', icon: 'building', hint: '1', run: () => { ui.tab = 'companies'; renderAll(); } },
      { g: 'This search', label: 'Show jobs', icon: 'briefcase', hint: '2', run: () => { ui.tab = 'jobs'; renderAll(); } },
      { g: 'This search', label: 'Show people', icon: 'user', hint: '3', run: () => { ui.tab = 'people'; renderAll(); } },
      { g: 'This search', label: 'Toggle compact density', icon: 'rows', hint: 'D', run: () => { document.body.dataset.density = document.body.dataset.density === 'compact' ? 'comfortable' : 'compact'; renderToolbar(); } },
      { g: 'This search', label: 'Filter: pinned only', icon: 'pin', run: () => { ui.chips[ui.tab].add('pinned'); renderToolbar(); renderRows(); } }
    ];
    if (cur) cmds.unshift({ g: 'Selected', label: (isPinned(cur.key) ? 'Unpin ' : 'Pin ') + nm(cur), icon: 'pin', hint: 'P', run: () => togglePin(cur.key) });
    if (cur && kindOf(cur.key) === 'person') cmds.unshift({ g: 'Selected', label: 'Copy connect message for ' + cur.name, icon: 'copy', hint: 'C', run: () => copyMsg(cur.key, document.querySelector('#detail [data-act="copy"]')) });
    return cmds.concat(all().map(x => ({ g: 'Jump to', label: nm(x) + (x.company ? ' · ' + x.company : ''), icon: { company: 'building', job: 'briefcase', person: 'user' }[kindOf(x.key)], run: () => openEntity(x.key) })));
  });

  renderAll();
  mobile.addEventListener && mobile.addEventListener('change', () => document.getElementById('detail').classList.remove('open'));
})();
