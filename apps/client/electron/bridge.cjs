// Browser bridge: keeps a logged in profile per site and drives it.
//
// Design rules:
//  * one persistent Chromium partition per provider (`persist:kv-<slug>`), so a
//    customer logs in once and the cookies stay on *their* laptop;
//  * the server never sees a password or a cookie - it only sends a command and
//    receives a result;
//  * the recipe op set is the same one the connector already uses
//    (`browser.goto|wait_for|click|type|press|extract|wait|screenshot`), so a
//    new site is data, not code;
//  * every command runs through a per-provider queue with a hard timeout.
const { BrowserWindow, session } = require("electron");

const SITES = new Map(); // provider -> { win, url }
const PAUSED = new Set();
const QUEUES = new Map(); // provider -> Promise (serialises commands)

// Facebook and friends refuse the Electron user agent; a real Chrome UA keeps
// the site in its normal desktop mode.
const CHROME_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36";

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function partitionFor(provider) {
  return `persist:kv-${String(provider).replace(/[^a-z0-9_-]/gi, "")}`;
}

function withQueue(provider, work) {
  const previous = QUEUES.get(provider) ?? Promise.resolve();
  const next = previous.then(work, work);
  QUEUES.set(
    provider,
    next.catch(() => undefined),
  );
  return next;
}

async function load(win, url, timeoutMs = 45000) {
  const current = win.webContents.getURL();
  if (current === url) return;
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error("load_timeout"));
    }, timeoutMs);
    function cleanup() {
      clearTimeout(timer);
      win.webContents.removeListener("did-finish-load", onDone);
      win.webContents.removeListener("did-fail-load", onFail);
    }
    function onDone() {
      cleanup();
      resolve();
    }
    function onFail(_event, code, description, validatedURL, isMainFrame) {
      if (isMainFrame === false) return;
      cleanup();
      reject(new Error(`load_failed:${code}:${description}:${validatedURL}`));
    }
    win.webContents.on("did-finish-load", onDone);
    win.webContents.on("did-fail-load", onFail);
    win.loadURL(url).catch((error) => {
      cleanup();
      reject(error);
    });
  });
}

async function ensureWindow(provider, url, { visible = false } = {}) {
  const entry = SITES.get(provider);
  if (entry && !entry.win.isDestroyed()) {
    if (visible) {
      if (entry.win.isMinimized()) entry.win.restore();
      entry.win.show();
      entry.win.focus();
    }
    if (url) await load(entry.win, url);
    return entry.win;
  }

  const win = new BrowserWindow({
    width: 1120,
    height: 840,
    show: visible,
    title: `کاروند — ${provider}`,
    backgroundColor: "#ffffff",
    autoHideMenuBar: true,
    webPreferences: {
      partition: partitionFor(provider),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      // a hidden window must keep timers alive, or Telegram Web stops loading
      backgroundThrottling: false,
    },
  });
  win.webContents.setUserAgent(CHROME_UA);
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  SITES.set(provider, { win, url });
  if (url) await load(win, url);
  return win;
}

/** Runs a snippet inside the page and returns a JSON-safe value. */
async function evaluate(win, body) {
  return win.webContents.executeJavaScript(`(() => { ${body} })()`, true);
}

const FIND_NODE = `
  const nodes = Array.from(document.querySelectorAll(SELECTOR));
  const seen = nodes.filter((n) => n.getClientRects().length > 0);
  const pool = seen.length ? seen : nodes;
  let node = null;
  if (CONTAINS) {
    node = pool.find((n) => ((n.innerText || n.textContent || "").includes(CONTAINS)));
  } else {
    node = pool[0] || null;
  }
`;

function clickBody(selector, contains) {
  return `
    const SELECTOR = ${JSON.stringify(selector)};
    const CONTAINS = ${JSON.stringify(contains ?? null)};
    ${FIND_NODE}
    if (!node) return { found: false };
    node.scrollIntoView({ block: "center" });
    const rect = node.getBoundingClientRect();
    const opts = {
      bubbles: true, cancelable: true, view: window,
      clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2,
    };
    node.dispatchEvent(new PointerEvent("pointerdown", opts));
    node.dispatchEvent(new MouseEvent("mousedown", opts));
    node.dispatchEvent(new PointerEvent("pointerup", opts));
    node.dispatchEvent(new MouseEvent("mouseup", opts));
    node.dispatchEvent(new MouseEvent("click", opts));
    return { found: true, tag: node.tagName, text: (node.innerText || "").slice(0, 80) };
  `;
}

