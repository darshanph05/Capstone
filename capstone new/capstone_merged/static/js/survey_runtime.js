(function () {
  const APP_CONFIG = window.APP_CONFIG || {};
  const DEFAULT_API_BASE = APP_CONFIG.apiBaseUrl || "http://127.0.0.1:8000";
  const API_BASE_KEY = "admin_api_base";
  const STATE_KEY = "participant_survey_state";

  function getApiBase() {
    return (localStorage.getItem(API_BASE_KEY) || DEFAULT_API_BASE).replace(/\/$/, "");
  }

  function getState() {
    try {
      return JSON.parse(sessionStorage.getItem(STATE_KEY) || "{}");
    } catch (_) {
      return {};
    }
  }

  function setState(next) {
    sessionStorage.setItem(STATE_KEY, JSON.stringify(next || {}));
  }

  function patchState(patch) {
    const current = getState();
    setState({ ...current, ...patch });
    return getState();
  }

  function clearState() {
    sessionStorage.removeItem(STATE_KEY);
  }

  function getTokenFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const queryToken = (params.get("token") || "").trim();
    if (queryToken) {
      return queryToken;
    }

    const match = (window.location.pathname || "").match(/^\/survey\/([^/?#]+)$/);
    if (!match) {
      return "";
    }

    const candidate = decodeURIComponent(match[1] || "").trim();
    const reserved = new Set(["consent", "student-details", "instructions", "questions", "submitted"]);
    return reserved.has(candidate.toLowerCase()) ? "" : candidate;
  }

  async function request(path, options) {
    const response = await fetch(`${getApiBase()}${path}`, options || {});
    let data = null;
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json();
    }
    if (!response.ok) {
      const message =
        (data && (data.message || data.detail)) ||
        `Request failed (${response.status})`;
      throw new Error(message);
    }
    return data;
  }

  function normalizeQuestionType(rawType) {
    const type = String(rawType || "").trim().toLowerCase();
    if (!type) return "mcq";
    if (type === "text" || type === "textentry" || type === "text-entry") {
      return "text_entry";
    }
    if (type === "multiple_choice" || type === "multiple-choice") {
      return "mcq";
    }
    return type;
  }

  function normalizeQuestions(survey) {
    const questions = Array.isArray(survey?.questions) ? survey.questions.slice() : [];
    return questions
      .filter((q) => q && q.is_visible !== false)
      .map((q) => ({
        ...q,
        type: normalizeQuestionType(q.type),
      }))
      .sort((a, b) => (a.order_index || 0) - (b.order_index || 0));
  }

  function buildFlow(questions) {
    const sorted = Array.isArray(questions) ? questions.slice() : [];
    const arrowQuestions = sorted
      .filter((q) => q.type === "arrow")
      .sort((a, b) => (a.order_index || 0) - (b.order_index || 0));
    const mcqQuestions = sorted
      .filter((q) => q.type === "mcq")
      .sort((a, b) => (a.order_index || 0) - (b.order_index || 0));
    const textEntryQuestions = sorted
      .filter((q) => q.type === "text_entry")
      .sort((a, b) => (a.order_index || 0) - (b.order_index || 0));
    const otherQuestions = sorted
      .filter((q) => q.type !== "arrow" && q.type !== "mcq" && q.type !== "text_entry")
      .sort((a, b) => (a.order_index || 0) - (b.order_index || 0));

    const orderedQuestions = [...arrowQuestions, ...mcqQuestions, ...textEntryQuestions, ...otherQuestions];
    const hasNonArrowSections = mcqQuestions.length > 0 || textEntryQuestions.length > 0 || otherQuestions.length > 0;
    const steps = [];

    if (arrowQuestions.length > 0) {
      if (hasNonArrowSections) {
        steps.push({ kind: "instruction", questionType: "arrow" });
      }
      arrowQuestions.forEach((q) => {
        steps.push({ kind: "question", questionType: "arrow", questionId: q.id });
      });
    }

    if (mcqQuestions.length > 0) {
      steps.push({ kind: "instruction", questionType: "mcq" });
      mcqQuestions.forEach((q) => {
        steps.push({ kind: "question", questionType: "mcq", questionId: q.id });
      });
    }

    textEntryQuestions.forEach((q) => {
      steps.push({ kind: "question", questionType: "text_entry", questionId: q.id });
    });

    otherQuestions.forEach((q) => {
      steps.push({ kind: "question", questionType: q.type || "mcq", questionId: q.id });
    });

    if (!steps.length && orderedQuestions.length > 0) {
      orderedQuestions.forEach((q) => {
        steps.push({ kind: "question", questionType: q.type || "mcq", questionId: q.id });
      });
    }

    return { orderedQuestions, steps };
  }

  async function loadSurveyByToken(token) {
    const survey = await request(`/surveys/${encodeURIComponent(token)}/show`, {
      method: "GET",
    });
    const questions = normalizeQuestions(survey);
    const flow = buildFlow(questions);
    patchState({
      token,
      survey: { ...survey, questions: flow.orderedQuestions },
      participant: null,
      attempt: null,
      flowSteps: flow.steps,
      currentStepIndex: 0,
      currentIndex: 0,
      answers: {},
      sectionTimers: {},
      mrInstructionSlide: 0,
    });
    return survey;
  }

  async function submitParticipant(payload) {
    return request("/participants/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async function submitOneAnswer(attemptId, payload) {
    return request(`/participants/attempts/${attemptId}/answers/one`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async function doneAttempt(attemptId) {
    return request(`/participants/attempts/${attemptId}/done`, {
      method: "POST",
    });
  }

  window.SurveyRuntime = {
    getApiBase,
    getState,
    setState,
    patchState,
    clearState,
    getTokenFromUrl,
    loadSurveyByToken,
    submitParticipant,
    submitOneAnswer,
    doneAttempt,
  };
})();
