/* gooddeeds.space Client-Side Vanilla JS SPA Controller */

const API_BASE = "/api";
let currentUser = null;
let currentToken = localStorage.getItem("gd_token") || null;

// Discussion thread state persistence (Req #3)
const expandedThreads = new Set();

// Synchronized startup sequence promise (Req #2)
let sessionPromise = null;

// Feed filters state
let currentTheme = "";
let currentGroupFilter = "";
let currentSortMode = "smart";
let currentSearch = "";
let currentTypeFilter = "";
let currentMyKudosMode = "";
let currentMyPostsMode = "";

// Wizard temporary draft storage (Feature 21)
let draftPost = null;

// Active Group Detail State
let activeGroupId = null;
let activeGroupData = null;

// Active Profile User State
let activeProfileData = null;
let currentProfileTab = "posts";

/* ================= INITIALIZATION & ROUTING ================= */

sessionPromise = checkSession();

window.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await sessionPromise;
  await loadQuickNavGroups();
  await handleRoute();
});

window.addEventListener("hashchange", async () => {
  await handleRoute();
});

function setupEventListeners() {
  let searchTimeout;
  const feedSearch = document.getElementById("feed-search-input");
  if (feedSearch) {
    feedSearch.addEventListener("input", (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentSearch = e.target.value.trim();
        loadFeed();
      }, 300);
    });
  }

  let gSearchTimeout;
  const grpSearch = document.getElementById("group-search-input");
  if (grpSearch) {
    grpSearch.addEventListener("input", (e) => {
      clearTimeout(gSearchTimeout);
      gSearchTimeout = setTimeout(() => {
        loadGroups(e.target.value.trim());
      }, 300);
    });
  }

  // Close Quick Nav dropdown when clicking outside
  document.addEventListener("click", (e) => {
    const container = document.getElementById("quick-nav-container");
    if (container && !container.contains(e.target)) {
      const dropdown = container.querySelector("div");
      if (dropdown) dropdown.classList.add("hidden");
    }
  });

  const quickBtn = document.querySelector("#quick-nav-container button");
  if (quickBtn) {
    quickBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const dropdown = document.querySelector("#quick-nav-container div");
      if (dropdown) dropdown.classList.toggle("hidden");
    });
  }
}

async function handleRoute() {
  await sessionPromise;
  const hash = window.location.hash || "#/";
  const path = hash.replace("#", "").split("?")[0];

  hideAllViews();

  if (path === "" || path === "/") {
    if (currentUser) {
      navigateTo("/feed");
      return;
    }
    showView("view-landing");
    loadLandingPreview();
  } else if (path === "/feed") {
    showView("view-feed");
    loadFeed();
    populateGroupFilterDropdown();
  } else if (path.startsWith("/kudos/") || path.startsWith("/post/") || path.startsWith("/posts/")) {
    showView("view-single-item");
    const id = path.split("/")[2];
    loadSingleItemView(id);
  } else if (path === "/groups") {
    showView("view-groups");
    loadGroups();
  } else if (path.startsWith("/group/")) {
    showView("view-group-detail");
    activeGroupId = path.split("/")[2];
    loadGroupDetail(activeGroupId);
  } else if (path === "/profile") {
    if (!currentUser) {
      showToast("Please log in to view your profile.");
      navigateTo("/");
      openModal("modal-login");
      return;
    }
    showView("view-profile");
    loadUserProfile(currentUser.id);
  } else if (path.startsWith("/user/")) {
    showView("view-profile");
    const targetId = path.split("/")[2];
    loadUserProfile(targetId);
  } else if (path === "/outbox") {
    showView("view-outbox");
    loadOutbox();
  } else if (path === "/code" || path === "/source" || path === "/browse") {
    showView("view-code");
    browseSourceFile("server.py");
  } else if (path === "/spotlight" || path === "/gamification" || path === "/halloffame") {
    showView("view-spotlight");
    loadSpotlightView();
  } else {
    showView("view-feed");
    loadFeed();
  }
}

function navigateTo(route) {
  window.location.hash = route;
}

function hideAllViews() {
  const views = ["view-landing", "view-feed", "view-single-item", "view-groups", "view-group-detail", "view-profile", "view-outbox", "view-code", "view-spotlight"];
  views.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.add("hidden");
  });
}

async function browseSourceFile(filename) {
  const viewerTitle = document.getElementById("code-viewer-title");
  const viewerPre = document.getElementById("code-viewer-pre");
  const viewerLines = document.getElementById("code-viewer-lines");
  if (viewerTitle) viewerTitle.textContent = `📄 ${filename}`;
  if (viewerPre) viewerPre.textContent = "Loading source code...";
  if (viewerLines) viewerLines.textContent = "";
  try {
    const data = await apiFetch(`/source?file=${encodeURIComponent(filename)}`);
    if (data && data.content) {
      viewerPre.textContent = data.content;
      const cnt = data.content.split("\n").length;
      if (viewerLines) viewerLines.textContent = `${cnt} lines | ${data.content.length} bytes`;
    } else {
      viewerPre.textContent = "// Error loading file content.";
    }
  } catch(e) {
    if (viewerPre) viewerPre.textContent = "// Could not fetch file from server.";
  }
}