function focusBody(selector, contains) {
  return `
    const SELECTOR = ${JSON.stringify(selector)};
    const CONTAINS = ${JSON.stringify(contains ?? null)};
    ${FIND_NODE}
    if (!node) return { found: false };
    node.scrollIntoView({ block: "center" });
    node.focus();
    const editable = node.isContentEditable || node.tagName === "TEXTAREA" || node.tagName === "INPUT";
    if (editable && !node.isContentEditable) {
      node.value = "";
      node.dispatchEvent(new Event("input", { bubbles: true }));
    }
    return { found: true, editable };
  `;
}

function waitBody(selector, contains, gone) {
  return `
    const SELECTOR = ${JSON.stringify(selector)};
    const CONTAINS = ${JSON.stringify(contains ?? null)};
    ${FIND_NODE}
    return { found: ${gone ? "!node" : "!!node"} };
  `;
}

function extractBody(selector, maxChars) {
  return `
    const nodes = Array.from(document.querySelectorAll(${JSON.stringify(selector)}));
    const text = nodes.map((n) => n.innerText || n.textContent || "").join("\\n").trim();
    return { count: nodes.length, text: text.slice(0, ${Number(maxChars) || 4000}) };
  `;
}

async function waitFor(win, { selector, contains, gone, timeout = 20000, interval = 250 }) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const result = await evaluate(win, waitBody(selector, contains, gone)).catch(() => ({
      found: false,
    }));
    if (result.found) return true;
    await delay(interval);
  }
  return false;
}

async function screenshot(win) {
  const image = await win.webContents.capturePage();
  if (image.isEmpty()) return null;
  // keep the payload small enough to travel through the API
  const { width } = image.getSize();
  const small = width > 1200 ? image.resize({ width: 1200 }) : image;
  return small.toPNG().toString("base64");
}

async function runOp(win, step, artifacts) {
  const op = String(step.op || "");
  switch (op) {
    case "browser.goto":
    case "browser.open":
      await load(win, String(step.url || ""));
      await delay(Number(step.settle_ms ?? 800));
      return { op, url: win.webContents.getURL() };
    case "browser.wait_for": {
      const found = await waitFor(win, {
        selector: String(step.selector),
        contains: step.contains,
        gone: Boolean(step.gone),
        timeout: Number(step.timeout ?? 20000),
      });
      if (!found) throw new Error(`wait_for_timeout:${step.selector}`);
      return { op, selector: step.selector };
    }
    case "browser.click": {
      const result = await evaluate(win, clickBody(String(step.selector), step.contains));
      if (!result.found) throw new Error(`click_not_found:${step.selector}`);
      await delay(Number(step.settle_ms ?? 500));
      return { op, ...result };
    }
    case "browser.type": {
      const result = await evaluate(win, focusBody(String(step.selector), step.contains));
      if (!result.found) throw new Error(`type_not_found:${step.selector}`);
      await delay(200);
      // insertText goes through the real input pipeline, so React/Vue state updates
      win.webContents.insertText(String(step.text ?? ""));
      await delay(200);
      return { op, chars: String(step.text ?? "").length };
    }
    case "browser.press": {
      const key = String(step.key || "Enter");
      win.webContents.sendInputEvent({ type: "keyDown", keyCode: key });
      win.webContents.sendInputEvent({ type: "keyUp", keyCode: key });
      return { op, key };
    }
    case "browser.extract": {
      const result = await evaluate(win, extractBody(String(step.selector), step.max_chars));
      return { op, ...result };
    }
    case "browser.wait":
      await delay(Math.min(Number(step.ms ?? 500), 30000));
      return { op, ms: step.ms };
    case "screenshot": {
      const shot = await screenshot(win);
      if (shot) artifacts.push(shot);
      return { op, captured: Boolean(shot) };
    }
    default:
      throw new Error(`unknown_op:${op}`);
  }
}

