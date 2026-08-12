// ==UserScript==
// @name         Bitwarden Inline Menu Toggle
// @namespace    https://github.com/YewFence/yew-needles
// @version      0.1.1
// @description  Temporarily hide or restore Bitwarden's inline autofill menu on the current page with Alt+Shift+B without disabling the extension.
// @author       YewFence
// @match        http://*/*
// @match        https://*/*
// @run-at       document-start
// @grant        GM_registerMenuCommand
// ==/UserScript==

(() => {
  "use strict";

  // Change this object to use a different shortcut. event.code identifies the physical key.
  const shortcut = Object.freeze({
    code: "KeyB",
    altKey: true,
    shiftKey: true,
    ctrlKey: false,
    metaKey: false,
  });

  const messageChannel = "yewfence:bitwarden-inline-menu-toggle:v1";
  const isTopFrame = window.top === window;

  let paused = false;
  let scanScheduled = false;
  let toastTimer;

  // Track only hosts detached by this script so restoring never affects unrelated page elements.
  const suppressedElements = new Map();

  const mutationObserver = new MutationObserver(() => scheduleScan());

  /**
   * Bitwarden randomizes its host element names, but the current implementation still has
   * a distinctive combination of characteristics:
   * - a manual popover;
   * - all: initial !important;
   * - fixed positioning and block display;
   * - the browser's maximum z-index.
   *
   * Chrome and Edge use randomized custom element names 9 to 15 characters long with
   * one to three hyphens. The matcher is intentionally strict: if Bitwarden changes its
   * implementation, failing safely is preferable to hiding an unrelated page element.
   */
  function isBitwardenInlineMenuHost(element) {
    if (!(element instanceof HTMLElement)) {
      return false;
    }

    if (element.getAttribute("popover") !== "manual" || element.childElementCount !== 0) {
      return false;
    }

    const tagName = element.localName;
    const looksLikeRandomCustomElement =
      tagName.length >= 9 &&
      tagName.length <= 15 &&
      /^[a-z]+(?:-[a-z]+){1,3}$/.test(tagName);
    if (!looksLikeRandomCustomElement) {
      return false;
    }

    const style = element.style;
    const hasImportantValue = (property, value) =>
      style.getPropertyValue(property).trim() === value &&
      style.getPropertyPriority(property) === "important";

    return (
      // Chromium clears the CSSOM value for `all` when specific properties follow it,
      // but preserves the declaration's important priority.
      style.getPropertyPriority("all") === "important" &&
      hasImportantValue("position", "fixed") &&
      hasImportantValue("display", "block") &&
      hasImportantValue("z-index", "2147483647") &&
      typeof element.hidePopover === "function" &&
      typeof element.showPopover === "function"
    );
  }

  function suppressElement(element) {
    if (!paused || !isBitwardenInlineMenuHost(element)) {
      return;
    }

    const existingRecord = suppressedElements.get(element);
    if (existingRecord) {
      if (element.isConnected) {
        element.remove();
      }
      return;
    }

    const parent = element.parentNode;
    if (!parent) {
      return;
    }

    suppressedElements.set(element, {
      parent,
      nextSibling: element.nextSibling,
      wasPopoverOpen: element.matches(":popover-open"),
    });
    element.remove();
  }

  function scanAndSuppress() {
    scanScheduled = false;
    if (!paused) {
      return;
    }

    document.querySelectorAll('[popover="manual"]').forEach(suppressElement);
  }

  function scheduleScan() {
    if (!paused || scanScheduled) {
      return;
    }

    scanScheduled = true;
    queueMicrotask(scanAndSuppress);
  }

  function handlePossibleMenuOpen(event) {
    if (!paused) {
      return;
    }

    if (event.type === "toggle" && event.target instanceof HTMLElement) {
      suppressElement(event.target);
      return;
    }

    // Bitwarden usually opens the menu after focus or pointer handling completes.
    scheduleScan();
  }

  function startSuppressing() {
    mutationObserver.observe(document, { childList: true, subtree: true });
    document.addEventListener("focusin", handlePossibleMenuOpen, true);
    document.addEventListener("pointerdown", handlePossibleMenuOpen, true);
    document.addEventListener("toggle", handlePossibleMenuOpen, true);
    scanAndSuppress();

    // The first toggle can share a frame with Bitwarden's asynchronous menu insertion.
    requestAnimationFrame(scanAndSuppress);
  }

  function stopSuppressing() {
    mutationObserver.disconnect();
    document.removeEventListener("focusin", handlePossibleMenuOpen, true);
    document.removeEventListener("pointerdown", handlePossibleMenuOpen, true);
    document.removeEventListener("toggle", handlePossibleMenuOpen, true);
    scanScheduled = false;
  }

  function restoreSuppressedElements() {
    const entries = [...suppressedElements];
    suppressedElements.clear();

    for (const [element, { parent, nextSibling }] of [...entries].reverse()) {
      if (element.isConnected || !parent.isConnected || !isBitwardenInlineMenuHost(element)) {
        continue;
      }

      const insertionPoint = nextSibling?.parentNode === parent ? nextSibling : null;
      parent.insertBefore(element, insertionPoint);
    }

    for (const [element, { wasPopoverOpen }] of entries) {
      if (!wasPopoverOpen || !element.isConnected) {
        continue;
      }

      try {
        element.showPopover();
      } catch {
        // The containing dialog may have closed, or Bitwarden may have invalidated the menu.
      }
    }
  }

  function setPaused(nextPaused, announce = false) {
    if (paused === nextPaused) {
      return;
    }

    paused = nextPaused;
    if (paused) {
      startSuppressing();
    } else {
      stopSuppressing();
      restoreSuppressedElements();
    }

    if (announce && isTopFrame) {
      showToast(paused ? "Bitwarden inline menu hidden" : "Bitwarden inline menu restored");
    }
  }

  function toggleFromTopFrame() {
    setPaused(!paused, true);
    broadcastStateToChildFrames();
  }

  function broadcastStateToChildFrames() {
    for (let index = 0; index < window.frames.length; index += 1) {
      try {
        window.frames[index].postMessage(
          { channel: messageChannel, type: "state", paused },
          "*",
        );
      } catch {
        // Cross-origin WindowProxy supports postMessage; ignore frames being destroyed.
      }
    }
  }

  function handleMessage(event) {
    const message = event.data;
    if (!message || message.channel !== messageChannel) {
      return;
    }

    if (isTopFrame && message.type === "toggle") {
      toggleFromTopFrame();
      return;
    }

    if (isTopFrame && message.type === "request-state") {
      try {
        event.source?.postMessage({ channel: messageChannel, type: "state", paused }, "*");
      } catch {
        // The requesting frame may have navigated.
      }
      return;
    }

    if (message.type === "state" && typeof message.paused === "boolean") {
      setPaused(message.paused);
      // Forward the state to nested frames.
      broadcastStateToChildFrames();
    }
  }

  function matchesShortcut(event) {
    return (
      event.code === shortcut.code &&
      event.altKey === shortcut.altKey &&
      event.shiftKey === shortcut.shiftKey &&
      event.ctrlKey === shortcut.ctrlKey &&
      event.metaKey === shortcut.metaKey
    );
  }

  function handleShortcut(event) {
    if (event.repeat || !matchesShortcut(event)) {
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();

    if (isTopFrame) {
      toggleFromTopFrame();
    } else {
      window.top.postMessage({ channel: messageChannel, type: "toggle" }, "*");
    }
  }

  function showToast(text) {
    const render = () => {
      document.getElementById("yewfence-bitwarden-inline-menu-status")?.remove();

      const toast = document.createElement("div");
      toast.id = "yewfence-bitwarden-inline-menu-status";
      toast.textContent = text;
      toast.setAttribute("role", "status");
      Object.assign(toast.style, {
        all: "initial",
        position: "fixed",
        top: "16px",
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: "2147483646",
        padding: "9px 14px",
        border: "1px solid rgba(255, 255, 255, 0.2)",
        borderRadius: "8px",
        background: "rgba(24, 24, 27, 0.94)",
        boxShadow: "0 6px 24px rgba(0, 0, 0, 0.28)",
        color: "#fafafa",
        font: "13px/1.4 system-ui, sans-serif",
        pointerEvents: "none",
      });

      document.documentElement.appendChild(toast);
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.remove(), 1400);
    };

    if (document.documentElement) {
      render();
    } else {
      document.addEventListener("DOMContentLoaded", render, { once: true });
    }
  }

  window.addEventListener("message", handleMessage);
  window.addEventListener("keydown", handleShortcut, true);

  if (isTopFrame) {
    if (typeof GM_registerMenuCommand === "function") {
      GM_registerMenuCommand("Toggle Bitwarden inline menu (Alt+Shift+B)", toggleFromTopFrame);
    }
  } else {
    // Newly loaded frames inherit the top-level page's current state.
    window.top.postMessage({ channel: messageChannel, type: "request-state" }, "*");
  }
})();
