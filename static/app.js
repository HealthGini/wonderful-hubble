/* gooddeeds.space Client-Side Vanilla JS SPA Controller */

const API_BASE = "/api";
let currentUser = null;
let currentToken = localStorage.getItem("gd_token") || null;
window._attachmentCache = window._attachmentCache || {};

// Discussion thread state persistence
const expandedThreads = new Set();

// Synchronized startup sequence promise
let sessionPromise = null;

// Feed filters state
let currentTheme = "";
let currentGroupFilter = "";
let currentSortMode = "smart";
let currentSearch = "";
let currentTypeFilter = "";
let currentMyKudosMode = "";
let currentMyPostsMode = "";
let currentFilterUserId = null;

// Feed pagination state
let feedLimit = 4;
let feedOffset = 0;
let feedHasMore = false;
let isLoadingMoreFeed = false;
let displayedFeedLimit = 4;

// Landing preview pagination state
let landingPreviewLimit = 4;
let landingPreviewOffset = 0;
let landingPreviewHasMore = false;
let isLoadingMoreLandingPreview = false;

// Wizard temporary draft storage
let draftPost = null;
let draftCurateResources = null;

// Active Group Detail State
let activeGroupId = null;
let activeGroupData = null;

// Active Profile User State
let activeProfileData = null;
let currentProfileTab = "posts";

// Autocomplete Users Cache
let allUsersCache = [];

/* ================= INITIALIZATION & ROUTING ================= */

sessionPromise = checkSession();

async function initApp() {
  setupEventListeners();
  try {
    await sessionPromise;
  } catch (err) {
    console.error("Session init error:", err);
  }
  try {
    loadQuickNavGroups();
  } catch (err) {
    console.error("QuickNav init error:", err);
  }
  await handleRoute();
}