/**
 * Execute a recipe on the site's profile.
 * Returns `{ ok, output, artifacts }`; throws with `link.*` codes on failure.
 */
async function runSteps(provider, steps, { siteUrl, visible = false, timeoutMs = 90000 } = {}) {
  if (PAUSED.has(provider)) throw new Error("link.paused");
  if (!Array.isArray(steps) || steps.length === 0) throw new Error("link.no_steps");

  return withQueue(provider, async () => {
    const win = await ensureWindow(provider, siteUrl, { visible });
    const artifacts = [];
    const output = [];
    const started = Date.now();
    for (const [index, step] of steps.entries()) {
      if (Date.now() - started > timeoutMs) throw new Error(`link.timeout:step=${index}`);
      try {
        output.push(await runOp(win, step, artifacts));
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        const failure = new Error(message);
        failure.step = index;
        failure.op = step.op;
        failure.output = output;
        failure.artifacts = artifacts;
        throw failure;
      }
    }
    return { ok: true, output, artifacts };
  });
}


/** Open the site window so the customer can log in once (visible on purpose). */
async function openSite(provider, siteUrl) {
  PAUSED.delete(provider);
  return withQueue(provider, async () => {
    const win = await ensureWindow(provider, siteUrl, { visible: true });
    return { ok: true, window: provider, url: win.webContents.getURL() };
  });
}

/**
 * Is this profile still logged in? The answer is site specific: the provider
 * registry supplies the URL fragments that mean "logged out" and a selector
 * that only exists after login.
 */
async function probe(provider, { siteUrl, loginCheck = {}, screenshot: wantShot = true } = {}) {
  return withQueue(provider, async () => {
    const win = await ensureWindow(provider, siteUrl, { visible: false });
    await delay(1200);

    const url = win.webContents.getURL();
    const blocked = (loginCheck.url_not_contains || []).some((part) => url.includes(part));
    let selectorOk = true;
    if (loginCheck.selector) {
      selectorOk = await waitFor(win, {
        selector: String(loginCheck.selector),
        timeout: Number(loginCheck.timeout ?? 12000),
      });
    }

    let displayName = null;
    if (!blocked && selectorOk && loginCheck.name_js) {
      displayName = await evaluate(win, `return String(${loginCheck.name_js} || "");`).catch(
        () => null,
      );
    }
    if (!displayName) {
      displayName = await evaluate(win, "return document.title || null;").catch(() => null);
    }

    const loggedIn = !blocked && selectorOk;
    if (loggedIn) PAUSED.delete(provider);
    return {
      ok: true,
      logged_in: loggedIn,
      url,
      display_name: loggedIn && displayName ? String(displayName).slice(0, 120) : null,
      detail: loggedIn ? null : blocked ? "login_required" : "selector_missing",
      screenshot: wantShot ? await screenshot(win) : null,
    };
  });
}

/** Disconnect: close the window and forget every cookie of that site. */
async function wipe(provider) {
  PAUSED.delete(provider);
  const entry = SITES.get(provider);
  if (entry && !entry.win.isDestroyed()) entry.win.destroy();
  SITES.delete(provider);
  const partition = session.fromPartition(partitionFor(provider));
  await partition.clearStorageData();
  await partition.clearCache();
  return { ok: true, provider };
}

/** Emergency stop: refuse every further recipe until the next open/probe. */
function stop(provider) {
  PAUSED.add(provider);
  return { ok: true, provider, paused: true };
}

function status() {
  return Array.from(SITES.keys()).map((provider) => ({
    provider,
    paused: PAUSED.has(provider),
    url: SITES.get(provider)?.win.webContents.getURL() ?? null,
  }));
}

function closeAll() {
  for (const entry of SITES.values()) {
    if (!entry.win.isDestroyed()) entry.win.destroy();
  }
  SITES.clear();
}

module.exports = { runSteps, probe, openSite, wipe, stop, status, closeAll, partitionFor };

