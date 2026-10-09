/**
 * PixelPeak API — Cloudflare Worker + KV.
 * Совместим по API с server/ (FastAPI): /api/health, /api/register, /api/login, /api/me, /api/logout.
 *
 * Хранилище: Workers KV.
 *   user:<id>            -> { id, username, email, password_hash, uuid, is_admin, created_at, last_login }
 *   name:<lowername>     -> <id>
 *   email:<loweremail>   -> <id>
 *   session:<token>      -> { uid }   (auto-expire через expirationTtl)
 */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders();

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    try {
      const { pathname } = url;
      if (pathname === "/api/health" && request.method === "GET") {
        return json({ status: "ok", service: "PixelPeak (Worker/KV)", time: unix() }, 200, cors);
      }
      if (pathname === "/api/user_exists" && request.method === "GET") {
        return await userExists(url, env, cors);
      }
      if (pathname === "/api/register" && request.method === "POST") {
        return await register(request, env, cors);
      }
      if (pathname === "/api/login" && request.method === "POST") {
        return await login(request, env, cors);
      }
      if (pathname === "/api/me" && request.method === "GET") {
        return await me(request, env, cors);
      }
      if (pathname === "/api/logout" && request.method === "POST") {
        return await logout(request, env, cors);
      }

      // --- профиль: аватар и скин ---
      if (pathname === "/api/profile/avatar" && request.method === "POST") {
        return await uploadImage(request, env, cors, "avatar", false);
      }
      if (pathname === "/api/profile/skin" && request.method === "POST") {
        return await uploadImage(request, env, cors, "skin", true);
      }
      if (pathname.startsWith("/api/avatar/") && request.method === "GET") {
        return await serveImage(env, cors, "avatar", pathname.slice("/api/avatar/".length));
      }
      if (pathname.startsWith("/api/skin/") && request.method === "GET") {
        return await serveImage(env, cors, "skin", pathname.slice("/api/skin/".length));
      }
      if (pathname.startsWith("/api/user/") && request.method === "GET") {
        return await getUserProfile(env, cors, pathname.slice("/api/user/".length));
      }

      // --- CustomSkinLoader (скины в игре) ---
      if (pathname.startsWith("/api/csl/") && request.method === "GET") {
        const rest = pathname.slice("/api/csl/".length);
        if (rest.startsWith("textures/")) {
          return await cslTexture(env, cors, rest.slice("textures/".length));
        }
        if (rest.endsWith(".json")) {
          return await cslProfile(env, cors, rest.slice(0, -5));
        }
      }

      // --- группы ---
      if (pathname === "/api/groups" && request.method === "GET") {
        return await listGroups(request, env, cors);
      }
      if (pathname === "/api/groups" && request.method === "POST") {
        return await createGroup(request, env, cors);
      }
      if (pathname.startsWith("/api/groups/")) {
        const rest = pathname.slice("/api/groups/".length);
        const [gid, action] = rest.split("/");
        if (!action && request.method === "GET") return await getGroup(request, env, cors, gid);
        if (action === "members" && request.method === "POST") return await addMember(request, env, cors, gid);
        if (action === "leave" && request.method === "POST") return await leaveGroup(request, env, cors, gid);
        if (action === "delete" && request.method === "POST") return await deleteGroup(request, env, cors, gid);
      }

      return json({ detail: "Not found" }, 404, cors);
    } catch (err) {
      return json({ detail: String((err && err.message) || err) }, 500, cors);
    }
  },
};

const SESSION_TTL = 60 * 60 * 24 * 30;
const DEFAULT_ITERATIONS = 10000;
const USERNAME_RE = /^[A-Za-z0-9_]{3,16}$/;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
  };
}

function json(obj, status, cors) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...cors },
  });
}

function unix() {
  return Math.floor(Date.now() / 1000);
}

function bearer(request) {
  const h = request.headers.get("Authorization") || "";
  if (h.toLowerCase().startsWith("bearer ")) return h.slice(7).trim();
  return h.trim() || null;
}

