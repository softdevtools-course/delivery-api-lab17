(() => {
  const tokenInput = document.getElementById("student-token");
  const form = document.getElementById("token-form");
  const registrationForm = document.getElementById("registration-form");
  const issuedPanel = document.getElementById("issued-token-panel");
  const issuedToken = document.getElementById("issued-token");
  const status = document.getElementById("connection-status");
  const toast = document.getElementById("progress-toast");
  const completionMessage = document.getElementById("completion-message");
  let swagger;
  let activeToken = null;
  let lastCompletionState = null;
  let progressRefreshTimer;
  let toastTimer;

  function showToast(message) {
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toast.hidden = true; }, 4000);
  }

  function setAuthorization(token) {
    if (!swagger) return;
    swagger.authActions.logout(["BearerAuth"]);
    if (token) swagger.preauthorizeApiKey("BearerAuth", token);
  }

  async function refreshProgress(token, announceChanges = false) {
    status.textContent = "Загружаем прогресс…";
    try {
      const response = await fetch("/progress", {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(response.status === 401 ? "Токен недействителен или срок его действия истёк." : "Не удалось загрузить прогресс.");
      const tasks = await response.json();
      const completionState = Object.fromEntries(tasks.map((task) => [task.task_code, task.completed]));
      const allCompleted = tasks.length > 0 && tasks.every((task) => task.completed);
      const wasAllCompleted = lastCompletionState !== null
        && Object.keys(lastCompletionState).length > 0
        && Object.values(lastCompletionState).every(Boolean);
      const changed = lastCompletionState !== null && Object.keys(completionState).some(
        (code) => lastCompletionState[code] !== completionState[code],
      );
      const newlyCompleted = tasks.filter(
        (task) => task.completed && lastCompletionState && !lastCompletionState[task.task_code],
      );
      lastCompletionState = completionState;
      completionMessage.hidden = !allCompleted;
      for (const task of tasks) {
        const row = document.querySelector(`[data-task-code="${CSS.escape(task.task_code)}"]`);
        if (!row) continue;
        row.classList.toggle("completed", task.completed);
        row.querySelector(".task-state").textContent = task.completed ? "✓" : "○";
      }
      status.textContent = "Токен принят. Прогресс обновлён.";
      if (announceChanges && changed) {
        const completedTitles = newlyCompleted.map((task) => task.title);
        showToast(allCompleted && !wasAllCompleted
          ? "Задание успешно выполнено! На этом лабораторная работа завершена."
          : completedTitles.length
          ? `Прогресс обновлён: выполнено — ${completedTitles.join(", ")}.`
          : "Прогресс обновлён.");
      }
    } catch (error) {
      status.textContent = error.message;
    }
  }

  function scheduleProgressRefresh() {
    if (!activeToken) return;
    clearTimeout(progressRefreshTimer);
    progressRefreshTimer = setTimeout(() => refreshProgress(activeToken, true), 120);
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const token = tokenInput.value.trim();
    activeToken = token || null;
    lastCompletionState = null;
    setAuthorization(token);
    if (token) refreshProgress(token);
    else status.textContent = "Введите учебный токен.";
  });

  registrationForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    status.textContent = "Создаём учебную сессию…";
    const values = Object.fromEntries(new FormData(registrationForm));
    try {
      const response = await fetch("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
        cache: "no-store",
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Не удалось зарегистрировать студента.");
      issuedToken.value = result.access_token;
      issuedPanel.hidden = false;
      tokenInput.value = result.access_token;
      activeToken = result.access_token;
      lastCompletionState = null;
      setAuthorization(result.access_token);
      refreshProgress(result.access_token);
      status.textContent = "Сессия создана на 24 часа. Скопируйте токен: повторная регистрация создаёт новую сессию.";
    } catch (error) {
      status.textContent = error.message;
    }
  });

  document.getElementById("copy-token").addEventListener("click", async () => {
    issuedToken.select();
    try {
      await navigator.clipboard.writeText(issuedToken.value);
      status.textContent = "Токен скопирован.";
    } catch {
      status.textContent = "Выделите токен и скопируйте его вручную.";
    }
  });

  swagger = SwaggerUIBundle({
    url: "/openapi.json",
    dom_id: "#swagger-ui",
    deepLinking: true,
    persistAuthorization: false,
    validatorUrl: "none",
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
    responseInterceptor: (response) => {
      if (!activeToken || !response.url) return response;
      try {
        const responseUrl = new URL(response.url, window.location.href);
        if (responseUrl.origin === window.location.origin
            && responseUrl.pathname !== "/progress"
            && responseUrl.pathname !== "/openapi.json") {
          scheduleProgressRefresh();
        }
      } catch {
        // Ignore responses with URLs that cannot be interpreted as local API paths.
      }
      return response;
    },
  });
})();
