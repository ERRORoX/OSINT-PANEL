/**
 * Панель theHarvester: анализ домена — email, поддомены, имена.
 */
import { apiRun } from "../app.js";

const TOOL_ID = "theharvester";

/** Нормализация домена: убрать протокол, www, путь. */
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

const SOURCE_OPTIONS = [
  { id: "duckduckgo", label: "DuckDuckGo" },
  { id: "brave", label: "Brave Search" },
  { id: "crtsh", label: "Crt.sh (сертификаты)" },
  { id: "rapiddns", label: "RapidDNS" },
  { id: "hackertarget", label: "HackerTarget" },
  { id: "threatcrowd", label: "ThreatCrowd" },
  { id: "virustotal", label: "VirusTotal (API)" },
  { id: "shodan", label: "Shodan (API)" },
  { id: "hunter", label: "Hunter (API)" },
  { id: "securityTrails", label: "SecurityTrails (API)" },
  { id: "censys", label: "Censys (API)" },
  { id: "google", label: "Google" },
  { id: "bing", label: "Bing" },
  { id: "baidu", label: "Baidu" },
  { id: "yahoo", label: "Yahoo" },
];

export function initPanel(container) {
  container.innerHTML = `
    <div class="tool-cli-page tool-theharvester-page tool-view">
      <section class="tool-view-section tool-view-section--search">
        <h2 class="tool-view-section__title">DOMAIN SEARCH</h2>
        <p class="tool-cli-desc">Сбор email, поддоменов и IP по домену. Домен можно ввести с https:// — будет приведён к example.com. Выберите один или несколько источников.</p>
        <form id="form-theharvester" class="tool-cli-form">
          <div class="form-group">
            <label for="th-domain">Домен</label>
            <input type="text" id="th-domain" name="domain" placeholder="example.com или https://example.com" autocomplete="off">
            <span class="form-hint">Будет автоматически приведён к виду example.com</span>
          </div>
          <div class="form-group form-group-sources">
            <label>Источники (можно несколько)</label>
            <div class="th-sources-grid" id="th-sources"></div>
          </div>
          <div class="form-group form-group-inline">
            <label for="th-limit">Лимит</label>
            <input type="number" id="th-limit" name="limit" value="100" min="10" max="500">
          </div>
          <div class="tool-form-actions">
          <button type="submit" class="btn btn-primary" id="btn-th-run">SEARCH</button>
          <button type="button" class="btn btn-secondary" id="btn-th-clear">CLEAR</button>
        </div>
        </form>
        <div id="th-form-error" class="form-error" role="alert"></div>
      </section>
      <section class="tool-view-section tool-view-section--terminal">
        <h2 class="tool-view-section__title">LIVE TERMINAL</h2>
        <div id="th-status" class="tool-cli-status" role="status"></div>
        <pre id="th-output" class="tool-terminal"></pre>
      </section>
    </div>
  `;

  const sourcesEl = container.querySelector("#th-sources");
  SOURCE_OPTIONS.forEach(({ id, label }) => {
    const labelEl = document.createElement("label");
    labelEl.className = "th-source-check";
    labelEl.innerHTML = `<input type="checkbox" name="source" value="${id}"> ${label}`;
    sourcesEl.appendChild(labelEl);
  });
  container.querySelector('input[value="duckduckgo"]').checked = true;

  const form = container.querySelector("#form-theharvester");
  const formErrorEl = container.querySelector("#th-form-error");
  const statusEl = container.querySelector("#th-status");
  const outputEl = container.querySelector("#th-output");
  const btn = container.querySelector("#btn-th-run");
  const btnClear = container.querySelector("#btn-th-clear");

  if (btnClear) btnClear.addEventListener("click", () => {
    form.querySelector("#th-domain").value = "";
    form.querySelector("#th-limit").value = "100";
    form.querySelectorAll('input[name="source"]').forEach((c) => { c.checked = c.value === "duckduckgo"; });
    outputEl.textContent = "";
    outputEl.className = "tool-terminal";
    statusEl.textContent = "";
    statusEl.className = "tool-cli-status";
    setFormError("");
  });

  function setFormError(msg) {
    formErrorEl.textContent = msg || "";
    formErrorEl.style.display = msg ? "block" : "none";
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const domain = normalizeDomain(form.querySelector("#th-domain").value);
    const selectedSources = Array.from(form.querySelectorAll('input[name="source"]:checked')).map((c) => c.value);
    const sources = selectedSources.length ? selectedSources : ["duckduckgo"];
    let limit = parseInt(form.querySelector("#th-limit").value, 10) || 100;
    setFormError("");
    if (!domain) {
      setFormError("Укажите домен (например example.com).");
      return;
    }
    if (domain.includes(" ")) {
      setFormError("Домен не должен содержать пробелы.");
      return;
    }
    limit = Math.min(500, Math.max(10, limit));
    form.querySelector("#th-limit").value = limit;
    const btnText = btn.textContent;
    btn.textContent = "Подождите…";
    btn.disabled = true;
    btn.classList.add("is-loading");
    statusEl.textContent = sources.length > 1 ? `Запуск по ${sources.length} источникам…` : "Запуск theHarvester…";
    statusEl.className = "tool-cli-status";
    outputEl.textContent = "";
    outputEl.style.display = "block";
    try {
      const data = await apiRun(TOOL_ID, { domain, sources, limit });
      statusEl.textContent = data.success ? "Готово." : (data.error || "Ошибка.");
      if (!data.success) statusEl.className = "tool-cli-status error";
      const outRaw = (data.output || data.error || "").trim();
      outputEl.textContent = outRaw || (data.error ? "" : "По этому домену и источнику ничего не найдено.");
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
