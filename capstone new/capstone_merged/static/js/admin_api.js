(() => {
  const APP_CONFIG = window.APP_CONFIG || {};
  const TOKEN_KEY = "admin_access_token";
  const USER_KEY = "admin_current_user";
  const API_BASE_KEY = "admin_api_base";
  const DEFAULT_API_BASE = APP_CONFIG.apiBaseUrl || "http://127.0.0.1:8000";
  const DEFAULT_ALLOWED_ADMIN_ROLES =
    Array.isArray(APP_CONFIG.adminAllowedRoles) && APP_CONFIG.adminAllowedRoles.length
      ? APP_CONFIG.adminAllowedRoles.map((r) => String(r).toUpperCase())
      : ["ADMIN"];

  function getApiBase() {
    return (localStorage.getItem(API_BASE_KEY) || DEFAULT_API_BASE).replace(/\/$/, "");
  }

  function setApiBase(baseUrl) {
    const normalized = (baseUrl || DEFAULT_API_BASE).trim().replace(/\/$/, "");
    localStorage.setItem(API_BASE_KEY, normalized);
    return normalized;
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token || "");
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function redirectToLoginOnUnauthorized(message, redirectTo = "admin_login.html") {
    const currentPath = (window.location.pathname || "").toLowerCase();
    if (currentPath.endsWith("/admin_login.html") || currentPath.endsWith("admin_login.html")) {
      return;
    }
    clearSession();
    window.location.href = `${redirectTo}?error=${encodeURIComponent(message || "Could not validate credentials")}`;
  }

  function getAllowedAdminRoles() {
    return DEFAULT_ALLOWED_ADMIN_ROLES;
  }

  function isAllowedAdminRole(roleCode) {
    if (!roleCode) return false;
    return getAllowedAdminRoles().includes(String(roleCode).toUpperCase());
  }

  function getUser() {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  function setUser(user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user || null));
  }

  async function apiRequest(path, options = {}) {
    const {
      method = "GET",
      body,
      auth = true,
      headers = {},
    } = options;

    const requestHeaders = { ...headers };
    if (auth) {
      const token = getToken();
      if (token) {
        requestHeaders.Authorization = `Bearer ${token}`;
      }
    }
    if (body !== undefined && !requestHeaders["Content-Type"]) {
      requestHeaders["Content-Type"] = "application/json";
    }

    const response = await fetch(`${getApiBase()}${path}`, {
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    let data = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    }

    if (!response.ok) {
      const message =
        (data && (data.message || data.detail)) ||
        `Request failed (${response.status})`;
      if (response.status === 401) {
        redirectToLoginOnUnauthorized(message);
      }
      throw new Error(message);
    }

    return data;
  }

  async function login(username, password) {
    return apiRequest("/auth/login", {
      method: "POST",
      auth: false,
      body: { username, password },
    });
  }

  async function getMe() {
    return apiRequest("/auth/me", { method: "GET", auth: true });
  }

  async function ensureAuthenticated(config = {}) {
    const { requireAdmin = false, redirectTo = "admin_login.html" } = config;
    if (!getToken()) {
      window.location.href = redirectTo;
      return null;
    }
    try {
      const user = await getMe();
      if (requireAdmin && !isAllowedAdminRole(user?.role?.code)) {
        clearSession();
        throw new Error("Current role is not allowed to access admin pages.");
      }
      setUser(user);
      return user;
    } catch (error) {
      clearSession();
      window.location.href = `${redirectTo}?error=${encodeURIComponent(error.message)}`;
      return null;
    }
  }

  function logout(redirectTo = "admin_login.html") {
    clearSession();
    window.location.href = redirectTo;
  }

  function listSurveys() {
    return apiRequest("/surveys", { method: "GET" });
  }

  function getSurvey(surveyId) {
    return apiRequest(`/surveys/${surveyId}`, { method: "GET" });
  }

  function getSurveyQuestionResponses(surveyId, questionId) {
    return apiRequest(`/surveys/${surveyId}/questions/${questionId}/responses`, { method: "GET" });
  }

  async function exportSurveyQuestionResponsesCsv(surveyId, questionId) {
    const token = getToken();
    const response = await fetch(`${getApiBase()}/surveys/${surveyId}/questions/${questionId}/responses/export`, {
      method: "GET",
      headers: token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : {},
    });

    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const data = await response.json();
        message = (data && (data.message || data.detail)) || message;
      }
      if (response.status === 401) {
        redirectToLoginOnUnauthorized(message);
      }
      throw new Error(message);
    }

    const disposition = response.headers.get("content-disposition") || "";
    let filename = `question_${questionId}_responses.csv`;
    const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    const plainName = disposition.match(/filename="?([^";]+)"?/i);
    if (utf8Name && utf8Name[1]) {
      filename = decodeURIComponent(utf8Name[1]);
    } else if (plainName && plainName[1]) {
      filename = plainName[1];
    }

    const blob = await response.blob();
    return { blob, filename };
  }

  async function exportSurveyResponsesCsv(surveyId) {
    const token = getToken();
    const response = await fetch(`${getApiBase()}/surveys/${surveyId}/responses/export`, {
      method: "GET",
      headers: token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : {},
    });

    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const data = await response.json();
        message = (data && (data.message || data.detail)) || message;
      }
      if (response.status === 401) {
        redirectToLoginOnUnauthorized(message);
      }
      throw new Error(message);
    }

    const disposition = response.headers.get("content-disposition") || "";
    let filename = `survey_${surveyId}_responses.csv`;
    const utf8Name = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    const plainName = disposition.match(/filename="?([^";]+)"?/i);
    if (utf8Name && utf8Name[1]) {
      filename = decodeURIComponent(utf8Name[1]);
    } else if (plainName && plainName[1]) {
      filename = plainName[1];
    }

    const blob = await response.blob();
    return { blob, filename };
  }

  function upsertSurvey(payload) {
    return apiRequest("/surveys", {
      method: "POST",
      body: payload,
    });
  }

  function deleteSurvey(surveyId) {
    return apiRequest(`/surveys/${surveyId}`, {
      method: "DELETE",
    });
  }

  function regenerateToken(surveyId) {
    return apiRequest(`/surveys/${surveyId}/token`, {
      method: "POST",
    });
  }

  async function uploadImage(file, folder = "images") {
    if (!file) {
      throw new Error("No file selected");
    }

    const token = getToken();
    if (!token) {
      throw new Error("Missing access token");
    }

    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(
      `${getApiBase()}/upload/image?folder=${encodeURIComponent(folder)}`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      }
    );

    let data = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    }

    if (!response.ok) {
      const message =
        (data && (data.message || data.detail)) ||
        `Upload failed (${response.status})`;
      if (response.status === 401) {
        redirectToLoginOnUnauthorized(message);
      }
      throw new Error(message);
    }

    return data;
  }

  window.AdminApi = {
    getApiBase,
    setApiBase,
    getToken,
    setToken,
    getAllowedAdminRoles,
    isAllowedAdminRole,
    getUser,
    setUser,
    clearSession,
    apiRequest,
    login,
    getMe,
    ensureAuthenticated,
    logout,
    listSurveys,
    getSurvey,
    getSurveyQuestionResponses,
    exportSurveyQuestionResponsesCsv,
    exportSurveyResponsesCsv,
    upsertSurvey,
    deleteSurvey,
    regenerateToken,
    uploadImage,
  };
})();
