/**
 * Панель инструмента ANONSMS. Работает независимо от других модулей.
 * Использует только apiRun из app.js и разметку внутри переданного container.
 */
import { apiRun } from "../app.js";

const TOOL_ID = "anonsms";

function formatAnonsmsResult(r) {
  const lines = [];
  if (r.success === true) {
    lines.push("✓ SMS отправлено");
  }
  if (r.textId != null) {
    lines.push(`ID сообщения: ${r.textId}`);
  }
  if (r.quotaRemaining != null) {
    lines.push(`Осталось в квоте: ${r.quotaRemaining}`);
  }
  if (lines.length === 0) {
    return JSON.stringify(r, null, 2);
  }
  return lines.join("\n");
}

export function initPanel(container) {
  container.innerHTML = `
    <div class="tool-view tool-anonsms-view">
      <section class="tool-view-section tool-view-section--search">
        <h2 class="tool-view-section__title">SMS SEND</h2>
        <p class="description">Отправка SMS через textbelt. Ключ настраивается во вкладке «API ключи».</p>
        <form id="form-anonsms" class="tool-form">
          <div class="phone-row">
            <div class="form-group">
              <label>Код страны</label>
              <input type="text" name="country_code" placeholder="7" maxlength="4" value="7">
            </div>
            <div class="form-group">
              <label>Номер телефона</label>
              <input type="text" name="phone_number" placeholder="9001234567" maxlength="15">
            </div>
          </div>
          <div class="form-group form-group-message">
            <label id="label-message-anonsms" class="label-message">Сообщение</label>
            <textarea name="message" placeholder="Текст SMS"></textarea>
          </div>
          <div id="countdown-anonsms" class="countdown-box" role="status" aria-live="polite"></div>
          <button type="submit" class="btn btn-primary">SEND</button>
        </form>
        <div id="form-error-anonsms" class="form-error" role="alert"></div>
      </section>
      <section class="tool-view-section tool-view-section--results">
        <h2 class="tool-view-section__title">RESULT</h2>
        <div id="result-anonsms" class="result-box tool-results-card" role="status"></div>
      </section>
    </div>
  `;

  const form = container.querySelector("#form-anonsms");
  const formErrorEl = container.querySelector("#form-error-anonsms");
  const resultEl = container.querySelector("#result-anonsms");
  const countdownEl = container.querySelector("#countdown-anonsms");
  const labelMessageEl = container.querySelector("#label-message-anonsms");
  let countdownTimer = null;

  function setFormError(msg) {
    formErrorEl.textContent = msg || "";
    formErrorEl.style.display = msg ? "block" : "none";
  }

  function setMessageLabelState(canSend) {
    labelMessageEl.classList.remove("label-message--ok", "label-message--blocked");
    labelMessageEl.classList.add(canSend ? "label-message--ok" : "label-message--blocked");
  }

  function stopCountdown() {
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  }

  function updateCountdown(nextSmsAtIso) {
    const target = new Date(nextSmsAtIso);
    function tick() {
      const now = new Date();
      if (now >= target) {
        countdownEl.textContent = "Можно отправить следующее SMS.";
        countdownEl.className = "countdown-box countdown-ready";
        setMessageLabelState(true);
        stopCountdown();
        return;
      }
      const ms = target - now;
      const sec = Math.floor((ms / 1000) % 60);
      const min = Math.floor((ms / 60000) % 60);
      const hr = Math.floor(ms / 3600000);
      countdownEl.textContent = `Следующее SMS через: ${hr} ч ${String(min).padStart(2, "0")} мин ${String(sec).padStart(2, "0")} сек`;
      countdownEl.className = "countdown-box";
    }
    stopCountdown();
    tick();
    countdownTimer = setInterval(tick, 1000);
  }

  function applyStatus(status) {
    if (status.canSend) {
      setMessageLabelState(true);
      countdownEl.textContent = "Можно отправить следующее SMS.";
      countdownEl.className = "countdown-box countdown-ready";
    } else {
      setMessageLabelState(false);
      countdownEl.style.display = "block";
      updateCountdown(status.nextSmsAt);
    }
  }

  fetch("/api/tools/anonsms/status")
    .then((r) => r.json())
    .then(applyStatus)
    .catch(() => {
      setMessageLabelState(true);
      countdownEl.textContent = "Можно отправить следующее SMS.";
      countdownEl.className = "countdown-box countdown-ready";
    });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    setFormError("");
    const fd = new FormData(form);
    const params = {
      country_code: (fd.get("country_code") || "").trim(),
      phone_number: (fd.get("phone_number") || "").trim().replace(/\s|-/g, ""),
      message: (fd.get("message") || "").trim(),
    };

    if (!params.phone_number) {
      setFormError("Укажите номер телефона.");
      return;
    }
    if (!params.message) {
      setFormError("Укажите текст сообщения.");
      return;
    }

    resultEl.textContent = "";
    resultEl.className = "result-box";
    countdownEl.className = "countdown-box";
    stopCountdown();
    form.classList.add("loading");
    const submitBtn = form.querySelector('button[type="submit"]');
    const btnText = submitBtn.textContent;
    submitBtn.textContent = "Отправка…";
    submitBtn.disabled = true;
    submitBtn.classList.add("is-loading");

    try {
      const data = await apiRun(TOOL_ID, params);
      if (data.success) {
        resultEl.className = "result-box success";
        const r = data.response || {};
        resultEl.textContent = formatAnonsmsResult(r);
        if (r.nextSmsAt) {
          setMessageLabelState(false);
          countdownEl.style.display = "block";
          updateCountdown(r.nextSmsAt);
        } else {
          setMessageLabelState(true);
          countdownEl.textContent = "Можно отправить следующее SMS.";
          countdownEl.className = "countdown-box countdown-ready";
        }
      } else {
        resultEl.className = "result-box error";
        resultEl.textContent = data.error || "Ошибка";
      }
    } catch (err) {
      resultEl.className = "result-box error";
      resultEl.textContent = err.message || "Ошибка сети";
    } finally {
      form.classList.remove("loading");
      if (submitBtn) {
        submitBtn.textContent = btnText;
        submitBtn.disabled = false;
        submitBtn.classList.remove("is-loading");
      }
    }
  });
}
