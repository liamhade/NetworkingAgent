/* Shared app shell for the mockup: icons, sidebar (Previous Searches), top nav, toast. */
(function(){
const P={
 building:'<path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16M14 10h5a1 1 0 0 1 1 1v10M2 21h20M8 8h2M8 12h2M8 16h2"/>',
 briefcase:'<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2M3 13h18"/>',
 user:'<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6"/>',
 search:'<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
 pin:'<path d="M12 17v5M8 3h8l-1 6 3 4H6l3-4z"/>',
 check:'<path d="m5 12 5 5 9-10"/>',
 plus:'<path d="M12 5v14M5 12h14"/>',
 copy:'<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h8"/>',
 ext:'<path d="M14 4h6v6M20 4 10 14M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
 chev:'<path d="m6 9 6 6 6-6"/>',
 x:'<path d="M6 6l12 12M18 6 6 18"/>',
 trash:'<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
 menu:'<path d="M4 7h16M4 12h16M4 17h16"/>',
 spark:'<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/>',
 send:'<path d="M21 3 10 14M21 3l-7 18-4-7-7-4z"/>',
 leaf:'<path d="M5 19c0-9 5-14 15-14 0 10-5 15-14 15M5 19c2-5 5-8 9-10"/>',
 arrow:'<path d="M5 12h14M13 6l6 6-6 6"/>',
 link:'<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3A4 4 0 0 0 11 18.700l1-1"/>',
 upload:'<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>',
 clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
 pen:'<path d="M4 20l4-1L19 8l-3-3L5 16z"/>',
 stop:'<rect x="6" y="6" width="12" height="12" rx="2"/>',
 pin2:'<path d="M12 21s7-6.2 7-11a7 7 0 0 0-14 0c0 4.800 7 11 7 11z"/><circle cx="12" cy="10" r="2.500"/>'
};
window.ic=(n,c)=>'<svg class="i '+(c||'')+'" viewBox="0 0 24 24" aria-hidden="true">'+P[n]+'</svg>';

const HIST=[
 {id:'a',t:'Software engineering roles, particularly in agentic AI, LLM applications and backend… · New York, NY',m:'Yesterday, 3:45 PM',s:'done',href:'results.html'},
 {id:'b',t:'Backend engineer, climate tech · Remote (US)',m:'Searching… step 3 of 5',s:'run',href:'running.html'},
 {id:'c',t:'Data platform roles at growth-stage startups · Boston, MA',m:'Nov 12 · Cancelled',s:'off',href:'results.html'},
 {id:'d',t:'ML infrastructure engineer · San Francisco, CA',m:'Nov 9 · Failed',s:'bad',href:'results.html'}
];
window.Shell={
 init(o){
  o=o||{};
  const side=document.getElementById('side');
  side.innerHTML=`
   <a class="brand" href="search.html"><span class="logo">${ic('leaf')}</span>Networking Agent</a>
   <a class="newbtn" href="search.html">${ic('plus')} New search</a>
   <div><h2 id="hist-h">Previous searches</h2>
   <ul class="hist" aria-labelledby="hist-h">${HIST.map(h=>`
     <li data-id="${h.id}"><a class="h" href="${h.href}" ${o.current===h.id?'aria-current="page"':''}>
        <span class="t">${h.t}</span><span class="m"><span class="dot ${h.s==='run'?'run':h.s==='bad'?'bad':h.s==='off'?'off':''}"></span>${h.m}</span></a>
       <button class="x" aria-label="${h.s==='run'?'Cancel search':'Delete search'}: ${h.t.replace(/"/g,'')}">${ic(h.s==='run'?'stop':'trash')}</button>
       <div class="confirm"><span>${h.s==='run'?'Cancel this search?':'Delete this search?'}</span><button class="keep">Keep</button><button class="del">${h.s==='run'?'Cancel':'Delete'}</button></div></li>`).join('')}
   </ul></div>
   <div class="me"><span class="av">TU</span><div><div style="font-weight:600;line-height:1.2">Test User</div><div style="font-size:12.5px;color:#B7CDBC">TEST_USER account</div></div></div>`;
  side.querySelectorAll('.hist li').forEach(li=>{
    li.querySelector('.x').onclick=()=>{li.classList.add('asking');li.querySelector('.keep').focus()};
    li.querySelector('.keep').onclick=()=>li.classList.remove('asking');
    li.querySelector('.del').onclick=()=>{li.remove();Shell.toast('Done. Removed from Previous searches.')};
  });
  const nav=document.getElementById('topnav');
  const items=[['search','Search','search.html','search'],['companies','Companies','results.html#companies','building'],['jobs','Jobs','results.html#jobs','briefcase'],['people','People','results.html#people','user']];
  nav.innerHTML=`<button class="menu" id="menubtn" aria-label="Open previous searches" aria-expanded="false">${ic('menu')}</button>`+
    items.map(i=>`<a class="nl" href="${i[2]}" ${o.active===i[0]?'aria-current="page"':''}>${ic(i[3])}${i[1]}</a>`).join('');
  const scrim=document.getElementById('scrim'),mb=document.getElementById('menubtn');
  const close=()=>{side.classList.remove('open');scrim.classList.remove('show');mb.setAttribute('aria-expanded','false')};
  mb.onclick=()=>{const o=side.classList.toggle('open');scrim.classList.toggle('show',o);mb.setAttribute('aria-expanded',o)};
  scrim.addEventListener('click',close);
 },
 toast(msg){
  let t=document.getElementById('toast');
  if(!t){t=document.createElement('div');t.id='toast';t.className='toast';t.setAttribute('role','status');document.body.appendChild(t)}
  t.textContent=msg;t.classList.add('show');clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove('show'),2600);
 }
};
})();
