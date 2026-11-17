/* Shared shell: icons, theme, top bar, Previous Searches sidebar, command palette, toasts. */
window.CC = (function () {
  const P = {
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    building: '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
    briefcase: '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/>',
    user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    external: '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    plus: '<path d="M5 12h14M12 5v14"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    down: '<path d="m6 9 6 6 6-6"/>',
    right: '<path d="m9 18 6-6-6-6"/>',
    back: '<path d="m15 18-6-6 6-6"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2m-7.07-2.93 1.41-1.41m11.32-11.32 1.41-1.41M2 12h2m16 0h2M4.93 4.93l1.41 1.41m11.32 11.32 1.41 1.41"/>',
    moon: '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    trash: '<path d="M3 6h18M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    save: '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2zM17 21v-8H7v8M7 3v5h8"/>',
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/>',
    menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
    clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    sparkle: '<path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/><path d="M19 17v4M17 19h4"/>',
    send: '<path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/>',
    link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    pin: '<path d="M12 17v5M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/>',
    loader: '<path d="M21 12a9 9 0 1 1-6.2-8.55"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5"/>',
    cmd: '<path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3"/>',
    rows: '<path d="M3 6h18M3 12h18M3 18h18"/>',
    tree: '<path d="M3 5h7M6 5v14M6 12h6M6 19h6M15 12h6M15 19h6"/>',
    chevs: '<path d="m7 8 5-5 5 5M7 16l5 5 5-5"/>',
    chevsin: '<path d="m7 4 5 5 5-5M7 20l5-5 5 5"/>'
  };
  const icon = (n, cls) => '<svg class="i ' + (cls || '') + '" viewBox="0 0 24 24" aria-hidden="true">' + (P[n] || '') + '</svg>';
  const hydrate = (root) => (root || document).querySelectorAll('[data-icon]').forEach(el => { el.outerHTML = icon(el.dataset.icon, el.className.baseVal || el.getAttribute('class') || ''); });
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform);
  const mod = isMac ? '⌘' : 'Ctrl';

  /* theme */
  const ls = { get: (k) => { try { return localStorage.getItem(k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} } };
  function setTheme(t) { document.documentElement.setAttribute('data-theme', t); ls.set('cnt-theme', t);
    document.querySelectorAll('.theme-toggle button').forEach(b => b.setAttribute('aria-pressed', b.dataset.set === t)); }
  document.documentElement.setAttribute('data-theme', ls.get('cnt-theme') || 'light');
  const theme = () => document.documentElement.getAttribute('data-theme');

  /* toast */
  function toast(msg, actionLabel, action) {
    let box = document.querySelector('.toasts');
    if (!box) { box = document.createElement('div'); box.className = 'toasts'; box.setAttribute('role', 'status'); box.setAttribute('aria-live', 'polite'); document.body.appendChild(box); }
    const t = document.createElement('div'); t.className = 'toast'; t.innerHTML = '<span>' + esc(msg) + '</span>';
    if (actionLabel) { const b = document.createElement('button'); b.textContent = actionLabel; b.onclick = () => { action && action(); t.remove(); }; t.appendChild(b); }
    box.appendChild(t); setTimeout(() => t.remove(), 4200);
  }

  /* persisted entity state (shared between pages) */
  const saved = (() => { try { return JSON.parse(ls.get('cnt-state') || 'null'); } catch (e) { return null; } })();
  const state = saved || JSON.parse(JSON.stringify(DATA.state));
  const persist = () => ls.set('cnt-state', JSON.stringify(state));

  /* top bar */
  function renderTop() {
    const el = document.getElementById('topbar'); if (!el) return;
    const page = document.body.dataset.page;
    const nav = [['search', 'search.html', 'search', 'Search'], ['companies', 'library.html?t=companies', 'building', 'Companies'], ['jobs', 'library.html?t=jobs', 'briefcase', 'Jobs'], ['people', 'library.html?t=people', 'user', 'People']];
    const lib = new URLSearchParams(location.search).get('t') || 'companies';
    const active = page === 'library' ? lib : 'search';
    el.innerHTML =
      '<button class="icon-btn menu-btn" id="menuBtn" aria-label="Open previous searches">' + icon('menu') + '</button>' +
      '<a class="brand" href="search.html"><span class="brand-mark">' + icon('sparkle') + '</span><span>Networking Agent</span></a>' +
      '<nav class="topnav" aria-label="Primary">' + nav.map(n => '<a href="' + n[1] + '"' + (n[0] === active ? ' aria-current="page"' : '') + '>' + icon(n[2]) + '<span>' + n[3] + '</span></a>').join('') + '</nav>' +
      '<div class="top-right">' +
      '<button class="cmdk" id="cmdkBtn" aria-label="Open command palette">' + icon('search') + '<span>Search or jump to...</span><kbd>' + mod + ' K</kbd></button>' +
      '<div class="theme-toggle" role="group" aria-label="Theme">' +
      '<button data-set="light" aria-pressed="true" title="Light (linen)">' + icon('sun') + '<span>Light</span></button>' +
      '<button data-set="dark" aria-pressed="false" title="Dark (warm)">' + icon('moon') + '<span>Dark</span></button></div></div>';
    el.querySelectorAll('.theme-toggle button').forEach(b => b.onclick = () => setTheme(b.dataset.set));
    setTheme(theme());
    document.getElementById('cmdkBtn').onclick = openPalette;
    document.getElementById('menuBtn').onclick = () => toggleSide(true);
  }
  function toggleSide(open) {
    const s = document.getElementById('side'), sc = document.getElementById('scrim');
    if (!s) return; s.classList.toggle('open', open); sc && sc.classList.toggle('open', open);
  }

  /* previous searches sidebar */
  let hist = DATA.history.slice(); let confirming = null;
  function renderSide() {
    const el = document.getElementById('side'); if (!el) return;
    const page = document.body.dataset.page, pageId = document.body.dataset.search;
    const row = (h) => {
      const cur = (pageId && pageId === h.id) ? ' aria-current="page"' : '';
      if (confirming === h.id) return '<div class="hist-confirm" role="alertdialog" aria-label="Confirm delete"><span style="flex:1">Delete this search?</span><button class="btn sm" data-h="keep">Keep</button><button class="btn sm danger" data-h="del" data-id="' + h.id + '">Delete</button></div>';
      const act = h.status === 'running'
        ? '<button class="icon-btn" data-h="cancel" data-id="' + h.id + '" aria-label="Cancel search: ' + esc(h.title) + '" title="Cancel search">' + icon('stop') + '</button>'
        : '<button class="icon-btn" data-h="ask" data-id="' + h.id + '" aria-label="Delete search: ' + esc(h.title) + '" title="Delete">' + icon('trash') + '</button>';
      return '<div class="hist-wrap"><a class="hist" href="' + h.href + '"' + cur + '><span class="dot ' + h.status + '"></span><div class="hist-title">' + esc(h.title) + '</div><div class="hist-meta">' + esc(h.meta) + '</div></a><div class="hist-actions">' + act + '</div></div>';
    };
    const running = hist.filter(h => h.status === 'running'), rest = hist.filter(h => h.status !== 'running');
    el.innerHTML =
      '<div class="side-head"><a class="btn primary" style="width:100%" href="search.html">' + icon('plus') + 'New search <kbd style="margin-left:auto;background:transparent;color:inherit;border-color:currentColor;opacity:.7">N</kbd></a></div>' +
      '<div class="side-scroll"><nav aria-label="Previous searches">' +
      (running.length ? '<h2>Running</h2>' + running.map(row).join('') : '') +
      '<h2>Previous searches <span class="num">' + rest.length + '</span></h2>' + rest.map(row).join('') + '</nav></div>' +
      '<div class="side-foot"><span class="avatar">TU</span><div><div style="font-weight:600;line-height:1.2">Test User</div><div class="muted" style="font-size:12px">TEST_USER</div></div></div>';
    el.querySelectorAll('[data-h]').forEach(b => b.onclick = (e) => {
      const a = b.dataset.h, id = b.dataset.id;
      if (a === 'ask') confirming = id; else if (a === 'keep') confirming = null;
      else if (a === 'del') { hist = hist.filter(h => h.id !== id); confirming = null; toast('Search deleted'); }
      else if (a === 'cancel') { hist = hist.map(h => h.id === id ? Object.assign({}, h, { status: 'cancelled', meta: 'Just now · Cancelled' }) : h); toast('Search cancelled'); }
      renderSide();
    });
  }

  /* command palette */
  const providers = []; let palEl, palIdx = 0, palItems = [];
  function addCommands(fn) { providers.push(fn); }
  function baseCommands() {
    return [
      { g: 'Go to', label: 'New search', icon: 'plus', hint: 'N', run: () => location.href = 'search.html' },
      { g: 'Go to', label: 'Current results', icon: 'rows', run: () => location.href = 'results.html' },
      { g: 'Go to', label: 'Running search view', icon: 'loader', run: () => location.href = 'running.html' },
      { g: 'Go to', label: 'Companies library', icon: 'building', run: () => location.href = 'library.html?t=companies' },
      { g: 'Go to', label: 'Jobs library', icon: 'briefcase', run: () => location.href = 'library.html?t=jobs' },
      { g: 'Go to', label: 'People library', icon: 'user', run: () => location.href = 'library.html?t=people' },
      { g: 'Appearance', label: 'Switch to ' + (theme() === 'dark' ? 'light' : 'dark') + ' theme', icon: theme() === 'dark' ? 'sun' : 'moon', run: () => setTheme(theme() === 'dark' ? 'light' : 'dark') }
    ];
  }
  function openPalette() {
    if (!palEl) {
      palEl = document.createElement('div'); palEl.className = 'palette';
      palEl.innerHTML = '<div class="pal-box" role="dialog" aria-modal="true" aria-label="Command palette"><input id="palIn" placeholder="Type a command, company, job or person..." aria-label="Command" autocomplete="off"><ul class="pal-list" id="palList" role="listbox"></ul><div class="pal-foot"><span><kbd>↑</kbd> <kbd>↓</kbd> move</span><span><kbd>Enter</kbd> run</span><span><kbd>Esc</kbd> close</span></div></div>';
      document.body.appendChild(palEl);
      palEl.addEventListener('mousedown', e => { if (e.target === palEl) closePalette(); });
      const inp = palEl.querySelector('input');
      inp.addEventListener('input', renderPal);
      inp.addEventListener('keydown', e => {
        if (e.key === 'ArrowDown') { palIdx = Math.min(palIdx + 1, palItems.length - 1); renderPal(true); e.preventDefault(); }
        else if (e.key === 'ArrowUp') { palIdx = Math.max(palIdx - 1, 0); renderPal(true); e.preventDefault(); }
        else if (e.key === 'Enter') { const it = palItems[palIdx]; if (it) { closePalette(); it.run(); } }
        else if (e.key === 'Escape') closePalette();
      });
    }
    palEl.classList.add('open'); const inp = palEl.querySelector('input'); inp.value = ''; palIdx = 0; renderPal(); inp.focus();
  }
  function closePalette() { palEl && palEl.classList.remove('open'); }
  function renderPal(keep) {
    const q = palEl.querySelector('input').value.trim().toLowerCase();
    let all = baseCommands(); providers.forEach(p => { all = p().concat(all); });
    palItems = all.filter(c => !q || c.label.toLowerCase().includes(q) || (c.g || '').toLowerCase().includes(q)).slice(0, 40);
    if (!keep) palIdx = 0;
    let last = '', html = '';
    palItems.forEach((c, i) => {
      if (c.g !== last) { html += '<li class="pal-grp" role="presentation">' + esc(c.g) + '</li>'; last = c.g; }
      html += '<li role="option" data-i="' + i + '" aria-selected="' + (i === palIdx) + '">' + icon(c.icon || 'search') + '<span>' + esc(c.label) + '</span>' + (c.hint ? '<small><kbd>' + esc(c.hint) + '</kbd></small>' : '') + '</li>';
    });
    const list = palEl.querySelector('#palList'); list.innerHTML = html || '<li style="cursor:default" class="muted">No matches</li>';
    list.querySelectorAll('li[data-i]').forEach(li => li.onclick = () => { closePalette(); palItems[+li.dataset.i].run(); });
    const s = list.querySelector('[aria-selected="true"]'); s && s.scrollIntoView({ block: 'nearest' });
  }
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); (palEl && palEl.classList.contains('open')) ? closePalette() : openPalette(); return; }
    const t = e.target, typing = t && (/INPUT|TEXTAREA|SELECT/.test(t.tagName) || t.isContentEditable);
    if (!typing && !e.ctrlKey && !e.metaKey && !e.altKey && e.key.toLowerCase() === 'n' && document.body.dataset.page !== 'search') { location.href = 'search.html'; }
    if (e.key === 'Escape') toggleSide(false);
  });

  function init() {
    renderTop(); renderSide(); hydrate();
    const sc = document.getElementById('scrim'); if (sc) sc.onclick = () => toggleSide(false);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  return { icon, hydrate, esc, toast, setTheme, theme, state, persist, addCommands, openPalette, mod, toggleSide, ls };
})();
