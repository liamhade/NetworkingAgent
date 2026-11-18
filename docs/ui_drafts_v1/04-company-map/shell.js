/* Shared app shell: icon sprite, top nav, Previous Searches sidebar. Mockup only. */
(function () {
  var icons = {
    building: '<path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16M14 9h5a1 1 0 0 1 1 1v11M2 21h20M8 8h2M8 12h2M8 16h2"/>',
    briefcase: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M3 13h18"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18 14.8c2.2.6 3.5 2.3 3.5 5.2"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    pin: '<path d="M9 4h6l-1 6 3 3v2H7v-2l3-3-1-6ZM12 15v6"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    chevron: '<path d="m6 9 6 6 6-6"/>',
    copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
    ext: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    send: '<path d="m21 3-9.5 18-2.5-7.5L1.5 11 21 3ZM9 13.5 21 3"/>',
    x: '<path d="m6 6 12 12M18 6 6 18"/>',
    sparkle: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3ZM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16Z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14-4L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    pin2: '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.5"/>',
    upload: '<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
    edit: '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4Z"/>',
    save: '<path d="M5 4h11l3 3v13H5V4ZM8 4v5h7V4M8 20v-6h8v6"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    layers: '<path d="m12 3 9 5-9 5-9-5 9-5ZM3 13l9 5 9-5"/>',
    list: '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
    alert: '<path d="M12 4 2.5 20h19L12 4ZM12 10v4M12 17.5h.01"/>',
    filter: '<path d="M3 5h18l-7 8v6l-4 2v-8L3 5Z"/>',
    expand: '<path d="m7 9 5-5 5 5M7 15l5 5 5-5"/>',
    collapse: '<path d="m7 4 5 5 5-5M7 20l5-5 5 5"/>'
  };
  var sprite = '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">';
  for (var k in icons) sprite += '<symbol id="i-' + k + '" viewBox="0 0 24 24">' + icons[k] + '</symbol>';
  sprite += '</svg>';
  document.body.insertAdjacentHTML('afterbegin', sprite);
  window.ic = function (n, c) { return '<svg class="i ' + (c || '') + '" aria-hidden="true"><use href="#i-' + n + '"/></svg>'; };
  window.esc = function (s) { return String(s).replace(/[&<>"]/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]; }); };

  var page = document.body.dataset.page || 'search';     // search | results | running | library
  var lib = (location.hash || '').replace('#', '');
  var navs = [
    ['search.html', 'search', 'Search', page === 'search' || page === 'results' || page === 'running'],
    ['library.html#companies', 'building', 'Companies', page === 'library' && lib === 'companies'],
    ['library.html#jobs', 'briefcase', 'Jobs', page === 'library' && lib === 'jobs'],
    ['library.html#people', 'users', 'People', page === 'library' && lib === 'people']
  ];

  var top = document.createElement('header');
  top.className = 'topbar';
  top.innerHTML =
    '<a class="skip" href="#main">Skip to content</a>' +
    '<button class="ibtn menu-btn" id="menuBtn" aria-label="Open previous searches" aria-controls="side">' + ic('menu', 'lg') + '</button>' +
    '<a class="brand" href="search.html"><span class="brand-mark">' + ic('layers') + '</span><span class="tx">Networking Agent</span></a>' +
    '<nav class="nav" aria-label="Primary">' + navs.map(function (n) {
      return '<a href="' + n[0] + '"' + (n[3] ? ' aria-current="page"' : '') + ' data-nav="' + n[1] + '">' + ic(n[1]) + '<span class="lbl">' + n[2] + '</span></a>';
    }).join('') + '</nav><span class="sp"></span>' +
    '<div class="user"><span class="nm">TEST_USER</span><span class="avatar" aria-hidden="true">TU</span></div>';
  document.body.insertBefore(top, document.body.firstChild.nextSibling);

  var hist = [
    { id: 'a', t: 'Agentic AI and backend engineering roles, Python or C++ · New York, NY', s: 'done', d: 'Yesterday, 3:45 PM', n: '6 co.', href: 'results.html', cur: page === 'results' },
    { id: 'r', t: 'Product designer roles at fintech startups · Seattle, WA', s: 'run', d: 'Searching…', n: '', href: 'running.html', cur: page === 'running' },
    { id: 'b', t: 'Data analyst roles in healthcare · Boston, MA', s: 'done', d: 'Nov 12, 10:02 AM', n: '4 co.', href: 'results.html' },
    { id: 'c', t: 'ML platform engineer, remote friendly', s: 'can', d: 'Cancelled · Nov 10', n: '', href: 'results.html' },
    { id: 'd', t: 'Backend roles · Austin, TX', s: 'err', d: 'Failed · Nov 9', n: '', href: 'results.html' }
  ];
  function histHtml() {
    return hist.map(function (h) {
      var label = { done: 'Done', run: 'Searching', can: 'Cancelled', err: 'Failed' }[h.s];
      var act = h.confirm
        ? '<div class="m" style="padding:0 12px 8px"><span>Delete this search?</span><button class="btn xs" data-keep="' + h.id + '">Keep</button><button class="btn xs danger" data-del="' + h.id + '">Delete</button></div>'
        : (h.s === 'run'
          ? '<button class="x stop" data-cancel="' + h.id + '" aria-label="Cancel search: ' + esc(h.t) + '">' + ic('stop', 'sm') + '</button>'
          : '<button class="x" data-ask="' + h.id + '" aria-label="Delete search: ' + esc(h.t) + '">' + ic('trash', 'sm') + '</button>');
      return '<li><a class="h" href="' + h.href + '"' + (h.cur ? ' aria-current="page"' : '') + '><div class="t">' + esc(h.t) + '</div>' +
        '<div class="m"><span class="dot ' + h.s + '" aria-hidden="true"></span><span>' + (h.s === 'run' ? 'Searching…' : (h.s === 'done' ? h.d : h.d)) + '</span>' +
        '<span class="sr">Status: ' + label + '</span>' + (h.n ? '<span class="cnt num">' + h.n + '</span>' : '') + '</div></a>' + act + '</li>';
    }).join('');
  }
  var side = document.createElement('aside');
  side.className = 'side'; side.id = 'side'; side.setAttribute('aria-label', 'Previous searches');
  side.innerHTML = '<a class="btn pri" href="search.html">' + ic('plus') + ' New search</a><h2>Previous searches</h2><ul class="hist" id="hist"></ul>' +
    '<div class="side-foot">Signed in as <b>TEST_USER</b><br>Local database (POC)</div>';
  var main = document.getElementById('main');
  var shell = document.createElement('div'); shell.className = 'shell';
  var scrim = document.createElement('div'); scrim.className = 'scrim';
  main.before(shell); shell.append(side, main); document.body.append(scrim);
  function draw() { document.getElementById('hist').innerHTML = histHtml(); }
  draw();
  side.addEventListener('click', function (e) {
    var b = e.target.closest('button'); if (!b) return;
    var id = b.dataset.ask || b.dataset.keep || b.dataset.del || b.dataset.cancel;
    var h = hist.filter(function (x) { return x.id === id; })[0];
    if (b.dataset.ask) h.confirm = true;
    if (b.dataset.keep) h.confirm = false;
    if (b.dataset.del) hist = hist.filter(function (x) { return x !== h; });
    if (b.dataset.cancel) { h.s = 'can'; h.d = 'Cancelled · just now'; if (window.onHistCancel) window.onHistCancel(); }
    draw();
  });
  function toggle(o) { side.classList.toggle('open', o); scrim.classList.toggle('open', o); document.getElementById('menuBtn').setAttribute('aria-expanded', o); }
  document.getElementById('menuBtn').addEventListener('click', function () { toggle(!side.classList.contains('open')); });
  scrim.addEventListener('click', function () { toggle(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') toggle(false); });

  window.toast = function (msg, undo) {
    var t = document.getElementById('toast');
    if (!t) { t = document.createElement('div'); t.id = 'toast'; t.className = 'toast'; t.setAttribute('role', 'status'); document.body.append(t); }
    t.innerHTML = '<span>' + msg + '</span>' + (undo ? '<button type="button" id="toastUndo">Undo</button>' : '');
    if (undo) t.querySelector('#toastUndo').onclick = function () { undo(); t.classList.remove('show'); };
    t.classList.add('show'); clearTimeout(t._h); t._h = setTimeout(function () { t.classList.remove('show'); }, 4200);
  };
})();
