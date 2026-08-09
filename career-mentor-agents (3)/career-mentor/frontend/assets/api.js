// ---- core auth + API helpers, shared by every page ----
const API = "";

function token(){ return localStorage.getItem("cm_token"); }
function setToken(t){ localStorage.setItem("cm_token", t); }
function clearToken(){ localStorage.removeItem("cm_token"); }
function isLoggedIn(){ return !!token(); }
function authHeaders(){ return {"Authorization": "Bearer " + token(), "Content-Type": "application/json"}; }
function authHeadersNoContentType(){ return {"Authorization": "Bearer " + token()}; }

async function api(path, opts={}){
  const isFormData = opts.body instanceof FormData;
  const res = await fetch(API + path, {
    ...opts,
    headers: {...(opts.headers||{}), ...(isFormData ? authHeadersNoContentType() : authHeaders())}
  });
  if(res.status === 401){
    clearToken();
    location.href = "login.html";
    throw new Error("Unauthorized");
  }
  if(!res.ok){
    const e = await res.json().catch(()=>({detail:"Error"}));
    throw new Error(e.detail || "Request failed");
  }
  return res.json();
}

// Routes a request through the backend's Coordinator agent (POST /api/agent/{name}),
// which dispatches to the named subagent and runs its result through the Feedback
// agent before returning. Used for the six subagents from the architecture diagram:
// profile, skillgap, roadmap, question, interview, progress.
async function agent(name, payload={}){
  return api('/api/agent/' + name, {method:'POST', body: JSON.stringify(payload)});
}

function logout(){
  clearToken();
  location.href = "login.html";
}
