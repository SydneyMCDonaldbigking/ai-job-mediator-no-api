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
      description: "\u5148\u4e0a\u4f20\u6216\u66f4\u65b0\u5404\u8bed\u8a00\u7b80\u5386\u3002",
      items: [
        "\u91cd\u65b0\u4e0a\u4f20\u4e3b\u7b80\u5386",
        "\u4e0a\u4f20\u82f1\u6587\u7b80\u5386",
        "\u4e0a\u4f20\u65e5\u6587\u7b80\u5386",
        "\u4e0a\u4f20\u4e2d\u6587\u7b80\u5386",
      ],
    },
    {
      title: "\u5c97\u4f4d\u641c\u7d22",
      description: "\u5148\u641c\u7d22\u5355\u4e2a\u7ad9\u70b9\uff0c\u518d\u7528\u626b\u63cf\u505a\u6279\u91cf\u68c0\u67e5\u3002",
      items: [
        "\u626b\u63cf\u804c\u4f4d",
        "SEEK \u641c\u7d22\u5c97\u4f4d",
        "doda \u641c\u7d22\u5c97\u4f4d",
      ],
    },
    {
      title: "\u6c42\u804c\u64cd\u4f5c",
      description: "\u56f4\u7ed5\u5f53\u524d\u4e3b\u7b80\u5386\u751f\u6210\u8bc4\u4f30\u4e0e ATS \u6750\u6599\u3002",
      items: ["A-F \u804c\u4f4d\u8bc4\u4f30", "\u4e0b\u8f7d ATS PDF"],
    },
    {
      title: "\u914d\u7f6e",
      description: "\u7ba1\u7406\u7ad9\u70b9\u89c4\u5219\u548c\u81ea\u52a8\u626b\u63cf\u8bbe\u7f6e\u3002",
      items: [
        "\u67e5\u770b Portals",
        "\u66f4\u65b0 Portals",
        "\u67e5\u770b\u81ea\u52a8\u626b\u63cf",
        "\u66f4\u65b0\u81ea\u52a8\u626b\u63cf",
      ],
    },
    {
      title: "\u7cfb\u7edf",
      description: "\u6e05\u7406\u5f53\u524d\u4f1a\u8bdd\uff0c\u4fdd\u6301\u804a\u5929\u7ebf\u7d22\u5e72\u51c0\u3002",
      items: ["\u5220\u9664\u5f53\u524d\u5bf9\u8bdd"],
    },
  ];
  const cardContent = {
    "\u91cd\u65b0\u4e0a\u4f20\u4e3b\u7b80\u5386": {
      badge: "\u4e0a\u4f20",
      ready: "\u6253\u5f00\u4e0a\u4f20\u6846\uff0c\u8986\u76d6\u5f53\u524d\u4e3b\u7b80\u5386\u3002",
      waiting: "\u7b49\u5f85\u4e3b\u7b80\u5386\u4e0a\u4f20\u5165\u53e3\u51fa\u73b0\u3002",
    },
    "\u4e0a\u4f20\u82f1\u6587\u7b80\u5386": {
      badge: "\u4e0a\u4f20",
      ready: "\u6253\u5f00\u4e0a\u4f20\u6846\uff0c\u8865\u5145\u82f1\u6587\u7b80\u5386\u4f9b SEEK \u4f7f\u7528\u3002",
      waiting: "\u7b49\u5f85\u82f1\u6587\u7b80\u5386\u4e0a\u4f20\u5165\u53e3\u51fa\u73b0\u3002",
    },
    "\u4e0a\u4f20\u65e5\u6587\u7b80\u5386": {
      badge: "\u4e0a\u4f20",
      ready: "\u6253\u5f00\u4e0a\u4f20\u6846\uff0c\u8865\u5145\u65e5\u6587\u7b80\u5386\u4f9b doda \u4f7f\u7528\u3002",
      waiting: "\u7b49\u5f85\u65e5\u6587\u7b80\u5386\u4e0a\u4f20\u5165\u53e3\u51fa\u73b0\u3002",
    },
    "\u4e0a\u4f20\u4e2d\u6587\u7b80\u5386": {
      badge: "\u4e0a\u4f20",
      ready: "\u6253\u5f00\u4e0a\u4f20\u6846\uff0c\u8865\u5145\u4e2d\u6587\u7b80\u5386\u4f9b\u540e\u7eed\u4e2d\u6587\u7ad9\u70b9\u4f7f\u7528\u3002",
      waiting: "\u7b49\u5f85\u4e2d\u6587\u7b80\u5386\u4e0a\u4f20\u5165\u53e3\u51fa\u73b0\u3002",
    },
    "\u626b\u63cf\u804c\u4f4d": {
      badge: "\u626b\u63cf",
      tags: ["\u6279\u91cf", "\u5df2\u914d\u7f6e", "\u9ad8\u5206"],
      ready: "\u6309\u5df2\u914d\u7f6e\u7ad9\u70b9\u6279\u91cf\u626b\u63cf\uff0c\u6c47\u603b\u65b0\u589e\u5c97\u4f4d\u548c\u9ad8\u5206\u672a\u6295\u9012\u5c97\u4f4d\u3002",
      waiting: "\u7b49\u5f85\u6279\u91cf\u626b\u63cf\u52a8\u4f5c\u5c31\u7eea\u3002",
    },
    "SEEK \u641c\u7d22\u5c97\u4f4d": {
      badge: "\u641c\u7d22",
      tags: ["\u82f1\u6587", "\u5355\u7ad9"],
      ready: "\u57fa\u4e8e\u82f1\u6587\u7b80\u5386\u641c\u7d22 SEEK \u5c97\u4f4d\u3002",
      waiting: "\u7b49\u5f85\u82f1\u6587\u7b80\u5386\u548c SEEK \u641c\u7d22\u5165\u53e3\u5c31\u7eea\u3002",
    },
    "doda \u641c\u7d22\u5c97\u4f4d": {
      badge: "\u641c\u7d22",
      tags: ["\u65e5\u6587", "\u5355\u7ad9"],
      ready: "\u57fa\u4e8e\u65e5\u6587\u7b80\u5386\u641c\u7d22 doda \u5c97\u4f4d\u3002",
      waiting: "\u7b49\u5f85\u65e5\u6587\u7b80\u5386\u548c doda \u641c\u7d22\u5165\u53e3\u5c31\u7eea\u3002",
    },
    "A-F \u804c\u4f4d\u8bc4\u4f30": {
      badge: "\u8bc4\u4f30",
      ready: "\u56f4\u7ed5\u5f53\u524d\u4e3b\u7b80\u5386\u751f\u6210 A-F \u5c97\u4f4d\u8bc4\u4f30\u3002",
      waiting: "\u7b49\u5f85\u804c\u4f4d\u8bc4\u4f30\u5165\u53e3\u5c31\u7eea\u3002",
    },
    "\u4e0b\u8f7d ATS PDF": {
      badge: "\u5bfc\u51fa",
      ready: "\u4e3a\u5f53\u524d JD \u4e0b\u8f7d ATS \u4f18\u5316 PDF\u3002",
      waiting: "\u7b49\u5f85 ATS PDF \u751f\u6210\u5165\u53e3\u5c31\u7eea\u3002",
    },
    "\u67e5\u770b Portals": {
      badge: "\u914d\u7f6e",
      ready: "\u67e5\u770b\u5f53\u524d\u6293\u53d6\u7ad9\u70b9\u548c\u641c\u7d22\u914d\u7f6e\u3002",
      waiting: "\u7b49\u5f85 Portals \u914d\u7f6e\u5165\u53e3\u5c31\u7eea\u3002",
    },
    "\u66f4\u65b0 Portals": {
      badge: "\u914d\u7f6e",
      ready: "\u66f4\u65b0\u7ad9\u70b9\u3001\u516c\u53f8\u548c\u641c\u7d22\u5173\u952e\u8bcd\u914d\u7f6e\u3002",
      waiting: "\u7b49\u5f85 Portals \u66f4\u65b0\u5165\u53e3\u5c31\u7eea\u3002",
    },
    "\u67e5\u770b\u81ea\u52a8\u626b\u63cf": {
      badge: "\u914d\u7f6e",
      ready: "\u67e5\u770b\u81ea\u52a8\u626b\u63cf\u65f6\u95f4\u3001\u7ad9\u70b9\u548c\u901a\u77e5\u8bbe\u7f6e\u3002",
      waiting: "\u7b49\u5f85\u81ea\u52a8\u626b\u63cf\u8bbe\u7f6e\u5165\u53e3\u5c31\u7eea\u3002",
    },
    "\u66f4\u65b0\u81ea\u52a8\u626b\u63cf": {
      badge: "\u914d\u7f6e",
      ready: "\u66f4\u65b0\u626b\u63cf\u65f6\u95f4\uff0c\u9608\u503c\u548c\u901a\u77e5\u8bbe\u7f6e\u3002",
      waiting: "\u7b49\u5f85\u81ea\u52a8\u626b\u63cf\u66f4\u65b0\u5165\u53e3\u5c31\u7eea\u3002",
    },
    "\u5220\u9664\u5f53\u524d\u5bf9\u8bdd": {
      badge: "\u7cfb\u7edf",
      ready: "\u6e05\u7406\u5f53\u524d\u5bf9\u8bdd\uff0c\u91cd\u65b0\u5f00\u59cb\u4e00\u6761\u5e72\u51c0\u7684\u6c42\u804c\u7ebf\u7d22\u3002",
      waiting: "\u7b49\u5f85\u5220\u9664\u5f53\u524d\u5bf9\u8bdd\u7684\u52a8\u4f5c\u51fa\u73b0\u3002",
    },
  };
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
      #${panelId} .tool-panel-results {
        margin-top: 14px;
        padding-top: 14px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
      }
      #${panelId} .tool-panel-results[hidden] {
        display: none !important;
      }
      #${panelId} .tool-panel-results-title {
        font-size: 13px;
        font-weight: 700;
        margin: 0 0 6px;
      }
      #${panelId} .tool-panel-results-subtitle {
        font-size: 11px;
        line-height: 1.4;
        color: rgba(255, 255, 255, 0.62);
        margin: 0 0 10px;
      }
      #${panelId} .tool-panel-results-group {
        margin-top: 12px;
      }
      #${panelId} .tool-panel-results-group-title {
        font-size: 12px;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.78);
        margin: 0 0 8px;
      }
      #${panelId} .tool-panel-results-list {
        display: grid;
        gap: 8px;
      }
      #${panelId} .tool-result-card {
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 10px;
        background: rgba(255, 255, 255, 0.04);
      }
      #${panelId} .tool-result-title {
        font-size: 12px;
        font-weight: 700;
        line-height: 1.35;
        margin: 0 0 4px;
      }
      #${panelId} .tool-result-meta,
      #${panelId} .tool-result-secondary {
        font-size: 11px;
        line-height: 1.45;
        color: rgba(255, 255, 255, 0.68);
      }
      #${panelId} .tool-result-link {
        display: inline-flex;
        margin-top: 6px;
        font-size: 11px;
        font-weight: 700;
        color: #ff7bb7;
        text-decoration: none;
      }
      #${panelId} .tool-result-actions {
        display: flex;
        gap: 8px;
        margin-top: 8px;
        flex-wrap: wrap;
      }
      #${panelId} .tool-result-action {
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 999px;
        padding: 4px 10px;
        background: rgba(255, 255, 255, 0.04);
        color: #f6f3f4;
        font-size: 11px;
        font-weight: 700;
      }
      #${panelId} .tool-result-action:hover {
        border-color: rgba(255, 123, 183, 0.42);
        color: #fff4f8;
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
      #${panelId} .tool-panel-section-description {
        font-size: 12px;
        line-height: 1.45;
        color: rgba(255, 255, 255, 0.62);
        margin: 0 0 10px;
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
      #${panelId} .tool-card[data-tool-card-priority="primary"] {
        border-color: rgba(255, 73, 146, 0.34);
        background: linear-gradient(180deg, rgba(255, 73, 146, 0.2), rgba(255, 255, 255, 0.06));
        box-shadow: inset 0 0 0 1px rgba(255, 123, 183, 0.14);
      }
      #${panelId} .tool-card[data-tool-card-priority="primary"] .tool-card-label {
        color: #fff4f8;
      }
      #${panelId} .tool-card[data-tool-card-priority="primary"] .tool-card-meta {
        color: rgba(255, 232, 240, 0.84);
      }
      #${panelId} .tool-card[data-tool-card-priority="workspace"] {
        border-color: rgba(126, 231, 135, 0.28);
        background: linear-gradient(180deg, rgba(126, 231, 135, 0.16), rgba(255, 255, 255, 0.04));
        box-shadow: inset 0 0 0 1px rgba(126, 231, 135, 0.12);
      }
      #${panelId} .tool-card[data-tool-card-priority="workspace"] .tool-card-label {
        color: #eefef0;
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
      #${panelId} .tool-card-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 8px;
      }
      #${panelId} .tool-card-tag {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 2px 8px;
        font-size: 10px;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.76);
        background: rgba(255, 255, 255, 0.08);
      }
      #${panelId} .tool-card-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-top: 8px;
        font-size: 11px;
        font-weight: 700;
        line-height: 1;
      }
      #${panelId} .tool-card-status::before {
        content: "";
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: currentColor;
        opacity: 0.95;
      }
      #${panelId} .tool-card-status[data-status="ready"] {
        color: #7ee787;
      }
      #${panelId} .tool-card-status[data-status="waiting"] {
        color: #ffb86b;
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
      <div class="tool-panel-results" data-ai-job-scan-results="true" hidden></div>
    `;
    document.body.appendChild(panel);
    return panel;
  }

  function getLatestMatchingButton(label) {
    const normalizedTarget = normalizeLabel(label);
    const currentMatch = Array.from(document.querySelectorAll("button")).find(
      (button) =>
        button.dataset.aiJobToolCurrent === "true" &&
        button.dataset.aiJobToolLabel === normalizedTarget
    );
    if (currentMatch) {
      return currentMatch;
    }
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

  function getLatestActionButtonByExactLabel(label) {
    const normalizedTarget = normalizeLabel(label);
    const buttons = Array.from(document.querySelectorAll("button"));
    const matches = buttons
      .filter((button) => normalizeLabel(button.innerText) === normalizedTarget)
      .filter((button) => button.offsetParent !== null || button.dataset.aiJobToolButton === "true");
    matches.sort((left, right) => {
      const leftRect = left.getBoundingClientRect();
      const rightRect = right.getBoundingClientRect();
      if (rightRect.top !== leftRect.top) return rightRect.top - leftRect.top;
      return 0;
    });
    return matches[0] || null;
  }

  function hideInlineToolButtons() {
    const buttons = Array.from(document.querySelectorAll("button"));
    const managedByLabel = new Map();

    buttons.forEach((button, index) => {
      const label = normalizeLabel(button.innerText);
      if (!managedLabels.includes(label)) return;
      const bucket = managedByLabel.get(label) || [];
      bucket.push({ button, index });
      managedByLabel.set(label, bucket);
    });

    managedByLabel.forEach((entries, label) => {
      const visibleEntries = entries.filter(({ button }) => button.offsetParent !== null);
      const rankedEntries = (visibleEntries.length ? visibleEntries : entries).sort((left, right) => {
        const leftRect = left.button.getBoundingClientRect();
        const rightRect = right.button.getBoundingClientRect();
        if (rightRect.top !== leftRect.top) return rightRect.top - leftRect.top;
        return right.index - left.index;
      });
      const currentEntry = rankedEntries[0] || null;

      entries.forEach(({ button }) => {
        button.dataset.aiJobToolLabel = label;
        button.dataset.aiJobToolCurrent = button === currentEntry?.button ? "true" : "false";
        button.dataset.aiJobToolButton = "true";
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
    });
  }

  function escapeHtml(text) {
    return String(text || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function decodeScanPayload(encoded) {
    if (!encoded) return null;
    try {
      const binary = window.atob(encoded);
      const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
      const jsonText = new TextDecoder().decode(bytes);
      return JSON.parse(jsonText);
    } catch (error) {
      return null;
    }
  }

  function getLatestScanPayload() {
    const text = document.body ? document.body.textContent || "" : "";
    const matches = Array.from(text.matchAll(/SCAN_RESULTS_PAYLOAD::([A-Za-z0-9+/=]+)/g));
    const latest = matches[matches.length - 1];
    if (!latest) return null;
    return decodeScanPayload(latest[1]);
  }
  function getLatestResumeAssetsPayload() {
    const text = document.body ? document.body.textContent || "" : "";
    const matches = Array.from(text.matchAll(/RESUME_ASSETS_PAYLOAD::([A-Za-z0-9+/=]+)/g));
    const latest = matches[matches.length - 1];
    if (!latest) return null;
    return decodeScanPayload(latest[1]);
  }

  function hideScanPayloadMarkers() {
    const panel = document.getElementById(panelId);
    Array.from(document.querySelectorAll("p, div, span, code")).forEach((node) => {
      if (panel && panel.contains(node)) return;
      const text = (node.textContent || "").trim();
      if (text.startsWith("SCAN_RESULTS_PAYLOAD::") || text.startsWith("RESUME_ASSETS_PAYLOAD::")) {
        node.style.display = "none";
      }
    });
  }

  function renderScanResults(panel) {
    const host = panel.querySelector(".tool-panel-results");
    if (!host) return;
    const payload = getLatestScanPayload();
    const recentJobs = payload?.recent_new_jobs || [];
    const highScoreJobs = payload?.high_score_unapplied_jobs || [];

    if (!recentJobs.length && !highScoreJobs.length) {
      host.hidden = true;
      host.innerHTML = "";
      return;
    }

    const renderJobs = (jobs) =>
      jobs
        .map((job) => {
          const companyBits = [job.company, job.location].filter(Boolean).join(" | ");
          const secondaryBits = [job.source, `score ${job.score?.toFixed ? job.score.toFixed(2) : job.score}`, job.status]
            .filter(Boolean)
            .join(" | ");
          const linkMarkup = job.job_url
            ? `<a class="tool-result-link" href="${escapeHtml(job.job_url)}" target="_blank" rel="noreferrer">\u6253\u5f00\u5c97\u4f4d</a>`
            : "";
          const applyMarkup = job.can_mark_applied && job.apply_action_label
            ? `<button type="button" class="tool-result-action" data-job-apply-label="${escapeHtml(job.apply_action_label)}">\u6807\u8bb0\u5df2\u6295\u9012</button>`
            : "";
          const actionsMarkup = linkMarkup || applyMarkup
            ? `<div class="tool-result-actions">${linkMarkup}${applyMarkup}</div>`
            : "";
          return `
            <article class="tool-result-card">
              <div class="tool-result-title">${escapeHtml(job.title)}</div>
              <div class="tool-result-meta">${escapeHtml(companyBits)}</div>
              <div class="tool-result-secondary">${escapeHtml(secondaryBits)}</div>
              ${actionsMarkup}
            </article>
          `;
        })
        .join("");

    const groups = [];
    if (recentJobs.length) {
      groups.push(`
        <section class="tool-panel-results-group">
          <div class="tool-panel-results-group-title">\u6700\u8fd1\u65b0\u589e\u5c97\u4f4d</div>
          <div class="tool-panel-results-list">${renderJobs(recentJobs)}</div>
        </section>
      `);
    }
    if (highScoreJobs.length) {
      groups.push(`
        <section class="tool-panel-results-group">
          <div class="tool-panel-results-group-title">\u9ad8\u5206\u672a\u6295\u9012\u5c97\u4f4d</div>
          <div class="tool-panel-results-list">${renderJobs(highScoreJobs)}</div>
        </section>
      `);
    }

    host.hidden = false;
    host.innerHTML = `
      <div class="tool-panel-results-title">\u5c97\u4f4d\u7ed3\u679c</div>
      <div class="tool-panel-results-subtitle">\u76f4\u63a5\u67e5\u770b\u6700\u8fd1\u65b0\u589e\u5c97\u4f4d\u548c\u9ad8\u5206\u672a\u6295\u9012\u5c97\u4f4d\u3002</div>
      ${groups.join("")}
    `;
    host.querySelectorAll("[data-job-apply-label]").forEach((button) => {
      if (button.dataset.aiJobApplyBound === "true") return;
      button.dataset.aiJobApplyBound = "true";
      button.addEventListener("click", () => {
        const label = button.getAttribute("data-job-apply-label");
        const actionButton = getLatestActionButtonByExactLabel(label);
        if (!actionButton) return;
        actionButton.click();
      });
    });
  }
  function resumeStatusText(payload, language) {
    const resume = payload?.resumes?.[language];
    if (!resume?.exists) {
      const names = { en: "英文", ja: "日文", zh: "中文" };
      return `当前没有${names[language] || ""}简历，需要上传。`;
    }
    const time = resume.updated_at || "未知时间";
    const filename = resume.filename ? `：${resume.filename}` : "";
    const names = { en: "英文", ja: "日文", zh: "中文" };
    return `${names[language] || ""}简历已存在${filename}（上次上传时间 ${time}）。再次点击可重新上传。`;
  }
  function cardOverrideForLabel(label, payload) {
    if (!payload) return null;
    if (label === "上传英文简历" || label === "重新上传主简历") {
      return {
        meta: resumeStatusText(payload, "en"),
        statusLabel: payload.resumes?.en?.exists ? "已存在" : "需上传",
        statusKey: payload.resumes?.en?.exists ? "ready" : "waiting",
      };
    }
    if (label === "上传日文简历") {
      return {
        meta: resumeStatusText(payload, "ja"),
        statusLabel: payload.resumes?.ja?.exists ? "已存在" : "需上传",
        statusKey: payload.resumes?.ja?.exists ? "ready" : "waiting",
      };
    }
    if (label === "上传中文简历") {
      return {
        meta: resumeStatusText(payload, "zh"),
        statusLabel: payload.resumes?.zh?.exists ? "已存在" : "需上传",
        statusKey: payload.resumes?.zh?.exists ? "ready" : "waiting",
      };
    }
    if (label === "SEEK 搜索岗位" && payload.search?.seek?.missing) {
      return {
        disabled: true,
        meta: "当前没有英文简历，需要先上传英文简历后才能搜索 SEEK。",
        statusLabel: "缺英文简历",
        statusKey: "waiting",
      };
    }
    if (label === "doda 搜索岗位" && payload.search?.doda?.missing) {
      return {
        disabled: true,
        meta: "当前没有日文简历，需要先上传日文简历后才能搜索 doda。",
        statusLabel: "缺日文简历",
        statusKey: "waiting",
      };
    }
    return null;
  }

  function renderPanel() {
    const panel = ensurePanel();
    const sectionsHost = panel.querySelector(".tool-panel-sections");
    if (!sectionsHost) return;

    const resumeAssetsPayload = getLatestResumeAssetsPayload();
    let actionableCount = 0;
    const fragments = panelSections.map((section) => {
      const cards = section.items
        .map((label) => {
          const original = getLatestMatchingButton(label);
          const override = cardOverrideForLabel(label, resumeAssetsPayload);
          const disabled =
            !original ||
            original.disabled ||
            original.getAttribute("aria-disabled") === "true" ||
            original.hasAttribute("disabled") ||
            override?.disabled === true;
          if (!disabled) {
            actionableCount += 1;
          }
          const content = cardContent[label] || {
            badge: section.title,
            tags: [],
            ready:
              "\u70b9\u51fb\u540e\u4f1a\u89e6\u53d1\u5f53\u524d\u9875\u9762\u4e0a\u6700\u65b0\u7684\u5bf9\u5e94\u52a8\u4f5c\u3002",
            waiting:
              "\u9875\u9762\u8fd8\u5728\u52a0\u8f7d\u8fd9\u4e2a\u52a8\u4f5c\uff0c\u7a0d\u7b49\u4e00\u4e0b\u5c31\u4f1a\u53d8\u4e3a\u53ef\u70b9\u3002",
          };
          const priority =
            label === "\u626b\u63cf\u804c\u4f4d"
              ? "workspace"
              : section.title === "\u7b80\u5386"
                ? "primary"
                : "standard";
          const tagsMarkup = (content.tags || [])
            .map((tag) => `<span class="tool-card-tag">${tag}</span>`)
            .join("");
          const tooltip = override?.meta || (disabled ? content.waiting : content.ready);
          const statusLabel = override?.statusLabel || (disabled ? "\u7b49\u5f85\u4e2d" : "\u53ef\u7528");
          const statusKey = override?.statusKey || (disabled ? "waiting" : "ready");
          return `
            <button
              type="button"
              class="tool-card"
              data-tool-card-label="${label}"
              data-tool-card-priority="${priority}"
              ${disabled ? "disabled" : ""}
            >
              <span>
                <span class="tool-card-label">${label}</span>
                <span class="tool-card-meta">${tooltip}</span>
                ${tagsMarkup ? `<span class="tool-card-tags">${tagsMarkup}</span>` : ""}
                <span class="tool-card-status" data-status="${statusKey}">${statusLabel}</span>
              </span>
              <span class="tool-card-badge">${content.badge}</span>
            </button>
          `;
        })
        .join("");

      return `
        <section class="tool-panel-section">
          <div class="tool-panel-section-title">${section.title}</div>
          <div class="tool-panel-section-description">${section.description || ""}</div>
          <div class="tool-panel-grid">${cards}</div>
        </section>
      `;
    });

    const sectionsMarkup = fragments.join("");
    if (sectionsMarkup !== lastSectionsMarkup) {
      sectionsHost.innerHTML = sectionsMarkup;
      lastSectionsMarkup = sectionsMarkup;
    }
    panel.dataset.empty = sectionsMarkup ? "false" : "true";
    panel.dataset.ready = actionableCount > 0 ? "true" : "false";
    renderScanResults(panel);

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
      hideScanPayloadMarkers();
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
