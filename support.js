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

  let tutorActive = false;
  let tutorSection = null;
  let tutorFrame = null;
  let tutorButton = null;

  const hideRegularSections = () => {
    if (!tutorActive) return;
    document.querySelectorAll("main").forEach(main => {
      if (main === tutorSection) return;
      if (!main.dataset.tutorHidden) {
        main.dataset.tutorHidden = "1";
        main.dataset.tutorOldDisplay = main.style.display || "";
      }
      main.style.display = "none";
    });
  };

  const restoreRegularSections = () => {
    document.querySelectorAll('main[data-tutor-hidden="1"]').forEach(main => {
      main.style.display = main.dataset.tutorOldDisplay || "";
      delete main.dataset.tutorHidden;
      delete main.dataset.tutorOldDisplay;
    });
  };

  const setTutorButtonActive = active => {
    if (!tutorButton || !tutorButton.isConnected) return;
    tutorButton.style.background = active ? "#1B1A17" : "transparent";
    tutorButton.style.color = active ? "#fff" : "#5C574D";
  };

  const prepareEmbeddedTutor = () => {
    if (!tutorFrame) return;
    try {
      const doc = tutorFrame.contentDocument;
      if (!doc) return;
      const innerHeader = doc.querySelector("header");
      if (innerHeader) innerHeader.style.display = "none";
      const innerMain = doc.querySelector("main");
      if (innerMain) {
        innerMain.style.paddingTop = "10px";
        innerMain.style.maxWidth = "860px";
      }
      doc.documentElement.style.background = "#FAF9F6";
      doc.body.style.background = "#FAF9F6";
    } catch (_) {}
  };

  const ensureTutorSection = () => {
    if (tutorSection && tutorSection.isConnected) return tutorSection;
    const header = document.querySelector("header");
    if (!header) return null;

    tutorSection = document.createElement("main");
    tutorSection.id = "aiTutorMainSection";
    tutorSection.style.cssText = "max-width:1060px;margin:0 auto;padding:0;display:none;animation:fadein .2s ease";

    tutorFrame = document.createElement("iframe");
    tutorFrame.src = "./chat.html?embedded=1";
    tutorFrame.title = "Tutor de español";
    tutorFrame.setAttribute("allow", "microphone");
    tutorFrame.style.cssText = "display:block;width:100%;height:calc(100dvh - 66px);min-height:620px;border:0;background:#FAF9F6";
    tutorFrame.addEventListener("load", prepareEmbeddedTutor);
    tutorSection.appendChild(tutorFrame);
    header.insertAdjacentElement("afterend", tutorSection);
    return tutorSection;
  };

  const openTutor = () => {
    const section = ensureTutorSection();
    if (!section) return;
    tutorActive = true;
    hideRegularSections();
    section.style.display = "block";
    setTutorButtonActive(true);
    if (location.hash !== "#chat") history.pushState({tutorChat:true}, "", "#chat");
    window.scrollTo(0, 0);
  };

  const closeTutor = ({cleanHash=false} = {}) => {
    if (!tutorActive) return;
    tutorActive = false;
    if (tutorSection && tutorSection.isConnected) tutorSection.style.display = "none";
    restoreRegularSections();
    setTutorButtonActive(false);
    if (cleanHash && location.hash === "#chat") {
      history.replaceState(null, "", location.pathname + location.search);
    }
  };

  const installTutorTab = () => {
    const nav = document.querySelector("header nav");
    if (!nav) return false;

    const existing = nav.querySelector('[data-tutor-chat="1"]');
    if (existing) {
      tutorButton = existing;
      setTutorButtonActive(tutorActive);
      return true;
    }

    tutorButton = document.createElement("button");
    tutorButton.type = "button";
    tutorButton.dataset.tutorChat = "1";
    tutorButton.textContent = "Chat";
    tutorButton.style.cssText = "padding:10px 14px;border-radius:8px;border:none;cursor:pointer;font-size:13.5px;font-weight:600;min-height:44px;background:transparent;color:#5C574D";
    tutorButton.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      openTutor();
    });
    nav.appendChild(tutorButton);
    setTutorButtonActive(tutorActive);
    return true;
  };

  const handleNormalNavClick = event => {
    if (!tutorActive) return;
    if (event.target.closest('[data-tutor-chat="1"]')) return;
    if (event.target.closest("header nav button")) closeTutor({cleanHash:true});
  };

  const maintainTutorUI = () => {
    const installed = installTutorTab();
    if (!installed) return;
    ensureTutorSection();
    if (tutorActive) {
      hideRegularSections();
      if (tutorSection) tutorSection.style.display = "block";
      setTutorButtonActive(true);
    }
  };

  const startTutorIntegration = () => {
    document.addEventListener("click", handleNormalNavClick, true);

    // The generated app may replace its rendered header during initialization or
    // later state updates. Observe the whole document and always reattach Chat
    // to the current rendered nav instead of assuming the first nav survives.
    const observer = new MutationObserver(() => maintainTutorUI());
    observer.observe(document.documentElement, {childList:true, subtree:true});

    // A short heartbeat covers renderer updates that do not produce a useful
    // mutation for our observer. It is tiny and stops doing work once Chat exists.
    setInterval(maintainTutorUI, 750);

    window.addEventListener("popstate", () => {
      if (location.hash === "#chat") openTutor();
      else closeTutor();
    });
    window.addEventListener("hashchange", () => {
      if (location.hash === "#chat") openTutor();
      else closeTutor();
    });

    maintainTutorUI();
    if (location.hash === "#chat") {
      const waitForRender = setInterval(() => {
        if (installTutorTab() && ensureTutorSection()) {
          clearInterval(waitForRender);
          openTutor();
        }
      }, 150);
      setTimeout(() => clearInterval(waitForRender), 10000);
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startTutorIntegration, {once:true});
  } else {
    startTutorIntegration();
  }

  document.write(`<script src="${RUNTIME_URL}"><\/script>`);
})();