function publicUser(u) {
  return {
    id: u.id,
    username: u.username,
    email: u.email,
    uuid: u.uuid,
    is_admin: !!u.is_admin,
    created_at: u.created_at,
    has_avatar: !!u.has_avatar,
    has_skin: !!u.has_skin,
  };
}

function avatarUrl(u) {
  return u && u.has_avatar ? `/api/avatar/${u.uuid}` : null;
}

function skinUrl(u) {
  return u && u.has_skin ? `/api/skin/${u.uuid}` : null;
}

function randomToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(48));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// --- KV helpers -------------------------------------------------------------

async function getJSON(env, key) {
  return await env.KV.get(key, "json");
}

async function putJSON(env, key, value, opts) {
  await env.KV.put(key, JSON.stringify(value), opts);
}

// --- пароли (совместимо с pbkdf2_sha256 из Python-бэкенда) ------------------

function b64encode(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

function b64decode(str) {
  const bin = atob(str);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

async function deriveBits(password, salt, iterations) {
  const enc = new TextEncoder();
  const baseKey = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    baseKey,
    256
  );
  return new Uint8Array(bits);
}

async function hashPassword(password, iterations) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const dk = await deriveBits(password, salt, iterations);
  return `pbkdf2_sha256$${iterations}$${b64encode(salt)}$${b64encode(dk)}`;
}

async function verifyPassword(password, stored) {
  try {
    const [algo, iters, saltB64, hashB64] = stored.split("$");
    if (algo !== "pbkdf2_sha256") return false;
    const salt = b64decode(saltB64);
    const expected = b64decode(hashB64);
    const dk = await deriveBits(password, salt, parseInt(iters, 10));
    if (dk.length !== expected.length) return false;
    let diff = 0;
    for (let i = 0; i < dk.length; i++) diff |= dk[i] ^ expected[i];
    return diff === 0;
  } catch {
    return false;
  }
}

// --- эндпоинты --------------------------------------------------------------

async function register(request, env, cors) {
  const body = await readJson(request);
  const username = String(body.username ?? "").trim();
  const email = String(body.email ?? "").trim().toLowerCase();
  const password = String(body.password ?? "");

  if (!USERNAME_RE.test(username)) {
    return json({ detail: "Ник: 3-16 символов, только A-Z, a-z, 0-9 и _" }, 422, cors);
  }
  if (!EMAIL_RE.test(email)) return json({ detail: "Некорректный email" }, 422, cors);
  if (password.length < 6) return json({ detail: "Пароль минимум 6 символов" }, 422, cors);

  const uname = username.toLowerCase();
  if (await env.KV.get("name:" + uname)) return json({ detail: "Такой ник уже занят" }, 409, cors);
  if (await env.KV.get("email:" + email)) return json({ detail: "Email уже зарегистрирован" }, 409, cors);

  const iterations = parseInt(env.PBKDF2_ITERATIONS || DEFAULT_ITERATIONS, 10);
  const hash = await hashPassword(password, iterations);
  const id = Date.now();
  const now = unix();
  const user = {
    id,
    username,
    email,
    password_hash: hash,
    uuid: offlineUuid(username),
    is_admin: 0,
    created_at: now,
    last_login: now,
  };

  await putJSON(env, "user:" + id, user);
  await env.KV.put("name:" + uname, String(id));
  await env.KV.put("email:" + email, String(id));
  await env.KV.put("uuid:" + user.uuid, String(id));

  const token = await createSession(env, id);
  return json({ token, user: publicUser(user) }, 201, cors);
}

