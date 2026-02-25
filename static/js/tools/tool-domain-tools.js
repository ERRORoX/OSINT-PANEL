/**
 * Объединённый раздел «Поиск по домену»: информация о домене (WHOIS, DNS, SSL, crt.sh) + theHarvester.
 */
import { apiRun } from "../app.js";

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
  { id: "crtsh", label: "Crt.sh" },
  { id: "rapiddns", label: "RapidDNS" },
  { id: "hackertarget", label: "HackerTarget" },
  { id: "threatcrowd", label: "ThreatCrowd" },
  { id: "virustotal", label: "VirusTotal (API)" },
  { id: "shodan", label: "Shodan (API)" },
  { id: "hunter", label: "Hunter (API)" },
  { id: "google", label: "Google" },
  { id: "bing", label: "Bing" },
];

export function initPanel(container) {
  container.innerHTML = `
    <div class="tool-view domain-tools-page">
      <section class="tool-view-section domain-tools-header">
        <h2 class="tool-view-section__title">ПОИСК ПО ДОМЕНУ</h2>
        <p class="tool-cli-desc">Введите домен (можно с https://), затем запустите нужный блок: информация о домене, theHarvester, Subfinder или dnsx.</p>
        <div class="domain-tools-domain-row">
          <div class="form-group">
            <label for="dt-domain">Домен</label>
            <input type="text" id="dt-domain" placeholder="example.com" autocomplete="off">
          </div>
          <button type="button" class="btn btn-secondary" id="dt-clear">Очистить всё</button>
        </div>
      </section>

      <section class="tool-view-section domain-tool-block" data-block="info">
        <h3 class="domain-tool-block__title">Информация о домене</h3>
        <p class="domain-tool-block__desc">WHOIS, DNS-записи, SSL-сертификат, поддомены с crt.sh.</p>
        <button type="button" class="btn btn-primary btn-block-run" data-tool="domain-search">Запустить</button>
        <div class="domain-tool-block__status" data-status-for="domain-search"></div>
        <pre class="tool-terminal domain-tool-block__output" data-output-for="domain-search"></pre>
      </section>

      <section class="tool-view-section domain-tool-block" data-block="theharvester">
        <h3 class="domain-tool-block__title">theHarvester</h3>
        <p class="domain-tool-block__desc">Email, поддомены, хосты по выбранным источникам.</p>
        <div class="form-group form-group-sources domain-tools-sources">
          <label>Источники (несколько)</label>
          <div class="th-sources-grid" id="dt-sources"></div>
        </div>
        <div class="form-group form-group-inline">
          <label for="dt-limit">Лимит</label>
          <input type="number" id="dt-limit" value="100" min="10" max="500">
        </div>
        <button type="button" class="btn btn-primary btn-block-run" data-tool="theharvester">Запустить</button>
        <div class="domain-tool-block__status" data-status-for="theharvester"></div>
        <pre class="tool-terminal domain-tool-block__output" data-output-for="theharvester"></pre>
      </section>

      <section class="tool-view-section domain-tool-block" data-block="subfinder">
        <h3 class="domain-tool-block__title">Subfinder</h3>
        <p class="domain-tool-block__desc">Пассивный поиск поддоменов (projectdiscovery). Нужен бинарник: соберите из tools/subfinder (go build) или установите в PATH.</p>
        <button type="button" class="btn btn-primary btn-block-run" data-tool="subfinder">Запустить</button>
        <div class="domain-tool-block__status" data-status-for="subfinder"></div>
        <pre class="tool-terminal domain-tool-block__output" data-output-for="subfinder"></pre>
      </section>

      <section class="tool-view-section domain-tool-block" data-block="dnsx">
        <h3 class="domain-tool-block__title">dnsx</h3>
        <p class="domain-tool-block__desc">DNS-запросы A, AAAA, CNAME по домену (projectdiscovery). Соберите: cd tools/dnsx && go build -buildvcs=false -o dnsx ./cmd/dnsx</p>
        <button type="button" class="btn btn-primary btn-block-run" data-tool="dnsx">Запустить</button>
        <div class="domain-tool-block__status" data-status-for="dnsx"></div>
        <pre class="tool-terminal domain-tool-block__output" data-output-for="dnsx"></pre>
      </section>
    </div>
  `;

  const domainInput = container.querySelector("#dt-domain");
  const sourcesEl = container.querySelector("#dt-sources");
  SOURCE_OPTIONS.forEach(({ id, label }) => {
    const labelEl = document.createElement("label");
    labelEl.className = "th-source-check";
    labelEl.innerHTML = `<input type="checkbox" name="source" value="${id}"> ${label}`;
    sourcesEl.appendChild(labelEl);
  });
  container.querySelector('input[value="duckduckgo"]').checked = true;

  function getDomain() {
    return normalizeDomain(domainInput.value);
  }

  container.querySelector("#dt-clear").addEventListener("click", () => {
    domainInput.value = "";
    container.querySelectorAll(".domain-tool-block__output").forEach((el) => { el.textContent = ""; el.className = "tool-terminal domain-tool-block__output"; });
    container.querySelectorAll(".domain-tool-block__status").forEach((el) => { el.textContent = ""; el.className = "domain-tool-block__status"; });
  });

  container.querySelectorAll(".btn-block-run").forEach((btnRun) => {
    btnRun.addEventListener("click", async () => {
      const toolId = btnRun.dataset.tool;
      const domain = getDomain();
      if (!domain) {
        const statusEl = container.querySelector(`[data-status-for="${toolId}"]`);
        statusEl.textContent = "Сначала введите домен.";
        statusEl.className = "domain-tool-block__status error";
        return;
      }

      const statusEl = container.querySelector(`[data-status-for="${toolId}"]`);
      const outputEl = container.querySelector(`[data-output-for="${toolId}"]`);
      const prevText = btnRun.textContent;
      btnRun.textContent = "Подождите…";
      btnRun.disabled = true;
      statusEl.textContent = "Запуск…";
      statusEl.className = "domain-tool-block__status";

      try {
        let data;
        if (toolId === "domain-search") {
          data = await apiRun("domain-search", { domain });
        } else if (toolId === "subfinder") {
          data = await apiRun("subfinder", { domain });
        } else if (toolId === "dnsx") {
          data = await apiRun("dnsx", { domain });
        } else {
          const sources = Array.from(container.querySelectorAll('input[name="source"]:checked')).map((c) => c.value);
          const limit = Math.min(500, Math.max(10, parseInt(container.querySelector("#dt-limit").value, 10) || 100));
          data = await apiRun("theharvester", { domain, sources: sources.length ? sources : ["duckduckgo"], limit });
        }
        statusEl.textContent = data.success ? "Готово." : (data.error || "Ошибка.");
        if (!data.success) statusEl.className = "domain-tool-block__status error";
        const out = (data.output || data.error || "").trim();
        outputEl.textContent = out || (data.error ? "" : "Нет данных.");
        outputEl.className = "tool-terminal domain-tool-block__output " + (data.success ? "success" : "error");
      } catch (err) {
        statusEl.className = "domain-tool-block__status error";
        statusEl.textContent = err.message || "Ошибка запроса.";
        outputEl.textContent = err.message || "";
        outputEl.className = "tool-terminal domain-tool-block__output error";
      }
      btnRun.textContent = prevText;
      btnRun.disabled = false;
    });
  });
}
