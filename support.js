// Compatibility loader for Arshia·Español.
// Keeps the generated dc-runtime pinned to the last known-good build while
// normalizing legacy Gemini requests to the current Gemini 3.x API contract.
"use strict";
(() => {
  const RUNTIME_COMMIT = "3355cdc9064d409ec1ece7bc8beddba20e80f30f";
  const RUNTIME_URL = `https://cdn.jsdelivr.net/gh/Arshia-Gha/Spanish@${RUNTIME_COMMIT}/support.js`;

  const MODEL_MAP = {
    "gemini-flash-lite-latest": "gemini-3.5-flash-lite",
    "gemini-flash-latest": "gemini-3.6-flash"
  };

  const nativeFetch = window.fetch.bind(window);

  window.fetch = async (input, init = {}) => {
    let url;
    try {
      const raw = typeof input === "string" || input instanceof URL ? input : input && input.url;
      if (!raw) return nativeFetch(input, init);
      url = new URL(raw, window.location.href);
    } catch (_) {
      return nativeFetch(input, init);
    }

    const geminiMatch = url.pathname.match(/^\/v1beta\/models\/([^/]+):generateContent$/);
    if (url.hostname !== "generativelanguage.googleapis.com" || !geminiMatch) {
      return nativeFetch(input, init);
    }

    const oldModel = decodeURIComponent(geminiMatch[1]);
    const model = MODEL_MAP[oldModel] || oldModel;
    if (model !== oldModel) {
      url.pathname = `/v1beta/models/${encodeURIComponent(model)}:generateContent`;
    }

    const baseHeaders = input instanceof Request ? input.headers : undefined;
    const headers = new Headers(baseHeaders || {});
    new Headers(init.headers || {}).forEach((value, key) => headers.set(key, value));

    const key = url.searchParams.get("key");
    if (key) {
      headers.set("x-goog-api-key", key);
      url.searchParams.delete("key");
    }

    let body = init.body;
    if (body === undefined && input instanceof Request && input.method !== "GET" && input.method !== "HEAD") {
      try {
        body = await input.clone().text();
      } catch (_) {}
    }

    if (typeof body === "string") {
      try {
        const payload = JSON.parse(body);
        const config = payload && payload.generationConfig;
        if (config && typeof config === "object" && /^gemini-3(?:\.|$)/.test(model)) {
          delete config.temperature;
          delete config.topP;
          delete config.topK;
          config.thinkingConfig = { thinkingLevel: "minimal" };
        }
        body = JSON.stringify(payload);
      } catch (_) {
        // Non-JSON bodies are passed through unchanged.
      }
    }

    const nextInit = {
      ...init,
      method: init.method || (input instanceof Request ? input.method : undefined),
      headers,
      body
    };

    try {
      return await nativeFetch(url.toString(), nextInit);
    } catch (error) {
      console.error("Gemini request failed", error);
      throw error;
    }
  };

  document.write(`<script src="${RUNTIME_URL}"><\/script>`);
})();
