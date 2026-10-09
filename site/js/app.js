(function () {
  "use strict";

  const CFG = window.PIXELPEAK || { API_BASE: "", DOWNLOAD_URL: "#" };
  const TOKEN_KEY = "pixelpeak_token";
  const USER_KEY = "pixelpeak_user";

  function apiUrl(path) {
    return (CFG.API_BASE || "") + path;
  }

  function assetUrl(uuid, kind, bust) {
    return (CFG.API_BASE || "") + "/api/" + kind + "/" + uuid + (bust ? "?t=" + bust : "");
  }

  async function api(path, { method = "GET", body = null, token = null, adminKey = null } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;
    if (adminKey) headers["X-Admin-Key"] = adminKey;

    const res = await fetch(apiUrl(path), {
      method,
      headers,
      body: body ? JSON.stringify(body) : null,
    });

    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      data = null;
    }

    if (!res.ok) {
      let msg = (data && (data.detail || data.message)) || "Ошибка сервера";
      if (Array.isArray(msg)) msg = msg.map((m) => m.msg || m).join(", ");
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function setMsg(el, text, kind) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "form-msg" + (kind ? " " + kind : "");
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  // ---- auth storage ---------------------------------------------------------
  function getToken() { return localStorage.getItem("pixelpeak_token"); }
  function getUser() {
    try { return JSON.parse(localStorage.getItem("pixelpeak_user") || "null"); }
    catch (e) { return null; }
  }
  function setAuth(token, user) {
    localStorage.setItem("pixelpeak_token", token);
    localStorage.setItem("pixelpeak_user", JSON.stringify(user));
  }
  function clearAuth() {
    localStorage.removeItem("pixelpeak_token");
    localStorage.removeItem("pixelpeak_user");
  }

  function getAdminKey() { return sessionStorage.getItem("pixelpeak_adminkey") || ""; }
  function setAdminKey(k) {
    if (k) sessionStorage.setItem("pixelpeak_adminkey", k);
    else sessionStorage.removeItem("pixelpeak_adminkey");
  }

  // ---- nav ------------------------------------------------------------------
  function renderNav() {
    document.querySelectorAll(".nav-links").forEach((nav) => {
      if (getToken()) {
        const u = getUser() || {};
        nav.innerHTML =
          '<a href="index.html">Главная</a>' +
          '<a href="profile.html">Аккаунт</a>' +
          (u.is_admin ? '<a href="admin.html">Админ</a>' : "") +
          '<a href="#" data-logout>Выйти</a>';
        const lo = nav.querySelector("[data-logout]");
        if (lo) lo.addEventListener("click", (e) => {
          e.preventDefault();
          clearAuth();
          window.location.href = "index.html";
        });
      } else {
        nav.innerHTML =
          '<a href="index.html">Главная</a>' +
          '<a href="login.html">Войти</a>' +
          '<a class="btn btn-primary" href="register.html">Создать аккаунт</a>';
      }
    });
  }
  renderNav();

  // ---- index page -----------------------------------------------------------
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  const dl = document.getElementById("downloadLink");
  if (dl && CFG.DOWNLOAD_URL) dl.href = CFG.DOWNLOAD_URL;

  // ---- login ----------------------------------------------------------------
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("msg");
      setMsg(msg, "Входим...", "");
      const fd = new FormData(loginForm);
      try {
        const data = await api("/api/login", {
          method: "POST",
          body: {
            username: fd.get("username").trim(),
            password: fd.get("password"),
          },
        });
        setAuth(data.token, data.user);
        setMsg(msg, "Успешно! Перенаправляем...", "ok");
        setTimeout(() => (window.location.href = "profile.html"), 700);
      } catch (err) {
        setMsg(msg, err.message, "err");
      }
    });
  }

  // ---- register -------------------------------------------------------------
  const registerForm = document.getElementById("registerForm");
  if (registerForm) {
    registerForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("msg");
      setMsg(msg, "Создаём аккаунт...", "");
      const fd = new FormData(registerForm);
      try {
        const data = await api("/api/register", {
          method: "POST",
          body: {
            username: fd.get("username").trim(),
            email: fd.get("email").trim(),
            password: fd.get("password"),
          },
        });
        setAuth(data.token, data.user);
        setMsg(msg, "Аккаунт создан! Перенаправляем...", "ok");
        setTimeout(() => (window.location.href = "profile.html"), 800);
      } catch (err) {
        setMsg(msg, err.message, "err");
      }
    });
  }

  // ---- profile page ---------------------------------------------------------
  const profilePage = document.getElementById("profilePage");
  if (profilePage) initProfile();

  // ---- admin page -----------------------------------------------------------
  const adminPage = document.getElementById("adminPage");
  if (adminPage) initAdmin();

  async function initProfile() {
    if (!getToken()) {
      window.location.href = "login.html";
      return;
    }
    const token = getToken();
    let me;
    try {
      me = await api("/api/me", { token });
    } catch (err) {
      clearAuth();
      window.location.href = "login.html";
      return;
    }
    setAuth(token, me);
    renderAccount(me);

    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) logoutBtn.addEventListener("click", (e) => {
      e.preventDefault();
      clearAuth();
      window.location.href = "index.html";
    });

    const avatarInput = document.getElementById("avatarInput");
    const avatarBtn = document.getElementById("avatarBtn");
    if (avatarBtn && avatarInput) avatarBtn.addEventListener("click", () => avatarInput.click());
    if (avatarInput) avatarInput.addEventListener("change", async () => {
      const file = avatarInput.files[0];
      if (!file) return;
      const msg = document.getElementById("avatarMsg");
      try {
        setMsg(msg, "Загружаем...", "");
        const img = await fileToImage(file);
        const dataUrl = imageToDataUrlCover(img, 128);
        const res = await api("/api/profile/avatar", { method: "POST", token, body: { image: dataUrl } });
        const updated = Object.assign({}, me, { has_avatar: true });
        setAuth(token, updated); me = updated;
        renderAccount(me);
        setMsg(msg, "Аватарка обновлена", "ok");
        avatarInput.value = "";
      } catch (err) {
        setMsg(msg, err.message, "err");
      }
    });

    const skinInput = document.getElementById("skinInput");
    const skinBtn = document.getElementById("skinBtn");
    if (skinBtn && skinInput) skinBtn.addEventListener("click", () => skinInput.click());
    if (skinInput) skinInput.addEventListener("change", async () => {
      const file = skinInput.files[0];
      if (!file) return;
      const msg = document.getElementById("skinMsg");
      try {
        setMsg(msg, "Загружаем...", "");
        const dataUrl = await fileToDataUrl(file);
        await api("/api/profile/skin", { method: "POST", token, body: { image: dataUrl } });
        const updated = Object.assign({}, me, { has_skin: true });
        setAuth(token, updated); me = updated;
        renderAccount(me);
        setMsg(msg, "Скин обновлён", "ok");
        skinInput.value = "";
      } catch (err) {
        setMsg(msg, err.message, "err");
      }
    });

    const groupForm = document.getElementById("groupForm");
    if (groupForm) groupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("groupMsg");
      const fd = new FormData(groupForm);
      const members = String(fd.get("members") || "").split(/[,\s]+/).filter(Boolean);
      try {
        setMsg(msg, "Создаём...", "");
        const data = await api("/api/groups", {
          method: "POST", token,
          body: { name: String(fd.get("name") || "").trim(), members },
        });
        let text = "Группа создана";
        if (data.not_found && data.not_found.length) text += ". Не найдены: " + data.not_found.join(", ");
        setMsg(msg, text, "ok");
        groupForm.reset();
        await refreshGroups();
      } catch (err) {
        setMsg(msg, err.message, "err");
      }
    });

    await refreshGroups();
  }

  function renderAccount(me) {
    const name = document.getElementById("accName");
    if (name) name.textContent = me.username || "";
    const email = document.getElementById("accEmail");
    if (email) email.textContent = me.email || "";
    renderAvatar(me);
    renderSkin(me);
  }

  function renderAvatar(me) {
    const img = document.getElementById("accAvatar");
    const ph = document.getElementById("accAvatarPh");
    if (ph) ph.textContent = (me.username || "?").charAt(0).toUpperCase();
    if (!img) return;
    if (me.has_avatar && me.uuid) {
      img.onload = () => { img.style.display = ""; if (ph) ph.style.display = "none"; };
      img.onerror = () => { img.style.display = "none"; if (ph) ph.style.display = ""; };
      img.style.display = "none";
      img.src = assetUrl(me.uuid, "avatar", Date.now());
    } else {
      img.removeAttribute("src");
      img.style.display = "none";
      if (ph) ph.style.display = "";
    }
  }

  function renderSkin(me) {
    const canvas = document.getElementById("skinCanvas");
    const head = document.getElementById("skinHead");
    const empty = document.getElementById("skinEmpty");
    if (!canvas) return;
    if (!me.has_skin || !me.uuid) {
      if (empty) { empty.style.display = ""; empty.textContent = "Скин не загружен"; }
      canvas.style.display = "none";
      if (head) head.style.display = "none";
      return;
    }
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      if (empty) empty.style.display = "none";
      canvas.style.display = "";
      if (head) head.style.display = "";
      drawSkin(canvas, head, img);
    };
    img.onerror = () => {
      if (empty) { empty.style.display = ""; empty.textContent = "Скин не загружен"; }
      canvas.style.display = "none";
      if (head) head.style.display = "none";
    };
    img.src = assetUrl(me.uuid, "skin", Date.now());
  }

  function drawSkin(canvas, head, img) {
    canvas.width = 128; canvas.height = 128;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, 128, 128);
    ctx.drawImage(img, 0, 0, 64, 64, 0, 0, 128, 128);
    if (head) {
      head.width = 64; head.height = 64;
      const h = head.getContext("2d");
      h.imageSmoothingEnabled = false;
      h.clearRect(0, 0, 64, 64);
      h.drawImage(img, 8, 8, 8, 8, 0, 0, 64, 64);
    }
  }

  async function refreshGroups() {
    const token = getToken();
    const box = document.getElementById("groupList");
    if (!box) return;
    box.innerHTML = '<p class="muted">Загрузка...</p>';
    try {
      const data = await api("/api/groups", { token });
      if (!data.groups.length) {
        box.innerHTML = '<p class="muted">Пока нет групп. Создай первую!</p>';
        return;
      }
      box.innerHTML = "";
      data.groups.forEach((g) => {
        const el = document.createElement("div");
        el.className = "group-card";
        el.innerHTML =
          '<div><b>' + esc(g.name) + "</b>" +
          '<div class="muted small">' + (g.owner ? "ты владелец" : "участник") + " · " + g.member_count + " чел.</div></div>";
        const b = document.createElement("button");
        b.className = "btn btn-ghost";
        b.textContent = "Открыть";
        b.addEventListener("click", () => openGroup(g.id));
        el.appendChild(b);
        box.appendChild(el);
      });
    } catch (err) {
      box.innerHTML = '<p class="form-msg err">' + esc(err.message) + "</p>";
    }
  }

  async function openGroup(gid) {
    const token = getToken();
    const panel = document.getElementById("groupPanel");
    if (!panel) return;
    panel.style.display = "";
    panel.innerHTML = '<p class="muted">Загрузка...</p>';
    try {
      const g = await api("/api/groups/" + gid, { token });
      let html = '<div class="group-head"><h3>' + esc(g.name) + '</h3><button class="btn btn-ghost" id="closeGroup">Закрыть</button></div>';
      html += '<div class="member-list">';
      g.members.forEach((m) => {
        const av = m.has_avatar
          ? '<img class="mini-av" src="' + assetUrl(m.uuid, "avatar") + '" alt="">'
          : '<span class="mini-av ph">' + esc((m.username || "?").charAt(0).toUpperCase()) + "</span>";
        html += '<div class="member">' + av + "<span>" + esc(m.username) + "</span>" +
          (m.owner ? '<span class="tag">владелец</span>' : "") + "</div>";
      });
      html += "</div>";
      html += '<form class="add-member" id="addMemberForm"><input name="username" placeholder="ник игрока" /><button class="btn btn-primary" type="submit">Добавить</button></form>';
      html += '<div class="group-actions"><button class="btn btn-ghost" id="leaveGroup">Выйти</button>' +
        (g.owner ? '<button class="btn btn-ghost danger" id="deleteGroup">Удалить группу</button>' : "") + "</div>";
      html += '<div class="form-msg" id="groupPanelMsg"></div>';
      panel.innerHTML = html;

      document.getElementById("closeGroup").addEventListener("click", () => { panel.style.display = "none"; });

      document.getElementById("addMemberForm").addEventListener("submit", async (e) => {
        e.preventDefault();
        const msg = document.getElementById("groupPanelMsg");
        const fd = new FormData(e.target);
        try {
          setMsg(msg, "Добавляем...", "");
          await api("/api/groups/" + gid + "/members", {
            method: "POST", token,
            body: { username: String(fd.get("username") || "").trim() },
          });
          await openGroup(gid);
          await refreshGroups();
        } catch (err) {
          setMsg(msg, err.message, "err");
        }
      });

      document.getElementById("leaveGroup").addEventListener("click", async () => {
        try {
          await api("/api/groups/" + gid + "/leave", { method: "POST", token });
          panel.style.display = "none";
          await refreshGroups();
        } catch (err) {
          setMsg(document.getElementById("groupPanelMsg"), err.message, "err");
        }
      });

      const del = document.getElementById("deleteGroup");
      if (del) del.addEventListener("click", async () => {
        if (!confirm("Удалить группу для всех участников?")) return;
        try {
          await api("/api/groups/" + gid + "/delete", { method: "POST", token });
          panel.style.display = "none";
          await refreshGroups();
        } catch (err) {
          setMsg(document.getElementById("groupPanelMsg"), err.message, "err");
        }
      });
    } catch (err) {
      panel.innerHTML = '<p class="form-msg err">' + esc(err.message) + "</p>";
    }
  }

  // ---- admin page -----------------------------------------------------------
  let adminUsers = [];
  let adminIsOwner = false;

  async function initAdmin() {
    if (!getToken()) { window.location.href = "login.html"; return; }
    const token = getToken();
    let me;
    try {
      me = await api("/api/me", { token });
    } catch (err) {
      clearAuth();
      window.location.href = "login.html";
      return;
    }
    setAuth(token, me);
    renderNav();

    adminIsOwner = !!me.is_owner;

    if (!me.is_admin) {
      showAdminDenied();
      return;
    }

    const search = document.getElementById("adminSearch");
    if (search) search.addEventListener("input", () => {
      const q = search.value.trim().toLowerCase();
      const filtered = !q ? adminUsers : adminUsers.filter((u) =>
        u.username.toLowerCase().includes(q) ||
        (u.email || "").toLowerCase().includes(q) ||
        u.uuid.toLowerCase().includes(q));
      renderUsers(filtered);
    });

    const unlockForm = document.getElementById("adminUnlockForm");
    if (unlockForm) unlockForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("adminUnlockMsg");
      const fd = new FormData(unlockForm);
      try {
        setMsg(msg, "Проверяем...", "");
        const data = await api("/api/admin/unlock", {
          method: "POST",
          body: { password: String(fd.get("password") || "") },
        });
        setAdminKey(data.key);
        setMsg(msg, "", "");
        unlockForm.reset();
        await loadAdmin();
      } catch (err) {
        setMsg(msg, err.message, "err");
      }
    });

    await loadAdmin();
  }

  function showAdminDenied() {
    const denied = document.getElementById("adminDenied");
    if (denied) denied.style.display = "";
    const login = document.getElementById("adminLogin");
    if (login) login.style.display = "none";
    const content = document.getElementById("adminContent");
    if (content) content.style.display = "none";
  }

  function showAdminLogin() {
    const login = document.getElementById("adminLogin");
    if (login) login.style.display = "";
    const content = document.getElementById("adminContent");
    if (content) content.style.display = "none";
  }

  async function loadAdmin() {
    const token = getToken();
    const adminKey = getAdminKey();
    const statsBox = document.getElementById("adminStats");
    if (!adminKey && !adminIsOwner) { showAdminLogin(); return; }
    if (statsBox) statsBox.innerHTML = '<p class="muted">Загрузка...</p>';
    try {
      const data = await api("/api/admin/users", { token, adminKey });
      adminUsers = data.users || [];
      const login = document.getElementById("adminLogin");
      if (login) login.style.display = "none";
      const content = document.getElementById("adminContent");
      if (content) content.style.display = "";
      renderStats(data.stats || {});
      renderUsers(adminUsers);
    } catch (err) {
      if (err.status === 401 && !adminIsOwner) {
        setAdminKey("");
        showAdminLogin();
        const msg = document.getElementById("adminUnlockMsg");
        setMsg(msg, "Пароль истёк — введите заново", "err");
        return;
      }
      if (statsBox) statsBox.innerHTML = '<p class="form-msg err">' + esc(err.message) + "</p>";
    }
  }

  function renderStats(s) {
    const box = document.getElementById("adminStats");
    if (!box) return;
    const items = [
      ["Всего игроков", s.total],
      ["Онлайн 24ч", s.online_24h],
      ["Онлайн 7д", s.online_7d],
      ["Админов", s.admins],
      ["Со скином", s.with_skin],
      ["С аватаркой", s.with_avatar],
      ["Групп", s.groups],
    ];
    box.innerHTML = items.map((it) =>
      '<div class="stat-card"><div class="stat-val">' + (it[1] || 0) +
      '</div><div class="stat-label">' + esc(it[0]) + "</div></div>"
    ).join("");
  }

  function fmtDate(ts) {
    if (!ts) return "—";
    return new Date(ts * 1000).toLocaleString("ru-RU", {
      day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }

  function renderUsers(users) {
    const box = document.getElementById("adminTable");
    if (!box) return;
    if (!users.length) { box.innerHTML = '<p class="muted">Нет игроков</p>'; return; }
    let html = '<table class="admin-table"><thead><tr>' +
      "<th></th><th>Ник</th><th>Email</th><th>UUID</th><th>Групп</th>" +
      "<th>Регистрация</th><th>Последний вход</th><th>Скин</th><th>Роль</th>" +
      "</tr></thead><tbody>";
    users.forEach((u) => {
      const av = u.has_avatar
        ? '<img class="mini-av" src="' + assetUrl(u.uuid, "avatar") + '" alt="">'
        : '<span class="mini-av ph">' + esc((u.username || "?").charAt(0).toUpperCase()) + "</span>";
      html += '<tr data-uuid="' + esc(u.uuid) + '" class="admin-row">' +
        "<td>" + av + "</td>" +
        "<td><b>" + esc(u.username) + "</b></td>" +
        '<td class="muted small">' + esc(u.email) + "</td>" +
        '<td class="muted small mono">' + esc(u.uuid) + "</td>" +
        "<td>" + u.groups + "</td>" +
        '<td class="muted small">' + fmtDate(u.created_at) + "</td>" +
        '<td class="muted small">' + fmtDate(u.last_login) + "</td>" +
        "<td>" + (u.has_skin ? '<span class="tag ok">есть</span>' : '<span class="muted small">—</span>') + "</td>" +
        "<td>" + (u.is_admin ? '<span class="tag">админ</span>' : '<span class="muted small">игрок</span>') + "</td>" +
        "</tr>";
    });
    html += "</tbody></table>";
    box.innerHTML = html;
    box.querySelectorAll(".admin-row").forEach((row) => {
      row.addEventListener("click", () => openUser(row.getAttribute("data-uuid")));
    });
  }

  async function openUser(uuid) {
    const token = getToken();
    const adminKey = getAdminKey();
    const panel = document.getElementById("adminPanel");
    if (!panel) return;
    panel.style.display = "";
    panel.innerHTML = '<p class="muted">Загрузка...</p>';
    try {
      const u = await api("/api/admin/users/" + uuid, { token, adminKey });
      const skin = u.has_skin
        ? '<img class="skin-thumb" src="' + assetUrl(u.uuid, "skin", Date.now()) + '" alt="">'
        : '<span class="muted">нет</span>';
      let html = '<div class="group-head"><h3>' + esc(u.username) +
        '</h3><button class="btn btn-ghost" id="closeUser">Закрыть</button></div>';
      html += '<div class="admin-detail">' +
        '<div><span class="muted">Email:</span> ' + esc(u.email) + "</div>" +
        '<div><span class="muted">UUID:</span> <span class="mono">' + esc(u.uuid) + "</span></div>" +
        '<div><span class="muted">Регистрация:</span> ' + fmtDate(u.created_at) + "</div>" +
        '<div><span class="muted">Последний вход:</span> ' + fmtDate(u.last_login) + "</div>" +
        '<div><span class="muted">Скин:</span> ' + skin + "</div>" +
        "</div>";
      html += "<h4>Группы</h4>";
      if (!u.groups || !u.groups.length) html += '<p class="muted">Нет групп</p>';
      else html += '<div class="member-list">' + u.groups.map((g) =>
        '<div class="member"><span>' + esc(g.name) + "</span>" +
        (g.owner ? '<span class="tag">владелец</span>' : "") +
        '<span class="muted small">' + g.member_count + " чел.</span></div>"
      ).join("") + "</div>";
      html += '<div class="group-actions"><button class="btn ' +
        (u.is_admin ? "btn-ghost danger" : "btn-primary") + '" id="toggleAdmin">' +
        (u.is_admin ? "Снять админа" : "Сделать админом") + "</button></div>";
      html += '<div class="form-msg" id="adminPanelMsg"></div>';
      panel.innerHTML = html;

      document.getElementById("closeUser").addEventListener("click", () => { panel.style.display = "none"; });
      document.getElementById("toggleAdmin").addEventListener("click", async () => {
        const msg = document.getElementById("adminPanelMsg");
        try {
          setMsg(msg, "Сохраняем...", "");
          await api("/api/admin/users/" + uuid + "/admin", {
            method: "POST", token, adminKey, body: { admin: !u.is_admin },
          });
          setMsg(msg, "Готово", "ok");
          await loadAdmin();
          panel.style.display = "none";
        } catch (err) {
          setMsg(msg, err.message, "err");
        }
      });
    } catch (err) {
      panel.innerHTML = '<p class="form-msg err">' + esc(err.message) + "</p>";
    }
  }

  // ---- file helpers ---------------------------------------------------------
  function fileToImage(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Не удалось открыть изображение")); };
      img.src = url;
    });
  }

  function fileToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve(r.result);
      r.onerror = () => reject(new Error("Не удалось прочитать файл"));
      r.readAsDataURL(file);
    });
  }

  function imageToDataUrlCover(img, size) {
    const c = document.createElement("canvas");
    c.width = size; c.height = size;
    const ctx = c.getContext("2d");
    const s = Math.min(img.width, img.height);
    const sx = (img.width - s) / 2;
    const sy = (img.height - s) / 2;
    ctx.drawImage(img, sx, sy, s, s, 0, 0, size, size);
    return c.toDataURL("image/png");
  }

  window.PixelPeak = { api, apiUrl, assetUrl, getToken, getUser, setAuth, clearAuth };
})();
