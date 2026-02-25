/**
 * Ядро приложения: загрузка списка инструментов, переключение панелей.
 * Логика каждого инструмента — в js/tools/tool-<id>.js (модули).
 */

const API = "/api";

let currentToolId = null;
const panels = new Map();

async function loadTools() {
  const res = await fetch(`${API}/tools`);
  if (!res.ok) throw new Error("Не удалось загрузить список инструментов");
  return res.json();
}

const DOMAIN_TOOLS_IDS = ["theharvester", "domain-search", "subfinder", "dnsx"];
const USERNAME_TOOLS_IDS = ["sherlock", "maigret"];

function renderNav(tools) {
  const nav = document.getElementById("nav-tools");
  const rest = tools.filter((t) => !DOMAIN_TOOLS_IDS.includes(t.id) && !USERNAME_TOOLS_IDS.includes(t.id));
  const toolLinks = rest.map(
    (t) => `<a href="#${t.id}" class="tool-link" data-tool-id="${t.id}">${escapeHtml(t.name)}</a>`
  ).join("");
  nav.innerHTML =
    '<a href="#dashboard" class="tool-link" data-tool-id="dashboard">Панель</a>' +
    '<a href="#domain-tools" class="tool-link" data-tool-id="domain-tools">Поиск по домену</a>' +
    '<a href="#username-tools" class="tool-link" data-tool-id="username-tools">Поиск по имени пользователя</a>' +
    toolLinks +
    '<a href="#reports" class="tool-link" data-tool-id="reports">Отчёты</a>';

  nav.querySelectorAll(".tool-link").forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      showTool(a.dataset.toolId);
    });
  });
}

function showTool(toolId) {
  if (currentToolId === toolId) return;
  currentToolId = toolId;
  window.location.hash = toolId;

  const mainEl = document.getElementById("main-content");
  if (mainEl) mainEl.dataset.currentTool = toolId || "";

  document.getElementById("panel-placeholder").classList.remove("active");
  document.querySelectorAll(".tool-panel").forEach((el) => el.classList.remove("active"));
  document.querySelectorAll(".tool-link").forEach((a) => {
    a.classList.toggle("active", a.dataset.toolId === toolId);
  });

  const panel = document.getElementById(`panel-${toolId}`);
  if (panel) {
    panel.classList.add("active");
    if (toolId === "dashboard") initDashboard(panel);
    else if (toolId === "reports") initReports(panel);
    else {
      const init = panels.get(toolId);
      if (typeof init === "function") init(panel);
    }
  } else {
    document.getElementById("panel-placeholder").classList.add("active");
    document.getElementById("panel-placeholder").textContent = `Инструмент "${toolId}" пока не подключён к панели.`;
  }
}

function initDashboard(panel) {
  if (panel.dataset.inited) return;
  panel.dataset.inited = "1";
  const tools = Array.from(document.querySelectorAll(".tool-link[data-tool-id]"))
    .filter((a) => !["dashboard", "reports", "settings"].includes(a.dataset.toolId))
    .map((a) => ({ id: a.dataset.toolId, name: a.textContent.trim() }));
  panel.innerHTML = `
    <div class="dashboard-page">
      <section class="dashboard-section dashboard-search">
        <h2 class="dashboard-title">Главная</h2>
        <p class="dashboard-desc">Выберите раздел в меню: поиск по домену, по имени пользователя или по email. Введите цель и запустите нужный инструмент.</p>
        <div class="dashboard-stats">
          <div class="dashboard-stat"><span class="dashboard-stat-value">—</span><span class="dashboard-stat-label">Найдено целей</span></div>
          <div class="dashboard-stat"><span class="dashboard-stat-value">—</span><span class="dashboard-stat-label">Активных задач</span></div>
          <div class="dashboard-stat"><span class="dashboard-stat-value">—</span><span class="dashboard-stat-label">Создано отчётов</span></div>
        </div>
      </section>
      <section class="dashboard-section dashboard-tools">
        <h3 class="dashboard-subtitle">Инструменты</h3>
        <div class="dashboard-tool-grid">
          ${tools.map((t) => `<a href="#${t.id}" class="dashboard-tool-card" data-tool-id="${t.id}">${escapeHtml(t.name)}</a>`).join("")}
        </div>
      </section>
    </div>
  `;
  panel.querySelectorAll(".dashboard-tool-card").forEach((a) => {
    a.addEventListener("click", (e) => { e.preventDefault(); showTool(a.dataset.toolId); });
  });
}

