// ==UserScript==
// @name         Bitwarden 内联菜单临时开关
// @namespace    https://github.com/YewFence/yew-needles
// @version      0.1.0
// @description  用 Alt+Shift+B 临时隐藏或恢复当前页面中的 Bitwarden 内联自动填充菜单，不停用 Bitwarden 扩展。
// @author       YewFence
// @match        http://*/*
// @match        https://*/*
// @run-at       document-start
// @grant        GM_registerMenuCommand
// ==/UserScript==

(() => {
  "use strict";

  // 想换快捷键时，只需修改这里。event.code 使用键盘物理按键名。
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

  // 这里只保存由本脚本关闭的元素。恢复时不会误打开原本就关闭的菜单。
  const suppressedElements = new Set();

  const mutationObserver = new MutationObserver(() => scheduleScan());

  /**
   * Bitwarden 会随机生成宿主元素名，但当前实现仍有一组相当独特的特征：
   * - 手动 popover；
   * - all: initial !important；
   * - fixed 定位、block 显示；
   * - 使用浏览器允许的最大 z-index。
   *
   * Chrome/Edge 使用总长度 9 到 15、带 1 到 3 个连字符的随机自定义元素名。
   * 匹配条件有意设置得较严格：Bitwarden 改实现后宁可失效，也不要误隐藏网页元素。
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
      // Chromium 在 all 之后设置具体属性时会让 all 的 CSSOM 值变为空，
      // 但仍保留这条声明的 important 优先级。
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

    try {
      if (element.matches(":popover-open")) {
        suppressedElements.add(element);
        element.hidePopover();
      }
    } catch {
      // 某些旧浏览器可能只实现了部分 Popover API；遇到时保持网页原状。
    }
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

    // Bitwarden 通常在焦点或指针事件结束后显示菜单，推迟到微任务再检查。
    scheduleScan();
  }

  function startSuppressing() {
    mutationObserver.observe(document, { childList: true, subtree: true });
    document.addEventListener("focusin", handlePossibleMenuOpen, true);
    document.addEventListener("pointerdown", handlePossibleMenuOpen, true);
    document.addEventListener("toggle", handlePossibleMenuOpen, true);
    scanAndSuppress();

    // 首次切换可能恰好和 Bitwarden 的异步显示处于同一帧，再兜底检查一次。
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
    const elements = [...suppressedElements];
    suppressedElements.clear();

    for (const element of elements) {
      if (!element.isConnected || !isBitwardenInlineMenuHost(element)) {
        continue;
      }

      try {
        if (!element.matches(":popover-open")) {
          element.showPopover();
        }
      } catch {
        // 元素所在的 dialog 可能已经关闭，或 Bitwarden 已让此菜单失效。
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
      showToast(paused ? "Bitwarden 内联菜单：已隐藏" : "Bitwarden 内联菜单：已恢复");
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
        // 跨域 WindowProxy 正常支持 postMessage；若 frame 正在销毁，忽略即可。
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
        // 请求状态的 frame 可能已经导航。
      }
      return;
    }

    if (message.type === "state" && typeof message.paused === "boolean") {
      setPaused(message.paused);
      // 将状态继续传给嵌套 iframe。
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
      GM_registerMenuCommand("切换 Bitwarden 内联菜单（Alt+Shift+B）", toggleFromTopFrame);
    }
  } else {
    // 新加载的 iframe 主动继承顶层页面当前的开关状态。
    window.top.postMessage({ channel: messageChannel, type: "request-state" }, "*");
  }
})();