async function login(request, env, cors) {
  const body = await readJson(request);
  const username = String(body.username ?? "").trim();
  const password = String(body.password ?? "");

  const key = username.toLowerCase();
  let id = await env.KV.get("name:" + key);
  if (!id) id = await env.KV.get("email:" + key);
  if (!id) return json({ detail: "Неверный ник или пароль" }, 401, cors);

  const user = await getJSON(env, "user:" + id);
  if (!user || !(await verifyPassword(password, user.password_hash))) {
    return json({ detail: "Неверный ник или пароль" }, 401, cors);
  }

  user.last_login = unix();
  await putJSON(env, "user:" + id, user);

  const token = await createSession(env, id);
  return json({ token, user: publicUser(user) }, 200, cors);
}

async function me(request, env, cors) {
  const user = await userFromRequest(request, env);
  if (!user) return json({ detail: "Сессия недействительна или истекла" }, 401, cors);
  return json(publicUser(user), 200, cors);
}

async function logout(request, env, cors) {
  const token = bearer(request);
  if (token) await env.KV.delete("session:" + token);
  return json({ ok: true }, 200, cors);
}

async function userFromRequest(request, env) {
  const token = bearer(request);
  if (!token) return null;
  const session = await getJSON(env, "session:" + token);
  if (!session) return null;
  return await getJSON(env, "user:" + session.uid);
}

async function createSession(env, userId) {
  const token = randomToken();
  await putJSON(env, "session:" + token, { uid: userId }, { expirationTtl: SESSION_TTL });
  return token;
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

async function userExists(url, env, cors) {
  const username = String(url.searchParams.get("username") || "").trim().toLowerCase();
  if (!username) return json({ exists: false, username: "" }, 200, cors);
  const id = await env.KV.get("name:" + username);
  return json({ exists: !!id, username }, 200, cors);
}

// --- профиль: аватар и скин ------------------------------------------------

function pngSize(b) {
  if (b.length < 24) return null;
  const sig = [137, 80, 78, 71, 13, 10, 26, 10];
  for (let i = 0; i < 8; i++) if (b[i] !== sig[i]) return null;
  const w = ((b[16] << 24) | (b[17] << 16) | (b[18] << 8) | b[19]) >>> 0;
  const h = ((b[20] << 24) | (b[21] << 16) | (b[22] << 8) | b[23]) >>> 0;
  return { w, h };
}

async function uploadImage(request, env, cors, kind, isSkin) {
  const user = await userFromRequest(request, env);
  if (!user) return json({ detail: "Требуется вход" }, 401, cors);

  const body = await readJson(request);
  const dataUrl = String(body.image || "");
  const m = /^data:image\/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=]+)$/i.exec(dataUrl);
  if (!m) return json({ detail: "Неверный формат изображения" }, 422, cors);

  let mime = "image/" + m[1].toLowerCase();
  if (mime === "image/jpg") mime = "image/jpeg";

  let bytes;
  try {
    const bin = atob(m[2]);
    bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  } catch {
    return json({ detail: "Не удалось прочитать изображение" }, 422, cors);
  }

  const max = isSkin ? 64 * 1024 : 512 * 1024;
  if (bytes.length > max) return json({ detail: "Файл слишком большой" }, 413, cors);

  if (isSkin) {
    const dim = pngSize(bytes);
    if (!dim) return json({ detail: "Скин должен быть PNG" }, 422, cors);
    if (!(dim.w === 64 && (dim.h === 64 || dim.h === 32))) {
      return json({ detail: "Скин должен быть 64×64 или 64×32" }, 422, cors);
    }
  }

  await putJSON(env, kind + ":" + user.id, { data: m[2], type: mime, updated: unix() });
  user["has_" + kind] = 1;
  await putJSON(env, "user:" + user.id, user);
  await env.KV.put("uuid:" + user.uuid, String(user.id));
  return json({ ok: true, url: `/${kind === "skin" ? "api/skin" : "api/avatar"}/${user.uuid}` }, 200, cors);
}