function initReports(panel) {
  if (panel.dataset.inited) return;
  panel.dataset.inited = "1";
  panel.innerHTML = `
    <div class="reports-page">
      <h2 class="reports-title">Последние отчёты</h2>
      <p class="reports-desc">Отчёты, сохранённые инструментами, появятся здесь.</p>
      <div class="reports-placeholder">Нет сохранённых отчётов</div>
    </div>
  `;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function registerPanel(toolId, initFn) {
  panels.set(toolId, initFn);
}

// Загрузка модулей только для инструментов, у которых есть своя панель в DOM
// (theharvester, domain-search, sherlock, maigret, subfinder встроены в domain-tools / username-tools)
async function loadToolModules(tools) {
  for (const t of tools) {
    if (!document.getElementById(`panel-${t.id}`)) continue;
    try {
      const mod = await import(`./tools/tool-${t.id}.js`);
      if (mod.initPanel) registerPanel(t.id, mod.initPanel);
    } catch (e) {
      console.warn(`Панель «${t.name}» не загружена:`, e.message);
    }
  }
}

async function init() {
  const tools = await loadTools();
  renderNav(tools);
  await loadToolModules(tools);
  try {
    const domainToolsMod = await import("./tools/tool-domain-tools.js");
    if (domainToolsMod.initPanel) registerPanel("domain-tools", domainToolsMod.initPanel);
  } catch (e) {
    console.warn("Панель «Поиск по домену» не загружена:", e.message);
  }
  try {
    const usernameToolsMod = await import("./tools/tool-username-tools.js");
    if (usernameToolsMod.initPanel) registerPanel("username-tools", usernameToolsMod.initPanel);
  } catch (e) {
    console.warn("Панель «Поиск по имени пользователя» не загружена:", e.message);
  }
  try {
    const settingsMod = await import("./settings.js");
    if (settingsMod.initPanel) registerPanel("settings", settingsMod.initPanel);
  } catch (e) {
    console.warn("Панель настроек не загружена:", e.message);
  }

  const hash = window.location.hash.slice(1);
  const validIds = ["dashboard", "reports", "settings", "domain-tools", "username-tools", ...tools.map((t) => t.id)];
  if (hash && validIds.includes(hash)) showTool(hash);
  else showTool("dashboard");

  window.addEventListener("hashchange", () => {
    const id = window.location.hash.slice(1);
    if (id) showTool(id);
  });

  const systemEl = document.getElementById("header-system");
  if (systemEl) {
    const ua = navigator.userAgent;
    if (ua.includes("Linux")) systemEl.textContent = "ОС: Linux";
    else if (ua.includes("Windows")) systemEl.textContent = "ОС: Windows";
    else if (ua.includes("Mac")) systemEl.textContent = "ОС: macOS";
    else systemEl.textContent = "ОС: —";
  }

  const btnUser = document.getElementById("btn-user-menu");
  const userMenu = document.getElementById("user-menu");
  if (btnUser && userMenu) {
    btnUser.addEventListener("click", () => {
      const open = btnUser.getAttribute("aria-expanded") === "true";
      btnUser.setAttribute("aria-expanded", !open);
      userMenu.hidden = open;
    });
    document.addEventListener("click", (e) => {
      if (!btnUser.contains(e.target) && !userMenu.contains(e.target)) {
        btnUser.setAttribute("aria-expanded", "false");
        userMenu.hidden = true;
      }
    });
  }
}

init().catch((e) => {
  const msg = e.message || "Нет связи с сервером";
  document.body.innerHTML = `<div class="init-error"><p><strong>Ошибка загрузки:</strong> ${escapeHtml(msg)}</p><p>Запустите сервер из корня проекта: <code>python run.py</code></p></div>`;
});

// Экспорт для модулей инструментов (вызов API). При ошибке возвращает текст от сервера (data.error).
export async function apiRun(toolId, params) {
  const res = await fetch(`${API}/tools/${toolId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.error || data.message || res.statusText || "Ошибка запроса";
    throw new Error(msg);
  }
  return data;
}

export { registerPanel };
