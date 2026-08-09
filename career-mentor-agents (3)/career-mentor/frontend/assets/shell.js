// ---- shared app-shell (sidebar/topbar) + small view helpers ----
const NAV_ITEMS = [
  {key:'dashboard', label:'Dashboard',            href:'dashboard.html'},
  {key:'career',    label:'Career',               href:'career.html'},
  {key:'skillgap',  label:'Skill gap',             href:'skillgap.html'},
  {key:'roadmap',   label:'Roadmap',               href:'roadmap.html'},
  {key:'courses',   label:'Courses',               href:'courses.html'},
  {key:'projects',  label:'Projects',              href:'projects.html'},
  {key:'quiz',      label:'Practice · Quiz',       href:'quiz.html'},
  {key:'interview', label:'Practice · Interview',  href:'interview.html'},
  {key:'progress',  label:'Progress',              href:'progress.html'},
  {key:'settings',  label:'Settings',               href:'settings.html'},
];

function renderSidebar(activeKey){
  const el = document.getElementById('sidebarSlot');
  if(!el) return;
  el.innerHTML =
    `<div class="logo"><span class="display" style="color:var(--ember);">●</span><span class="display" style="font-size:16px;">Career Mentor</span></div>` +
    NAV_ITEMS.map(n => `<a class="navitem${n.key===activeKey?' active':''}" href="${n.href}">${n.label}</a>`).join('');
}

function renderTopbar(){
  const el = document.getElementById('topbarSlot');
  if(!el) return;
  el.innerHTML = `
    <input placeholder="Search..." class="focus-ring">
    <div style="display:flex; align-items:center; gap:6px;">
      <button class="icon-btn focus-ring" onclick="toggleTheme()">☾</button>
      <button class="icon-btn focus-ring">🔔</button>
      <div class="avatar" id="avatarInitial">·</div>
    </div>`;
}

function toggleTheme(){
  document.body.classList.toggle('light');
  localStorage.setItem('cm_theme', document.body.classList.contains('light') ? 'light' : 'dark');
}
function applySavedTheme(){
  if(localStorage.getItem('cm_theme') === 'light'){ document.body.classList.add('light'); }
}

function trailHTML(doneCount, total, labels){
  let html='';
  labels.forEach((label,i)=>{
    const state = i<doneCount ? 'done' : (i===doneCount ? 'current pulse' : '');
    html += `<div class="wp"><div class="wp-dot ${state}"></div><div class="wp-label">${label}</div></div>`;
    if(i<labels.length-1){ html += `<div class="wp-line ${i<doneCount-1?'done':''}"></div>`; }
  });
  return html;
}

// kept as a compatibility shim from the original SPA — renders everything, no real pagination
function makePager(containerEl, pagerEl, items, pageSize, renderItem){
  containerEl.innerHTML = items.map(renderItem).join('') || '<div style="color:var(--mist); font-size:13px;">Nothing here yet.</div>';
  if(pagerEl) pagerEl.innerHTML = '';
}

// Runs a page's data-loading function and, if it throws (e.g. the API is
// unreachable because this file was opened directly instead of via the
// FastAPI server), shows a clear on-page banner instead of leaving the
// page silently blank.
async function safeRun(activeKey, loaderFn){
  try{
    await initShell(activeKey);
    await loaderFn();
  }catch(e){
    const main = document.querySelector('.main') || document.body;
    const banner = document.createElement('div');
    banner.className = 'card';
    banner.style.cssText = 'border-color:var(--danger,#e5484d); color:var(--danger,#e5484d); margin-bottom:16px;';
    banner.innerHTML = `<strong>Couldn't load this page.</strong><br><span style="font-size:13px;">`
      + `${(e && e.message) || 'Unknown error'}. Make sure you opened this app at `
      + `<code>http://localhost:8000</code> (started via <code>uvicorn main:app</code>), `
      + `not as a local file — the API calls need to be served from the same origin.</span>`;
    main.prepend(banner);
  }
}

// Renders the sidebar/topbar for the given active page, loads /api/me for the avatar.
// Call this once, near the top of each app-shell page's own script.
async function initShell(activeKey){
  applySavedTheme();
  renderSidebar(activeKey);
  renderTopbar();
  try{
    const me = await api('/api/me');
    const avatarEl = document.getElementById('avatarInitial');
    if(avatarEl) avatarEl.textContent = me.email[0].toUpperCase();
    return me;
  }catch(e){
    // api() already redirects to login.html on 401
    return null;
  }
}
