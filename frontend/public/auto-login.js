(function () {
  const username = "local-user";
  const password = "job-mediator-123";
  const attemptKey = "ai_job_mediator_auto_login_attempted";
  const panelId = "ai-job-mediator-tool-panel";
  const styleId = "ai-job-mediator-tool-panel-style";
  const managedLabels = [
    "\u91cd\u65b0\u4e0a\u4f20\u4e3b\u7b80\u5386",
    "A-F \u804c\u4f4d\u8bc4\u4f30",
    "\u4e0b\u8f7d ATS PDF",
    "\u626b\u63cf\u804c\u4f4d",
    "SEEK \u641c\u7d22\u5c97\u4f4d",
    "doda \u641c\u7d22\u5c97\u4f4d",
    "\u4e0a\u4f20\u82f1\u6587\u7b80\u5386",
    "\u4e0a\u4f20\u65e5\u6587\u7b80\u5386",
    "\u4e0a\u4f20\u4e2d\u6587\u7b80\u5386",
    "\u67e5\u770b Portals",
    "\u66f4\u65b0 Portals",
    "\u67e5\u770b\u81ea\u52a8\u626b\u63cf",
    "\u66f4\u65b0\u81ea\u52a8\u626b\u63cf",
    "\u5220\u9664\u5f53\u524d\u5bf9\u8bdd",
  ];
  const panelSections = [
    {
      title: "\u7b80\u5386",
      items: [
        "\u91cd\u65b0\u4e0a\u4f20\u4e3b\u7b80\u5386",
        "\u4e0a\u4f20\u82f1\u6587\u7b80\u5386",
        "\u4e0a\u4f20\u65e5\u6587\u7b80\u5386",
        "\u4e0a\u4f20\u4e2d\u6587\u7b80\u5386",
      ],
    },
    {
      title: "\u5c97\u4f4d\u641c\u7d22",
      items: [
        "\u626b\u63cf\u804c\u4f4d",
        "SEEK \u641c\u7d22\u5c97\u4f4d",
        "doda \u641c\u7d22\u5c97\u4f4d",
      ],
    },
    {
      title: "\u6c42\u804c\u64cd\u4f5c",
      items: ["A-F \u804c\u4f4d\u8bc4\u4f30", "\u4e0b\u8f7d ATS PDF"],
    },
    {
      title: "\u914d\u7f6e",
      items: [
        "\u67e5\u770b Portals",
        "\u66f4\u65b0 Portals",
        "\u67e5\u770b\u81ea\u52a8\u626b\u63cf",
        "\u66f4\u65b0\u81ea\u52a8\u626b\u63cf",
      ],
    },
    {
      title: "\u7cfb\u7edf",
      items: ["\u5220\u9664\u5f53\u524d\u5bf9\u8bdd"],
    },
  ];
  const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const rootPath =
    (document
      .querySelector('meta[property="og:root_path"]')
      ?.getAttribute("content") || "").replace(/\/$/, "");
  const appRootUrl = window.location.origin + rootPath + "/";
  const currentPath = window.location.pathname.replace(/\/$/, "");
  const loginPath = (rootPath || "") + "/login";
  const isLoginPage = currentPath === loginPath;
  let refreshScheduled = false;
  let lastSectionsMarkup = "";

  function normalizeLabel(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  function ensureStyles() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      body[data-ai-job-tool-panel="ready"] {
        --ai-job-tool-panel-width: 312px;
      }
      @media (min-width: 1180px) {
        body[data-ai-job-tool-panel="ready"] #root,
        body[data-ai-job-tool-panel="ready"] main {
          padding-right: calc(var(--ai-job-tool-panel-width) + 28px);
        }
      }
      #${panelId} {
        position: fixed;
        top: 84px;
        right: 18px;
        width: min(312px, calc(100vw - 24px));
        max-height: calc(100vh - 104px);
        overflow: auto;
        z-index: 2147483000;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.09);
        background: rgba(20, 20, 22, 0.94);
        box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
        backdrop-filter: blur(14px);
        color: #f4f2f3;
        padding: 16px;
      }
      #${panelId}[data-empty="true"] {
        display: none;
      }
      #${panelId} .tool-panel-title {
        font-size: 18px;
        font-weight: 700;
        margin: 0 0 6px;
      }
      #${panelId} .tool-panel-subtitle {
        font-size: 12px;
        line-height: 1.45;
        color: rgba(255, 255, 255, 0.68);
        margin: 0 0 14px;
      }
      #${panelId} .tool-panel-section {
        margin-bottom: 14px;
      }
      #${panelId} .tool-panel-section-title {
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(255, 255, 255, 0.56);
        margin: 0 0 8px;
      }
      #${panelId} .tool-panel-grid {
        display: grid;
        gap: 8px;
      }
      #${panelId} .tool-card {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 10px;
        width: 100%;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 12px 12px 10px;
        background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
        color: #f8f7f7;
        text-align: left;
        transition: transform 120ms ease, border-color 120ms ease, background 120ms ease;
      }
      #${panelId} .tool-card:hover:not(:disabled) {
        transform: translateY(-1px);
        border-color: rgba(255, 73, 146, 0.48);
        background: linear-gradient(180deg, rgba(255,73,146,0.18), rgba(255,255,255,0.05));
      }
      #${panelId} .tool-card:disabled {
        cursor: not-allowed;
        opacity: 0.46;
      }
      #${panelId} .tool-card-label {
        font-size: 14px;
        font-weight: 700;
        line-height: 1.25;
      }
      #${panelId} .tool-card-meta {
        display: block;
        font-size: 11px;
        line-height: 1.35;
        color: rgba(255, 255, 255, 0.62);
        margin-top: 4px;
      }
      #${panelId} .tool-card-badge {
        flex: 0 0 auto;
        border-radius: 999px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: 700;
        background: rgba(255, 73, 146, 0.16);
        color: #ff7bb7;
      }
      [data-ai-job-tool-button="true"] {
        display: none !important;
      }
      .ai-job-tool-actions-hidden {
        display: none !important;
      }
      @media (max-width: 1179px) {
        #${panelId} {
          position: static;
          width: auto;
          max-height: none;
          margin: 12px;
        }
      }
    `;
    document.head.appendChild(style);
    document.body.dataset.aiJobToolPanel = "ready";
  }

  function ensurePanel() {
    ensureStyles();
    let panel = document.getElementById(panelId);
    if (panel) return panel;

    panel = document.createElement("aside");
    panel.id = panelId;
    panel.setAttribute("aria-label", "\u5e38\u7528\u529f\u80fd");
    panel.innerHTML = `
      <h2 class="tool-panel-title">\u5e38\u7528\u529f\u80fd</h2>
      <p class="tool-panel-subtitle">\u53f3\u4fa7\u56fa\u5b9a\u5165\u53e3\u3002\u4e00\u4e2a\u529f\u80fd\u4e00\u4e2a\u6846\uff0c\u51cf\u5c11\u804a\u5929\u6d41\u91cc\u91cd\u590d\u6309\u94ae\u5361\u4f4f\u7684\u95ee\u9898\u3002</p>
      <div class="tool-panel-sections"></div>
    `;
    document.body.appendChild(panel);
    return panel;
  }

  function getLatestMatchingButton(label) {
    const normalizedTarget = normalizeLabel(label);
    const buttons = Array.from(document.querySelectorAll("button"));
    const matches = buttons
      .filter((button) => normalizeLabel(button.innerText) === normalizedTarget)
      .filter((button) => button.offsetParent !== null || button.dataset.aiJobToolButton === "true");
    matches.sort((left, right) => {
      const leftRect = left.getBoundingClientRect();
      const rightRect = right.getBoundingClientRect();
      return rightRect.top - leftRect.top;
    });
    return matches[0] || null;
  }

  function hideInlineToolButtons() {
    const buttons = Array.from(document.querySelectorAll("button"));
    buttons.forEach((button) => {
      const label = normalizeLabel(button.innerText);
      if (!managedLabels.includes(label)) return;
      if (button.dataset.aiJobToolButton !== "true") {
        button.dataset.aiJobToolButton = "true";
      }
      if (button.style.display !== "none") {
        button.style.display = "none";
      }

      const container = button.parentElement;
      if (!container) return;
      const visibleButtons = Array.from(container.querySelectorAll("button")).filter((item) => {
        const itemLabel = normalizeLabel(item.innerText);
        return !managedLabels.includes(itemLabel);
      });
      if (visibleButtons.length === 0) {
        if (!container.classList.contains("ai-job-tool-actions-hidden")) {
          container.classList.add("ai-job-tool-actions-hidden");
        }
      } else if (container.classList.contains("ai-job-tool-actions-hidden")) {
        container.classList.remove("ai-job-tool-actions-hidden");
      }
    });
  }

  function renderPanel() {
    const panel = ensurePanel();
    const sectionsHost = panel.querySelector(".tool-panel-sections");
    if (!sectionsHost) return;

    let actionableCount = 0;
    const fragments = panelSections.map((section) => {
      const cards = section.items
        .map((label) => {
          const original = getLatestMatchingButton(label);
          const disabled =
            !original ||
            original.disabled ||
            original.getAttribute("aria-disabled") === "true" ||
            original.hasAttribute("disabled");
          if (!disabled) {
            actionableCount += 1;
          }
          const tooltip = original
            ? original.getAttribute("title") || original.getAttribute("aria-label") || ""
            : "\u9875\u9762\u8fd8\u5728\u52a0\u8f7d\u8fd9\u4e2a\u52a8\u4f5c\uff0c\u7a0d\u7b49\u4e00\u4e0b\u5c31\u4f1a\u53d8\u4e3a\u53ef\u70b9\u3002";
          return `
            <button
              type="button"
              class="tool-card"
              data-tool-card-label="${label}"
              ${disabled ? "disabled" : ""}
            >
              <span>
                <span class="tool-card-label">${label}</span>
                <span class="tool-card-meta">${tooltip || "\u70b9\u51fb\u540e\u4f1a\u89e6\u53d1\u5f53\u524d\u9875\u9762\u4e0a\u6700\u65b0\u7684\u5bf9\u5e94\u52a8\u4f5c\u3002"}</span>
              </span>
              <span class="tool-card-badge">${section.title}</span>
            </button>
          `;
        })
        .join("");

      return `
        <section class="tool-panel-section">
          <div class="tool-panel-section-title">${section.title}</div>
          <div class="tool-panel-grid">${cards}</div>
        </section>
      `;
    });

    const sectionsMarkup = fragments.join("");
    if (sectionsMarkup !== lastSectionsMarkup) {
      sectionsHost.innerHTML = sectionsMarkup;
      lastSectionsMarkup = sectionsMarkup;
    }
    panel.dataset.empty = actionableCount > 0 ? "false" : "true";
    panel.dataset.ready = actionableCount > 0 ? "true" : "false";

    sectionsHost.querySelectorAll("[data-tool-card-label]").forEach((button) => {
      if (button.dataset.aiJobToolBound === "true") return;
      button.dataset.aiJobToolBound = "true";
      button.addEventListener("click", () => {
        const label = button.getAttribute("data-tool-card-label");
        const original = getLatestMatchingButton(label);
        if (!original) return;
        original.click();
      });
    });
  }

  function schedulePanelRefresh() {
    if (refreshScheduled) return;
    refreshScheduled = true;
    window.requestAnimationFrame(() => {
      refreshScheduled = false;
      hideInlineToolButtons();
      renderPanel();
    });
  }

  function mutationNeedsRefresh(mutation) {
    const panel = document.getElementById(panelId);
    if (!panel) return true;

    const isPanelNode = (node) => node instanceof Node && panel.contains(node);
    const targetInsidePanel = mutation.target instanceof Node && panel.contains(mutation.target);
    const addedOutsidePanel = Array.from(mutation.addedNodes || []).some((node) => !isPanelNode(node));
    const removedOutsidePanel = Array.from(mutation.removedNodes || []).some((node) => !isPanelNode(node));

    if (addedOutsidePanel || removedOutsidePanel) return true;
    return !targetInsidePanel;
  }

  function bootToolPanel() {
    ensurePanel();
    schedulePanelRefresh();

    const observer = new MutationObserver((mutations) => {
      if (!mutations.some(mutationNeedsRefresh)) {
        return;
      }
      schedulePanelRefresh();
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["disabled", "aria-disabled", "style", "class"],
    });

    window.addEventListener("load", () => {
      schedulePanelRefresh();
    });
    window.addEventListener("resize", schedulePanelRefresh);
  }

  async function autoLogin() {
    if (!isLocalHost) return;
    try {
      const authConfigResponse = await fetch("/auth/config", { credentials: "include" });
      if (!authConfigResponse.ok) return;
      const authConfig = await authConfigResponse.json();
      if (!authConfig?.requireLogin || !authConfig?.passwordAuth) return;
      const currentUserResponse = await fetch("/user", { credentials: "include" });
      if (currentUserResponse.ok) {
        sessionStorage.removeItem(attemptKey);
        if (isLoginPage) {
          window.location.replace(appRootUrl);
        }
        return;
      }
      if (!isLoginPage) {
        sessionStorage.removeItem(attemptKey);
        window.location.replace(loginPath);
        return;
      }
      if (sessionStorage.getItem(attemptKey) === "1") return;
      sessionStorage.setItem(attemptKey, "1");
      await fetch("/logout", {
        method: "POST",
        credentials: "include",
      }).catch(() => null);
      const form = new URLSearchParams();
      form.set("username", username);
      form.set("password", password);
      const loginResponse = await fetch("/login", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: form.toString(),
      });
      if (!loginResponse.ok) {
        sessionStorage.removeItem(attemptKey);
        return;
      }
      sessionStorage.removeItem(attemptKey);
      window.location.replace(appRootUrl);
    } catch (error) {
      sessionStorage.removeItem(attemptKey);
      console.warn("Local auto-login failed.", error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootToolPanel, { once: true });
  } else {
    bootToolPanel();
  }

  autoLogin();
})();
