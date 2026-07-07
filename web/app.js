"use strict";

// ── Constants ─────────────────────────────────────────────────
const CARDS_VISIBLE = 9;

// ── State ─────────────────────────────────────────────────────
let data          = null;
let activecat     = "all";
let searchQ       = "";
let pollTimer     = null;
let isWebview     = false;
let selectedCard  = null;

// ── DOM helpers ───────────────────────────────────────────────
const $   = (id) => document.getElementById(id);
const esc = (s)  => (s || "")
  .replace(/&/g,"&amp;").replace(/</g,"&lt;")
  .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
const fmtNum = (n) =>
  n >= 1e6 ? (n/1e6).toFixed(1)+"M" : n >= 1000 ? (n/1000).toFixed(1)+"k" : String(n);

// ── Toast ─────────────────────────────────────────────────────
let _toastTimer;
function toast(msg, ms = 3000) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.remove("show"), ms);
}

// ── Source badge ──────────────────────────────────────────────
function srcBadge(source) {
  const map = { "GitHub Trending":"src-github", "GitHub":"src-github",
                "HackerNews":"src-hackernews", "Dev.to":"src-devto" };
  const cls   = map[source] ?? "src-github";
  const label = source === "GitHub Trending" ? "GitHub" : source;
  return `<span class="src-badge ${cls}">${esc(label)}</span>`;
}

// ── Rank-change badge ─────────────────────────────────────────
function rcBadge(rc) {
  if (rc == null)  return `<span class="rc rc-new">NEW</span>`;
  if (rc > 0)      return `<span class="rc rc-up">▲${rc}</span>`;
  if (rc < 0)      return `<span class="rc rc-down">▼${Math.abs(rc)}</span>`;
  return                  `<span class="rc rc-same">●</span>`;
}

function catCls(id) {
  return {
    dev:"tc-dev", ai:"tc-ai", learn:"tc-learn", design:"tc-design",
    devops:"tc-devops", security:"tc-security", data:"tc-data", mobile:"tc-mobile",
  }[id] ?? "";
}

