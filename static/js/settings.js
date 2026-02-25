/**
 * Вкладка «API ключи»: поля для ключей, сохранение в .env, кнопка «Помощь» у каждого поля.
 */
const API = "/api";

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

export function initPanel(container) {
  container.innerHTML = `
    <h2>API ключи</h2>
    <p class="description">Ключи сохраняются в файл .env в корне проекта. Каждый ключ — отдельное поле.</p>
    <form id="form-settings-keys">
      <div id="settings-keys-list"></div>
      <button type="submit" class="btn btn-primary btn-save">Сохранить</button>
    </form>
    <div id="settings-message" class="settings-message" role="status"></div>
  `;

  const listEl = container.querySelector("#settings-keys-list");
  const form = container.querySelector("#form-settings-keys");
  const messageEl = container.querySelector("#settings-message");

  function showMessage(text, isError = false) {
    messageEl.textContent = text;
    messageEl.className = "settings-message " + (isError ? "error" : "success");
    messageEl.style.display = text ? "block" : "none";
  }

  async function loadKeys() {
    const res = await fetch(`${API}/settings/keys`);
    if (!res.ok) throw new Error("Не удалось загрузить настройки");
    const data = await res.json();
    listEl.innerHTML = data.keys
      .map(
        (k) => `
      <div class="settings-key-row" data-key-id="${escapeHtml(k.id)}">
        <label>${escapeHtml(k.label)}</label>
        <div class="key-input-wrap">
          <input type="password" name="${escapeHtml(k.id)}" placeholder="${k.isSet ? "Ключ сохранён (введите новый, чтобы заменить)" : "Введите ключ"}" autocomplete="off">
          <button type="button" class="btn-help" aria-expanded="false" data-key-id="${escapeHtml(k.id)}">Помощь</button>
        </div>
        <div class="help-block" id="help-${escapeHtml(k.id)}" role="region">
          ${escapeHtml(k.helpText)}<br>
          <a href="${escapeHtml(k.helpUrl)}" target="_blank" rel="noopener">Инструкция и получение ключа →</a>
        </div>
      </div>
    `
      )
      .join("");

    listEl.querySelectorAll(".btn-help").forEach((btn) => {
      btn.addEventListener("click", () => {
        const keyId = btn.dataset.keyId;
        const block = document.getElementById(`help-${keyId}`);
        const open = block.classList.toggle("visible");
        btn.setAttribute("aria-expanded", open);
      });
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const payload = {};
    listEl.querySelectorAll('input[name]').forEach((input) => {
      const v = (fd.get(input.name) || "").trim();
      payload[input.name] = v;
    });
    showMessage("");
    try {
      const res = await fetch(`${API}/settings/keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(res.statusText);
      showMessage("Ключи сохранены в .env");
    } catch (err) {
      showMessage("Ошибка: " + err.message, true);
    }
  });

  loadKeys().catch((err) => showMessage("Ошибка загрузки: " + err.message, true));
}
