/**
 * BotMAX Mini-App Client Logic
 * Implements real-time ticket drawdown, interactive grid, and SBP checkout
 */

(function () {
  "use strict";

  // App State
  const state = {
    user: {
      id: 471249415,
      username: "max_user",
      name: "Пользователь MAX",
    },
    currentRaffleId: null,
    currentRaffle: null,
    selectedTickets: new Set(),
    activeOrder: null,
    countdownInterval: null,
    pollingInterval: null,
    syncInterval: null,
  };

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initialize User from URL Query Params, WebApp SDK, or LocalStorage
  function initUser() {
    const urlParams = new URLSearchParams(window.location.search);
    const uid = urlParams.get("user_id") || localStorage.getItem("botmax_user_id");
    const uname = urlParams.get("username") || localStorage.getItem("botmax_username");
    const storedNick = localStorage.getItem("botmax_nickname");
    const storedPhone = localStorage.getItem("botmax_phone") || "";

    if (uid) {
      state.user.id = parseInt(uid, 10);
    } else {
      const randId = Math.floor(100000 + Math.random() * 900000);
      state.user.id = randId;
    }

    // Determine nickname & whether participant has explicitly set it
    if (storedNick && !storedNick.toLowerCase().startsWith("user_")) {
      state.user.username = storedNick;
      state.user.name = `@${storedNick}`;
      state.user.isNickConfigured = true;
    } else if (uname && !uname.toLowerCase().startsWith("user_")) {
      state.user.username = uname;
      state.user.name = `@${uname}`;
      state.user.isNickConfigured = true;
      localStorage.setItem("botmax_nickname", uname);
    } else {
      state.user.username = `user_${state.user.id}`;
      state.user.name = `Участник #${state.user.id}`;
      state.user.isNickConfigured = false;
    }

    state.user.phone = storedPhone;

    localStorage.setItem("botmax_user_id", state.user.id);
    localStorage.setItem("botmax_username", state.user.username);
    if (state.user.phone) {
      localStorage.setItem("botmax_phone", state.user.phone);
    }

    updateUserBadgeDisplay();
  }

  function updateUserBadgeDisplay() {
    const nameEl = document.getElementById("userNameDisplay");
    if (nameEl) {
      if (state.user.isNickConfigured) {
        nameEl.textContent = `@${state.user.username}`;
      } else {
        nameEl.textContent = "Задать Ник 🎭";
      }
    }
  }

  // Theme Management
  function initTheme() {
    const savedTheme = localStorage.getItem("botmax_theme") || "light";
    document.documentElement.setAttribute("data-theme", savedTheme);
    updateThemeIcon(savedTheme);

    const toggleBtn = document.getElementById("themeToggleBtn");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        const next = cur === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem("botmax_theme", next);
        updateThemeIcon(next);
      });
    }
  }

  function updateThemeIcon(theme) {
    const btn = document.getElementById("themeToggleBtn");
    if (btn) btn.textContent = theme === "dark" ? "☀️" : "🌙";
  }

  // Tabs Navigation
  function initTabs() {
    const tabs = document.querySelectorAll(".tab-btn");
    tabs.forEach((btn) => {
      btn.addEventListener("click", () => {
        const tab = btn.getAttribute("data-tab");
        switchTab(tab);
      });
    });
  }

  function switchTab(tabId) {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view-section").forEach((s) => s.classList.remove("active"));

    const targetBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
    if (targetBtn) targetBtn.classList.add("active");

    const targetView = document.getElementById(`view${capitalize(tabId)}`);
    if (targetView) targetView.classList.add("active");

    const checkoutBar = document.getElementById("floatingCheckoutBar");
    if (checkoutBar) {
      checkoutBar.style.display = (tabId === "board" && state.currentRaffle) ? "flex" : "none";
    }

    if (tabId === "raffles") loadRaffles();
    if (tabId === "portfolio") loadUserPortfolio();
    if (tabId === "hall") loadCompletedHall();
  }

  function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
  }

  // ==========================================
  // VIEW 1: RAFFLES CATALOG
  // ==========================================
  async function loadRaffles() {
    try {
      const res = await fetch("/api/raffles");
      const data = await res.json();
      if (!data.success) return;

      const grid = document.getElementById("rafflesGrid");
      const loading = document.getElementById("rafflesLoading");
      if (loading) loading.style.display = "none";
      if (!grid) return;

      grid.innerHTML = "";
      data.raffles.forEach((r) => {
        grid.appendChild(createRaffleCard(r));
      });
    } catch (err) {
      console.error("Failed to load raffles:", err);
    }
  }

  function createRaffleCard(r) {
    const card = document.createElement("div");
    card.className = "raffle-card";

    let badgeClass = "badge-active";
    let badgeText = "🟢 В игре";
    if (r.status === "completed") {
      badgeClass = "badge-completed";
      badgeText = "🏆 Разыгран";
    } else if (r.available_tickets <= 10) {
      badgeClass = "badge-hot";
      badgeText = "🔥 Финал";
    }

    const prizes = r.prizes || [];
    const prizesCount = prizes.length;
    const badgeTextLot = prizesCount > 1 ? `🏆 ${prizesCount} призовых мест` : `🏷️ Лот №${r.lot_number || 1}`;
    const mainImg = (prizes[0] && prizes[0].prize_image_url) ? prizes[0].prize_image_url : r.prize_image_url;
    const medalMap = { 1: "🥇", 2: "🥈", 3: "🥉" };

    let multiLotsHtml = "";
    if (prizesCount > 1) {
      multiLotsHtml = `
        <div class="card-lots-showcase">
          ${prizes.map((p) => {
            const medal = medalMap[p.place] || "🏅";
            const pImg = p.prize_image_url || mainImg;
            return `
              <div class="card-lot-item">
                <div class="card-lot-item-top">
                  <span class="card-lot-badge">${medal} ${p.place} место (Лот №${p.lot_number || p.place})</span>
                  <span class="card-lot-title">${escapeHtml(p.title)}</span>
                </div>
                ${p.description ? `<p class="card-lot-desc">${escapeHtml(p.description)}</p>` : ''}
                <img src="${escapeHtml(pImg)}" class="card-lot-img" alt="${escapeHtml(p.title)}" onerror="this.src='${mainImg}'">
              </div>
            `;
          }).join('')}
        </div>
      `;
    }

    card.innerHTML = `
      <div class="raffle-image-wrapper">
        <img class="raffle-image" src="${mainImg}" alt="${escapeHtml(r.title)}" onerror="this.src='https://images.unsplash.com/photo-1590794056226-79ef3a8147e1?auto=format&fit=crop&w=800&q=80'">
        <div class="raffle-badge-status ${badgeClass}">${badgeText}</div>
        <div class="raffle-lot-badge">${badgeTextLot}</div>
        <div class="raffle-price-tag">${Math.round(r.price_per_ticket)} ₽ / билет</div>
      </div>
      <div class="raffle-card-content">
        <h2 class="raffle-card-title">${escapeHtml(r.title)}</h2>
        <p class="raffle-card-desc">${escapeHtml(r.description || "")}</p>
        ${multiLotsHtml}
        
        <div class="drawdown-progress-container">
          <div class="drawdown-labels">
            <span class="label-remaining">Осталось: ${r.available_tickets} из ${r.total_tickets}</span>
            <span class="label-percent">Убыло: ${r.percent_sold}%</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${r.percent_sold}%"></div>
          </div>
        </div>

        <button class="btn-select-tickets">
          <span>🎟️ Выбрать билеты</span>
        </button>
      </div>
    `;

    card.addEventListener("click", () => {
      openRaffleBoard(r.id);
    });

    return card;
  }

  // ==========================================
  // VIEW 2: TICKET BOARD & DRAWDOWN
  // ==========================================
  async function openRaffleBoard(raffleId) {
    state.currentRaffleId = raffleId;
    state.selectedTickets.clear();
    switchTab("board");

    await reloadBoard();
  }

  async function reloadBoard() {
    if (!state.currentRaffleId) return;

    try {
      const res = await fetch(`/api/raffles/${state.currentRaffleId}`);
      const data = await res.json();
      if (!data.success) return;

      state.currentRaffle = data.raffle;
      renderBoardHeader(data.raffle);
      renderTicketsGrid(data.raffle.tickets);
      updateCheckoutBar();
    } catch (err) {
      console.error("Failed to load raffle board:", err);
    }
  }

  function renderBoardHeader(raffle) {
    const thumb = document.getElementById("boardRaffleThumb");
    const title = document.getElementById("boardRaffleTitle");
    const subtitle = document.getElementById("boardRaffleSubtitle");
    const lotsContainer = document.getElementById("boardLotsContainer");

    const prizes = raffle.prizes || [];
    const mainImg = (prizes[0] && prizes[0].prize_image_url) ? prizes[0].prize_image_url : raffle.prize_image_url;
    if (thumb) thumb.src = mainImg;
    if (title) title.textContent = raffle.title;
    if (subtitle) {
      const extra = prizes.length > 1 ? ` • ${prizes.length} призовых мест` : '';
      subtitle.textContent = `Доступно: ${raffle.available_tickets} из ${raffle.total_tickets} шт. • ${Math.round(raffle.price_per_ticket)} ₽ / билет${extra}`;
    }

    if (lotsContainer) {
      const medalMap = { 1: "🥇", 2: "🥈", 3: "🥉" };
      lotsContainer.innerHTML = prizes.map((p) => {
        const medal = medalMap[p.place] || "🏅";
        const pImg = p.prize_image_url || mainImg;
        return `
          <div class="board-lot-card">
            <div class="board-lot-header">
              <span class="board-lot-badge">${medal} ${p.place} место (Лот №${p.lot_number || p.place})</span>
              <span class="board-lot-title">${escapeHtml(p.title)}</span>
            </div>
            <div class="board-lot-body">
              ${p.description ? `<p class="board-lot-desc">${escapeHtml(p.description)}</p>` : ''}
              <div class="board-lot-img-wrap">
                <img src="${escapeHtml(pImg)}" class="board-lot-img" alt="${escapeHtml(p.title)}" onerror="this.src='${mainImg}'">
              </div>
            </div>
          </div>
        `;
      }).join("");
    }
  }

  function renderTicketsGrid(tickets) {
    const grid = document.getElementById("ticketsGrid");
    if (!grid) return;
    grid.innerHTML = "";

    tickets.forEach((t) => {
      const cell = document.createElement("div");
      cell.className = `ticket-cell ${t.status}`;
      cell.setAttribute("data-ticket", t.ticket_number);

      if (state.selectedTickets.has(t.ticket_number)) {
        cell.classList.add("selected");
      }

      let sublabel = "";
      if (t.status === "sold") sublabel = "Убыл";
      else if (t.status === "reserved") sublabel = "Бронь";
      else if (t.status === "winner") sublabel = "Приз!";

      cell.innerHTML = `
        <span>№${t.ticket_number}</span>
        ${sublabel ? `<span class="ticket-sublabel">${sublabel}</span>` : ""}
      `;

      if (t.status === "available") {
        cell.addEventListener("click", () => {
          toggleTicketSelection(t.ticket_number, cell);
        });
      }

      grid.appendChild(cell);
    });
  }

  function toggleTicketSelection(ticketNumber, cellEl) {
    if (state.selectedTickets.has(ticketNumber)) {
      state.selectedTickets.delete(ticketNumber);
      cellEl.classList.remove("selected");
    } else {
      state.selectedTickets.add(ticketNumber);
      cellEl.classList.add("selected");
    }
    updateCheckoutBar();
  }

  function updateCheckoutBar() {
    const count = state.selectedTickets.size;
    const price = state.currentRaffle ? state.currentRaffle.price_per_ticket : 0;
    const total = Math.round(count * price);

    const countEl = document.getElementById("checkoutTicketsCount");
    const totalEl = document.getElementById("checkoutTotalPrice");
    const btn = document.getElementById("btnProceedSbp");

    if (countEl) countEl.textContent = `Выбрано: ${count} ${declensionTickets(count)}`;
    if (totalEl) totalEl.textContent = `${total} ₽`;
    if (btn) btn.disabled = count === 0;

    const bar = document.getElementById("floatingCheckoutBar");
    if (bar) bar.style.display = "flex";
  }

  function declensionTickets(n) {
    if (n % 10 === 1 && n % 100 !== 11) return "билет";
    if ([2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100)) return "билета";
    return "билетов";
  }

  // Quick Selector Controls
  function initQuickSelectors() {
    document.getElementById("btnQuickRandom1")?.addEventListener("click", () => selectRandom(1));
    document.getElementById("btnQuickPlus1")?.addEventListener("click", () => selectNextAvailable(1));
    document.getElementById("btnQuickPlus3")?.addEventListener("click", () => selectNextAvailable(3));
    document.getElementById("btnQuickPlus5")?.addEventListener("click", () => selectNextAvailable(5));
    document.getElementById("btnClearSelection")?.addEventListener("click", () => {
      state.selectedTickets.clear();
      document.querySelectorAll(".ticket-cell.selected").forEach((c) => c.classList.remove("selected"));
      updateCheckoutBar();
    });
  }

  function selectRandom(count) {
    if (!state.currentRaffle) return;
    const avail = state.currentRaffle.tickets
      .filter((t) => t.status === "available" && !state.selectedTickets.has(t.ticket_number))
      .map((t) => t.ticket_number);

    if (avail.length === 0) {
      alert("Нет свободных билетов для выбора");
      return;
    }

    const shuffled = avail.sort(() => 0.5 - Math.random());
    shuffled.slice(0, count).forEach((num) => {
      state.selectedTickets.add(num);
      const cell = document.querySelector(`.ticket-cell[data-ticket="${num}"]`);
      if (cell) cell.classList.add("selected");
    });
    updateCheckoutBar();
  }

  function selectNextAvailable(count) {
    if (!state.currentRaffle) return;
    const avail = state.currentRaffle.tickets
      .filter((t) => t.status === "available" && !state.selectedTickets.has(t.ticket_number))
      .map((t) => t.ticket_number);

    avail.slice(0, count).forEach((num) => {
      state.selectedTickets.add(num);
      const cell = document.querySelector(`.ticket-cell[data-ticket="${num}"]`);
      if (cell) cell.classList.add("selected");
    });
    updateCheckoutBar();
  }

  // ==========================================
  // SBP CHECKOUT & RESERVATION MODAL
  // ==========================================
  let resBannerInterval = null;

  async function checkActiveReservation() {
    if (!state.user || !state.user.id) return;
    try {
      const res = await fetch(`/api/users/${state.user.id}/active-reservation`);
      const data = await res.json();
      if (data.success && data.has_active && data.order) {
        state.activeOrder = data.order;
        showReservationBanner(data.order);
      } else {
        hideReservationBanner();
      }
    } catch (err) {
      console.warn("Could not check active reservation:", err);
    }
  }

  function showReservationBanner(order) {
    const banner = document.getElementById("activeReservationBanner");
    const timerEl = document.getElementById("resBannerCountdown");
    const subEl = document.getElementById("resBannerSubtitle");
    if (!banner) return;

    banner.classList.remove("hidden");
    if (subEl) {
      const tStr = (order.ticket_numbers || []).map((n) => `#${n}`).join(", ");
      subEl.textContent = `${order.raffle_title} • ${tStr} • ${Math.round(order.amount)} ₽`;
    }

    clearInterval(resBannerInterval);
    const target = new Date(order.expires_at).getTime();

    function updateTimer() {
      const diff = Math.max(0, Math.floor((target - Date.now()) / 1000));
      const mins = Math.floor(diff / 60);
      const secs = diff % 60;
      if (timerEl) {
        timerEl.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
      }
      if (diff <= 0) {
        clearInterval(resBannerInterval);
        hideReservationBanner();
        state.activeOrder = null;
        reloadBoard();
      }
    }
    updateTimer();
    resBannerInterval = setInterval(updateTimer, 1000);

    const btnResume = document.getElementById("btnResResume");
    if (btnResume) {
      btnResume.onclick = () => {
        openSbpModal(order);
      };
    }

    const btnCancel = document.getElementById("btnResCancel");
    if (btnCancel) {
      btnCancel.onclick = () => {
        cancelActiveOrder(order.order_id);
      };
    }
  }

  function hideReservationBanner() {
    clearInterval(resBannerInterval);
    const banner = document.getElementById("activeReservationBanner");
    if (banner) banner.classList.add("hidden");
  }

  async function cancelActiveOrder(orderId) {
    if (!orderId && state.activeOrder) {
      orderId = state.activeOrder.order_id;
    }
    if (!orderId) return;

    if (!confirm("Вы действительно хотите снять бронь? Билеты станут доступны всем участникам.")) {
      return;
    }

    try {
      const res = await fetch(`/api/orders/${orderId}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: state.user.id }),
      });
      const data = await res.json();
      if (data.success) {
        state.activeOrder = null;
        clearInterval(state.countdownInterval);
        clearInterval(state.pollingInterval);
        document.getElementById("modalSbp")?.classList.remove("active");
        hideReservationBanner();
        await reloadBoard();
        alert("Бронь успешно снята. Билеты возвращены в продажу.");
      } else {
        alert(data.detail || data.error || "Не удалось снять бронь");
      }
    } catch (err) {
      console.error("Cancel order error:", err);
      alert("Ошибка соединения с сервером при снятии брони");
    }
  }

  // ==========================================
  // PARTICIPANT NICKNAME & PROFILE MODAL
  // ==========================================
  let pendingReserveCallback = null;

  function openParticipantProfileModal() {
    const modal = document.getElementById("modalParticipantProfile");
    const nickInput = document.getElementById("inputParticipantNickname");
    const phoneInput = document.getElementById("inputParticipantPhone");
    const errBox = document.getElementById("participantProfileError");

    if (errBox) {
      errBox.classList.add("hidden");
      errBox.textContent = "";
    }

    if (nickInput) {
      nickInput.value = state.user.isNickConfigured ? state.user.username : "";
    }
    if (phoneInput) {
      phoneInput.value = state.user.phone || "";
    }

    if (modal) {
      modal.classList.add("active");
    }
  }

  function closeParticipantProfileModal() {
    const modal = document.getElementById("modalParticipantProfile");
    if (modal) {
      modal.classList.remove("active");
    }
    pendingReserveCallback = null;
  }

  async function handleSaveParticipantProfile() {
    const nickInput = document.getElementById("inputParticipantNickname");
    const phoneInput = document.getElementById("inputParticipantPhone");
    const errBox = document.getElementById("participantProfileError");
    const saveBtn = document.getElementById("btnSaveParticipantProfile");

    const rawNick = (nickInput?.value || "").trim().replace(/^@+/, "");
    const rawPhone = (phoneInput?.value || "").trim();

    if (!rawNick || rawNick.length < 3) {
      if (errBox) {
        errBox.textContent = "Никнейм должен содержать минимум 3 символа";
        errBox.classList.remove("hidden");
      }
      return;
    }
    if (rawNick.toLowerCase().startsWith("user_")) {
      if (errBox) {
        errBox.textContent = "Пожалуйста, придумайте уникальный ник (без префикса 'user_')";
        errBox.classList.remove("hidden");
      }
      return;
    }

    if (saveBtn) saveBtn.disabled = true;
    try {
      // 1. Check uniqueness
      const checkRes = await fetch("/api/users/check-nickname", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nickname: rawNick, user_id: state.user.id }),
      });
      const checkData = await checkRes.json();
      if (!checkData.available) {
        if (errBox) {
          errBox.textContent = checkData.detail || "Этот никнейм уже занят другим участником. Пожалуйста, придумайте другой ник.";
          errBox.classList.remove("hidden");
        }
        if (saveBtn) saveBtn.disabled = false;
        return;
      }

      // 2. Persist profile
      const profRes = await fetch("/api/users/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: state.user.id,
          nickname: rawNick,
          phone: rawPhone,
        }),
      });
      const profData = await profRes.json();
      if (profRes.ok && profData.success) {
        state.user.username = rawNick;
        state.user.phone = rawPhone;
        state.user.isNickConfigured = true;
        localStorage.setItem("botmax_nickname", rawNick);
        localStorage.setItem("botmax_username", rawNick);
        if (rawPhone) {
          localStorage.setItem("botmax_phone", rawPhone);
        }
        updateUserBadgeDisplay();
        closeParticipantProfileModal();

        // If checkout was waiting on nickname setup, proceed automatically!
        if (typeof pendingReserveCallback === "function") {
          const cb = pendingReserveCallback;
          pendingReserveCallback = null;
          cb();
        }
      } else {
        if (errBox) {
          errBox.textContent = profData.detail || "Ошибка при сохранении профиля";
          errBox.classList.remove("hidden");
        }
      }
    } catch (e) {
      if (errBox) {
        errBox.textContent = "Ошибка соединения с сервером";
        errBox.classList.remove("hidden");
      }
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  function initCheckout() {
    const btnProceed = document.getElementById("btnProceedSbp");
    if (btnProceed) {
      btnProceed.addEventListener("click", startSbpCheckout);
    }

    document.getElementById("userProfileBtn")?.addEventListener("click", () => {
      openParticipantProfileModal();
    });
    document.getElementById("btnCloseProfileModal")?.addEventListener("click", () => {
      closeParticipantProfileModal();
    });
    document.getElementById("participantProfileForm")?.addEventListener("submit", (e) => {
      e.preventDefault();
      handleSaveParticipantProfile();
    });
    document.getElementById("btnSaveParticipantProfile")?.addEventListener("click", () => {
      handleSaveParticipantProfile();
    });

    document.getElementById("btnCloseSbpModal")?.addEventListener("click", closeSbpModal);
    document.getElementById("btnCancelOrder")?.addEventListener("click", () => {
      cancelActiveOrder();
    });
    document.getElementById("btnCancelReservationInModal")?.addEventListener("click", () => {
      cancelActiveOrder();
    });
    document.getElementById("btnSimulateSbpSuccess")?.addEventListener("click", simulateSbpPayment);
    document.getElementById("btnGoToPortfolio")?.addEventListener("click", () => {
      document.getElementById("modalSuccess")?.classList.remove("active");
      switchTab("portfolio");
    });
  }

  async function startSbpCheckout() {
    if (state.selectedTickets.size === 0 || !state.currentRaffleId) return;

    // Check if participant has chosen a unique nickname
    if (!state.user.isNickConfigured) {
      pendingReserveCallback = () => startSbpCheckout();
      openParticipantProfileModal();
      return;
    }

    const ticketsArr = Array.from(state.selectedTickets);
    const payload = {
      user_id: state.user.id,
      username: state.user.username,
      phone: state.user.phone || "",
      ticket_numbers: ticketsArr,
    };

    try {
      const res = await fetch(`/api/raffles/${state.currentRaffleId}/reserve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!data.success) {
        alert(data.error || "Не удалось забронировать билеты");
        await reloadBoard();
        return;
      }

      state.activeOrder = data;
      showReservationBanner(data);
      openSbpModal(data);
    } catch (err) {
      console.error("Reservation error:", err);
      alert("Ошибка связи с сервером при бронировании билетов");
    }
  }

  function openSbpModal(orderData) {
    state.activeOrder = orderData;
    document.getElementById("sbpModalRaffleTitle").textContent = orderData.raffle_title;
    document.getElementById("sbpModalTicketNumbers").textContent =
      `Номера билетов: ${orderData.ticket_numbers.map((n) => "#" + n).join(", ")}`;
    document.getElementById("sbpModalAmount").textContent = `${orderData.amount} ₽`;

    // QR Image
    const qrImg = document.getElementById("sbpQrImage");
    if (qrImg && orderData.sbp?.qr_data_url) {
      qrImg.src = orderData.sbp.qr_data_url;
    }

    // Set mobile deep link
    const btnApp = document.getElementById("btnOpenBankApp");
    if (btnApp) {
      btnApp.onclick = () => {
        window.location.href = orderData.sbp?.deep_link || orderData.sbp?.nspk_url;
      };
    }

    // Start 10-minute countdown timer
    startCountdown(orderData.expires_at);

    // Start polling order status
    startOrderPolling(orderData.order_id);

    document.getElementById("modalSbp")?.classList.add("active");
  }

  function closeSbpModal() {
    clearInterval(state.countdownInterval);
    clearInterval(state.pollingInterval);
    document.getElementById("modalSbp")?.classList.remove("active");
    checkActiveReservation();
    reloadBoard();
  }

  function startCountdown(expiresAtIso) {
    clearInterval(state.countdownInterval);
    const target = new Date(expiresAtIso).getTime();

    function update() {
      const now = Date.now();
      const diff = Math.max(0, Math.floor((target - now) / 1000));
      const mins = Math.floor(diff / 60);
      const secs = diff % 60;
      const display = document.getElementById("sbpCountdownDisplay");
      if (display) {
        display.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
      }

      if (diff <= 0) {
        clearInterval(state.countdownInterval);
        alert("Время бронирования истекло. Билеты возвращены в продажу.");
        closeSbpModal();
      }
    }

    update();
    state.countdownInterval = setInterval(update, 1000);
  }

  function startOrderPolling(orderId) {
    clearInterval(state.pollingInterval);
    state.pollingInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/orders/${orderId}`);
        const data = await res.json();
        if (data.success && data.order.status === "paid") {
          clearInterval(state.pollingInterval);
          onPaymentSuccess(data.order);
        }
      } catch (e) {
        // quiet error
      }
    }, 2500);
  }

  async function simulateSbpPayment() {
    if (!state.activeOrder) return;
    try {
      const res = await fetch(`/api/orders/${state.activeOrder.order_id}/confirm-simulation`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.success) {
        onPaymentSuccess(data.order);
      } else {
        alert(data.error || "Ошибка симуляции");
      }
    } catch (err) {
      console.error("Simulation error:", err);
    }
  }

  function onPaymentSuccess(order) {
    hideReservationBanner();
    state.activeOrder = null;
    closeSbpModal();

    // Trigger celebratory confetti
    if (typeof confetti === "function") {
      confetti({
        particleCount: 120,
        spread: 80,
        origin: { y: 0.6 },
      });
    }

    const titleEl = document.getElementById("successRaffleTitle");
    const ticketsEl = document.getElementById("successTicketsList");

    if (titleEl) titleEl.textContent = state.activeOrder?.raffle_title || "Розыгрыш";
    if (ticketsEl) {
      ticketsEl.textContent = order.ticket_numbers.map((n) => `№${n}`).join(", ");
    }

    state.selectedTickets.clear();
    document.getElementById("modalSuccess")?.classList.add("active");
  }

  // ==========================================
  // VIEW 3: USER PORTFOLIO
  // ==========================================
  async function loadUserPortfolio() {
    const list = document.getElementById("userTicketsList");
    if (!list) return;

    try {
      const res = await fetch(`/api/users/${state.user.id}/tickets`);
      const data = await res.json();
      if (!data.success || data.tickets.length === 0) {
        list.innerHTML = `
          <div style="text-align: center; padding: 40px 16px; color: var(--text-secondary);">
            У вас пока нет купленных билетов. Перейдите во вкладку «Розыгрыши»!
          </div>
        `;
        return;
      }

      list.innerHTML = "";
      data.tickets.forEach((t) => {
        const item = document.createElement("div");
        item.className = "user-ticket-card";

        let badgeStatus = "🟢 Активен";
        if (t.ticket_status === "winner") badgeStatus = "🏆 ВЫ ВЫИГРАЛИ ПРИЗ!";

        item.innerHTML = `
          <div>
            <div style="font-weight: 700; font-size: 15px;">${t.raffle_title}</div>
            <div style="font-size: 12px; color: var(--text-secondary); margin-top: 4px;">
              Статус: ${badgeStatus}
            </div>
          </div>
          <div class="ticket-num-badge">№${t.ticket_number}</div>
        `;
        list.appendChild(item);
      });
    } catch (err) {
      console.error("Portfolio error:", err);
    }
  }

  // ==========================================
  // VIEW 4: WINNERS & DRAW ROULETTE
  // ==========================================
  function loadCompletedHall() {
    const btnSimulate = document.getElementById("btnSimulateDraw");
    const roulette = document.getElementById("rouletteDisplay");

    if (btnSimulate && roulette) {
      btnSimulate.onclick = () => {
        let count = 0;
        const interval = setInterval(() => {
          const randNum = Math.floor(1 + Math.random() * 100);
          roulette.textContent = `№ ${randNum}`;
          count++;
          if (count > 25) {
            clearInterval(interval);
            roulette.textContent = `№ ${randNum} 🏆`;
            if (typeof confetti === "function") {
              confetti({ particleCount: 80, spread: 60 });
            }
          }
        }, 80);
      };
    }
  }

  // ==========================================
  // VIEW 5: ADMIN PANEL
  // ==========================================
  function initAdminForm() {
    const form = document.getElementById("createRaffleForm");
    if (!form) return;

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = {
        id: document.getElementById("adminRaffleId").value.trim(),
        title: document.getElementById("adminRaffleTitle").value.trim(),
        description: document.getElementById("adminRaffleDesc").value.trim(),
        prize_image_url: document.getElementById("adminRaffleImage").value.trim(),
        total_tickets: parseInt(document.getElementById("adminRaffleTickets").value, 10),
        price_per_ticket: parseFloat(document.getElementById("adminRafflePrice").value),
      };

      try {
        const res = await fetch("/api/admin/create-raffle", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
          alert(`Розыгрыш «${payload.title}» успешно создан!`);
          form.reset();
          switchTab("raffles");
        } else {
          alert(data.error || "Ошибка создания");
        }
      } catch (err) {
        console.error("Admin create error:", err);
        alert("Ошибка при создании розыгрыша");
      }
    });
  }

  // Background Live Sync (Refreshes grid every 5s for live ticket drawdown)
  function initLiveSync() {
    setInterval(() => {
      const activeTab = document.querySelector(".tab-btn.active")?.getAttribute("data-tab");
      if (activeTab === "raffles") loadRaffles();
      else if (activeTab === "board" && !state.activeOrder) reloadBoard();
    }, 5000);
  }

  // Initialization
  document.addEventListener("DOMContentLoaded", () => {
    initUser();
    initTheme();
    initTabs();
    initQuickSelectors();
    initCheckout();
    initAdminForm();
    initLiveSync();
    checkActiveReservation();
    loadRaffles();
  });
})();
