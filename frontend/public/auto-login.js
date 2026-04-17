(function () {
  const username = "local-user";
  const password = "job-mediator-123";
  const attemptKey = "ai_job_mediator_auto_login_attempted";
  const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const rootPath =
    (document
      .querySelector('meta[property="og:root_path"]')
      ?.getAttribute("content") || "").replace(/\/$/, "");
  const appRootUrl = window.location.origin + rootPath + "/";
  const currentPath = window.location.pathname.replace(/\/$/, "");
  const loginPath = (rootPath || "") + "/login";
  const isLoginPage = currentPath === loginPath;
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
  autoLogin();
})();
