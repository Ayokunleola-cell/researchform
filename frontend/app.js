// ===================================================
// ResearchForm — Full Frontend SPA
// Vanilla JS SPA with all views and functionality
// ===================================================

// ====== STATE ======
const State = {
  theme: localStorage.getItem('rf-theme') || 'light',
  user: { name: 'Dr. Adebayo Okonkwo', institution: 'University of Lagos', role: 'researcher' },
  currentView: 'dashboard',
  surveys: [
    { id: '1', title: 'Effect of Teaching Methods on Student Performance', status: 'active', responses: 47, target: 100, created: '2026-04-01', slug: 'tm-student-perf-abc123' },
    { id: '2', title: 'Factors Influencing Academic Motivation Among Undergraduates', status: 'closed', responses: 120, target: 120, created: '2026-03-15', slug: 'acad-motiv-def456', hasAnalysis: true },
    { id: '3', title: 'Impact of Smartphone Use on Study Hours', status: 'draft', responses: 0, target: 80, created: '2026-04-05', slug: 'smartphone-study-ghi789' },
  ],
  activeSurvey: null,
  activeAnalysis: null,
  builderQuestions: [],
  respondentPage: 0,
  modal: null,
};

// ====== ICONS (inline SVG strings) ======
const Icon = {
  home: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
  survey: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
  chart: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>`,
  file: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>`,
  plus: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>`,
  settings: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M4.93 4.93a10 10 0 0 0 0 14.14"/></svg>`,
  moon: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`,
  sun: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/></svg>`,
  link: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>`,
  download: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`,
  trash: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>`,
  edit: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`,
  eye: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`,
  check: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>`,
  x: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`,
  upload: `<svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>`,
  menu: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>`,
  flask: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 3H15M9 3v6L4.5 15.5A2 2 0 0 0 6 19h12a2 2 0 0 0 1.5-3.5L15 9V3M9 3h6"/></svg>`,
  users: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  share: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>`,
  copy: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  qr: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h1v1h-1zM17 14h1v1h-1zM14 17h3v3h1v-4h-4z"/></svg>`,
  alert: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  info: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
  drag: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/></svg>`,
  play: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"/></svg>`,
  report: `<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
};

// ====== UTILS ======
const $ = sel => document.querySelector(sel);
const $$ = sel => document.querySelectorAll(sel);

function render(html) {
  $('#app').innerHTML = html;
}

function setTheme(t) {
  State.theme = t;
  document.body.setAttribute('data-theme', t);
  localStorage.setItem('rf-theme', t);
}

function navigate(view, data = {}) {
  State.currentView = view;
  Object.assign(State, data);
  renderApp();
  window.scrollTo(0,0);
}

function statusBadge(status) {
  const map = {
    active:   ['badge-green', 'Active'],
    closed:   ['badge-neutral', 'Closed'],
    draft:    ['badge-amber', 'Draft'],
    analysed: ['badge-blue', 'Analysed'],
    pending:  ['badge-neutral', 'Pending'],
    running:  ['badge-blue', '● Running'],
    done:     ['badge-green', 'Done'],
    review:   ['badge-amber', 'Review Needed'],
    failed:   ['badge-red', 'Failed'],
  };
  const [cls, label] = map[status] || ['badge-neutral', status];
  return `<span class="badge ${cls}">${label}</span>`;
}

function formatDate(d) {
  return new Date(d).toLocaleDateString('en-NG', {day:'numeric',month:'short',year:'numeric'});
}

function progressBar(value, max, color='var(--text)') {
  const pct = Math.min(100, Math.round((value/max)*100));
  return `<div style="height:6px;background:var(--border);border-radius:3px;overflow:hidden;">
    <div style="height:100%;width:${pct}%;background:${color};border-radius:3px;transition:width .4s ease"></div>
  </div>
  <div style="font-size:.75rem;color:var(--text3);margin-top:4px">${value} / ${max} responses (${pct}%)</div>`;
}

// ====== NAVBAR ======
function renderNavbar() {
  const isDark = State.theme === 'dark';
  return `
  <nav class="navbar">
    <div class="navbar-inner">
      <div class="logo" onclick="navigate('dashboard')">
        <div class="logo-mark">
          <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
          </svg>
        </div>
        <span class="logo-text">Research<span>Form</span></span>
      </div>
      <div class="nav-links">
        <button class="nav-link ${State.currentView==='dashboard'?'active':''}" onclick="navigate('dashboard')">Dashboard</button>
        <button class="nav-link ${State.currentView==='surveys'||State.currentView==='builder'?'active':''}" onclick="navigate('surveys')">Surveys</button>
        <button class="nav-link ${State.currentView==='analysis'?'active':''}" onclick="navigate('analysis')">Analysis</button>
        <button class="nav-link ${State.currentView==='reports'?'active':''}" onclick="navigate('reports')">Reports</button>
      </div>
      <div class="nav-actions">
        <button class="theme-btn" onclick="toggleTheme()" title="Toggle theme">
          ${isDark ? Icon.sun : Icon.moon}
        </button>
        <button class="btn btn-primary btn-sm" onclick="navigate('builder',{activeSurvey:null,builderQuestions:[]})">
          ${Icon.plus} New Survey
        </button>
      </div>
    </div>
  </nav>`;
}

function toggleTheme() {
  setTheme(State.theme === 'dark' ? 'light' : 'dark');
  renderApp();
}

// ====== DASHBOARD ======
function renderDashboard() {
  const totalResponses = State.surveys.reduce((a,s) => a + s.responses, 0);
  const activeSurveys = State.surveys.filter(s => s.status === 'active').length;
  return `
  ${renderNavbar()}
  <div class="main-content" style="max-width:1200px;margin:0 auto">
    <div class="page-header" style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px">
      <div>
        <div style="font-size:.85rem;color:var(--text3);margin-bottom:4px">Welcome back,</div>
        <h2 style="margin-bottom:4px">${State.user.name}</h2>
        <div style="font-size:.875rem;color:var(--text3)">${State.user.institution}</div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-secondary" onclick="navigate('surveys')">View All Surveys</button>
        <button class="btn btn-primary" onclick="navigate('builder',{activeSurvey:null,builderQuestions:getDefaultQuestions()})">
          ${Icon.plus} New Survey
        </button>
      </div>
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">${State.surveys.length}</div>
        <div class="stat-label">Total Surveys</div>
        <div class="stat-delta up">↑ 2 this month</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${totalResponses}</div>
        <div class="stat-label">Total Responses</div>
        <div class="stat-delta up">↑ 47 this week</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${activeSurveys}</div>
        <div class="stat-label">Active Surveys</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">2</div>
        <div class="stat-label">Reports Generated</div>
        <div class="stat-delta up">↑ 1 new</div>
      </div>
    </div>

    <div class="grid-2">
      <div>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
          <h3>Recent Surveys</h3>
          <button class="btn btn-ghost btn-sm" onclick="navigate('surveys')">View all</button>
        </div>
        ${State.surveys.map(s => `
        <div class="card" style="margin-bottom:12px;cursor:pointer" onclick="navigate('survey-detail',{activeSurvey:State.surveys.find(x=>x.id==='${s.id}')})">
          <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:12px">
            <div style="font-weight:600;font-size:.9rem;color:var(--text);line-height:1.4">${s.title}</div>
            ${statusBadge(s.status)}
          </div>
          ${progressBar(s.responses, s.target)}
          <div style="display:flex;gap:8px;margin-top:12px">
            ${s.status==='active'?`<button class="btn btn-sm btn-ghost" onclick="event.stopPropagation();navigate('share',{activeSurvey:State.surveys.find(x=>x.id==='${s.id}')})">${Icon.share} Share</button>`:''}
            ${s.hasAnalysis||s.status==='closed'?`<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();navigate('analysis',{activeAnalysis:State.surveys.find(x=>x.id==='${s.id}')})">${Icon.chart} Analyse</button>`:''}
          </div>
        </div>`).join('')}
      </div>

      <div>
        <div style="margin-bottom:16px"><h3>Quick Actions</h3></div>
        <div style="display:flex;flex-direction:column;gap:10px">
          ${[
            {icon:Icon.survey, label:'Build a new survey', desc:'Create questions & share with respondents', action:`navigate('builder',{activeSurvey:null,builderQuestions:getDefaultQuestions()})`},
            {icon:Icon.upload, label:'Upload existing data', desc:'SPSS .sav, Excel, CSV files', action:`navigate('analysis')`},
            {icon:Icon.chart, label:'Run statistical analysis', desc:'AI-powered test selection & execution', action:`navigate('analysis')`},
            {icon:Icon.report, label:'Generate Chapter 4 report', desc:'Formatted Word document output', action:`navigate('reports')`},
            {icon:Icon.file, label:'Export to SPSS / Excel', desc:'Download your data in any format', action:`showExportModal()`},
          ].map(a => `
          <button class="card card-sm" style="display:flex;align-items:center;gap:14px;cursor:pointer;text-align:left;border:none;width:100%;transition:all .2s" onclick="${a.action}">
            <div style="width:40px;height:40px;border-radius:10px;background:var(--bg3);display:flex;align-items:center;justify-content:center;color:var(--text2);flex-shrink:0">${a.icon}</div>
            <div>
              <div style="font-weight:600;font-size:.875rem;color:var(--text)">${a.label}</div>
              <div style="font-size:.8rem;color:var(--text3)">${a.desc}</div>
            </div>
          </button>`).join('')}
        </div>

        <div style="margin-top:24px">
          <div style="margin-bottom:12px"><h3>Pipeline Activity</h3></div>
          <div class="card card-sm">
            ${[
              {name:'Teaching Methods Survey', stage:'Report Generation', status:'done', time:'2h ago'},
              {name:'Academic Motivation Study', stage:'Decode Review', status:'review', time:'Just now'},
            ].map(a => `
            <div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid var(--border)">
              <div class="stage-icon ${a.status}" style="width:28px;height:28px;font-size:.7rem;border-radius:6px">${a.status==='done'?Icon.check:Icon.alert}</div>
              <div style="flex:1;min-width:0">
                <div style="font-size:.8125rem;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${a.name}</div>
                <div style="font-size:.75rem;color:var(--text3)">${a.stage}</div>
              </div>
              <div style="font-size:.75rem;color:var(--text3);white-space:nowrap">${a.time}</div>
            </div>`).join('')}
          </div>
        </div>
      </div>
    </div>
  </div>`;
}

// ====== SURVEYS LIST ======
function renderSurveys() {
  return `
  ${renderNavbar()}
  <div class="main-content" style="max-width:1200px;margin:0 auto">
    <div class="page-header flex justify-between items-center flex-wrap gap-4">
      <h2>Surveys</h2>
      <button class="btn btn-primary" onclick="navigate('builder',{activeSurvey:null,builderQuestions:getDefaultQuestions()})">
        ${Icon.plus} New Survey
      </button>
    </div>

    <div style="display:flex;gap:8px;margin-bottom:24px;flex-wrap:wrap">
      ${['All','Active','Draft','Closed','Analysed'].map(f=>`
      <button class="btn btn-sm ${f==='All'?'btn-primary':'btn-ghost'}" onclick="">${f}</button>`).join('')}
    </div>

    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Survey Title</th>
          <th>Status</th>
          <th>Responses</th>
          <th>Created</th>
          <th>Actions</th>
        </tr></thead>
        <tbody>
          ${State.surveys.map(s => `
          <tr>
            <td>
              <div style="font-weight:600;color:var(--text);margin-bottom:2px">${s.title}</div>
              <div style="font-size:.75rem;font-family:var(--font-mono);color:var(--text3)">/${s.slug}</div>
            </td>
            <td>${statusBadge(s.status)}</td>
            <td>
              <span style="font-weight:600;font-family:var(--font-mono)">${s.responses}</span>
              <span style="color:var(--text3)"> / ${s.target}</span>
            </td>
            <td>${formatDate(s.created)}</td>
            <td>
              <div style="display:flex;gap:4px">
                <button class="btn btn-sm btn-ghost btn-icon" title="Edit" onclick="navigate('builder',{activeSurvey:s})">${Icon.edit}</button>
                <button class="btn btn-sm btn-ghost btn-icon" title="Share" onclick="navigate('share',{activeSurvey:State.surveys.find(x=>x.id==='${s.id}')})">${Icon.share}</button>
                <button class="btn btn-sm btn-ghost btn-icon" title="Preview" onclick="navigate('respondent',{activeSurvey:State.surveys.find(x=>x.id==='${s.id}')})">${Icon.eye}</button>
                ${s.status==='closed'||s.hasAnalysis?`<button class="btn btn-sm btn-secondary" onclick="navigate('analysis',{activeAnalysis:State.surveys.find(x=>x.id==='${s.id}')})">Analyse</button>`:''}
              </div>
            </td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  </div>`;
}

// ====== SURVEY BUILDER ======
const QUESTION_TYPES = [
  { type: 'short_text', label: 'Short Text', icon: '✏️', level: 'nominal' },
  { type: 'long_text', label: 'Long Text', icon: '📝', level: 'nominal' },
  { type: 'single_choice', label: 'Single Choice', icon: '🔵', level: 'nominal' },
  { type: 'multi_choice', label: 'Multiple Choice', icon: '☑️', level: 'nominal' },
  { type: 'likert', label: 'Likert Scale', icon: '📊', level: 'ordinal' },
  { type: 'rating', label: 'Rating', icon: '⭐', level: 'ordinal' },
  { type: 'number', label: 'Number', icon: '🔢', level: 'ratio' },
  { type: 'date', label: 'Date', icon: '📅', level: 'interval' },
  { type: 'matrix', label: 'Matrix', icon: '🔲', level: 'ordinal' },
  { type: 'section_header', label: 'Section Break', icon: '📌', level: null },
];

function getDefaultQuestions() {
  return [
    { id: 'q1', type: 'short_text', text: 'What is your full name?', required: false, variable_name: 'respondent_name', options: [] },
    { id: 'q2', type: 'single_choice', text: 'What is your gender?', required: true, variable_name: 'gender', options: ['Male','Female','Prefer not to say'], measurement_level: 'nominal' },
    { id: 'q3', type: 'single_choice', text: 'What is your level of study?', required: true, variable_name: 'level', options: ['100 Level','200 Level','300 Level','400 Level','500 Level','Postgraduate'], measurement_level: 'ordinal' },
  ];
}

let dragSrc = null;
function renderBuilder() {
  const q = State.builderQuestions || [];
  return `
  ${renderNavbar()}
  <div style="display:grid;grid-template-columns:280px 1fr 300px;height:calc(100vh - 65px);overflow:hidden">
    <!-- Left: Question Types Panel -->
    <div style="border-right:1px solid var(--border);background:var(--bg2);padding:20px;overflow-y:auto">
      <div style="font-size:.75rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text3);margin-bottom:12px">Add Question</div>
      ${QUESTION_TYPES.map(t => `
      <button onclick="addQuestion('${t.type}')"
        style="display:flex;align-items:center;gap:10px;width:100%;padding:10px 12px;border-radius:8px;border:none;background:none;cursor:pointer;text-align:left;transition:all .15s;font-family:inherit;color:var(--text2);font-size:.875rem;font-weight:500;margin-bottom:2px"
        onmouseenter="this.style.background='var(--bg3)';this.style.color='var(--text)'"
        onmouseleave="this.style.background='none';this.style.color='var(--text2)'">
        <span style="font-size:1.1rem">${t.icon}</span>
        <span>${t.label}</span>
        ${t.level?`<span style="margin-left:auto;font-size:.7rem;background:var(--bg3);padding:2px 6px;border-radius:4px;color:var(--text3)">${t.level}</span>`:''}
      </button>`).join('')}

      <div style="margin-top:24px;padding-top:20px;border-top:1px solid var(--border)">
        <div style="font-size:.75rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text3);margin-bottom:12px">Project Brief</div>
        <div class="form-group">
          <label class="form-label">Study Type</label>
          <select class="form-select" style="font-size:.8rem">
            <option>Quantitative</option><option>Qualitative</option><option>Mixed Methods</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Hypothesis</label>
          <textarea class="form-textarea" placeholder="H0: There is no significant difference..." style="min-height:80px;font-size:.8rem"></textarea>
        </div>
      </div>
    </div>

    <!-- Center: Canvas -->
    <div style="overflow-y:auto;background:var(--bg2);padding:24px" id="builder-canvas">
      <div style="max-width:680px;margin:0 auto">
        <div class="card" style="margin-bottom:20px">
          <input type="text" value="Effect of Teaching Methods on Student Performance"
            style="font-family:var(--font-display);font-size:1.3rem;font-weight:400;border:none;background:none;color:var(--text);width:100%;outline:none"
            placeholder="Survey Title"/>
          <input type="text" placeholder="Add a description or introduction…"
            style="font-size:.875rem;border:none;background:none;color:var(--text3);width:100%;outline:none;margin-top:8px"/>
        </div>

        <div id="questions-list">
          ${q.length === 0 ? `
          <div style="text-align:center;padding:60px 20px;color:var(--text3)">
            <div style="font-size:2.5rem;margin-bottom:12px">📋</div>
            <div style="font-weight:600;margin-bottom:6px">Start building your survey</div>
            <div style="font-size:.875rem">Click a question type on the left to add it</div>
          </div>` :
          q.map((question, i) => renderBuilderQuestion(question, i)).join('')}
        </div>

        <button onclick="addQuestion('short_text')"
          style="width:100%;padding:14px;border:2px dashed var(--border2);border-radius:10px;background:none;cursor:pointer;color:var(--text3);font-family:inherit;font-size:.875rem;transition:all .2s;margin-top:8px"
          onmouseenter="this.style.borderColor='var(--text)';this.style.color='var(--text)'"
          onmouseleave="this.style.borderColor='var(--border2)';this.style.color='var(--text3)'">
          ${Icon.plus} Add Question
        </button>
      </div>
    </div>

    <!-- Right: Settings Panel -->
    <div style="border-left:1px solid var(--border);background:var(--bg);padding:20px;overflow-y:auto">
      <div style="font-size:.75rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text3);margin-bottom:16px">Survey Settings</div>

      <div class="form-group">
        <label class="form-label">Response Limit</label>
        <input type="number" class="form-input" value="100" style="font-size:.875rem"/>
      </div>
      <div class="form-group">
        <label class="form-label">Closes On <span>(optional)</span></label>
        <input type="date" class="form-input" style="font-size:.875rem"/>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <div>
          <div style="font-size:.875rem;font-weight:600;color:var(--text)">Shuffle questions</div>
          <div style="font-size:.75rem;color:var(--text3)">Randomize order for each respondent</div>
        </div>
        <label class="toggle"><input type="checkbox"><span class="toggle-slider"></span></label>
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
        <div>
          <div style="font-size:.875rem;font-weight:600;color:var(--text)">Show progress bar</div>
        </div>
        <label class="toggle"><input type="checkbox" checked><span class="toggle-slider"></span></label>
      </div>

      <div style="display:flex;flex-direction:column;gap:8px">
        <button class="btn btn-primary" onclick="saveSurvey()" style="width:100%">Save & Publish</button>
        <button class="btn btn-secondary" onclick="navigate('respondent',{activeSurvey:{title:'Preview Survey',slug:'preview'}})" style="width:100%">${Icon.eye} Preview</button>
        <button class="btn btn-ghost" onclick="navigate('share',{activeSurvey:{title:'My Survey',slug:'survey-abc123'}})" style="width:100%">${Icon.share} Share Link</button>
      </div>

      <div style="margin-top:24px;padding-top:20px;border-top:1px solid var(--border)">
        <div style="font-size:.75rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--text3);margin-bottom:12px">Export Data</div>
        <div style="display:flex;flex-direction:column;gap:6px">
          ${['CSV','Excel (.xlsx)','SPSS (.sav)','JSON'].map(f=>`
          <button class="btn btn-ghost btn-sm" style="justify-content:flex-start">${Icon.download} ${f}</button>`).join('')}
        </div>
      </div>
    </div>
  </div>`;
}

function renderBuilderQuestion(q, i) {
  const typeInfo = QUESTION_TYPES.find(t => t.type === q.type) || {};
  return `
  <div class="question-card fade-in" id="qcard-${q.id}" draggable="true"
    ondragstart="dragStart(event,'${q.id}')" ondragover="dragOver(event,'${q.id}')" ondrop="drop(event,'${q.id}')">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
      <span class="question-handle" style="cursor:grab">${Icon.drag}</span>
      <span style="font-size:.75rem;font-weight:700;color:var(--text3)">Q${i+1}</span>
      <span class="question-type-badge">${typeInfo.icon || ''} ${typeInfo.label || q.type}</span>
      <div style="margin-left:auto;display:flex;gap:4px">
        <button class="btn btn-sm btn-ghost btn-icon" onclick="deleteQuestion('${q.id}')" style="color:var(--text3)">${Icon.trash}</button>
      </div>
    </div>
    <input type="text" value="${q.text}" placeholder="Question text…"
      style="width:100%;border:none;background:none;font-size:.95rem;font-weight:600;color:var(--text);outline:none;margin-bottom:12px;font-family:inherit"
      onchange="updateQuestion('${q.id}','text',this.value)"/>
    ${renderQuestionInput(q)}
    <div style="display:flex;align-items:center;gap:16px;margin-top:12px;padding-top:12px;border-top:1px solid var(--border)">
      <label style="display:flex;align-items:center;gap:6px;font-size:.8rem;color:var(--text3);cursor:pointer">
        <input type="checkbox" ${q.required?'checked':''} onchange="updateQuestion('${q.id}','required',this.checked)"/> Required
      </label>
      <div style="margin-left:auto;font-size:.75rem;font-family:var(--font-mono);color:var(--text3)">${q.variable_name||'var_'+q.id.slice(-4)}</div>
    </div>
  </div>`;
}

function renderQuestionInput(q) {
  switch(q.type) {
    case 'short_text': return `<input class="form-input" placeholder="Short answer…" disabled style="opacity:.6"/>`;
    case 'long_text': return `<textarea class="form-textarea" placeholder="Long answer…" disabled style="opacity:.6;min-height:70px"></textarea>`;
    case 'number': return `<input class="form-input" type="number" placeholder="0" disabled style="opacity:.6;max-width:200px"/>`;
    case 'date': return `<input class="form-input" type="date" disabled style="opacity:.6;max-width:200px"/>`;
    case 'section_header': return `<div style="height:2px;background:var(--border);border-radius:1px"></div>`;
    case 'likert': return `
      <div style="display:flex;gap:6px;flex-wrap:wrap">
        ${[1,2,3,4,5].map(n => `
        <div style="display:flex;flex-direction:column;align-items:center;gap:4px;padding:8px 14px;border-radius:8px;border:1.5px solid var(--border);min-width:52px;background:var(--bg);opacity:.7">
          <span style="font-weight:700;font-family:var(--font-mono)">${n}</span>
          <span style="font-size:.65rem;color:var(--text3)">${n===1?'SA':n===2?'A':n===3?'N':n===4?'D':'SD'}</span>
        </div>`).join('')}
      </div>`;
    case 'rating': return `
      <div style="display:flex;gap:4px">
        ${[1,2,3,4,5].map(n=>`<span style="font-size:1.5rem;opacity:.4;cursor:default">★</span>`).join('')}
      </div>`;
    case 'single_choice':
    case 'multi_choice': {
      const opts = q.options && q.options.length ? q.options : ['Option 1','Option 2','Option 3'];
      const isMulti = q.type === 'multi_choice';
      return `
      <div style="display:flex;flex-direction:column;gap:6px">
        ${opts.map((o,i) => `
        <div style="display:flex;align-items:center;gap:8px">
          <span style="width:16px;height:16px;border-radius:${isMulti?'4px':'50%'};border:2px solid var(--border2);flex-shrink:0;display:inline-block"></span>
          <input type="text" value="${o}" style="border:none;background:none;color:var(--text);font-family:inherit;font-size:.875rem;outline:none;flex:1" placeholder="Option ${i+1}"/>
        </div>`).join('')}
        <button style="font-size:.8rem;color:var(--text3);background:none;border:none;cursor:pointer;text-align:left;padding:4px 0;font-family:inherit" onclick="">+ Add option</button>
      </div>`;
    }
    case 'matrix': return `
      <div style="overflow-x:auto">
        <table style="font-size:.8rem;border-collapse:collapse;width:100%">
          <thead><tr>
            <th style="padding:6px 10px;border:1px solid var(--border);background:var(--bg2);text-align:left">Statement</th>
            ${['SA','A','N','D','SD'].map(h=>`<th style="padding:6px 10px;border:1px solid var(--border);background:var(--bg2);text-align:center">${h}</th>`).join('')}
          </tr></thead>
          <tbody>
            ${['Statement 1','Statement 2'].map(row=>`
            <tr>
              <td style="padding:6px 10px;border:1px solid var(--border)">${row}</td>
              ${[1,2,3,4,5].map(()=>`<td style="padding:6px;border:1px solid var(--border);text-align:center"><input type="radio" disabled/></td>`).join('')}
            </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
    default: return `<div style="color:var(--text3);font-size:.875rem">Question preview</div>`;
  }
}

function addQuestion(type) {
  const id = 'q' + Date.now();
  const typeInfo = QUESTION_TYPES.find(t => t.type === type) || {};
  const newQ = {
    id, type, text: '', required: false,
    variable_name: 'q_' + id.slice(-4),
    options: ['single_choice','multi_choice'].includes(type) ? ['Option 1','Option 2','Option 3'] : [],
    measurement_level: typeInfo.level,
  };
  State.builderQuestions = [...(State.builderQuestions||[]), newQ];
  navigate('builder');
}

function deleteQuestion(id) {
  State.builderQuestions = (State.builderQuestions||[]).filter(q => q.id !== id);
  navigate('builder');
}

function updateQuestion(id, field, value) {
  const q = (State.builderQuestions||[]).find(q => q.id === id);
  if(q) q[field] = value;
}

function dragStart(e, id) { dragSrc = id; e.dataTransfer.effectAllowed='move'; }
function dragOver(e, id) { e.preventDefault(); e.dataTransfer.dropEffect='move'; }
function drop(e, id) {
  e.preventDefault();
  if(dragSrc === id) return;
  const qs = [...(State.builderQuestions||[])];
  const si = qs.findIndex(q=>q.id===dragSrc);
  const ti = qs.findIndex(q=>q.id===id);
  const [item] = qs.splice(si,1);
  qs.splice(ti,0,item);
  State.builderQuestions = qs;
  navigate('builder');
}

function saveSurvey() {
  const slug = 'survey-' + Math.random().toString(36).slice(2,8);
  const newSurvey = {
    id: String(Date.now()), title: 'New Survey', status: 'active',
    responses: 0, target: 100, created: new Date().toISOString().slice(0,10), slug
  };
  State.surveys.unshift(newSurvey);
  navigate('share', {activeSurvey: newSurvey});
}

// ====== SHARE VIEW ======
function renderShare() {
  const s = State.activeSurvey || {title:'My Survey', slug:'survey-abc123'};
  const url = `https://researchform.app/s/${s.slug}`;
  return `
  ${renderNavbar()}
  <div class="main-content" style="max-width:800px;margin:0 auto">
    <div style="margin-bottom:24px">
      <button class="btn btn-ghost btn-sm" onclick="navigate('surveys')" style="margin-bottom:16px">← Back to Surveys</button>
      <h2>${s.title}</h2>
      <p style="margin-top:8px">Share your survey with respondents using the link or QR code below.</p>
    </div>

    <div class="grid-2">
      <div>
        <div class="card" style="margin-bottom:16px">
          <div style="font-weight:700;font-size:.875rem;color:var(--text);margin-bottom:12px">Survey Link</div>
          <div style="display:flex;gap:8px">
            <input type="text" value="${url}" class="form-input" readonly style="font-family:var(--font-mono);font-size:.8125rem;flex:1"/>
            <button class="btn btn-secondary" onclick="copyLink('${url}')">Copy</button>
          </div>
          <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-sm btn-ghost">${Icon.share} WhatsApp</button>
            <button class="btn btn-sm btn-ghost">${Icon.share} Email</button>
            <button class="btn btn-sm btn-ghost">${Icon.share} Twitter</button>
          </div>
        </div>

        <div class="card" style="margin-bottom:16px">
          <div style="font-weight:700;font-size:.875rem;color:var(--text);margin-bottom:16px">Embed Code</div>
          <div class="code-block" style="font-size:.75rem">&lt;iframe src="${url}/embed"
  width="100%" height="600"
  frameborder="0"&gt;&lt;/iframe&gt;</div>
        </div>

        <div class="card">
          <div style="font-weight:700;font-size:.875rem;color:var(--text);margin-bottom:12px">Live Response Feed</div>
          <div class="stat-grid" style="grid-template-columns:1fr 1fr">
            <div class="stat-card card-sm">
              <div class="stat-value" style="font-size:1.5rem">47</div>
              <div class="stat-label">Responses</div>
            </div>
            <div class="stat-card card-sm">
              <div class="stat-value" style="font-size:1.5rem">82%</div>
              <div class="stat-label">Completion</div>
            </div>
          </div>
          <button class="btn btn-primary" style="width:100%;margin-top:12px" onclick="navigate('analysis')">
            ${Icon.chart} Analyse Data
          </button>
        </div>
      </div>

      <div>
        <div class="qr-container">
          <div style="font-weight:700;font-size:.875rem;color:var(--text);margin-bottom:16px;text-align:left">QR Code</div>
          <div class="qr-placeholder">
            <div style="text-align:center">
              <div style="font-size:3rem;margin-bottom:8px">⬛</div>
              QR Code<br/>${s.slug}
            </div>
          </div>
          <div style="font-size:.8rem;color:var(--text3);margin-bottom:16px">Scan with any smartphone camera to open survey</div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-secondary" style="flex:1">${Icon.download} PNG</button>
            <button class="btn btn-secondary" style="flex:1">${Icon.download} SVG</button>
          </div>
        </div>

        <div class="card" style="margin-top:16px">
          <div style="font-weight:700;font-size:.875rem;color:var(--text);margin-bottom:12px">Survey Settings</div>
          <div style="display:flex;flex-direction:column;gap:12px">
            ${[
              {label:'Allow multiple responses', checked:false},
              {label:'Require email address', checked:false},
              {label:'Show response count', checked:true},
              {label:'Allow editing responses', checked:false},
            ].map(s=>`
            <div style="display:flex;align-items:center;justify-content:space-between">
              <span style="font-size:.875rem;color:var(--text2)">${s.label}</span>
              <label class="toggle"><input type="checkbox" ${s.checked?'checked':''}><span class="toggle-slider"></span></label>
            </div>`).join('')}
          </div>
        </div>
      </div>
    </div>
  </div>`;
}

function copyLink(url) {
  navigator.clipboard?.writeText(url).catch(()=>{});
  showToast('Link copied to clipboard!');
}

// ====== RESPONDENT VIEW ======
const SAMPLE_QUESTIONS = [
  {id:'rq1',type:'section_header',text:'Section A: Personal Information'},
  {id:'rq2',type:'short_text',text:'What is your full name?',required:false,variable_name:'name'},
  {id:'rq3',type:'single_choice',text:'What is your gender?',required:true,variable_name:'gender',options:['Male','Female','Prefer not to say']},
  {id:'rq4',type:'single_choice',text:'What is your level of study?',required:true,variable_name:'level',options:['100 Level','200 Level','300 Level','400 Level','Postgraduate']},
  {id:'rq5',type:'section_header',text:'Section B: Teaching Methods'},
  {id:'rq6',type:'likert',text:'The lecturer uses clear and organized teaching methods.',required:true,variable_name:'q1_clarity'},
  {id:'rq7',type:'likert',text:'I am able to understand lecture content during class sessions.',required:true,variable_name:'q2_understanding'},
  {id:'rq8',type:'likert',text:'Teaching methods used in this course motivate me to study more.',required:true,variable_name:'q3_motivation'},
  {id:'rq9',type:'number',text:'What is your current CGPA? (e.g. 3.5)',required:true,variable_name:'cgpa'},
  {id:'rq10',type:'long_text',text:'Any additional comments about the teaching methods used?',required:false,variable_name:'comments'},
];

function renderRespondent() {
  const s = State.activeSurvey || {title:'Effect of Teaching Methods on Student Performance', description:'This survey is conducted as part of a research project. Your responses are anonymous and will be used for academic purposes only.'};
  const total = SAMPLE_QUESTIONS.filter(q=>q.type!=='section_header').length;
  const answered = 3;
  const pct = Math.round((answered/total)*100);

  return `
  <div class="survey-page" data-theme="${State.theme}">
    <div class="survey-header">
      <div style="max-width:680px;margin:0 auto">
        <div style="font-size:.75rem;opacity:.6;margin-bottom:6px;letter-spacing:.05em;text-transform:uppercase">ResearchForm</div>
        <h1>${s.title}</h1>
        <p>${s.description || 'Please answer all required questions honestly. Your participation is greatly appreciated.'}</p>
      </div>
    </div>
    <div class="survey-progress">
      <div class="survey-progress-fill" style="width:${pct}%"></div>
    </div>

    <div class="survey-body">
      ${SAMPLE_QUESTIONS.map((q, i) => {
        if(q.type==='section_header') return `
        <div style="padding:16px 0 8px;margin-top:${i>0?'24px':'0'}">
          <div style="font-size:.75rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text3);margin-bottom:4px">Section</div>
          <h3 style="font-family:var(--font-display);color:var(--text);font-size:1.2rem">${q.text}</h3>
          <div style="height:2px;background:var(--border);border-radius:1px;margin-top:12px"></div>
        </div>`;

        const qNum = SAMPLE_QUESTIONS.slice(0,i+1).filter(x=>x.type!=='section_header').length;
        return `
        <div class="survey-question fade-in">
          <div class="question-number">Question ${qNum} of ${total}${q.required?` <span class="required-star">*</span>`:''}</div>
          <div class="question-text">${q.text}</div>
          ${renderRespondentInput(q)}
        </div>`;
      }).join('')}

      <div style="display:flex;justify-content:flex-end;margin-top:32px;padding-bottom:40px">
        <button class="btn btn-primary btn-lg" onclick="submitSurvey()">
          Submit Responses →
        </button>
      </div>
    </div>
  </div>`;
}

function renderRespondentInput(q) {
  switch(q.type) {
    case 'short_text': return `<input class="form-input" placeholder="Your answer…"/>`;
    case 'long_text': return `<textarea class="form-textarea" placeholder="Your answer…" style="min-height:120px"></textarea>`;
    case 'number': return `<input class="form-input" type="number" step="0.01" placeholder="e.g. 3.50" style="max-width:200px"/>`;
    case 'date': return `<input class="form-input" type="date" style="max-width:240px"/>`;
    case 'single_choice': return `
      <div style="display:flex;flex-direction:column;gap:8px">
        ${(q.options||[]).map(o=>`
        <label style="display:flex;align-items:center;gap:12px;padding:12px 16px;border-radius:8px;border:1.5px solid var(--border);cursor:pointer;transition:all .15s"
          onmouseenter="this.style.borderColor='var(--text)';this.style.background='var(--bg2)'"
          onmouseleave="this.style.borderColor='var(--border)';this.style.background='transparent'">
          <input type="radio" name="q${q.id}" style="width:18px;height:18px;cursor:pointer"/>
          <span style="font-size:.9rem;color:var(--text)">${o}</span>
        </label>`).join('')}
      </div>`;
    case 'multi_choice': return `
      <div style="display:flex;flex-direction:column;gap:8px">
        ${(q.options||[]).map(o=>`
        <label style="display:flex;align-items:center;gap:12px;padding:12px 16px;border-radius:8px;border:1.5px solid var(--border);cursor:pointer;transition:all .15s"
          onmouseenter="this.style.borderColor='var(--text)';this.style.background='var(--bg2)'"
          onmouseleave="this.style.borderColor='var(--border)';this.style.background='transparent'">
          <input type="checkbox" style="width:18px;height:18px;cursor:pointer"/>
          <span style="font-size:.9rem;color:var(--text)">${o}</span>
        </label>`).join('')}
      </div>`;
    case 'likert': return `
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        ${[{v:1,l:'Strongly\nAgree'},{v:2,l:'Agree'},{v:3,l:'Neutral'},{v:4,l:'Disagree'},{v:5,l:'Strongly\nDisagree'}].map(opt=>`
        <label class="likert-option" style="cursor:pointer">
          <input type="radio" name="q${q.id}" style="display:none"/>
          <span class="likert-value">${opt.v}</span>
          <span class="likert-label">${opt.l}</span>
        </label>`).join('')}
      </div>`;
    case 'rating': return `
      <div style="display:flex;gap:6px">
        ${[1,2,3,4,5].map(n=>`
        <button style="font-size:2rem;background:none;border:none;cursor:pointer;color:var(--border2);transition:color .15s" onclick="this.style.color='#f59e0b'">★</button>`).join('')}
      </div>`;
    default: return '';
  }
}

function submitSurvey() {
  render(`
  <div style="min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);flex-direction:column;gap:24px;text-align:center;padding:24px">
    <div style="font-size:4rem">🎉</div>
    <h2 style="font-family:var(--font-display);font-size:2rem">Thank You!</h2>
    <p style="color:var(--text3);max-width:400px">Your responses have been recorded successfully. The researcher will use this data for their academic analysis.</p>
    <button class="btn btn-primary" onclick="navigate('dashboard')">Back to Dashboard</button>
  </div>`);
}

// ====== ANALYSIS VIEW ======
const PIPELINE_STAGES = [
  {num:1,name:'Data Assembly',desc:'Survey DB / uploaded file',status:'done'},
  {num:2,name:'Data Decode',desc:'Parsing + data dictionary',status:'review',star:true},
  {num:3,name:'Brief Parsing',desc:'Research objectives & hypotheses',status:'pending'},
  {num:4,name:'Test Selection',desc:'AI-powered statistical test choice',status:'pending'},
  {num:5,name:'Code Generation',desc:'Python analysis script',status:'pending'},
  {num:6,name:'Code Execution',desc:'Sandboxed execution',status:'pending'},
  {num:7,name:'Visualisation',desc:'Charts & graphs',status:'pending'},
  {num:8,name:'Report Writing',desc:'Chapter 4 narrative',status:'pending'},
  {num:9,name:'Document Build',desc:'Word document export',status:'pending'},
];

function renderAnalysis() {
  const [activeTab, setActiveTab] = ['upload','decode','pipeline','results'].includes(State.analysisTab||'') ? [State.analysisTab] : ['upload'];

  return `
  ${renderNavbar()}
  <div class="main-content" style="max-width:1100px;margin:0 auto">
    <div class="page-header flex justify-between items-center flex-wrap gap-4">
      <div>
        <h2>Analysis Pipeline</h2>
        <p>9-stage AI-powered statistical analysis</p>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn btn-ghost btn-sm" onclick="showExportModal()">Export Data</button>
        <button class="btn btn-primary btn-sm" onclick="State.analysisTab='pipeline';navigate('analysis')">View Pipeline</button>
      </div>
    </div>

    <div class="tabs">
      ${[['upload','📤 Upload & Source'],['decode','🔍 Decode Review'],['pipeline','⚙️ Pipeline'],['results','📊 Results']].map(([v,l])=>`
      <button class="tab ${(State.analysisTab||'upload')===v?'active':''}" onclick="State.analysisTab='${v}';navigate('analysis')">${l}</button>`).join('')}
    </div>

    ${(State.analysisTab||'upload')==='upload' ? renderAnalysisUpload() : ''}
    ${State.analysisTab==='decode' ? renderDecodeReview() : ''}
    ${State.analysisTab==='pipeline' ? renderPipeline() : ''}
    ${State.analysisTab==='results' ? renderResults() : ''}
  </div>`;
}

function renderAnalysisUpload() {
  return `
  <div class="grid-2">
    <div>
      <div class="card" style="margin-bottom:16px">
        <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:16px">Project Brief</div>
        <div class="form-group">
          <label class="form-label">Project Title</label>
          <input class="form-input" value="Effect of Teaching Methods on Student Performance"/>
        </div>
        <div class="form-group">
          <label class="form-label">Study Type</label>
          <select class="form-select">
            <option selected>Quantitative</option><option>Qualitative</option><option>Mixed Methods</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Research Objectives</label>
          <textarea class="form-textarea" style="min-height:80px">1. To determine the effect of teaching methods on student performance.
2. To examine gender differences in academic performance.</textarea>
        </div>
        <div class="form-group">
          <label class="form-label">Null Hypothesis (H₀)</label>
          <input class="form-input" value="There is no significant difference in student performance based on teaching method."/>
        </div>
        <div class="form-group">
          <label class="form-label">Significance Level (α)</label>
          <select class="form-select">
            <option selected>0.05</option><option>0.01</option><option>0.001</option>
          </select>
        </div>
      </div>
    </div>

    <div>
      <div class="card" style="margin-bottom:16px">
        <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:16px">Data Source</div>
        <div style="display:flex;gap:8px;margin-bottom:16px">
          ${['Survey Data','Upload File'].map((tab,i)=>`
          <button class="btn btn-sm ${i===0?'btn-primary':'btn-ghost'}" onclick="">${tab}</button>`).join('')}
        </div>
        <div class="card" style="margin-bottom:12px;cursor:pointer;background:var(--green-bg);border-color:var(--green)">
          <div style="display:flex;align-items:center;gap:12px">
            <div style="font-size:1.5rem">✅</div>
            <div>
              <div style="font-weight:600;font-size:.875rem;color:var(--green)">Teaching Methods Survey</div>
              <div style="font-size:.75rem;color:var(--text3)">120 responses · Closed 3 days ago</div>
            </div>
            <button class="btn btn-sm btn-success" style="margin-left:auto">Selected</button>
          </div>
        </div>
        <div class="drop-zone" onclick="" style="margin-top:12px">
          <div class="drop-zone-icon">${Icon.upload}</div>
          <p><strong>Or upload a file</strong></p>
          <p style="font-size:.8rem">SPSS (.sav), Excel (.xlsx), CSV</p>
        </div>
      </div>

      <button class="btn btn-primary btn-lg" style="width:100%" onclick="State.analysisTab='decode';navigate('analysis')">
        ${Icon.play} Run Decode Stage →
      </button>
    </div>
  </div>`;
}

function renderDecodeReview() {
  const VARS = [
    {name:'respondent_name',label:'Respondent Name',dtype:'object',level:'nominal',n_valid:120,n_missing:3,pct_missing:2.5,warn:false},
    {name:'gender',label:'Gender',dtype:'category',level:'nominal',n_valid:120,n_missing:0,pct_missing:0,warn:false},
    {name:'level',label:'Level of Study',dtype:'category',level:'ordinal',n_valid:120,n_missing:0,pct_missing:0,warn:false},
    {name:'q1_clarity',label:'Teaching Clarity (Q1)',dtype:'int64',level:'ordinal',n_valid:118,n_missing:2,pct_missing:1.7,warn:false},
    {name:'q2_understanding',label:'Understanding (Q2)',dtype:'int64',level:'ordinal',n_valid:120,n_missing:0,pct_missing:0,warn:false},
    {name:'q3_motivation',label:'Motivation (Q3)',dtype:'int64',level:'ordinal',n_valid:120,n_missing:0,pct_missing:0,warn:false},
    {name:'cgpa',label:'CGPA',dtype:'float64',level:'ratio',n_valid:115,n_missing:5,pct_missing:4.2,warn:true},
    {name:'comments',label:'Additional Comments',dtype:'object',level:'nominal',n_valid:67,n_missing:53,pct_missing:44.2,warn:true},
  ];

  return `
  <div class="alert alert-warn">
    ${Icon.alert}
    <div><strong>Decode Review Required —</strong> Please review the decoded variables below, correct any measurement levels, assign roles, and confirm your missing value strategy before running analysis.</div>
  </div>

  <div class="stat-grid" style="grid-template-columns:repeat(4,1fr)">
    <div class="stat-card"><div class="stat-value">120</div><div class="stat-label">Respondents</div></div>
    <div class="stat-card"><div class="stat-value">8</div><div class="stat-label">Variables</div></div>
    <div class="stat-card"><div class="stat-value">2</div><div class="stat-label">Warnings</div></div>
    <div class="stat-card"><div class="stat-value">survey_db</div><div class="stat-label">Source Type</div></div>
  </div>

  <div class="card" style="margin-bottom:16px">
    <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:16px">Variable Review</div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Variable</th><th>Label</th><th>Type</th><th>Measurement Level</th><th>Role</th><th>Missing</th><th>Action</th>
        </tr></thead>
        <tbody>
          ${VARS.map(v=>`
          <tr style="${v.warn?'background:var(--amber-bg)':''}">
            <td style="font-family:var(--font-mono);font-size:.8rem">${v.name}</td>
            <td>${v.label}</td>
            <td><span style="font-family:var(--font-mono);font-size:.75rem;background:var(--bg3);padding:2px 6px;border-radius:4px">${v.dtype}</span></td>
            <td>
              <select style="border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:.8rem;background:var(--bg);color:var(--text);font-family:inherit">
                ${['nominal','ordinal','interval','ratio'].map(l=>`<option ${v.level===l?'selected':''}>${l}</option>`).join('')}
              </select>
            </td>
            <td>
              <select style="border:1px solid var(--border);border-radius:6px;padding:4px 8px;font-size:.8rem;background:var(--bg);color:var(--text);font-family:inherit">
                ${['—','DV','IV','Control','ID'].map(r=>`<option>${r}</option>`).join('')}
              </select>
            </td>
            <td>
              <span style="font-size:.8125rem;${v.pct_missing>20?'color:var(--red);font-weight:600':v.pct_missing>5?'color:var(--amber)':'color:var(--green)'}">${v.pct_missing}%</span>
            </td>
            <td>${v.warn?`<span class="badge badge-amber">${Icon.alert} Review</span>`:`<span class="badge badge-green">${Icon.check} OK</span>`}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  </div>

  <div class="card" style="margin-bottom:16px">
    <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:12px">Missing Value Strategy</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      ${[
        {v:'flag_only',l:'Flag Only',d:'Keep all rows, mark missing'},
        {v:'drop_rows',l:'Drop Rows',d:'Remove rows with any missing'},
        {v:'mean_impute',l:'Mean Impute',d:'Replace with column mean'},
        {v:'median_impute',l:'Median Impute',d:'Replace with column median'},
      ].map(s=>`
      <label style="display:flex;align-items:flex-start;gap:8px;padding:10px 14px;border-radius:8px;border:1.5px solid var(--border);cursor:pointer;transition:all .15s;flex:1;min-width:160px"
        onmouseenter="this.style.borderColor='var(--text)'"
        onmouseleave="this.style.borderColor='var(--border)'">
        <input type="radio" name="missing" ${s.v==='flag_only'?'checked':''} style="margin-top:2px"/>
        <div>
          <div style="font-weight:600;font-size:.8125rem;color:var(--text)">${s.l}</div>
          <div style="font-size:.75rem;color:var(--text3)">${s.d}</div>
        </div>
      </label>`).join('')}
    </div>
  </div>

  <div style="display:flex;justify-content:flex-end;gap:12px">
    <button class="btn btn-ghost" onclick="State.analysisTab='upload';navigate('analysis')">← Back</button>
    <button class="btn btn-primary btn-lg" onclick="State.analysisTab='pipeline';navigate('analysis')">
      Confirm & Run Analysis →
    </button>
  </div>`;
}

function renderPipeline() {
  return `
  <div class="grid-2">
    <div>
      <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:16px">Pipeline Progress</div>
      <div class="pipeline-status">
        ${PIPELINE_STAGES.map(s => `
        <div class="pipeline-stage">
          <div class="stage-icon ${s.status}">
            ${s.status==='done'?Icon.check : s.status==='running'?'<div class="spinner" style="width:16px;height:16px;border-width:2px"></div>' : s.status==='review'?Icon.alert : s.num}
          </div>
          <div style="flex:1;min-width:0">
            <div class="stage-name">${s.num}. ${s.name} ${s.star?'<span style="color:var(--amber)">★</span>':''}</div>
            <div class="stage-desc">${s.desc}</div>
          </div>
          ${statusBadge(s.status)}
        </div>`).join('')}
      </div>
    </div>

    <div>
      <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:16px">LLM Test Selection (Stage 4)</div>
      <div class="card" style="margin-bottom:16px">
        <div class="alert alert-info" style="margin-bottom:16px">
          ${Icon.info}
          <div>The AI has analyzed your research brief and data dictionary to select the most appropriate statistical tests.</div>
        </div>
        ${[
          {test:'Independent Samples t-test',reason:'Comparing means of 2 groups (teaching method: traditional vs CBL); CGPA is ratio-level data',alpha:'0.05',pkg:'scipy.stats.ttest_ind'},
          {test:'Mann-Whitney U Test',reason:'Non-parametric alternative for Likert motivation scores (ordinal data)',alpha:'0.05',pkg:'scipy.stats.mannwhitneyu'},
          {test:"Pearson's r Correlation",reason:'Testing relationship between teaching method engagement and CGPA (both continuous)',alpha:'0.05',pkg:'scipy.stats.pearsonr'},
        ].map(t=>`
        <div style="padding:12px;background:var(--bg2);border-radius:8px;margin-bottom:8px">
          <div style="font-weight:600;font-size:.875rem;color:var(--text);margin-bottom:4px">${t.test}</div>
          <div style="font-size:.8rem;color:var(--text3);margin-bottom:6px">${t.reason}</div>
          <div style="display:flex;gap:6px;flex-wrap:wrap">
            <span class="badge badge-blue">α = ${t.alpha}</span>
            <span class="badge badge-neutral" style="font-family:var(--font-mono)">${t.pkg}</span>
          </div>
        </div>`).join('')}
      </div>

      <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:12px">Generated Python Code (Stage 5)</div>
      <div class="code-block">
<span style="color:var(--text3)"># Generated by ResearchForm AI Engine
# Study: Teaching Methods on Student Performance</span>

import pandas as pd
import scipy.stats as stats
from statsmodels.stats.power import TTestIndPower

df = pd.read_pickle('data.pkl')

<span style="color:var(--text3)"># Hypothesis 1: t-test</span>
group_a = df[df['teaching_method']=='Traditional']['cgpa']
group_b = df[df['teaching_method']=='CBL']['cgpa']
t_stat, p_value = stats.ttest_ind(group_a, group_b)

print(f"t({len(df)-2}) = {t_stat:.3f}, p = {p_value:.3f}")
      </div>

      <div style="margin-top:12px;display:flex;gap:8px">
        <button class="btn btn-primary" style="flex:1" onclick="State.analysisTab='results';navigate('analysis')">
          ${Icon.play} View Results →
        </button>
      </div>
    </div>
  </div>`;
}

function renderResults() {
  return `
  <div>
    <div class="alert alert-success" style="margin-bottom:20px">
      ${Icon.check}
      <div><strong>Analysis Complete!</strong> All statistical tests have been executed. Chapter 4 report is ready for download.</div>
    </div>

    <div class="stat-grid">
      <div class="stat-card"><div class="stat-value" style="font-size:1.5rem;color:var(--green)">p=.003</div><div class="stat-label">t-test p-value</div></div>
      <div class="stat-card"><div class="stat-value" style="font-size:1.5rem">3.21</div><div class="stat-label">t-statistic</div></div>
      <div class="stat-card"><div class="stat-value" style="font-size:1.5rem;color:var(--green)">d=0.58</div><div class="stat-label">Cohen's d</div></div>
      <div class="stat-card"><div class="stat-value" style="font-size:1.5rem;color:var(--green)">H₀ Rejected</div><div class="stat-label">Decision</div></div>
    </div>

    <div class="grid-2">
      <div>
        <div class="card" style="margin-bottom:16px">
          <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:16px">Test Results Summary</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Test</th><th>Statistic</th><th>p-value</th><th>Decision</th></tr></thead>
              <tbody>
                <tr><td>t-test (CGPA)</td><td>t(118) = 3.21</td><td style="color:var(--green);font-weight:700">0.003</td><td><span class="badge badge-red">Reject H₀</span></td></tr>
                <tr><td>Mann-Whitney U</td><td>U = 1842.5</td><td style="color:var(--green);font-weight:700">0.012</td><td><span class="badge badge-red">Reject H₀</span></td></tr>
                <tr><td>Pearson r</td><td>r = 0.42</td><td style="color:var(--green);font-weight:700">0.001</td><td><span class="badge badge-red">Reject H₀</span></td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:12px">Descriptive Statistics</div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Group</th><th>N</th><th>Mean</th><th>SD</th></tr></thead>
              <tbody>
                <tr><td>Traditional</td><td>58</td><td>3.21</td><td>0.44</td></tr>
                <tr><td>CBL</td><td>62</td><td>3.67</td><td>0.38</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div>
        <div class="card" style="margin-bottom:16px">
          <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:12px">Charts Generated</div>
          ${[
            {name:'Box Plot — CGPA by Teaching Method',type:'boxplot'},
            {name:'Bar Chart — Likert Response Distribution',type:'bar'},
            {name:'Scatter Plot — Teaching Method vs CGPA',type:'scatter'},
          ].map(c=>`
          <div style="display:flex;align-items:center;gap:12px;padding:10px;border-radius:8px;background:var(--bg2);margin-bottom:8px">
            <div style="width:48px;height:40px;background:var(--bg3);border-radius:6px;display:flex;align-items:center;justify-content:center;color:var(--text3)">📊</div>
            <div style="flex:1;font-size:.8125rem;color:var(--text);font-weight:500">${c.name}</div>
            <button class="btn btn-sm btn-ghost">${Icon.eye}</button>
          </div>`).join('')}
        </div>

        <div class="card">
          <div style="font-weight:700;font-size:.9rem;color:var(--text);margin-bottom:12px">Chapter 4 Preview</div>
          <div class="report-preview" style="font-size:9pt;padding:20px;max-height:200px;overflow:hidden">
            <p><strong>CHAPTER FOUR</strong></p>
            <p><strong>DATA PRESENTATION, ANALYSIS AND DISCUSSION OF FINDINGS</strong></p>
            <br/>
            <p>This chapter presents the analysis of data collected from 120 undergraduate students on the effect of teaching methods on academic performance. The independent samples t-test yielded t(118) = 3.21, p = 0.003 which is less than the 0.05 level of significance. Therefore, H₀ is rejected.</p>
          </div>
          <div style="margin-top:12px;display:flex;gap:8px">
            <button class="btn btn-primary" style="flex:1" onclick="navigate('reports')">${Icon.report} Full Report</button>
            <button class="btn btn-secondary" onclick="showExportModal()">${Icon.download} Download</button>
          </div>
        </div>
      </div>
    </div>
  </div>`;
}

// ====== REPORTS VIEW ======
function renderReports() {
  return `
  ${renderNavbar()}
  <div class="main-content" style="max-width:1100px;margin:0 auto">
    <div class="page-header flex justify-between items-center flex-wrap gap-4">
      <div>
        <h2>Reports</h2>
        <p>Generated Chapter 4 reports and analysis documents</p>
      </div>
      <button class="btn btn-primary" onclick="navigate('analysis')">${Icon.plus} New Analysis</button>
    </div>

    <div class="grid-2" style="margin-bottom:32px">
      ${[
        {title:'Effect of Teaching Methods on Student Performance',date:'Apr 6, 2026',pages:14,tests:['t-test','Mann-Whitney U','Pearson r'],status:'done'},
        {title:'Academic Motivation Among Undergraduates',date:'Mar 18, 2026',pages:18,tests:['ANOVA','Tukey HSD','Descriptive Stats'],status:'done'},
      ].map(r=>`
      <div class="card">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:16px">
          <div style="font-weight:700;font-size:.95rem;color:var(--text);line-height:1.4">${r.title}</div>
          ${statusBadge(r.status)}
        </div>
        <div style="font-size:.8125rem;color:var(--text3);margin-bottom:12px">Generated ${r.date} · ${r.pages} pages</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px">
          ${r.tests.map(t=>`<span class="badge badge-blue">${t}</span>`).join('')}
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-secondary btn-sm" onclick="State.showReportPreview=true;navigate('reports')">${Icon.eye} Preview</button>
          <button class="btn btn-sm btn-ghost">${Icon.download} DOCX</button>
          <button class="btn btn-sm btn-ghost">${Icon.download} PDF</button>
        </div>
      </div>`).join('')}
    </div>

    ${State.showReportPreview ? `
    <div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
        <h3>Report Preview — Chapter 4</h3>
        <div style="display:flex;gap:8px">
          <button class="btn btn-primary">${Icon.download} Download DOCX</button>
          <button class="btn btn-ghost" onclick="State.showReportPreview=false;navigate('reports')">${Icon.x}</button>
        </div>
      </div>
      <div class="report-preview">
        <p style="text-align:center"><strong>CHAPTER FOUR</strong></p>
        <p style="text-align:center"><strong>DATA PRESENTATION, ANALYSIS AND DISCUSSION OF FINDINGS</strong></p>
        <br/>
        <p><strong>4.1 Introduction</strong></p>
        <p>This chapter presents the analysis of data collected from one hundred and twenty (120) undergraduate students at the University of Lagos concerning the effect of teaching methods on academic performance. Data were collected using a structured questionnaire consisting of twenty-two (22) items covering teaching clarity, student motivation, and academic performance (CGPA).</p>
        <br/>
        <p><strong>4.2 Descriptive Statistics</strong></p>
        <p>Table 4.1 presents the descriptive statistics for the dependent variable (CGPA) across the two teaching method groups.</p>
        <br/>
        <table>
          <tr><th>Teaching Method</th><th>N</th><th>Mean</th><th>Std. Deviation</th><th>Min</th><th>Max</th></tr>
          <tr><td>Traditional</td><td>58</td><td>3.21</td><td>0.44</td><td>2.30</td><td>4.10</td></tr>
          <tr><td>Computer-Based Learning</td><td>62</td><td>3.67</td><td>0.38</td><td>2.80</td><td>4.50</td></tr>
          <tr><td><strong>Total</strong></td><td><strong>120</strong></td><td><strong>3.45</strong></td><td><strong>0.46</strong></td><td><strong>2.30</strong></td><td><strong>4.50</strong></td></tr>
        </table>
        <br/>
        <p><strong>4.3 Test of Hypotheses</strong></p>
        <p><strong>Hypothesis One</strong></p>
        <p>H₀: There is no significant difference in academic performance (CGPA) between students taught using traditional methods and those taught using computer-based learning.</p>
        <p>H₁: There is a significant difference in academic performance (CGPA) between students taught using traditional methods and those taught using computer-based learning.</p>
        <br/>
        <table>
          <tr><th>Test</th><th>t</th><th>df</th><th>p-value</th><th>Cohen's d</th><th>95% CI</th></tr>
          <tr><td>Independent Samples t-test</td><td>3.213</td><td>118</td><td>0.003</td><td>0.583</td><td>[0.173, 0.742]</td></tr>
        </table>
        <br/>
        <p>The independent samples t-test yielded t(118) = 3.21, p = 0.003 which is less than the 0.05 level of significance. The mean CGPA of students in the computer-based learning group (M = 3.67, SD = 0.38) was significantly higher than that of students in the traditional group (M = 3.21, SD = 0.44). The effect size (Cohen's d = 0.58) indicates a medium practical significance. Therefore, the null hypothesis is rejected. There is a significant difference in academic performance based on teaching method.</p>
        <br/>
        <p><strong>4.4 Discussion of Findings</strong></p>
        <p>The findings of this study revealed that teaching method has a significant effect on student academic performance (p = 0.003 &lt; 0.05). These findings are consistent with Adeyemi (2022) who reported that computer-based learning approaches significantly improved student outcomes in Nigerian universities. The medium effect size (d = 0.58) suggests that the difference is not only statistically significant but also practically meaningful.</p>
      </div>
    </div>` : ''}
  </div>`;
}

// ====== EXPORT MODAL ======
function showExportModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay fade-in';
  overlay.onclick = (e) => { if(e.target===overlay) overlay.remove(); };
  overlay.innerHTML = `
  <div class="modal" onclick="event.stopPropagation()">
    <div class="modal-header">
      <div class="modal-title">Export Data</div>
      <button class="modal-close" onclick="this.closest('.modal-overlay').remove()">${Icon.x}</button>
    </div>
    <p style="margin-bottom:20px">Choose format to export your survey data</p>
    <div style="display:flex;flex-direction:column;gap:10px">
      ${[
        {fmt:'CSV',icon:'📄',desc:'Comma-separated values — compatible with all tools'},
        {fmt:'Excel (.xlsx)',icon:'📊',desc:'Microsoft Excel workbook with formatted sheets'},
        {fmt:'SPSS (.sav)',icon:'🔬',desc:'SPSS data file with value labels and measurement levels'},
        {fmt:'JSON',icon:'{ }',desc:'Machine-readable format for developers'},
        {fmt:'Codebook (PDF)',icon:'📋',desc:'Variable definitions, labels, and response codes'},
      ].map(e=>`
      <button class="card card-sm" style="display:flex;align-items:center;gap:14px;cursor:pointer;border:1px solid var(--border);text-align:left;width:100%;font-family:inherit;transition:all .15s"
        onmouseenter="this.style.background='var(--bg2)'"
        onmouseleave="this.style.background=''"
        onclick="this.closest('.modal-overlay').remove();showToast('Downloading ${e.fmt}…')">
        <span style="font-size:1.5rem">${e.icon}</span>
        <div>
          <div style="font-weight:600;font-size:.875rem;color:var(--text)">${e.fmt}</div>
          <div style="font-size:.8rem;color:var(--text3)">${e.desc}</div>
        </div>
        <span style="margin-left:auto;color:var(--text3)">${Icon.download}</span>
      </button>`).join('')}
    </div>
  </div>`;
  document.body.appendChild(overlay);
}

// ====== TOAST ======
function showToast(message, type='success') {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position:fixed;bottom:24px;right:24px;z-index:999;
    background:var(--text);color:var(--bg);
    padding:12px 20px;border-radius:10px;
    font-size:.875rem;font-weight:600;
    font-family:var(--font-body);
    box-shadow:var(--shadow-lg);
    animation:fadeIn .2s ease;
    display:flex;align-items:center;gap:10px;
    max-width:360px;
  `;
  toast.innerHTML = `${type==='success'?Icon.check:Icon.info} ${message}`;
  document.body.appendChild(toast);
  setTimeout(()=>toast.remove(), 3000);
}

// ====== ROUTER ======
function renderApp() {
  document.body.setAttribute('data-theme', State.theme);
  switch(State.currentView) {
    case 'dashboard': $('#app').innerHTML = renderDashboard(); break;
    case 'surveys': $('#app').innerHTML = renderSurveys(); break;
    case 'builder': $('#app').innerHTML = renderBuilder(); break;
    case 'share': $('#app').innerHTML = renderShare(); break;
    case 'respondent': $('#app').innerHTML = renderRespondent(); break;
    case 'analysis': $('#app').innerHTML = renderAnalysis(); break;
    case 'reports': $('#app').innerHTML = renderReports(); break;
    case 'survey-detail': $('#app').innerHTML = renderSurveys(); break;
    default: $('#app').innerHTML = renderDashboard();
  }
  // Add fade-in to new content
  const main = $('#app > *:first-child');
  if(main) main.classList.add('fade-in');
}

// ====== INIT ======
document.addEventListener('DOMContentLoaded', () => {
  State.builderQuestions = getDefaultQuestions();
  renderApp();
});

// Expose functions globally
window.navigate = navigate;
window.toggleTheme = toggleTheme;
window.addQuestion = addQuestion;
window.deleteQuestion = deleteQuestion;
window.updateQuestion = updateQuestion;
window.dragStart = dragStart;
window.dragOver = dragOver;
window.drop = drop;
window.saveSurvey = saveSurvey;
window.copyLink = copyLink;
window.submitSurvey = submitSurvey;
window.showExportModal = showExportModal;
window.showToast = showToast;
window.State = State;