function showView(viewId) {
  const el = document.getElementById(viewId);
  if (el) el.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openModal(modalId) {
  if (modalId === "modal-kudos" && !currentUser) {
    showToast("Please log in to give Kudos.");
    openModal("modal-login");
    return;
  }
  if (modalId === "modal-post" && !currentUser) {
    showToast("Please log in to share posts.");
    openModal("modal-login");
    return;
  }
  if (modalId === "modal-create-group" && !currentUser) {
    showToast("Please log in to create a group.");
    openModal("modal-login");
    return;
  }
  if (modalId === "modal-support" && !currentUser) {
    showToast("Please log in to contact customer service.");
    openModal("modal-login");
    return;
  }

  const dlg = document.getElementById(modalId);
  if (dlg) {
    if (modalId === "modal-kudos") populateKudosModal();
    if (modalId === "modal-post") populatePostModal();
    if (modalId === "modal-edit-profile") populateEditProfileModal();
    dlg.showModal();
  }
}

function closeModal(modalId) {
  const dlg = document.getElementById(modalId);
  if (dlg) dlg.close();
}

function switchModal(fromId, toId) {
  closeModal(fromId);
  openModal(toId);
}

function showToast(msg) {
  const toast = document.getElementById("toast-popup");
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.remove("hidden");
  setTimeout(() => {
    toast.classList.add("hidden");
  }, 3500);
}

/* ================= AUTHENTICATION & SESSION ================= */

async function apiFetch(endpoint, options = {}) {
  const headers = options.headers || {};
  if (currentToken) {
    headers["Authorization"] = `Bearer ${currentToken}`;
  }
  if (!headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  options.headers = headers;

  const res = await fetch(API_BASE + endpoint, options);
  let data = {};
  try {
    data = await res.json();
  } catch (err) {}

  if (!res.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

async function checkSession() {
  if (!currentToken) {
    updateAuthUI(null);
    return;
  }
  try {
    const data = await apiFetch("/auth/me");
    currentUser = data.user;
    updateAuthUI(currentUser);
  } catch (err) {
    currentToken = null;
    localStorage.removeItem("gd_token");
    currentUser = null;
    updateAuthUI(null);
  }
}

function updateAuthUI(user) {
  const guestBox = document.getElementById("nav-auth-guest");
  const userBox = document.getElementById("nav-auth-user");
  if (!guestBox || !userBox) return;

  if (user) {
    guestBox.classList.add("hidden");
    userBox.classList.remove("hidden");
    document.getElementById("nav-user-name").textContent = user.username;
    document.getElementById("nav-user-avatar").src = user.avatar_url;
  } else {
    guestBox.classList.remove("hidden");
    userBox.classList.add("hidden");
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-pw").value;

  try {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    currentToken = data.token;
    localStorage.setItem("gd_token", currentToken);
    currentUser = data.user;
    updateAuthUI(currentUser);
    closeModal("modal-login");
    showToast(`☀️ Welcome back, ${currentUser.username}!`);
    await loadQuickNavGroups();
    navigateTo("/feed");
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

function presetLogin(email) {
  document.getElementById("login-email").value = email;
  document.getElementById("login-pw").value = "password123";
}

function selectAvatar(url) {
  document.getElementById("sup-avatar").value = url;
}

async function handleSignup(e) {
  e.preventDefault();
  const email = document.getElementById("sup-email").value.trim();
  const username = document.getElementById("sup-username").value.trim();
  const password = document.getElementById("sup-pw").value;
  const phone = document.getElementById("sup-phone").value.trim();
  const avatar_url = document.getElementById("sup-avatar").value.trim();
  const bio = document.getElementById("sup-bio").value.trim();

  try {
    const data = await apiFetch("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, username, password, phone, avatar_url, bio })
    });
    currentToken = data.token;
    localStorage.setItem("gd_token", currentToken);
    currentUser = data.user;
    updateAuthUI(currentUser);
    closeModal("modal-signup");
    showToast(`☀️ Welcome to gooddeeds.space, ${currentUser.username}!`);
    await loadQuickNavGroups();
    navigateTo("/feed");
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function logout() {
  try {
    await apiFetch("/auth/logout", { method: "POST" });
  } catch (err) {}
  currentToken = null;
  localStorage.removeItem("gd_token");
  currentUser = null;
  updateAuthUI(null);
  showToast("You have logged out safely.");
  await loadQuickNavGroups();
  navigateTo("/");
}

/* ================= QUICK NAVIGATION (JOINED GROUPS Req #23) ================= */

async function loadQuickNavGroups() {
  const container = document.getElementById("quick-groups-list");
  if (!container) return;
  if (!currentUser) {
    container.innerHTML = `<p class="px-4 py-3 text-stone-500 text-sm font-medium">Log in to see your joined groups</p>`;
    return;
  }

  try {
    const data = await apiFetch("/groups/joined");
    const groups = data.groups || [];
    if (groups.length === 0) {
      container.innerHTML = `<p class="px-4 py-3 text-stone-500 text-sm font-medium">You haven't joined any groups yet. Explore above!</p>`;
    } else {
      container.innerHTML = groups.map(g => `
        <a href="/#/group/${g.id}" class="flex items-center space-x-3 px-4 py-3 hover:bg-teal-50 transition touch-target border-b border-stone-100 last:border-0">
          <img src="${g.icon_url}" class="w-8 h-8 rounded-xl object-cover shrink-0">
          <span class="font-black text-stone-800 text-base truncate">${g.name}</span>
        </a>
      `).join("");
    }
  } catch (err) {}
}

/* ================= FEED CARDS RENDERER ================= */

function renderFeedCard(item, isProfileView = false) {
  const isKudos = item.item_type === "KUDOS";
  const cardClass = isKudos ? "kudos-card border-l-8 border-amber-500" : "post-card border-l-8 border-teal-600";
  const itemLink = isKudos ? `/#/kudos/${item.id}` : `/#/post/${item.id}`;
  
  // Groups badges
  const groupBadges = (item.groups || []).map(g => `
    <a href="/#/group/${g.id}" class="inline-flex items-center px-3 py-1 rounded-full text-xs font-black bg-stone-200 hover:bg-stone-300 text-stone-800 transition">
      👥 ${g.name}
    </a>
  `).join(" ");

  // Reactions bar
  const emojis = ["❤️", "👏", "🌟", "🤗", "🎉"];
  const reactionsHtml = emojis.map(em => {
    const cnt = (item.reactions || {})[em] || 0;
    const isActive = (item.user_reactions || []).includes(em);
    const btnStyle = isActive ? "bg-amber-500 text-white font-black shadow" : "bg-stone-100 hover:bg-stone-200 text-stone-700 font-bold";
    return `
      <button type="button" onclick="toggleReaction(${item.id}, '${em}')" class="px-3.5 py-2 rounded-xl text-base transition inline-flex items-center space-x-1.5 touch-target ${btnStyle}" title="React with ${em}">
        <span>${em}</span>
        ${cnt > 0 ? `<span class="text-sm">${cnt}</span>` : ""}
      </button>
    `;
  }).join("");

  // Comments HTML
  const commentsHtml = (item.comments || []).map(c => `
    <div class="bg-stone-50 p-4 rounded-2xl border border-stone-200 flex items-start space-x-3 text-base">
      <img src="${c.author_avatar}" alt="${c.author_name}" class="w-9 h-9 rounded-full object-cover border border-stone-300 shrink-0">
      <div class="flex-1 overflow-hidden">
        <div class="flex justify-between items-baseline">
          <a href="/#/user/${c.author_name}" class="font-black text-stone-900 hover:underline truncate">${c.author_name}</a>
          <span class="text-xs text-stone-400 font-bold shrink-0 pl-2">${c.created_at}</span>
        </div>
        <p class="text-stone-800 pt-0.5 font-medium whitespace-pre-line">${c.content}</p>
      </div>
    </div>
  `).join("");

  const isExpanded = expandedThreads.has(item.id);
  const commentsBoxClass = isExpanded 
    ? "space-y-3.5 pt-2.5 border-t border-stone-200/40" 
    : "space-y-3.5 hidden pt-2.5 border-t border-stone-200/40";
  const toggleIconText = isExpanded 
    ? (item.comments.length > 0 ? "▲ Hide Thread" : "▲ Hide Reply")
    : (item.comments.length > 0 ? "▼ Show Thread" : "▼ Write Reply");

  return `
    <article class="bg-white rounded-3xl border border-slate-200/80 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 p-6 sm:p-8 space-y-6 ${cardClass}">
      
      <!-- Author & Recipient Banner -->
      <div class="flex flex-wrap justify-between items-center gap-4">
        <div class="flex items-center space-x-3.5">
          <a href="/#/user/${item.author_id}">
            <img src="${item.author_avatar}" alt="${item.author_name}" class="w-12 h-12 rounded-full object-cover border border-slate-200 shadow-sm">
          </a>
          <div>
            <div class="text-lg font-bold text-slate-900 flex items-center flex-wrap gap-1.5">
              <a href="/#/user/${item.author_id}" class="hover:text-indigo-600 transition">${item.author_name}</a>
              ${["Maya_Lin", "Marcus_Vance", "Elena_Wellness", "Arthur_Pendleton"].includes(item.author_name) ? `<a href="/#/spotlight" class="inline-flex items-center space-x-1 px-2.5 py-0.5 bg-gradient-to-r from-amber-500 to-yellow-500 text-white font-black text-[10px] rounded-full uppercase tracking-wider shadow-sm hover:opacity-90 transition" title="June 2026 Hall of Fame Winner"><span>👑</span><span>Monthly Winner</span></a>` : ""}
              ${isKudos ? `
                <span class="text-amber-600 font-semibold text-base">celebrated</span>
                <a href="/#/user/${item.recipient_id}" class="hover:underline font-extrabold text-amber-900 bg-amber-50 border border-amber-200 px-3 py-0.5 rounded-full text-sm">${item.recipient_name}</a>
              ` : `
                <span class="px-2.5 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-full text-xs font-bold">🏷️ ${item.theme}</span>
              `}
            </div>
            <div class="text-xs text-slate-400 font-medium pt-0.5">
              <span>⏱️ ${item.created_at}</span>
              <span class="px-2">•</span>
              <a href="${itemLink}" class="text-slate-400 hover:text-indigo-600 transition">Direct Share Link ↗</a>
            </div>
          </div>
        </div>
        <div>${groupBadges}</div>
      </div>

      <!-- Main Body Content -->
      <div class="space-y-3">
        ${!isKudos && item.title ? `<h2 class="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight"><a href="${itemLink}" class="hover:text-indigo-600 transition">${item.title}</a></h2>` : ""}
        <p class="text-slate-700 text-lg whitespace-pre-line font-medium leading-relaxed">${item.content}</p>
        
        ${(() => {
          if (!item.resource_url) return "";
          let urls = [];
          try {
            if (item.resource_url.startsWith("[")) urls = JSON.parse(item.resource_url);
            else urls = item.resource_url.split("\n").filter(Boolean);
          } catch(e) { urls = [item.resource_url]; }
          return `<div class="pt-3 flex flex-wrap gap-2">` + urls.map((u, idx) => `
            <a href="${u}" target="_blank" rel="noopener" class="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-950 font-bold text-sm border border-indigo-200 transition touch-target shadow-sm">
              <span>📎 Attached Link or File ${urls.length > 1 ? '#' + (idx+1) : ''} ↗</span>
            </a>
          `).join("") + `</div>`;
        })()}
      </div>

      <!-- Emoji Reactions Bar (Req #4) -->
      <div class="flex flex-wrap items-center gap-2 pt-2 border-t border-stone-100">
        <span class="text-xs font-black text-stone-400 uppercase tracking-wider pr-1">Celebrate:</span>
        ${reactionsHtml}
      </div>

      <!-- Comments Stream & Authoring Input (Req #4) -->
      <div class="bg-stone-100/70 !mt-2 py-1 px-3 sm:py-1.5 sm:px-4 rounded-xl border border-stone-200 space-y-3">
        <button type="button" onclick="toggleCommentsStream(${item.id})" class="w-full flex justify-between items-center text-sm font-black text-stone-500 uppercase tracking-wider hover:text-stone-850 transition touch-target">
          <span class="flex items-center space-x-1.5">
            <span>💬 Community Discussion</span>
            <span class="bg-stone-200 text-stone-700 px-2 py-0.5 rounded-full text-xs font-extrabold">${item.comments.length}</span>
          </span>
          <span id="comments-toggle-icon-${item.id}" class="text-xs text-amber-700 hover:underline">
            ${toggleIconText}
          </span>
        </button>

        <div id="comments-stream-box-${item.id}" class="${commentsBoxClass}">
          ${item.comments.length > 0 ? `
            <div class="space-y-2.5">${commentsHtml}</div>
          ` : `
            <p class="text-sm text-slate-400 font-bold italic py-1 text-left">No comments yet. Be the first to share an uplifting note! ☀️</p>
          `}

          <form onsubmit="handleCommentSubmit(event, ${item.id})" class="flex gap-2 pt-2 border-t border-stone-200/50">
            <input type="text" placeholder="Add an uplifting comment or word of encouragement..." required class="flex-1 px-4 py-3 rounded-xl border-2 border-stone-300 font-semibold text-base focus:bg-white focus:border-amber-600 transition">
            <button type="submit" class="px-6 py-3 bg-stone-800 hover:bg-black text-white font-black text-base rounded-xl shadow transition touch-target shrink-0">Reply</button>
          </form>
        </div>
      </div>

    </article>
  `;
}

/* ================= FEED CARDS LOADING & FILTERING ================= */

async function loadLandingPreview() {
  await sessionPromise;
  const container = document.getElementById("landing-preview-feed");
  if (!container) return;
  try {
    const data = await apiFetch("/feed");
    const items = (data.feed || []).slice(0, 2);
    container.innerHTML = items.map(it => renderFeedCard(it, false)).join("");
  } catch (err) {}
}

async function loadFeed() {
  await sessionPromise;
  checkPendingInvitations();
  const container = document.getElementById("feed-items-container");
  if (!container) return;
  container.innerHTML = `<p class="text-center font-bold text-xl text-stone-500 py-12">Loading feed...</p>`;

  let url = `/feed?sort=${currentSortMode}&`;
  if (currentTheme) url += `theme=${encodeURIComponent(currentTheme)}&`;
  if (currentGroupFilter) url += `group_id=${encodeURIComponent(currentGroupFilter)}&`;
  if (currentSearch) url += `search=${encodeURIComponent(currentSearch)}&`;
  if (currentTypeFilter) url += `filter_type=${encodeURIComponent(currentTypeFilter)}&`;
  if (currentMyKudosMode === "received" && currentUser) url += `recipient_id=${currentUser.id}&filter_type=KUDOS&`;
  if (currentMyKudosMode === "given" && currentUser) url += `author_id=${currentUser.id}&filter_type=KUDOS&`;
  if (currentMyPostsMode === "authored" && currentUser) url += `author_id=${currentUser.id}&filter_type=POST&`;

  try {
    const data = await apiFetch(url);
    const feed = data.feed || [];
    if (feed.length === 0) {
      container.innerHTML = `
        <div class="bg-white p-12 rounded-3xl border border-slate-200 text-center space-y-3">
          <div class="text-5xl">🕊️</div>
          <h3 class="text-2xl font-bold text-slate-800">No Stories Found</h3>
          <p class="text-base text-slate-500 font-medium">No posts or kudos match your active filter selection.</p>
          <button onclick="clearAllFilters()" class="px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-xl shadow-sm transition">Reset All Filters</button>
        </div>
      `;
    } else {
      container.innerHTML = feed.map(item => renderFeedCard(item, false)).join("");
    }
  } catch (err) {
    container.innerHTML = `<p class="text-center font-bold text-red-600 py-12">Failed to load feed: ${err.message}</p>`;
  }
}

function filterByTheme(th) {
  currentTheme = th;
  document.querySelectorAll(".theme-pill").forEach(el => {
    if (th !== "" && el.textContent.includes(th)) {
      el.className = "theme-pill px-3.5 py-1.5 rounded-xl font-bold text-sm bg-amber-500 text-white shadow-sm transition touch-target";
    } else if (th === "" && el.textContent.includes("All Topics")) {
      el.className = "theme-pill px-3.5 py-1.5 rounded-xl font-bold text-sm bg-slate-900 text-white transition touch-target shadow-sm";
    } else {
      el.className = "theme-pill px-3.5 py-1.5 rounded-xl font-bold text-sm bg-slate-100 hover:bg-slate-200 text-slate-700 transition touch-target";
    }
  });
  loadFeed();
}

function filterByGroup(gid) {
  currentGroupFilter = gid;
  loadFeed();
}

function filterByType(type) {
  currentTypeFilter = type;
  currentMyKudosMode = "";
  currentMyPostsMode = "";
  loadFeed();
}

function filterFeedByMyKudos(mode) {
  if (!currentUser) {
    showToast("Please log in to view your Kudos history.");
    openModal("modal-login");
    return;
  }
  currentMyPostsMode = "";
  if (mode === "all") {
    currentMyKudosMode = "";
    currentTypeFilter = "";
    showToast("🔄 Showing all community feed items.");
  } else {
    currentMyKudosMode = mode;
    currentTypeFilter = "KUDOS";
    const typeSel = document.getElementById("feed-type-select");
    if (typeSel) typeSel.value = "KUDOS";
    showToast(mode === "received" ? "📥 Filtering by Kudos you've received!" : "📤 Filtering by Kudos you've given!");
  }
  if (window.location.hash !== "#/feed" && window.location.hash !== "#/" && window.location.hash !== "") {
    navigateTo("/feed");
  } else {
    loadFeed();
  }
}

function filterFeedByMyPosts(mode) {
  if (!currentUser) {
    showToast("Please log in to view your Posts history.");
    openModal("modal-login");
    return;
  }
  currentMyKudosMode = "";
  if (mode === "all") {
    currentMyPostsMode = "";
    currentTypeFilter = "";
    showToast("🔄 Showing all community feed items.");
  } else {
    currentMyPostsMode = "authored";
    currentTypeFilter = "POST";
    const typeSel = document.getElementById("feed-type-select");
    if (typeSel) typeSel.value = "POST";
    showToast("📂 Filtering by Posts you've authored!");
  }
  if (window.location.hash !== "#/feed" && window.location.hash !== "#/" && window.location.hash !== "") {
    navigateTo("/feed");
  } else {
    loadFeed();
  }
}

function changeSortMode(mode) {
  currentSortMode = mode;
  loadFeed();
}

function clearAllFilters() {
  currentTheme = "";
  currentGroupFilter = "";
  currentSearch = "";
  currentTypeFilter = "";
  currentMyKudosMode = "";
  currentMyPostsMode = "";
  const sInput = document.getElementById("feed-search-input");
  if (sInput) sInput.value = "";
  const gSel = document.getElementById("feed-group-select");
  if (gSel) gSel.value = "";
  const tSel = document.getElementById("feed-type-select");
  if (tSel) tSel.value = "";
  filterByTheme("");
}

async function populateGroupFilterDropdown() {
  const sel = document.getElementById("feed-group-select");
  if (!sel) return;
  try {
    const data = await apiFetch("/groups");
    sel.innerHTML = `<option value="">All Groups</option>` + 
      (data.groups || []).map(g => `<option value="${g.id}">👥 ${g.name}</option>`).join("");
  } catch (err) {}
}

/* ================= SINGLE ITEM VIEW (DIRECT URL) ================= */

async function loadSingleItemView(id) {
  await sessionPromise;
  const container = document.getElementById("single-item-container");
  if (!container) return;
  container.innerHTML = `<p class="text-center font-bold text-xl text-stone-500 py-12">Loading celebration...</p>`;
  try {
    const data = await apiFetch(`/feed/${id}`);
    container.innerHTML = renderFeedCard(data.item, false);
  } catch (err) {
    container.innerHTML = `
      <div class="bg-white p-12 rounded-3xl border-2 border-red-200 text-center space-y-4">
        <div class="text-6xl">❌</div>
        <h2 class="text-3xl font-black text-stone-800">Kudos or Story Not Found</h2>
        <p class="text-lg text-stone-600">The requested direct link may be invalid or expired.</p>
        <button onclick="navigateTo('/feed')" class="px-6 py-3 bg-amber-600 text-white font-bold rounded-xl">Return to Feed</button>
      </div>
    `;
  }
}

/* ================= CONTENT CREATION WIZARDS ================= */

async function populateKudosModal() {
  const recipSelect = document.getElementById("kudos-recipient");
  if (!recipSelect) return;
  try {
    const data = await apiFetch("/users");
    const otherUsers = (data.users || []).filter(u => currentUser && u.id !== currentUser.id);
    recipSelect.innerHTML = `<option value="">-- Choose Member --</option>` + 
      otherUsers.map(u => `<option value="${u.id}">${u.username}</option>`).join("");
    populateGroupCheckboxes("kudos-groups-list", "kudos-group");
  } catch (err) {}
}

async function populatePostModal() {
  populateGroupCheckboxes("post-groups-list", "post-group");
}

async function populateGroupCheckboxes(containerId, inputName) {
  const container = document.getElementById(containerId);
  if (!container) return;
  try {
    const data = await apiFetch("/groups");
    container.innerHTML = (data.groups || []).map(g => `
      <label class="inline-flex items-center space-x-2 px-3 py-2 rounded-xl bg-white border-2 border-stone-200 font-bold text-sm cursor-pointer hover:bg-amber-50 hover:border-amber-400 transition touch-target">
        <input type="checkbox" name="${inputName}" value="${g.id}" class="w-5 h-5 text-amber-600 rounded">
        <span>${g.name}</span>
      </label>
    `).join("");
  } catch (err) {}
}

async function handleGiveKudos(e) {
  e.preventDefault();
  const recipient_id = parseInt(document.getElementById("kudos-recipient").value);
  const content = document.getElementById("kudos-content").value.trim();
  const group_ids = Array.from(document.querySelectorAll("#kudos-groups-list input:checked")).map(el => parseInt(el.value));

  try {
    const data = await apiFetch("/kudos", {
      method: "POST",
      body: JSON.stringify({ recipient_id, content, group_ids })
    });
    closeModal("modal-kudos");
    document.getElementById("kudos-content").value = "";
    showToast("🌟 Public Kudos sent & email alert triggered!");
    if (window.location.hash.includes("/feed") || window.location.hash === "#/") loadFeed();
    else navigateTo("/feed");
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function reviewPostStep(e) {
  if (e) e.preventDefault();
  const title = document.getElementById("post-input-title").value.trim();
  const theme = document.getElementById("post-input-theme").value;
  const content = document.getElementById("post-input-content").value.trim();
  const linkInputs = document.querySelectorAll(".post-link-input");
  const fileInput = document.getElementById("post-file-input");
  const group_ids = Array.from(document.querySelectorAll("#post-groups-list input:checked")).map(el => parseInt(el.value));

  if (!title || !content) {
    showToast("Please provide both a title and description/story content.");
    return;
  }

  const attachments = [];
  linkInputs.forEach(inp => {
    const u = inp.value.trim();
    if (u) attachments.push(u);
  });

  const files = fileInput && fileInput.files ? Array.from(fileInput.files) : [];
  for (const file of files) {
    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject("");
        reader.readAsDataURL(file);
      });
      if (dataUrl) attachments.push(dataUrl);
    } catch(err) {}
  }

  const resource_url = attachments.length > 0 ? JSON.stringify(attachments) : "";

  draftPost = { title, theme, content, resource_url, group_ids };

  document.getElementById("post-step-1").classList.add("hidden");
  document.getElementById("post-step-2").classList.remove("hidden");

  const previewBox = document.getElementById("post-preview-card");
  previewBox.innerHTML = `
    <div class="font-extrabold text-2xl text-slate-900 tracking-tight">${title}</div>
    <div class="flex gap-2 pt-1"><span class="px-3 py-1 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full text-xs font-bold">🏷️ ${theme}</span></div>
    <p class="text-base text-slate-700 pt-3 whitespace-pre-line font-medium leading-relaxed">${content}</p>
    ${attachments.length > 0 ? `<div class="pt-3 font-bold text-indigo-600 text-sm">📎 ${attachments.length} Link(s) / File(s) Attached</div>` : ""}
  `;
}

function addPostLinkField() {
  const container = document.getElementById("post-links-list");
  if (!container) return;
  const div = document.createElement("div");
  div.className = "flex gap-2 animate-fadeIn";
  div.innerHTML = `
    <input type="url" placeholder="https://example.com/another-resource" class="post-link-input flex-1 px-4 py-3 rounded-xl border border-slate-300 font-medium text-sm bg-slate-50 focus:bg-white focus:border-indigo-600 transition">
    <button type="button" onclick="this.closest('.flex').remove()" class="px-3 py-2 text-slate-400 hover:text-red-500 font-bold text-lg rounded-lg border border-slate-200 bg-white" title="Remove link">×</button>
  `;
  container.appendChild(div);
}

function handlePostFilesSelect(e) {
  const preview = document.getElementById("post-files-preview");
  if (!preview) return;
  const files = e.target.files ? Array.from(e.target.files) : [];
  if (files.length === 0) {
    preview.innerHTML = "";
    return;
  }
  preview.innerHTML = files.map(f => `
    <div class="flex items-center justify-between px-4 py-2.5 bg-indigo-50/60 rounded-xl border border-indigo-100 text-xs font-bold text-indigo-950">
      <span class="truncate max-w-[280px] sm:max-w-[400px]">📄 ${f.name} (${Math.round(f.size/1024)} KB)</span>
      <span class="text-emerald-600 font-extrabold uppercase">Ready</span>
    </div>
  `).join("");
}

function backToPostStep1() {
  document.getElementById("post-step-1").classList.remove("hidden");
  document.getElementById("post-step-2").classList.add("hidden");
}

async function confirmPublishPost() {
  if (!draftPost) return;
  try {
    await apiFetch("/posts", {
      method: "POST",
      body: JSON.stringify(draftPost)
    });
    closeModal("modal-post");
    draftPost = null;
    document.getElementById("post-input-title").value = "";
    document.getElementById("post-input-content").value = "";
    document.getElementById("post-input-url").value = "";
    backToPostStep1();
    showToast("✅ Story published permanently to community feed!");
    navigateTo("/feed");
    loadFeed();
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

/* ================= REACTIONS & COMMENTS ACTIONS ================= */

async function toggleReaction(itemId, emoji) {
  if (!currentUser) {
    showToast("Please log in to react with emojis.");
    openModal("modal-login");
    return;
  }
  try {
    await apiFetch("/reactions", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId, emoji })
    });
    if (window.location.hash.includes("/kudos/") || window.location.hash.includes("/post/")) {
      const id = window.location.hash.split("/")[2];
      loadSingleItemView(id);
    } else if (window.location.hash.includes("/profile") || window.location.hash.includes("/user/")) {
      renderProfileTabContent();
    } else {
      loadFeed();
    }
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function handleCommentSubmit(e, itemId) {
  e.preventDefault();
  if (!currentUser) {
    showToast("Please log in to leave comments.");
    openModal("modal-login");
    return;
  }
  const input = e.target.querySelector("input");
  const content = input.value.trim();
  if (!content) return;

  try {
    await apiFetch("/comments", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId, content })
    });
    input.value = "";
    showToast("💬 Discussion reply added!");
    if (window.location.hash.includes("/kudos/") || window.location.hash.includes("/post/")) {
      const id = window.location.hash.split("/")[2];
      loadSingleItemView(id);
    } else if (window.location.hash.includes("/profile") || window.location.hash.includes("/user/")) {
      const uId = activeProfileData ? activeProfileData.user.id : currentUser.id;
      await loadUserProfile(uId);
    } else {
      loadFeed();
    }
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

/* ================= GROUPS DIRECTORY ================= */

async function loadGroups(searchQuery = "") {
  const container = document.getElementById("groups-grid");
  if (!container) return;
  container.innerHTML = `<p class="text-stone-500 font-bold text-xl col-span-3 text-center py-12">Loading centers...</p>`;

  const themeFilter = document.getElementById("group-theme-filter") ? document.getElementById("group-theme-filter").value : "";

  let url = "/groups?";
  if (searchQuery) url += `search=${encodeURIComponent(searchQuery)}&`;
  if (themeFilter) url += `theme=${encodeURIComponent(themeFilter)}`;

  try {
    const data = await apiFetch(url);
    const groups = data.groups || [];

    if (groups.length === 0) {
      container.innerHTML = `<p class="text-stone-500 font-bold text-xl col-span-3 text-center py-12">No community groups match your filters.</p>`;
      return;
    }

    container.innerHTML = groups.map(g => `
      <div class="bg-white p-8 rounded-3xl border-2 border-stone-200 shadow-sm flex flex-col justify-between hover:border-teal-600 transition space-y-6">
        <div class="space-y-4">
          <div class="flex items-center space-x-4">
            <img src="${g.icon_url}" alt="${g.name}" class="w-16 h-16 rounded-2xl object-cover border-2 border-teal-700 shadow">
            <div>
              <h3 class="text-2xl font-black text-stone-900 leading-tight">${g.name}</h3>
              <span class="text-xs font-bold text-stone-400">👥 ${g.member_count} active members</span>
            </div>
          </div>
          <p class="text-stone-700 font-medium text-base leading-relaxed">${g.description}</p>
          <div class="flex flex-wrap gap-1.5 pt-1">
            ${(g.themes || []).map(t => `<span class="px-3 py-1 bg-stone-100 text-stone-700 font-black text-xs rounded-full">${t}</span>`).join("")}
          </div>
        </div>

        <div class="pt-2 flex items-center justify-between gap-3">
          <a href="/#/group/${g.id}" class="flex-1 py-3.5 bg-teal-800 hover:bg-teal-900 text-white font-black text-center rounded-xl shadow transition touch-target block">
            Enter Hub ↗
          </a>
          ${g.is_joined ? `
            <span class="px-4 py-3.5 bg-teal-50 text-teal-800 font-black text-xs rounded-xl border border-teal-200 flex items-center">Joined ✅</span>
          ` : ""}
        </div>
      </div>
    `).join("");
  } catch (err) {}
}

function filterGroupsTheme(theme) {
  const sInput = document.getElementById("group-search-input");
  loadGroups(sInput ? sInput.value.trim() : "");
}

/* ================= GROUP DETAIL PAGE ================= */

async function loadGroupDetail(gid) {
  const headerContainer = document.getElementById("group-detail-header");
  if (!headerContainer) return;
  try {
    const data = await apiFetch(`/groups/${gid}`);
    activeGroupData = data.group;

    const isMember = activeGroupData.is_joined;
    const isGroupAdmin = activeGroupData.is_admin;
    const isSiteAdmin = currentUser && currentUser.is_site_admin === 1;
    const isAdmin = isGroupAdmin || isSiteAdmin;

    const isInviteFlow = window.location.hash.includes("invite=yes") || window.location.hash.includes("invite=1");
    const inviteBannerHtml = (isInviteFlow && !isMember) ? `
      <div class="w-full bg-gradient-to-r from-emerald-600 via-teal-600 to-indigo-600 p-8 sm:p-10 rounded-3xl text-white shadow-2xl flex flex-col md:flex-row items-center justify-between gap-6 mb-8 text-left animate-fadeIn border-4 border-amber-300">
        <div class="space-y-2 max-w-2xl">
          <span class="px-4 py-1 bg-white/20 backdrop-blur font-black text-xs uppercase tracking-wider rounded-full border border-white/30 inline-block">💌 Special Community Invitation</span>
          <h2 class="text-2xl sm:text-3xl font-black tracking-tight leading-tight">Accept Your Invitation to Join "${activeGroupData.name}"</h2>
          <p class="text-emerald-100 font-medium text-sm sm:text-base leading-relaxed">You were specifically invited to become an active member of this space. Click below to accept your invitation and start participating!</p>
        </div>
        <div class="shrink-0 w-full md:w-auto text-center">
          ${!currentUser ? `
            <button onclick="openModal('modal-login')" class="w-full md:w-auto px-8 py-4 bg-amber-500 hover:bg-amber-600 text-slate-950 font-black text-lg rounded-2xl shadow-xl transition touch-target hover:scale-105">🔑 Log In to Accept Invitation</button>
          ` : `
            <button onclick="toggleGroupMembership(${gid}, 'join')" class="w-full md:w-auto px-8 py-4 bg-white hover:bg-amber-100 text-emerald-900 font-black text-lg rounded-2xl shadow-2xl transition touch-target hover:scale-105 flex items-center justify-center space-x-2"><span>✅</span><span>Accept Invitation & Become Member</span></button>
          `}
        </div>
      </div>
    ` : "";

    headerContainer.innerHTML = inviteBannerHtml + `
      <div class="flex items-center space-x-6">
        <img src="${activeGroupData.icon_url}" alt="${activeGroupData.name}" class="w-24 h-24 rounded-3xl object-cover border-4 border-teal-700 shadow-md">
        <div class="space-y-2">
          <div class="flex items-center space-x-3">
            <h1 class="text-3xl sm:text-4xl font-black text-stone-900">${activeGroupData.name}</h1>
            ${isGroupAdmin ? `<span class="px-3 py-1 bg-amber-500 text-white font-black text-xs rounded-full">Group Admin</span>` : isSiteAdmin ? `<span class="px-3 py-1 bg-indigo-600 text-white font-black text-xs rounded-full">Site Admin</span>` : ""}
          </div>
          <p class="text-stone-700 font-medium text-lg max-w-2xl">${activeGroupData.description}</p>
          <div class="flex flex-wrap gap-2 pt-1">
            ${(activeGroupData.themes || []).map(t => `<span class="px-3 py-1 bg-stone-200 text-stone-800 font-bold text-xs rounded-full">${t}</span>`).join("")}
          </div>
        </div>
      </div>

      <div class="pt-4 md:pt-0 shrink-0 flex flex-col sm:flex-row gap-3 items-center">
        ${!currentUser ? `
          <button onclick="openModal('modal-login')" class="px-8 py-4 bg-amber-600 hover:bg-amber-700 text-white font-black text-lg rounded-2xl shadow transition touch-target">Log In to Join</button>
        ` : isMember ? `
          <button onclick="openGroupInviteModal()" class="px-6 py-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-base rounded-2xl shadow transition touch-target flex items-center space-x-2"><span>💌</span><span>Invite Others to Join</span></button>
          <button onclick="toggleGroupMembership(${gid}, 'leave')" class="px-6 py-4 bg-stone-200 hover:bg-red-100 hover:text-red-700 text-stone-700 font-black text-base rounded-2xl transition touch-target">Leave Group</button>
        ` : `
          <button onclick="toggleGroupMembership(${gid}, 'join')" class="px-8 py-4 bg-teal-800 hover:bg-teal-900 text-white font-black text-xl rounded-2xl shadow-lg transition touch-target">+ Join Group Free</button>
        `}
      </div>
    `;

    // Admin resource curation box visibility
    const curateBox = document.getElementById("admin-curate-box");
    if (curateBox) {
      if (isAdmin) curateBox.classList.remove("hidden");
      else curateBox.classList.add("hidden");
    }

    switchGroupTab("chat");
  } catch (err) {
    showToast("Group not found");
    navigateTo("/groups");
  }
}

async function toggleGroupMembership(gid, action) {
  try {
    await apiFetch(`/groups/${gid}/${action}`, { method: "POST" });
    showToast(action === "join" ? "🎉 You joined this group!" : "You left this group.");
    await loadQuickNavGroups();
    await loadGroupDetail(gid);
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

function switchGroupTab(tabName) {
  ["chat", "resources", "roster"].forEach(t => {
    const btn = document.getElementById(`gtab-${t}`);
    const box = document.getElementById(`gcontent-${t}`);
    if (!btn || !box) return;
    if (t === tabName) {
      btn.className = "gtab-btn px-8 py-4 font-black text-xl border-b-4 border-amber-600 text-amber-800 transition touch-target shrink-0";
      box.classList.remove("hidden");
    } else {
      btn.className = "gtab-btn px-8 py-4 font-black text-xl border-b-4 border-transparent text-stone-500 hover:text-stone-800 transition touch-target shrink-0";
      box.classList.add("hidden");
    }
  });

  if (tabName === "chat") renderGroupChatList();
  if (tabName === "resources") renderGroupResources();
  if (tabName === "roster") renderGroupRoster();
}

function renderGroupChatList() {
  const container = document.getElementById("group-chat-list");
  if (!container || !activeGroupData) return;
  const msgs = activeGroupData.chat_messages || [];
  if (msgs.length === 0) {
    container.innerHTML = `<p class="text-slate-400 font-bold text-center py-8 text-base">No instant messages yet. Be the first to say hello above! ☀️</p>`;
    return;
  }
  container.innerHTML = msgs.map(m => `
    <div class="bg-white p-5 sm:p-6 rounded-2xl border border-slate-200/80 shadow-sm flex items-start space-x-3.5">
      <img src="${m.author_avatar}" alt="${m.author_name}" class="w-10 h-10 rounded-full object-cover border border-slate-200 shrink-0">
      <div class="flex-1 min-w-0">
        <div class="flex justify-between items-baseline mb-1">
          <strong class="text-sm font-bold text-slate-900 truncate pr-2">${m.author_name}</strong>
          <span class="text-xs text-slate-400 font-medium shrink-0">${m.created_at}</span>
        </div>
        <p class="text-base text-slate-800 font-normal whitespace-pre-line leading-relaxed break-words">${m.message}</p>
      </div>
    </div>
  `).join("");
}

async function sendGroupChat() {
  if (!currentUser) {
    showToast("Please log in to chat on this board.");
    openModal("modal-login");
    return;
  }
  const input = document.getElementById("group-chat-input");
  const message = input.value.trim();
  if (!message) return;

  try {
    const data = await apiFetch(`/groups/${activeGroupId}/chat`, {
      method: "POST",
      body: JSON.stringify({ message })
    });
    input.value = "";
    activeGroupData.chat_messages.push(data.message);
    renderGroupChatList();
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

function renderGroupResources() {
  const container = document.getElementById("group-resources-list");
  if (!container || !activeGroupData) return;
  const res = activeGroupData.resources || [];
  if (res.length === 0) {
    container.innerHTML = `<p class="text-stone-400 font-bold col-span-2 text-center py-8 text-lg">No curated resource files added to this group library yet.</p>`;
    return;
  }
  container.innerHTML = res.map(r => `
    <div class="bg-white p-7 rounded-3xl border-2 border-stone-200 shadow-sm space-y-4 flex flex-col justify-between">
      <div class="space-y-2.5">
        <span class="px-3.5 py-1 bg-teal-50 text-teal-800 font-black text-xs rounded-full border border-teal-200">${r.theme}</span>
        <h4 class="text-2xl font-black text-stone-900">${r.description || r.title}</h4>
        <p class="text-xs font-bold text-stone-400">Curated by ${r.added_by_name || "Admin"}</p>
      </div>
      <a href="${r.url}" target="_blank" rel="noopener" class="w-full py-3.5 bg-stone-100 hover:bg-stone-200 text-stone-900 font-black text-center rounded-2xl border-2 border-stone-300 transition block touch-target">
        ${r.resource_type === "PDF" ? "📄 View PDF Guide Guide ↗" : "🌐 Open Web Link ↗"}
      </a>
    </div>
  `).join("");
}

async function submitBatchGroupResources(e) {
  if (e) e.preventDefault();
  if (!activeGroupId) return;

  const title = document.getElementById("curate-title").value.trim();
  const desc = document.getElementById("curate-desc").value.trim();
  const theme = document.getElementById("res-theme").value;
  const linkInputs = document.querySelectorAll(".curate-link-input");
  const fileInput = document.getElementById("curate-file-input");

  const resources = [];

  // 1. Process web links
  linkInputs.forEach((inp, idx) => {
    const u = inp.value.trim();
    if (u) {
      resources.push({
        title: linkInputs.length > 1 ? `${title} (Link ${idx+1})` : title,
        description: desc || title,
        url: u,
        resource_type: "URL",
        theme: theme
      });
    }
  });

  // 2. Process attached files via FileReader
  const files = fileInput && fileInput.files ? Array.from(fileInput.files) : [];
  for (const file of files) {
    try {
      const dataUrl = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject("");
        reader.readAsDataURL(file);
      });
      if (dataUrl) {
        resources.push({
          title: file.name,
          description: desc ? `${file.name} - ${desc}` : file.name,
          url: dataUrl,
          resource_type: file.name.toLowerCase().endsWith(".pdf") ? "PDF" : "FILE",
          theme: theme
        });
      }
    } catch(err) {
      console.error("Could not read file:", file.name);
    }
  }

  if (resources.length === 0) {
    showToast("Please add at least one web link or select a file to upload.");
    return;
  }

  try {
    const res = await apiFetch(`/groups/${activeGroupId}/resources`, {
      method: "POST",
      body: JSON.stringify({ resources: resources })
    });
    showToast(`✅ Successfully attached ${resources.length} resource(s) to group library!`);
    
    document.getElementById("curate-title").value = "";
    document.getElementById("curate-desc").value = "";
    linkInputs.forEach((inp, idx) => {
      if (idx === 0) inp.value = "";
      else inp.closest(".flex").remove();
    });
    if (fileInput) fileInput.value = "";
    const preview = document.getElementById("curate-files-preview");
    if (preview) preview.innerHTML = "";

    await loadGroupDetail(activeGroupId);
    switchGroupTab("resources");
  } catch (err) {
    showToast("❌ " + (err.message || "Upload failed."));
  }
}

function addCurateLinkField() {
  const container = document.getElementById("curate-links-list");
  if (!container) return;
  const div = document.createElement("div");
  div.className = "flex gap-2 animate-fadeIn";
  div.innerHTML = `
    <input type="url" placeholder="https://example.com/another-link" class="curate-link-input flex-1 px-4 py-3 rounded-xl border border-slate-300 font-medium text-sm bg-slate-50 focus:bg-white focus:border-indigo-600 transition">
    <button type="button" onclick="this.closest('.flex').remove()" class="px-3 py-2 text-slate-400 hover:text-red-500 font-bold text-lg rounded-lg border border-slate-200 bg-white" title="Remove link">×</button>
  `;
  container.appendChild(div);
}

function handleCurateFilesSelect(e) {
  const preview = document.getElementById("curate-files-preview");
  if (!preview) return;
  const files = e.target.files ? Array.from(e.target.files) : [];
  if (files.length === 0) {
    preview.innerHTML = "";
    return;
  }
  preview.innerHTML = files.map(f => `
    <div class="flex items-center justify-between px-4 py-2.5 bg-indigo-50/60 rounded-xl border border-indigo-100 text-xs font-bold text-indigo-950">
      <span class="truncate max-w-[280px] sm:max-w-[400px]">📄 ${f.name} (${Math.round(f.size/1024)} KB)</span>
      <span class="text-emerald-600 font-extrabold uppercase">Ready</span>
    </div>
  `).join("");
}

function renderGroupRoster() {
  const container = document.getElementById("group-roster-list");
  if (!container || !activeGroupData) return;
  const roster = activeGroupData.roster || [];
  const invites = activeGroupData.invitations || [];
  const canManageRoles = currentUser && (currentUser.is_site_admin === 1 || activeGroupData.is_admin);

  const membersHtml = roster.map(m => {
    let adminToggleBtn = "";
    if (canManageRoles) {
      if (m.is_admin) {
        adminToggleBtn = `<button onclick="event.preventDefault(); event.stopPropagation(); toggleMemberRole(${activeGroupData.id}, ${m.id}, 0)" class="mt-2 px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-800 font-bold text-xs rounded-xl transition">Demote from Admin</button>`;
      } else {
        adminToggleBtn = `<button onclick="event.preventDefault(); event.stopPropagation(); toggleMemberRole(${activeGroupData.id}, ${m.id}, 1)" class="mt-2 px-3 py-1.5 bg-amber-100 hover:bg-amber-200 text-amber-900 font-bold text-xs rounded-xl transition">Promote to Admin</button>`;
      }
    }

    return `
    <div class="bg-white p-6 rounded-2xl border-2 border-stone-200 shadow-sm flex items-center justify-between space-x-4 hover:border-amber-500 transition">
      <a href="/#/user/${m.id}" class="flex items-center space-x-4 truncate flex-1 min-w-0">
        <img src="${m.avatar_url}" alt="${m.username}" class="w-16 h-16 rounded-full object-cover border-2 ${m.is_admin ? "border-amber-500" : "border-stone-300"} shrink-0">
        <div class="truncate text-left flex-1">
          <div class="font-black text-xl text-stone-900 flex items-center space-x-2">
            <span>${m.username}</span>
            ${m.is_admin ? `<span class="text-xs bg-amber-100 text-amber-800 px-2.5 py-0.5 rounded-full font-black shrink-0">Admin</span>` : `<span class="text-xs bg-teal-100 text-teal-800 px-2.5 py-0.5 rounded-full font-black shrink-0">Member</span>`}
          </div>
          <p class="text-sm font-medium text-stone-500 truncate pt-1">${m.bio || "Community member"}</p>
        </div>
      </a>
      ${adminToggleBtn ? `<div class="shrink-0">${adminToggleBtn}</div>` : ""}
    </div>
    `;
  }).join("");

  let invitesHtml = "";
  if (invites.length > 0) {
    invitesHtml = `
      <div class="col-span-1 md:col-span-2 pt-8 border-t-4 border-slate-200 mt-6 text-left space-y-4 font-sans">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="text-xl font-black text-slate-900 flex items-center space-x-2"><span>💌</span><span>Sent Group Invitations Roster</span></h3>
            <p class="text-xs text-slate-500 font-medium">Track everyone invited to join this space and their real-time status.</p>
          </div>
          <span class="text-xs font-black bg-indigo-100 text-indigo-900 px-3.5 py-1 rounded-full border border-indigo-200">${invites.length} Tracked</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
          ${invites.map(inv => {
            let badgeClass = "bg-amber-100 text-amber-900 border-amber-300";
            let statusIcon = "⏱️";
            if (inv.status === "ACCEPTED") { badgeClass = "bg-emerald-100 text-emerald-900 border-emerald-300"; statusIcon = "✅"; }
            if (inv.status === "REJECTED") { badgeClass = "bg-red-100 text-red-900 border-red-300"; statusIcon = "✕"; }
            return `
              <div class="bg-slate-50 p-5 rounded-2xl border-2 border-slate-200 flex items-center justify-between gap-3 transition hover:bg-slate-100/80">
                <div class="truncate text-left min-w-0">
                  <div class="font-bold text-base text-slate-900 truncate flex items-center space-x-1.5"><span>Invited:</span> <strong class="text-indigo-700 font-black">${inv.recipient_username}</strong></div>
                  <div class="text-xs text-slate-500 font-medium truncate pt-0.5">Sent by <strong>${inv.sender_name}</strong> • ${inv.created_at || 'Just now'}</div>
                  ${inv.message ? `<div class="text-xs text-slate-400 italic truncate mt-0.5">"${inv.message}"</div>` : ''}
                </div>
                <span class="px-3 py-1.5 rounded-xl border text-xs font-black shrink-0 flex items-center space-x-1 shadow-sm ${badgeClass}">
                  <span>${statusIcon}</span><span>${inv.status}</span>
                </span>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }

  container.innerHTML = membersHtml + invitesHtml;
}

async function handleCreateGroup(e) {
  e.preventDefault();
  const name = document.getElementById("cgrp-name").value.trim();
  const icon_url = document.getElementById("cgrp-icon").value.trim();
  const description = document.getElementById("cgrp-desc").value.trim();
  const themes = Array.from(document.querySelectorAll("input[name='cgrp-theme']:checked")).map(el => el.value);

  try {
    const data = await apiFetch("/groups", {
      method: "POST",
      body: JSON.stringify({ name, icon_url, description, themes })
    });
    closeModal("modal-create-group");
    showToast("🎉 Group created successfully!");
    await loadQuickNavGroups();
    navigateTo(`/group/${data.id}`);
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

/* ================= USER PROFILE & SEGREGATED HISTORY (Req #20 Fix) ================= */

async function loadUserProfile(targetId) {
  try {
    const data = await apiFetch(`/users/${targetId}`);
    activeProfileData = data;
    const u = data.user;

    document.getElementById("prof-avatar").src = u.avatar_url;
    document.getElementById("prof-username").textContent = u.username;
    document.getElementById("prof-email").textContent = `Member since ${new Date(u.created_at).toLocaleDateString()}`;
    document.getElementById("prof-bio").textContent = u.bio ? `"${u.bio}"` : "No bio added yet.";

    const editBox = document.getElementById("prof-edit-btn-box");
    if (currentUser && currentUser.id === u.id) {
      editBox.classList.remove("hidden");
    } else {
      editBox.classList.add("hidden");
    }
  } catch (err) {
    showToast("❌ Failed to load profile: " + err.message);
    navigateTo("/feed");
  }
}

function switchProfileTab(tab) {
  currentProfileTab = tab;
  ["posts", "received", "given"].forEach(t => {
    const btn = document.getElementById(`ptab-${t}`);
    if (!btn) return;
    if (t === tab) {
      btn.className = "ptab-btn px-8 py-4 font-black text-xl border-b-4 border-teal-600 text-teal-800 transition touch-target shrink-0";
    } else {
      btn.className = "ptab-btn px-8 py-4 font-black text-xl border-b-4 border-transparent text-stone-500 hover:text-stone-800 transition touch-target shrink-0";
    }
  });

  renderProfileTabContent();
}

function renderProfileTabContent() {
  const container = document.getElementById("prof-tab-content");
  if (!container || !activeProfileData) return;

  let items = [];
  if (currentProfileTab === "posts") items = activeProfileData.authored_posts || [];
  if (currentProfileTab === "received") items = activeProfileData.received_kudos || [];
  if (currentProfileTab === "given") items = activeProfileData.given_kudos || [];

  if (items.length === 0) {
    container.innerHTML = `<p class="text-stone-400 font-bold text-center py-12 text-lg">No ${currentProfileTab} found for this member.</p>`;
  } else {
    container.innerHTML = items.map(item => renderFeedCard(item, true)).join("");
  }
}

function openEditProfileModal() {
  openModal("modal-edit-profile");
}

function populateEditProfileModal() {
  if (!currentUser) return;
  document.getElementById("eprof-avatar").value = currentUser.avatar_url;
  document.getElementById("eprof-bio").value = currentUser.bio || "";
}

async function handleProfileUpdate(e) {
  e.preventDefault();
  const avatar_url = document.getElementById("eprof-avatar").value.trim();
  const bio = document.getElementById("eprof-bio").value.trim();
  const password = document.getElementById("eprof-pw").value;

  try {
    const data = await apiFetch("/users/profile", {
      method: "PUT",
      body: JSON.stringify({ avatar_url, bio, password })
    });
    currentUser = data.user;
    updateAuthUI(currentUser);
    closeModal("modal-edit-profile");
    showToast("✏️ Profile updated successfully!");
    loadUserProfile(currentUser.id);
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

/* ================= EMAIL OUTBOX INSPECTOR (Req #19 & #22) ================= */

async function loadOutbox() {
  const container = document.getElementById("outbox-list");
  if (!container) return;
  container.innerHTML = `<p class="text-amber-800 font-bold text-center py-8 text-lg">Loading real-time audit logs...</p>`;
  try {
    const data = await apiFetch("/outbox");
    const emails = data.emails || [];

    if (emails.length === 0) {
      container.innerHTML = `<p class="text-amber-800 font-bold text-center py-8 text-lg">No notification emails triggered yet.</p>`;
      return;
    }

    container.innerHTML = emails.map(em => {
      let ctaBtn = "";
      if (em.subject && em.subject.includes("invited to join")) {
        const m = em.body.match(/group\/(\d+)/);
        const gId = m ? m[1] : "1";
        ctaBtn = `
          <div class="pt-4 border-t border-slate-200 mt-4 text-center font-sans">
            <a href="/#/group/${gId}?invite=yes" class="inline-flex items-center space-x-2 px-8 py-4 bg-emerald-600 hover:bg-emerald-700 text-white font-black text-lg rounded-2xl shadow-xl transition touch-target hover:scale-105">
              <span>💌</span><span>Accept Invitation & Become Member ↗</span>
            </a>
          </div>
        `;
      }
      return `
      <div class="bg-white p-7 rounded-3xl border-2 border-amber-300 shadow-sm space-y-3 font-mono text-sm">
        <div class="flex flex-wrap justify-between items-center bg-amber-100/70 p-4 rounded-2xl border border-amber-200">
          <div><strong class="text-amber-950">TO:</strong> <span class="text-teal-900 font-black text-base">${em.recipient_email}</span></div>
          <div class="text-xs font-bold text-amber-800">⏱️ ${em.sent_at} [${em.status}]</div>
        </div>
        <div class="text-lg font-sans font-black text-stone-900 border-b pb-2">SUBJECT: ${em.subject}</div>
        <div class="font-sans text-stone-800 text-lg whitespace-pre-line leading-relaxed pt-1 bg-stone-50 p-6 rounded-2xl border border-stone-200 font-medium">${em.body}${ctaBtn}</div>
      </div>
      `;
    }).join("");
  } catch (err) {}
}

/* ================= CUSTOMER SERVICE PORTAL (Req #22) ================= */

async function handleSupportSubmit(e) {
  e.preventDefault();
  const subject = document.getElementById("supp-subject").value.trim();
  const message = document.getElementById("supp-message").value.trim();

  try {
    const data = await apiFetch("/support", {
      method: "POST",
      body: JSON.stringify({ subject, message })
    });
    closeModal("modal-support");
    document.getElementById("supp-subject").value = "";
    document.getElementById("supp-message").value = "";
    showToast("✅ " + data.message);
    setTimeout(() => {
      if (confirm("Inquiry submitted! Would you like to view the simulated email alert sent to roht_kgupta@yahoo.com in the Email Outbox Audit Log?")) {
        navigateTo("/outbox");
      }
    }, 500);
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

/* ================= GAMIFICATION & MONTHLY SPOTLIGHT Req ================= */

async function loadSpotlightView(reqMonth = "June 2026") {
  const kGrid = document.getElementById("spotlight-kudos-grid");
  const pGrid = document.getElementById("spotlight-posts-grid");
  const rBox = document.getElementById("spotlight-res-container");
  if (!kGrid || !pGrid || !rBox) return;

  // Update month selector button styles
  document.querySelectorAll(".smonth-btn").forEach(btn => {
    if (btn.textContent.includes(reqMonth.split(" ")[0])) {
      btn.className = "smonth-btn px-4 py-2 rounded-xl font-bold text-sm bg-amber-500 text-white shadow-sm transition touch-target";
    } else {
      btn.className = "smonth-btn px-4 py-2 rounded-xl font-bold text-sm bg-slate-100 hover:bg-slate-200 text-slate-700 transition touch-target";
    }
  });

  const bannerTitle = document.querySelector("#view-spotlight h1");
  if (bannerTitle) bannerTitle.textContent = `${reqMonth} Community Champions`;

  kGrid.innerHTML = `<p class="col-span-4 text-center text-slate-400 py-6">Loading champions...</p>`;
  pGrid.innerHTML = `<p class="col-span-4 text-center text-slate-400 py-6">Loading storyteller...</p>`;
  rBox.innerHTML = `<p class="col-span-3 text-center text-slate-400 py-6">Loading valuable resources...</p>`;

  try {
    const data = await apiFetch(`/spotlight?month=${encodeURIComponent(reqMonth)}`);
    const medals = ["🥇", "🥈", "🥉", "🏅"];
    const colors = ["from-amber-500/20 to-amber-100/30 border-amber-300", "from-slate-200/50 to-slate-100 border-slate-300", "from-orange-200/40 to-orange-100/30 border-orange-300", "from-slate-50 to-white border-slate-200"];

    // 1. Kudos Champions
    kGrid.innerHTML = (data.top_kudos_champions || []).map((c, i) => `
      <div class="bg-gradient-to-br ${colors[i % 4]} p-6 rounded-3xl border shadow-sm text-center space-y-3 relative overflow-hidden transition hover:-translate-y-1">
        <div class="absolute top-3 right-3 text-2xl">${medals[i % 4]}</div>
        <img src="${c.avatar_url}" alt="${c.username}" class="w-20 h-20 rounded-full object-cover mx-auto border-4 border-white shadow-md">
        <div>
          <strong class="text-lg font-black text-slate-900 block truncate">${c.username}</strong>
          <span class="text-xs font-bold text-amber-700 uppercase tracking-wider block">Kindness Champion</span>
        </div>
        <p class="text-xs text-slate-600 line-clamp-2 min-h-[32px]">${c.bio || 'Promoting community goodness every single day.'}</p>
        <div class="bg-white/80 backdrop-blur px-4 py-2 rounded-2xl border border-amber-200/60 flex justify-around text-xs font-black text-slate-800">
          <span>🌟 ${c.kudos_count} Kudos</span>
          <span>❤️ ${c.total_reactions} Likes</span>
        </div>
      </div>
    `).join("");

    // 2. Post Storytellers
    pGrid.innerHTML = (data.top_post_creators || []).map((p, i) => `
      <div class="bg-gradient-to-br from-indigo-50/60 via-white to-teal-50/40 p-6 rounded-3xl border border-indigo-100 shadow-sm text-center space-y-3 relative overflow-hidden transition hover:-translate-y-1">
        <div class="absolute top-3 right-3 text-2xl">${medals[i % 4]}</div>
        <img src="${p.avatar_url}" alt="${p.username}" class="w-20 h-20 rounded-full object-cover mx-auto border-4 border-white shadow-md">
        <div>
          <strong class="text-lg font-black text-slate-900 block truncate">${p.username}</strong>
          <span class="text-xs font-bold text-indigo-600 uppercase tracking-wider block">Inspiring Creator</span>
        </div>
        <p class="text-xs text-slate-600 line-clamp-2 min-h-[32px]">${p.bio || 'Sharing impactful mutual aid stories.'}</p>
        <div class="bg-indigo-500/10 px-4 py-2 rounded-2xl border border-indigo-200/50 flex justify-around text-xs font-black text-indigo-950">
          <span>🔥 ${p.total_likes} Story Likes</span>
          <span>📝 ${p.post_count} Posts</span>
        </div>
      </div>
    `).join("");

    // 3. Valuable Resources
    const resDict = data.valuable_resources || {};
    let rHtml = "";
    Object.keys(resDict).forEach(catName => {
      const topR = (resDict[catName] || [])[0] || {};
      rHtml += `
        <div class="bg-white p-6 sm:p-8 rounded-3xl border border-slate-200 shadow-sm space-y-4 flex flex-col justify-between transition hover:shadow-md">
          <div class="space-y-2 text-left">
            <div class="flex justify-between items-center">
              <span class="px-3 py-1 bg-stone-100 text-stone-700 font-extrabold text-[11px] uppercase tracking-wider rounded-full">${catName}</span>
              <span class="px-3 py-1 bg-emerald-100 text-emerald-800 font-black text-xs rounded-full flex items-center space-x-1"><span>⬆️</span><span>${topR.saves || 128} Saves</span></span>
            </div>
            <h3 class="font-black text-slate-900 text-lg sm:text-xl pt-1 leading-snug">${topR.title || 'Essential Community Guide'}</h3>
            <p class="text-xs text-slate-500 font-medium">Curated inside: <strong class="text-slate-700">${topR.group_name || 'Community Center'}</strong></p>
          </div>
          <a href="${topR.url || '#'}" target="_blank" class="block w-full text-center py-3 bg-slate-900 hover:bg-slate-800 text-white font-bold text-sm rounded-xl transition shadow-sm touch-target">
            Access Resource ↗
          </a>
        </div>
      `;
    });
    rBox.innerHTML = rHtml || `<p class="col-span-3 text-center text-slate-400">No resources available yet.</p>`;

  } catch (err) {
    showToast("❌ Failed to load spotlight data: " + err.message);
  }
}

function cheerSpotlightChampions() {
  showToast("🎉🎊 🥳 Sending a massive community cheer to June's top contributors!");
  const popup = document.getElementById("toast-popup");
  if (popup) {
    popup.classList.add("scale-110", "bg-amber-600");
    setTimeout(() => popup.classList.remove("scale-110", "bg-amber-600"), 1500);
  }
}

/* ================= GROUP MEMBERS INVITATION (Req) ================= */

let allCommunityMembersCache = null;

async function openGroupInviteModal() {
  if (!activeGroupData) return;
  const gn = document.getElementById("ginvite-group-name");
  if (gn) gn.textContent = activeGroupData.name;
  openModal("modal-invite-group");

  if (!allCommunityMembersCache) {
    try {
      const data = await apiFetch("/users");
      allCommunityMembersCache = data.users || [];
    } catch (err) {}
  }
}

function handleInviteAutocomplete(query) {
  const sugBox = document.getElementById("ginvite-suggestions");
  if (!sugBox) return;
  if (!allCommunityMembersCache || !query) {
    sugBox.classList.add("hidden");
    return;
  }
  const parts = query.split(",");
  const currentTerm = parts[parts.length - 1].trim().toLowerCase();
  if (currentTerm.length < 1) {
    sugBox.classList.add("hidden");
    return;
  }

  const matches = allCommunityMembersCache.filter(u => 
    (u.username && u.username.toLowerCase().includes(currentTerm)) ||
    (u.email && u.email.toLowerCase().includes(currentTerm))
  ).slice(0, 6);

  if (matches.length === 0) {
    sugBox.classList.add("hidden");
    return;
  }

  sugBox.innerHTML = matches.map(u => `
    <div onclick="selectInviteMember('${u.email || u.username}')" class="px-4 py-3 hover:bg-indigo-50/80 cursor-pointer flex items-center space-x-3 transition">
      <img src="${u.avatar_url}" alt="${u.username}" class="w-8 h-8 rounded-full object-cover border border-slate-200 shrink-0">
      <div class="truncate text-left flex-1">
        <strong class="text-sm font-black text-slate-900 block truncate">${u.username}</strong>
        <span class="text-xs font-semibold text-indigo-600 block truncate">${u.email || ''}</span>
      </div>
    </div>
  `).join("");
  sugBox.classList.remove("hidden");
}

function selectInviteMember(selectedEmailOrName) {
  const input = document.getElementById("ginvite-email");
  const sugBox = document.getElementById("ginvite-suggestions");
  if (!input) return;
  const parts = input.value.split(",");
  parts[parts.length - 1] = selectedEmailOrName;
  input.value = parts.map(p => p.trim()).filter(Boolean).join(", ") + ", ";
  if (sugBox) sugBox.classList.add("hidden");
  input.focus();
}

document.addEventListener("click", e => {
  const sugBox = document.getElementById("ginvite-suggestions");
  const input = document.getElementById("ginvite-email");
  if (sugBox && !sugBox.classList.contains("hidden") && e.target !== input && !sugBox.contains(e.target)) {
    sugBox.classList.add("hidden");
  }
});

async function handleGroupInviteSubmit(e) {
  e.preventDefault();
  if (!activeGroupId) return;
  const emails = document.getElementById("ginvite-email").value.trim();
  const message = document.getElementById("ginvite-message").value.trim();
  if (!emails) {
    showToast("⚠️ Please enter recipient username or email.");
    return;
  }

  const submitBtn = e.target.querySelector("button[type='submit']");
  const origText = submitBtn ? submitBtn.textContent : "Send Invitation ↗";
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Sending..."; }

  try {
    const data = await apiFetch(`/groups/${activeGroupId}/invite`, {
      method: "POST",
      body: JSON.stringify({ emails, message })
    });
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = origText; }
    closeModal("modal-invite-group");
    document.getElementById("ginvite-email").value = "";
    document.getElementById("ginvite-message").value = "";
    if (activeGroupId) {
      try {
        const fresh = await apiFetch(`/groups/${activeGroupId}`);
        if (fresh && fresh.group) activeGroupData = fresh.group;
      } catch (err) {}
    }
    renderGroupRoster();
    showToast("✅ " + (data.message || "Invitation sent successfully!"));
    setTimeout(() => {
      if (confirm("Invitation sent successfully! Would you like to inspect the simulated invitation email in the Email Outbox Audit Log?")) {
        navigateTo("/outbox");
      }
    }, 300);
  } catch (err) {
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = origText; }
    showToast("❌ " + err.message);
  }
}

/* ================= PENDING GROUP INVITATIONS ON-SITE ALERTS ================= */

async function checkPendingInvitations() {
  const banner = document.getElementById("pending-invitations-banner");
  if (!banner) return;
  if (!currentUser) {
    banner.classList.add("hidden");
    return;
  }

  try {
    const data = await apiFetch("/invitations/pending");
    const invites = data.invitations || [];
    if (invites.length === 0) {
      banner.classList.add("hidden");
      return;
    }

    banner.innerHTML = `
      <div class="bg-gradient-to-r from-amber-500 via-yellow-500 to-amber-600 p-6 sm:p-8 rounded-3xl text-white shadow-xl space-y-4 border-4 border-amber-200 mb-2 text-left animate-fadeIn">
        <div class="flex items-center justify-between border-b border-white/30 pb-3">
          <span class="font-black text-xs sm:text-sm uppercase tracking-wider bg-white/25 backdrop-blur px-3.5 py-1.5 rounded-full shadow-sm">💌 You Have Pending Group Invitations!</span>
          <span class="text-xs font-extrabold bg-slate-900 px-3 py-1 rounded-full text-amber-300">${invites.length} Waiting</span>
        </div>
        <div class="space-y-3 pt-1">
          ${invites.map(inv => `
            <div class="bg-slate-900/40 backdrop-blur-md p-4 sm:p-5 rounded-2xl border border-white/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div class="flex items-center space-x-4 text-left flex-1">
                <img src="${inv.group_icon || 'https://images.unsplash.com/photo-1511632765486-a01980e01a18?auto=format&fit=crop&w=200&q=80'}" alt="${inv.group_name}" class="w-14 h-14 rounded-2xl object-cover border-2 border-white shadow shrink-0">
                <div>
                  <h4 class="font-black text-lg sm:text-xl text-white leading-snug">${inv.group_name}</h4>
                  <p class="text-xs sm:text-sm text-amber-100 font-medium pt-0.5">Invited by <strong class="text-white underline">${inv.sender_name}</strong>${inv.message ? ` — "${inv.message}"` : ''}</p>
                </div>
              </div>
              <div class="flex items-center space-x-2.5 shrink-0 w-full sm:w-auto justify-end pt-2 sm:pt-0">
                <button onclick="respondGroupInvite(${inv.invite_id}, 'reject')" class="px-5 py-3 bg-black/30 hover:bg-black/50 text-white font-bold text-xs sm:text-sm rounded-xl transition touch-target">Decline</button>
                <button onclick="respondGroupInvite(${inv.invite_id}, 'accept')" class="px-6 py-3 bg-white hover:bg-amber-100 text-slate-900 font-black text-xs sm:text-sm rounded-xl shadow-lg transition hover:scale-105 touch-target flex items-center space-x-1.5"><span>✅</span><span>Accept & Join</span></button>
              </div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
    banner.classList.remove("hidden");
  } catch (err) {
    banner.classList.add("hidden");
  }
}

async function respondGroupInvite(inviteId, action) {
  try {
    const data = await apiFetch("/invitations/respond", {
      method: "POST",
      body: JSON.stringify({ invite_id: inviteId, action })
    });
    showToast(data.message);
    checkPendingInvitations();
    if (action === "accept" && data.group_id) {
      setTimeout(() => navigateTo(`/group/${data.group_id}`), 400);
    }
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

function toggleCommentsStream(itemId) {
  const box = document.getElementById(`comments-stream-box-${itemId}`);
  const icon = document.getElementById(`comments-toggle-icon-${itemId}`);
  if (!box || !icon) return;

  const isCollapsed = box.classList.contains("hidden");
  const text = icon.textContent.trim();
  const isReplyFlow = text.includes("Reply") || text.includes("Write");

  if (isCollapsed) {
    box.classList.remove("hidden");
    icon.textContent = isReplyFlow ? "▲ Hide Reply" : "▲ Hide Thread";
    expandedThreads.add(itemId);
  } else {
    box.classList.add("hidden");
    icon.textContent = isReplyFlow ? "▼ Write Reply" : "▼ Show Thread";
    expandedThreads.delete(itemId);
  }
}

async function toggleMemberRole(gid, uid, isAdmin) {
  try {
    await apiFetch(`/groups/${gid}/members/role`, {
      method: "POST",
      body: JSON.stringify({ group_id: gid, user_id: uid, is_admin: isAdmin })
    });
    showToast(isAdmin ? "✅ User promoted to group admin!" : "ℹ️ User demoted from group admin.");
    await loadGroupDetail(gid);
    switchGroupTab("roster");
  } catch (err) {
    showToast("❌ " + (err.message || "Could not update member role."));
  }
}

/* Global scope attachments for DOM event handlers */
window.toggleCommentsStream = toggleCommentsStream;
window.toggleReaction = toggleReaction;
window.handleCommentSubmit = handleCommentSubmit;
window.filterByTheme = filterByTheme;
window.filterByGroup = filterByGroup;
window.filterByType = filterByType;
window.filterFeedByMyKudos = filterFeedByMyKudos;
window.filterFeedByMyPosts = filterFeedByMyPosts;
window.changeSortMode = changeSortMode;
window.clearAllFilters = clearAllFilters;
window.navigateTo = navigateTo;
window.openModal = openModal;
window.closeModal = closeModal;
window.switchModal = switchModal;
