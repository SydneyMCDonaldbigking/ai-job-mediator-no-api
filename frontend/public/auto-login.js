(function () {
  const username = "local-user";
  const password = "job-mediator-123";
  const attemptKey = "ai_job_mediator_auto_login_attempted";
  const panelId = "ai-job-mediator-tool-panel";
  const styleId = "ai-job-mediator-tool-panel-style";
  const managedLabels = [
    "重新上传主简历",
    "A-F 职位评估",
    "下载 ATS PDF",
    "扫描职位",
    "SEEK 搜索岗位",
    "doda 搜索岗位",
    "上传英文简历",
    "上传日文简历",
    "上传中文简历",
    "查看 Portals",
    "更新 Portals",
    "查看自动扫描",
    "更新自动扫描",
    "删除当前对话",
  ];
  const panelSections = [
    {
      title: "简历",
      items: ["重新上传主简历", "上传英文简历", "上传日文简历", "上传中文简历"],
    },
    {
      title: "岗位搜索",
      items: ["扫描职位", "SEEK 搜索岗位", "doda 搜索岗位"],
    },
    {
      title: "求职操作",
      items: ["A-F 职位评估", "下载 ATS PDF"],
    },
    {
      title: "配置",
      items: ["查看 Portals", "更新 Portals", "查看自动扫描", "更新自动扫描"],
    },
    {
      title: "系统",
      items: ["删除当前对话"],
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
    panel.setAttribute("aria-label", "常用功能");
    panel.innerHTML = `
      <h2 class="tool-panel-title">常用功能</h2>
      <p class="tool-panel-subtitle">右侧固定入口。一个功能一个框，减少聊天流里重复按钮卡住的问题。</p>
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
      button.dataset.aiJobToolButton = "true";
      button.style.display = "none";

      const container = button.parentElement;
      if (!container) return;
      const visibleButtons = Array.from(container.querySelectorAll("button")).filter((item) => {
        const itemLabel = normalizeLabel(item.innerText);
        return !managedLabels.includes(itemLabel);
      });
      if (visibleButtons.length === 0) {
        container.classList.add("ai-job-tool-actions-hidden");
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
            : "页面还在加载这个动作，稍等一下就会变为可点。";
          return `
            <button
              type="button"
              class="tool-card"
              data-tool-card-label="${label}"
              ${disabled ? "disabled" : ""}
            >
              <span>
                <span class="tool-card-label">${label}</span>
                <span class="tool-card-meta">${tooltip || "点击后会触发当前页面上最新的对应动作。"}</span>
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

    sectionsHost.innerHTML = fragments.join("");
    panel.dataset.empty = "false";
    panel.dataset.ready = actionableCount > 0 ? "true" : "false";

    sectionsHost.querySelectorAll("[data-tool-card-label]").forEach((button) => {
      button.addEventListener("click", () => {
        const label = button.getAttribute("data-tool-card-label");
        const original = getLatestMatchingButton(label);
        if (!original) return;
        original.click();
      });
    });
  }

  function bootToolPanel() {
    ensurePanel();
    hideInlineToolButtons();
    renderPanel();

    const observer = new MutationObserver(() => {
      hideInlineToolButtons();
      renderPanel();
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["disabled", "aria-disabled", "style", "class"],
    });

    window.addEventListener("load", () => {
      hideInlineToolButtons();
      renderPanel();
    });
    window.addEventListener("resize", renderPanel);
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
