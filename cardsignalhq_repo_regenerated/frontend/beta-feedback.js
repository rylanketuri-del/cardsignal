/**
 * Beta Feedback modal — unobtrusive collector feedback for closed beta.
 */
(function initBetaFeedback(global) {
  const VERSION = global.CARDSIGNAL_VERSION || {};
  const FEEDBACK_TYPES = [
    { value: "CONFUSING", label: "Confusing" },
    { value: "BUG", label: "Bug" },
    { value: "IDEA", label: "Idea" },
    { value: "LOVE", label: "Love it" },
    { value: "OTHER", label: "Other" },
  ];

  let launcher = null;
  let modal = null;
  let form = null;
  let messageInput = null;
  let statusEl = null;
  let submitBtn = null;
  let closeBtn = null;
  let isSubmitting = false;
  let lastFocusTarget = null;
  let focusTrapHandler = null;

  function getApiBase() {
    return (global.APP_CONFIG && global.APP_CONFIG.API_BASE_URL) || "https://cardsignal-api.onrender.com";
  }

  function getContext() {
    const route = global.CardSignalRouting ? global.CardSignalRouting.getCurrentRoute() : { type: "home" };
    const ctx = global.CardSignalAppContext || {};
    return {
      page_url: global.location.href.split("#")[0] + (global.location.hash || ""),
      current_route: global.location.hash || "#/",
      entity_type: ctx.entity_type || null,
      entity_id: ctx.entity_id || null,
      sport: ctx.sport || null,
      app_version: VERSION.appVersion || "0.14.1",
      build_id: VERSION.buildId || "unknown",
      browser_summary: summarizeBrowser(),
      viewport_width: global.innerWidth || null,
      viewport_height: global.innerHeight || null,
      route_type: route.type,
    };
  }

  function summarizeBrowser() {
    const ua = global.navigator.userAgent || "";
    const platform = global.navigator.platform || "";
    const summary = `${platform} · ${ua}`.slice(0, 240);
    return summary;
  }

  function setStatus(message, kind) {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.dataset.kind = kind || "";
    statusEl.hidden = !message;
  }

  function trapFocus(event) {
    if (!modal || modal.hidden) return;
    const focusable = modal.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    const items = [...focusable].filter((el) => el.offsetParent !== null);
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.key === "Tab") {
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    if (event.key === "Escape") {
      event.preventDefault();
      closeModal();
    }
  }

  function openModal() {
    if (!modal) return;
    lastFocusTarget = document.activeElement;
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("beta-feedback-open");
    setStatus("", "");
    if (!messageInput.value) messageInput.value = "";
    submitBtn.disabled = false;
    isSubmitting = false;
    if (!focusTrapHandler) {
      focusTrapHandler = trapFocus;
      document.addEventListener("keydown", focusTrapHandler);
    }
    closeBtn.focus();
  }

  function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("beta-feedback-open");
    setStatus("", "");
    if (focusTrapHandler) {
      document.removeEventListener("keydown", focusTrapHandler);
      focusTrapHandler = null;
    }
    if (lastFocusTarget && typeof lastFocusTarget.focus === "function") {
      lastFocusTarget.focus();
    } else if (launcher) {
      launcher.focus();
    }
  }

  async function submitFeedback(event) {
    event.preventDefault();
    if (isSubmitting) return;

    const type = form.querySelector('input[name="feedback_type"]:checked');
    const message = (messageInput.value || "").trim();
    if (!type) {
      setStatus("Please choose a feedback type.", "error");
      return;
    }
    if (message.length < 3) {
      setStatus("Please enter a message.", "error");
      return;
    }

    isSubmitting = true;
    submitBtn.disabled = true;
    setStatus("Sending feedback…", "loading");

    const context = getContext();
    const payload = {
      feedback_type: type.value,
      message,
      page_url: context.page_url,
      current_route: context.current_route,
      entity_type: context.entity_type,
      entity_id: context.entity_id,
      sport: context.sport,
      app_version: context.app_version,
      build_id: context.build_id,
      browser_summary: context.browser_summary,
      viewport_width: context.viewport_width,
      viewport_height: context.viewport_height,
    };

    try {
      const headers = { "Content-Type": "application/json" };
      if (global.CardSignalAuthToken) {
        headers.Authorization = `Bearer ${global.CardSignalAuthToken}`;
      }
      const response = await fetch(`${getApiBase()}/api/beta-feedback`, {
        method: "POST",
        headers,
        body: JSON.stringify(payload),
      });
      if (response.status === 503) {
        setStatus("Feedback is temporarily unavailable. Please try again later.", "error");
        isSubmitting = false;
        submitBtn.disabled = false;
        return;
      }
      if (!response.ok) {
        setStatus("We couldn't send your feedback. Please try again.", "error");
        isSubmitting = false;
        submitBtn.disabled = false;
        return;
      }
      setStatus("Thanks — your feedback was sent.", "success");
      messageInput.value = "";
      setTimeout(() => closeModal(), 1400);
    } catch (_) {
      setStatus("We couldn't send your feedback. Please try again.", "error");
      isSubmitting = false;
      submitBtn.disabled = false;
    }
  }

  function buildModal() {
    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
      <button type="button" class="beta-feedback-launcher" id="beta-feedback-launcher" aria-haspopup="dialog" aria-controls="beta-feedback-modal">
        Beta Feedback
      </button>
      <div class="beta-feedback-modal" id="beta-feedback-modal" role="dialog" aria-modal="true" aria-labelledby="beta-feedback-title" aria-hidden="true" hidden>
        <div class="beta-feedback-backdrop" data-beta-feedback-close tabindex="-1"></div>
        <div class="beta-feedback-panel" role="document">
          <header class="beta-feedback-header">
            <h2 id="beta-feedback-title">Beta Feedback</h2>
            <button type="button" class="beta-feedback-close" id="beta-feedback-close" aria-label="Close feedback form">×</button>
          </header>
          <form id="beta-feedback-form" class="beta-feedback-form" novalidate>
            <p class="beta-feedback-prompt">What confused you, what did you love, or what should CardSignal improve?</p>
            <fieldset class="beta-feedback-types">
              <legend class="sr-only">Feedback type</legend>
              ${FEEDBACK_TYPES.map(
                (item, index) => `
                  <label class="beta-feedback-type">
                    <input type="radio" name="feedback_type" value="${item.value}" ${index === 0 ? "checked" : ""} required />
                    <span>${item.label}</span>
                  </label>`
              ).join("")}
            </fieldset>
            <label class="beta-feedback-message-label" for="beta-feedback-message">Message <span aria-hidden="true">*</span></label>
            <textarea id="beta-feedback-message" name="message" rows="4" maxlength="2000" required placeholder="Tell us what happened…"></textarea>
            <p class="beta-feedback-hint">No passwords or personal information required.</p>
            <!-- Future hook: optional screenshot upload when private storage is available -->
            <p id="beta-feedback-status" class="beta-feedback-status" hidden></p>
            <div class="beta-feedback-actions">
              <button type="submit" class="primary" id="beta-feedback-submit">Send feedback</button>
            </div>
          </form>
        </div>
      </div>
    `;
    document.body.appendChild(wrapper);
    launcher = document.getElementById("beta-feedback-launcher");
    modal = document.getElementById("beta-feedback-modal");
    form = document.getElementById("beta-feedback-form");
    messageInput = document.getElementById("beta-feedback-message");
    statusEl = document.getElementById("beta-feedback-status");
    submitBtn = document.getElementById("beta-feedback-submit");
    closeBtn = document.getElementById("beta-feedback-close");

    launcher.addEventListener("click", openModal);
    closeBtn.addEventListener("click", closeModal);
    form.addEventListener("submit", submitFeedback);
    modal.addEventListener("click", (event) => {
      if (event.target.closest("[data-beta-feedback-close]")) closeModal();
    });
  }

  function mount() {
    if (document.getElementById("beta-feedback-launcher")) return;
    buildModal();
  }

  global.CardSignalBetaFeedback = {
    mount,
    openModal,
    closeModal,
    getContext,
    summarizeBrowser,
    FEEDBACK_TYPES,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})(window);
