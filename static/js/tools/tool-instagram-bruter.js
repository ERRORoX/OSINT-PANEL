/**
 * Панель Instagram Bruter. Всё выполняется через панель.
 */
import { apiRun } from "../app.js";

const TOOL_ID = "instagram-bruter";

function escapeHtml(s) {
  if (s == null) return "";
  const t = String(s);
  return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

const RUNNING_KEY = "instagram-bruter-running";
let _pollIntervalId = null;

/** Из вывода брутера достаёт только список проверяемых паролей (без дубликатов, по порядку). */
function parsePasswordsFromOutput(output) {
  if (!output) return [];
  const seen = new Set();
  const list = [];
  const re = /\[-\]\s*Password:\s*(.+)/;
  output.split("\n").forEach((line) => {
    const m = line.match(re);
    if (m) {
      const pwd = m[1].trim();
      if (pwd && !seen.has(pwd)) {
        seen.add(pwd);
        list.push(pwd);
      }
    }
  });
  return list;
}

/** Последнее значение Attempts из вывода ([-] Attempts: N). */
function parseAttemptsFromOutput(output) {
  if (!output) return null;
  let last = null;
  const re = /\[-\]\s*Attempts:\s*(\d+)/;
  output.split("\n").forEach((line) => {
    const m = line.match(re);
    if (m) last = parseInt(m[1], 10);
  });
  return last;
}

function applyStatusToUI(st, resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, onFoundCallback) {
  const passwords = parsePasswordsFromOutput(st.output || "");
  const attempts = parseAttemptsFromOutput(st.output || "");
  const attemptsStr = attempts != null ? " (попыток: " + attempts + ")" : "";
  if (passwords.length) {
    resultEl.className = "result-box result-box--stream result-box--compact";
    resultEl.innerHTML = "<div class=\"stream-title\">Проверяются пароли" + attemptsStr + ":</div><ul class=\"password-list\">" +
      passwords.slice(-60).map((p) => "<li>" + escapeHtml(p) + "</li>").join("") + "</ul>";
  } else if (st.output) {
    resultEl.className = "result-box result-box--stream result-box--compact";
    resultEl.textContent = st.output.trim().split("\n").slice(-5).join("\n");
  } else {
    resultEl.className = "result-box result-box--stream result-box--compact";
    resultEl.textContent = "Ожидание вывода…";
  }
  if (st.done) {
    sessionStorage.removeItem(RUNNING_KEY);
    if (_pollIntervalId) {
      clearInterval(_pollIntervalId);
      _pollIntervalId = null;
    }
    statusEl.textContent = "";
    statusEl.className = "run-status";
    form.classList.remove("loading");
    if (submitBtn) submitBtn.disabled = false;
    if (submitBtn) submitBtn.style.display = "";
    if (stopBtn) stopBtn.style.display = "none";
    if (refreshBtn) refreshBtn.disabled = false;
    if (st.error) {
      resultEl.className = "result-box error";
      resultEl.textContent = (st.output ? st.output + "\n\n" : "") + st.error;
    } else if (st.found_password) {
      resultEl.className = "result-box success result-box--found";
      resultEl.innerHTML = "<div class=\"found-password\">Пароль найден: <strong>" + escapeHtml(st.found_password) + "</strong></div>";
      if (onFoundCallback) onFoundCallback();
    } else {
      resultEl.className = "result-box success result-box--compact";
      const pw = parsePasswordsFromOutput(st.output || "");
      if (pw.length) {
        const lastAttempts = parseAttemptsFromOutput(st.output || "");
        const sub = lastAttempts != null ? " (попыток: " + lastAttempts + ")" : "";
        resultEl.innerHTML = "<div class=\"stream-title\">Проверено паролей: " + pw.length + sub + "</div><ul class=\"password-list\">" +
          pw.slice(-80).map((p) => "<li>" + escapeHtml(p) + "</li>").join("") + "</ul>";
      } else {
        const out = st.result && st.result.output;
        resultEl.textContent = out != null ? out : (st.output || "Готово.");
      }
    }
    return true;
  }
  return false;
}

async function pollOnce(resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, onFoundCallback) {
  try {
    const res = await fetch("/api/tools/instagram-bruter/run-status");
    const st = await res.json();
    return applyStatusToUI(st, resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, onFoundCallback);
  } catch (_) {
    return false;
  }
}

function startPolling(resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, onFoundCallback) {
  if (_pollIntervalId) {
    clearInterval(_pollIntervalId);
    _pollIntervalId = null;
  }
  const run = async () => {
    const done = await pollOnce(resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, onFoundCallback);
    if (done) {
      if (_pollIntervalId) clearInterval(_pollIntervalId);
      _pollIntervalId = null;
    }
  };
  run(); // сразу один запрос
  const id = setInterval(run, 1500);
  _pollIntervalId = id;
  return id;
}

export function initPanel(container) {
  if (_pollIntervalId) {
    clearInterval(_pollIntervalId);
    _pollIntervalId = null;
  }
  container.innerHTML = `
    <h2>Instagram Bruter</h2>
    <p class="description">Списки паролей и прокси сохранены локально — работа офлайн и быстрее. Один раз нажмите «Обновить списки», затем вводите только имя аккаунта.</p>
    <div class="instagram-bruter-layout">
      <div class="instagram-bruter-left">
        <div class="form-group">
          <button type="button" id="btn-refresh-lists" class="btn btn-secondary">Обновить списки (пароли + прокси)</button>
          <span id="refresh-status" class="refresh-status"></span>
        </div>
        <form id="form-instagram-bruter" class="tool-form">
          <div class="form-group">
            <label>Имя пользователя или email Instagram</label>
            <input type="text" name="username" placeholder="username" required autocomplete="off">
            <span id="tried-count-hint" class="tried-count-hint" aria-live="polite"></span>
            <button type="button" id="btn-clear-tried" class="btn-link">Сбросить учёт проверенных паролей для этого аккаунта</button>
          </div>
          <div class="form-group">
            <label>Режим (количество потоков)</label>
            <select name="mode">
              <option value="0">0 — 32 потока</option>
              <option value="1">1 — 16 потоков</option>
              <option value="2" selected>2 — 8 потоков</option>
              <option value="3">3 — 4 потока</option>
            </select>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary" id="btn-start-bruter">Запустить</button>
            <button type="button" class="btn btn-danger" id="btn-stop-bruter" style="display:none">Остановить</button>
          </div>
        </form>
        <div id="status-instagram-bruter" class="run-status" role="status" aria-live="polite"></div>
      </div>
      <div class="instagram-bruter-right">
        <div id="result-instagram-bruter" class="result-box result-box--placeholder" role="status">Введите имя аккаунта и нажмите «Запустить» — здесь появится список проверяемых паролей и результат.</div>
        <div id="found-instagram-bruter" class="found-accounts-section">
          <h3 class="found-accounts-title">Найденные учётки</h3>
          <div id="found-instagram-bruter-list" class="found-accounts-list" aria-live="polite">Загрузка…</div>
        </div>
      </div>
    </div>
  `;

  const refreshBtn = container.querySelector("#btn-refresh-lists");
  const refreshStatus = container.querySelector("#refresh-status");
  refreshBtn.addEventListener("click", async () => {
    refreshStatus.textContent = "Загрузка…";
    refreshBtn.disabled = true;
    try {
      const res = await fetch("/api/tools/instagram-bruter/refresh-lists", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        refreshStatus.textContent = "Готово. " + (data.wordlist?.message || "") + " " + (data.proxies?.message || "");
        refreshStatus.className = "refresh-status success";
      } else {
        refreshStatus.textContent = (data.wordlist && !data.wordlist.ok ? data.wordlist.message + ". " : "") + (data.proxies && !data.proxies.ok ? data.proxies.message : data.error || "Ошибка");
        refreshStatus.className = "refresh-status error";
      }
    } catch (e) {
      refreshStatus.textContent = "Ошибка сети";
      refreshStatus.className = "refresh-status error";
    } finally {
      refreshBtn.disabled = false;
    }
  });

  const form = container.querySelector("#form-instagram-bruter");
  const resultEl = container.querySelector("#result-instagram-bruter");
  const statusEl = container.querySelector("#status-instagram-bruter");
  const submitBtn = container.querySelector("#btn-start-bruter");
  const stopBtn = container.querySelector("#btn-stop-bruter");
  const usernameInput = form.querySelector('input[name="username"]');
  const triedCountHint = container.querySelector("#tried-count-hint");

  let triedCountDebounce = null;
  usernameInput.addEventListener("input", () => {
    const uname = (usernameInput.value || "").trim();
    triedCountHint.textContent = "";
    if (triedCountDebounce) clearTimeout(triedCountDebounce);
    if (!uname) return;
    triedCountDebounce = setTimeout(async () => {
      triedCountDebounce = null;
      try {
        const res = await fetch("/api/tools/instagram-bruter/tried-count?username=" + encodeURIComponent(uname));
        const data = await res.json();
        if (data.count > 0) triedCountHint.textContent = "Для этого аккаунта уже проверено паролей: " + data.count;
      } catch (_) {}
    }, 400);
  });

  stopBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/tools/instagram-bruter/stop", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        statusEl.textContent = "Остановка…";
      const done = await pollOnce(resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, loadFoundList);
      if (!done) setTimeout(() => pollOnce(resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, loadFoundList), 800);
      }
    } catch (_) {}
  });

  container.querySelector("#btn-clear-tried").addEventListener("click", async () => {
    const username = (form.querySelector('input[name="username"]').value || "").trim();
    if (!username) {
      refreshStatus.textContent = "Введите имя аккаунта.";
      refreshStatus.className = "refresh-status error";
      return;
    }
    try {
      const res = await fetch("/api/tools/instagram-bruter/clear-tried", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const data = await res.json();
      refreshStatus.textContent = data.success ? "Готово. Учёт сброшен." : (data.error || "Ошибка");
      refreshStatus.className = data.success ? "refresh-status success" : "refresh-status error";
    } catch (e) {
      refreshStatus.textContent = "Ошибка сети";
      refreshStatus.className = "refresh-status error";
    }
  });

  form.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.ctrlKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const params = {
      username: (fd.get("username") || "").trim(),
      mode: fd.get("mode") || "2",
    };

    resultEl.textContent = "";
    resultEl.className = "result-box";
    resultEl.classList.remove("result-box--placeholder");
    statusEl.textContent = "Запуск…";
    statusEl.className = "run-status run-status--busy";
    form.classList.add("loading");
    if (submitBtn) submitBtn.disabled = true;
    if (submitBtn) submitBtn.style.display = "none";
    if (stopBtn) stopBtn.style.display = "inline-block";
    if (refreshBtn) refreshBtn.disabled = true;

    let data;
    try {
      data = await apiRun(TOOL_ID, params);
      if (data.started) {
        sessionStorage.setItem(RUNNING_KEY, "1");
        statusEl.textContent = "Перебор идёт — ниже видны проверяемые пароли. Можно переключить вкладку — при возврате вывод восстановится.";
        startPolling(resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, loadFoundList);
      } else {
        statusEl.textContent = "";
        statusEl.className = "run-status";
        if (submitBtn) submitBtn.style.display = "";
        if (stopBtn) stopBtn.style.display = "none";
        if (refreshBtn) refreshBtn.disabled = false;
        if (data.success) {
          resultEl.className = "result-box success";
          const out = data.response && data.response.output;
          resultEl.textContent = out != null ? out : (data.message || "Готово.");
        } else {
          resultEl.className = "result-box error";
          resultEl.textContent = data.error || "Ошибка";
        }
      }
    } catch (err) {
      statusEl.textContent = "";
      statusEl.className = "run-status";
      resultEl.className = "result-box error";
      resultEl.textContent = err.message || "Ошибка сети";
      if (submitBtn) submitBtn.style.display = "";
      if (stopBtn) stopBtn.style.display = "none";
    } finally {
      if (!data || !data.started) {
        form.classList.remove("loading");
        if (submitBtn) submitBtn.disabled = false;
      }
    }
  });

  async function loadFoundList() {
    const listEl = container.querySelector("#found-instagram-bruter-list");
    if (!listEl) return;
    try {
      const res = await fetch("/api/tools/instagram-bruter/found-list?limit=30");
      const data = await res.json();
      const found = (data.found || []);
      if (found.length === 0) {
        listEl.textContent = "Пока нет найденных учёток.";
        listEl.className = "found-accounts-list found-accounts-list--empty";
      } else {
        listEl.className = "found-accounts-list";
        listEl.innerHTML = "<ul class=\"found-accounts-ul\">" + found.map((r) =>
          "<li><span class=\"found-u\">" + escapeHtml(r.username) + "</span> : <span class=\"found-p\">" + escapeHtml(r.password) + "</span></li>"
        ).join("") + "</ul>";
      }
    } catch (_) {
      listEl.textContent = "Не удалось загрузить список.";
      listEl.className = "found-accounts-list found-accounts-list--empty";
    }
  }
  loadFoundList();

  // При открытии панели: показать текущий статус (перебор идёт или уже завершён)
  (async function checkRunning() {
    try {
      const res = await fetch("/api/tools/instagram-bruter/run-status");
      const st = await res.json();
      if (st.running && !st.done) {
        statusEl.textContent = "Перебор идёт — ниже видны проверяемые пароли.";
        statusEl.className = "run-status run-status--busy";
        form.classList.add("loading");
        if (submitBtn) submitBtn.disabled = true;
        if (submitBtn) submitBtn.style.display = "none";
        if (stopBtn) stopBtn.style.display = "inline-block";
        if (refreshBtn) refreshBtn.disabled = true;
        sessionStorage.setItem(RUNNING_KEY, "1");
        applyStatusToUI(st, resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, loadFoundList);
        startPolling(resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, loadFoundList);
      } else if (st.done && (st.result || st.error)) {
        sessionStorage.removeItem(RUNNING_KEY);
        applyStatusToUI(st, resultEl, statusEl, form, submitBtn, stopBtn, refreshBtn, loadFoundList);
      }
    } catch (_) {}
  })();
}
