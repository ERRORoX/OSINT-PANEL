/**
 * Панель «Поиск по домену» — модуль modules/domain_search (WHOIS, DNS, SSL, crt.sh).
 */
import { apiRun } from "../app.js";

const TOOL_ID = "domain-search";

function normalizeDomain(s) {
  if (!s || typeof s !== "string") return "";
  let t = s.trim().toLowerCase();
  if (t.startsWith("https://")) t = t.slice(8);
  else if (t.startsWith("http://")) t = t.slice(7);
  const slash = t.indexOf("/");
  if (slash !== -1) t = t.slice(0, slash);
  if (t.startsWith("www.")) t = t.slice(4);
  return t;
}

export function initPanel(container) {
  container.innerHTML = `
    <div class="tool-view tool-domain-search-page">
      <section class="tool-view-section tool-view-section--search">
        <h2 class="tool-view-section__title">ПОИСК ПО ДОМЕНУ</h2>
        <p class="tool-cli-desc">Введите домен — получите WHOIS, DNS, SSL-сертификат и поддомены с crt.sh. Домен можно ввести с https:// — будет приведён к виду example.com.</p>
        <form id="form-domain-search" class="tool-cli-form">
          <div class="form-group">
            <label for="ds-domain">Домен</label>
            <input type="text" id="ds-domain" name="domain" placeholder="example.com или https://example.com" autocomplete="off">
          </div>
          <div class="tool-form-actions">
            <button type="submit" class="btn btn-primary" id="btn-ds-run">Поиск</button>
            <button type="button" class="btn btn-secondary" id="btn-ds-clear">Очистить</button>
          </div>
        </form>
        <div id="ds-form-error" class="form-error" role="alert"></div>
      </section>
      <section class="tool-view-section tool-view-section--terminal">
        <h2 class="tool-view-section__title">РЕЗУЛЬТАТ</h2>
        <div id="ds-status" class="tool-cli-status" role="status"></div>
        <pre id="ds-output" class="tool-terminal"></pre>
      </section>
    </div>
  `;

  const form = container.querySelector("#form-domain-search");
  const formErrorEl = container.querySelector("#ds-form-error");
  const statusEl = container.querySelector("#ds-status");
  const outputEl = container.querySelector("#ds-output");
  const btn = container.querySelector("#btn-ds-run");
  const btnClear = container.querySelector("#btn-ds-clear");

  function setFormError(msg) {
    formErrorEl.textContent = msg || "";
    formErrorEl.style.display = msg ? "block" : "none";
  }

  if (btnClear) btnClear.addEventListener("click", () => {
    form.querySelector("#ds-domain").value = "";
    outputEl.textContent = "";
    outputEl.className = "tool-terminal";
    statusEl.textContent = "";
    statusEl.className = "tool-cli-status";
    setFormError("");
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const domain = normalizeDomain(form.querySelector("#ds-domain").value);
    setFormError("");
    if (!domain) {
      setFormError("Укажите домен (например example.com).");
      return;
    }
    if (domain.includes(" ")) {
      setFormError("Домен не должен содержать пробелы.");
      return;
    }

    const btnText = btn.textContent;
    btn.textContent = "Подождите…";
    btn.disabled = true;
    btn.classList.add("is-loading");
    statusEl.textContent = "Запрос WHOIS, DNS, SSL, crt.sh…";
    statusEl.className = "tool-cli-status";
    outputEl.textContent = "";
    outputEl.style.display = "block";

    try {
      const data = await apiRun(TOOL_ID, { domain });
      statusEl.textContent = data.success ? "Готово." : (data.error || "Ошибка.");
      if (!data.success) statusEl.className = "tool-cli-status error";
      const outRaw = (data.output || data.error || "").trim();
      outputEl.textContent = outRaw || (data.error ? "" : "Нет данных по домену.");
      outputEl.className = "tool-terminal " + (data.success ? "success" : "error");
    } catch (err) {
      statusEl.className = "tool-cli-status error";
      statusEl.textContent = err.message || "Ошибка запроса.";
      outputEl.textContent = err.message || "Ошибка сети";
      outputEl.className = "tool-terminal error";
    }
    btn.textContent = btnText;
    btn.disabled = false;
    btn.classList.remove("is-loading");
  });
}
