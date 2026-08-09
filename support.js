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

  // Keep the tutor internally isolated, but present it as a normal section of
  // the main app so the working generated runtime does not need to be edited.
  let tutorActive = false;
  let tutorSection = null;
  let tutorFrame = null;
  let tutorButton = null;
  let sectionObserver = null;

  const hideRegularSections = () => {
    if (!tutorActive) return;
    document.querySelectorAll("main").forEach(main => {
      if (main === tutorSection || main.closest("iframe")) return;
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
    if (!tutorButton) return;
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
    tutorSection.style.cssText = [
      "max-width:1060px",
      "margin:0 auto",
      "padding:0 0 0",
      "display:none",
      "animation:fadein .2s ease"
    ].join(";");

    tutorFrame = document.createElement("iframe");
    tutorFrame.src = "./chat.html?embedded=1";
    tutorFrame.title = "Tutor de español";
    tutorFrame.setAttribute("allow", "microphone");
    tutorFrame.style.cssText = [
      "display:block",
      "width:100%",
      "height:calc(100dvh - 66px)",
      "min-height:620px",
      "border:0",
      "background:#FAF9F6"
    ].join(";");
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
    window.scrollTo({top:0, behavior:"instant"});
  };

  const closeTutor = ({cleanHash=false} = {}) => {
    if (!tutorActive) return;
    tutorActive = false;
    if (tutorSection) tutorSection.style.display = "none";
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

    // Any normal app tab closes the embedded tutor first, then the original
    // click handler continues normally.
    nav.addEventListener("click", event => {
      if (!tutorActive) return;
      if (event.target.closest('[data-tutor-chat="1"]')) return;
      closeTutor({cleanHash:true});
    }, true);

    return true;
  };

  const startTutorIntegration = () => {
    const install = () => {
      if (!installTutorTab()) return false;
      ensureTutorSection();
      if (location.hash === "#chat") openTutor();
      return true;
    };

    if (!install()) {
      const observer = new MutationObserver(() => {
        if (install()) observer.disconnect();
      });
      observer.observe(document.documentElement, {childList:true, subtree:true});
      setTimeout(() => observer.disconnect(), 15000);
    }

    sectionObserver = new MutationObserver(() => hideRegularSections());
    sectionObserver.observe(document.documentElement, {childList:true, subtree:true});

    window.addEventListener("popstate", () => {
      if (location.hash === "#chat") openTutor();
      else closeTutor();
    });
    window.addEventListener("hashchange", () => {
      if (location.hash === "#chat") openTutor();
      else closeTutor();
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startTutorIntegration, {once:true});
  } else {
    startTutorIntegration();
  }

  document.write(`<script src="${RUNTIME_URL}"><\/script>`);
})();
