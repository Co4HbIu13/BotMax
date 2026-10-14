/**
 * BotMAX Studio — Admin Control Dashboard Logic
 * Multi-Tenant Organizer Hierarchy & Multi-Lot Raffles
 */

(function () {
  "use strict";

  // State
  let adminToken = localStorage.getItem("botmax_admin_token") || "";
  let currentAdmin = null;
  let rafflesList = [];
  let adminsList = [];
  let currentFilter = "all";
  let currentMainTab = "raffles";
  let activeDrawRaffleId = null;

  // Multi-prize state in Create Modal
  let currentPrizes = [];

  // DOM Elements - Auth Screen
  const authScreen = document.getElementById("authScreen");
  const adminApp = document.getElementById("adminApp");
  const loginForm = document.getElementById("loginForm");
  const adminUsernameInput = document.getElementById("adminUsername");
  const adminPasswordInput = document.getElementById("adminPassword");
  const togglePasswordBtn = document.getElementById("togglePasswordBtn");
  const loginBtn = document.getElementById("loginBtn");
  const authErrorMsg = document.getElementById("authErrorMsg");
  const logoutBtn = document.getElementById("logoutBtn");
  const themeToggleBtn = document.getElementById("themeToggleBtn");
  const themeIcon = document.getElementById("themeIcon");

  // Top Bar User Pill & Profile
  const currentUserPill = document.getElementById("currentUserPill");
  const currentUserRoleBadge = document.getElementById("currentUserRoleBadge");
  const currentUserName = document.getElementById("currentUserName");
  const openProfileBtn = document.getElementById("openProfileBtn");

  // SuperAdmin Tabs & Sections
  const superadminNavTabs = document.getElementById("superadminNavTabs");
  const tabShowRaffles = document.getElementById("tabShowRaffles");
  const tabShowAdmins = document.getElementById("tabShowAdmins");
  const countAdminsNav = document.getElementById("countAdminsNav");
  const rafflesSection = document.getElementById("rafflesSection");
  const rafflesSectionDesc = document.getElementById("rafflesSectionDesc");
  const adminsSection = document.getElementById("adminsSection");
  const adminsListContainer = document.getElementById("adminsListContainer");
  const emptyAdminsState = document.getElementById("emptyAdminsState");
  const openCreateAdminModalBtn = document.getElementById("openCreateAdminModalBtn");
  const emptyCreateAdminBtn = document.getElementById("emptyCreateAdminBtn");

  // Metrics
  const statTotalRaffles = document.getElementById("statTotalRaffles");
  const statActiveRaffles = document.getElementById("statActiveRaffles");
  const statSoldTickets = document.getElementById("statSoldTickets");
  const statTicketsRatio = document.getElementById("statTicketsRatio");
  const statTotalRevenue = document.getElementById("statTotalRevenue");
  const statTotalGroups = document.getElementById("statTotalGroups");
  const statTotalUsers = document.getElementById("statTotalUsers");

  // Raffles Tabs & Grid
  const statusTabs = document.querySelectorAll(".status-tab");
  const countAll = document.getElementById("countAll");
  const countActive = document.getElementById("countActive");
  const countCompleted = document.getElementById("countCompleted");
  const rafflesGrid = document.getElementById("rafflesGrid");
  const emptyRafflesState = document.getElementById("emptyRafflesState");
  const refreshBtn = document.getElementById("refreshBtn");
  const broadcastShowcaseBtn = document.getElementById("broadcastShowcaseBtn");

  // Create Raffle Modal
  const createModal = document.getElementById("createModal");
  const openCreateModalBtn = document.getElementById("openCreateModalBtn");
  const emptyCreateBtn = document.getElementById("emptyCreateBtn");
  const closeCreateModalBtn = document.getElementById("closeCreateModalBtn");
  const cancelCreateBtn = document.getElementById("cancelCreateBtn");
  const submitCreateBtn = document.getElementById("submitCreateBtn");
  const createRaffleForm = document.getElementById("createRaffleForm");
  const raffleTitle = document.getElementById("raffleTitle");
  const raffleDesc = document.getElementById("raffleDesc");
  const totalTickets = document.getElementById("totalTickets");
  const pricePerTicket = document.getElementById("pricePerTicket");
  const calcPoolTotal = document.getElementById("calcPoolTotal");

  // Live Preview Elements
  const prevImg = document.getElementById("prevImg");
  const prevBadge = document.getElementById("prevBadge");
  const prevTitle = document.getElementById("prevTitle");
  const prevPrice = document.getElementById("prevPrice");
  const prevCountLabel = document.getElementById("prevCountLabel");

  // Draw Modal
  const drawModal = document.getElementById("drawModal");
  const closeDrawModalBtn = document.getElementById("closeDrawModalBtn");
  const closeDrawBtn = document.getElementById("closeDrawBtn");
  const drawRaffleTitle = document.getElementById("drawRaffleTitle");
  const drawTotalTickets = document.getElementById("drawTotalTickets");
  const drawSoldTickets = document.getElementById("drawSoldTickets");
  const startDrawBtn = document.getElementById("startDrawBtn");
  const drawInitialState = document.getElementById("drawInitialState");
  const drawRollingState = document.getElementById("drawRollingState");
  const drawWinnerState = document.getElementById("drawWinnerState");
  const rouletteDrum = document.getElementById("rouletteDrum");

  // Tickets Inspect Modal
  const ticketsModal = document.getElementById("ticketsModal");
  const closeTicketsModalBtn = document.getElementById("closeTicketsModalBtn");
  const closeTicketsBtn = document.getElementById("closeTicketsBtn");
  const ticketsRaffleTitle = document.getElementById("ticketsRaffleTitle");
  const ticketsInspectGrid = document.getElementById("ticketsInspectGrid");

  // Create Admin Modal Elements
  const createAdminModal = document.getElementById("createAdminModal");
  const closeCreateAdminModalBtn = document.getElementById("closeCreateAdminModalBtn");
  const cancelCreateAdminBtn = document.getElementById("cancelCreateAdminBtn");
  const submitCreateAdminBtn = document.getElementById("submitCreateAdminBtn");
  const createAdminForm = document.getElementById("createAdminForm");
  const newAdminUsername = document.getElementById("newAdminUsername");
  const newAdminPassword = document.getElementById("newAdminPassword");
  const newAdminDisplayName = document.getElementById("newAdminDisplayName");
  const newAdminSbpPhone = document.getElementById("newAdminSbpPhone");
  const newAdminSbpBank = document.getElementById("newAdminSbpBank");
  const createAdminErrorMsg = document.getElementById("createAdminErrorMsg");

  // Profile / SBP Modal Elements
  const profileModal = document.getElementById("profileModal");
  const closeProfileModalBtn = document.getElementById("closeProfileModalBtn");
  const closeProfileBtn = document.getElementById("closeProfileBtn");
  const saveProfileBtn = document.getElementById("saveProfileBtn");
  const profileForm = document.getElementById("profileForm");
  const profileUsername = document.getElementById("profileUsername");
  const profileDisplayName = document.getElementById("profileDisplayName");
  const profileSbpPhone = document.getElementById("profileSbpPhone");
  const profileSbpBank = document.getElementById("profileSbpBank");
  const profileNewPassword = document.getElementById("profileNewPassword");
  const profileSuccessMsg = document.getElementById("profileSuccessMsg");

  const toastContainer = document.getElementById("toastContainer");

  // ========================================================
  // INITIALIZATION
  // ========================================================
  function init() {
    initTheme();
    checkAuthSession();
    bindEvents();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  // ========================================================
  // THEME & SENIOR ACCESSIBILITY MODE
  // ========================================================
  function initTheme() {
    const saved = localStorage.getItem("botmax_admin_theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);
    if (themeIcon) {
      themeIcon.textContent = saved === "dark" ? "☀️" : "🌙";
    }
    initSeniorMode();
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute("data-theme");
    const next = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("botmax_admin_theme", next);
    if (themeIcon) {
      themeIcon.textContent = next === "dark" ? "☀️" : "🌙";
    }
  }

  function initSeniorMode() {
    const isSenior = localStorage.getItem("botmax_senior_mode") === "true";
    if (isSenior) {
      document.body.classList.add("senior-mode");
      updateSeniorModeUI(true);
    }
  }

  function toggleSeniorMode() {
    const isNowSenior = document.body.classList.toggle("senior-mode");
    localStorage.setItem("botmax_senior_mode", isNowSenior ? "true" : "false");
    updateSeniorModeUI(isNowSenior);
    showToast(isNowSenior ? "👓 Включен крупный шрифт" : "👓 Стандартный шрифт", "info");
  }

  function updateSeniorModeUI(isSenior) {
    const navBtn = document.getElementById("seniorModeToggleBtn");
    if (navBtn) {
      navBtn.classList.toggle("active", isSenior);
    }
    const mbSenior = document.getElementById("mbNavSenior");
    if (mbSenior) {
      mbSenior.classList.toggle("active", isSenior);
    }
  }

  // ========================================================
  // AUTHENTICATION & PROFILE
  // ========================================================
  async function checkAuthSession() {
    const rememberedUser = localStorage.getItem("botmax_admin_username");
    if (rememberedUser && adminUsernameInput) {
      adminUsernameInput.value = rememberedUser;
    }

    if (!adminToken) {
      showAuthScreen();
      return;
    }

    try {
      const res = await fetch("/api/admin/me", {
        headers: { "Authorization": `Bearer ${adminToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        currentAdmin = data.admin;
        showDashboard();
      } else {
        localStorage.removeItem("botmax_admin_token");
        adminToken = "";
        currentAdmin = null;
        showAuthScreen();
      }
    } catch (e) {
      showAuthScreen();
    }
  }

  function showAuthScreen() {
    authScreen.classList.remove("hidden");
    adminApp.classList.add("hidden");
  }

  function showDashboard() {
    authScreen.classList.add("hidden");
    adminApp.classList.remove("hidden");

    applyRoleUI();
    loadDashboardStats();
    loadRaffles();

    if (currentAdmin && currentAdmin.role === "superadmin") {
      loadAdminsList();
    }
  }

  function applyRoleUI() {
    if (!currentAdmin) return;

    if (currentUserName) {
      currentUserName.textContent = currentAdmin.display_name || currentAdmin.username;
    }

    if (currentUserRoleBadge) {
      if (currentAdmin.role === "superadmin") {
        currentUserRoleBadge.textContent = "👑 СуперАдмин";
        currentUserRoleBadge.className = "badge-role-pill role-superadmin";
      } else {
        currentUserRoleBadge.textContent = "👤 Организатор";
        currentUserRoleBadge.className = "badge-role-pill role-admin";
      }
    }

    if (currentAdmin.role === "superadmin") {
      if (superadminNavTabs) superadminNavTabs.classList.remove("hidden");
      if (rafflesSectionDesc) {
        rafflesSectionDesc.textContent = "Просмотр и управление играми всех организаторов платформы";
      }
    } else {
      if (superadminNavTabs) superadminNavTabs.classList.add("hidden");
      if (rafflesSectionDesc) {
        rafflesSectionDesc.textContent = "Ваши личные игры и розыгрыши. Все средства за билеты поступают на ваш СБП";
      }
      switchMainTab("raffles");
    }
  }

  async function handleLogin() {
    const username = adminUsernameInput ? adminUsernameInput.value.trim() : "superadmin";
    const password = adminPasswordInput.value.trim();

    if (!username) {
      showAuthError("Введите логин администратора");
      return;
    }
    if (!password) {
      showAuthError("Введите пароль");
      return;
    }

    loginBtn.disabled = true;
    loginBtn.querySelector(".btn-text").classList.add("hidden");
    loginBtn.querySelector(".btn-spinner").classList.remove("hidden");
    hideAuthError();

    try {
      const res = await fetch("/api/admin/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        adminToken = data.token;
        const rememberCheckbox = document.getElementById("rememberMeCheckbox");
        if (rememberCheckbox && rememberCheckbox.checked) {
          localStorage.setItem("botmax_admin_token", adminToken);
          localStorage.setItem("botmax_admin_username", username);
        } else {
          sessionStorage.setItem("botmax_admin_token", adminToken);
          localStorage.removeItem("botmax_admin_username");
        }

        // Fetch full profile info
        const meRes = await fetch("/api/admin/me", {
          headers: { "Authorization": `Bearer ${adminToken}` },
        });
        if (meRes.ok) {
          const meData = await meRes.json();
          currentAdmin = meData.admin;
        } else {
          currentAdmin = {
            id: data.admin_id,
            username: data.username,
            display_name: data.display_name,
            role: data.role,
          };
        }

        showToast("Авторизация успешна!", "success");
        showDashboard();
      } else {
        showAuthError(data.detail || "Неверный логин или пароль");
      }
    } catch (err) {
      showAuthError("Ошибка подключения к серверу");
    } finally {
      loginBtn.disabled = false;
      loginBtn.querySelector(".btn-text").classList.remove("hidden");
      loginBtn.querySelector(".btn-spinner").classList.add("hidden");
    }
  }

  function handleLogout() {
    if (confirm("Вы уверены, что хотите выйти из панели управления?")) {
      fetch("/api/admin/auth/logout", {
        method: "POST",
        headers: { "Authorization": `Bearer ${adminToken}` },
      }).catch(() => {});
      localStorage.removeItem("botmax_admin_token");
      adminToken = "";
      currentAdmin = null;
      showAuthScreen();
      showToast("Сессия завершена", "info");
    }
  }

  function showAuthError(msg) {
    authErrorMsg.textContent = msg;
    authErrorMsg.classList.remove("hidden");
  }

  function hideAuthError() {
    authErrorMsg.classList.add("hidden");
  }

  // ========================================================
  // MAIN NAVIGATION TABS (SUPERADMIN: RAFFLES vs ADMINS)
  // ========================================================
  function switchMainTab(tabName) {
    currentMainTab = tabName;
    if (tabName === "admins") {
      tabShowRaffles?.classList.remove("active");
      tabShowAdmins?.classList.add("active");
      rafflesSection?.classList.add("hidden");
      adminsSection?.classList.remove("hidden");
      loadAdminsList();
    } else {
      tabShowAdmins?.classList.remove("active");
      tabShowRaffles?.classList.add("active");
      adminsSection?.classList.add("hidden");
      rafflesSection?.classList.remove("hidden");
      loadRaffles();
    }
  }

  // ========================================================
  // DASHBOARD DATA FETCHING
  // ========================================================
  async function loadDashboardStats() {
    try {
      const res = await fetch("/api/admin/stats", {
        headers: { "Authorization": `Bearer ${adminToken}` },
      });
      if (res.status === 401) {
        showAuthScreen();
        return;
      }
      const data = await res.json();
      if (data.success && data.stats) {
        renderStats(data.stats);
      }
    } catch (e) {
      console.error("Failed to load admin stats:", e);
    }
  }

  function renderStats(s) {
    statTotalRaffles.textContent = s.total_raffles || 0;
    statActiveRaffles.textContent = `${s.active_raffles || 0} активных в игре`;
    statSoldTickets.textContent = s.sold_tickets || 0;

    const percent = s.total_tickets > 0 ? Math.round((s.sold_tickets / s.total_tickets) * 100) : 0;
    statTicketsRatio.textContent = `${percent}% от пула (${s.sold_tickets}/${s.total_tickets})`;

    statTotalRevenue.textContent = `${(s.total_revenue || 0).toLocaleString("ru-RU")} ₽`;
    statTotalGroups.textContent = s.total_groups || 0;
    statTotalUsers.textContent = `${s.total_users || 0} участников`;
  }

  async function loadRaffles() {
    try {
      const res = await fetch("/api/admin/raffles", {
        headers: { "Authorization": `Bearer ${adminToken}` },
      });
      if (res.status === 401) {
        showAuthScreen();
        return;
      }
      const data = await res.json();
      if (data.success) {
        rafflesList = data.raffles || [];
        updateTabsCounters();
        renderRafflesGrid();
      }
    } catch (e) {
      console.error("Failed to load raffles:", e);
      showToast("Не удалось загрузить список игр", "error");
    }
  }

  function updateTabsCounters() {
    const total = rafflesList.length;
    const active = rafflesList.filter(r => r.status === "active").length;
    const completed = rafflesList.filter(r => r.status === "completed").length;

    countAll.textContent = total;
    countActive.textContent = active;
    countCompleted.textContent = completed;
  }

  function renderRafflesGrid() {
    const filtered = rafflesList.filter(r => {
      if (currentFilter === "active") return r.status === "active";
      if (currentFilter === "completed") return r.status === "completed";
      return true;
    });

    if (filtered.length === 0) {
      rafflesGrid.innerHTML = "";
      emptyRafflesState.classList.remove("hidden");
      return;
    }

    emptyRafflesState.classList.add("hidden");
    rafflesGrid.innerHTML = filtered.map(r => createRaffleCardHtml(r)).join("");
  }

  function createRaffleCardHtml(r) {
    const isCompleted = r.status === "completed";
    const statusBadge = isCompleted
      ? `<span class="card-badge-status badge-completed">🏆 Завершен</span>`
      : `<span class="card-badge-status badge-active">🟢 В игре</span>`;

    const percent = r.percent_sold || 0;
    const revenue = ((r.sold_tickets || 0) * (r.price_per_ticket || 0)).toLocaleString("ru-RU");

    const prizes = r.prizes || [];
    const count = prizes.length;
    const lotBadgeText = count > 1 ? `🏆 ${count} призовых места` : `🏷️ Лот №${r.lot_number || 1}`;
    const mainImg = (prizes[0] && prizes[0].prize_image_url) ? prizes[0].prize_image_url : r.prize_image_url;

    const medalMap = { 1: "🥇", 2: "🥈", 3: "🥉" };

    let prizesHtml = "";
    if (count > 0) {
      prizesHtml = `
        <div class="card-prizes-summary">
          ${prizes.map(p => `
            <div class="card-prize-pill">
              <span>${medalMap[p.place] || '🏅'}</span>
              <strong>${p.place}м (Лот №${p.lot_number || p.place}):</strong> ${escapeHtml(p.title)}
            </div>
          `).join('')}
        </div>
      `;
    }

    // Organizer pill info
    const creatorName = r.creator_name || "Организатор";
    const creatorUser = r.creator_username ? `@${r.creator_username}` : "";
    const sbpInfo = r.creator_sbp_phone ? `• 💳 СБП: ${escapeHtml(r.creator_sbp_phone)} (${escapeHtml(r.creator_sbp_bank || 'Банк')})` : "";
    const organizerPill = `
      <div class="card-organizer-pill">
        <span>👤</span> <strong>${escapeHtml(creatorName)}</strong> ${escapeHtml(creatorUser)} ${sbpInfo}
      </div>
    `;

    let winnerBanner = "";
    if (isCompleted) {
      if (prizes.length > 0 && prizes[0].winner_ticket_number) {
        winnerBanner = `
          <div class="winner-banner">
            ${prizes.map(p => `
              <div>${medalMap[p.place] || '🏅'} ${p.place}м (${escapeHtml(p.title)}): <strong>#${p.winner_ticket_number}</strong> — @${escapeHtml(p.winner_username || "участник")}</div>
            `).join('')}
          </div>
        `;
      } else {
        winnerBanner = `
          <div class="winner-banner">
            <span>🏆</span>
            <div>Победитель: <strong>#${r.winner_ticket_number}</strong> — @${escapeHtml(r.winner_username || "участник")}</div>
          </div>
        `;
      }
    }

    const drawButton = !isCompleted ? `
      <button class="btn-primary-action-lg" onclick="window.botmaxAdmin.openDrawModal('${r.id}')">
        <span>🎲</span> ВЫБРАТЬ ПОБЕДИТЕЛЯ
      </button>
    ` : `
      <div class="winner-trophy-badge">
        <span>🏆</span> Розыгрыш проведен
      </div>
    `;

    return `
      <div class="raffle-manage-card" data-id="${r.id}">
        <div class="card-media-wrap">
          <img src="${escapeHtml(mainImg)}" alt="${escapeHtml(r.title)}" class="card-img" onerror="this.src='https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=800&q=80'">
          ${statusBadge}
          <span class="card-badge-lot">${lotBadgeText}</span>
        </div>

        <div class="card-body">
          <h3 class="card-title">${escapeHtml(r.title)}</h3>
          ${organizerPill}
          ${prizesHtml}

          <div class="card-price-row">
            <span class="card-price-val">${r.price_per_ticket} ₽</span>
            <span class="card-price-label">за 1 билет | Сбор: ${revenue} ₽</span>
          </div>

          <div class="card-progress-box">
            <div class="progress-bar-bg">
              <div class="progress-bar-fill" style="width: ${percent}%;"></div>
            </div>
            <div class="progress-stats-row">
              <span>Продано: <strong>${r.sold_tickets || 0} из ${r.total_tickets} билетов</strong></span>
              <span>${percent}%</span>
            </div>
          </div>

          ${winnerBanner}

          <div class="card-actions-stack">
            ${drawButton}
            <div class="card-secondary-actions-row">
              <button class="btn-card-action-sub" onclick="window.botmaxAdmin.inspectTickets('${r.id}')">
                <span>📋</span> Билеты
              </button>
              <button class="btn-card-action-sub" onclick="window.botmaxAdmin.broadcastRaffle('${r.id}')" title="Опубликовать в группах MAX">
                <span>📢</span> В группу
              </button>
              <button class="btn-card-action-sub danger" onclick="window.botmaxAdmin.deleteRaffle('${r.id}')" title="Удалить розыгрыш">
                <span>🗑️</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // ========================================================
  // ADMINS & ORGANIZERS MANAGEMENT (SUPERADMIN ONLY)
  // ========================================================
  async function loadAdminsList() {
    if (!currentAdmin || currentAdmin.role !== "superadmin") return;

    try {
      const res = await fetch("/api/admin/users", {
        headers: { "Authorization": `Bearer ${adminToken}` },
      });
      if (res.status === 401) {
        showAuthScreen();
        return;
      }
      const data = await res.json();
      if (res.ok && data.success) {
        adminsList = data.admins || [];
        if (countAdminsNav) {
          countAdminsNav.textContent = adminsList.length;
        }
        renderAdminsGrid();
      }
    } catch (e) {
      console.error("Failed to load admins:", e);
      showToast("Не удалось загрузить список организаторов", "error");
    }
  }

  function renderAdminsGrid() {
    if (!adminsListContainer) return;

    if (adminsList.length === 0) {
      adminsListContainer.innerHTML = "";
      emptyAdminsState?.classList.remove("hidden");
      return;
    }

    emptyAdminsState?.classList.add("hidden");
    adminsListContainer.innerHTML = adminsList.map(a => {
      const isSuper = a.role === "superadmin";
      const roleBadge = isSuper
        ? `<span class="user-role-badge">👑 СуперАдмин</span>`
        : `<span class="user-role-badge role-admin">👤 Организатор</span>`;

      const deleteBtn = !isSuper ? `
        <button class="btn-delete-admin" onclick="window.botmaxAdmin.deleteAdminUser('${a.id}', '${escapeHtml(a.display_name)}')">
          🗑️ Удалить доступ
        </button>
      ` : `<span style="font-size:12px;color:var(--text-dim);">Главный аккаунт</span>`;

      const sbpPhone = a.sbp_phone || "Не указан";
      const sbpBank = a.sbp_bank || "Т-Банк";
      const totalRevenue = ((a.total_revenue || 0)).toLocaleString("ru-RU");

      return `
        <div class="admin-card" data-admin-id="${a.id}">
          <div class="admin-card-header">
            <div class="admin-card-title-group">
              <span class="admin-card-name">${escapeHtml(a.display_name)}</span>
              <span class="admin-card-username">@${escapeHtml(a.username)}</span>
            </div>
            ${roleBadge}
          </div>

          <div class="admin-sbp-box">
            <span class="admin-sbp-label">📲 СБП для начисления денег</span>
            <span class="admin-sbp-details">${escapeHtml(sbpPhone)} (${escapeHtml(sbpBank)})</span>
          </div>

          <div class="admin-card-stats">
            <div class="admin-stat-item">
              <span class="admin-stat-number">${a.active_raffles || 0} / ${a.total_raffles || 0}</span>
              <span class="admin-stat-label">Активных / Всего игр</span>
            </div>
            <div class="admin-stat-item">
              <span class="admin-stat-number">${totalRevenue} ₽</span>
              <span class="admin-stat-label">СБП Выручка (${a.sold_tickets || 0} бил.)</span>
            </div>
          </div>

          <div class="admin-card-actions">
            ${deleteBtn}
          </div>
        </div>
      `;
    }).join("");
  }

  function openCreateAdminModal() {
    createAdminForm.reset();
    createAdminErrorMsg?.classList.add("hidden");
    createAdminModal?.classList.remove("hidden");
  }

  function closeCreateAdminModal() {
    createAdminModal?.classList.add("hidden");
  }

  async function handleCreateAdminSubmit() {
    const username = newAdminUsername.value.trim();
    const password = newAdminPassword.value.trim();
    const displayName = newAdminDisplayName.value.trim();
    const sbpPhone = newAdminSbpPhone.value.trim();
    const sbpBank = newAdminSbpBank.value.trim() || "Т-Банк";

    if (!username || !password || !displayName) {
      if (createAdminErrorMsg) {
        createAdminErrorMsg.textContent = "Заполните логин, пароль и имя организатора!";
        createAdminErrorMsg.classList.remove("hidden");
      }
      return;
    }

    submitCreateAdminBtn.disabled = true;
    submitCreateAdminBtn.querySelector(".btn-text").classList.add("hidden");
    submitCreateAdminBtn.querySelector(".btn-spinner").classList.remove("hidden");
    createAdminErrorMsg?.classList.add("hidden");

    try {
      const res = await fetch("/api/admin/users", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${adminToken}`,
        },
        body: JSON.stringify({
          username,
          password,
          display_name: displayName,
          sbp_phone: sbpPhone,
          sbp_bank: sbpBank,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`Организатор «${displayName}» успешно создан!`, "success");
        closeCreateAdminModal();
        loadAdminsList();
      } else {
        if (createAdminErrorMsg) {
          createAdminErrorMsg.textContent = data.detail || "Ошибка при создании организатора";
          createAdminErrorMsg.classList.remove("hidden");
        }
      }
    } catch (e) {
      if (createAdminErrorMsg) {
        createAdminErrorMsg.textContent = "Ошибка соединения с сервером";
        createAdminErrorMsg.classList.remove("hidden");
      }
    } finally {
      submitCreateAdminBtn.disabled = false;
      submitCreateAdminBtn.querySelector(".btn-text").classList.remove("hidden");
      submitCreateAdminBtn.querySelector(".btn-spinner").classList.add("hidden");
    }
  }

  async function deleteAdminUser(adminId, adminName) {
    if (!confirm(`Вы действительно хотите удалить профиль организатора «${adminName}»?\n\nВсе созданные им розыгрыши останутся сохранены и будут переведены под контроль СуперАдмина.`)) {
      return;
    }

    try {
      const res = await fetch(`/api/admin/users/${adminId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${adminToken}` },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`Организатор «${adminName}» удален`, "success");
        loadAdminsList();
        loadRaffles();
        loadDashboardStats();
      } else {
        alert(data.detail || "Ошибка удаления организатора");
      }
    } catch (e) {
      alert("Ошибка соединения с сервером");
    }
  }

  // ========================================================
  // PROFILE & SBP SETTINGS MODAL
  // ========================================================
  function openProfileModal() {
    if (!currentAdmin) return;

    if (profileUsername) profileUsername.value = currentAdmin.username || "";
    if (profileDisplayName) profileDisplayName.value = currentAdmin.display_name || "";
    if (profileSbpPhone) profileSbpPhone.value = currentAdmin.sbp_phone || "";
    if (profileSbpBank) profileSbpBank.value = currentAdmin.sbp_bank || "Т-Банк";
    if (profileNewPassword) profileNewPassword.value = "";
    if (profileSuccessMsg) profileSuccessMsg.classList.add("hidden");

    profileModal?.classList.remove("hidden");
  }

  function closeProfileModal() {
    profileModal?.classList.add("hidden");
  }

  async function handleSaveProfileSubmit() {
    const displayName = profileDisplayName.value.trim();
    const sbpPhone = profileSbpPhone.value.trim();
    const sbpBank = profileSbpBank.value.trim();
    const newPassword = profileNewPassword.value.trim();

    saveProfileBtn.disabled = true;
    saveProfileBtn.querySelector(".btn-text").classList.add("hidden");
    saveProfileBtn.querySelector(".btn-spinner").classList.remove("hidden");

    const payload = {};
    if (displayName) payload.display_name = displayName;
    if (sbpPhone !== undefined) payload.sbp_phone = sbpPhone;
    if (sbpBank !== undefined) payload.sbp_bank = sbpBank;
    if (newPassword) payload.password = newPassword;

    try {
      const res = await fetch("/api/admin/me", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${adminToken}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        currentAdmin = data.admin;
        applyRoleUI();
        if (profileSuccessMsg) profileSuccessMsg.classList.remove("hidden");
        showToast("Реквизиты СБП и профиль сохранены!", "success");
        setTimeout(closeProfileModal, 1200);
      } else {
        alert(data.detail || "Ошибка сохранения профиля");
      }
    } catch (e) {
      alert("Ошибка отправки данных на сервер");
    } finally {
      saveProfileBtn.disabled = false;
      saveProfileBtn.querySelector(".btn-text").classList.remove("hidden");
      saveProfileBtn.querySelector(".btn-spinner").classList.add("hidden");
    }
  }

  // ========================================================
  // MULTI-PRIZE MANAGEMENT IN MODAL
  // ========================================================
  function initPrizesManager() {
    const addBtn = document.getElementById("addPrizePlaceBtn");
    addBtn?.addEventListener("click", addPrizePlace);
  }

  function addPrizePlace() {
    const nextPlace = currentPrizes.length + 1;
    currentPrizes.push({
      place: nextPlace,
      lot_number: nextPlace,
      title: "",
      prize_image_url: "https://images.unsplash.com/photo-1584990347449-399c51239bf0?auto=format&fit=crop&w=800&q=80",
      description: "",
    });
    renderPrizeItems();
  }

  function removePrize(idx) {
    if (currentPrizes.length <= 1) return;
    currentPrizes.splice(idx, 1);
    currentPrizes.forEach((p, i) => {
      p.place = i + 1;
      p.lot_number = i + 1;
    });
    renderPrizeItems();
  }

  function updatePrizeTitle(idx, val) {
    if (currentPrizes[idx]) {
      currentPrizes[idx].title = val;
      updateLivePreview();
    }
  }

  function updatePrizeDescription(idx, val) {
    if (currentPrizes[idx]) {
      currentPrizes[idx].description = val;
      updateLivePreview();
    }
  }

  function renderPrizeItems() {
    const container = document.getElementById("prizesItemsContainer");
    if (!container) return;

    const medalMap = { 1: "🥇", 2: "🥈", 3: "🥉" };

    container.innerHTML = currentPrizes.map((p, idx) => {
      const placeClass = p.place <= 3 ? `place-${p.place}` : "";
      const medal = medalMap[p.place] || "🏅";
      const removeBtn = currentPrizes.length > 1
        ? `<button type="button" class="btn-remove-prize" onclick="window.botmaxAdmin.removePrize(${idx})" title="Удалить это место">✕</button>`
        : "";

      return `
        <div class="prize-item-card" data-index="${idx}">
          <div class="prize-item-top">
            <span class="prize-place-badge ${placeClass}">
              <span>${medal}</span>
              <span>${p.place} место (Лот №${p.lot_number})</span>
            </span>
            ${removeBtn}
          </div>

          <div class="form-group mb-1">
            <input
              type="text"
              class="form-input prize-title-input"
              placeholder="Название приза (например: Сковорода Tefal 28см)"
              value="${escapeHtml(p.title)}"
              oninput="window.botmaxAdmin.updatePrizeTitle(${idx}, this.value)"
              required
            >
          </div>

          <div class="form-group mb-1">
            <input
              type="text"
              class="form-input prize-desc-input"
              placeholder="Описание лота (например: Антипригарное покрытие, новая в упаковке)"
              value="${escapeHtml(p.description || '')}"
              oninput="window.botmaxAdmin.updatePrizeDescription(${idx}, this.value)"
            >
          </div>

          <div class="prize-upload-row">
            <img src="${escapeHtml(p.prize_image_url || 'https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=800&q=80')}" class="prize-thumb-preview" id="prizeThumb_${idx}" alt="Превью" onerror="this.src='https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=800&q=80'">
            <div class="prize-upload-controls">
              <input type="file" id="prizeFileInput_${idx}" accept="image/*" class="file-input-hidden" onchange="window.botmaxAdmin.handlePrizeFileChange(${idx}, this)">
              <button type="button" class="btn-browse-file" onclick="document.getElementById('prizeFileInput_${idx}').click()">
                <span>📁</span> Загрузить фото с компьютера
              </button>
              <div id="prizeUploadStatus_${idx}" class="upload-status-text hidden"></div>
            </div>
          </div>
        </div>
      `;
    }).join("");

    updateLivePreview();
  }

  async function handlePrizeFileChange(idx, input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    if (!file.type.startsWith("image/")) {
      alert("Пожалуйста, выберите файл изображения (JPG, PNG, WebP)");
      return;
    }

    const statusEl = document.getElementById(`prizeUploadStatus_${idx}`);
    if (statusEl) {
      statusEl.textContent = "⏳ Загрузка фото на сервер...";
      statusEl.className = "upload-status-text uploading";
      statusEl.classList.remove("hidden");
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
      const base64Data = e.target.result;
      const thumb = document.getElementById(`prizeThumb_${idx}`);
      if (thumb) thumb.src = base64Data;

      try {
        const res = await fetch("/api/admin/upload-image", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${adminToken}`,
          },
          body: JSON.stringify({
            filename: file.name,
            image_data: base64Data,
          }),
        });

        const data = await res.json();
        if (res.ok && data.success) {
          currentPrizes[idx].prize_image_url = data.url;
          if (statusEl) {
            statusEl.textContent = `✓ Фото загружено на сервер (${file.name})`;
            statusEl.className = "upload-status-text success";
          }
          updateLivePreview();
          showToast(`Фото для ${idx + 1}-го места сохранено!`, "success");
        } else {
          if (statusEl) {
            statusEl.textContent = data.detail || "Ошибка загрузки фото";
            statusEl.className = "upload-status-text error";
          }
        }
      } catch (err) {
        if (statusEl) {
          statusEl.textContent = "Ошибка связи с сервером при загрузке";
          statusEl.className = "upload-status-text error";
        }
      }
    };
    reader.readAsDataURL(file);
  }

  function updateLivePreview() {
    const title = raffleTitle.value.trim() || "Название игры";
    const price = parseFloat(pricePerTicket.value) || 100;
    const tickets = parseInt(totalTickets.value, 10) || 50;

    prevTitle.textContent = title;
    prevPrice.textContent = `${price} ₽`;
    prevCountLabel.textContent = `Доступно: ${tickets}/${tickets}`;

    const count = currentPrizes.length;
    prevBadge.textContent = count > 1 ? `🏆 ${count} призовых места` : `🏷️ Лот №1`;

    const mainImg = currentPrizes[0]?.prize_image_url || "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=800&q=80";
    prevImg.src = mainImg;

    const prevPrizesList = document.getElementById("prevPrizesList");
    if (prevPrizesList) {
      const medalMap = { 1: "🥇", 2: "🥈", 3: "🥉" };
      prevPrizesList.innerHTML = currentPrizes.map(p => `
        <div class="prev-prize-row">
          <img src="${escapeHtml(p.prize_image_url || mainImg)}" class="prev-prize-thumb" alt="" onerror="this.src='${mainImg}'">
          <span><strong>${medalMap[p.place] || '🏅'} ${p.place}м (Лот ${p.lot_number}):</strong> ${escapeHtml(p.title || 'Приз')}</span>
        </div>
      `).join("");
    }

    const totalPool = (tickets * price).toLocaleString("ru-RU");
    calcPoolTotal.textContent = `${totalPool} ₽`;
    const formulaEl = document.querySelector(".calc-formula");
    if (formulaEl) {
      formulaEl.textContent = `(${tickets} билетов × ${price} ₽)`;
    }
  }

  function updateActiveChips() {
    const currTickets = totalTickets.value;
    document.querySelectorAll("[data-tickets]").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-tickets") === currTickets);
    });

    const currPrice = pricePerTicket.value;
    document.querySelectorAll("[data-price]").forEach(btn => {
      btn.classList.toggle("active", btn.getAttribute("data-price") === currPrice);
    });
  }

  async function handleCreateRaffleSubmit() {
    const title = raffleTitle.value.trim();
    const desc = raffleDesc.value.trim();
    const tickets = parseInt(totalTickets.value, 10);
    const price = parseFloat(pricePerTicket.value);

    if (!title || !tickets || !price) {
      alert("Пожалуйста, заполните название игры, количество билетов и цену!");
      return;
    }

    // Validate prizes
    for (let i = 0; i < currentPrizes.length; i++) {
      if (!currentPrizes[i].title.trim()) {
        alert(`Пожалуйста, введите название приза для ${i + 1}-го места (Лот №${i + 1})!`);
        return;
      }
    }

    submitCreateBtn.disabled = true;
    submitCreateBtn.querySelector(".btn-text").classList.add("hidden");
    submitCreateBtn.querySelector(".btn-spinner").classList.remove("hidden");

    try {
      const payloadPrizes = currentPrizes.map((p, idx) => ({
        place: idx + 1,
        lot_number: idx + 1,
        title: p.title.trim(),
        prize_image_url: p.prize_image_url,
        description: p.description || "",
      }));

      const res = await fetch("/api/admin/raffles", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${adminToken}`,
        },
        body: JSON.stringify({
          title,
          category: "lot",
          description: desc,
          total_tickets: tickets,
          price_per_ticket: price,
          prize_image_url: payloadPrizes[0]?.prize_image_url || "",
          prizes: payloadPrizes,
        }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`🎉 Игра «${title}» с ${payloadPrizes.length} призовыми местами запущена!`, "success");
        closeCreateModal();
        loadDashboardStats();
        loadRaffles();
      } else {
        alert(data.detail || "Ошибка при создании игры");
      }
    } catch (e) {
      alert("Ошибка отправки данных на сервер");
    } finally {
      submitCreateBtn.disabled = false;
      submitCreateBtn.querySelector(".btn-text").classList.remove("hidden");
      submitCreateBtn.querySelector(".btn-spinner").classList.add("hidden");
    }
  }

  function openCreateModal() {
    createRaffleForm.reset();

    raffleTitle.value = "🍳 Кухонный батл: Посуда и бытовая техника";
    raffleDesc.value = "1 купленный билет участвует в розыгрыше всех призовых мест!";
    totalTickets.value = 50;
    pricePerTicket.value = 100;

    currentPrizes = [
      {
        place: 1,
        lot_number: 1,
        title: "Сковорода Tefal с антипригарным покрытием 28 см",
        prize_image_url: "https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=800&q=80",
        description: "",
      },
      {
        place: 2,
        lot_number: 2,
        title: "Стиральный порошок Ariel Горный Родник Автомат 9 кг",
        prize_image_url: "https://images.unsplash.com/photo-1585421514284-efb74c2b69ba?auto=format&fit=crop&w=800&q=80",
        description: "",
      },
    ];

    updateActiveChips();
    renderPrizeItems();
    createModal.classList.remove("hidden");
  }

  function closeCreateModal() {
    createModal.classList.add("hidden");
  }

  // ========================================================
  // WINNER DRAW MODAL
  // ========================================================
  function openDrawModal(raffleId) {
    const raffle = rafflesList.find(r => r.id === raffleId);
    if (!raffle) return;

    activeDrawRaffleId = raffleId;
    drawRaffleTitle.textContent = raffle.title;
    drawTotalTickets.textContent = `${raffle.total_tickets} шт.`;
    drawSoldTickets.textContent = `${raffle.sold_tickets || 0} шт.`;

    if ((raffle.sold_tickets || 0) === 0) {
      alert("Внимание: На эту игру еще не куплено ни одного билета! Для честного выбора должен быть хотя бы 1 купленный билет.");
      return;
    }

    drawInitialState.classList.remove("hidden");
    drawRollingState.classList.add("hidden");
    drawWinnerState.classList.add("hidden");

    drawModal.classList.remove("hidden");
  }

  async function executeDrawWinner() {
    if (!activeDrawRaffleId) return;

    drawInitialState.classList.add("hidden");
    drawRollingState.classList.remove("hidden");

    let rollCounter = 0;
    const rollInterval = setInterval(() => {
      const randomNum = Math.floor(Math.random() * 100) + 1;
      rouletteDrum.textContent = `#${randomNum}`;
      rollCounter++;
    }, 80);

    try {
      const res = await fetch(`/api/admin/raffles/${activeDrawRaffleId}/draw`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${adminToken}` },
      });

      const data = await res.json();
      clearInterval(rollInterval);

      if (res.ok && data.success) {
        rouletteDrum.textContent = `#${data.winning_ticket_number || 1}`;

        setTimeout(() => {
          drawRollingState.classList.add("hidden");
          drawWinnerState.classList.remove("hidden");

          const winners = data.winners || [{
            place: 1,
            lot_number: 1,
            prize_title: "Главный приз",
            ticket_number: data.winning_ticket_number,
            username: data.winner_username,
            user_id: data.winner_user_id,
          }];

          const drawWinnersListContainer = document.getElementById("drawWinnersListContainer");
          if (drawWinnersListContainer) {
            const medalMap = { 1: "🥇 1-е место", 2: "🥈 2-е место", 3: "🥉 3-е место" };
            drawWinnersListContainer.innerHTML = winners.map(w => `
              <div class="winner-place-card">
                <div class="winner-place-info">
                  <span class="winner-place-title">${medalMap[w.place] || `🏅 ${w.place} место`} (Лот №${w.lot_number} — ${escapeHtml(w.prize_title)})</span>
                  <span class="winner-place-sub">Победитель: <strong>@${escapeHtml(w.username || 'участник')}</strong> (ID: ${w.user_id})</span>
                </div>
                <div class="winner-place-ticket-pill">Билет #${w.ticket_number}</div>
              </div>
            `).join('');
          }

          showToast(`🏆 Победители определены для всех призовых мест!`, "success");
          loadDashboardStats();
          loadRaffles();
        }, 500);
      } else {
        drawRollingState.classList.add("hidden");
        drawInitialState.classList.remove("hidden");
        alert(data.detail || data.error || "Ошибка проведения розыгрыша");
      }
    } catch (e) {
      clearInterval(rollInterval);
      drawRollingState.classList.add("hidden");
      drawInitialState.classList.remove("hidden");
      alert("Ошибка связи с сервером при розыгрыше");
    }
  }

  function closeDrawModal() {
    drawModal.classList.add("hidden");
    activeDrawRaffleId = null;
  }

  // ========================================================
  // TICKETS INSPECTION MODAL
  // ========================================================
  async function inspectTickets(raffleId) {
    const raffle = rafflesList.find(r => r.id === raffleId);
    ticketsRaffleTitle.textContent = raffle ? raffle.title : "Сетка билетов";
    ticketsInspectGrid.innerHTML = "<p style='grid-column: 1/-1; text-align: center;'>Загрузка билетов...</p>";
    const pendingContainer = document.getElementById("ticketsPendingReservations");
    if (pendingContainer) {
      pendingContainer.classList.add("hidden");
      pendingContainer.innerHTML = "";
    }
    ticketsModal.classList.remove("hidden");

    try {
      const [ticketsRes, pendingRes] = await Promise.all([
        fetch(`/api/admin/raffles/${raffleId}/tickets`, {
          headers: { "Authorization": `Bearer ${adminToken}` },
        }),
        fetch(`/api/admin/raffles/${raffleId}/pending-reservations`, {
          headers: { "Authorization": `Bearer ${adminToken}` },
        }).catch(() => null),
      ]);

      const ticketsData = await ticketsRes.json();
      if (ticketsRes.ok && ticketsData.success) {
        renderTicketsInspectGrid(ticketsData.tickets);
      } else {
        ticketsInspectGrid.innerHTML = "<p>Ошибка загрузки билетов</p>";
      }

      if (pendingRes && pendingRes.ok) {
        const pendingData = await pendingRes.json();
        const orders = pendingData.pending_orders || [];
        if (pendingContainer && orders.length > 0) {
          pendingContainer.classList.remove("hidden");
          pendingContainer.innerHTML = `
            <div class="pending-res-banner">
              <div class="pending-res-banner-title">
                <span>⏳ Забронированные билеты (${orders.length} заказов):</span>
              </div>
              <div class="pending-res-list">
                ${orders.map(o => `
                  <div class="pending-res-row">
                    <div class="pending-res-info">
                      <span class="pending-res-tickets">Билеты: <b>${o.ticket_numbers.map(n => '#' + n).join(', ')}</b></span>
                      <span class="pending-res-user">Участник: <b>@${escapeHtml(o.username || o.user_id)}</b></span>
                      <span class="pending-res-sum">Сумма: <b>${Math.round(o.amount)} ₽</b></span>
                    </div>
                    <button type="button" class="btn-action-release-res" onclick="window.botmaxAdmin.releaseReservation('${o.id}', '${raffleId}')" title="Снять бронь и вернуть билеты в продажу">
                      ❌ Снять бронь
                    </button>
                  </div>
                `).join('')}
              </div>
            </div>
          `;
        }
      }
    } catch (e) {
      ticketsInspectGrid.innerHTML = "<p>Ошибка сервера</p>";
    }
  }

  async function releaseReservation(orderId, raffleId) {
    if (!confirm("Вы действительно хотите снять бронь с этого заказа и вернуть билеты в доступные?")) {
      return;
    }

    try {
      const res = await fetch(`/api/admin/orders/${orderId}/release`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${adminToken}`,
        },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast("✅ Бронь успешно снята, билеты снова в продаже!", "success");
        await inspectTickets(raffleId);
        loadRafflesList();
        loadSystemMetrics();
      } else {
        showToast(data.detail || data.error || "Ошибка при снятии брони", "error");
      }
    } catch (e) {
      showToast("Ошибка соединения с сервером", "error");
    }
  }

  function renderTicketsInspectGrid(tickets) {
    if (!tickets || tickets.length === 0) {
      ticketsInspectGrid.innerHTML = "<p>Билеты не найдены</p>";
      return;
    }

    ticketsInspectGrid.innerHTML = tickets.map(t => {
      let statusClass = "t-avail";
      let statusTitle = "Свободен";
      if (t.status === "winner") {
        statusClass = "t-win";
        statusTitle = `🏆 Победитель: @${t.username || t.user_id}`;
      } else if (t.status === "sold") {
        statusClass = "t-sold";
        statusTitle = `Куплен: @${t.username || t.user_id}`;
      } else if (t.status === "reserved") {
        statusClass = "t-res";
        statusTitle = `Бронь: @${t.username || t.user_id}`;
      }

      return `
        <div class="ticket-cell ${statusClass}" title="${statusTitle}">
          <span>#${t.ticket_number}</span>
        </div>
      `;
    }).join("");
  }

  function closeTicketsModal() {
    ticketsModal.classList.add("hidden");
  }

  // ========================================================
  // BROADCAST TO MAX MESSENGER GROUPS
  // ========================================================
  async function broadcastRaffle(raffleId) {
    if (!confirm("Опубликовать и закрепить этот розыгрыш во всех подключенных группах MAX?")) {
      return;
    }

    showToast("Отправка в группы MAX...", "info");
    try {
      const res = await fetch(`/api/admin/raffles/${raffleId}/broadcast`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${adminToken}` },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`✅ Опубликовано в ${data.broadcasted_groups_count} групп(ах) MAX!`, "success");
      } else {
        showToast(data.detail || "Ошибка отправки в группы", "error");
      }
    } catch (e) {
      showToast("Ошибка соединения", "error");
    }
  }

  async function broadcastFullShowcase() {
    if (!confirm("Опубликовать витрину активных розыгрышей во всех подключенных группах MAX?")) {
      return;
    }

    showToast("Отправка витрины в группы...", "info");
    try {
      const res = await fetch("/api/admin/broadcast-showcase", {
        method: "POST",
        headers: { "Authorization": `Bearer ${adminToken}` },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`✅ Витрина опубликована в ${data.broadcasted_groups_count} группах!`, "success");
      } else {
        showToast(data.detail || "Ошибка отправки", "error");
      }
    } catch (e) {
      showToast("Ошибка соединения", "error");
    }
  }

  async function deleteRaffle(raffleId) {
    if (!confirm("Вы действительно хотите удалить этот розыгрыш и все его билеты? Это действие необратимо.")) {
      return;
    }

    try {
      const res = await fetch(`/api/admin/raffles/${raffleId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${adminToken}` },
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast("Розыгрыш успешно удален", "success");
        loadDashboardStats();
        loadRaffles();
      } else {
        alert(data.detail || "Ошибка удаления");
      }
    } catch (e) {
      alert("Ошибка соединения с сервером");
    }
  }

  // ========================================================
  // UTILITIES & EVENTS
  // ========================================================
  function bindEvents() {
    // Auth
    if (loginForm) {
      loginForm.addEventListener("submit", (e) => {
        e.preventDefault();
        handleLogin();
      });
    }
    if (loginBtn) {
      loginBtn.addEventListener("click", (e) => {
        e.preventDefault();
        handleLogin();
      });
    }
    if (adminPasswordInput) {
      adminPasswordInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          handleLogin();
        }
      });
    }
    if (togglePasswordBtn) {
      togglePasswordBtn.addEventListener("click", () => {
        const isPassword = adminPasswordInput.type === "password";
        adminPasswordInput.type = isPassword ? "text" : "password";
        togglePasswordBtn.textContent = isPassword ? "🙈" : "👁️";
      });
    }
    if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);
    if (themeToggleBtn) themeToggleBtn.addEventListener("click", toggleTheme);

    // Profile & SBP Modal
    openProfileBtn?.addEventListener("click", openProfileModal);
    closeProfileModalBtn?.addEventListener("click", closeProfileModal);
    closeProfileBtn?.addEventListener("click", closeProfileModal);
    saveProfileBtn?.addEventListener("click", handleSaveProfileSubmit);

    // SuperAdmin Navigation Tabs
    tabShowRaffles?.addEventListener("click", () => switchMainTab("raffles"));
    tabShowAdmins?.addEventListener("click", () => switchMainTab("admins"));

    // Admin Creation Modal (SuperAdmin)
    openCreateAdminModalBtn?.addEventListener("click", openCreateAdminModal);
    emptyCreateAdminBtn?.addEventListener("click", openCreateAdminModal);
    closeCreateAdminModalBtn?.addEventListener("click", closeCreateAdminModal);
    cancelCreateAdminBtn?.addEventListener("click", closeCreateAdminModal);
    submitCreateAdminBtn?.addEventListener("click", handleCreateAdminSubmit);

    // Filter Tabs for Raffles
    statusTabs.forEach(tab => {
      tab.addEventListener("click", () => {
        statusTabs.forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        currentFilter = tab.getAttribute("data-filter");
        renderRafflesGrid();
      });
    });

    refreshBtn?.addEventListener("click", () => {
      loadDashboardStats();
      if (currentMainTab === "admins") {
        loadAdminsList();
      } else {
        loadRaffles();
      }
      showToast("Данные обновлены", "info");
    });

    broadcastShowcaseBtn?.addEventListener("click", broadcastFullShowcase);

    // Create Raffle Modal
    openCreateModalBtn?.addEventListener("click", openCreateModal);
    emptyCreateBtn?.addEventListener("click", openCreateModal);
    closeCreateModalBtn?.addEventListener("click", closeCreateModal);
    cancelCreateBtn?.addEventListener("click", closeCreateModal);
    submitCreateBtn?.addEventListener("click", handleCreateRaffleSubmit);

    // Live preview inputs
    raffleTitle?.addEventListener("input", updateLivePreview);
    raffleDesc?.addEventListener("input", updateLivePreview);
    totalTickets?.addEventListener("input", () => {
      updateActiveChips();
      updateLivePreview();
    });
    pricePerTicket?.addEventListener("input", () => {
      updateActiveChips();
      updateLivePreview();
    });

    initPrizesManager();

    // Chips
    document.querySelectorAll("[data-tickets]").forEach(btn => {
      btn.addEventListener("click", () => {
        totalTickets.value = btn.getAttribute("data-tickets");
        updateActiveChips();
        updateLivePreview();
      });
    });

    document.querySelectorAll("[data-price]").forEach(btn => {
      btn.addEventListener("click", () => {
        pricePerTicket.value = btn.getAttribute("data-price");
        updateActiveChips();
        updateLivePreview();
      });
    });

    // Draw Modal
    closeDrawModalBtn?.addEventListener("click", closeDrawModal);
    closeDrawBtn?.addEventListener("click", closeDrawModal);
    startDrawBtn?.addEventListener("click", executeDrawWinner);

    // Senior Mode Accessibility Buttons
    document.getElementById("seniorModeToggleBtn")?.addEventListener("click", toggleSeniorMode);
    document.getElementById("loginSeniorModeBtn")?.addEventListener("click", toggleSeniorMode);

    // Mobile Bottom Navigation Bar (APK & Phone screens)
    const mbNavGames = document.getElementById("mbNavGames");
    const mbNavCreate = document.getElementById("mbNavCreate");
    const mbNavSbp = document.getElementById("mbNavSbp");
    const mbNavRefresh = document.getElementById("mbNavRefresh");
    const mbNavSenior = document.getElementById("mbNavSenior");

    mbNavGames?.addEventListener("click", () => {
      document.querySelectorAll(".mb-nav-btn").forEach(b => b.classList.remove("active"));
      mbNavGames.classList.add("active");
      switchMainTab("raffles");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });

    mbNavCreate?.addEventListener("click", () => {
      openCreateModal();
    });

    mbNavSbp?.addEventListener("click", () => {
      openProfileModal();
    });

    mbNavRefresh?.addEventListener("click", () => {
      loadDashboardStats();
      if (currentMainTab === "admins") {
        loadAdminsList();
      } else {
        loadRaffles();
      }
      showToast("Данные обновлены", "info");
    });

    mbNavSenior?.addEventListener("click", () => {
      toggleSeniorMode();
    });

    // Tickets Modal
    closeTicketsModalBtn?.addEventListener("click", closeTicketsModal);
    closeTicketsBtn?.addEventListener("click", closeTicketsModal);
  }

  function showToast(message, type = "info") {
    if (!toastContainer) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icon = type === "success" ? "✅" : (type === "error" ? "❌" : "ℹ️");
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;

    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(40px)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Expose methods for inline onclick attributes
  window.botmaxAdmin = {
    openDrawModal,
    broadcastRaffle,
    inspectTickets,
    deleteRaffle,
    addPrizePlace,
    removePrize,
    updatePrizeTitle,
    updatePrizeDescription,
    releaseReservation,
    handlePrizeFileChange,
    openCreateModal,
    deleteAdminUser,
  };

})();