// ── Open URL ──────────────────────────────────────────────────
function openUrl(url) {
  if (!url || !(url.startsWith("http://") || url.startsWith("https://"))) return;
  if (window.pywebview) {
    window.pywebview.api.open_tool_url(url, "");
  } else {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

// ── Copy to clipboard ─────────────────────────────────────────
async function copyCmd(text) {
  try {
    if (window.pywebview) {
      await pywebview.api.copy_to_clipboard(text);
    } else {
      await navigator.clipboard.writeText(text);
    }
    toast("📋 Copied!");
  } catch (_) {
    toast("Select the text and copy manually");
  }
}

// ── Smart install detection ───────────────────────────────────
function detectInstallCmds(tags, repo, url) {
  const t   = (tags || []).map(s => s.toLowerCase());
  const pkg = repo.replace(/[_\s]+/g, "-").toLowerCase();

  if (t.some(s => ["python","python3","jupyter","ipynb"].includes(s)))
    return [
      { cmd: `pip install ${pkg}`,  icon: "🐍", tip: "Python package manager" },
      { cmd: `pipx install ${pkg}`, icon: "🐍", tip: "Isolated env (recommended for CLI tools)" },
    ];

  if (t.some(s => ["javascript","typescript","node.js","nodejs","npm"].includes(s)))
    return [
      { cmd: `npm install -g ${pkg}`, icon: "📦", tip: "Install globally with npm" },
      { cmd: `npx ${pkg}`,            icon: "⚡", tip: "Run once without installing" },
    ];

  if (t.some(s => s === "rust"))
    return [{ cmd: `cargo install ${pkg}`, icon: "🦀", tip: "Rust package manager" }];

  if (t.some(s => s === "go")) {
    const m = url.match(/github\.com\/([^/?#]+\/[^/?#]+)/);
    if (m) return [{ cmd: `go install github.com/${m[1]}@latest`, icon: "🐹", tip: "Go module install" }];
  }

  if (t.some(s => ["ruby","gem"].includes(s)))
    return [{ cmd: `gem install ${pkg}`, icon: "💎", tip: "Ruby gem" }];

  if (t.some(s => ["shell","bash","zsh","fish"].includes(s)))
    return [{ cmd: `git clone --depth=1 ${url} ~/tools/${repo}`, icon: "🐚", tip: "Clone shell scripts" }];

  return [{ cmd: `git clone --depth=1 ${url}`, icon: "⬇", tip: "Clone the repository" }];
}

// ── pywebview detection ───────────────────────────────────────
function detectWebview() {
  const check = () => {
    if (window.pywebview) {
      try { pywebview.api.is_app().then(v => { isWebview = !!v; }); } catch (_) {}
    }
  };
  if (window.pywebview) { check(); }
  else { window.addEventListener("pywebviewready", check, { once: true }); }
}

// ── Load & render ─────────────────────────────────────────────
async function loadData() {
  try {
    const r = await fetch("/api/tools");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    data = await r.json();
    render();
  } catch (e) {
    $("loadingState").classList.add("hidden");
    $("emptyState").classList.remove("hidden");
    toast("⚠ Failed to load: " + e.message);
  }
}

function render() {
  $("loadingState").classList.add("hidden");
  if (!data?.categories?.length) { $("emptyState").classList.remove("hidden"); return; }
  $("emptyState").classList.add("hidden");
  $("app").classList.remove("hidden");
  renderMeta();
  renderTabs();
  renderSuggestion();
  renderMovers();
  renderCategories();
}

// ── Meta line ─────────────────────────────────────────────────
function renderMeta() {
  const el = $("updateInfo");
  if (!data.last_updated) { el.textContent = ""; return; }
  const days = Math.floor((Date.now() - new Date(data.last_updated)) / 86400000);
  let txt = days === 0 ? "Updated today" : days === 1 ? "Updated yesterday" : `Updated ${days}d ago`;
  if (days >= 7) { txt += " ⚠"; el.classList.add("stale"); } else el.classList.remove("stale");
  el.textContent = txt;
}

// ── Nav tabs ──────────────────────────────────────────────────
function renderTabs() {
  const nav = $("navInner");
  nav.querySelectorAll(".nav-tab:not([data-cat='all'])").forEach(e => e.remove());
  for (const cat of data.categories) {
    const medal = ["🥇","🥈","🥉",""][Math.min(cat.rank - 1, 3)];
    const btn = document.createElement("button");
    btn.className   = "nav-tab";
    btn.dataset.cat = cat.id;
    btn.textContent = `${medal} ${cat.icon} ${cat.name}`;
    btn.addEventListener("click", () => filterCat(cat.id));
    nav.appendChild(btn);
  }
}

// ── Suggestion of the day ─────────────────────────────────────
function renderSuggestion() {
  const s = data.suggestion_of_the_day;
  if (!s) { $("suggestionSection").classList.add("hidden"); return; }
  $("suggestionSection").classList.remove("hidden");

  const cat     = data.categories.find(c => c.tools?.some(t => t.id === s.id));
  const catIcon = cat?.icon ?? "🔧";

  const card = $("suggestionCard");
  card.innerHTML = `
    <div class="sug-icon">${catIcon}</div>
    <div class="sug-body">
      <div class="sug-name">${esc(s.name)}</div>
      <div class="sug-desc">${esc(s.description)}</div>
      <div class="sug-meta">
        ${srcBadge(s.source)}
        <span class="tc-score">${esc(s.score_label)}</span>
        ${rcBadge(s.rank_change)}
        ${(s.tags||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join("")}
      </div>
    </div>
    <div class="sug-side">
      <a class="sug-open" id="sugOpenBtn" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">Open ↗</a>
      <button class="sug-detail" id="sugDetailBtn">Details</button>
      <span class="sug-cat">${esc(cat?.name ?? "")}</span>
    </div>
  `;

  if (cat?.color) card.style.borderColor = cat.color + "35";

  $("sugOpenBtn").addEventListener("click", (e) => e.stopPropagation());
  $("sugDetailBtn").onclick = (e) => { e.stopPropagation(); openDetailPanel(s, cat, null); };
  card.onclick = () => openDetailPanel(s, cat, null);
}

// ── Top movers ────────────────────────────────────────────────
function renderMovers() {
  const movers = data.categories
    .flatMap(c => c.tools.map(t => ({ ...t, catName: c.name, catIcon: c.icon, catColor: c.color, catId: c.id })))
    .filter(t => t.rank_change > 0)
    .sort((a, b) => b.rank_change - a.rank_change)
    .slice(0, 8);

  if (!movers.length) { $("moversSection").classList.add("hidden"); return; }
  $("moversSection").classList.remove("hidden");

  const list = $("moversList");
  list.innerHTML = "";
  movers.forEach(t => {
    const cat  = data.categories.find(c => c.id === t.catId);
    const card = document.createElement("div");
    card.className = "mover-card";
    card.style.borderColor = (t.catColor || "#388BFD") + "40";
    card.innerHTML = `
      <div class="mover-top">
        <span class="mover-name">${esc(t.name)}</span>
        ${rcBadge(t.rank_change)}
      </div>
      <div class="mover-score-row">
        <span class="mover-cat">${esc(t.catIcon)} ${esc(t.catName)}</span>
        <span class="tc-score">${esc(t.score_label)}</span>
      </div>
    `;
    card.onclick = () => openDetailPanel(t, cat, null);
    list.appendChild(card);
  });
}

// ── Category sections ─────────────────────────────────────────
function renderCategories() {
  const container = $("categoriesContainer");
  container.innerHTML = "";
  const q = searchQ.toLowerCase().trim();
  let totalShown = 0;

  for (const cat of data.categories) {
    if (activecat !== "all" && cat.id !== activecat) continue;

    let tools = cat.tools;
    if (q) tools = tools.filter(t =>
      t.name.toLowerCase().includes(q) ||
      t.description.toLowerCase().includes(q) ||
      (t.tags||[]).some(tag => tag.toLowerCase().includes(q))
    );
    if (!tools.length) continue;
    totalShown += tools.length;

    const rankCls = ["r1","r2","r3","r4"][Math.min(cat.rank - 1, 3)];
    const section = document.createElement("section");
    section.className = "category-section";
    section.id        = `cat-${cat.id}`;

    const countLabel = q ? `${tools.length} result${tools.length !== 1 ? "s" : ""}` : `${tools.length} tools`;

    section.innerHTML = `
      <div class="cat-header">
        <div class="cat-rank ${rankCls}">${cat.rank}</div>
        <span class="cat-icon">${cat.icon}</span>
        <span class="cat-name" style="color:${cat.color}">${esc(cat.name)}</span>
        <div class="cat-meta">
          ${rcBadge(cat.rank_change)}
          <span class="cat-stats">${countLabel} · ${fmtNum(cat.total_score)} pts</span>
        </div>
      </div>
      <div class="tools-grid" id="grid-${cat.id}"></div>
    `;
    container.appendChild(section);

    const grid    = $(`grid-${cat.id}`);
    const visible = q ? tools : tools.slice(0, CARDS_VISIBLE);
    visible.forEach(t => grid.appendChild(buildCard(t, cat)));

    if (!q && tools.length > CARDS_VISIBLE) {
      const remaining = tools.length - CARDS_VISIBLE;
      const btn = document.createElement("button");
      btn.className   = "show-more-btn";
      btn.textContent = `Show ${remaining} more`;
      btn.onclick = () => {
        tools.slice(CARDS_VISIBLE).forEach(t => grid.appendChild(buildCard(t, cat)));
        btn.remove();
      };
      section.appendChild(btn);
    }
  }

  if (!totalShown) {
    container.innerHTML = `
      <div class="state-screen" style="min-height:200px">
        <p>No tools match <strong>"${esc(searchQ)}"</strong></p>
      </div>`;
  }
}

// ── Build tool card ───────────────────────────────────────────
function buildCard(tool, cat) {
  const div = document.createElement("div");
  div.className = `tool-card ${catCls(cat.id)}`;
  div.setAttribute("tabindex", "0");

  const rankCls = tool.rank <= 3 ? " gold" : "";

  div.innerHTML = `
    <div class="tc-top">
      <span class="tc-rank${rankCls}">#${tool.rank}</span>
      <span class="tc-name">${esc(tool.name)}</span>
      <div class="tc-badges">
        ${srcBadge(tool.source)}
        ${rcBadge(tool.rank_change)}
      </div>
    </div>
    <div class="tc-desc">${esc(tool.description)}</div>
    <div class="tc-foot">
      <div class="tc-tags">${(tool.tags||[]).slice(0,3).map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</div>
      <div class="tc-foot-right">
        <span class="tc-score">${esc(tool.score_label)}</span>
        ${tool.url ? `<a class="tc-open-btn" href="${esc(tool.url)}" target="_blank" rel="noopener noreferrer" title="${esc(tool.name)}">Open ↗</a>` : ""}
      </div>
    </div>
  `;

  div.querySelector(".tc-open-btn")?.addEventListener("click", (e) => e.stopPropagation());

  div.addEventListener("click", () => openDetailPanel(tool, cat, div));
  div.addEventListener("keydown", (e) => {
    if (e.key === "Enter") openDetailPanel(tool, cat, div);
    if (e.key === " ")    { e.preventDefault(); openUrl(tool.url); }
  });

  return div;
}

// ── Install helper ────────────────────────────────────────────
async function _runInstall(btnId, action) {
  const btn    = $(btnId);
  const result = $("installResult");
  btn.disabled = true;
  btn.classList.add("running");
  result.className = "install-result hidden";
  try {
    const { ok, msg } = await action();
    result.className = `install-result ${ok ? "ok" : "err"}`;
    result.textContent = ok ? `✓  ${msg}` : `✗  ${msg}`;
  } catch (e) {
    result.className = "install-result err";
    result.textContent = `✗  ${e.message}`;
  } finally {
    btn.disabled = false;
    btn.classList.remove("running");
  }
}

// ── Live repo info ────────────────────────────────────────────
async function _loadRepoInfo(url) {
  if (!window.pywebview) return;
  try {
    const info = await pywebview.api.get_repo_info(url);
    if (info.error) return;

    // Stats row
    const statsEl = $("dpRepoStats");
    if (statsEl) {
      const parts = [];
      if (info.stars    != null) parts.push(`⭐ ${fmtNum(info.stars)}`);
      if (info.forks    != null) parts.push(`🍴 ${fmtNum(info.forks)}`);
      if (info.language)         parts.push(`<span class="dp-lang">${esc(info.language)}</span>`);
      if (info.license)          parts.push(`📄 ${esc(info.license)}`);
      if (info.open_issues)      parts.push(`🐛 ${info.open_issues} issues`);
      statsEl.innerHTML = parts.map(p => `<span class="dp-stat">${p}</span>`).join("");
      statsEl.classList.toggle("hidden", !parts.length);
    }

    // Topics
    if (info.topics?.length) {
      const topicsEl = $("dpTopics");
      if (topicsEl) {
        topicsEl.innerHTML = info.topics.map(t => `<span class="tag topic-tag">${esc(t)}</span>`).join("");
        topicsEl.classList.remove("hidden");
      }
    }

    // Homepage
    if (info.homepage) {
      const homeEl = $("dpHomepage");
      if (homeEl) {
        homeEl.innerHTML = `<a class="dp-homepage-link" href="${esc(info.homepage)}" target="_blank" rel="noopener noreferrer">🌐 ${esc(info.homepage)}</a>`;
        homeEl.classList.remove("hidden");
      }
    }
  } catch (_) {}
}

// ── GitHub state loader ───────────────────────────────────────
async function _loadGhState(url, repo) {
  try {
    const s = await pywebview.api.check_repo_state(url);

    const cloneBtn = $("cloneBtn");
    if (cloneBtn && s.cloned) {
      cloneBtn.classList.replace("get-clone", "get-update");
      $("cloneTitle").textContent = `Update ~/tools/${repo}`;
      $("cloneSub").textContent   = "git pull — fetch latest changes";
      cloneBtn.onclick = () => _runInstall("cloneBtn", () =>
        pywebview.api.update_repo(repo).then(r =>
          r.success ? { ok: true,  msg: r.output || "Already up to date" }
                    : { ok: false, msg: r.error }
        )
      );
    } else if (cloneBtn) {
      cloneBtn.onclick = () => _runInstall("cloneBtn", () =>
        pywebview.api.clone_repo(url).then(r =>
          r.success ? { ok: true,  msg: r.already ? `Already at ~/tools/${repo}` : `Cloned to ~/tools/${repo}` }
                    : { ok: false, msg: r.error }
        )
      );
    }

    const starBtn   = $("starBtn");
    const starIcon  = $("starIcon");
    const starLabel = $("starLabel");
    if (starBtn) {
      if (s.starred) {
        starBtn.classList.add("active");
        starIcon.textContent  = "★";
        starLabel.textContent = "Starred";
      }
      starBtn.disabled = false;
      starBtn.onclick = async () => {
        const on = starBtn.classList.contains("active");
        starBtn.disabled = true;
        const r = on ? await pywebview.api.unstar_repo(url)
                     : await pywebview.api.star_repo(url);
        starBtn.disabled = false;
        if (r.success) {
          starBtn.classList.toggle("active", !on);
          starIcon.textContent  = on ? "☆" : "★";
          starLabel.textContent = on ? "Star" : "Starred";
          toast(on ? "Unstarred" : "⭐ Starred!");
        } else {
          toast("⚠ " + (r.error || "Run: gh auth login"));
        }
      };
    }

    const watchBtn   = $("watchBtn");
    const watchLabel = $("watchLabel");
    if (watchBtn) {
      if (s.watching) {
        watchBtn.classList.add("active");
        watchLabel.textContent = "Watching";
      }
      watchBtn.disabled = false;
      watchBtn.onclick = async () => {
        const on = watchBtn.classList.contains("active");
        watchBtn.disabled = true;
        const r = on ? await pywebview.api.unwatch_repo(url)
                     : await pywebview.api.watch_repo(url);
        watchBtn.disabled = false;
        if (r.success) {
          watchBtn.classList.toggle("active", !on);
          watchLabel.textContent = on ? "Watch" : "Watching";
          toast(on ? "Unwatched" : "🔔 Watching!");
        } else {
          toast("⚠ " + (r.error || "Run: gh auth login"));
        }
      };
    }

    if (!s.gh_available) {
      [starBtn, watchBtn].forEach(b => {
        if (b) { b.disabled = true; b.title = "Run: gh auth login in Terminal"; }
      });
    }

  } catch (_) {}
}

// ── Detail panel ──────────────────────────────────────────────
function openDetailPanel(tool, cat, cardEl) {
  selectedCard?.classList.remove("selected");
  selectedCard = cardEl;
  cardEl?.classList.add("selected");

  const rc = tool.rank_change;
  let changeBlock;
  if (rc == null) {
    changeBlock = `<div class="dp-change new"><span>✨</span><div><b>New this week</b><div class="dp-sub">First time appearing</div></div></div>`;
  } else if (rc > 0) {
    changeBlock = `<div class="dp-change up"><span>▲</span><div><b style="color:var(--rc-up)">Rose ${rc} spot${rc>1?"s":""}</b><div class="dp-sub">Was #${tool.rank + rc} last week</div></div></div>`;
  } else if (rc < 0) {
    const d = Math.abs(rc);
    changeBlock = `<div class="dp-change down"><span>▼</span><div><b style="color:var(--rc-down)">Dropped ${d} spot${d>1?"s":""}</b><div class="dp-sub">Was #${tool.rank - d} last week</div></div></div>`;
  } else {
    changeBlock = `<div class="dp-change same"><span>●</span><div><b>Held position</b><div class="dp-sub">Same rank as last week</div></div></div>`;
  }

  const catColor = cat?.color ?? "#58A6FF";
  const prevRank = (rc != null) ? tool.rank + rc : null;

  // Detect install commands
  const ghM = (tool.url || "").match(/^https?:\/\/github\.com\/([^/?#]+)\/([^/?#]+?)(?:\.git)?\/?$/);
  const repo = ghM ? ghM[2] : null;
  const installCmds = repo ? detectInstallCmds(tool.tags, repo, tool.url) : [];

  const installSection = installCmds.length ? `
    <div class="dp-section">
      <div class="dp-section-label">⚡ Quick Install</div>
      ${installCmds.map((c, i) => `
        <div class="cmd-block${i > 0 ? " cmd-alt" : ""}">
          <span class="cmd-icon">${c.icon}</span>
          <code class="cmd-text">${esc(c.cmd)}</code>
          <button class="copy-btn" title="${esc(c.tip)}" onclick="copyCmd(${JSON.stringify(c.cmd)})">Copy</button>
        </div>
      `).join("")}
    </div>
  ` : "";

  $("dpBody").innerHTML = `
    <span class="dp-cat-badge" style="background:${catColor}18;color:${catColor};border:1px solid ${catColor}35">
      ${cat?.icon ?? "🔧"} ${esc(cat?.name ?? "")}
    </span>

    <div class="dp-title">${esc(tool.name)}</div>
    <div class="dp-desc">${esc(tool.description) || `<em style="opacity:.45">No description</em>`}</div>

    <div class="dp-stats-row hidden" id="dpRepoStats"></div>
    <div class="hidden" id="dpHomepage"></div>

    <div class="dp-grid">
      <div class="dp-cell"><div class="dp-label">Score</div><div class="dp-val">${esc(tool.score_label)}</div></div>
      <div class="dp-cell"><div class="dp-label">Source</div><div class="dp-val">${srcBadge(tool.source)}</div></div>
      <div class="dp-cell"><div class="dp-label">Rank now</div><div class="dp-val">#${tool.rank}</div></div>
      <div class="dp-cell"><div class="dp-label">Last week</div><div class="dp-val">${prevRank != null ? "#"+prevRank : "—"}</div></div>
    </div>

    <div class="dp-weekly">
      <div class="dp-weekly-label">🗓 Weekly Rank</div>
      ${changeBlock}
    </div>

    ${(tool.tags||[]).length ? `<div class="dp-tags">${tool.tags.map(t=>`<span class="tag">${esc(t)}</span>`).join("")}</div>` : ""}
    <div class="dp-topics hidden" id="dpTopics"></div>

    ${installSection}

    <a class="dp-visit" id="dpVisit" href="${esc(tool.url)}" target="_blank" rel="noopener noreferrer">Open Site ↗</a>
  `;

  // GitHub actions section
  if (ghM) {
    const [, , repoName] = ghM;
    const pkgName = repoName.toLowerCase().replace(/[_\s]+/g, "-");
    const sec = document.createElement("div");
    sec.className = "get-tool-section";
    sec.innerHTML = `
      <div class="get-tool-label">↓ Get This Tool</div>
      <button class="get-action-btn get-clone" id="cloneBtn">
        <span class="ga-icon">⬇</span>
        <span class="ga-text">
          <span class="ga-title" id="cloneTitle">Clone to ~/tools/${esc(repoName)}</span>
          <span class="ga-sub"   id="cloneSub">git clone — saves repo files to your Mac</span>
        </span>
      </button>
      <button class="get-action-btn get-pip" id="pipBtn">
        <span class="ga-icon">🐍</span>
        <span class="ga-text">
          <span class="ga-title">pip install ${esc(pkgName)}</span>
          <span class="ga-sub">Install as Python package (if available on PyPI)</span>
        </span>
      </button>
      <div class="gh-action-row">
        <button class="gh-btn" id="starBtn" disabled title="Loading…">
          <span class="gh-btn-icon" id="starIcon">☆</span>
          <span id="starLabel">Star</span>
        </button>
        <button class="gh-btn gh-desktop" id="desktopBtn">
          <span class="gh-btn-icon">🖥</span>
          <span>GitHub Desktop</span>
        </button>
        <button class="gh-btn" id="watchBtn" disabled title="Loading…">
          <span class="gh-btn-icon">🔔</span>
          <span id="watchLabel">Watch</span>
        </button>
      </div>
      <div class="install-result hidden" id="installResult"></div>
    `;

    // Insert before the visit button
    const visitBtn = $("dpVisit");
    $("dpBody").insertBefore(sec, visitBtn);

    if (!isWebview) {
      sec.querySelectorAll(".get-action-btn, .gh-btn").forEach(b => {
        b.disabled = true;
        b.title = "Open the ToolRadar desktop app to use this";
      });
      const note = document.createElement("p");
      note.className = "install-note";
      note.textContent = "Launch the desktop app to use these features";
      sec.appendChild(note);
    } else {
      $("desktopBtn").onclick = () => pywebview.api.open_in_github_desktop(tool.url);

      $("pipBtn").onclick = () => _runInstall("pipBtn", () =>
        pywebview.api.pip_install(pkgName).then(r =>
          r.success ? { ok: true,  msg: `Installed ${pkgName}` }
                    : { ok: false, msg: r.error }
        )
      );

      $("cloneBtn").onclick = () => _runInstall("cloneBtn", () =>
        pywebview.api.clone_repo(tool.url).then(r =>
          r.success ? { ok: true,  msg: r.already ? `Already at ~/tools/${repoName}` : `Cloned to ~/tools/${repoName}` }
                    : { ok: false, msg: r.error }
        )
      );

      _loadGhState(tool.url, repoName);
      _loadRepoInfo(tool.url);
    }
  } else if (isWebview && tool.url) {
    _loadRepoInfo(tool.url);
  }

  $("detailPanel").classList.remove("hidden", "closing");
  $("detailOverlay").classList.remove("hidden");
  $("mainContent").classList.add("panel-open");

  setTimeout(() => $("dpVisit")?.focus(), 180);
}

function closeDetailPanel() {
  const panel = $("detailPanel");
  panel.classList.add("closing");
  panel.addEventListener("animationend", () => {
    panel.classList.add("hidden");
    panel.classList.remove("closing");
  }, { once: true });
  $("detailOverlay").classList.add("hidden");
  $("mainContent").classList.remove("panel-open");
  selectedCard?.classList.remove("selected");
  selectedCard = null;
}

// ── Filter / Search ───────────────────────────────────────────
function filterCat(id) {
  activecat = id;
  if (id !== "all") { searchQ = ""; $("search").value = ""; $("clearSearch").classList.remove("visible"); }
  document.querySelectorAll(".nav-tab").forEach(t => t.classList.toggle("active", t.dataset.cat === id));
  renderCategories();
  if (id !== "all") document.getElementById(`cat-${id}`)?.scrollIntoView({ behavior:"smooth", block:"start" });
}

// ── Refresh ───────────────────────────────────────────────────
async function triggerRefresh() {
  const btn = $("refreshBtn");
  btn.classList.add("loading");
  btn.disabled = true;
  toast("📡 Refreshing… ~60 s", 10000);
  try {
    await fetch("/api/refresh");
    let tries = 0;
    pollTimer = setInterval(async () => {
      tries++;
      const st = await fetch("/api/status").then(r => r.json());
      if (!st.running) {
        clearInterval(pollTimer);
        btn.classList.remove("loading"); btn.disabled = false;
        toast("✅ Done!"); await loadData();
      }
      if (tries > 48) {
        clearInterval(pollTimer);
        btn.classList.remove("loading"); btn.disabled = false;
        toast("⏱ Timed out"); await loadData();
      }
    }, 5000);
  } catch (e) {
    btn.classList.remove("loading"); btn.disabled = false;
    toast("⚠ " + e.message);
  }
}

// ── Event wiring ──────────────────────────────────────────────
$("refreshBtn").addEventListener("click", triggerRefresh);
$("emptyFetchBtn").addEventListener("click", triggerRefresh);
$("dpClose").addEventListener("click", closeDetailPanel);
$("detailOverlay").addEventListener("click", closeDetailPanel);

$("search").addEventListener("input", e => {
  searchQ = e.target.value;
  $("clearSearch").classList.toggle("visible", searchQ.length > 0);
  if (searchQ) {
    activecat = "all";
    document.querySelectorAll(".nav-tab").forEach(t => t.classList.toggle("active", t.dataset.cat === "all"));
  }
  renderCategories();
});

$("clearSearch").addEventListener("click", () => {
  $("search").value = ""; searchQ = "";
  $("clearSearch").classList.remove("visible");
  renderCategories();
});

document.querySelector("[data-cat='all']").addEventListener("click", () => filterCat("all"));

document.addEventListener("keydown", e => {
  if (e.key === "Escape" && !$("detailPanel").classList.contains("hidden")) closeDetailPanel();
});

// ── Boot ──────────────────────────────────────────────────────
detectWebview();
loadData();

// ── Theme system ──────────────────────────────────────────────
const THEMES = [
  { id: 'howl',     label: "Howl's Castle",    emoji: '🔥',
    colors: ['#EAC41A','#2B1A10','#0D0804','#E75B64','#4F90CA'] },
  { id: 'spirited', label: 'Spirited Away',     emoji: '🏮',
    colors: ['#D4A017','#3A0810','#0D0205','#7C7D9D','#F5D0C8'] },
  { id: 'mononoke', label: 'Princess Mononoke', emoji: '🌲',
    colors: ['#C74148','#0D1B0F','#070E09','#769B7C','#DBB9A0'] },
  { id: 'kiki',     label: "Kiki's Delivery",   emoji: '🧹',
    colors: ['#6C4453','#64B2F9','#FBFFF3','#A5839A','#EBD28D'] },
  { id: 'laputa',   label: 'Castle in the Sky', emoji: '🌟',
    colors: ['#F0D77B','#B4DAE5','#AE93BE','#403369','#14191F'] },
];

let currentTheme  = localStorage.getItem('toolradar-theme')  || 'howl';
let currentFont   = localStorage.getItem('toolradar-font')   || 'serif';
let currentSize   = localStorage.getItem('toolradar-size')   || 'normal';
let currentAccent = localStorage.getItem('toolradar-accent') || '';
let themePanelBuilt = false;

// Ghibli accent palette — real film colors from researched palettes
const ACCENTS = [
  { color: '#EAC41A', label: 'Calcifer' },
  { color: '#E75B64', label: 'Ember'    },
  { color: '#4F90CA', label: 'Sky'      },
  { color: '#C74148', label: 'Mononoke' },
  { color: '#769B7C', label: 'Forest'   },
  { color: '#D4A017', label: 'Lantern'  },
  { color: '#A5839A', label: 'Kiki'     },
  { color: '#F0D77B', label: 'Crystal'  },
  { color: '#BD6E56', label: 'Bakery'   },
  { color: '#5C5992', label: 'Laputa'   },
];

function initTheme() {
  applyTheme(currentTheme, false);
  applyFont(currentFont, false);
  applySize(currentSize, false);
  if (currentAccent) applyAccent(currentAccent, false);
  const btn = $('themeBtn');
  if (btn) btn.onclick = toggleThemePanel;
}

function applyFont(fontId, save = true) {
  currentFont = fontId;
  if (fontId === 'serif') document.documentElement.removeAttribute('data-font');
  else document.documentElement.dataset.font = fontId;
  if (save) localStorage.setItem('toolradar-font', fontId);
  document.querySelectorAll('.tp-toggle[data-font]').forEach(b => {
    b.classList.toggle('active', b.dataset.font === fontId);
  });
}

function applySize(sizeId, save = true) {
  currentSize = sizeId;
  if (sizeId === 'normal') document.documentElement.removeAttribute('data-size');
  else document.documentElement.dataset.size = sizeId;
  if (save) localStorage.setItem('toolradar-size', sizeId);
  document.querySelectorAll('.tp-toggle[data-size]').forEach(b => {
    b.classList.toggle('active', b.dataset.size === sizeId);
  });
}

function applyAccent(color, save = true) {
  currentAccent = color;
  const root = document.documentElement;
  if (color) {
    root.style.setProperty('--fire-gold', color);
    root.style.setProperty('--accent', color);
  } else {
    root.style.removeProperty('--fire-gold');
    root.style.removeProperty('--accent');
  }
  if (save) localStorage.setItem('toolradar-accent', color);
  document.querySelectorAll('.tp-accent-dot').forEach(d => {
    d.classList.toggle('active', d.dataset.color === color);
  });
}

function applyTheme(themeId, save = true) {
  currentTheme = themeId;
  if (themeId === 'howl') {
    document.documentElement.removeAttribute('data-theme');
  } else {
    document.documentElement.dataset.theme = themeId;
  }
  if (save) localStorage.setItem('toolradar-theme', themeId);
  document.querySelectorAll('.tp-card').forEach(c => {
    c.classList.toggle('active', c.dataset.theme === themeId);
  });
  const btn = $('themeBtn');
  if (btn) btn.classList.toggle('active', themeId !== 'howl');
}

function buildThemePanel() {
  if (themePanelBuilt) return;
  themePanelBuilt = true;

  const overlay = document.createElement('div');
  overlay.id = 'themeOverlay';
  overlay.className = 'theme-overlay hidden';
  overlay.onclick = closeThemePanel;
  document.body.appendChild(overlay);

  const panel = document.createElement('aside');
  panel.id = 'themePanel';
  panel.className = 'theme-panel hidden';
  panel.innerHTML = `
    <div class="tp-header">
      <span class="tp-title">🎨 自定义</span>
      <button class="tp-close" id="tpClose">✕</button>
    </div>

    <div class="tp-section-label" style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--text3);margin-bottom:8px;font-family:-apple-system,sans-serif;">
      主题 Theme
    </div>
    <div class="tp-cards">
      ${THEMES.map(t => `
        <button class="tp-card${t.id === currentTheme ? ' active' : ''}" data-theme="${t.id}">
          <div class="tp-preview">
            ${t.colors.map(c => `<span class="tp-dot" style="background:${c}"></span>`).join('')}
          </div>
          <div class="tp-info">
            <span class="tp-emoji">${t.emoji}</span>
            <span class="tp-label">${t.label}</span>
          </div>
        </button>
      `).join('')}
    </div>

    <div class="tp-section">
      <div class="tp-section-label">高亮色 Accent</div>
      <div class="tp-accent-grid" id="tpAccentGrid">
        ${ACCENTS.map(a => `
          <div class="tp-accent-dot${a.color === currentAccent ? ' active' : ''}"
               data-color="${a.color}"
               title="${a.label}"
               style="background:${a.color}"></div>
        `).join('')}
      </div>
    </div>

    <div class="tp-section">
      <div class="tp-section-label">字体 Font</div>
      <div class="tp-toggle-row">
        <button class="tp-toggle${currentFont === 'serif' ? ' active' : ''}" data-font="serif">✏ Serif</button>
        <button class="tp-toggle${currentFont === 'sans'  ? ' active' : ''}" data-font="sans">A Sans</button>
      </div>
    </div>

    <div class="tp-section">
      <div class="tp-section-label">大小 Size</div>
      <div class="tp-toggle-row">
        <button class="tp-toggle${currentSize === 'normal' ? ' active' : ''}" data-size="normal">A 标准</button>
        <button class="tp-toggle${currentSize === 'large'  ? ' active' : ''}" data-size="large">A 大字</button>
      </div>
    </div>

    <div class="tp-section" style="padding-bottom:4px">
      <button class="tp-toggle" id="tpReset" style="width:100%;font-size:12px;color:var(--text3)">↺ 重置默认</button>
    </div>
  `;
  document.body.appendChild(panel);

  $('tpClose').onclick = closeThemePanel;
  panel.querySelectorAll('.tp-card').forEach(card => {
    card.onclick = () => { applyTheme(card.dataset.theme); applyAccent(''); };
  });
  panel.querySelectorAll('.tp-accent-dot').forEach(dot => {
    dot.onclick = () => applyAccent(dot.dataset.color === currentAccent ? '' : dot.dataset.color);
  });
  panel.querySelectorAll('.tp-toggle[data-font]').forEach(btn => {
    btn.onclick = () => applyFont(btn.dataset.font);
  });
  panel.querySelectorAll('.tp-toggle[data-size]').forEach(btn => {
    btn.onclick = () => applySize(btn.dataset.size);
  });
  $('tpReset').onclick = () => {
    applyTheme('howl'); applyFont('serif'); applySize('normal'); applyAccent('');
  };
}

function toggleThemePanel() {
  buildThemePanel();
  const panel = $('themePanel');
  const overlay = $('themeOverlay');
  if (panel.classList.contains('hidden')) {
    panel.classList.remove('hidden');
    overlay.classList.remove('hidden');
  } else {
    closeThemePanel();
  }
}

function closeThemePanel() {
  $('themePanel')?.classList.add('hidden');
  $('themeOverlay')?.classList.add('hidden');
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeThemePanel();
});

document.addEventListener('DOMContentLoaded', initTheme);