if (document.readyState === "loading") {
  window.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

window.addEventListener("hashchange", async () => {
  await handleRoute();
});

function setupEventListeners() {
  let searchTimeout;
  const feedSearch = document.getElementById("feed-search-input");
  const feedSearchClearBtn = document.getElementById("feed-search-clear-btn");

  function updateSearchClearBtn() {
    if (!feedSearch || !feedSearchClearBtn) return;
    if (feedSearch.value.trim().length > 0) {
      feedSearchClearBtn.classList.remove("hidden");
    } else {
      feedSearchClearBtn.classList.add("hidden");
    }
  }

  if (feedSearch) {
    feedSearch.addEventListener("input", (e) => {
      updateSearchClearBtn();
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentSearch = e.target.value.trim();
        if (!currentSearch || !currentSearch.toLowerCase().includes("author:")) {
          currentFilterUserId = null;
          currentMyPostsMode = "";
          currentMyKudosMode = "";
        }
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
      if (window.location.hash !== "#/feed") {
        window.location.hash = "#/feed";
        return;
      }
      showView("view-feed");
      loadFeed();
      populateGroupFilterDropdown();
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
  const newHash = route.startsWith("#") ? route : `#${route}`;
  if (window.location.hash === newHash) {
    handleRoute();
  } else {
    window.location.hash = newHash;
  }
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
  let url;
  if (endpoint.startsWith("http")) {
    url = endpoint;
  } else if (endpoint.startsWith("/api/")) {
    url = endpoint;
  } else {
    url = API_BASE + (endpoint.startsWith("/") ? endpoint : "/" + endpoint);
  }
  const headers = options.headers || {};
  if (currentToken) {
    headers["Authorization"] = `Bearer ${currentToken}`;
  }
  if (!headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  options.headers = headers;

  const res = await fetch(url, options);
  let data = {};
  try {
    data = await res.json();
  } catch (err) {}

  if (!res.ok) {
    if (res.status === 401 && currentToken) {
      currentToken = null;
      localStorage.removeItem("gd_token");
      currentUser = null;
      updateAuthUI(null);
    }
    throw new Error(data.error || "Request failed");
  }
  return data;
}

async function checkSession() {
  if (!currentToken) {
    updateAuthUI(null);
    return;
  }
  const timeoutPromise = new Promise(resolve => setTimeout(resolve, 2500));
  try {
    const fetchPromise = apiFetch("/auth/me").then(data => {
      currentUser = data.user;
      updateAuthUI(currentUser);
    });
    await Promise.race([fetchPromise, timeoutPromise]);
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
    currentGroupFilter = "my_spaces";
  } else {
    guestBox.classList.remove("hidden");
    userBox.classList.add("hidden");
    currentGroupFilter = "";
  }
  populateGroupFilterDropdown();
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
    const token = data.token || data.access_token;
    if (!token) throw new Error(data.error || "Login failed");
    currentToken = token;
    localStorage.setItem("gd_token", currentToken);
    currentUser = data.user;
    sessionPromise = Promise.resolve();
    updateAuthUI(currentUser);
    closeModal("modal-login");
    showToast(`☀️ Welcome back, ${currentUser.username}!`);
    await loadQuickNavGroups();
    navigateTo("/feed");
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function presetLogin(email) {
  document.getElementById("login-email").value = email;
  document.getElementById("login-pw").value = "password123";
  try {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password: "password123" })
    });
    const token = data.token || data.access_token;
    if (!token) throw new Error(data.error || "Login failed");
    currentToken = token;
    localStorage.setItem("gd_token", currentToken);
    currentUser = data.user;
    sessionPromise = Promise.resolve();
    updateAuthUI(currentUser);
    closeModal("modal-login");
    showToast(`☀️ Welcome back, ${currentUser.username}!`);
    await loadQuickNavGroups();
    navigateTo("/feed");
  } catch (err) {
    showToast("❌ " + err.message);
  }
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
    sessionPromise = Promise.resolve();
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

/* ================= QUICK NAVIGATION (JOINED SPACES Req #1) ================= */

async function loadQuickNavGroups() {
  const container = document.getElementById("quick-groups-list");
  if (!container) return;
  if (!currentUser) {
    container.innerHTML = `<p class="px-4 py-3 text-slate-500 text-sm font-medium">Log in to see your joined spaces</p>`;
    return;
  }

  try {
    const data = await apiFetch("/groups/joined");
    const groups = data.groups || [];
    if (groups.length === 0) {
      container.innerHTML = `<p class="px-4 py-3 text-slate-500 text-sm font-medium">You haven't joined any spaces yet. Explore above!</p>`;
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
  if (!item) return "";
  const authorName = item.author_name || "Anonymous";
  const recipientName = item.recipient_name || "Community Member";
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
  const emojis = ["👍", "❤️", "👏", "🌟", "🤗", "🎉"];
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
  const commentsCount = (item.comments || []).length;
  const toggleIconText = isExpanded 
    ? (commentsCount > 0 ? "▲ Hide Thread" : "▲ Hide Reply")
    : (commentsCount > 0 ? "▼ Show Thread" : "▼ Write Reply");

  return `
    <article class="bg-white rounded-3xl border border-slate-200/80 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 p-6 sm:p-8 space-y-6 ${cardClass}">
      
      <!-- Author & Recipient Banner -->
      <div class="flex flex-wrap justify-between items-center gap-4">
        <div class="flex items-center space-x-3.5">
          ${isKudos ? `
            <a href="/#/user/${item.recipient_id}">
              <img src="${item.recipient_avatar || item.author_avatar}" alt="${recipientName}" class="w-12 h-12 rounded-full object-cover border-2 border-amber-400 shadow-sm">
            </a>
            <div>
              <div class="text-lg font-bold text-slate-900 flex items-center flex-wrap gap-1.5">
                <a href="/#/user/${item.recipient_id}" class="hover:text-amber-700 transition font-extrabold text-slate-900">${recipientName}</a>
                ${["Maya_Lin", "Marcus_Vance", "Elena_Wellness", "Arthur_Pendleton"].includes(recipientName) ? `<a href="/#/spotlight" class="inline-flex items-center space-x-1 px-2.5 py-0.5 bg-gradient-to-r from-amber-500 to-yellow-500 text-white font-black text-[10px] rounded-full uppercase tracking-wider shadow-sm hover:opacity-90 transition" title="June 2026 Hall of Fame Winner"><span>👑</span><span>Monthly Winner</span></a>` : ""}
                <span class="text-amber-600 font-semibold text-base">received Kudos from</span>
                <a href="/#/user/${item.author_id}" class="hover:underline font-bold text-slate-700 bg-stone-100 border border-stone-200 px-3 py-0.5 rounded-full text-sm">${authorName}</a>
                ${["Maya_Lin", "Marcus_Vance", "Elena_Wellness", "Arthur_Pendleton"].includes(authorName) && !["Maya_Lin", "Marcus_Vance", "Elena_Wellness", "Arthur_Pendleton"].includes(recipientName) ? `<a href="/#/spotlight" class="inline-flex items-center space-x-1 px-2.5 py-0.5 bg-gradient-to-r from-amber-500 to-yellow-500 text-white font-black text-[10px] rounded-full uppercase tracking-wider shadow-sm hover:opacity-90 transition" title="June 2026 Hall of Fame Winner"><span>👑</span><span>Monthly Winner</span></a>` : ""}
              </div>
              <div class="text-xs text-slate-400 font-medium pt-0.5">
                <span>⏱️ ${item.created_at}</span>
                <span class="px-2">•</span>
                <a href="${itemLink}" class="text-slate-400 hover:text-indigo-600 transition">Direct Share Link ↗</a>
              </div>
            </div>
          ` : `
            <a href="/#/user/${item.author_id}">
              <img src="${item.author_avatar}" alt="${authorName}" class="w-12 h-12 rounded-full object-cover border border-slate-200 shadow-sm">
            </a>
            <div>
              <div class="text-lg font-bold text-slate-900 flex items-center flex-wrap gap-1.5">
                <a href="/#/user/${item.author_id}" class="hover:text-indigo-600 transition">${authorName}</a>
                ${["Maya_Lin", "Marcus_Vance", "Elena_Wellness", "Arthur_Pendleton"].includes(authorName) ? `<a href="/#/spotlight" class="inline-flex items-center space-x-1 px-2.5 py-0.5 bg-gradient-to-r from-amber-500 to-yellow-500 text-white font-black text-[10px] rounded-full uppercase tracking-wider shadow-sm hover:opacity-90 transition" title="June 2026 Hall of Fame Winner"><span>👑</span><span>Monthly Winner</span></a>` : ""}
                <span class="px-2.5 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-full text-xs font-bold">🏷️ ${item.theme}</span>
              </div>
              <div class="text-xs text-slate-400 font-medium pt-0.5">
                <span>⏱️ ${item.created_at}</span>
                <span class="px-2">•</span>
                <a href="${itemLink}" class="text-slate-400 hover:text-indigo-600 transition">Direct Share Link ↗</a>
              </div>
            </div>
          `}
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
          return `<div class="pt-3 flex flex-wrap gap-2">` + urls.map((u, idx) => {
            const cacheKey = `attachment_${item.id}_${idx}`;
            window._attachmentCache[cacheKey] = u;
            return `
            <button type="button" onclick="window.openAttachment(window._attachmentCache['${cacheKey}'], 'attachment_${item.id}_${idx}')" class="inline-flex items-center space-x-2 px-4 py-2.5 rounded-xl bg-indigo-50 hover:bg-indigo-100 text-indigo-950 font-bold text-sm border border-indigo-200 transition touch-target shadow-sm">
              <span>${formatAttachmentLabel(u, idx, urls.length)}</span>
            </button>
            `;
          }).join("") + `</div>`;
        })()}
      </div>

      <!-- Emoji Reactions Bar -->
      <div class="flex flex-wrap items-center gap-2 pt-2 border-t border-stone-100">
        <span class="text-xs font-black text-stone-400 uppercase tracking-wider pr-1">Celebrate:</span>
        ${reactionsHtml}
      </div>

      <!-- Comments Stream & Authoring Input -->
      <div class="bg-stone-100/70 !mt-2 py-1 px-3 sm:py-1.5 sm:px-4 rounded-xl border border-stone-200 space-y-3">
        <button type="button" onclick="toggleCommentsStream(${item.id})" class="w-full flex justify-between items-center text-sm font-black text-stone-500 uppercase tracking-wider hover:text-stone-850 transition touch-target">
          <span class="flex items-center space-x-1.5">
            <span>💬 Community Discussion</span>
            <span class="bg-stone-200 text-stone-700 px-2 py-0.5 rounded-full text-xs font-extrabold">${commentsCount}</span>
          </span>
          <span id="comments-toggle-icon-${item.id}" class="text-xs text-amber-700 hover:underline">
            ${toggleIconText}
          </span>
        </button>

        <div id="comments-stream-box-${item.id}" class="${commentsBoxClass}">
          ${commentsCount > 0 ? `
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

async function loadLandingPreview(isLoadMore = false) {
  const container = document.getElementById("landing-public-feed-preview") || document.getElementById("landing-preview-feed");
  const loadMoreContainer = document.getElementById("landing-load-more-container");
  if (!container) return;

  if (!isLoadMore) {
    landingPreviewOffset = 0;
    container.innerHTML = `<p class="text-stone-500 font-bold text-center col-span-2 py-8">Loading highlights...</p>`;
    if (loadMoreContainer) loadMoreContainer.innerHTML = "";
  }

  let reqLimit = landingPreviewLimit;
  let reqOffset = landingPreviewOffset;

  let url = `/feed?sort=smart&limit=${reqLimit}&offset=${reqOffset}`;

  try {
    const data = await apiFetch(url);
    const feed = data.feed || [];
    landingPreviewHasMore = (data.has_more !== undefined) ? data.has_more : (feed.length === reqLimit);

    if (!isLoadMore) {
      if (feed.length === 0) {
        container.innerHTML = `<p class="text-stone-500 font-bold text-center col-span-2 py-8">No community posts or kudos yet.</p>`;
        if (loadMoreContainer) loadMoreContainer.innerHTML = "";
      } else {
        container.innerHTML = feed.map(item => { try { return renderFeedCard(item, false); } catch(err) { console.error("Failed to render preview card:", err, item); return ""; } }).join("");
        renderLandingLoadMoreControls();
      }
    } else {
      if (feed.length > 0) {
        container.insertAdjacentHTML("beforeend", feed.map(item => { try { return renderFeedCard(item, false); } catch(err) { console.error("Failed to render preview card:", err, item); return ""; } }).join(""));
      }
      renderLandingLoadMoreControls();
    }
  } catch (err) {
    if (!isLoadMore) {
      container.innerHTML = `<p class="text-center font-bold text-red-600 col-span-2 py-8">Failed to load highlights: ${err.message}</p>`;
    }
  }
}

function renderLandingLoadMoreControls() {
  const loadMoreContainer = document.getElementById("landing-load-more-container");
  if (!loadMoreContainer) return;

  if (landingPreviewHasMore) {
    loadMoreContainer.innerHTML = `
      <button id="landing-load-more-btn" onclick="loadMoreLandingPreview()" class="px-8 py-3.5 bg-indigo-600 hover:bg-indigo-700 text-white font-black text-base rounded-2xl shadow-sm hover:shadow transition duration-200 inline-flex items-center space-x-2 touch-target">
        <span>Load More Posts & Kudos</span>
        <span>👇</span>
      </button>
    `;
  } else {
    loadMoreContainer.innerHTML = `
      <div class="py-4 text-center">
        <p class="text-slate-500 font-bold text-sm bg-slate-100 inline-block px-6 py-2.5 rounded-full border border-slate-200">You're all caught up! 🎉</p>
      </div>
    `;
  }
}

async function loadMoreLandingPreview() {
  if (isLoadingMoreLandingPreview || !landingPreviewHasMore) return;
  isLoadingMoreLandingPreview = true;
  const loadMoreBtn = document.getElementById("landing-load-more-btn");
  if (loadMoreBtn) {
    loadMoreBtn.disabled = true;
    loadMoreBtn.innerHTML = `<span>Loading...</span> <span class="animate-spin inline-block">⏳</span>`;
  }
  landingPreviewOffset += landingPreviewLimit;
  await loadLandingPreview(true);
  isLoadingMoreLandingPreview = false;
}

async function loadFeed(isLoadMore = false, isReload = false) {
  await sessionPromise;
  checkPendingInvitations();
  const container = document.getElementById("feed-items-container");
  const loadMoreContainer = document.getElementById("feed-load-more-container");
  if (!container) return;

  if (!isLoadMore && !isReload) {
    feedOffset = 0;
    displayedFeedLimit = 4;
    container.innerHTML = `<p class="text-center font-bold text-xl text-stone-500 py-12">Loading feed...</p>`;
    if (loadMoreContainer) loadMoreContainer.innerHTML = "";
  }

  let reqLimit = isLoadMore ? feedLimit : (isReload ? displayedFeedLimit : feedLimit);
  let reqOffset = isLoadMore ? feedOffset : 0;

  let url = `/feed?sort=${currentSortMode}&limit=${reqLimit}&offset=${reqOffset}&`;
  if (currentTheme) url += `theme=${encodeURIComponent(currentTheme)}&`;
  if (currentGroupFilter) url += `group_id=${encodeURIComponent(currentGroupFilter)}&`;
  if (currentSearch) url += `search=${encodeURIComponent(currentSearch)}&`;
  if (currentTypeFilter) url += `filter_type=${encodeURIComponent(currentTypeFilter)}&`;
  let userIdToFilter = currentFilterUserId || (currentUser ? currentUser.id : null);
  if (currentMyKudosMode === "received" && userIdToFilter) url += `recipient_id=${userIdToFilter}&filter_type=KUDOS&`;
  if (currentMyKudosMode === "given" && userIdToFilter) url += `author_id=${userIdToFilter}&filter_type=KUDOS&`;
  if (currentMyPostsMode === "authored" && userIdToFilter) url += `author_id=${userIdToFilter}&filter_type=POST&`;

  try {
    const data = await apiFetch(url);
    const feed = data.feed || [];
    feedHasMore = (data.has_more !== undefined) ? data.has_more : (feed.length === reqLimit);

    if (!isLoadMore) {
      if (feed.length === 0) {
        if (currentGroupFilter === "my_spaces") {
          currentGroupFilter = "";
          const gSel = document.getElementById("feed-group-select");
          if (gSel) gSel.value = "";
          return loadFeed(isLoadMore, isReload);
        }
        container.innerHTML = `
          <div class="bg-white p-12 rounded-3xl border border-slate-200 text-center space-y-3">
            <div class="text-5xl">🕊️</div>
            <h3 class="text-2xl font-bold text-slate-800">No Posts or Kudos Found</h3>
            <p class="text-base text-slate-500 font-medium">No posts or kudos match your active filter selection.</p>
            <button onclick="clearAllFilters()" class="px-6 py-3 bg-amber-500 hover:bg-amber-600 text-white font-bold rounded-xl shadow-sm transition">Reset All Filters</button>
          </div>
        `;
        if (loadMoreContainer) loadMoreContainer.innerHTML = "";
      } else {
        container.innerHTML = feed.map(item => { try { return renderFeedCard(item, false); } catch(err) { console.error("Failed to render feed card:", err, item); return ""; } }).join("");
        renderLoadMoreControls();
      }
    } else {
      if (feed.length > 0) {
        container.insertAdjacentHTML("beforeend", feed.map(item => { try { return renderFeedCard(item, false); } catch(err) { console.error("Failed to render feed card:", err, item); return ""; } }).join(""));
        displayedFeedLimit = feedOffset + feed.length;
      }
      renderLoadMoreControls();
    }
  } catch (err) {
    if (!isLoadMore) {
      if (currentGroupFilter) {
        currentGroupFilter = "";
        const gSel = document.getElementById("feed-group-select");
        if (gSel) gSel.value = "";
        return loadFeed(isLoadMore, isReload);
      }
      container.innerHTML = `<p class="text-center font-bold text-red-600 py-12">Failed to load feed: ${err.message}</p>`;
    }
  }
}

function renderLoadMoreControls() {
  const loadMoreContainer = document.getElementById("feed-load-more-container");
  if (!loadMoreContainer) return;

  if (feedHasMore) {
    loadMoreContainer.innerHTML = `
      <button id="load-more-btn" onclick="loadMoreFeed()" class="px-8 py-3.5 bg-indigo-600 hover:bg-indigo-700 text-white font-black text-base rounded-2xl shadow-sm hover:shadow transition duration-200 inline-flex items-center space-x-2 touch-target">
        <span>Load More Posts & Kudos</span>
        <span>👇</span>
      </button>
    `;
  } else {
    loadMoreContainer.innerHTML = `
      <div class="py-4 text-center">
        <p class="text-slate-500 font-bold text-sm bg-slate-100 inline-block px-6 py-2.5 rounded-full border border-slate-200">You're all caught up! 🎉</p>
      </div>
    `;
  }
}

async function loadMoreFeed() {
  if (isLoadingMoreFeed || !feedHasMore) return;
  isLoadingMoreFeed = true;
  const loadMoreBtn = document.getElementById("load-more-btn");
  if (loadMoreBtn) {
    loadMoreBtn.disabled = true;
    loadMoreBtn.innerHTML = `<span>Loading...</span> <span class="animate-spin inline-block">⏳</span>`;
  }
  feedOffset += feedLimit;
  await loadFeed(true, false);
  isLoadingMoreFeed = false;
}

function filterByTheme(th) {
  currentTheme = th;
  document.querySelectorAll(".theme-pill").forEach(el => {
    const onclickAttr = el.getAttribute("onclick") || "";
    if (th !== "" && onclickAttr.includes(`'${th}'`)) {
      el.className = "theme-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-amber-500 text-white shadow-sm transition touch-target";
    } else if (th === "" && onclickAttr.includes("''")) {
      el.className = "theme-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-slate-900 text-white transition touch-target shadow-sm";
    } else {
      el.className = "theme-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-slate-100 hover:bg-slate-200 text-slate-700 transition touch-target";
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

async function getUsernameForIdAsync(targetId) {
  if (!targetId && currentUser) return currentUser.username;
  if (currentUser && currentUser.id === Number(targetId)) return currentUser.username;
  if (activeProfileData && activeProfileData.user && activeProfileData.user.id === Number(targetId)) {
    return activeProfileData.user.username;
  }
  const uObj = allUsersCache.find(u => u.id === Number(targetId));
  if (uObj) return uObj.username;
  try {
    const data = await apiFetch(`/users/${targetId}`);
    if (data && data.user) return data.user.username;
  } catch(e) {}
  return currentUser ? currentUser.username : "Maya_Lin";
}

async function filterFeedByMyKudos(mode, targetUserId = null) {
  currentFilterUserId = targetUserId || (currentUser ? currentUser.id : null);
  currentMyPostsMode = "";
  if (mode === "all") {
    currentMyKudosMode = "";
    currentTypeFilter = "";
    currentFilterUserId = null;
    currentSearch = "";
    const sInput = document.getElementById("feed-search-input");
    if (sInput) sInput.value = "";
    const clearBtn = document.getElementById("feed-search-clear-btn");
    if (clearBtn) clearBtn.classList.add("hidden");
    showToast("🔄 Showing all community feed items.");
  } else {
    currentMyKudosMode = mode;
    currentTypeFilter = "KUDOS";
    const typeSel = document.getElementById("feed-type-select");
    if (typeSel) typeSel.value = "KUDOS";
    const username = await getUsernameForIdAsync(currentFilterUserId);
    currentSearch = `author:${username}`;
    const sInput = document.getElementById("feed-search-input");
    if (sInput) sInput.value = currentSearch;
    const clearBtn = document.getElementById("feed-search-clear-btn");
    if (clearBtn) clearBtn.classList.remove("hidden");
    showToast(mode === "received" ? `📥 Filtering by Kudos received by ${username}!` : `📤 Filtering by Kudos given by ${username}!`);
  }
  if (window.location.hash !== "#/feed" && window.location.hash !== "#/" && window.location.hash !== "") {
    navigateTo("/feed");
  } else {
    loadFeed();
  }
}

async function filterFeedByMyPosts(mode, targetUserId = null) {
  currentFilterUserId = targetUserId || (currentUser ? currentUser.id : null);
  currentMyKudosMode = "";
  if (mode === "all") {
    currentMyPostsMode = "";
    currentTypeFilter = "";
    currentFilterUserId = null;
    currentSearch = "";
    const sInput = document.getElementById("feed-search-input");
    if (sInput) sInput.value = "";
    const clearBtn = document.getElementById("feed-search-clear-btn");
    if (clearBtn) clearBtn.classList.add("hidden");
    showToast("🔄 Showing all community feed items.");
  } else {
    currentMyPostsMode = "authored";
    currentTypeFilter = "POST";
    currentGroupFilter = "";
    const typeSel = document.getElementById("feed-type-select");
    if (typeSel) typeSel.value = "POST";
    const grpSel = document.getElementById("feed-group-select");
    if (grpSel) grpSel.value = "";
    const username = await getUsernameForIdAsync(currentFilterUserId);
    currentSearch = `author:${username}`;
    const sInput = document.getElementById("feed-search-input");
    if (sInput) sInput.value = currentSearch;
    const clearBtn = document.getElementById("feed-search-clear-btn");
    if (clearBtn) clearBtn.classList.remove("hidden");
    showToast(`📂 Filtering by Posts authored by ${username}!`);
  }
  if (window.location.hash !== "#/feed" && window.location.hash !== "#/" && window.location.hash !== "") {
    navigateTo("/feed");
  } else {
    loadFeed();
  }
}

function clearFeedSearchInput() {
  const sInput = document.getElementById("feed-search-input");
  if (sInput) sInput.value = "";
  const clearBtn = document.getElementById("feed-search-clear-btn");
  if (clearBtn) clearBtn.classList.add("hidden");
  clearAllFilters();
}
window.clearFeedSearchInput = clearFeedSearchInput;

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
  currentFilterUserId = null;
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
    const groups = data.groups || [];
    let html = "";
    if (currentUser) {
      html += `<option value="my_spaces">⭐ My Spaces (All Joined)</option>`;
      html += `<option value="">All Spaces</option>`;
      const joined = groups.filter(g => g.is_joined);
      const others = groups.filter(g => !g.is_joined);
      if (joined.length > 0) {
        html += `<optgroup label="My Joined Spaces">` +
          joined.map(g => `<option value="${g.id}">👥 ${g.name}</option>`).join("") +
          `</optgroup>`;
      }
      if (others.length > 0) {
        html += `<optgroup label="Other Community Spaces">` +
          others.map(g => `<option value="${g.id}">👥 ${g.name}</option>`).join("") +
          `</optgroup>`;
      }
    } else {
      html += `<option value="">All Spaces</option>`;
      html += groups.map(g => `<option value="${g.id}">👥 ${g.name}</option>`).join("");
    }
    sel.innerHTML = html;
    if (currentGroupFilter) {
      sel.value = currentGroupFilter;
    }
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
        <h2 class="text-3xl font-black text-stone-800">Kudos or Post Not Found</h2>
        <p class="text-lg text-stone-600">The requested direct link may be invalid or expired.</p>
        <button onclick="navigateTo('/feed')" class="px-6 py-3 bg-amber-600 text-white font-bold rounded-xl">Return to Feed</button>
      </div>
    `;
  }
}

/* ================= CONTENT CREATION WIZARDS ================= */

/* Give Kudos Modal Autocomplete (Req #4) */
async function populateKudosModal() {
  const recipInput = document.getElementById("kudos-recipient-input");
  const recipIdHidden = document.getElementById("kudos-recipient-id");
  if (recipInput) recipInput.value = "";
  if (recipIdHidden) recipIdHidden.value = "";
  const container = document.getElementById("kudos-groups-list");
  if (container) container.innerHTML = `<p class="text-stone-500 font-medium text-sm p-2">Select a recipient to see shared groups.</p>`;

  try {
    const data = await apiFetch("/users");
    allUsersCache = data.users || [];
  } catch (err) {}
}

function handleKudosRecipientSearch(query) {
  const sugBox = document.getElementById("kudos-recipient-suggestions");
  if (!sugBox) return;
  const term = query.trim().toLowerCase();
  if (!term || !allUsersCache.length) {
    sugBox.classList.add("hidden");
    return;
  }

  const matches = allUsersCache.filter(u => 
    (!currentUser || u.id !== currentUser.id) &&
    ((u.username && u.username.toLowerCase().includes(term)) ||
     (u.email && u.email.toLowerCase().includes(term)))
  ).slice(0, 6);

  if (matches.length === 0) {
    sugBox.classList.add("hidden");
    return;
  }

  sugBox.innerHTML = matches.map(u => `
    <div onclick="selectKudosRecipient(${u.id}, '${u.username.replace(/'/g, "\\'")}', '${(u.email || '').replace(/'/g, "\\'")}')" class="px-4 py-3 hover:bg-amber-50 cursor-pointer flex items-center space-x-3 transition">
      <img src="${u.avatar_url}" alt="${u.username}" class="w-8 h-8 rounded-full object-cover border border-slate-200 shrink-0">
      <div class="truncate text-left flex-1">
        <strong class="text-sm font-black text-slate-900 block truncate">${u.username}</strong>
        <span class="text-xs font-semibold text-amber-700 block truncate">${u.email || ''}</span>
      </div>
    </div>
  `).join("");
  sugBox.classList.remove("hidden");
}

function selectKudosRecipient(id, username, email) {
  const recipInput = document.getElementById("kudos-recipient-input");
  const recipIdHidden = document.getElementById("kudos-recipient-id");
  const sugBox = document.getElementById("kudos-recipient-suggestions");
  if (recipInput) recipInput.value = username;
  if (recipIdHidden) recipIdHidden.value = id;
  if (sugBox) sugBox.classList.add("hidden");
  updateKudosGroupCheckboxes();
}

document.addEventListener("click", e => {
  const sugBox = document.getElementById("kudos-recipient-suggestions");
  const input = document.getElementById("kudos-recipient-input");
  if (sugBox && !sugBox.classList.contains("hidden") && e.target !== input && !sugBox.contains(e.target)) {
    sugBox.classList.add("hidden");
  }
});

async function updateKudosGroupCheckboxes() {
  const container = document.getElementById("kudos-groups-list");
  const recipIdHidden = document.getElementById("kudos-recipient-id");
  if (!container || !recipIdHidden) return;
  const targetId = recipIdHidden.value;
  if (!targetId) {
    container.innerHTML = `<p class="text-stone-500 font-medium text-sm p-2">Select a recipient to see shared groups.</p>`;
    return;
  }
  try {
    const data = await apiFetch(`/groups/joined?target_user_id=${targetId}`);
    const groups = data.groups || [];
    if (groups.length === 0) {
      container.innerHTML = `<p class="text-stone-500 font-medium text-sm p-2">You and this member do not share any common groups yet.</p>`;
    } else {
      container.innerHTML = groups.map(g => `
        <label class="inline-flex items-center space-x-2 px-3 py-2 rounded-xl bg-white border-2 border-stone-200 font-bold text-sm cursor-pointer hover:bg-amber-50 hover:border-amber-400 transition touch-target">
          <input type="checkbox" name="kudos-group" value="${g.id}" class="w-5 h-5 text-amber-600 rounded">
          <span>${g.name}</span>
        </label>
      `).join("");
    }
  } catch (err) {
    container.innerHTML = `<p class="text-stone-500 font-medium text-sm p-2">Failed to load common groups.</p>`;
  }
}

async function handleGiveKudos(e) {
  e.preventDefault();
  const recipient_id = parseInt(document.getElementById("kudos-recipient-id").value);
  const content = document.getElementById("kudos-content").value.trim();
  const group_ids = Array.from(document.querySelectorAll("#kudos-groups-list input:checked")).map(el => parseInt(el.value));

  if (!recipient_id) {
    showToast("⚠️ Please select a valid member from the recipient list.");
    return;
  }

  try {
    const data = await apiFetch("/kudos", {
      method: "POST",
      body: JSON.stringify({ recipient_id, content, group_ids })
    });
    closeModal("modal-kudos");
    document.getElementById("kudos-content").value = "";
    document.getElementById("kudos-recipient-input").value = "";
    document.getElementById("kudos-recipient-id").value = "";
    showToast("🌟 Public Kudos sent & email alert triggered!");
    if (window.location.hash.includes("/feed") || window.location.hash === "#/") loadFeed();
    else navigateTo("/feed");
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

/* Create Post Subtype & Event Date Logic (Req #3) */
function togglePostSubtype(subtype) {
  const container = document.getElementById("post-event-date-container");
  const dateInput = document.getElementById("post-event-date");
  if (!container) return;

  if (subtype === "Community Event" || subtype === "EVENT") {
    container.classList.remove("hidden");
    const today = new Date().toISOString().split("T")[0];
    if (dateInput) {
      dateInput.setAttribute("min", today);
      if (!dateInput.value) dateInput.value = today;
    }
  } else {
    container.classList.add("hidden");
  }
}

async function populatePostModal() {
  populateGroupCheckboxes("post-groups-list", "post-group");
  const defaultSubtypeRadio = document.querySelector("input[name='post_subtype'][value='GENERAL'], input[name='post-subtype'][value='General Post'], input[name='post_subtype'][value='GENERAL']");
  if (defaultSubtypeRadio) {
    defaultSubtypeRadio.checked = true;
    togglePostSubtype(defaultSubtypeRadio.value);
  }
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

async function reviewPostStep(e) {
  if (e) e.preventDefault();
  const title = document.getElementById("post-input-title").value.trim();
  const theme = document.getElementById("post-input-theme").value;
  let content = document.getElementById("post-input-content").value.trim();
  const subtypeRadio = document.querySelector("input[name='post_subtype']:checked, input[name='post-subtype']:checked");
  const rawSubtype = subtypeRadio ? subtypeRadio.value : "GENERAL";
  const subtype = rawSubtype === "Community Event" ? "EVENT" : (rawSubtype === "Community Resource" ? "RESOURCE" : (rawSubtype === "General Post" ? "GENERAL" : rawSubtype));
  const eventDate = document.getElementById("post-event-date") ? document.getElementById("post-event-date").value : "";

  if (!title || !content) {
    showToast("Please provide both a title and description/story content.");
    return;
  }

  if (subtype === "Community Event" && eventDate) {
    content = `📅 Event Date: ${eventDate}\n\n${content}`;
  }

  const linkInputs = document.querySelectorAll(".post-link-input");
  const fileInput = document.getElementById("post-file-input");
  const group_ids = Array.from(document.querySelectorAll("#post-groups-list input:checked")).map(el => parseInt(el.value));

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
    <div class="flex flex-wrap gap-2 pt-1">
      <span class="px-3 py-1 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full text-xs font-bold">🏷️ ${theme}</span>
      <span class="px-3 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-full text-xs font-bold">${subtype === "Community Event" ? "📅 Event" : subtype === "Community Resource" ? "📚 Resource" : "📝 Post"}</span>
    </div>
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
    showToast("✅ Post published permanently to community feed!");
    navigateTo("/feed");
    loadFeed();
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

/* Add Space Resources 2-Step Wizard (Req #5) */
function toggleCurateSubtype(subtype) {
  const container = document.getElementById("curate-event-date-container");
  const dateInput = document.getElementById("curate-event-date");
  if (!container) return;

  if (subtype === "Community Event") {
    container.classList.remove("hidden");
    const today = new Date().toISOString().split("T")[0];
    if (dateInput) {
      dateInput.setAttribute("min", today);
      if (!dateInput.value) dateInput.value = today;
    }
  } else {
    container.classList.add("hidden");
  }
}

async function reviewCurateStep(e) {
  if (e) e.preventDefault();
  const title = document.getElementById("curate-title").value.trim();
  let desc = document.getElementById("curate-desc").value.trim();
  const theme = document.getElementById("res-theme").value;
  const subtypeRadio = document.querySelector("input[name='curate-subtype']:checked");
  const subtype = subtypeRadio ? subtypeRadio.value : "General Post";
  const eventDate = document.getElementById("curate-event-date") ? document.getElementById("curate-event-date").value : "";

  if (!title || !desc) {
    showToast("Please provide both a title and description.");
    return;
  }

  if (subtype === "Community Event" && eventDate) {
    desc = `📅 Event Date: ${eventDate}\n\n${desc}`;
  }

  const linkInputs = document.querySelectorAll(".curate-link-input");
  const fileInput = document.getElementById("curate-file-input");

  const resources = [];
  linkInputs.forEach((inp, idx) => {
    const u = inp.value.trim();
    if (u) {
      resources.push({
        title: linkInputs.length > 1 ? `${title} (Link ${idx+1})` : title,
        description: desc,
        url: u,
        resource_type: "URL",
        theme: theme
      });
    }
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
      if (dataUrl) {
        resources.push({
          title: file.name,
          description: desc ? `${file.name} - ${desc}` : file.name,
          url: dataUrl,
          resource_type: file.name.toLowerCase().endsWith(".pdf") ? "PDF" : "FILE",
          theme: theme
        });
      }
    } catch(err) {}
  }

  if (resources.length === 0) {
    showToast("Please add at least one web link or select a file to upload.");
    return;
  }

  draftCurateResources = resources;

  document.getElementById("curate-step-1").classList.add("hidden");
  document.getElementById("curate-step-2").classList.remove("hidden");

  const previewBox = document.getElementById("curate-preview-card");
  previewBox.innerHTML = `
    <div class="font-extrabold text-2xl text-slate-900 tracking-tight">${title}</div>
    <div class="flex flex-wrap gap-2 pt-1">
      <span class="px-3 py-1 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full text-xs font-bold">🏷️ ${theme}</span>
      <span class="px-3 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-full text-xs font-bold">${subtype === "Community Event" ? "📅 Event" : subtype === "Community Resource" ? "📚 Resource" : "📝 Post"}</span>
    </div>
    <p class="text-base text-slate-700 pt-3 whitespace-pre-line font-medium leading-relaxed">${desc}</p>
    <div class="pt-3 font-bold text-indigo-600 text-sm">📎 ${resources.length} Resource Item(s) Ready to Add</div>
  `;
}

function backToCurateStep1() {
  document.getElementById("curate-step-1").classList.remove("hidden");
  document.getElementById("curate-step-2").classList.add("hidden");
}

async function confirmSubmitCurateResources() {
  if (!draftCurateResources || !activeGroupId) return;
  try {
    await apiFetch(`/groups/${activeGroupId}/resources`, {
      method: "POST",
      body: JSON.stringify({ resources: draftCurateResources })
    });
    showToast(`✅ Successfully attached ${draftCurateResources.length} resource(s) to space library!`);

    draftCurateResources = null;
    document.getElementById("curate-title").value = "";
    document.getElementById("curate-desc").value = "";
    document.querySelectorAll(".curate-link-input").forEach((inp, idx) => {
      if (idx === 0) inp.value = "";
      else inp.closest(".flex").remove();
    });
    const fileInput = document.getElementById("curate-file-input");
    if (fileInput) fileInput.value = "";
    const preview = document.getElementById("curate-files-preview");
    if (preview) preview.innerHTML = "";

    backToCurateStep1();
    await loadGroupDetail(activeGroupId);
    switchGroupTab("resources");
  } catch (err) {
    showToast("❌ " + (err.message || "Upload failed."));
  }
}

async function submitBatchGroupResources(e) {
  reviewCurateStep(e);
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
      loadFeed(false, true);
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
      loadFeed(false, true);
    }
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

/* ================= GROUPS DIRECTORY ================= */

async function loadGroups(searchQuery = "") {
  const container = document.getElementById("groups-grid");
  if (!container) return;
  container.innerHTML = `<p class="text-stone-500 font-bold text-xl col-span-3 text-center py-12">Loading spaces...</p>`;

  const themeFilter = document.getElementById("group-theme-filter") ? document.getElementById("group-theme-filter").value : "";

  let url = "/groups?";
  if (searchQuery) url += `search=${encodeURIComponent(searchQuery)}&`;
  if (themeFilter) url += `theme=${encodeURIComponent(themeFilter)}`;

  try {
    const data = await apiFetch(url);
    const groups = data.groups || [];

    if (groups.length === 0) {
      container.innerHTML = `<p class="text-stone-500 font-bold text-xl col-span-3 text-center py-12">No community spaces match your filters.</p>`;
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
            Enter Space ↗
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
            ${isGroupAdmin ? `<span class="px-3 py-1 bg-amber-500 text-white font-black text-xs rounded-full">Space Admin</span>` : isSiteAdmin ? `<span class="px-3 py-1 bg-indigo-600 text-white font-black text-xs rounded-full">Site Admin</span>` : ""}
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
          <button onclick="toggleGroupMembership(${gid}, 'leave')" class="px-6 py-4 bg-stone-200 hover:bg-red-100 hover:text-red-700 text-stone-700 font-black text-base rounded-2xl transition touch-target">Leave Space</button>
        ` : `
          <button onclick="toggleGroupMembership(${gid}, 'join')" class="px-8 py-4 bg-teal-800 hover:bg-teal-900 text-white font-black text-xl rounded-2xl shadow-lg transition touch-target">+ Join Space Free</button>
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
    showToast("Space not found");
    navigateTo("/groups");
  }
}

async function toggleGroupMembership(gid, action) {
  try {
    await apiFetch(`/groups/${gid}/${action}`, { method: "POST" });
    showToast(action === "join" ? "🎉 You joined this space!" : "You left this space.");
    await loadQuickNavGroups();
    await loadGroupDetail(gid);
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

function switchGroupTab(tabName) {
  ["chat", "kudos", "posts", "roster", "resources"].forEach(t => {
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
  if (tabName === "kudos") renderGroupKudos();
  if (tabName === "posts") renderGroupPosts();
  if (tabName === "roster") renderGroupRoster();
  if (tabName === "resources") renderGroupResources();
}

async function renderGroupKudos() {
  const container = document.getElementById("group-kudos-list");
  if (!container || !activeGroupId) return;
  container.innerHTML = `<p class="text-stone-500 font-bold text-center py-8">Loading Kudos...</p>`;
  try {
    const data = await apiFetch(`/feed?group_id=${activeGroupId}&filter_type=KUDOS`);
    const feed = data.feed || [];
    if (feed.length === 0) {
      container.innerHTML = `<p class="text-slate-400 font-bold text-center py-8 text-base">No Kudos recognized within this space yet. Send a Kudos to a fellow member!</p>`;
      return;
    }
    container.innerHTML = feed.map(item => renderFeedCard(item, false)).join("");
  } catch (err) {
    container.innerHTML = `<p class="text-red-500 font-bold text-center py-8">Failed to load Kudos.</p>`;
  }
}

async function renderGroupPosts() {
  const container = document.getElementById("group-posts-list");
  if (!container || !activeGroupId) return;
  container.innerHTML = `<p class="text-stone-500 font-bold text-center py-8">Loading Posts...</p>`;
  try {
    const data = await apiFetch(`/feed?group_id=${activeGroupId}&filter_type=POST`);
    const feed = data.feed || [];
    if (feed.length === 0) {
      container.innerHTML = `<p class="text-slate-400 font-bold text-center py-8 text-base">No Posts shared in this space yet. Create a post tagged with this space!</p>`;
      return;
    }
    container.innerHTML = feed.map(item => renderFeedCard(item, false)).join("");
  } catch (err) {
    container.innerHTML = `<p class="text-red-500 font-bold text-center py-8">Failed to load Posts.</p>`;
  }
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

async function renderGroupResources() {
  const container = document.getElementById("group-resources-list");
  if (!container || !activeGroupData) return;

  container.className = "flex flex-col space-y-4";
  container.innerHTML = `<p class="text-stone-500 font-bold text-center py-8">Loading space resources and attachments...</p>`;

  let feedItems = [];
  try {
    const res = await apiFetch("/feed?group_id=" + activeGroupData.id);
    if (res && res.feed) {
      feedItems = res.feed;
    }
  } catch (err) {
    console.error("Failed to fetch space feed for resources:", err);
  }

  const unifiedList = [];

  // 1. Admin-curated resources
  const res_curated = activeGroupData.resources || [];
  res_curated.forEach((r, idx) => {
    const cacheKey = `group_res_${activeGroupData.id}_${idx}`;
    const filename = `resource_${activeGroupData.id}_${idx}`;
    unifiedList.push({
      url: r.url,
      cacheKey: cacheKey,
      filename: filename,
      theme: r.theme || "Community Resources",
      title: r.title || r.description || "Resource",
      description: r.description && r.description !== r.title ? r.description : "",
      meta: `Curated by ${r.added_by_name || "Admin"}`,
      isAdmin: true
    });
  });

  // 2. Post / Kudos attachments
  feedItems.forEach(item => {
    if (!item.resource_url) return;
    let urls = [];
    const resUrlStr = String(item.resource_url || "").trim();
    if (resUrlStr) {
      try {
        if (resUrlStr.startsWith("[")) {
          urls = JSON.parse(resUrlStr);
        } else {
          urls = resUrlStr.split("\n").map(u => u.trim()).filter(Boolean);
        }
      } catch (e) {
        urls = [resUrlStr];
      }
    }
    if (Array.isArray(urls)) {
      urls.forEach((u, idx) => {
        if (!u) return;
        const cacheKey = `attachment_${item.id}_${idx}`;
        const filename = `attachment_${item.id}_${idx}`;
        const isKudos = item.item_type === "KUDOS";
        const fromPrefix = isKudos ? "From kudos: " : "From post: ";
        const postTitle = item.title || (item.content ? (item.content.length > 80 ? item.content.substring(0, 80) + "..." : item.content) : "Untitled Post");
        const descText = fromPrefix + postTitle;
        const authorName = item.author_name || "Anonymous";
        const dateStr = item.created_at ? ` • ${item.created_at}` : "";
        unifiedList.push({
          url: u,
          cacheKey: cacheKey,
          filename: filename,
          theme: item.theme || (isKudos ? "Kudos Attachment" : "Post Attachment"),
          title: descText,
          description: "",
          meta: `Shared by ${authorName}${dateStr}`,
          isAdmin: false
        });
      });
    }
  });

  if (unifiedList.length === 0) {
    container.innerHTML = `<p class="text-stone-400 font-bold text-center py-8 text-lg">No resources or attachments associated with this space yet.</p>`;
    return;
  }

  window._attachmentCache = window._attachmentCache || {};

  container.innerHTML = unifiedList.map((item, idx) => {
    window._attachmentCache[item.cacheKey] = item.url;
    const descHtml = item.description ? `<p class="text-stone-600 font-medium text-sm pt-1 whitespace-pre-line break-words">${item.description}</p>` : "";
    const badgeStyle = item.isAdmin
      ? "bg-teal-50 text-teal-800 border-teal-200"
      : "bg-indigo-50 text-indigo-700 border-indigo-200";

    return `
    <div class="bg-white p-6 sm:p-7 rounded-3xl border-2 border-stone-200 shadow-sm space-y-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div class="space-y-2 flex-1 min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="px-3.5 py-1 font-black text-xs rounded-full border ${badgeStyle}">${item.theme}</span>
          <span class="text-xs font-bold text-stone-400">${item.meta}</span>
        </div>
        <h4 class="text-xl font-black text-stone-900 break-words">${item.title}</h4>
        ${descHtml}
      </div>
      <div class="flex-shrink-0">
        <button type="button" onclick="window.openAttachment(window._attachmentCache[\"${item.cacheKey}\"], \"${item.filename}\")" class="w-full sm:w-auto px-6 py-3.5 bg-stone-100 hover:bg-stone-200 text-stone-900 font-black text-center rounded-2xl border-2 border-stone-300 transition block touch-target">
          ${formatAttachmentLabel(item.url, 0, 1)}
        </button>
      </div>
    </div>
    `;
  }).join("");
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
            <h3 class="text-xl font-black text-slate-900 flex items-center space-x-2"><span>💌</span><span>Sent Space Invitations Roster</span></h3>
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
  const themeVal = document.getElementById("cgrp-theme") ? document.getElementById("cgrp-theme").value : "Mental Health";
  const themes = [themeVal];

  try {
    const data = await apiFetch("/groups", {
      method: "POST",
      body: JSON.stringify({ name, icon_url, description, themes })
    });
    closeModal("modal-create-group");
    showToast("🎉 Community Space created successfully!");
    await loadQuickNavGroups();
    navigateTo(`/group/${data.id}`);
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

/* ================= USER PROFILE ================= */

async function loadUserProfile(targetId) {
  if (!targetId || targetId === "profile" || targetId === "undefined" || targetId === "null" || targetId === "me") {
    targetId = currentUser ? currentUser.id : 1;
  }
  try {
    const data = await apiFetch(`/users/${targetId}`);
    if (!data || !data.user) return;
    activeProfileData = data;
    const u = data.user;

    const avatarEl = document.getElementById("prof-avatar");
    if (avatarEl) avatarEl.src = u.avatar_url || "";

    const unameEl = document.getElementById("prof-username");
    if (unameEl) unameEl.textContent = u.username || "";

    const emailEl = document.getElementById("prof-email");
    if (emailEl) {
      const createdStr = u.created_at ? new Date(u.created_at).toLocaleDateString() : "";
      emailEl.textContent = createdStr ? `Member since ${createdStr}` : "Member";
    }

    const bioEl = document.getElementById("prof-bio");
    if (bioEl) bioEl.textContent = u.bio ? `"${u.bio}"` : "No bio added yet.";

    const editBox = document.getElementById("prof-edit-btn-box");
    if (editBox) {
      if (currentUser && currentUser.id === u.id) {
        editBox.classList.remove("hidden");
      } else {
        editBox.classList.add("hidden");
      }
    }

    const s = data.stats || {};
    const setEl = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = (val !== undefined && val !== null) ? val : "0";
    };

    setEl("stat-kudos-received", s.kudos_received ?? 0);
    setEl("stat-avg-kudos-year", s.avg_kudos_year ?? 0.0);
    setEl("stat-kudos-given", s.kudos_given ?? 0);
    setEl("stat-unique-givers", s.unique_kudos_givers ?? s.unique_givers ?? 0);
    setEl("stat-posts-authored", s.posts_authored ?? 0);
    setEl("stat-avg-reactions", s.avg_reactions_per_post ?? s.avg_reactions ?? 0.0);

    const bannerHeading = document.getElementById("prof-banner-heading");
    if (bannerHeading) {
      if (currentUser && currentUser.id === u.id) {
        bannerHeading.textContent = "Looking for your Kudos or Posts?";
      } else {
        bannerHeading.textContent = `Looking for ${u.username}'s Kudos or Posts?`;
      }
    }

    const kudosBtn = document.getElementById("prof-open-kudos-btn");
    if (kudosBtn) {
      kudosBtn.setAttribute("onclick", `filterFeedByMyKudos('received', ${u.id})`);
    }
    const postsBtn = document.getElementById("prof-open-posts-btn");
    if (postsBtn) {
      postsBtn.setAttribute("onclick", `filterFeedByMyPosts('authored', ${u.id})`);
    }
  } catch (err) {
    console.error("loadUserProfile error:", err);
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

/* ================= EMAIL OUTBOX INSPECTOR ================= */

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

/* ================= CUSTOMER SERVICE PORTAL ================= */

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

/* ================= GAMIFICATION & MONTHLY SPOTLIGHT ================= */

async function loadSpotlightView(reqMonth = "June 2026") {
  const kGrid = document.getElementById("spotlight-kudos-grid");
  const pGrid = document.getElementById("spotlight-posts-grid");
  const rBox = document.getElementById("spotlight-res-container");
  if (!kGrid || !pGrid || !rBox) return;

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

/* ================= GROUP MEMBERS INVITATION ================= */

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
    <div onclick="selectInviteMember('${(u.email || u.username).replace(/'/g, "\\'")}')" class="px-4 py-3 hover:bg-indigo-50/80 cursor-pointer flex items-center space-x-3 transition">
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
          <span class="font-black text-xs sm:text-sm uppercase tracking-wider bg-white/25 backdrop-blur px-3.5 py-1.5 rounded-full shadow-sm">💌 You Have Pending Space Invitations!</span>
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
    showToast(isAdmin ? "✅ User promoted to space admin!" : "ℹ️ User demoted from space admin.");
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
window.handleKudosRecipientSearch = handleKudosRecipientSearch;
window.selectKudosRecipient = selectKudosRecipient;
window.togglePostSubtype = togglePostSubtype;
window.toggleCurateSubtype = toggleCurateSubtype;
window.reviewPostStep = reviewPostStep;
window.backToPostStep1 = backToPostStep1;
window.confirmPublishPost = confirmPublishPost;
window.reviewCurateStep = reviewCurateStep;
window.backToCurateStep1 = backToCurateStep1;
window.confirmSubmitCurateResources = confirmSubmitCurateResources;
window.addCurateLinkField = addCurateLinkField;
window.handleCurateFilesSelect = handleCurateFilesSelect;
window.handleInviteAutocomplete = handleInviteAutocomplete;
window.selectInviteMember = selectInviteMember;

function formatAttachmentLabel(url, idx, totalCount) {
  const count = (totalCount !== undefined && totalCount !== null && !isNaN(Number(totalCount))) ? Number(totalCount) : 1;
  let num = 1;
  if (idx !== undefined && idx !== null && !isNaN(Number(idx))) {
    num = Number(idx) + 1;
  }
  const prefix = count > 1 ? `#${num}: ` : "";

  if (!url) return `📎 ${prefix}Attached Link or File ↗`;

  const str = String(url).trim();
  if (str.toLowerCase().startsWith("data:")) {
    const mimePart = str.slice(5).split(";")[0].split(",")[0].trim().toLowerCase();
    let label = "Attached File";
    let icon = "📎";
    if (mimePart.includes("pdf")) {
      label = "PDF Document";
      icon = "📄";
    } else if (mimePart.includes("sheet") || mimePart.includes("excel") || mimePart.includes("xls") || mimePart.includes("csv") || mimePart.includes("opendocument.spreadsheet")) {
      label = "Spreadsheet";
      icon = "📊";
    } else if (mimePart.includes("presentation") || mimePart.includes("powerpoint") || mimePart.includes("ppt") || mimePart.includes("opendocument.presentation")) {
      label = "Presentation";
      icon = "📊";
    } else if (mimePart.includes("word") || mimePart.includes("msword") || mimePart.includes("officedocument") || mimePart.includes("opendocument.text") || mimePart.includes("rtf") || mimePart.includes("pages") || mimePart === "application/document") {
      label = "Word Document";
      icon = "📄";
    } else if (mimePart.startsWith("image/") || mimePart.includes("image") || mimePart.includes("png") || mimePart.includes("jpeg") || mimePart.includes("jpg") || mimePart.includes("gif") || mimePart.includes("webp") || mimePart.includes("svg") || mimePart.includes("bmp") || mimePart.includes("ico")) {
      label = "Image File";
      icon = "🖼️";
    } else if (mimePart.startsWith("audio/") || mimePart.includes("audio")) {
      label = "Audio File";
      icon = "🎵";
    } else if (mimePart.startsWith("video/") || mimePart.includes("video")) {
      label = "Video File";
      icon = "🎬";
    } else if (mimePart.includes("zip") || mimePart.includes("archive") || mimePart.includes("tar") || mimePart.includes("gzip") || mimePart.includes("compressed") || mimePart.includes("rar") || mimePart.includes("7z")) {
      label = "Archive File";
      icon = "🗜️";
    } else if (mimePart.startsWith("text/") || mimePart.includes("text") || mimePart.includes("plain") || mimePart.includes("json") || mimePart.includes("xml") || mimePart.includes("html") || mimePart.includes("md")) {
      label = "Text Document";
      icon = "📝";
    }
    return `${icon} ${prefix}${label} ↗`;
  }

  // HTTP/HTTPS or relative URL or domain string
  let cleanUrl = str.split("?")[0].split("#")[0];
  let noProto = cleanUrl.replace(/^https?:\/\//i, "").replace(/^www\./i, "").replace(/\/+$/, "");
  if (!noProto) noProto = str;

  const parts = noProto.split("/").filter(Boolean);
  const lastPart = parts[parts.length - 1] || noProto;

  let extracted = noProto;
  const knownExtRegex = /\.(pdf|doc|docx|txt|rtf|pages|odt|png|jpg|jpeg|gif|webp|svg|bmp|ico|xls|xlsx|ods|csv|ppt|pptx|odp|zip|tar|gz|rar|7z|bz2|xz|tgz|mp3|wav|ogg|flac|m4a|aac|mp4|mov|avi|mkv|webm|flv|bin|exe|json|xml|html|htm|md|log|sql|apk|jar|dmg|iso)$/i;
  const validFileRegex = /^[^\/]+\.[a-z][a-z0-9]{0,4}$/i;
  if (knownExtRegex.test(lastPart) || (parts.length > 1 && validFileRegex.test(lastPart) && !lastPart.toLowerCase().endsWith(".com") && !lastPart.toLowerCase().endsWith(".org") && !lastPart.toLowerCase().endsWith(".net") && !lastPart.toLowerCase().endsWith(".io") && !lastPart.toLowerCase().endsWith(".space") && !lastPart.toLowerCase().endsWith(".co") && !lastPart.toLowerCase().endsWith(".gov") && !lastPart.toLowerCase().endsWith(".edu"))) {
    extracted = lastPart;
  }

  if (extracted.length > 26) {
    extracted = extracted.slice(0, 23) + "...";
  }

  let icon = "🌐";
  if (/\.(pdf|doc|docx|rtf|pages|odt)$/i.test(lastPart)) {
    icon = "📄";
  } else if (/\.(png|jpg|jpeg|gif|webp|svg|bmp|ico)$/i.test(lastPart)) {
    icon = "🖼️";
  } else if (/\.(txt|md|csv|json|xml|html|htm|log)$/i.test(lastPart)) {
    icon = "📝";
  } else if (/\.(xls|xlsx|ods|csv|ppt|pptx|odp)$/i.test(lastPart)) {
    icon = "📊";
  } else if (/\.(zip|tar|gz|rar|7z|bz2|xz|tgz)$/i.test(lastPart)) {
    icon = "🗜️";
  } else if (/\.(mp3|wav|ogg|flac|m4a|aac)$/i.test(lastPart)) {
    icon = "🎵";
  } else if (/\.(mp4|mov|avi|mkv|webm|flv)$/i.test(lastPart)) {
    icon = "🎬";
  } else if (extracted === lastPart && (knownExtRegex.test(lastPart) || validFileRegex.test(lastPart))) {
    icon = "📎";
  }

  return `${icon} ${prefix}${extracted} ↗`;
}
window.formatAttachmentLabel = formatAttachmentLabel;

function openAttachment(url, filename) {
  if (!url) return;
  let targetUrl = url;
  try {
    const strUrl = String(url).trim();
    if (strUrl.toLowerCase().startsWith("data:")) {
      const commaIdx = strUrl.indexOf(",");
      if (commaIdx !== -1) {
        const header = strUrl.slice(0, commaIdx);
        const base64Data = strUrl.slice(commaIdx + 1);
        let mimeType = "application/octet-stream";
        const mimeMatch = header.match(/^data:([^;,]+)/i);
        if (mimeMatch && mimeMatch[1] && mimeMatch[1].trim()) {
          mimeType = mimeMatch[1].trim();
        }
        if (/;base64/i.test(header) || header.toLowerCase().includes(";base64")) {
          const cleanBase64 = base64Data.replace(/\s+/g, '');
          const byteString = atob(cleanBase64);
          const ab = new ArrayBuffer(byteString.length);
          const ia = new Uint8Array(ab);
          for (let i = 0; i < byteString.length; i++) {
            ia[i] = byteString.charCodeAt(i);
          }
          const blob = new Blob([ab], { type: mimeType });
          targetUrl = URL.createObjectURL(blob);
        }
      }
    }
  } catch (e) {
    targetUrl = url;
  }
  const win = window.open(targetUrl, '_blank');
  if (win) {
    win.focus();
  } else {
    window.location.href = targetUrl;
  }
}
window.openAttachment = openAttachment;

function toggleMobileMenu() {
  const menu = document.getElementById("mobile-menu");
  if (menu) menu.classList.toggle("hidden");
}

function closeMobileMenu() {
  const menu = document.getElementById("mobile-menu");
  if (menu) menu.classList.add("hidden");
}

window.presetLogin = presetLogin;
window.handleLogin = handleLogin;
window.handleSignup = handleSignup;
window.logout = logout;
window.selectAvatar = selectAvatar;
window.handleGiveKudos = handleGiveKudos;
window.handleCreateGroup = handleCreateGroup;
window.handleProfileUpdate = handleProfileUpdate;
window.handleSupportSubmit = handleSupportSubmit;
window.handleGroupInviteSubmit = handleGroupInviteSubmit;
window.filterGroupsTheme = filterGroupsTheme;
window.switchGroupTab = switchGroupTab;
window.sendGroupChat = sendGroupChat;
window.openEditProfileModal = openEditProfileModal;
window.loadOutbox = loadOutbox;
window.browseSourceFile = browseSourceFile;
window.loadSpotlightView = loadSpotlightView;
window.toggleMobileMenu = toggleMobileMenu;
window.closeMobileMenu = closeMobileMenu;
window.openGroupInviteModal = openGroupInviteModal;
window.toggleGroupMembership = toggleGroupMembership;
window.toggleMemberRole = toggleMemberRole;
window.loadMoreLandingPreview = loadMoreLandingPreview;
window.loadMoreFeed = loadMoreFeed;
window.respondGroupInvite = respondGroupInvite;
window.showView = showView;
window.hideAllViews = hideAllViews;
window.addPostLinkField = addPostLinkField;
window.handlePostFilesSelect = handlePostFilesSelect;
