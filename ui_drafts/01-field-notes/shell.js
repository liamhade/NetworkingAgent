/* Shared app shell for the Field Notes mockup: icons, sidebar (Previous searches), top nav, mobile drawer. */
(function () {
  const p = (d, extra) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${extra || ''}>${d}</svg>`;
  window.I = {
    search: p('<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/>'),
    building: p('<path d="M4 21V5a1 1 0 011-1h8a1 1 0 011 1v16M14 10h5a1 1 0 011 1v10M3 21h18M8 8h2M8 12h2M8 16h2"/>'),
    briefcase: p('<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2M3 13h18"/>'),
    user: p('<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>'),
    bookmark: p('<path d="M6 4h12v17l-6-4-6 4z"/>'),
    bookmarkFill: p('<path d="M6 4h12v17l-6-4-6 4z" fill="currentColor"/>'),
    check: p('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
    circle: p('<circle cx="12" cy="12" r="8"/>'),
    copy: p('<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 012-2h9"/>'),
    chev: p('<path d="M6 9l6 6 6-6"/>'),
    ext: p('<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V7a1 1 0 011-1h5"/>'),
    send: p('<path d="M21 3L10 14M21 3l-7 18-4-7-7-4z"/>'),
    plus: p('<path d="M12 5v14M5 12h14"/>'),
    x: p('<path d="M6 6l12 12M18 6L6 18"/>'),
    menu: p('<path d="M4 7h16M4 12h16M4 17h16"/>'),
    spark: p('<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>'),
    trash: p('<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>'),
    pencil: p('<path d="M4 20l1-4L16.5 4.5a2 2 0 012.8 2.8L8 18.5z"/>'),
    save: p('<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>'),
    upload: p('<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>'),
    file: p('<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>'),
    link: p('<path d="M10 14a4 4 0 005.7 0l3-3a4 4 0 00-5.7-5.7l-1 1M14 10a4 4 0 00-5.7 0l-3 3A4 4 0 0011 18.7l1-1"/>'),
    filter: p('<path d="M4 6h16M7 12h10M10 18h4"/>'),
    star: p('<path d="M12 3.5l2.6 5.3 5.9.8-4.3 4.1 1 5.8L12 16.8 6.8 19.5l1-5.8L3.5 9.6l5.9-.8z"/>'),
    msg: p('<path d="M4 5h16v11H9l-5 4z"/>'),
    stop: p('<rect x="6" y="6" width="12" height="12" rx="2"/>'),
    refresh: p('<path d="M20 11a8 8 0 10-2.3 5.7M20 4v7h-7"/>'),
    warn: p('<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17.5v.01"/>')
  };

  const page = document.body.dataset.page || 'results';
  const cur = document.body.dataset.hist || '';

  const hist = [
    { id: 'a', t: 'Software engineering roles, particularly in agentic AI… · New York, NY', m: 'Yesterday, 3:45 PM', href: 'results.html' },
    { id: 'b', t: 'Data platform engineering · Remote (US)', st: 'run', m: 'Searching…', href: 'running.html' },
    { id: 'c', t: 'ML infrastructure at fintech firms · Boston, MA', m: 'Nov 12, 10:08 AM', href: 'results.html' },
    { id: 'd', t: 'Backend roles at climate tech startups · New York, NY', st: 'can', m: 'Cancelled · Nov 10', href: 'results.html' },
    { id: 'e', t: 'Platform engineering in healthcare · Chicago, IL', st: 'err', m: 'Failed · Nov 8', href: 'results.html' }
  ];

  const side = document.getElementById('side');
  if (side) {
    side.innerHTML = `
      <a class="brand" href="search.html" aria-label="Networking Agent, home">
        <span class="brand-mark" aria-hidden="true">N</span>
        <span><span class="brand-name">Networking Agent</span><span class="brand-sub">Your job-search desk</span></span>
      </a>
      <a class="btn btn-primary" href="search.html">${I.plus} New search</a>
      <nav aria-labelledby="hist-h">
        <h2 class="side-h" id="hist-h">Previous searches</h2>
        <ul class="hist">
          ${hist.map(h => `
          <li data-id="${h.id}">
            <a class="hist-link" href="${h.href}" ${h.id === cur ? 'aria-current="page"' : ''}>
              <span class="hist-t">${h.t}</span>
              <span class="hist-m">${h.st === 'run' ? '<span class="dot-live" aria-hidden="true"></span><span class="st st-run">Searching…</span> · step 3 of 5' : h.st === 'err' ? '<span class="st st-err">' + h.m + '</span>' : h.st === 'can' ? '<span class="st st-can">' + h.m + '</span>' : h.m + ' · 6 companies'}</span>
            </a>
            ${h.st === 'run'
              ? `<button class="hist-x" data-act="side-cancel" aria-label="Cancel search: ${h.t}" title="Cancel search">${I.stop}</button>`
              : `<button class="hist-x" data-act="side-del" aria-label="Delete search: ${h.t}" title="Delete search">${I.trash}</button>`}
            <div class="hist-confirm" hidden>Delete this search? <button class="btn btn-sm btn-ghost" data-act="side-keep">Keep</button><button class="btn btn-sm btn-danger" data-act="side-del-yes">Delete</button></div>
          </li>`).join('')}
        </ul>
      </nav>
      <div class="side-foot"><span class="avatar" aria-hidden="true">TU</span> Test User</div>`;
  }

  const top = document.getElementById('topbar');
  if (top) {
    const nav = [
      ['search', 'search.html', I.search, 'Search'],
      ['companies', 'results.html#companies', I.building, 'Companies'],
      ['jobs', 'results.html#jobs', I.briefcase, 'Jobs'],
      ['people', 'results.html#people', I.user, 'People']
    ];
    top.innerHTML = `
      <button class="icon-btn menu-btn" data-act="drawer" aria-label="Previous searches and menu" aria-controls="side">${I.menu}</button>
      <nav class="nav" aria-label="Primary">
        ${nav.map(n => `<a href="${n[1]}" data-nav="${n[0]}" ${n[0] === page || (page === 'running' && n[0] === 'search') || (page === 'results' && n[0] === 'companies' && !location.hash) ? 'aria-current="page"' : ''}>${n[2]}<span>${n[3]}</span></a>`).join('')}
      </nav>
      <span class="sp"></span>
      <a class="btn btn-sm" href="search.html">${I.plus}<span>New search</span></a>`;
  }

  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-act]');
    if (!b) { if (document.body.classList.contains('drawer') && !e.target.closest('.side')) document.body.classList.remove('drawer'); return; }
    const a = b.dataset.act;
    if (a === 'drawer') { document.body.classList.toggle('drawer'); }
    if (a === 'side-del') { const li = b.closest('li'); li.querySelector('.hist-confirm').hidden = false; li.querySelector('.hist-link').style.display = 'none'; b.style.display = 'none'; }
    if (a === 'side-keep') { const li = b.closest('li'); li.querySelector('.hist-confirm').hidden = true; li.querySelector('.hist-link').style.display = ''; li.querySelector('.hist-x').style.display = ''; }
    if (a === 'side-del-yes') { b.closest('li').remove(); window.toast && window.toast('Search deleted'); }
    if (a === 'side-cancel') { window.location.href = 'running.html#cancel'; }
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') document.body.classList.remove('drawer'); });

  /* toast helper */
  let tEl, tT;
  window.toast = function (msg, undo) {
    if (!tEl) { tEl = document.createElement('div'); tEl.className = 'toast'; tEl.setAttribute('role', 'status'); tEl.setAttribute('aria-live', 'polite'); document.body.appendChild(tEl); }
    tEl.innerHTML = `<span>${msg}</span>${undo ? '<button type="button">Undo</button>' : ''}`;
    if (undo) tEl.querySelector('button').onclick = () => { undo(); tEl.classList.remove('show'); };
    tEl.classList.add('show'); clearTimeout(tT); tT = setTimeout(() => tEl.classList.remove('show'), 4000);
  };
})();
