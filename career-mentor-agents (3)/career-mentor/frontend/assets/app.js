// ---- per-page data loaders. Each function only touches DOM ids that exist on its own page. ----

async function loadDashboard(){
  const d = await api('/api/dashboard');
  document.getElementById('readinessNum').textContent = d.readiness + '%';
  document.getElementById('resumeScoreNum').textContent = d.resume_score > 0 ? d.resume_score + '/100' : 'Not uploaded';
  document.getElementById('dashMissing').innerHTML = d.missing_skills.map(s=>`<span class="pill pill-danger">${s.name}</span>`).join('');
  document.getElementById('dashRoadmap').textContent = `Day ${d.roadmap_progress.done} of ${d.roadmap_progress.total}`;
  document.getElementById('dashTasks').innerHTML = d.upcoming_tasks.map(t=>`<li>${t.title}</li>`).join('') || '<li>No tasks yet — generate a roadmap</li>';
  document.getElementById('dashTrail').innerHTML = trailHTML(2, 5, ['Resume','Skill gap','Roadmap','Interview','Offer']);
  document.getElementById('dashTrackPill').textContent = d.track_label || '';
}

async function loadCareer(){
  const d = await api('/api/career');
  const note = document.getElementById('careerNote');
  if(note){
    note.textContent = d.resume_based
      ? 'Ranked from the skills detected on your uploaded resume.'
      : 'Upload your resume to get recommendations tailored to your actual skills.';
  }
  makePager(document.getElementById('careerList'), document.getElementById('careerPager'), d.recommendations, 4, r=>`
    <div class="card" style="display:flex; justify-content:space-between; align-items:flex-start;">
      <div><div style="font-weight:600; font-size:16px;">${r.role} <span class="mono" style="font-size:10px; color:var(--mist); font-weight:400;">${r.track_label||''}</span></div>
      <p style="font-size:13px; color:var(--mist); margin:8px 0; max-width:460px;">${r.why}</p>
      <div style="display:flex; gap:6px; flex-wrap:wrap;">${r.skills.map(s=>`<span class="pill ${(r.matched_skills||[]).includes(s)?'pill-signal':'pill-mist'}">${s}</span>`).join('')}</div></div>
      <div class="display" style="font-size:26px; color:${r.score>75?'var(--ember)':'var(--mist)'};">${r.score}%</div>
    </div>`);
}

async function loadSkillGap(){
  const d = await agent('skillgap');
  const note = document.getElementById('skillgapNote');
  if(note){
    note.textContent = d.resume_based
      ? 'Based on the skills detected on your uploaded resume.'
      : 'Upload your resume for a gap analysis based on your actual skills.';
  }
  document.getElementById('strongSkills').innerHTML = d.strong_skills.length
    ? d.strong_skills.map(s=>`<span class="pill pill-signal">${s}</span>`).join('')
    : '<span class="pill pill-mist">None detected yet</span>';
  document.getElementById('missingSkills').innerHTML = d.missing_skills.map(s=>`<span class="pill pill-danger">${s.name} · ${s.priority}</span>`).join('');
  document.getElementById('readinessBar').style.width = d.readiness + '%';
  document.getElementById('readinessPct').textContent = d.readiness + '%';
}

async function loadRoadmap(){
  const d = await agent('roadmap');
  const weekNums = Object.keys(d.weeks);
  const container = document.getElementById('roadmapWeeks');
  const pager = document.getElementById('roadmapPager');
  makePager(container, pager, weekNums, 1, week=>{
    const tasks = d.weeks[week];
    return `<div class="card"><div class="mono" style="font-size:11px; color:var(--mist); margin-bottom:10px;">WEEK ${week}</div>` +
      tasks.map(t=>`<label style="display:flex; align-items:center; gap:10px; padding:6px 0; font-size:14px; cursor:pointer;">
        <input type="checkbox" ${t.done?'checked':''} onchange="toggleTask(${t.id}, this.checked)"> ${t.title}
      </label>`).join('') + `</div>`;
  });
}
async function toggleTask(id, done){
  await agent('roadmap', {toggle_task_id: id, done});
}

