/**
 * Панель Google OSINT: email — Holehe и h8mail, все ответы в одной панели.
 */
import { apiRun } from "../app.js";

const TOOL_ID = "google-osint";

function escapeHtml(s) {
  if (s == null) return "";
  const t = String(s);
  return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function initPanel(container) {
  container.innerHTML = `
    <div class="tool-google-osint-page tool-view">
      <section class="tool-view-section tool-view-section--search">
        <h2 class="tool-view-section__title">EMAIL SEARCH</h2>
        <p class="tool-cli-desc">Введите email — Holehe (сайты по email) и h8mail (утечки). Для h8mail добавьте API-ключи в «API ключи».</p>
        <form id="form-google-osint" class="tool-google-osint-form">
          <div class="form-group">
            <label for="go-email">Email</label>
            <input type="text" id="go-email" name="email" placeholder="user@gmail.com">
          </div>
          <div class="tool-google-osint-checkboxes">
            <label class="grabcam-feature-check"><input type="checkbox" name="run_holehe" id="go-run-holehe" checked> Holehe</label>
            <label class="grabcam-feature-check"><input type="checkbox" name="run_h8mail" id="go-run-h8mail" checked> h8mail</label>
          </div>
          <div class="tool-form-actions">
            <button type="submit" class="btn btn-primary" id="btn-go-run">SEARCH</button>
            <button type="button" class="btn btn-secondary" id="btn-go-clear">CLEAR</button>
          </div>
        </form>
      </section>
      <section class="tool-view-section tool-view-section--terminal">
        <h2 class="tool-view-section__title">LIVE TERMINAL</h2>
        <div id="go-terminal" class="tool-terminal" role="log"></div>
        <div id="go-status" class="tool-cli-status" role="status"></div>
      </section>
      <section class="tool-view-section tool-view-section--results">
        <h2 class="tool-view-section__title">RESULTS OVERVIEW</h2>
        <div id="go-results" class="tool-google-osint-results tool-results-overview"></div>
      </section>
    </div>
  `;

  const form = container.querySelector("#form-google-osint");
  const statusEl = container.querySelector("#go-status");
  const terminalEl = container.querySelector("#go-terminal");
  const resultsEl = container.querySelector("#go-results");
  const btn = container.querySelector("#btn-go-run");
  const btnClear = container.querySelector("#btn-go-clear");
  if (btnClear) btnClear.addEventListener("click", () => {
    form.querySelector("#go-email").value = "";
    terminalEl.textContent = "";
    statusEl.textContent = "";
    statusEl.className = "tool-cli-status";
    resultsEl.innerHTML = "";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = (form.querySelector("#go-email").value || "").trim();
    const run_holehe = form.querySelector("#go-run-holehe").checked;
    const run_h8mail = form.querySelector("#go-run-h8mail").checked;

    if (!email || !email.includes("@")) {
      statusEl.textContent = "Укажите email.";
      statusEl.className = "tool-cli-status error";
      return;
    }
    statusEl.className = "tool-cli-status";
    statusEl.textContent = "";

    const btnText = btn.textContent;
    btn.textContent = "Подождите…";
    btn.disabled = true;
    btn.classList.add("is-loading");
    statusEl.textContent = "Запуск…";
    terminalEl.textContent = "[+] Searching for email: " + email + "\n[+] Running Holehe, h8mail…";
    resultsEl.innerHTML = "";

    try {
      const data = await apiRun(TOOL_ID, {
        email,
        run_holehe,
        run_h8mail,
      });

      statusEl.className = "tool-cli-status " + (data.success ? "" : "error");
      statusEl.textContent = data.success ? "Готово." : (data.error || "Часть проверок завершилась с ошибками.");
      const results = data.results || {};
      const sections = [
        { key: "holehe", title: "Holehe (сайты по email)" },
        { key: "h8mail", title: "h8mail (утечки)" },
      ];
      const logParts = sections.map(({ key, title }) => {
        const r = results[key] || {};
        const out = (r.output || "").trim() || "(нет вывода)";
        return `========== ${title} ==========\n${out}`;
      });
      const fullLog = logParts.join("\n\n");
      terminalEl.textContent = "[+] Email: " + email + "\n" + fullLog;

      const blocksHtml = sections
        .map(({ key, title }) => {
          const r = results[key] || {};
          const rawOut = (r.output || "").trim();
          const out = rawOut || "(нет вывода)";
          const ok = r.success;
          return `
            <div class="tool-results-card tool-google-osint-block ${ok ? "success" : "error"}">
              <h3 class="tool-results-card__title">${escapeHtml(title)}</h3>
              <div class="tool-results-card__content"><pre>${escapeHtml(out)}</pre></div>
            </div>
          `;
        })
        .join("");

      resultsEl.innerHTML = blocksHtml;
    } catch (err) {
      statusEl.className = "tool-cli-status error";
      statusEl.textContent = err.message || "Ошибка запроса.";
      terminalEl.textContent = (terminalEl.textContent || "") + "\n[!] " + (err.message || "Ошибка сети");
      resultsEl.innerHTML = "";
    }
    btn.textContent = btnText;
    btn.disabled = false;
    btn.classList.remove("is-loading");
  });
}
