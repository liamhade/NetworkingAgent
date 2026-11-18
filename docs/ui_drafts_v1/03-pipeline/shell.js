/* Shared app shell: icons, sidebar (Previous Searches), top nav, toast. */
(function () {
  const P = {
    building: '<path d="M4 21V4a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v17M14 9h5a1 1 0 0 1 1 1v11M2 21h20M8 7h2M8 11h2M8 15h2"/>',
    briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-7 8-7s8 3 8 7"/>',
    pin: '<path d="M6 3h12v18l-6-4-6 4z"/>',
    check: '<path d="M4 12.5l5 5L20 6.5"/>',
    send: '<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>',
    copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/>',
    ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    chev: '<path d="M6 9l6 6 6-6"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
    x: '<path d="M6 6l12 12M18 6L6 18"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
    board: '<rect x="3" y="3" width="5" height="18" rx="1.5"/><rect x="10" y="3" width="5" height="12" rx="1.5"/><rect x="17" y="3" width="4" height="8" rx="1.5"/>',
    spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 17l.8 2.2L22 20l-2.2.8L19 23l-.8-2.2L16 20l2.2-.8z"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    loader: '<path d="M12 3a9 9 0 1 0 9 9"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    edit: '<path d="M4 20h4L19 9l-4-4L4 16zM13 7l4 4"/>',
    save: '<path d="M5 3h11l3 3v15H5zM8 3v5h7V3M8 21v-7h8v7"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
    file: '<path d="M6 3h8l4 4v14H6zM14 3v4h4"/>',
    flag: '<path d="M5 21V4M5 4h12l-2 4 2 4H5"/>'
  };
  window.ic = function (name, cls) {
    return '<svg class="i ' + (cls || '') + '" viewBox="0 0 24 24" aria-hidden="true">' + P[name] + '</svg>';
  };

  window.toast = function (msg) {
    let t = document.getElementById('toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 2200);
  };

  const HIST = [
    { id: 'run', href: 'running.html', title: 'Backend and data infrastructure roles · Remote US', st: 'run', when: 'Searching… 4 of 5 steps' },
    { id: 'a', href: 'results.html', title: 'Software engineering roles, particularly in agentic AI… · New York, NY', st: 'done', when: 'Yesterday, 3:45 PM · 6 companies' },
    { id: 'b', href: 'results.html', title: 'Platform engineer at climate startups · Brooklyn, NY', st: 'done', when: 'Nov 11, 9:10 AM · 5 companies' },
    { id: 'c', href: 'running.html', title: 'ML research engineer, healthcare · Boston, MA', st: 'err', when: 'Failed · Nov 9' },
    { id: 'd', href: 'running.html', title: 'Quant developer · Chicago, IL', st: 'can', when: 'Cancelled · Nov 7' }
  ];

  window.NA = window.NA || {};
  NA.shell = function (opt) {
    const side = document.getElementById('side');
    const nav = document.getElementById('nav');
    const li = HIST.map(h => {
      const act = h.id === opt.active;
      const label = { run: 'Searching', err: 'Failed', can: 'Cancelled', done: '' }[h.st];
      return '<li class="' + (act ? 'active' : '') + '" data-id="' + h.id + '">' +
        '<a class="h-main" href="' + h.href + '"' + (act ? ' aria-current="page"' : '') + '>' + h.title +
        '<span class="h-meta"><span class="dot ' + (h.st === 'run' ? 'run' : h.st === 'err' ? 'err' : h.st === 'can' ? 'can' : '') + '"></span>' + h.when + '</span></a>' +
        (h.st === 'run'
          ? '<button class="btn btn-ghost btn-sm h-cancel" data-cancel>' + ic('x') + ' Cancel search</button>'
          : '<button class="h-del" data-del aria-label="Delete search: ' + h.title.replace(/"/g, '') + '">' + ic('trash') + '</button>') +
        '</li>';
    }).join('');
    side.innerHTML =
      '<a class="brand" href="search.html"><span class="mark">' + ic('spark').replace('class="i "', 'class="i fill" style="width:18px;height:18px"') + '</span>Networking Agent</a>' +
      '<a class="btn btn-primary" href="search.html">' + ic('plus') + ' New search</a>' +
      '<h2 id="hist-h">Previous searches</h2><ul class="hist" aria-labelledby="hist-h">' + li + '</ul>' +
      '<div class="me"><span class="avatar" aria-hidden="true">TU</span>Test User</div>';
    const links = [['search', 'Search', 'search', 'search.html'], ['companies', 'Companies', 'building', 'library.html?type=companies'], ['jobs', 'Jobs', 'briefcase', 'library.html?type=jobs'], ['people', 'People', 'user', 'library.html?type=people']];
    nav.innerHTML = '<button class="menu-btn" aria-label="Open previous searches" aria-controls="side" data-menu>' + ic('menu') + '</button>' +
      links.map(l => '<a class="tab" href="' + l[3] + '"' + (opt.nav === l[0] ? ' aria-current="page"' : '') + '>' + ic(l[2]) + '<span class="lbl">' + l[1] + '</span></a>').join('') +
      '<span class="spacer"></span><span class="pill p-pinned">' + ic('pin', 'fill') + ' TEST_USER</span>';

    let scrim = document.querySelector('.scrim');
    if (!scrim) { scrim = document.createElement('div'); scrim.className = 'scrim'; document.body.appendChild(scrim); }
    const setMenu = o => { side.classList.toggle('open', o); scrim.classList.toggle('open', o); };
    nav.querySelector('[data-menu]').onclick = () => setMenu(true);
    scrim.onclick = () => setMenu(false);

    side.addEventListener('click', e => {
      const del = e.target.closest('[data-del]');
      if (del) {
        const li = del.closest('li'); del.hidden = true;
        const c = document.createElement('div'); c.className = 'h-confirm';
        c.innerHTML = 'Delete this search? <button class="btn btn-ghost btn-sm" data-keep>Keep</button><button class="btn btn-danger btn-sm" data-yes>Delete</button>';
        li.appendChild(c); c.querySelector('[data-keep]').focus();
      }
      if (e.target.closest('[data-keep]')) { const li = e.target.closest('li'); li.querySelector('[data-del]').hidden = false; li.querySelector('.h-confirm').remove(); }
      if (e.target.closest('[data-yes]')) { e.target.closest('li').remove(); toast('Search deleted'); }
      if (e.target.closest('[data-cancel]')) { document.dispatchEvent(new CustomEvent('na-cancel')); toast('Search cancelled'); }
    });
  };
})();
