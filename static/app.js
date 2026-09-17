/* gooddeeds.space Client-Side Vanilla JS SPA Controller */

function escapeHtml(unsafeStr) {
  if (unsafeStr === null || unsafeStr === undefined) return "";
  return String(unsafeStr)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
window.escapeHtml = escapeHtml;

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
let currentFormatFilter = "";
let currentGroupFilter = "";
let currentSortMode = "recent";
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

let landingGroupFilter = "";
let landingTypeFilter = "";
let landingThemeFilter = "";
let landingFormatFilter = "";
let allGroupsCache = [];

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
  try {
    loadPlatformStats();
  } catch (err) {
    console.error("Platform stats init error:", err);
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

  // Close Quick Nav and Profile dropdowns when clicking outside
  document.addEventListener("click", (e) => {
    const quickContainer = document.getElementById("quick-nav-container");
    if (quickContainer && !quickContainer.contains(e.target)) {
      const dropdown = quickContainer.querySelector("div");
      if (dropdown) dropdown.classList.add("hidden");
    }
    const profileContainer = document.getElementById("profile-menu-container");
    if (profileContainer && !profileContainer.contains(e.target)) {
      closeProfileDropdown();
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

  const profileMenuBtn = document.getElementById("profile-menu-btn");
  if (profileMenuBtn) {
    profileMenuBtn.addEventListener("click", (e) => {
      toggleProfileDropdown(e);
    });
  }

  // Passkey Event Listeners
  const regBtn = document.getElementById("btn-register-passkey");
  if (regBtn) {
    regBtn.addEventListener("click", registerPasskey);
  }

  document.querySelectorAll(".btn-passkey-login").forEach(btn => {
    btn.addEventListener("click", loginWithPasskey);
  });
}

function trackAnalyticsPageView(pagePath) {
  if (typeof window.gtag === "function") {
    window.gtag("event", "page_view", {
      page_path: pagePath || "/",
      page_location: window.location.href,
      page_title: document.title
    });
  }
}

function trackAnalyticsEvent(eventName, eventParams = {}) {
  if (typeof window.gtag === "function") {
    window.gtag("event", eventName, eventParams);
  }
}
window.trackAnalyticsPageView = trackAnalyticsPageView;
window.trackAnalyticsEvent = trackAnalyticsEvent;

async function handleRoute() {
  await sessionPromise;
  const hash = window.location.hash || "#/";
  const path = hash.replace("#", "").split("?")[0];

  trackAnalyticsPageView(path);
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
    populateGroupFilterDropdown();
    loadPlatformStats();
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
  } else if (path === "/moderation") {
    showView("view-moderation");
    loadModerationQueue();
  } else if (path === "/code" || path === "/source" || path === "/browse") {
    showView("view-code");
    browseSourceFile("server.py");
  } else if (path === "/spotlight" || path === "/gamification" || path === "/halloffame") {
    // Hall of fame / spotlight view is hidden for now; redirect to feed
    window.location.hash = "#/feed";
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
  const views = ["view-landing", "view-feed", "view-single-item", "view-groups", "view-group-detail", "view-profile", "view-outbox", "view-moderation", "view-code", "view-spotlight"];
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
    if (modalId === "modal-login" || modalId === "modal-signup") {
      adjustPasskeyButtonsSupport();
    }
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
  
  const activeDialog = document.querySelector("dialog[open]");
  if (activeDialog) {
    activeDialog.appendChild(toast);
  } else {
    document.body.appendChild(toast);
  }

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

  if (options.body && typeof options.body === 'object' && !(options.body instanceof Blob) && !(options.body instanceof FormData)) {
    options.body = JSON.stringify(options.body);
  }

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
  const mobileActions = document.getElementById("mobile-auth-actions");
  const mobileMenuActions = document.getElementById("mobile-menu-auth-actions");
  if (!guestBox || !userBox) return;

  const modLink = document.getElementById("nav-moderation-link");
  if (user) {
    guestBox.classList.add("hidden");
    userBox.classList.remove("hidden");
    if (mobileActions) mobileActions.classList.remove("hidden");
    if (mobileMenuActions) mobileMenuActions.classList.remove("hidden");
    if (modLink) {
      if (user.is_site_admin === 1) modLink.classList.remove("hidden");
      else modLink.classList.add("hidden");
    }
    document.getElementById("nav-user-name").textContent = user.username;
    document.getElementById("nav-user-avatar").src = user.avatar_url;
    currentGroupFilter = "my_spaces";
    loadNotifications(false);
    startNotificationsPolling();
  } else {
    guestBox.classList.remove("hidden");
    userBox.classList.add("hidden");
    if (mobileActions) mobileActions.classList.add("hidden");
    if (mobileMenuActions) mobileMenuActions.classList.add("hidden");
    if (modLink) modLink.classList.add("hidden");
    currentGroupFilter = "";
    stopNotificationsPolling();
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

async function triggerGoogleSignIn() {
  if (window.google && google.accounts && google.accounts.id) {
    google.accounts.id.prompt();
  } else {
    const token = prompt("Enter Google ID Token for local testing:");
    if (token) {
      handleGoogleOauthResponse({ credential: token });
    }
  }
}

async function handleGoogleOauthResponse(response) {
  try {
    const tokenStr = response.credential || response.id_token;
    if (!tokenStr) return;
    const data = await apiFetch("/auth/oauth/google", {
      method: "POST",
      body: { credential: tokenStr }
    });
    if (data && data.token && data.user) {
      closeModal('modal-login');
      closeModal('modal-signup');
      currentToken = data.token;
      localStorage.setItem("gd_token", currentToken);
      currentUser = data.user;
      if (typeof sessionPromise !== "undefined") {
        sessionPromise = Promise.resolve();
      }
      updateAuthUI(currentUser);
      showToast("Welcome, " + currentUser.username + "!");
      if (typeof loadQuickNavGroups === "function") {
        await loadQuickNavGroups();
      }
      navigateTo("/feed");
    }
  } catch (err) {
    showToast("❌ " + (err.message || "Google Sign-In failed"));
  }
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
  const authorName = escapeHtml(item.author_name || "Anonymous");
  const recipientName = escapeHtml(item.recipient_name || "Community Member");
  const isKudos = item.item_type === "KUDOS";
  const cardClass = isKudos ? "kudos-card border-l-8 border-amber-500" : "post-card border-l-8 border-teal-600";
  const itemLink = isKudos ? `/#/kudos/${item.id}` : `/#/post/${item.id}`;
  
  // Groups badges
  const groupBadges = (item.groups || []).map(g => `
    <a href="/#/group/${g.id}" class="inline-flex items-center px-3 py-1 rounded-full text-xs font-black bg-stone-200 hover:bg-stone-300 text-stone-800 transition">
      👥 ${escapeHtml(g.name)}
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
  const commentsHtml = (item.comments || []).map(c => {
    const canDeleteComment = currentUser && (currentUser.id === c.user_id || currentUser.is_site_admin === 1 || currentUser.id === item.author_id);
    const canReportComment = currentUser && currentUser.id !== c.user_id;
    return `
    <div class="bg-stone-50 p-4 rounded-2xl border border-stone-200 flex items-start space-x-3 text-base">
      <img src="${escapeHtml(c.author_avatar)}" alt="${escapeHtml(c.author_name)}" class="w-9 h-9 rounded-full object-cover border border-stone-300 shrink-0">
      <div class="flex-1 overflow-hidden">
        <div class="flex justify-between items-baseline">
          <a href="/#/user/${encodeURIComponent(c.author_name || '')}" class="font-black text-stone-900 hover:underline truncate">${escapeHtml(c.author_name)}</a>
          <div class="flex items-center space-x-2 shrink-0 pl-2">
            <span class="text-xs text-stone-400 font-bold">${escapeHtml(c.created_at)}</span>
            ${canReportComment ? `<button type="button" onclick="openReportModal('COMMENT', ${c.id})" class="text-xs text-stone-400 hover:text-amber-700 font-bold" title="Report comment">🚩</button>` : ""}
            ${canDeleteComment ? `<button type="button" onclick="deleteComment(${c.id}, ${item.id})" class="text-xs text-stone-400 hover:text-red-600 font-bold" title="Delete comment">🗑️</button>` : ""}
          </div>
        </div>
        <p class="text-stone-800 pt-0.5 font-medium whitespace-pre-line">${escapeHtml(c.content)}</p>
      </div>
    </div>
  `;
  }).join("");

  const isExpanded = expandedThreads.has(item.id);
  const commentsBoxClass = isExpanded 
    ? "space-y-3.5 pt-2.5 border-t border-stone-200/40" 
    : "space-y-3.5 hidden pt-2.5 border-t border-stone-200/40";
  const commentsCount = (item.comments || []).length;
  const toggleIconText = isExpanded 
    ? (commentsCount > 0 ? "▲ Hide Thread" : "▲ Hide Reply")
    : (commentsCount > 0 ? "▼ Show Thread" : "▼ Write Reply");

  const postSubtypeBadge = (!isKudos)
    ? ((item.post_subtype === "EVENT" || item.event_date)
        ? `<span class="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider bg-rose-50 text-rose-800 border border-rose-200 shadow-xs">📅 Event Post</span>`
        : ((item.post_subtype === "RESOURCE" || item.resource_url)
            ? `<span class="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider bg-teal-50 text-teal-800 border border-teal-200 shadow-xs">📚 Resource Post</span>`
            : `<span class="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider bg-indigo-50 text-indigo-800 border border-indigo-200 shadow-xs">📝 Community Post</span>`))
    : `<span class="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs font-extrabold uppercase tracking-wider bg-amber-200/80 text-amber-950 border border-amber-400 shadow-xs">🌟 Gratitude Kudos</span>`;

  return `
    <article class="bg-white rounded-3xl border border-slate-200/80 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 p-6 sm:p-8 space-y-5 ${cardClass}">
      
      <!-- Card Type Ribbon & Space Badges -->
      <div class="flex flex-wrap items-center justify-between gap-2 pb-2 border-b ${isKudos ? 'border-amber-200/60' : 'border-slate-100'}">
        <div class="flex items-center gap-2 flex-wrap">
          ${postSubtypeBadge}
          ${!isKudos && item.theme ? `<span class="px-2.5 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-full text-xs font-bold">🏷️ ${escapeHtml(item.theme)}</span>` : ""}
        </div>
        <div class="flex flex-wrap gap-1.5">${groupBadges}</div>
      </div>

      <!-- Author & Recipient Banner -->
      <div class="flex flex-wrap justify-between items-center gap-4">
        <div class="flex items-center space-x-3.5">
          ${isKudos ? `
            <a href="/#/user/${item.recipient_id}" class="relative shrink-0">
              <img src="${escapeHtml(item.recipient_avatar || item.author_avatar)}" alt="${recipientName}" class="w-12 h-12 rounded-full object-cover border-2 border-amber-500 shadow-sm">
              <span class="absolute -bottom-1 -right-1 text-sm bg-amber-400 text-white rounded-full w-5 h-5 flex items-center justify-center shadow" title="Kudos Recipient">🌟</span>
            </a>
            <div>
              <div class="text-lg font-bold text-slate-900 flex items-center flex-wrap gap-1.5">
                <a href="/#/user/${item.recipient_id}" class="hover:text-amber-700 transition font-extrabold text-slate-900">${recipientName}</a>
                <span class="text-amber-700 font-extrabold text-base">received Kudos from</span>
                <a href="/#/user/${item.author_id}" class="hover:underline font-bold text-amber-950 bg-amber-100/80 border border-amber-300 px-3 py-0.5 rounded-full text-sm">${authorName}</a>
              </div>
              <div class="text-xs text-slate-500 font-medium pt-0.5">
                <span>⏱️ ${escapeHtml(item.created_at)}</span>
                <span class="px-2">•</span>
                <a href="${itemLink}" class="text-slate-500 hover:text-amber-700 transition">Direct Share Link ↗</a>
              </div>
            </div>
          ` : `
            <a href="/#/user/${item.author_id}" class="shrink-0">
              <img src="${escapeHtml(item.author_avatar)}" alt="${authorName}" class="w-12 h-12 rounded-full object-cover border border-slate-200 shadow-sm">
            </a>
            <div>
              <div class="text-lg font-bold text-slate-900 flex items-center flex-wrap gap-1.5">
                <a href="/#/user/${item.author_id}" class="hover:text-indigo-600 transition">${authorName}</a>
                <span class="text-xs text-slate-400 font-semibold">shared a post</span>
              </div>
              <div class="text-xs text-slate-400 font-medium pt-0.5">
                <span>⏱️ ${escapeHtml(item.created_at)}</span>
                <span class="px-2">•</span>
                <a href="${itemLink}" class="text-slate-400 hover:text-indigo-600 transition">Direct Share Link ↗</a>
              </div>
            </div>
          `}
        </div>
      </div>

      <!-- Main Body Content -->
      <div class="space-y-3">
        ${!isKudos && item.title ? `<h2 class="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight"><a href="${itemLink}" class="hover:text-indigo-600 transition">${escapeHtml(item.title)}</a></h2>` : ""}
        ${isKudos ? `
          <div class="bg-amber-100/40 border border-amber-300/80 rounded-2xl p-4 sm:p-5 text-slate-900 text-lg whitespace-pre-line font-semibold leading-relaxed shadow-xs">
            <span class="text-amber-500 font-serif text-2xl leading-none select-none mr-1">“</span>${escapeHtml(item.content)}<span class="text-amber-500 font-serif text-2xl leading-none select-none ml-1">”</span>
          </div>
        ` : `
          <p class="text-slate-700 text-lg whitespace-pre-line font-medium leading-relaxed">${escapeHtml(item.content)}</p>
        `}
        
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
      <div class="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-stone-100">
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-xs font-black text-stone-400 uppercase tracking-wider pr-1">Celebrate:</span>
          ${reactionsHtml}
        </div>
        ${currentUser && currentUser.id !== item.author_id ? `
          <button type="button" onclick="openReportModal('${isKudos ? 'KUDOS' : 'POST'}', ${item.id})" class="text-xs font-bold text-stone-400 hover:text-amber-700 px-2.5 py-1 rounded-lg hover:bg-stone-100 transition flex items-center space-x-1" title="Report content">
            <span>🚩</span><span>Report</span>
          </button>
        ` : ""}
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

async function loadPlatformStats() {
  try {
    const res = await apiFetch("/stats");
    if (res && res.success && res.stats) {
      const elActs = document.getElementById("stat-acts-of-kindness");
      const elMembers = document.getElementById("stat-community-members");
      const elSpaces = document.getElementById("stat-active-spaces");
      if (elActs && res.stats.acts_of_kindness !== undefined) {
        elActs.textContent = Number(res.stats.acts_of_kindness).toLocaleString();
      }
      if (elMembers && res.stats.community_members !== undefined) {
        elMembers.textContent = Number(res.stats.community_members).toLocaleString();
      }
      if (elSpaces && res.stats.active_spaces !== undefined) {
        elSpaces.textContent = Number(res.stats.active_spaces).toLocaleString();
      }
    }
  } catch (err) {
    console.warn("Could not load dynamic platform stats, keeping default fallbacks.", err);
    const elActs = document.getElementById("stat-acts-of-kindness");
    const elMembers = document.getElementById("stat-community-members");
    const elSpaces = document.getElementById("stat-active-spaces");
    if (elActs && (!elActs.textContent.trim() || elActs.textContent === "...")) elActs.textContent = "0";
    if (elMembers && (!elMembers.textContent.trim() || elMembers.textContent === "...")) elMembers.textContent = "0";
    if (elSpaces && (!elSpaces.textContent.trim() || elSpaces.textContent === "...")) elSpaces.textContent = "0";
  }
}
window.loadPlatformStats = loadPlatformStats;

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

  let url = `/feed?sort=recent&limit=${reqLimit}&offset=${reqOffset}&`;
  if (landingGroupFilter) url += `group_id=${encodeURIComponent(landingGroupFilter)}&`;
  if (landingTypeFilter) url += `filter_type=${encodeURIComponent(landingTypeFilter)}&`;
  if (landingThemeFilter) url += `theme=${encodeURIComponent(landingThemeFilter)}&`;
  if (landingFormatFilter) url += `subtype=${encodeURIComponent(landingFormatFilter)}&`;

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
  if (currentFormatFilter) url += `subtype=${encodeURIComponent(currentFormatFilter)}&`;
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
        let emptyTitle = "No Posts or Kudos Found";
        let emptySubtitle = "No posts or kudos match your active filter selection.";
        if (currentTypeFilter === "KUDOS") {
          emptyTitle = "No Kudos Found";
          emptySubtitle = "No gratitude kudos match your active filter selection.";
        } else if (currentTypeFilter === "POST") {
          emptyTitle = "No Posts Found";
          emptySubtitle = "No community posts match your active filter selection.";
        }
        container.innerHTML = `
          <div class="bg-white p-12 rounded-3xl border border-slate-200 text-center space-y-3">
            <div class="text-5xl">🕊️</div>
            <h3 class="text-2xl font-bold text-slate-800">${emptyTitle}</h3>
            <p class="text-base text-slate-500 font-medium">${emptySubtitle}</p>
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
  if (th !== "" && currentTheme === th) {
    currentTheme = "";
  } else {
    currentTheme = th;
  }
  document.querySelectorAll(".theme-pill").forEach(el => {
    const onclickAttr = el.getAttribute("onclick") || "";
    if (currentTheme !== "" && onclickAttr.includes(`'${currentTheme}'`)) {
      el.className = "theme-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-amber-500 text-white shadow-sm transition touch-target";
    } else if (currentTheme === "" && onclickAttr.includes("''")) {
      el.className = "theme-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-slate-900 text-white transition touch-target shadow-sm";
    } else {
      el.className = "theme-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-white hover:bg-slate-50 text-slate-700 transition touch-target shadow-xs";
    }
  });
  updateThemePillsCollapseUI();
  loadFeed();
}

function filterByFormat(fmt) {
  if (currentFormatFilter === fmt) {
    currentFormatFilter = "";
  } else {
    currentFormatFilter = fmt;
  }
  document.querySelectorAll(".format-pill").forEach(el => {
    const onclickAttr = el.getAttribute("onclick") || "";
    if (currentFormatFilter !== "" && onclickAttr.includes(`'${currentFormatFilter}'`)) {
      el.className = "format-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-amber-500 text-white shadow-sm transition touch-target";
    } else {
      el.className = "format-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-white hover:bg-amber-100/60 text-slate-700 transition touch-target shadow-xs";
    }
  });
  updateThemePillsCollapseUI();
  loadFeed();
}
window.filterByFormat = filterByFormat;

let isThemePillsCollapsed = false;
let isLandingThemePillsCollapsed = false;

function toggleThemePillsBar(forceState) {
  if (typeof forceState === "boolean") {
    isThemePillsCollapsed = forceState;
  } else {
    isThemePillsCollapsed = !isThemePillsCollapsed;
  }
  updateThemePillsCollapseUI();
}
window.toggleThemePillsBar = toggleThemePillsBar;

function updateThemePillsCollapseUI() {
  const pillsBar = document.getElementById("theme-pills-bar");
  const toggleBtn = document.getElementById("btn-toggle-theme-pills");
  const toggleIcon = document.getElementById("theme-pills-toggle-icon");
  const indicator = document.getElementById("theme-pills-active-indicator");

  if (!pillsBar) return;

  const hasActive = Boolean(currentTheme || currentFormatFilter);

  if (isThemePillsCollapsed) {
    pillsBar.classList.add("hidden");
    if (toggleIcon) toggleIcon.textContent = "▼";
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", "false");
      if (hasActive) {
        toggleBtn.className = "px-4 py-3 rounded-xl border border-amber-400 font-bold text-sm bg-amber-50 text-amber-900 transition flex items-center justify-center space-x-2 shrink-0 touch-target shadow-xs";
      } else {
        toggleBtn.className = "px-4 py-3 rounded-xl border border-slate-300 font-bold text-sm bg-slate-50 hover:bg-slate-100 text-slate-700 transition flex items-center justify-center space-x-2 shrink-0 touch-target";
      }
    }
  } else {
    pillsBar.classList.remove("hidden");
    if (toggleIcon) toggleIcon.textContent = "▲";
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", "true");
      if (hasActive) {
        toggleBtn.className = "px-4 py-3 rounded-xl border border-amber-400 font-bold text-sm bg-amber-50 text-amber-900 transition flex items-center justify-center space-x-2 shrink-0 touch-target shadow-xs";
      } else {
        toggleBtn.className = "px-4 py-3 rounded-xl border border-slate-300 font-bold text-sm bg-white hover:bg-slate-50 text-slate-700 transition flex items-center justify-center space-x-2 shrink-0 touch-target";
      }
    }
  }

  if (indicator) {
    if (hasActive) {
      indicator.classList.remove("hidden");
    } else {
      indicator.classList.add("hidden");
    }
  }
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
  currentSortMode = mode || "recent";
  const sortSel = document.getElementById("feed-order-select");
  if (sortSel && sortSel.value !== currentSortMode) {
    sortSel.value = currentSortMode;
  }
  loadFeed();
}
window.changeSortMode = changeSortMode;

function clearAllFilters() {
  currentTheme = "";
  currentFormatFilter = "";
  currentGroupFilter = "";
  currentSortMode = "recent";
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
  const sortSel = document.getElementById("feed-order-select");
  if (sortSel) sortSel.value = "recent";
  document.querySelectorAll(".format-pill").forEach(el => {
    el.className = "format-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-white hover:bg-amber-100/60 text-slate-700 transition touch-target shadow-xs";
  });
  filterByTheme("");
}

async function populateGroupFilterDropdown() {
  const sel = document.getElementById("feed-group-select");
  const landingSel = document.getElementById("landing-group-select");
  if (!sel && !landingSel) return;
  try {
    const data = await apiFetch("/groups");
    const groups = data.groups || [];
    allGroupsCache = groups;
    if (landingSel) {
      let landingHtml = `<option value="">All Spaces</option>` +
        groups.map(g => `<option value="${g.id}">👥 ${g.name}</option>`).join("");
      landingSel.innerHTML = landingHtml;
      if (landingGroupFilter) {
        landingSel.value = landingGroupFilter;
      }
    }
    if (!sel) return;
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

function getCurrentSpaceContextId() {
  if (window.location.hash && window.location.hash.startsWith("#/group/")) {
    const raw = window.location.hash.replace("#/group/", "").split("/")[0].split("?")[0];
    const id = parseInt(raw);
    if (!isNaN(id)) return id;
  }
  if (typeof activeGroupId !== "undefined" && activeGroupId) {
    const id = parseInt(activeGroupId);
    if (!isNaN(id)) return id;
  }
  if (typeof activeGroupData !== "undefined" && activeGroupData && activeGroupData.id) {
    return parseInt(activeGroupData.id);
  }
  return null;
}

/* Give Kudos Modal Autocomplete (Req #4) */
async function populateKudosModal() {
  const recipInput = document.getElementById("kudos-recipient-input");
  const recipIdHidden = document.getElementById("kudos-recipient-id");
  if (recipInput) recipInput.value = "";
  if (recipIdHidden) recipIdHidden.value = "";
  const container = document.getElementById("kudos-groups-list");
  const currentSpaceId = getCurrentSpaceContextId();
  const spaceName = (typeof activeGroupData !== "undefined" && activeGroupData && activeGroupData.name) ? activeGroupData.name : "this Space";
  if (container) {
    if (currentSpaceId) {
      container.innerHTML = `<p class="text-stone-500 font-medium text-sm p-2">Select a recipient to tag <strong>${spaceName}</strong>.</p>`;
    } else {
      container.innerHTML = `<p class="text-stone-500 font-medium text-sm p-2">Select a recipient to see shared groups.</p>`;
    }
  }

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
function presetKudosRecipient(id, username, email = "") {
  selectKudosRecipient(id, username, email);
  setTimeout(() => {
    selectKudosRecipient(id, username, email);
  }, 50);
}
window.handleKudosRecipientSearch = handleKudosRecipientSearch;
window.selectKudosRecipient = selectKudosRecipient;
window.presetKudosRecipient = presetKudosRecipient;

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
  const currentSpaceId = getCurrentSpaceContextId();
  if (!targetId) {
    const spaceName = (typeof activeGroupData !== "undefined" && activeGroupData && activeGroupData.name) ? activeGroupData.name : "this Space";
    if (currentSpaceId) {
      container.innerHTML = `<p class="text-stone-500 font-medium text-sm p-2">Select a recipient to tag <strong>${spaceName}</strong>.</p>`;
    } else {
      container.innerHTML = `<p class="text-stone-500 font-medium text-sm p-2">Select a recipient to see shared groups.</p>`;
    }
    return;
  }
  try {
    const data = await apiFetch(`/groups/joined?target_user_id=${targetId}`);
    const groups = data.groups || [];
    if (groups.length === 0) {
      container.innerHTML = `<p class="text-stone-500 font-medium text-sm p-2">You and this member do not share any common groups yet.</p>`;
    } else {
      container.innerHTML = groups.map(g => {
        const isChecked = (currentSpaceId && parseInt(currentSpaceId) === g.id) ? "checked" : "";
        return `
          <label class="inline-flex items-center space-x-2 px-3 py-2 rounded-xl bg-white border-2 border-stone-200 font-bold text-sm cursor-pointer hover:bg-amber-50 hover:border-amber-400 transition touch-target">
            <input type="checkbox" name="kudos-group" value="${g.id}" ${isChecked} class="w-5 h-5 text-amber-600 rounded">
            <span>${g.name}</span>
          </label>
        `;
      }).join("");
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
    trackAnalyticsEvent("give_kudos", { recipient_id });
    document.getElementById("kudos-content").value = "";
    document.getElementById("kudos-recipient-input").value = "";
    document.getElementById("kudos-recipient-id").value = "";
    showToast("🌟 Public Kudos sent & email alert triggered!");
    if (window.location.hash.startsWith("#/group/")) {
      loadGroupDetail(activeGroupId);
    } else if (window.location.hash.includes("/feed") || window.location.hash === "#/") {
      loadFeed();
    } else {
      navigateTo("/feed");
    }
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
  await populateGroupCheckboxes("post-groups-list", "post-group");
  const defaultSubtypeRadio = document.querySelector("input[name='post_subtype'][value='GENERAL'], input[name='post-subtype'][value='General Post'], input[name='post_subtype'][value='GENERAL']");
  if (defaultSubtypeRadio) {
    defaultSubtypeRadio.checked = true;
    togglePostSubtype(defaultSubtypeRadio.value);
  }
  const currentSpaceId = getCurrentSpaceContextId();
  if (currentSpaceId && typeof activeGroupData !== "undefined" && activeGroupData) {
    const spaceTheme = activeGroupData.theme || (activeGroupData.themes && activeGroupData.themes[0]);
    const themeSelect = document.getElementById("post-input-theme");
    if (spaceTheme && themeSelect) {
      for (const opt of themeSelect.options) {
        if (opt.value === spaceTheme) {
          themeSelect.value = spaceTheme;
          break;
        }
      }
    }
  }
}

async function populateGroupCheckboxes(containerId, inputName) {
  const container = document.getElementById(containerId);
  if (!container) return;
  try {
    const data = await apiFetch("/groups");
    const currentSpaceId = getCurrentSpaceContextId();
    container.innerHTML = (data.groups || []).map(g => {
      const isChecked = (currentSpaceId && parseInt(currentSpaceId) === g.id) ? "checked" : "";
      return `
        <label class="inline-flex items-center space-x-2 px-3 py-2 rounded-xl bg-white border-2 border-stone-200 font-bold text-sm cursor-pointer hover:bg-amber-50 hover:border-amber-400 transition touch-target">
          <input type="checkbox" name="${inputName}" value="${g.id}" ${isChecked} class="w-5 h-5 text-amber-600 rounded">
          <span>${g.name}</span>
        </label>
      `;
    }).join("");
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
      if (dataUrl) {
        const enrichedUrl = file.name ? dataUrl.replace(/^data:([^;,]+)/, `data:$1;name=${encodeURIComponent(file.name)}`) : dataUrl;
        attachments.push(enrichedUrl);
      }
    } catch(err) {}
  }

  const resource_url = attachments.length > 0 ? JSON.stringify(attachments) : "";

  draftPost = { title, theme, content, resource_url, group_ids };

  document.getElementById("post-step-1").classList.add("hidden");
  document.getElementById("post-step-2").classList.remove("hidden");

  const previewBox = document.getElementById("post-preview-card");
  const attachmentsPreviewHtml = attachments.length > 0 ? `
    <div id="confirm-post-attachments" class="pt-3 border-t border-slate-200/80 space-y-2">
      <div class="font-extrabold text-indigo-900 text-xs uppercase tracking-wider">📎 Attached Links & Files (${attachments.length}) — Click to Preview & Validate:</div>
      <div class="flex flex-col gap-2">
        ${attachments.map((u, idx) => {
          const previewKey = `preview_attachment_${idx}`;
          window._attachmentCache[previewKey] = u;
          const isDataUri = String(u).startsWith("data:");
          const displayLabel = isDataUri
            ? formatAttachmentLabel(u, idx, attachments.length)
            : `🔗 ${escapeHtml(u)}`;
          return `
            <button type="button" onclick="window.openAttachment(window._attachmentCache['${previewKey}'], '${previewKey}')" class="w-full text-left flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl bg-white hover:bg-indigo-50 text-indigo-700 hover:text-indigo-900 font-bold text-sm border border-indigo-200 shadow-xs transition touch-target">
              <span class="truncate underline">${displayLabel}</span>
              <span class="shrink-0 text-xs font-extrabold bg-indigo-100 text-indigo-800 px-2.5 py-1 rounded-lg">Open to Verify ↗</span>
            </button>
          `;
        }).join("")}
      </div>
    </div>
  ` : "";

  previewBox.innerHTML = `
    <div class="font-extrabold text-2xl text-slate-900 tracking-tight">${escapeHtml(title)}</div>
    <div class="flex flex-wrap gap-2 pt-1">
      <span class="px-3 py-1 bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full text-xs font-bold">🏷️ ${escapeHtml(theme)}</span>
      <span class="px-3 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-full text-xs font-bold">${subtype === "Community Event" ? "📅 Event" : subtype === "Community Resource" ? "📚 Resource" : "📝 Post"}</span>
    </div>
    <p class="text-base text-slate-700 pt-3 whitespace-pre-line font-medium leading-relaxed">${escapeHtml(content)}</p>
    ${attachmentsPreviewHtml}
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
    if (window.location.hash.startsWith("#/group/")) {
      loadGroupDetail(activeGroupId);
    } else {
      navigateTo("/feed");
      loadFeed();
    }
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
        const enrichedUrl = file.name ? dataUrl.replace(/^data:([^;,]+)/, `data:$1;name=${encodeURIComponent(file.name)}`) : dataUrl;
        resources.push({
          title: file.name,
          description: desc ? `${file.name} - ${desc}` : file.name,
          url: enrichedUrl,
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
    if (typeof closeModal === "function") closeModal("modal-curate-resource");
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
    allGroupsCache = groups;

    if (groups.length === 0) {
      container.innerHTML = `<p class="text-stone-500 font-bold text-xl col-span-3 text-center py-12">No community spaces match your filters.</p>`;
      return;
    }

    container.innerHTML = groups.map(g => `
      <div class="bg-white p-7 sm:p-8 rounded-3xl border border-stone-200/80 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 flex flex-col justify-between space-y-6">
        <div class="space-y-4">
          <div class="flex items-center space-x-4">
            <img src="${g.icon_url}" alt="${g.name}" class="w-16 h-16 rounded-2xl object-cover border-2 border-emerald-500 shadow-sm">
            <div>
              <h3 class="text-2xl font-black text-stone-900 leading-tight">${g.name}</h3>
              <span class="text-xs font-bold text-stone-400">👥 ${g.member_count} active members</span>
            </div>
          </div>
          <p class="text-stone-600 font-medium text-base leading-relaxed">${g.description}</p>
          <div class="flex flex-wrap gap-1.5 pt-1">
            ${(g.themes || []).map(t => `<span class="px-3 py-1 bg-amber-50 text-amber-900 border border-amber-200/60 font-bold text-xs rounded-full">${t}</span>`).join("")}
          </div>
        </div>

        <div class="pt-2 flex items-center justify-between gap-3">
          <a href="/#/group/${g.id}" class="flex-1 py-3.5 bg-gradient-to-r from-emerald-600 to-teal-700 hover:from-emerald-700 hover:to-teal-800 text-white font-black text-center rounded-full shadow-sm transition touch-target block">
            Enter Space ↗
          </a>
          ${g.is_joined ? `
            <span class="px-4 py-3.5 bg-emerald-50 text-emerald-800 font-black text-xs rounded-full border border-emerald-200 flex items-center">Joined ✅</span>
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

    const memberCount = (activeGroupData.members && activeGroupData.members.length) || activeGroupData.member_count || activeGroupData.members_count || 0;
    const memberBtnText = memberCount > 0 ? `Members List (${memberCount})` : `Members List`;

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

      <div class="pt-4 md:pt-0 shrink-0 flex flex-wrap sm:flex-row gap-3 items-center justify-end">
        <button type="button" id="btn-space-members-link" onclick="switchGroupTab('roster')" class="px-6 py-3.5 bg-stone-100 hover:bg-amber-100/80 text-stone-800 hover:text-amber-950 border border-stone-300 font-black text-sm rounded-2xl shadow-xs transition touch-target flex items-center space-x-2">
          <span>👥</span>
          <span>${memberBtnText}</span>
        </button>
        ${!currentUser ? `
          <button onclick="openModal('modal-login')" class="px-8 py-4 bg-amber-600 hover:bg-amber-700 text-white font-black text-lg rounded-2xl shadow transition touch-target">Log In to Join</button>
        ` : isMember ? `
          <button onclick="openGroupInviteModal()" class="px-6 py-3.5 bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-sm rounded-2xl shadow transition touch-target flex items-center space-x-2"><span>💌</span><span>Invite Others to Join</span></button>
          <button id="btn-leave-space" onclick="toggleGroupMembership(${gid}, 'leave')" class="px-4 py-2 bg-stone-100 hover:bg-red-50 text-stone-500 hover:text-red-700 border border-stone-200 hover:border-red-200 font-bold text-xs rounded-xl transition touch-target">Leave Space</button>
        ` : `
          <button onclick="toggleGroupMembership(${gid}, 'join')" class="px-8 py-3.5 bg-teal-800 hover:bg-teal-900 text-white font-black text-base rounded-2xl shadow-lg transition touch-target">+ Join Space Free</button>
        `}
      </div>
    `;

    // Admin resource curation form is kept hidden from space tab view
    const curateBox = document.getElementById("admin-curate-box");
    if (curateBox) {
      curateBox.classList.add("hidden");
    }

    if (typeof renderGroupCalendar === "function") renderGroupCalendar();
    if (typeof updateCalendarCollapseUI === "function") updateCalendarCollapseUI();
    switchGroupTab("chat");
  } catch (err) {
    showToast("Space not found");
    navigateTo("/groups");
  }
}

async function toggleGroupMembership(gid, action) {
  if (action === "leave") {
    const spaceName = (activeGroupData && activeGroupData.name) ? ` "${activeGroupData.name}"` : " this space";
    if (!confirm(`Are you sure you want to leave${spaceName}?`)) {
      return;
    }
  }
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
    if (box) {
      if (t === tabName) box.classList.remove("hidden");
      else box.classList.add("hidden");
    }
    if (btn) {
      if (t === tabName) {
        btn.className = "gtab-btn px-8 py-4 font-black text-xl border-b-4 border-amber-600 text-amber-800 transition touch-target shrink-0";
      } else {
        btn.className = "gtab-btn px-8 py-4 font-black text-xl border-b-4 border-transparent text-stone-500 hover:text-stone-800 transition touch-target shrink-0";
      }
    }
  });

  const membersHeaderBtn = document.getElementById("btn-space-members-link");
  if (membersHeaderBtn) {
    if (tabName === "roster") {
      membersHeaderBtn.className = "px-6 py-3.5 bg-amber-500 text-white border border-amber-600 font-black text-sm rounded-2xl shadow-sm transition touch-target flex items-center space-x-2";
    } else {
      membersHeaderBtn.className = "px-6 py-3.5 bg-stone-100 hover:bg-amber-100/80 text-stone-800 hover:text-amber-950 border border-stone-300 font-black text-sm rounded-2xl shadow-xs transition touch-target flex items-center space-x-2";
    }
  }

  if (tabName === "chat") renderGroupChatList();
  if (tabName === "kudos") renderGroupKudos();
  if (tabName === "posts") renderGroupPosts();
  if (tabName === "roster") renderGroupRoster();
  if (tabName === "resources") renderGroupResources();
}

async function renderGroupKudos() {
  const container = document.getElementById("group-kudos-list");
  if (!container || !activeGroupId) return;
  const parent = container.parentNode;
  if (parent) {
    let banner = document.getElementById("group-kudos-creation-banner");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "group-kudos-creation-banner";
      parent.insertBefore(banner, container);
    }
    const spaceName = activeGroupData ? activeGroupData.name : 'this space';
    banner.className = "bg-gradient-to-r from-amber-500/10 via-white to-amber-500/10 p-6 rounded-3xl border border-amber-200/80 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4 mb-6";
    banner.innerHTML = `
      <div class="space-y-1 text-center sm:text-left">
        <h3 class="text-lg font-black text-slate-900">Recognize Space Members</h3>
        <p class="text-sm font-medium text-slate-600">Celebrate contributions and kindness within ${spaceName}.</p>
      </div>
      <button onclick="openModal('modal-kudos')" class="px-6 py-3 rounded-2xl font-black text-sm bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-white shadow-md transition touch-target flex items-center space-x-2 shrink-0">
        <span>✨ + Give Space Kudos</span>
      </button>
    `;
  }
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
  const parent = container.parentNode;
  if (parent) {
    let banner = document.getElementById("group-posts-creation-banner");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "group-posts-creation-banner";
      parent.insertBefore(banner, container);
    }
    const spaceName = activeGroupData ? activeGroupData.name : 'this space';
    banner.className = "bg-gradient-to-r from-indigo-600/10 via-white to-indigo-600/10 p-6 rounded-3xl border border-indigo-200/80 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4 mb-6";
    banner.innerHTML = `
      <div class="space-y-1 text-center sm:text-left">
        <h3 class="text-lg font-black text-slate-900">Share with Space Members</h3>
        <p class="text-sm font-medium text-slate-600">Post discussions, stories, or events to ${spaceName}.</p>
      </div>
      <button onclick="openModal('modal-post')" class="px-6 py-3 rounded-2xl font-black text-sm bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-700 hover:to-violet-700 text-white shadow-md transition touch-target flex items-center space-x-2 shrink-0">
        <span>✍️ + Share Space Post</span>
      </button>
    `;
  }
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
  const isGroupAdmin = currentUser && (currentUser.is_site_admin === 1 || activeGroupData.is_admin);
  container.innerHTML = msgs.map(m => {
    const canDeleteMsg = currentUser && (currentUser.id === m.user_id || isGroupAdmin);
    const canReportMsg = currentUser && currentUser.id !== m.user_id;
    return `
    <div class="bg-white p-5 sm:p-6 rounded-2xl border border-slate-200/80 shadow-sm flex items-start space-x-3.5">
      <img src="${escapeHtml(m.author_avatar)}" alt="${escapeHtml(m.author_name)}" class="w-10 h-10 rounded-full object-cover border border-slate-200 shrink-0">
      <div class="flex-1 min-w-0">
        <div class="flex justify-between items-baseline mb-1">
          <strong class="text-sm font-bold text-slate-900 truncate pr-2">${escapeHtml(m.author_name)}</strong>
          <div class="flex items-center space-x-2 shrink-0">
            <span class="text-xs text-slate-400 font-medium">${escapeHtml(m.created_at)}</span>
            ${canReportMsg ? `<button type="button" onclick="openReportModal('CHAT', ${m.id})" class="text-xs text-slate-400 hover:text-amber-700 font-bold" title="Report chat message">🚩</button>` : ""}
            ${canDeleteMsg ? `<button type="button" onclick="deleteGroupChatMessage(${m.id})" class="text-xs text-slate-400 hover:text-red-600 font-bold" title="Delete chat message">🗑️</button>` : ""}
          </div>
        </div>
        <p class="text-base text-slate-800 font-normal whitespace-pre-line leading-relaxed break-words">${escapeHtml(m.message)}</p>
      </div>
    </div>
  `;
  }).join("");
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
    if (!activeGroupData.chat_messages) activeGroupData.chat_messages = [];
    activeGroupData.chat_messages.unshift(data.message);
    renderGroupChatList();
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

function formatResourceSummary(item) {
  if (!item) return "";
  let desc = String(item.description || "").trim();
  const title = String(item.title || "").trim();
  const url = String(item.url || "").trim();
  const content = String(item.content || "").trim();
  const extText = String(item.extracted_text || "").trim();

  let candidate = "";
  if (desc && desc !== title && desc !== url) {
    candidate = desc;
  } else if (extText) {
    candidate = extText;
  } else if (content) {
    candidate = content;
  }

  if (candidate) {
    let cleaned = candidate
      .replace(/%PDF-[0-9.]+/g, "")
      .replace(/stream[\s\S]*?endstream/gi, "")
      .replace(/[\[\]{}"\\]/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    if (cleaned.startsWith("From post: ")) cleaned = cleaned.substring(11).trim();
    if (cleaned.startsWith("From kudos: ")) cleaned = cleaned.substring(12).trim();

    if (cleaned.length > 180) {
      const dotIdx = cleaned.indexOf(". ", 80);
      if (dotIdx !== -1 && dotIdx < 190) {
        cleaned = cleaned.substring(0, dotIdx + 1);
      } else {
        const spaceIdx = cleaned.lastIndexOf(" ", 170);
        cleaned = (spaceIdx !== -1 ? cleaned.substring(0, spaceIdx) : cleaned.substring(0, 170)) + "...";
      }
    }
    if (cleaned.length >= 15 && /[a-zA-Z]/.test(cleaned)) {
      return cleaned;
    }
  }

  const urlLower = url.toLowerCase();
  const titleLower = title.toLowerCase();
  const theme = item.theme || "Community Resource";
  const themeLower = theme.toLowerCase();

  if (urlLower.includes("grounding") || titleLower.includes("grounding") || titleLower.includes("first aid")) {
    return "Practical grounding techniques, breathing exercises, and emotional regulation steps for managing acute anxiety.";
  }
  if (urlLower.includes("mindfulness") || titleLower.includes("mindfulness") || titleLower.includes("meditation")) {
    return "Curated online webpage offering guided mindfulness sessions, audio meditations, and daily wellness practices.";
  }
  if (urlLower.includes("resume") || titleLower.includes("resume") || titleLower.includes("career")) {
    return "Step-by-step resume building templates, career transition advice, and mentorship networking strategies.";
  }
  if (urlLower.includes("volunteer") || urlLower.includes("map") || titleLower.includes("volunteer") || titleLower.includes("mutual aid")) {
    return "Interactive community map and volunteer coordination directory for local food pantries and mutual aid.";
  }
  if (urlLower.includes("mentorship") || titleLower.includes("tutoring") || titleLower.includes("fair")) {
    return "Community event guide detailing academic tutoring tracks, volunteer schedules, and skill share sessions.";
  }
  if (urlLower.includes("kindness") || titleLower.includes("goodness") || titleLower.includes("negativity")) {
    return "Actionable strategies and community insights on fostering daily kindness, gratitude, and breaking negative cycles.";
  }

  if (url.startsWith("http://") || url.startsWith("https://")) {
    try {
      const hostname = new URL(url).hostname.replace("www.", "");
      return `Curated online web resource hosted at ${hostname} providing reference materials and guidance for ${title || theme}.`;
    } catch(e) {}
  }

  return `Helpful ${themeLower} guide and downloadable reference material for space members.`;
}
window.formatResourceSummary = formatResourceSummary;

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
      title: r.title || "Resource",
      description: r.description || "",
      extracted_text: r.extracted_text || "",
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
          content: item.content || "",
          extracted_text: item.extracted_text || "",
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
    const summary = formatResourceSummary(item);
    const descHtml = summary ? `<p class="text-stone-600 font-medium text-sm pt-1 line-clamp-2 leading-relaxed break-words">${summary}</p>` : "";
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
    let kickMemberBtn = "";
    if (canManageRoles) {
      if (m.is_admin) {
        adminToggleBtn = `<button onclick="event.preventDefault(); event.stopPropagation(); toggleMemberRole(${activeGroupData.id}, ${m.id}, 0)" class="mt-2 px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-800 font-bold text-xs rounded-xl transition">Demote from Admin</button>`;
      } else {
        adminToggleBtn = `<button onclick="event.preventDefault(); event.stopPropagation(); toggleMemberRole(${activeGroupData.id}, ${m.id}, 1)" class="mt-2 px-3 py-1.5 bg-amber-100 hover:bg-amber-200 text-amber-900 font-bold text-xs rounded-xl transition">Promote to Admin</button>`;
      }
      if (m.id !== (currentUser ? currentUser.id : null)) {
        kickMemberBtn = `<button onclick="event.preventDefault(); event.stopPropagation(); kickGroupMember(${activeGroupData.id}, ${m.id}, '${m.username}')" class="mt-2 px-3 py-1.5 bg-stone-100 hover:bg-red-600 text-stone-700 hover:text-white font-bold text-xs rounded-xl transition">🚫 Kick/Ban</button>`;
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
      ${(adminToggleBtn || kickMemberBtn) ? `<div class="shrink-0 flex flex-col gap-1 items-end">${adminToggleBtn}${kickMemberBtn}</div>` : ""}
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
    if (unameEl) {
      unameEl.innerHTML = `${u.username || ""} ${u.is_banned === 1 ? '<span class="ml-2 px-3 py-1 bg-red-600 text-white text-xs font-black rounded-full uppercase">🚫 Suspended</span>' : ''}`;
    }

    const emailEl = document.getElementById("prof-email");
    if (emailEl) {
      const createdStr = u.created_at ? new Date(u.created_at).toLocaleDateString() : "";
      emailEl.textContent = createdStr ? `Member since ${createdStr}` : "Member";
    }

    const bioEl = document.getElementById("prof-bio");
    if (bioEl) bioEl.textContent = u.bio ? `"${u.bio}"` : "No bio added yet.";

    const editBox = document.getElementById("prof-edit-btn-box");
    const actionsBox = document.getElementById("prof-actions");
    if (editBox) {
      if (currentUser && currentUser.id === u.id) {
        editBox.classList.remove("hidden");
      } else {
        editBox.classList.add("hidden");
      }
    }
    if (actionsBox) {
      if (currentUser && currentUser.id !== u.id) {
        actionsBox.classList.remove("hidden");
        const safeName = (u.username || "").replace(/'/g, "\\'");
        const safeEmail = (u.email || "").replace(/'/g, "\\'");
        let adminBanBtn = "";
        if (currentUser.is_site_admin === 1) {
          if (u.is_banned === 1) {
            adminBanBtn = `<button onclick="toggleUserBan(${u.id}, 0)" class="px-5 py-3.5 bg-emerald-600 hover:bg-emerald-700 text-white font-black text-sm rounded-2xl shadow transition touch-target">✅ Restore Account</button>`;
          } else {
            adminBanBtn = `<button onclick="toggleUserBan(${u.id}, 1)" class="px-5 py-3.5 bg-red-600 hover:bg-red-700 text-white font-black text-sm rounded-2xl shadow transition touch-target">🚫 Suspend User</button>`;
          }
        }
        actionsBox.innerHTML = `
          <div class="flex flex-wrap gap-3 items-center">
            <button onclick="openModal('modal-kudos'); presetKudosRecipient(${u.id}, '${safeName}', '${safeEmail}')" class="px-8 py-4 bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-600 hover:to-yellow-600 text-white font-black text-lg rounded-2xl shadow-lg shadow-amber-500/30 transition touch-target flex items-center space-x-2">
              <span>🌟 Give Kudos to ${u.username}</span>
            </button>
            ${adminBanBtn}
          </div>
        `;
      } else {
        actionsBox.classList.add("hidden");
        actionsBox.innerHTML = "";
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
    adjustPasskeyButtonsSupport();
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
      if (confirm("Inquiry submitted! Would you like to view the simulated support alert in the Email Outbox Audit Log?")) {
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

async function filterLandingByGroup(gid) {
  landingGroupFilter = gid;
  window.landingGroupFilter = gid;
  const banner = document.getElementById("landing-space-info-banner");
  if (!banner) return;
  if (gid !== "" && gid !== null && gid !== undefined) {
    let group = allGroupsCache.find(g => String(g.id) === String(gid));
    if (!group) {
      try {
        const data = await apiFetch(`/groups/${gid}`);
        if (data) group = data.group || data;
      } catch (err) {
        console.error("Failed to fetch group details for landing banner:", err);
      }
    }
    if (group) {
      const iconUrl = group.icon_url || "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?w=150&auto=format&fit=crop&q=80";
      const memberCount = group.member_count !== undefined ? group.member_count : (group.roster ? group.roster.length : (group.members ? group.members.length : 0));
      const themesHtml = (group.themes || []).map(t => `<span class="px-3 py-1 bg-teal-950/60 text-teal-200 font-bold text-xs rounded-full border border-teal-700/50">${t}</span>`).join("");
      banner.innerHTML = `
        <div class="bg-gradient-to-r from-teal-900 via-teal-800 to-stone-900 p-6 sm:p-8 rounded-3xl text-white shadow-xl flex flex-col md:flex-row items-center justify-between gap-6 border-2 border-teal-600/50">
          <div class="flex items-center space-x-5 max-w-2xl">
            <img src="${iconUrl}" alt="${group.name || ''}" class="w-20 h-20 rounded-2xl object-cover border-2 border-teal-400 shadow-md shrink-0">
            <div class="space-y-2">
              <div class="flex items-baseline space-x-3">
                <h3 class="text-2xl sm:text-3xl font-black tracking-tight">${group.name || ''}</h3>
                <span class="text-xs font-bold text-teal-200">👥 ${memberCount} active members</span>
              </div>
              <p class="text-teal-50 font-medium text-sm sm:text-base leading-relaxed">${group.description || ''}</p>
              <div class="flex flex-wrap gap-1.5 pt-1">
                ${themesHtml}
              </div>
            </div>
          </div>
          <div class="shrink-0 w-full md:w-auto text-center">
            <button type="button" onclick="showView('view-group-detail'); activeGroupId = ${group.id || gid}; loadGroupDetail(${group.id || gid}); navigateTo('/group/${group.id || gid}');" class="w-full md:w-auto px-6 py-3.5 bg-amber-500 hover:bg-amber-600 text-stone-950 font-black text-sm sm:text-base rounded-2xl shadow-lg transition touch-target flex items-center justify-center space-x-2">
              <span>Enter Full Space (Chat, Roster & Resources) ↗</span>
            </button>
          </div>
        </div>
      `;
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
      banner.innerHTML = "";
    }
  } else {
    banner.classList.add("hidden");
    banner.innerHTML = "";
  }
  loadLandingPreview();
}

function filterLandingByType(type) {
  landingTypeFilter = type;
  loadLandingPreview();
}

function filterLandingByTheme(th) {
  if (th !== "" && landingThemeFilter === th) {
    landingThemeFilter = "";
  } else {
    landingThemeFilter = th;
  }
  document.querySelectorAll(".landing-theme-pill").forEach(el => {
    const onclickAttr = el.getAttribute("onclick") || "";
    if (landingThemeFilter !== "" && onclickAttr.includes(`'${landingThemeFilter}'`)) {
      el.className = "landing-theme-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-amber-500 text-white shadow-sm transition touch-target";
    } else if (landingThemeFilter === "" && onclickAttr.includes("''")) {
      el.className = "landing-theme-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-slate-900 text-white transition touch-target shadow-sm";
    } else {
      el.className = "landing-theme-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-white hover:bg-slate-50 text-slate-700 transition touch-target shadow-xs";
    }
  });
  updateLandingThemePillsCollapseUI();
  loadLandingPreview();
}

function filterLandingByFormat(fmt) {
  if (landingFormatFilter === fmt) {
    landingFormatFilter = "";
  } else {
    landingFormatFilter = fmt;
  }
  document.querySelectorAll(".landing-format-pill").forEach(el => {
    const onclickAttr = el.getAttribute("onclick") || "";
    if (landingFormatFilter !== "" && onclickAttr.includes(`'${landingFormatFilter}'`)) {
      el.className = "landing-format-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-amber-500 text-white shadow-sm transition touch-target";
    } else {
      el.className = "landing-format-pill shrink-0 px-3.5 py-1.5 rounded-xl font-bold text-sm bg-white hover:bg-amber-100/60 text-slate-700 transition touch-target shadow-xs";
    }
  });
  updateLandingThemePillsCollapseUI();
  loadLandingPreview();
}

function toggleLandingThemePillsBar(forceState) {
  if (typeof forceState === "boolean") {
    isLandingThemePillsCollapsed = forceState;
  } else {
    isLandingThemePillsCollapsed = !isLandingThemePillsCollapsed;
  }
  updateLandingThemePillsCollapseUI();
}
window.toggleLandingThemePillsBar = toggleLandingThemePillsBar;

function updateLandingThemePillsCollapseUI() {
  const pillsBar = document.getElementById("landing-theme-pills-bar");
  const toggleBtn = document.getElementById("btn-toggle-landing-theme-pills");
  const toggleIcon = document.getElementById("landing-theme-pills-toggle-icon");
  const indicator = document.getElementById("landing-theme-pills-active-indicator");

  if (!pillsBar) return;

  const hasActive = Boolean(landingThemeFilter || landingFormatFilter);

  if (isLandingThemePillsCollapsed) {
    pillsBar.classList.add("hidden");
    if (toggleIcon) toggleIcon.textContent = "▼";
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", "false");
      if (hasActive) {
        toggleBtn.className = "px-3.5 py-2.5 rounded-xl border border-amber-400 font-bold text-sm bg-amber-50 text-amber-900 transition flex items-center space-x-1.5 shrink-0 touch-target shadow-xs";
      } else {
        toggleBtn.className = "px-3.5 py-2.5 rounded-xl border border-slate-300 font-bold text-sm bg-slate-50 hover:bg-slate-100 text-slate-700 transition flex items-center space-x-1.5 shrink-0 touch-target";
      }
    }
  } else {
    pillsBar.classList.remove("hidden");
    if (toggleIcon) toggleIcon.textContent = "▲";
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-expanded", "true");
      if (hasActive) {
        toggleBtn.className = "px-3.5 py-2.5 rounded-xl border border-amber-400 font-bold text-sm bg-amber-50 text-amber-900 transition flex items-center space-x-1.5 shrink-0 touch-target shadow-xs";
      } else {
        toggleBtn.className = "px-3.5 py-2.5 rounded-xl border border-slate-300 font-bold text-sm bg-white hover:bg-slate-50 text-slate-700 transition flex items-center space-x-1.5 shrink-0 touch-target";
      }
    }
  }

  if (indicator) {
    if (hasActive) {
      indicator.classList.remove("hidden");
    } else {
      indicator.classList.add("hidden");
    }
  }
}

window.filterLandingByGroup = filterLandingByGroup;
window.filterLandingByType = filterLandingByType;
window.filterLandingByTheme = filterLandingByTheme;
window.filterLandingByFormat = filterLandingByFormat;
window.landingGroupFilter = landingGroupFilter;

function formatAttachmentLabel(url, idx, totalCount, fallbackName) {
  const count = (totalCount !== undefined && totalCount !== null && !isNaN(Number(totalCount))) ? Number(totalCount) : 1;
  let num = 1;
  if (idx !== undefined && idx !== null && !isNaN(Number(idx))) {
    num = Number(idx) + 1;
  }
  const prefix = count > 1 ? `#${num}: ` : "";

  if (!url) return `📎 ${prefix}Attached Link or File ↗`;

  let rawUrl = url;
  let explicitName = (fallbackName && typeof fallbackName === "string") ? fallbackName.trim() : "";
  if (typeof url === "object" && url !== null) {
    explicitName = explicitName || url.filename || url.name || url.title || "";
    rawUrl = url.url || url.data || url.dataUrl || url.src || "";
  }

  const str = String(rawUrl || "").trim();
  if (str.toLowerCase().startsWith("data:")) {
    const mimePart = str.slice(5).split(";")[0].split(",")[0].trim().toLowerCase();
    
    if (!explicitName) {
      const headerPart = str.split(",")[0];
      const match = headerPart.match(/(?:name|filename|title)\*?=(?:UTF-8'')?([^;,#?&]+)/i) || 
                    str.match(/[#?&](?:name|filename|title)=([^;,#?&]+)/i) ||
                    str.match(/#([^\s,;?&]+\.[a-z0-9]{2,5})/i);
      if (match && match[1]) {
        try {
          explicitName = decodeURIComponent(match[1].replace(/^["']|["']$/g, '').trim());
        } catch(e) {
          explicitName = match[1].trim();
        }
      }
    }

    let label = "Attached File";
    let icon = "📎";
    if (mimePart.includes("pdf") || (explicitName && explicitName.toLowerCase().endsWith(".pdf"))) {
      label = explicitName || "PDF Document";
      icon = "📄";
    } else if (mimePart.includes("sheet") || mimePart.includes("excel") || mimePart.includes("xls") || mimePart.includes("csv") || mimePart.includes("opendocument.spreadsheet") || (explicitName && /\.(xls|xlsx|csv|ods)$/i.test(explicitName))) {
      label = explicitName || "Spreadsheet";
      icon = "📊";
    } else if (mimePart.includes("presentation") || mimePart.includes("powerpoint") || mimePart.includes("ppt") || mimePart.includes("opendocument.presentation") || (explicitName && /\.(ppt|pptx|odp)$/i.test(explicitName))) {
      label = explicitName || "Presentation";
      icon = "📊";
    } else if (mimePart.includes("word") || mimePart.includes("msword") || mimePart.includes("officedocument") || mimePart.includes("opendocument.text") || mimePart.includes("rtf") || mimePart.includes("pages") || mimePart === "application/document" || (explicitName && /\.(doc|docx|rtf|pages|odt)$/i.test(explicitName))) {
      label = explicitName || "Word Document";
      icon = "📄";
    } else if (mimePart.startsWith("image/") || mimePart.includes("image") || mimePart.includes("png") || mimePart.includes("jpeg") || mimePart.includes("jpg") || mimePart.includes("gif") || mimePart.includes("webp") || mimePart.includes("svg") || mimePart.includes("bmp") || mimePart.includes("ico") || (explicitName && /\.(png|jpg|jpeg|gif|webp|svg|bmp|ico)$/i.test(explicitName))) {
      label = explicitName || "Image File";
      icon = "🖼️";
    } else if (mimePart.startsWith("audio/") || mimePart.includes("audio") || (explicitName && /\.(mp3|wav|ogg|flac|m4a|aac)$/i.test(explicitName))) {
      label = explicitName || "Audio File";
      icon = "🎵";
    } else if (mimePart.startsWith("video/") || mimePart.includes("video") || (explicitName && /\.(mp4|mov|avi|mkv|webm|flv)$/i.test(explicitName))) {
      label = explicitName || "Video File";
      icon = "🎬";
    } else if (mimePart.includes("zip") || mimePart.includes("archive") || mimePart.includes("tar") || mimePart.includes("gzip") || mimePart.includes("compressed") || mimePart.includes("rar") || mimePart.includes("7z") || (explicitName && /\.(zip|tar|gz|rar|7z|bz2)$/i.test(explicitName))) {
      label = explicitName || "Archive File";
      icon = "🗜️";
    } else if (mimePart.startsWith("text/") || mimePart.includes("text") || mimePart.includes("plain") || mimePart.includes("json") || mimePart.includes("xml") || mimePart.includes("html") || mimePart.includes("md") || (explicitName && /\.(txt|json|xml|html|htm|md|log)$/i.test(explicitName))) {
      label = explicitName || "Text Document";
      icon = "📝";
    } else if (explicitName) {
      label = explicitName;
    }

    let displayed = label;
    if (displayed.length > 26) {
      displayed = displayed.slice(0, 23) + "...";
    }
    return `${icon} ${prefix}${displayed} ↗`;
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

function toggleProfileDropdown(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  const dropdown = document.getElementById("profile-dropdown-menu");
  if (dropdown) dropdown.classList.toggle("hidden");
}

function closeProfileDropdown() {
  const dropdown = document.getElementById("profile-dropdown-menu");
  if (dropdown) dropdown.classList.add("hidden");
}

window.presetLogin = presetLogin;
window.triggerGoogleSignIn = triggerGoogleSignIn;
window.handleGoogleOauthResponse = handleGoogleOauthResponse;
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
window.toggleProfileDropdown = toggleProfileDropdown;
window.closeProfileDropdown = closeProfileDropdown;
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

// ================== SPACE CALENDAR CONTROLLER & SCRAPING ==================
window.currentCalendarYear = new Date().getFullYear();
window.currentCalendarMonth = new Date().getMonth();
window.isCalendarCollapsed = false;
window._cachedCalendarEvents = {};
window._groupCalendarEvents = {};
window._scrapedCalendarEvents = [];
window._scrapedEventsPreview = [];

function toggleCalendarWidget(forceCollapse) {
  if (typeof forceCollapse === "boolean") {
    window.isCalendarCollapsed = forceCollapse;
  } else {
    window.isCalendarCollapsed = !window.isCalendarCollapsed;
  }
  updateCalendarCollapseUI();
}

function updateCalendarCollapseUI() {
  const sidebar = document.getElementById("group-calendar-sidebar");
  const mainCol = document.getElementById("group-main-content-col");
  const toggleBtn = document.getElementById("btn-toggle-calendar");
  const toggleText = document.getElementById("calendar-toggle-text");
  const toggleIcon = document.getElementById("calendar-toggle-icon");

  if (!sidebar || !mainCol) return;

  if (window.isCalendarCollapsed) {
    sidebar.classList.add("hidden");
    mainCol.classList.remove("lg:col-span-2");
    mainCol.classList.add("lg:col-span-3", "col-span-full");
    if (toggleText) toggleText.textContent = "Show Calendar";
    if (toggleIcon) toggleIcon.textContent = "📅";
    if (toggleBtn) {
      toggleBtn.classList.add("bg-amber-100", "text-amber-900", "border-amber-400");
      toggleBtn.classList.remove("bg-stone-100", "text-stone-700", "border-stone-300");
      toggleBtn.setAttribute("title", "Expand calendar widget to view scheduled events");
    }
  } else {
    sidebar.classList.remove("hidden");
    mainCol.classList.remove("lg:col-span-3", "col-span-full");
    mainCol.classList.add("lg:col-span-2");
    if (toggleText) toggleText.textContent = "Hide Calendar";
    if (toggleIcon) toggleIcon.textContent = "📅";
    if (toggleBtn) {
      toggleBtn.classList.remove("bg-amber-100", "text-amber-900", "border-amber-400");
      toggleBtn.classList.add("bg-stone-100", "text-stone-700", "border-stone-300");
      toggleBtn.setAttribute("title", "Collapse calendar to expand tabs & feeds space");
    }
    if (typeof renderGroupCalendar === "function") {
      renderGroupCalendar();
    }
  }
}

async function renderGroupCalendar() {
  if (!activeGroupData || !activeGroupData.id) return;
  const grid = document.getElementById("calendar-days-grid");
  if (!grid) return;
  
  if (window.currentCalendarYear === undefined || window.currentCalendarYear === null) {
    window.currentCalendarYear = new Date().getFullYear();
  }
  if (window.currentCalendarMonth === undefined || window.currentCalendarMonth === null) {
    window.currentCalendarMonth = new Date().getMonth();
  }

  const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  const header = document.getElementById("calendar-month-header");
  if (header) {
    header.textContent = `${monthNames[window.currentCalendarMonth]} ${window.currentCalendarYear}`;
  }

  const isGroupAdmin = activeGroupData.is_admin;
  const isSiteAdmin = currentUser && currentUser.is_site_admin === 1;
  const isAdmin = isGroupAdmin || isSiteAdmin;

  const bar1 = document.getElementById("calendar-admin-action-bar");
  const bar2 = document.getElementById("admin-calendar-actions");
  if (bar1) {
    if (isAdmin) bar1.classList.remove("hidden");
    else bar1.classList.add("hidden");
  }
  if (bar2) {
    if (isAdmin) bar2.classList.remove("hidden");
    else bar2.classList.add("hidden");
  }

  let posts = [];
  if (Array.isArray(activeGroupData.posts)) {
    posts = activeGroupData.posts;
  } else {
    try {
      const feedRes = await apiFetch(`/feed?group_id=${activeGroupData.id}&filter_type=POST`);
      posts = feedRes.feed || [];
    } catch (e) {
      posts = [];
    }
  }

  const resources = Array.isArray(activeGroupData.resources) ? activeGroupData.resources : [];
  const eventsByDate = {};

  posts.forEach(p => {
    if (p.item_type === "POST" && p.post_subtype === "EVENT" && p.event_date) {
      const dateStr = String(p.event_date).split("T")[0];
      if (!eventsByDate[dateStr]) eventsByDate[dateStr] = [];
      eventsByDate[dateStr].push({
        id: p.id,
        title: p.title || "Community Event",
        event_date: dateStr,
        time: p.time || "",
        description: p.content || p.description || "",
        resource_url: p.resource_url || "",
        author_id: p.author_id,
        author_name: p.author_name || "Member",
        type: "POST"
      });
    }
  });

  resources.forEach((r, idx) => {
    if (r.event_date) {
      const dateStr = String(r.event_date).split("T")[0];
      if (!eventsByDate[dateStr]) eventsByDate[dateStr] = [];
      eventsByDate[dateStr].push({
        id: r.id || `res_${idx}`,
        title: r.title || r.description || "Resource Event",
        event_date: dateStr,
        time: r.time || "",
        description: r.description || r.title || "",
        resource_url: r.url || "",
        author_id: r.added_by,
        author_name: r.added_by_name || "Admin",
        type: "RESOURCE"
      });
    }
  });

  window._cachedCalendarEvents = eventsByDate;
  window._groupCalendarEvents = eventsByDate;

  const firstDay = new Date(window.currentCalendarYear, window.currentCalendarMonth, 1).getDay();
  const daysInMonth = new Date(window.currentCalendarYear, window.currentCalendarMonth + 1, 0).getDate();
  const todayStr = new Date().toISOString().split("T")[0];

  let html = "";
  for (let i = 0; i < firstDay; i++) {
    html += `<div class="p-1.5 min-h-[3.8rem] bg-stone-50/40 rounded-2xl opacity-30 border border-transparent"></div>`;
  }

  for (let day = 1; day <= daysInMonth; day++) {
    const dateStr = `${window.currentCalendarYear}-${String(window.currentCalendarMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const evList = eventsByDate[dateStr] || [];
    const hasEvents = evList.length > 0;
    const isToday = (dateStr === todayStr);

    let cellClass = "p-1.5 min-h-[3.8rem] rounded-2xl flex flex-col items-center justify-between border transition relative text-xs ";
    let hoverTitle = "";

    if (hasEvents) {
      cellClass += "bg-amber-50/90 hover:bg-amber-100 border-2 border-amber-400 cursor-pointer text-stone-900 font-bold shadow-xs hover:shadow-md hover:scale-[1.02]";
      hoverTitle = `${evList.length} event${evList.length > 1 ? "s" : ""} on ${dateStr}:\n` + evList.map(e => `• ${e.title}${e.time ? ` (${e.time})` : ""}`).join("\n");
    } else if (isToday) {
      cellClass += "bg-indigo-50/70 border-2 border-indigo-300 text-indigo-950 font-extrabold cursor-pointer hover:bg-indigo-100/70";
      hoverTitle = `Today (${dateStr}) - Click to add event`;
    } else {
      cellClass += "bg-stone-50/80 border border-stone-200/70 text-stone-700 hover:bg-stone-100 hover:border-stone-300 cursor-pointer";
      hoverTitle = `${dateStr} - Click to add event`;
    }

    const clickAttr = hasEvents ? `onclick="showCalendarDayEvents('${dateStr}')"` : `onclick="openAddCalendarEventModal('${dateStr}')"`;

    let eventIndicatorHtml = "";
    if (hasEvents) {
      const dotsHtml = evList.slice(0, 3).map(() => `<span class="w-1.5 h-1.5 rounded-full bg-amber-500 shadow-xs"></span>`).join("");
      const moreText = evList.length > 3 ? `<span class="text-[8px] font-black text-amber-700">+${evList.length - 3}</span>` : "";
      eventIndicatorHtml = `
        <div class="mt-auto w-full flex flex-col items-center justify-center pt-0.5">
          <div class="flex items-center justify-center gap-1 mb-0.5">
            ${dotsHtml}
            ${moreText}
          </div>
          <span class="text-[9px] font-black text-amber-900 bg-amber-200/90 px-1.5 py-0.5 rounded-md leading-tight text-center truncate max-w-full">
            ${evList.length} ${evList.length === 1 ? 'event' : 'events'}
          </span>
        </div>
      `;
    }

    html += `
      <div class="${cellClass}" ${clickAttr} title="${hoverTitle.replace(/"/g, "&quot;")}">
        <span class="${isToday ? 'w-5 h-5 rounded-full bg-indigo-600 text-white font-black text-[11px] flex items-center justify-center shadow-xs' : 'font-black text-xs text-stone-900'} leading-none">${day}</span>
        ${eventIndicatorHtml}
      </div>
    `;
  }
  grid.innerHTML = html;
}

function navigateGroupCalendar(offset) {
  if (window.currentCalendarYear === undefined) window.currentCalendarYear = new Date().getFullYear();
  if (window.currentCalendarMonth === undefined) window.currentCalendarMonth = new Date().getMonth();
  
  window.currentCalendarMonth += offset;
  if (window.currentCalendarMonth > 11) {
    window.currentCalendarMonth = 0;
    window.currentCalendarYear++;
  } else if (window.currentCalendarMonth < 0) {
    window.currentCalendarMonth = 11;
    window.currentCalendarYear--;
  }
  renderGroupCalendar();
}

function showCalendarDayEvents(dateStr) {
  const modalTitle1 = document.getElementById("calendar-day-modal-title");
  const modalTitle2 = document.getElementById("modal-calendar-day-header");
  const listEl1 = document.getElementById("calendar-day-events-list");
  const listEl2 = document.getElementById("modal-calendar-day-list");
  
  let formattedDate = dateStr;
  try {
    const d = new Date(dateStr + "T00:00:00");
    if (!isNaN(d.getTime())) {
      formattedDate = d.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    }
  } catch(e) {}

  if (modalTitle1) modalTitle1.textContent = formattedDate;
  if (modalTitle2) modalTitle2.textContent = `Events on ${dateStr}`;

  const evList = (window._cachedCalendarEvents && window._cachedCalendarEvents[dateStr]) || (window._groupCalendarEvents && window._groupCalendarEvents[dateStr]) || [];

  let contentHtml = "";
  if (evList.length === 0) {
    contentHtml = `<p class="text-stone-500 font-bold py-6 text-center">No events scheduled for this day.</p>`;
  } else {
    window._attachmentCache = window._attachmentCache || {};
    contentHtml = evList.map((ev, idx) => {
      // Permission check: event author, site admin, or group admin
      const isAuthor = currentUser && (Number(currentUser.id) === Number(ev.author_id));
      const isSiteAdmin = currentUser && (currentUser.is_site_admin === 1);
      const isGroupAdmin = currentUser && activeGroupData && (activeGroupData.is_admin === 1);
      const canModify = Boolean(isAuthor || isSiteAdmin || isGroupAdmin);

      // Clean description and extract time & URLs
      let cleanDesc = ev.description || "";
      let eventTime = ev.time || "";
      const timeMatch = cleanDesc.match(/\[Time:\s*([^\]]+)\]/i);
      if (timeMatch) {
        if (!eventTime) eventTime = timeMatch[1].trim();
        cleanDesc = cleanDesc.replace(/\[Time:\s*[^\]]+\]\s*/gi, "").trim();
      }

      // Collect all attachment URLs (from resource_url and embedded in description)
      let urls = [];
      if (ev.resource_url) {
        try {
          const parsed = JSON.parse(ev.resource_url);
          if (Array.isArray(parsed)) urls = parsed;
          else if (typeof parsed === "string") urls = [parsed];
          else urls = [ev.resource_url];
        } catch(e) {
          urls = [ev.resource_url];
        }
      }

      // Extract standalone URLs from description so they render as consistent pill buttons
      const urlRegex = /(https?:\/\/[^\s]+)/gi;
      const embeddedUrls = cleanDesc.match(urlRegex) || [];
      embeddedUrls.forEach(u => {
        if (!urls.includes(u)) urls.push(u);
        cleanDesc = cleanDesc.replace(u, "").trim();
      });

      let attachmentHtml = "";
      if (urls.length > 0) {
        const pillsHtml = urls.filter(Boolean).map((u, uIdx) => {
          const cacheKey = `cal_${dateStr}_${ev.id || idx}_${uIdx}`;
          const filename = `cal_att_${ev.id || idx}_${uIdx}`;
          window._attachmentCache[cacheKey] = u;
          return `
            <button type="button" onclick="window.openAttachment(window._attachmentCache['${cacheKey}'], '${filename}')" class="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-xl bg-amber-100 hover:bg-amber-200 text-amber-950 font-bold text-xs border border-amber-300 transition touch-target shadow-sm">
              <span>${formatAttachmentLabel(u, uIdx, urls.length)}</span>
            </button>
          `;
        }).join("");
        if (pillsHtml) {
          attachmentHtml = `
            <div class="mt-3 pt-2 border-t border-amber-200/60 flex flex-wrap gap-2">
              ${pillsHtml}
            </div>
          `;
        }
      }

      // Actions buttons (Edit / Delete)
      let actionsHtml = "";
      if (canModify) {
        actionsHtml = `
          <div class="flex items-center space-x-1.5 ml-2">
            <button type="button" onclick="openEditCalendarEventModal('${ev.id}', '${ev.type || 'POST'}', '${dateStr}')" class="p-1.5 rounded-xl bg-white hover:bg-amber-100 border border-stone-200 hover:border-amber-300 text-stone-600 hover:text-amber-800 transition touch-target" title="Edit event" aria-label="Edit event">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
            </button>
            <button type="button" onclick="deleteCalendarEvent('${ev.id}', '${ev.type || 'POST'}', '${dateStr}')" class="p-1.5 rounded-xl bg-white hover:bg-red-50 border border-stone-200 hover:border-red-300 text-stone-400 hover:text-red-600 transition touch-target" title="Delete event" aria-label="Delete event">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
            </button>
          </div>
        `;
      }

      return `
        <div class="bg-amber-50/70 p-5 rounded-2xl border border-amber-300 shadow-sm space-y-2 text-left">
          <div class="flex items-start justify-between">
            <div class="flex-1 pr-2">
              <h4 class="font-black text-stone-900 text-base leading-snug">${ev.title}</h4>
              ${ev.author_name ? `<span class="text-[11px] font-bold text-stone-500">By ${ev.author_name}</span>` : ""}
            </div>
            <div class="flex items-center">
              ${eventTime ? `<span class="px-2.5 py-1 bg-amber-500 text-white font-extrabold text-xs rounded-full shadow-xs whitespace-nowrap">${eventTime}</span>` : ""}
              ${actionsHtml}
            </div>
          </div>
          ${cleanDesc ? `<p class="text-stone-700 font-medium text-sm leading-relaxed whitespace-pre-line">${cleanDesc}</p>` : ""}
          ${attachmentHtml}
        </div>
      `;
    }).join("");
  }

  if (listEl1) listEl1.innerHTML = contentHtml;
  if (listEl2 && listEl2 !== listEl1) listEl2.innerHTML = contentHtml;

  openModal("modal-calendar-day");
}

let editingCalendarEventId = null;
let editingCalendarEventType = "POST";
let editingCalendarEventDate = null;

function addEventLinkField(initialValue = "") {
  const container = document.getElementById("add-event-links-list");
  if (!container) return;
  const div = document.createElement("div");
  div.className = "flex gap-2 animate-fadeIn";
  div.innerHTML = `
    <input type="url" value="${initialValue.replace(/"/g, '&quot;')}" placeholder="https://example.com/another-link" class="add-event-link-input flex-1 px-3.5 py-2.5 rounded-xl border border-stone-300 font-medium text-sm text-stone-900 bg-stone-50 focus:bg-white focus:border-amber-600 focus:outline-none transition">
    <button type="button" onclick="this.closest('.flex').remove()" class="px-3 py-2 text-stone-400 hover:text-red-500 font-bold text-lg rounded-lg border border-stone-200 bg-white" title="Remove link">×</button>
  `;
  container.appendChild(div);
}

function handleAddEventFilesSelect(e) {
  const preview = document.getElementById("add-event-files-preview");
  if (!preview) return;
  const files = e.target.files ? Array.from(e.target.files) : [];
  if (files.length === 0) {
    preview.innerHTML = "";
    return;
  }
  preview.innerHTML = files.map(f => `
    <div class="flex items-center justify-between px-4 py-2.5 bg-amber-50/60 rounded-xl border border-amber-200 text-xs font-bold text-amber-950">
      <span class="truncate max-w-[280px] sm:max-w-[400px]">📄 ${f.name} (${Math.round(f.size/1024)} KB)</span>
      <span class="text-emerald-600 font-extrabold uppercase">Ready</span>
    </div>
  `).join("");
}

function openAddCalendarEventModal(dateStr) {
  if (!currentUser) {
    showToast("Please log in to add calendar events.");
    openModal("modal-login");
    return;
  }

  editingCalendarEventId = null;
  editingCalendarEventType = "POST";
  editingCalendarEventDate = null;

  const modalHeader = document.querySelector("#modal-add-event h3");
  const modalDesc = document.querySelector("#modal-add-event p");
  const submitBtn = document.querySelector("#modal-add-event button[type='submit']");
  if (modalHeader) modalHeader.textContent = "Add Calendar Event";
  if (modalDesc) modalDesc.textContent = "Schedule an activity, workshop, or community gathering.";
  if (submitBtn) submitBtn.textContent = "Add to Calendar";

  const title1 = document.getElementById("add-event-title");
  const title2 = document.getElementById("addevent-title");
  const date1 = document.getElementById("add-event-date");
  const date2 = document.getElementById("addevent-date");
  const time1 = document.getElementById("add-event-time");
  const time2 = document.getElementById("addevent-time");
  const desc1 = document.getElementById("add-event-description");
  const desc2 = document.getElementById("addevent-description");
  const linksContainer = document.getElementById("add-event-links-list");
  const fileInput = document.getElementById("add-event-file-input");
  const filesPreview = document.getElementById("add-event-files-preview");

  const today = new Date().toISOString().split("T")[0];
  const targetDate = (dateStr && /^\d{4}-\d{2}-\d{2}$/.test(dateStr)) ? dateStr : today;

  if (title1) title1.value = "";
  if (title2) title2.value = "";
  if (date1) {
    date1.value = targetDate;
    date1.setAttribute("min", today);
  }
  if (date2) date2.value = targetDate;
  if (time1) time1.value = "";
  if (time2) time2.value = "";
  if (desc1) desc1.value = "";
  if (desc2) desc2.value = "";
  if (linksContainer) {
    linksContainer.innerHTML = `
      <div class="flex gap-2">
        <input type="url" id="add-event-input-url" placeholder="https://example.com/event-details" class="add-event-link-input flex-1 px-3.5 py-2.5 rounded-xl border border-stone-300 font-medium text-sm text-stone-900 bg-stone-50 focus:bg-white focus:border-amber-600 focus:outline-none transition">
      </div>
    `;
  }
  if (fileInput) fileInput.value = "";
  if (filesPreview) filesPreview.innerHTML = "";

  openModal("modal-add-event");
}
const openAddEventModal = openAddCalendarEventModal;

function openEditCalendarEventModal(eventId, eventType, dateStr) {
  const evList = (window._cachedCalendarEvents && window._cachedCalendarEvents[dateStr]) || [];
  const ev = evList.find(e => String(e.id) === String(eventId));
  if (!ev) return;

  editingCalendarEventId = ev.id;
  editingCalendarEventType = eventType || ev.type || "POST";
  editingCalendarEventDate = dateStr;

  const modalHeader = document.querySelector("#modal-add-event h3");
  const modalDesc = document.querySelector("#modal-add-event p");
  const submitBtn = document.querySelector("#modal-add-event button[type='submit']");
  if (modalHeader) modalHeader.textContent = "Edit Calendar Event";
  if (modalDesc) modalDesc.textContent = "Update event details, time, links, or attachments.";
  if (submitBtn) submitBtn.textContent = "Save Changes";

  const title1 = document.getElementById("add-event-title");
  const date1 = document.getElementById("add-event-date");
  const time1 = document.getElementById("add-event-time");
  const desc1 = document.getElementById("add-event-description");
  const linksContainer = document.getElementById("add-event-links-list");
  const fileInput = document.getElementById("add-event-file-input");
  const filesPreview = document.getElementById("add-event-files-preview");

  if (title1) title1.value = ev.title || "";
  if (date1) {
    date1.value = ev.event_date || dateStr;
    date1.removeAttribute("min");
  }

  // Clean description and extract time
  let cleanDesc = ev.description || "";
  let eventTime = ev.time || "";
  const timeMatch = cleanDesc.match(/\[Time:\s*([^\]]+)\]/i);
  if (timeMatch) {
    if (!eventTime) eventTime = timeMatch[1].trim();
    cleanDesc = cleanDesc.replace(/\[Time:\s*[^\]]+\]\s*/gi, "").trim();
  }

  // Collect all URLs
  let urls = [];
  if (ev.resource_url) {
    try {
      const parsed = JSON.parse(ev.resource_url);
      if (Array.isArray(parsed)) urls = parsed;
      else if (typeof parsed === "string") urls = [parsed];
      else urls = [ev.resource_url];
    } catch(e) {
      urls = [ev.resource_url];
    }
  }
  const urlRegex = /(https?:\/\/[^\s]+)/gi;
  const embeddedUrls = cleanDesc.match(urlRegex) || [];
  embeddedUrls.forEach(u => {
    if (!urls.includes(u)) urls.push(u);
    cleanDesc = cleanDesc.replace(u, "").trim();
  });

  if (time1) time1.value = eventTime;
  if (desc1) desc1.value = cleanDesc;

  // Populate link inputs
  if (linksContainer) {
    const webUrls = urls.filter(u => !u.startsWith("data:"));
    if (webUrls.length === 0) {
      linksContainer.innerHTML = `
        <div class="flex gap-2">
          <input type="url" id="add-event-input-url" placeholder="https://example.com/event-details" class="add-event-link-input flex-1 px-3.5 py-2.5 rounded-xl border border-stone-300 font-medium text-sm text-stone-900 bg-stone-50 focus:bg-white focus:border-amber-600 focus:outline-none transition">
        </div>
      `;
    } else {
      linksContainer.innerHTML = webUrls.map((u, i) => `
        <div class="flex gap-2 animate-fadeIn">
          <input type="url" value="${u.replace(/"/g, '&quot;')}" placeholder="https://example.com/event-details" class="add-event-link-input flex-1 px-3.5 py-2.5 rounded-xl border border-stone-300 font-medium text-sm text-stone-900 bg-stone-50 focus:bg-white focus:border-amber-600 focus:outline-none transition">
          ${i > 0 ? `<button type="button" onclick="this.closest('.flex').remove()" class="px-3 py-2 text-stone-400 hover:text-red-500 font-bold text-lg rounded-lg border border-stone-200 bg-white" title="Remove link">×</button>` : ""}
        </div>
      `).join("");
    }
  }

  if (fileInput) fileInput.value = "";
  if (filesPreview) {
    const fileUrls = urls.filter(u => u.startsWith("data:"));
    if (fileUrls.length > 0) {
      filesPreview.innerHTML = fileUrls.map((f, fIdx) => `
        <div class="flex items-center justify-between px-4 py-2.5 bg-amber-50/60 rounded-xl border border-amber-200 text-xs font-bold text-amber-950">
          <span class="truncate max-w-[280px] sm:max-w-[400px]">📄 ${formatAttachmentLabel(f, fIdx, fileUrls.length)}</span>
          <span class="text-amber-600 font-extrabold uppercase">Existing File</span>
        </div>
      `).join("");
    } else {
      filesPreview.innerHTML = "";
    }
  }

  closeModal("modal-calendar-day");
  openModal("modal-add-event");
}

async function deleteCalendarEvent(eventId, eventType, dateStr) {
  if (!confirm("Are you sure you want to delete this event? This cannot be undone.")) return;
  try {
    if (eventType === "RESOURCE" && activeGroupId) {
      await apiFetch(`/groups/${activeGroupId}/resources/${eventId}`, { method: "DELETE" });
    } else {
      await apiFetch(`/posts/${eventId}`, { method: "DELETE" });
    }
    showToast("🗑️ Event deleted successfully!");
    closeModal("modal-calendar-day");
    if (activeGroupId) {
      await loadGroupDetail(activeGroupId);
    }
    await renderGroupCalendar();
    if (dateStr) {
      const remaining = (window._cachedCalendarEvents && window._cachedCalendarEvents[dateStr]) || [];
      if (remaining.length > 0) {
        showCalendarDayEvents(dateStr);
      }
    }
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function submitAddEventModal(event) {
  if (event && event.preventDefault) event.preventDefault();
  if (!activeGroupData || !activeGroupData.id) return;

  const titleInput = document.getElementById("add-event-title") || document.getElementById("addevent-title");
  const dateInput = document.getElementById("add-event-date") || document.getElementById("addevent-date");
  const timeInput = document.getElementById("add-event-time") || document.getElementById("addevent-time");
  const descInput = document.getElementById("add-event-description") || document.getElementById("addevent-description");
  const linkInputs = document.querySelectorAll(".add-event-link-input");
  const fileInput = document.getElementById("add-event-file-input");

  const title = titleInput ? titleInput.value.trim() : "";
  const event_date = dateInput ? dateInput.value.trim() : "";
  const time = timeInput ? timeInput.value.trim() : "";
  let description = descInput ? descInput.value.trim() : "";
  if (time && description && !description.includes(`Time: ${time}`)) {
    description = `[Time: ${time}] ${description}`.trim();
  } else if (time && !description) {
    description = `[Time: ${time}]`;
  }

  if (!title || !event_date) {
    showToast("Title and Event Date are required.");
    return;
  }

  const attachments = [];
  if (linkInputs) {
    linkInputs.forEach(inp => {
      const u = inp.value.trim();
      if (u) attachments.push(u);
    });
  }

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
        const enrichedUrl = file.name ? dataUrl.replace(/^data:([^;,]+)/, `data:$1;name=${encodeURIComponent(file.name)}`) : dataUrl;
        attachments.push(enrichedUrl);
      }
    } catch (e) {}
  }

  const resUrl = attachments.length === 1 ? attachments[0] : (attachments.length > 1 ? JSON.stringify(attachments) : "");

  const payload = {
    title: title,
    theme: "Events",
    content: description || title,
    resource_url: resUrl,
    attachments: attachments,
    post_subtype: "EVENT",
    event_date: event_date,
    group_ids: [activeGroupData.id]
  };

  try {
    if (editingCalendarEventId) {
      const updateUrl = (editingCalendarEventType === "RESOURCE" && activeGroupId) 
        ? `/api/posts/${editingCalendarEventId}` 
        : `/api/posts/${editingCalendarEventId}`;
      const res = await apiFetch(updateUrl, {
        method: "PUT",
        body: payload
      });
      if (res.success || res.item || res.post) {
        showToast("🎉 Event updated successfully!");
        closeModal("modal-add-event");
        const updatedDate = event_date || editingCalendarEventDate;
        editingCalendarEventId = null;
        if (activeGroupId) await loadGroupDetail(activeGroupId);
        await renderGroupCalendar();
        if (updatedDate) showCalendarDayEvents(updatedDate);
        if (typeof renderGroupPosts === "function") renderGroupPosts();
      }
    } else {
      const res = await apiFetch("/api/posts", {
        method: "POST",
        body: payload
      });
      if (res.success || res.item || res.post) {
        showToast("🎉 Calendar event added!");
        closeModal("modal-add-event");
        await renderGroupCalendar();
        if (typeof renderGroupPosts === "function") renderGroupPosts();
      }
    }
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function handleCalendarPdfUpload(event) {
  const file = event.target.files && event.target.files[0];
  if (!file || !activeGroupData || !activeGroupData.id) return;

  const reader = new FileReader();
  reader.onload = async function(e) {
    const b64Data = e.target.result;
    try {
      showToast("⏳ Scraping calendar events from PDF...");
      const res = await apiFetch(`/api/groups/${activeGroupData.id}/scrape_calendar`, {
        method: "POST",
        body: { file_data: b64Data, resource_url: b64Data }
      });
      if (res.success && res.suggested_events && res.suggested_events.length > 0) {
        window._scrapedCalendarEvents = res.suggested_events;
        window._scrapedEventsPreview = res.suggested_events;
        populateScrapePreviewModal(res.suggested_events);
        openModal("modal-scrape-preview");
      } else {
        showToast("No events found in PDF.");
      }
    } catch (err) {
      showToast("❌ " + err.message);
    } finally {
      if (event.target) event.target.value = "";
    }
  };
  reader.readAsDataURL(file);
}

function populateScrapePreviewModal(suggested_events) {
  const container = document.getElementById("scrape-preview-list");
  if (!container) return;
  if (!suggested_events || suggested_events.length === 0) {
    container.innerHTML = `<p class="text-stone-500 font-bold text-center py-6">No date patterns found in this PDF document.</p>`;
    return;
  }
  container.innerHTML = suggested_events.map((ev, idx) => `
    <div class="bg-stone-50 p-4 rounded-2xl border border-stone-200 space-y-3 flex items-start space-x-3 text-left">
      <input type="checkbox" id="scrape-chk-${idx}" checked class="scraped-event-checkbox mt-1.5 w-5 h-5 text-indigo-600 rounded focus:ring-indigo-500" data-index="${idx}">
      <div class="flex-1 space-y-2">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
          <div>
            <label class="block text-[11px] font-bold text-stone-500 uppercase">Event Title</label>
            <input type="text" id="scrape-title-${idx}" value="${ev.title || ''}" class="w-full px-2.5 py-1 rounded border border-stone-300 text-sm font-bold text-stone-900">
          </div>
          <div>
            <label class="block text-[11px] font-bold text-stone-500 uppercase">Date (YYYY-MM-DD)</label>
            <input type="date" id="scrape-date-${idx}" value="${ev.event_date || ''}" class="w-full px-2.5 py-1 rounded border border-stone-300 text-sm font-bold text-stone-900">
          </div>
          <div>
            <label class="block text-[11px] font-bold text-stone-500 uppercase">Time</label>
            <input type="text" id="scrape-time-${idx}" value="${ev.time || ''}" placeholder="10:00 AM" class="w-full px-2.5 py-1 rounded border border-stone-300 text-sm font-bold text-stone-900">
          </div>
        </div>
        <div>
          <label class="block text-[11px] font-bold text-stone-500 uppercase">Description</label>
          <input type="text" id="scrape-desc-${idx}" value="${ev.description || ''}" class="w-full px-2.5 py-1 rounded border border-stone-300 text-sm text-stone-700">
        </div>
      </div>
    </div>
  `).join("");
}

async function confirmImportScrapedEvents() {
  if (!activeGroupData || !activeGroupData.id) return;
  const checkboxes = document.querySelectorAll(".scraped-event-checkbox:checked, [id^='scrape-chk-']:checked");
  if (checkboxes.length === 0) {
    showToast("Please select at least one event to import.");
    return;
  }

  let importedCount = 0;
  for (let i = 0; i < checkboxes.length; i++) {
    const idx = checkboxes[i].getAttribute("data-index") || checkboxes[i].id.split("-").pop();
    const titleEl = document.getElementById(`scrape-title-${idx}`);
    const dateEl = document.getElementById(`scrape-date-${idx}`);
    const timeEl = document.getElementById(`scrape-time-${idx}`);
    const descEl = document.getElementById(`scrape-desc-${idx}`);

    const title = titleEl ? titleEl.value.trim() : "Scraped Event";
    const date = dateEl ? dateEl.value.trim() : "";
    const time = timeEl ? timeEl.value.trim() : "";
    const desc = descEl ? descEl.value.trim() : "";

    if (!title || !date) continue;

    let content = desc || title;
    if (time && !content.includes(`Time: ${time}`)) {
      content = `[Time: ${time}] ${content}`.trim();
    }

    try {
      await apiFetch("/api/posts", {
        method: "POST",
        body: {
          title: title,
          theme: "Events",
          content: content,
          post_subtype: "EVENT",
          event_date: date,
          group_ids: [activeGroupData.id]
        }
      });
      importedCount++;
    } catch (e) {
      console.error("Failed to import event:", e);
    }
  }

  showToast(`🎉 Imported ${importedCount} calendar events!`);
  closeModal("modal-scrape-preview");
  await renderGroupCalendar();
  if (typeof renderGroupPosts === "function") renderGroupPosts();
}

window.renderGroupCalendar = renderGroupCalendar;
window.navigateGroupCalendar = navigateGroupCalendar;
window.showCalendarDayEvents = showCalendarDayEvents;
window.openAddCalendarEventModal = openAddCalendarEventModal;
window.openAddEventModal = openAddEventModal;
window.openEditCalendarEventModal = openEditCalendarEventModal;
window.deleteCalendarEvent = deleteCalendarEvent;
window.submitAddEventModal = submitAddEventModal;
window.addEventLinkField = addEventLinkField;
window.handleAddEventFilesSelect = handleAddEventFilesSelect;
window.handleCalendarPdfUpload = handleCalendarPdfUpload;
window.populateScrapePreviewModal = populateScrapePreviewModal;
window.confirmImportScrapedEvents = confirmImportScrapedEvents;
window.toggleCalendarWidget = toggleCalendarWidget;
window.updateCalendarCollapseUI = updateCalendarCollapseUI;

// ================== WEBAUTHN / PASSKEY CONTROLLER ==================

function bufferFromBase64url(base64url) {
  let base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
  while (base64.length % 4) {
    base64 += '=';
  }
  const raw = window.atob(base64);
  const buffer = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) {
    buffer[i] = raw.charCodeAt(i);
  }
  return buffer.buffer;
}

function bufferToBase64url(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  const base64 = window.btoa(binary);
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

function prepareRegistrationOptions(options) {
  const pk = options.publicKey;
  pk.challenge = bufferFromBase64url(pk.challenge);
  pk.user.id = bufferFromBase64url(pk.user.id);
  if (pk.excludeCredentials) {
    pk.excludeCredentials.forEach(cred => {
      cred.id = bufferFromBase64url(cred.id);
    });
  }
  return options;
}

function prepareAuthenticationOptions(options) {
  const pk = options.publicKey;
  pk.challenge = bufferFromBase64url(pk.challenge);
  if (pk.allowCredentials) {
    pk.allowCredentials.forEach(cred => {
      cred.id = bufferFromBase64url(cred.id);
    });
  }
  return options;
}

function formatRegistrationResponse(cred) {
  return {
    id: cred.id,
    rawId: bufferToBase64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bufferToBase64url(cred.response.clientDataJSON),
      attestationObject: bufferToBase64url(cred.response.attestationObject),
      transports: cred.response.getTransports ? cred.response.getTransports() : []
    }
  };
}

function formatAuthenticationResponse(cred) {
  return {
    id: cred.id,
    rawId: bufferToBase64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bufferToBase64url(cred.response.clientDataJSON),
      authenticatorData: bufferToBase64url(cred.response.authenticatorData),
      signature: bufferToBase64url(cred.response.signature),
      userHandle: cred.response.userHandle ? bufferToBase64url(cred.response.userHandle) : null
    }
  };
}

async function registerPasskey() {
  if (!window.PublicKeyCredential || !navigator.credentials) {
    showToast("❌ Passkeys require a secure context (HTTPS or localhost). Please enable HTTPS or access via localhost.", "error");
    return;
  }
  try {
    showToast("Requesting registration challenge...");
    const options = await apiFetch("/auth/webauthn/register/challenge", { method: "POST" });
    if (!options || !options.publicKey) {
      throw new Error(options.error || "Failed to get registration options");
    }
    
    prepareRegistrationOptions(options);
    
    showToast("Please interact with your authenticator...");
    const credential = await navigator.credentials.create({
      publicKey: options.publicKey
    });
    
    const formatted = formatRegistrationResponse(credential);
    formatted.deviceName = navigator.userAgent.substring(0, 50); // Simple device name
    
    showToast("Verifying passkey registration...");
    const verifyResult = await apiFetch("/auth/webauthn/register/verify", {
      method: "POST",
      body: formatted
    });
    
    if (verifyResult && verifyResult.success) {
      showToast("🎉 Passkey registered successfully!");
    } else {
      throw new Error(verifyResult.error || "Verification failed");
    }
  } catch (err) {
    console.error("Passkey registration error:", err);
    showToast("❌ Passkey registration failed: " + err.message, "error");
  }
}

async function loginWithPasskey() {
  if (!window.PublicKeyCredential || !navigator.credentials) {
    showToast("❌ Passkeys require a secure context (HTTPS or localhost). Please enable HTTPS or access via localhost.", "error");
    return;
  }
  try {
    let usernameOrEmail = "";
    const loginModal = document.getElementById("modal-login");
    const signupModal = document.getElementById("modal-signup");
    
    if (loginModal && loginModal.open) {
      const emailInput = document.getElementById("login-email");
      if (emailInput && emailInput.value) {
        usernameOrEmail = emailInput.value.trim();
      }
    } else if (signupModal && signupModal.open) {
      const emailInput = document.getElementById("sup-email");
      if (emailInput && emailInput.value) {
        usernameOrEmail = emailInput.value.trim();
      }
    }
    
    showToast("Requesting authentication challenge...");
    const options = await apiFetch("/auth/webauthn/login/challenge", {
      method: "POST",
      body: { username: usernameOrEmail, email: usernameOrEmail }
    });
    if (!options || !options.publicKey) {
      throw new Error(options.error || "Failed to get authentication options");
    }
    
    prepareAuthenticationOptions(options);
    
    showToast("Please interact with your authenticator...");
    const assertion = await navigator.credentials.get({
      publicKey: options.publicKey
    });
    
    const formatted = formatAuthenticationResponse(assertion);
    
    showToast("Verifying login...");
    const loginResult = await apiFetch("/auth/webauthn/login/verify", {
      method: "POST",
      body: formatted
    });
    
    if (loginResult && loginResult.token) {
      currentToken = loginResult.token;
      localStorage.setItem("gd_token", currentToken);
      currentUser = loginResult.user;
      
      showToast("🎉 Logged in successfully with Passkey!");
      closeModal("modal-login");
      closeModal("modal-signup");
      
      updateAuthUI(currentUser);
      window.location.hash = "#/feed";
    } else {
      throw new Error(loginResult.error || "Login verification failed");
    }
  } catch (err) {
    console.error("Passkey login error:", err);
    showToast("❌ Passkey login failed: " + err.message, "error");
  }
}

window.registerPasskey = registerPasskey;
window.loginWithPasskey = loginWithPasskey;
window.getCurrentSpaceContextId = getCurrentSpaceContextId;

function adjustPasskeyButtonsSupport() {
  if (!window.PublicKeyCredential || !navigator.credentials) {
    const buttons = [
      ...document.querySelectorAll(".btn-passkey-login"),
      document.getElementById("btn-register-passkey")
    ].filter(Boolean);
    
    buttons.forEach(btn => {
      btn.classList.add("opacity-70");
      btn.title = "Passkeys require a secure context (HTTPS or localhost) - Click for details";
    });
  }
}

/* ================= MODERATION & GOVERNANCE CONTROLS ================= */

async function deleteComment(commentId, itemId) {
  if (!confirm("Are you sure you want to delete this comment?")) return;
  try {
    await apiFetch(`/comments/${commentId}`, { method: "DELETE" });
    showToast("🗑️ Comment deleted.");
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

async function deleteGroupChatMessage(msgId) {
  if (!activeGroupId) return;
  if (!confirm("Are you sure you want to delete this chat message?")) return;
  try {
    await apiFetch(`/groups/${activeGroupId}/chat/${msgId}`, { method: "DELETE" });
    showToast("🗑️ Chat message deleted.");
    if (activeGroupData && activeGroupData.chat_messages) {
      activeGroupData.chat_messages = activeGroupData.chat_messages.filter(m => m.id !== msgId);
      renderGroupChatList();
    } else {
      await loadGroupDetail(activeGroupId);
    }
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function toggleUserBan(targetUserId, isBanned) {
  let purge = false;
  if (isBanned === 1) {
    if (!confirm("Are you sure you want to suspend this user account? Their active sessions will be terminated immediately.")) {
      return;
    }
    purge = confirm("Would you also like to purge all posts, comments, and chat messages authored by this user?");
  }
  try {
    await apiFetch(`/admin/users/${targetUserId}/ban`, {
      method: "POST",
      body: JSON.stringify({ is_banned: isBanned, purge_content: purge })
    });
    showToast(isBanned === 1 ? "🚫 User account suspended." : "✅ User account restored.");
    await loadUserProfile(targetUserId);
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function kickGroupMember(groupId, userId, username) {
  if (!confirm(`Remove "${username}" from this space?`)) return;
  const ban = confirm(`Prevent "${username}" from re-joining this space in the future?`);
  try {
    await apiFetch(`/groups/${groupId}/members/kick`, {
      method: "POST",
      body: JSON.stringify({ user_id: userId, ban })
    });
    showToast(ban ? `🚫 Removed and banned ${username} from space.` : `👋 Removed ${username} from space.`);
    await loadGroupDetail(groupId);
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

function openReportModal(targetType, targetId) {
  if (!currentUser) {
    showToast("Please log in to report content.");
    openModal("modal-login");
    return;
  }
  const typeEl = document.getElementById("report-target-type");
  const idEl = document.getElementById("report-target-id");
  const notesEl = document.getElementById("report-notes");
  if (typeEl) typeEl.value = targetType;
  if (idEl) idEl.value = targetId;
  if (notesEl) notesEl.value = "";
  openModal("modal-report-content");
}

async function submitContentReport(e) {
  e.preventDefault();
  const targetType = document.getElementById("report-target-type").value;
  const targetId = document.getElementById("report-target-id").value;
  const reason = document.getElementById("report-reason").value;
  const notes = document.getElementById("report-notes").value;

  try {
    await apiFetch("/reports", {
      method: "POST",
      body: JSON.stringify({
        target_type: targetType,
        target_id: Number(targetId),
        reason,
        notes
      })
    });
    closeModal("modal-report-content");
    showToast("🚩 Thank you. Your report has been submitted to the moderation team.");
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function loadModerationQueue() {
  const container = document.getElementById("moderation-queue-list");
  if (!container) return;
  container.innerHTML = `<p class="text-stone-500 font-bold text-center py-12">Loading moderation reports...</p>`;
  try {
    const data = await apiFetch("/admin/reports");
    const reports = data.reports || [];
    if (reports.length === 0) {
      container.innerHTML = `
        <div class="bg-white p-12 rounded-3xl border border-stone-200 text-center space-y-2">
          <div class="text-4xl">🎉</div>
          <h3 class="text-2xl font-black text-stone-800">All clear!</h3>
          <p class="text-stone-500 font-medium">There are no pending content reports in the moderation queue.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = reports.map(rep => {
      const isPending = rep.status === "PENDING";
      const statusBadge = isPending
        ? `<span class="px-3 py-1 bg-amber-100 text-amber-900 font-black text-xs rounded-full uppercase">⏳ Pending Review</span>`
        : `<span class="px-3 py-1 bg-stone-200 text-stone-700 font-bold text-xs rounded-full uppercase">✓ ${rep.status}</span>`;

      return `
        <div class="bg-white p-6 rounded-3xl border-2 ${isPending ? "border-amber-300 shadow-md" : "border-stone-200 opacity-75"} flex flex-col md:flex-row justify-between gap-6">
          <div class="space-y-2 flex-1">
            <div class="flex flex-wrap items-center gap-2">
              ${statusBadge}
              <span class="px-3 py-1 bg-indigo-50 text-indigo-800 font-bold text-xs rounded-full border border-indigo-200">Type: ${escapeHtml(rep.target_type)} #${rep.target_id}</span>
              <span class="text-xs text-stone-400 font-bold">Reported by @${escapeHtml(rep.reporter_name || "member")} • ${escapeHtml(rep.created_at)}</span>
            </div>
            <div class="text-lg font-black text-stone-900">${escapeHtml(rep.reason)}</div>
            ${rep.notes ? `<p class="text-sm text-stone-600 italic bg-stone-50 p-3 rounded-xl border border-stone-200">"${escapeHtml(rep.notes)}"</p>` : ""}
            <div class="bg-stone-100 p-4 rounded-2xl border border-stone-200 text-sm font-medium text-stone-800">
              <div class="text-xs font-extrabold uppercase text-stone-400 mb-1">Reported Content Snippet ${rep.target_author_name ? `(Author: @${escapeHtml(rep.target_author_name)})` : ""}:</div>
              <div class="whitespace-pre-line">${escapeHtml(rep.content_snippet)}</div>
            </div>
          </div>
          ${isPending ? `
            <div class="flex flex-col gap-2 shrink-0 justify-center">
              <button onclick="resolveReport(${rep.id}, 'DISMISS')" class="px-5 py-2.5 bg-stone-200 hover:bg-stone-300 text-stone-800 font-bold text-xs rounded-xl transition touch-target">✅ Dismiss Report</button>
              <button onclick="resolveReport(${rep.id}, 'DELETE_CONTENT')" class="px-5 py-2.5 bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs rounded-xl transition touch-target">🗑️ Delete Content</button>
              <button onclick="resolveReport(${rep.id}, 'BAN_AUTHOR')" class="px-5 py-2.5 bg-red-600 hover:bg-red-700 text-white font-black text-xs rounded-xl transition touch-target">🚫 Delete & Ban Author</button>
            </div>
          ` : ""}
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<p class="text-red-600 font-bold text-center py-8">❌ ${err.message}</p>`;
  }
}

async function resolveReport(reportId, action) {
  try {
    await apiFetch(`/admin/reports/${reportId}/resolve`, {
      method: "POST",
      body: JSON.stringify({ action })
    });
    showToast(`🛡️ Report #${reportId} resolved (${action}).`);
    await loadModerationQueue();
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

window.deleteComment = deleteComment;
window.deleteGroupChatMessage = deleteGroupChatMessage;
window.toggleUserBan = toggleUserBan;
window.kickGroupMember = kickGroupMember;
window.openReportModal = openReportModal;
window.submitContentReport = submitContentReport;
window.loadModerationQueue = loadModerationQueue;
window.resolveReport = resolveReport;

/* ================= REAL-TIME IN-APP NOTIFICATIONS ================= */

let notificationsPollTimer = null;
let lastSeenNotifId = 0;

function startNotificationsPolling() {
  stopNotificationsPolling();
  notificationsPollTimer = setInterval(() => {
    if (currentUser) {
      loadNotifications(true);
    }
  }, 15000);
}

function stopNotificationsPolling() {
  if (notificationsPollTimer) {
    clearInterval(notificationsPollTimer);
    notificationsPollTimer = null;
  }
}

function toggleNotificationsDropdown() {
  const menu = document.getElementById("notifications-dropdown-menu");
  if (!menu) return;
  menu.classList.toggle("hidden");
}

async function loadNotifications(showToastForNew = false) {
  if (!currentUser) return;
  try {
    const data = await apiFetch("/notifications");
    const list = data.notifications || [];
    const unread = data.unread_count || 0;

    const badge = document.getElementById("notifications-unread-badge");
    if (badge) {
      if (unread > 0) {
        badge.textContent = unread > 99 ? "99+" : String(unread);
        badge.classList.remove("hidden");
      } else {
        badge.classList.add("hidden");
      }
    }

    if (list.length > 0) {
      const newestId = list[0].id;
      if (showToastForNew && lastSeenNotifId > 0 && newestId > lastSeenNotifId && list[0].is_read === 0) {
        showToast(list[0].message);
      }
      if (newestId > lastSeenNotifId) {
        lastSeenNotifId = newestId;
      }
    }

    const container = document.getElementById("notifications-list");
    if (!container) return;
    if (list.length === 0) {
      container.innerHTML = `<p class="px-4 py-6 text-center text-stone-400 text-sm font-medium">No notifications yet</p>`;
      return;
    }

    container.innerHTML = list.map(n => `
      <div onclick="handleNotificationClick(${n.id}, '${escapeHtml(n.link_hash || '')}')" class="px-4 py-3 hover:bg-amber-50/70 transition cursor-pointer flex items-start space-x-3 ${n.is_read === 0 ? "bg-amber-50/40 font-bold" : "opacity-80"}">
        <div class="flex-1 min-w-0">
          <p class="text-xs sm:text-sm text-stone-800 leading-snug break-words">${escapeHtml(n.message)}</p>
          <span class="text-[11px] text-stone-400 font-medium block mt-1">${escapeHtml(n.created_at)}</span>
        </div>
        ${n.is_read === 0 ? `<span class="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0 mt-1.5"></span>` : ""}
      </div>
    `).join("");
  } catch (err) {
    // Silent fail on background poll
  }
}

async function markAllNotificationsRead() {
  try {
    await apiFetch("/notifications/read", {
      method: "POST",
      body: JSON.stringify({})
    });
    await loadNotifications(false);
  } catch (err) {
    showToast("❌ " + err.message);
  }
}

async function handleNotificationClick(notifId, linkHash) {
  try {
    await apiFetch("/notifications/read", {
      method: "POST",
      body: JSON.stringify({ id: notifId })
    });
    await loadNotifications(false);
  } catch (e) {}
  const menu = document.getElementById("notifications-dropdown-menu");
  if (menu) menu.classList.add("hidden");
  if (linkHash) {
    window.location.hash = linkHash.startsWith("#") ? linkHash : linkHash.replace(/^\/#/, "#");
  }
}

window.loadNotifications = loadNotifications;
window.markAllNotificationsRead = markAllNotificationsRead;
window.handleNotificationClick = handleNotificationClick;
window.toggleNotificationsDropdown = toggleNotificationsDropdown;
window.startNotificationsPolling = startNotificationsPolling;
window.stopNotificationsPolling = stopNotificationsPolling;