async function serveImage(env, cors, kind, uuid) {
  const uid = await env.KV.get("uuid:" + uuid);
  if (!uid) return new Response("Not found", { status: 404, headers: cors });
  const rec = await getJSON(env, kind + ":" + uid);
  if (!rec || !rec.data) return new Response("Not found", { status: 404, headers: cors });
  return new Response(b64decode(rec.data), {
    status: 200,
    headers: { "Content-Type": rec.type || "image/png", "Cache-Control": "public, max-age=120", ...cors },
  });
}

async function getUserProfile(env, cors, uuid) {
  const uid = await env.KV.get("uuid:" + uuid);
  if (!uid) return json({ detail: "Пользователь не найден" }, 404, cors);
  const u = await getJSON(env, "user:" + uid);
  if (!u) return json({ detail: "Пользователь не найден" }, 404, cors);
  return json(
    {
      username: u.username,
      uuid: u.uuid,
      created_at: u.created_at,
      has_avatar: !!u.has_avatar,
      avatar_url: avatarUrl(u),
      has_skin: !!u.has_skin,
      skin_url: skinUrl(u),
    },
    200,
    cors
  );
}

// --- CustomSkinLoader -------------------------------------------------------

async function sha256hex(input) {
  const data = typeof input === "string" ? new TextEncoder().encode(input) : input;
  const buf = await crypto.subtle.digest("SHA-256", data);
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function cslProfile(env, cors, username) {
  const name = decodeURIComponent(String(username || "")).toLowerCase();
  const id = await env.KV.get("name:" + name);
  if (!id) return json({ detail: "Not found" }, 404, cors);
  const u = await getJSON(env, "user:" + id);
  if (!u || !u.has_skin) return json({ detail: "No skin" }, 404, cors);
  const rec = await getJSON(env, "skin:" + id);
  if (!rec || !rec.data) return json({ detail: "No skin" }, 404, cors);

  const bytes = b64decode(rec.data);
  const hash = await sha256hex(bytes);
  await env.KV.put("csltex:" + hash, String(id));
  return json({ username: u.username, skin: hash, textures: { default: hash } }, 200, cors);
}

async function cslTexture(env, cors, hash) {
  const id = await env.KV.get("csltex:" + String(hash || "").toLowerCase());
  if (!id) return new Response("Not found", { status: 404, headers: cors });
  const rec = await getJSON(env, "skin:" + id);
  if (!rec || !rec.data) return new Response("Not found", { status: 404, headers: cors });
  return new Response(b64decode(rec.data), {
    status: 200,
    headers: { "Content-Type": rec.type || "image/png", "Cache-Control": "public, max-age=120", ...cors },
  });
}

// --- группы ----------------------------------------------------------------

function randomId(nbytes = 8) {
  const a = crypto.getRandomValues(new Uint8Array(nbytes));
  return [...a].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function listGroups(request, env, cors) {
  const user = await userFromRequest(request, env);
  if (!user) return json({ detail: "Требуется вход" }, 401, cors);
  const ids = (await getJSON(env, "usergroups:" + user.id)) || [];
  const groups = [];
  for (const gid of ids) {
    const g = await getJSON(env, "group:" + gid);
    if (g) {
      groups.push({
        id: g.id,
        name: g.name,
        owner: String(g.owner) === String(user.id),
        member_count: g.members.length,
        created_at: g.created_at,
      });
    }
  }
  return json({ groups }, 200, cors);
}

async function createGroup(request, env, cors) {
  const user = await userFromRequest(request, env);
  if (!user) return json({ detail: "Требуется вход" }, 401, cors);
  const body = await readJson(request);
  const name = String(body.name || "").trim().slice(0, 40) || "Моя группа";
  const requested = Array.isArray(body.members) ? body.members.slice(0, 20) : [];

  const memberIds = [String(user.id)];
  const notFound = [];
  for (const uname of requested) {
    const clean = String(uname || "").trim().toLowerCase();
    if (!clean) continue;
    const uid = await env.KV.get("name:" + clean);
    if (uid && !memberIds.includes(String(uid))) memberIds.push(String(uid));
    else if (!uid) notFound.push(String(uname).trim());
  }

  const id = randomId(8);
  const g = { id, name, owner: String(user.id), members: memberIds, created_at: unix() };
  await putJSON(env, "group:" + id, g);
  for (const uid of memberIds) {
    const list = (await getJSON(env, "usergroups:" + uid)) || [];
    if (!list.includes(id)) {
      list.push(id);
      await putJSON(env, "usergroups:" + uid, list);
    }
  }
  return json(
    { group: { id, name, member_count: memberIds.length, owner: true }, not_found: notFound },
    201,
    cors
  );
}

async function getGroup(request, env, cors, gid) {
  const user = await userFromRequest(request, env);
  if (!user) return json({ detail: "Требуется вход" }, 401, cors);
  const g = await getJSON(env, "group:" + gid);
  if (!g) return json({ detail: "Группа не найдена" }, 404, cors);
  if (!g.members.map(String).includes(String(user.id))) return json({ detail: "Нет доступа" }, 403, cors);

  const members = [];
  for (const uid of g.members) {
    const u = await getJSON(env, "user:" + uid);
    if (u) {
      members.push({
        username: u.username,
        uuid: u.uuid,
        owner: String(uid) === String(g.owner),
        has_avatar: !!u.has_avatar,
        avatar_url: avatarUrl(u),
        has_skin: !!u.has_skin,
        skin_url: skinUrl(u),
      });
    }
  }
  return json(
    { id: g.id, name: g.name, owner: String(g.owner) === String(user.id), created_at: g.created_at, members },
    200,
    cors
  );
}

async function addMember(request, env, cors, gid) {
  const user = await userFromRequest(request, env);
  if (!user) return json({ detail: "Требуется вход" }, 401, cors);
  const g = await getJSON(env, "group:" + gid);
  if (!g) return json({ detail: "Группа не найдена" }, 404, cors);
  if (!g.members.map(String).includes(String(user.id))) return json({ detail: "Нет доступа" }, 403, cors);

  const body = await readJson(request);
  const clean = String(body.username || "").trim().toLowerCase();
  if (!USERNAME_RE.test(clean)) return json({ detail: "Некорректный ник" }, 422, cors);
  const uid = await env.KV.get("name:" + clean);
  if (!uid) return json({ detail: `Игрок «${body.username}» не найден` }, 404, cors);

  if (!g.members.map(String).includes(String(uid))) {
    g.members.push(String(uid));
    await putJSON(env, "group:" + gid, g);
    const list = (await getJSON(env, "usergroups:" + uid)) || [];
    if (!list.includes(gid)) {
      list.push(gid);
      await putJSON(env, "usergroups:" + uid, list);
    }
  }
  return json({ ok: true, member_count: g.members.length }, 200, cors);
}

async function leaveGroup(request, env, cors, gid) {
  const user = await userFromRequest(request, env);
  if (!user) return json({ detail: "Требуется вход" }, 401, cors);
  const g = await getJSON(env, "group:" + gid);
  if (!g) return json({ detail: "Группа не найдена" }, 404, cors);

  const uid = String(user.id);
  g.members = g.members.filter((m) => String(m) !== uid);
  if (String(g.owner) === uid) {
    if (g.members.length) {
      g.owner = g.members[0];
      await putJSON(env, "group:" + gid, g);
    } else {
      await env.KV.delete("group:" + gid);
    }
  } else {
    await putJSON(env, "group:" + gid, g);
  }
  const list = (await getJSON(env, "usergroups:" + uid)) || [];
  await putJSON(env, "usergroups:" + uid, list.filter((x) => x !== gid));
  return json({ ok: true }, 200, cors);
}

async function deleteGroup(request, env, cors, gid) {
  const user = await userFromRequest(request, env);
  if (!user) return json({ detail: "Требуется вход" }, 401, cors);
  const g = await getJSON(env, "group:" + gid);
  if (!g) return json({ detail: "Группа не найдена" }, 404, cors);
  if (String(g.owner) !== String(user.id)) return json({ detail: "Удалять может только владелец" }, 403, cors);

  for (const uid of g.members) {
    const list = (await getJSON(env, "usergroups:" + uid)) || [];
    await putJSON(env, "usergroups:" + uid, list.filter((x) => x !== gid));
  }
  await env.KV.delete("group:" + gid);
  return json({ ok: true }, 200, cors);
}

// --- offline UUID (md5, как в Java offline-mode) ----------------------------

function offlineUuid(name) {
  const hex = md5("OfflinePlayer:" + name);
  const b = hex.match(/../g).map((h) => parseInt(h, 16));
  b[6] = (b[6] & 0x0f) | 0x30;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = b.map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

// Компактная реализация MD5 (Joseph Myers, public domain).
function md5cycle(x, k) {
  let a = x[0], b = x[1], c = x[2], d = x[3];
  a = ff(a, b, c, d, k[0], 7, -680876936);
  d = ff(d, a, b, c, k[1], 12, -389564586);
  c = ff(c, d, a, b, k[2], 17, 606105819);
  b = ff(b, c, d, a, k[3], 22, -1044525330);
  a = ff(a, b, c, d, k[4], 7, -176418897);
  d = ff(d, a, b, c, k[5], 12, 1200080426);
  c = ff(c, d, a, b, k[6], 17, -1473231341);
  b = ff(b, c, d, a, k[7], 22, -45705983);
  a = ff(a, b, c, d, k[8], 7, 1770035416);
  d = ff(d, a, b, c, k[9], 12, -1958414417);
  c = ff(c, d, a, b, k[10], 17, -42063);
  b = ff(b, c, d, a, k[11], 22, -1990404162);
  a = ff(a, b, c, d, k[12], 7, 1804603682);
  d = ff(d, a, b, c, k[13], 12, -40341101);
  c = ff(c, d, a, b, k[14], 17, -1502002290);
  b = ff(b, c, d, a, k[15], 22, 1236535329);

  a = gg(a, b, c, d, k[1], 5, -165796510);
  d = gg(d, a, b, c, k[6], 9, -1069501632);
  c = gg(c, d, a, b, k[11], 14, 643717713);
  b = gg(b, c, d, a, k[0], 20, -373897302);
  a = gg(a, b, c, d, k[5], 5, -701558691);
  d = gg(d, a, b, c, k[10], 9, 38016083);
  c = gg(c, d, a, b, k[15], 14, -660478335);
  b = gg(b, c, d, a, k[4], 20, -405537848);
  a = gg(a, b, c, d, k[9], 5, 568446438);
  d = gg(d, a, b, c, k[14], 9, -1019803690);
  c = gg(c, d, a, b, k[3], 14, -187363961);
  b = gg(b, c, d, a, k[8], 20, 1163531501);
  a = gg(a, b, c, d, k[13], 5, -1444681467);
  d = gg(d, a, b, c, k[2], 9, -51403784);
  c = gg(c, d, a, b, k[7], 14, 1735328473);
  b = gg(b, c, d, a, k[12], 20, -1926607734);

  a = hh(a, b, c, d, k[5], 4, -378558);
  d = hh(d, a, b, c, k[8], 11, -2022574463);
  c = hh(c, d, a, b, k[11], 16, 1839030562);
  b = hh(b, c, d, a, k[14], 23, -35309556);
  a = hh(a, b, c, d, k[1], 4, -1530992060);
  d = hh(d, a, b, c, k[4], 11, 1272893353);
  c = hh(c, d, a, b, k[7], 16, -155497632);
  b = hh(b, c, d, a, k[10], 23, -1094730640);
  a = hh(a, b, c, d, k[13], 4, 681279174);
  d = hh(d, a, b, c, k[0], 11, -358537222);
  c = hh(c, d, a, b, k[3], 16, -722521979);
  b = hh(b, c, d, a, k[6], 23, 76029189);
  a = hh(a, b, c, d, k[9], 4, -640364487);
  d = hh(d, a, b, c, k[12], 11, -421815835);
  c = hh(c, d, a, b, k[15], 16, 530742520);
  b = hh(b, c, d, a, k[2], 23, -995338651);

  a = ii(a, b, c, d, k[0], 6, -198630844);
  d = ii(d, a, b, c, k[7], 10, 1126891415);
  c = ii(c, d, a, b, k[14], 15, -1416354905);
  b = ii(b, c, d, a, k[5], 21, -57434055);
  a = ii(a, b, c, d, k[12], 6, 1700485571);
  d = ii(d, a, b, c, k[3], 10, -1894986606);
  c = ii(c, d, a, b, k[10], 15, -1051523);
  b = ii(b, c, d, a, k[1], 21, -2054922799);
  a = ii(a, b, c, d, k[8], 6, 1873313359);
  d = ii(d, a, b, c, k[15], 10, -30611744);
  c = ii(c, d, a, b, k[6], 15, -1560198380);
  b = ii(b, c, d, a, k[13], 21, 1309151649);
  a = ii(a, b, c, d, k[4], 6, -145523070);
  d = ii(d, a, b, c, k[11], 10, -1120210379);
  c = ii(c, d, a, b, k[2], 15, 718787259);
  b = ii(b, c, d, a, k[9], 21, -343485551);

  x[0] = add32(x[0], a);
  x[1] = add32(x[1], b);
  x[2] = add32(x[2], c);
  x[3] = add32(x[3], d);
}

function cmn(q, a, b, x, s, t) {
  a = add32(add32(a, q), add32(x, t));
  return add32((a << s) | (a >>> (32 - s)), b);
}

function ff(a, b, c, d, x, s, t) {
  return cmn((b & c) | (~b & d), a, b, x, s, t);
}
function gg(a, b, c, d, x, s, t) {
  return cmn((b & d) | (c & ~d), a, b, x, s, t);
}
function hh(a, b, c, d, x, s, t) {
  return cmn(b ^ c ^ d, a, b, x, s, t);
}
function ii(a, b, c, d, x, s, t) {
  return cmn(c ^ (b | ~d), a, b, x, s, t);
}

function add32(a, b) {
  return (a + b) & 0xffffffff;
}

function md5blk(s) {
  const md5blks = [];
  for (let i = 0; i < 64; i += 4) {
    md5blks[i >> 2] =
      s.charCodeAt(i) +
      (s.charCodeAt(i + 1) << 8) +
      (s.charCodeAt(i + 2) << 16) +
      (s.charCodeAt(i + 3) << 24);
  }
  return md5blks;
}

function md51(s) {
  const n = s.length;
  const state = [1732584193, -271733879, -1732584194, 271733878];
  let i;
  for (i = 64; i <= n; i += 64) {
    md5cycle(state, md5blk(s.substring(i - 64, i)));
  }
  s = s.substring(i - 64);
  const tail = new Array(16).fill(0);
  for (i = 0; i < s.length; i++) tail[i >> 2] |= s.charCodeAt(i) << ((i % 4) << 3);
  tail[i >> 2] |= 0x80 << ((i % 4) << 3);
  if (i > 55) {
    md5cycle(state, tail);
    for (i = 0; i < 16; i++) tail[i] = 0;
  }
  tail[14] = n * 8;
  md5cycle(state, tail);
  return state;
}

function rhex(n) {
  const hexChars = "0123456789abcdef";
  let s = "";
  for (let j = 0; j < 4; j++) {
    for (let i = 0; i < 4; i++) {
      s += hexChars.charAt((n[(j * 4 + i) >> 2] >> ((i * 8) % 32 + 4)) & 0x0f);
      s += hexChars.charAt((n[(j * 4 + i) >> 2] >> ((i * 8) % 32)) & 0x0f);
    }
  }
  return s;
}

function md5(s) {
  return rhex(md51(s));
}

export { offlineUuid, md5 };
