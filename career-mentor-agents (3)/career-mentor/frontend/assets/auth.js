// ---- login/register page ----
let isRegisterMode = false;

function toggleAuthMode(){
  isRegisterMode = !isRegisterMode;
  document.getElementById('authTitle').textContent = isRegisterMode ? "Create an account" : "Sign in";
  document.getElementById('authSubmit').textContent = isRegisterMode ? "Register" : "Sign in";
  document.getElementById('authToggleText').textContent = isRegisterMode ? "Already have an account?" : "New here?";
  document.getElementById('authToggleLink').textContent = isRegisterMode ? "Sign in" : "Create an account";
  document.getElementById('authErr').textContent = "";
  document.getElementById('trackField').style.display = isRegisterMode ? 'block' : 'none';
}

async function submitAuth(){
  const email = document.getElementById('authEmail').value.trim();
  const password = document.getElementById('authPassword').value;
  const errEl = document.getElementById('authErr');
  errEl.textContent = "";
  if(!email || !password){ errEl.textContent = "Enter both email and password."; return; }
  try{
    const path = isRegisterMode ? "/api/auth/register" : "/api/auth/login";
    const payload = {email, password};
    if(isRegisterMode){ payload.track = document.getElementById('authTrack').value; }
    const res = await fetch(API + path, {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if(!res.ok){ errEl.textContent = data.detail || "Something went wrong."; return; }
    setToken(data.token);
    await routeAfterAuth();
  }catch(e){ errEl.textContent = "Could not reach the server."; }
}

// Decide which page to land on after a successful login/register, or on repeat visits
// to login.html while already signed in.
async function routeAfterAuth(){
  try{
    const status = await api('/api/onboarding/status');
    if(!status.resume_done){ location.href = 'resume.html'; }
    else if(!status.profile_done){ location.href = 'profile.html'; }
    else { location.href = 'dashboard.html'; }
  }catch(e){ /* api() redirects to login.html on 401 */ }
}

// Called on login.html load: if already signed in, skip straight past the login form.
async function redirectIfAlreadyAuthed(){
  if(isLoggedIn()){ await routeAfterAuth(); }
}

// ---- resume upload page ----
const MAX_RESUME_BYTES = 10 * 1024 * 1024; // 10MB
const ALLOWED_RESUME_EXT = ['.pdf', '.doc', '.docx'];

function triggerFileSelect(){
  document.getElementById('resumeFileInput').click();
}

function initResumeUpload(){
  const input = document.getElementById('resumeFileInput');
  const dropzone = document.getElementById('dropzone');

  input.addEventListener('change', (e)=>{
    const file = e.target.files && e.target.files[0];
    if(file) handleResumeFile(file);
  });

  // real drag-and-drop support
  ['dragover','dragenter'].forEach(evt=>{
    dropzone.addEventListener(evt, (e)=>{
      e.preventDefault();
      dropzone.style.borderColor = 'var(--ember)';
    });
  });
  ['dragleave','dragend'].forEach(evt=>{
    dropzone.addEventListener(evt, (e)=>{
      e.preventDefault();
      dropzone.style.borderColor = 'var(--panelBorder)';
    });
  });
  dropzone.addEventListener('drop', (e)=>{
    e.preventDefault();
    dropzone.style.borderColor = 'var(--panelBorder)';
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if(file) handleResumeFile(file);
  });
}

function validateResumeFile(file){
  const name = file.name.toLowerCase();
  const okExt = ALLOWED_RESUME_EXT.some(ext => name.endsWith(ext));
  if(!okExt) return `Please choose a PDF, DOC, or DOCX file.`;
  if(file.size > MAX_RESUME_BYTES) return `That file is too large — max 10MB.`;
  return null;
}

async function handleResumeFile(file){
  const errEl = document.getElementById('uploadErr');
  errEl.textContent = '';
  const problem = validateResumeFile(file);
  if(problem){ errEl.textContent = problem; return; }

  document.getElementById('dropzone').style.display='none';
  document.getElementById('fileChip').style.display='flex';
  document.getElementById('fileChipName').textContent = file.name;
  document.getElementById('progressBar').style.display='block';
  setTimeout(()=>{document.getElementById('progressFill').style.width='100%';},20);

  try{
    const formData = new FormData();
    formData.append('file', file, file.name);
    const data = await api('/api/onboarding/resume', {method:'POST', body: formData});
    setTimeout(()=>{
      document.getElementById('parsedPreview').style.display='block';
      document.getElementById('parsedSkills').innerHTML = data.skills.length
        ? data.skills.map(s=>`<span class="pill pill-signal">${s}</span>`).join('')
        : '<span class="pill pill-mist">No recognized skills found — you can still continue</span>';
      document.getElementById('parsedScore').textContent = data.resume_score + "/100";
      document.getElementById('continueBtn').disabled=false;
    },250);
  }catch(e){
    errEl.textContent = "Could not upload your resume — try again.";
    resetUpload();
  }
}

async function skipResume(){
  // Guard: if a resume was already successfully parsed on this page, treat
  // "I don't have a resume yet" as a destructive action and confirm first —
  // it's positioned right next to "Continue to profile" and an accidental
  // click would silently throw away real analysis (score, detected skills,
  // and the personalized roadmap built from them).
  const alreadyParsed = document.getElementById('parsedPreview') &&
    document.getElementById('parsedPreview').style.display !== 'none';
  if(alreadyParsed){
    const ok = confirm("You already uploaded a resume and it was analyzed successfully. " +
      "Skipping now will discard that analysis and reset your dashboard, skill gap, " +
      "and roadmap to generic defaults. Continue anyway?");
    if(!ok) return;
  }
  await api('/api/onboarding/resume/skip', {method:'POST'});
  location.href = 'profile.html';
}
function resetUpload(){
  document.getElementById('dropzone').style.display='block';
  document.getElementById('fileChip').style.display='none';
  document.getElementById('progressBar').style.display='none';
  document.getElementById('progressFill').style.width='0%';
  document.getElementById('parsedPreview').style.display='none';
  document.getElementById('continueBtn').disabled=true;
  document.getElementById('resumeFileInput').value = '';
}

// ---- profile wizard page ----
const qFields=["highest_qualification","degree_branch","institution","graduation_year","current_skills"];
const questions=[
  "What's your highest qualification?","What's your degree and branch?",
  "Which institution do you study at?","What's your graduation year?",
  "What skills do you already have?"
];
let qIndex=0; const qAnswers={};

function renderQ(){
  document.getElementById('qCounter').textContent='Question '+(qIndex+1)+' of '+questions.length;
  document.getElementById('qText').textContent=questions[qIndex];
  document.getElementById('qInput').value = qAnswers[qFields[qIndex]] || "";
  document.getElementById('qProgress').style.width=Math.round(((qIndex+1)/questions.length)*100)+'%';
  document.getElementById('nextBtn').textContent = qIndex===questions.length-1 ? 'Build my profile' : 'Next';
  const errEl = document.getElementById('qError');
  if(errEl) errEl.textContent = "";
}
async function nextQ(){
  const val = document.getElementById('qInput').value.trim();
  if(!val){
    showQError("Please enter an answer before continuing.");
    return;
  }
  qAnswers[qFields[qIndex]] = val;
  if(qIndex<questions.length-1){ qIndex++; renderQ(); }
  else{
    const btn = document.getElementById('nextBtn');
    btn.disabled = true;
    try{
      await agent('profile', qAnswers);
      location.href = 'dashboard.html';
    }catch(e){
      showQError(e.message || "Could not save your profile — please try again.");
      btn.disabled = false;
    }
  }
}
function showQError(msg){
  let el = document.getElementById('qError');
  if(!el){
    el = document.createElement('div');
    el.id = 'qError';
    el.style.cssText = 'color:#ff6b6b; font-size:13px; margin-top:10px;';
    document.getElementById('qInput').insertAdjacentElement('afterend', el);
  }
  el.textContent = msg;
}
function prevQ(){
  if(qIndex>0){ qAnswers[qFields[qIndex]] = document.getElementById('qInput').value; qIndex--; renderQ(); }
  else { location.href = 'resume.html'; }
}