async function loadCourses(){
  const d = await api('/api/courses');
  makePager(document.getElementById('coursesList'), document.getElementById('coursesPager'), d.courses, 3, c=>`
    <a class="card" href="${c.url||'#'}" target="_blank" rel="noopener" style="display:block; text-decoration:none; color:inherit; cursor:pointer;">
    <span class="pill ${c.free?'pill-signal':'pill-ember'}">${c.free?'Free':'Paid'} · ${c.platform}</span>
    <div style="font-weight:600; margin-top:10px;">${c.title}</div>
    <div style="font-size:12px; color:var(--mist); margin-top:4px;">${c.duration}</div></a>`);
}
async function loadProjects(){
  const d = await api('/api/projects');
  const lvlClass = {Beginner:'pill-signal', Intermediate:'pill-ember', Advanced:'pill-danger'};
  makePager(document.getElementById('projectsList'), document.getElementById('projectsPager'), d.projects, 3, p=>`
    <a class="card" href="${p.url||'#'}" target="_blank" rel="noopener" style="display:block; text-decoration:none; color:inherit; cursor:pointer;">
    <span class="pill ${lvlClass[p.level]}">${p.level}</span>
    <div style="font-weight:600; margin-top:10px;">${p.title}</div>
    <p class="display-i" style="font-size:13px; margin-top:8px; color:var(--mist);">"${p.outcome}"</p></a>`);
}

let currentQuizId = null;
async function loadQuiz(){
  const q = await agent('question');
  currentQuizId = q.id;
  document.getElementById('quizQuestion').textContent = q.question;
  document.getElementById('quizResult').textContent = '';
  document.getElementById('quizOptions').innerHTML = q.options.map((o,i)=>
    `<button class="btn-ghost focus-ring" style="text-align:left;" onclick="answerQuiz(${i})">${o}</button>`).join('');
}
async function answerQuiz(idx){
  const res = await agent('question', {question_id: currentQuizId, selected_index: idx});
  document.getElementById('quizResult').innerHTML = res.correct
    ? `<span style="color:var(--signal);">Correct.</span>`
    : `<span style="color:var(--danger);">Not quite — review and try the next one.</span>`;
}

let currentInterviewId = null;
async function loadInterview(){
  const q = await agent('interview');
  currentInterviewId = q.id;
  document.getElementById('interviewQuestion').textContent = q.question;
  document.getElementById('interviewAnswer').value = '';
  document.getElementById('interviewFeedback').textContent = '';
}
async function submitInterview(){
  const answer = document.getElementById('interviewAnswer').value.trim();
  if(!answer) return;
  const res = await agent('interview', {question_id: currentInterviewId, answer});
  document.getElementById('interviewFeedback').innerHTML = `<span style="color:var(--ember);">Rating: ${res.rating}/5</span> — ${res.feedback}`;
}

async function loadProgress(){
  const d = await agent('progress');
  document.getElementById('streakNum').textContent = d.streak_days;
  const bar = (v,max,color)=>`<div style="width:14px;height:${Math.max(10,Math.round((v/max)*60))}px;background:${color};"></div>`;
  document.getElementById('quizBars').innerHTML = (d.quiz_scores.length? d.quiz_scores : [0,0,0]).map(v=>bar(v||0.3,1,'var(--signal)')).join('');
  document.getElementById('interviewBars').innerHTML = (d.interview_scores.length? d.interview_scores : [1,1,1]).map(v=>bar(v,5,'var(--ember)')).join('');
}

async function loadSettings(){
  const d = await api('/api/settings');
  document.getElementById('settingsEmail').textContent = d.email;
  document.getElementById('settingsTrack').innerHTML = d.available_tracks.map(t=>
    `<option value="${t.value}" ${t.value===d.track?'selected':''}>${t.label}</option>`).join('');
}
async function updateTrack(track){
  await api('/api/settings/track', {method:'POST', body: JSON.stringify({track})});
  // track affects career, skill gap, courses, projects, quiz, interview, roadmap seed
}
