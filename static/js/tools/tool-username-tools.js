/**
 * Объединённый раздел «Поиск по имени пользователя»: Sherlock + Maigret.
 */
import { apiRun } from "../app.js";

export function initPanel(container) {
  container.innerHTML = `
    <div class="tool-view username-tools-page">
      <section class="tool-view-section username-tools-header">
        <h2 class="tool-view-section__title">ПОИСК ПО ИМЕНИ ПОЛЬЗОВАТЕЛЯ</h2>
        <p class="tool-cli-desc">Введите одно имя пользователя (без пробелов), затем запустите Sherlock и/или Maigret. Результаты появятся под каждой кнопкой.</p>
        <div class="username-tools-input-row">
          <div class="form-group">
            <label for="ut-username">Имя пользователя</label>
            <input type="text" id="ut-username" placeholder="username" autocomplete="off">
          </div>
          <button type="button" class="btn btn-secondary" id="ut-clear">Очистить всё</button>
        </div>
      </section>

      <section class="tool-view-section domain-tool-block" data-block="sherlock">
        <h3 class="domain-tool-block__title">Sherlock</h3>
        <p class="domain-tool-block__desc">Поиск по сотням соцсетей (GitHub, Twitter, Instagram и др.).</p>
        <button type="button" class="btn btn-primary btn-block-run" data-tool="sherlock">Запустить</button>
        <div class="domain-tool-block__status" data-status-for="sherlock"></div>
        <pre class="tool-terminal domain-tool-block__output" data-output-for="sherlock"></pre>
      </section>

      <section class="tool-view-section domain-tool-block" data-block="maigret">
        <h3 class="domain-tool-block__title">Maigret</h3>
        <p class="domain-tool-block__desc">Поиск по тысячам сайтов (расширенная база).</p>
        <button type="button" class="btn btn-primary btn-block-run" data-tool="maigret">Запустить</button>
        <div class="domain-tool-block__status" data-status-for="maigret"></div>
        <pre class="tool-terminal domain-tool-block__output" data-output-for="maigret"></pre>
      </section>
    </div>
  `;

  const usernameInput = container.querySelector("#ut-username");

  container.querySelector("#ut-clear").addEventListener("click", () => {
    usernameInput.value = "";
    container.querySelectorAll(".domain-tool-block__output").forEach((el) => { el.textContent = ""; el.className = "tool-terminal domain-tool-block__output"; });
    container.querySelectorAll(".domain-tool-block__status").forEach((el) => { el.textContent = ""; el.className = "domain-tool-block__status"; });
  });

  container.querySelectorAll(".btn-block-run").forEach((btnRun) => {
    btnRun.addEventListener("click", async () => {
      const toolId = btnRun.dataset.tool;
      const username = (usernameInput.value || "").trim();
      if (!username) {
        const statusEl = container.querySelector(`[data-status-for="${toolId}"]`);
        statusEl.textContent = "Сначала введите имя пользователя.";
        statusEl.className = "domain-tool-block__status error";
        return;
      }
      if (username.includes(" ")) {
        const statusEl = container.querySelector(`[data-status-for="${toolId}"]`);
        statusEl.textContent = "Введите одно имя без пробелов.";
        statusEl.className = "domain-tool-block__status error";
        return;
      }

      const statusEl = container.querySelector(`[data-status-for="${toolId}"]`);
      const outputEl = container.querySelector(`[data-output-for="${toolId}"]`);
      const prevText = btnRun.textContent;
      btnRun.textContent = "Подождите…";
      btnRun.disabled = true;
      statusEl.textContent = "Запуск… (может занять несколько минут)";
      statusEl.className = "domain-tool-block__status";

      try {
        const data = await apiRun(toolId, { username });
        statusEl.textContent = data.success ? "Готово." : (data.error || "Ошибка.");
        if (!data.success) statusEl.className = "domain-tool-block__status error";
        const out = (data.output || data.error || "").trim();
        outputEl.textContent = out || (data.error ? "" : "Нет результатов.");
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
