(function () {
  "use strict";

  const CFG = window.PIXELPEAK || { API_BASE: "", DOWNLOAD_URL: "#" };

  function apiUrl(path) {
    return (CFG.API_BASE || "") + path;
  }

  async function api(path, { method = "GET", body = null, token = null } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;

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
      throw new Error(msg);
    }
    return data;
  }

  function setMsg(el, text, kind) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "form-msg" + (kind ? " " + kind : "");
  }

  // ---- index page ---------------------------------------------------------
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  const dl = document.getElementById("downloadLink");
  if (dl && CFG.DOWNLOAD_URL) dl.href = CFG.DOWNLOAD_URL;

  // ---- login --------------------------------------------------------------
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
        localStorage.setItem("pixelpeak_token", data.token);
        localStorage.setItem("pixelpeak_user", JSON.stringify(data.user));
        setMsg(msg, "Успешно! Перенаправляем...", "ok");
        setTimeout(() => (window.location.href = "index.html"), 700);
      } catch (err) {
        setMsg(msg, err.message, "err");
      }
    });
  }

  // ---- register -----------------------------------------------------------
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
        localStorage.setItem("pixelpeak_token", data.token);
        localStorage.setItem("pixelpeak_user", JSON.stringify(data.user));
        setMsg(msg, "Аккаунт создан! Перенаправляем...", "ok");
        setTimeout(() => (window.location.href = "index.html"), 800);
      } catch (err) {
        setMsg(msg, err.message, "err");
      }
    });
  }

  window.PixelPeak = { api, apiUrl };
})();
