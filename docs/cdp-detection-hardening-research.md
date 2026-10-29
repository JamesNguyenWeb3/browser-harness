# CDP detection hardening: what is actually verified

Research date: 2026-10-29. Sources were read from the live `main` branches of
Chromium, V8, the CDP spec, and the named projects. Branch contents move; no
commit SHAs are pinned here because the pages I opened did not expose a stable
one in the fetched text. Every claim below links the file/function it came
from. Claims I could not check are labelled explicitly.

Scope: this document evaluates `docs/make-agent-undetectable.md` against
primary sources, then evaluates the real surface in `src/browser_harness/`.

---

## TL;DR

The motivating document is **directionally right about the biggest leak and
wrong about its mechanism and certainty**.

- **Confirmed:** `Runtime.enable` makes Chrome serialize console arguments,
  and that serialization runs JavaScript in the page. For current Chrome the
  reliable trigger is the built-in `Error.stack` getter (which runs
  `Error.prepareStackTrace`) and a prototype-chain `name` getter, not a
  user-defined own-property getter on `stack`.
- **Confirmed:** this harness does send `Runtime.enable` (`daemon.py:563`), so
  the leak applies. It also does not consume any Runtime event, so the command
  is unnecessary.
- **Wrong / overstated:** "getter fires without DevTools open -> 100% certainty".
  Open DevTools, logging libraries, and extensions trigger the same probe
  (`rebrowser-bot-detector` says so in its own note). Chrome 136 and older ran
  a user `error.stack` getter; Chrome 137+ does not. It is a strong signal,
  not a proof.
- **Moot for this harness:** `navigator.webdriver` is set by launch switches.
  Attaching to a Chrome started on a specific `--remote-debugging-port` does
  **not** set it, by explicit Chromium design.
- **Real and under-discussed:** the harness injects a horse emoji into
  `document.title` on every attach and page load. That is a deterministic,
  page-readable automation marker.

Verdict summary on the motivating doc:

| Claim | Verdict |
| --- | --- |
| `Runtime.enable` causes console-argument serialization | Confirmed by V8 source |
| Serialization can run a getter | Confirmed, with caveats |
| Fires a custom own-property getter on `error.stack` | Outdated: Chrome 137+ no longer does this |
| "100% certainty a CDP driver is attached" | Overstated: DevTools/log libs/extensions produce the same signal |
| "Even with a real profile, `--remote-debugging-port` introduces three leak vectors" | Misleading: the port itself is not page-visible; enabled domains and injected scripts are |
| Attach-only avoids `navigator.webdriver` | Confirmed, and stronger than the doc says |
| `Input.insertText` and teleporting clicks are detectable | Mechanism confirmed; detection prevalence is community-sourced |
| Rebrowser/patchright "fix" = run scripts in isolated worlds | Half true: that is only Rebrowser's `alwaysIsolated` mode |
| browser-use Cloud runs custom-patched Chromium stripping serialization at C++ level | Unverified; no primary source found |

---

## 1. The `Runtime.enable` serialization leak

### What it is

`Runtime.enable` is defined as: "Enables reporting of execution contexts
creation by means of `executionContextCreated` event. When the reporting gets
enabled the event will be sent immediately for each existing execution
context."
([js_protocol.json, `Runtime.enable`](https://github.com/ChromeDevTools/devtools-protocol/blob/master/json/js_protocol.json)).
The protocol description does not mention console. The implementation does:

1. `V8RuntimeAgentImpl::enable()` sets `m_enabled` and ensures console message
   storage.
   ([v8-runtime-agent-impl.cc `enable`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/v8-runtime-agent-impl.cc))
2. Every `console.*` call goes through `V8ConsoleMessageStorage::addMessage`,
   which calls `session->runtimeAgent()->messageAdded(...)` for each session.
   ([v8-console-message.cc `addMessage`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/v8-console-message.cc))
3. `V8RuntimeAgentImpl::messageAdded` only acts when enabled, and calls
   `reportMessage(message, /*generatePreview=*/true)`.
   ([v8-runtime-agent-impl.cc `messageAdded`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/v8-runtime-agent-impl.cc))
4. `reportToFrontend` -> `wrapArguments(session, generatePreview)` ->
   `session->wrapObject(...)`. Its own comment states: "Wrapping the arguments
   can run JavaScript (i.e. getters while building previews or custom
   formatters), which might terminate execution."
   ([v8-console-message.cc `wrapArguments`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/v8-console-message.cc))
5. `InjectedScript::wrapObjectMirror` repeats the warning: "Building the remote
   object (i.e. the preview) can run JavaScript".
   ([injected-script.cc](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/injected-script.cc))
6. For an `Error`, `ValueMirror::create` -> `clientMirror` ->
   `descriptionForError`, which reads `name`, `stack`, and `message` through
   `getErrorProperty`.
   ([value-mirror.cc `clientMirror`, `descriptionForError`, `getErrorProperty`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/value-mirror.cc))
7. `getErrorProperty` invokes a getter only when it is a **built-in** getter.
   A user-defined own-property accessor is skipped. A property not present
   as an own property falls through to `object->Get(context, name)`, which
   walks the prototype chain and **does** run a user getter there.
   (same file, `getErrorProperty`)

`stack` is installed as a built-in accessor on errors, so reading it runs the
built-in stack getter, which runs `Error.prepareStackTrace`. That is the
current Chrome detection path.

The Rebrowser maintainers document the exact behaviour in
[`rebrowser-bot-detector/index.js`](https://github.com/rebrowser/rebrowser-bot-detector/blob/main/index.js):
"With Runtime.enable on, Chrome serializes every console argument for
Runtime.consoleAPICalled. Since Chrome 137 that no longer runs a user getter on
error.stack, but it still formats the stack (Error.prepareStackTrace runs) and
reads error.name an extra time." Their probe counts `prepareStackTrace`, an
overridden `name` getter on an Error subclass, and (on old Chrome/DevTools) a
`stack` getter.

### Does it apply to this harness?

Yes. `Daemon._enable_default_domains` sends `Page.enable`, `DOM.enable`,
`Runtime.enable`, and `Network.enable` on every attach and on every tab switch:

```python
# src/browser_harness/daemon.py:541-563
await asyncio.gather(*(enable_one(d) for d in ("Page", "DOM", "Runtime", "Network")))
```

`_enable_default_domains` is called from `attach_first_page` (both the named
and default paths) and from the `set_session` handler used by `switch_tab` /
`new_tab`
(`src/browser_harness/daemon.py:481, 522, 733`).

Nothing in the harness consumes a Runtime event. A grep for
`executionContextCreated`, `consoleAPICalled`, and `exceptionThrown` over
`src/browser_harness/*.py` returns no consumers. `Runtime` is enabled "because
the four domains are enabled together", not because it is needed.

Importantly, `Runtime.evaluate` does **not** require `Runtime.enable`.
`V8RuntimeAgentImpl::evaluate` has no `m_enabled` gate (unlike `compileScript`,
`runScript`, `setCustomObjectFormatterEnabled`, and others, which do).
([v8-runtime-agent-impl.cc `evaluate`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/v8-runtime-agent-impl.cc)).
The `nodriver` project does exactly this: it sends `Runtime.evaluate` without
ever enabling Runtime
([nodriver `tab.py`](https://github.com/ultrafunkamsterdam/nodriver/blob/main/nodriver/core/tab.py)).

### Confirmation: FPScanner's `hasCDP` is this exact leak

FPScanner (Antoine Vastel) reports a `hasCDP` flag, and its implementation is
the same probe described above, not transport detection. The detection is
`signals.automation.cdp === true`
([`src/detections/hasCDP.ts`](https://cdn.jsdelivr.net/npm/fpscanner@1.0.8/src/detections/hasCDP.ts));
the signal is collected in
[`src/signals/cdp.ts`](https://cdn.jsdelivr.net/npm/fpscanner@1.0.8/src/signals/cdp.ts),
which saves `Error.prepareStackTrace`, replaces it with a wrapper that sets a
`wasAccessed` flag, calls `console.log(new Error(''))`, and returns that flag.
It checks no globals, DOM properties, event properties, ports, or timing.

Measured on this checkout, against a live attached Chrome:

| State | `signals.automation.cdp` |
| --- | --- |
| Harness as-is (`Runtime.enable` sent) | `true` |
| After `Runtime.disable` on the same session | `false` |
| `js()` after `Runtime.disable` | works (returns `2`) |

So the `hasCDP` flag is fully explained by the `Runtime.enable` call at
`daemon.py:563`, and removing it clears the flag. This also resolves the
"could not verify" note below: at least one publicly available detector does
use this probe in production.

### Remediation, ranked

1. **Stop sending `Runtime.enable`** (lowest cost, highest value). Remove
   `"Runtime"` from the tuple at `daemon.py:563`. Keep `Page` (dialogs/load
   events), `Network` (`wait_for_network_idle`), and `DOM` (only if any DOM
   event consumer exists). This removes the console-serialization path
   entirely, because `messageAdded` is gated on `m_enabled`.
   Risk: low. Verify with a page that defines
   `Error.prepareStackTrace` and logs an Error (see the Rebrowser detector).
2. **If Runtime events are ever needed, use `Runtime.enable` lazily and
   `Runtime.disable` immediately** after capturing the context ID. Rebrowser
   labels this mode "not fully leak-free" and does not recommend it
   ([rebrowser-patches README](https://github.com/rebrowser/rebrowser-patches)).
   Do not do this for a permanent connection.
3. **Move JS to an isolated world** (`Page.createIsolatedWorld` +
   `Runtime.evaluate(contextId)`). This does not fix the leak by itself; it
   only keeps injected scripts out of the main world. See section 5 for its
   real limits.

### Secondary getter exposure: `returnByValue`

`_runtime_evaluate` always passes `returnByValue=True`
(`src/browser_harness/helpers.py:137`). For an object result, CDP converts it
with `objectToProtocolValueImpl`, which calls `object->Get(context, name)` on
each own property name, invoking own-property getters.
([value-mirror.cc `objectToProtocolValueImpl`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/value-mirror.cc)).
This is not gated on `Runtime.enable`. It is a much narrower trap because the
page does not choose what the agent evaluates, but it means "drop
`Runtime.enable`" removes the reliable console trap, not every getter path. The
harness's own helpers mostly evaluate primitives (`page_info`, `readyState`,
title), so exposure is small.

---

## 2. Automation flags and `navigator.webdriver`

### What it is

`navigator.webdriver` "Returns true if webdriver-active flag is set, false
otherwise" ([W3C WebDriver, `NavigatorAutomationInformation`](https://w3c.github.io/webdriver/#interface)).
Blink implements it as:

```cpp
bool Navigator::webdriver() const {
  if (RuntimeEnabledFeatures::AutomationControlledEnabled()) return true;
  bool automation_enabled = false;
  probe::ApplyAutomationOverride(GetExecutionContext(), automation_enabled);
  return automation_enabled;
}
```

([navigator.cc](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/core/frame/navigator.cc)).

`AutomationControlled` is enabled from command-line switches in
`content/child/runtime_features.cc`:

```cpp
{wrf::EnableAutomationControlled, switches::kEnableAutomation, true},
{wrf::EnableAutomationControlled, switches::kHeadless, true},
{wrf::EnableAutomationControlled, switches::kRemoteDebuggingPipe, true},
```

and, critically, the same file contains this comment and code:

> Set EnableAutomationControlled if the caller passes `--remote-debugging-port=0`
> ... If the caller provides a specific port number, this is more likely for
> attaching a debugger, so we should leave EnableAutomationControlled unset to
> ensure the browser behaves as it does when not under automation control.

([runtime_features.cc](https://chromium.googlesource.com/chromium/src/+/main/content/child/runtime_features.cc)).

`--disable-blink-features=AutomationControlled` genuinely turns the runtime
feature off by name, overriding the switch
([runtime_features.cc `kDisableBlinkFeatures` handling](https://chromium.googlesource.com/chromium/src/+/main/content/child/runtime_features.cc)).

The other way to set it at runtime is CDP `Emulation.setAutomationOverride`,
which sets `navigator.webdriver = true`
([inspector_emulation_agent.cc](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/core/inspector/inspector_emulation_agent.cc)).

### Does it apply to this harness?

**No, not in the default path.** The harness attaches to a running browser. It
never passes `--enable-automation`, `--headless`, `--remote-debugging-pipe`, or
`--remote-debugging-port=0`. When Chrome is closed, `_launch_browser` opens it
the normal way (`open -a`, `start`, or the user's binary) with no automation
switches (`src/browser_harness/admin.py:1274-1343`). The connection is made to
the specific port in `DevToolsActivePort` (`src/browser_harness/daemon.py:243-260`).
By the Chromium comment above, that is the "attaching a debugger" case and
`navigator.webdriver` stays false.

The reasoning in the motivating doc ("launch manually with
`--disable-blink-features=AutomationControlled` then attach") is therefore not
needed for this harness, and it cannot be applied to a running browser anyway.
It is a launch-time switch.

Caveats:
- If the user's Chrome was previously launched by another automation stack
  with `--enable-automation` or a pipe, the flag is already set; the harness
  inherits it and cannot fix it without a restart.
- If the harness ever adds a "launch a dedicated automation browser" mode, it
  must use `--remote-debugging-port=0` **and**
  `--disable-blink-features=AutomationControlled`, or `navigator.webdriver`
  will be true.
- `--headless` also sets it. The harness's cloud mode is out of scope here.

### Remediation

None required for local attach-only use. Do not add launch flags to the user's
normal Chrome shortcut; they do nothing for a running instance.

---

## 3. Synthetic input and behavioral telemetry

### What the harness does

`click_at_xy` sends exactly two events, at the target coordinates, with no
prior movement:

```python
# src/browser_harness/helpers.py:193-194
cdp("Input.dispatchMouseEvent", type="mousePressed",  x=x, y=y, button=button, clickCount=clicks)
cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button=button, clickCount=clicks)
```

`type_text` uses IME-style insertion:

```python
# src/browser_harness/helpers.py:196-197
cdp("Input.insertText", text=text)
```

SKILL.md directs agents to click the accessibility-tree box centre
(`SKILL.md:185-186`), so every click lands on the exact centre.

### Verified mechanics

- **No movement events.** `Input.dispatchMouseEvent` accepts
  `mousePressed | mouseReleased | mouseMoved | mouseWheel`
  ([browser_protocol.json `Input.dispatchMouseEvent`](https://github.com/ChromeDevTools/devtools-protocol/blob/master/json/browser_protocol.json)).
  The harness only ever sends pressed/released. The press handler updates
  hover/active state (`HandleMousePressEventUpdateStates`, which dispatches
  `mouseover`/`mouseenter`/`pointerover`) but I found no path that synthesizes
  move events, so `mousemove` / `pointermove` do not occur before the click
  ([event_handler.cc](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/core/input/event_handler.cc)).
  A page reading `onmousemove` sees zero movement.
- **`mousedown.buttons` is 0.** CDP's `buttons` parameter is only used to add
  `kLeftButtonDown`-style modifier bits
  ([input_handler.cc `GetEventModifiers`](https://chromium.googlesource.com/chromium/src/+/main/content/browser/devtools/protocol/input_handler.cc)).
  DOM `MouseEvent.buttons` is derived from those modifier bits, not from the
  `button` field:
  `initializer->setButtons(MouseEvent::WebInputEventModifiersToButtons(mouse_event.GetModifiers()))`
  ([mouse_event_manager.cc](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/core/input/mouse_event_manager.cc)).
  The harness omits `buttons`, so a real `mousedown` reports `buttons === 0`
  where a physical click reports `1`. This is a one-line page check and a
  concrete defect.
- **Trust.** Events created by the browser input pipeline are `isTrusted =
  true`; events made with `new Event(...)` and `dispatchEvent` are `false`
  ([DOM spec, `isTrusted`](https://dom.spec.whatwg.org/#dom-event-istrusted)).
  CDP mouse/key events are forwarded through the normal renderer input path
  (`widget_host_->ForwardMouseEvent`, `ForwardKeyboardEventWithCommands` in
  `input_handler.cc`), so they are trusted. The JS-dispatched events in
  `fill_input` and `dispatch_key` are not.
- **`Input.insertText` is an IME commit, not typing.** It calls
  `GetWidgetInputHandler()->ImeCommitText(...)`
  ([input_handler.cc `InsertText`](https://chromium.googlesource.com/chromium/src/+/main/content/browser/devtools/protocol/input_handler.cc)).
  It produces no `keydown`, `keypress`, or `keyup`. The CDP description says
  it "emulates inserting text that doesn't come from a key press"
  ([browser_protocol.json](https://github.com/ChromeDevTools/devtools-protocol/blob/master/json/browser_protocol.json)).
- **Multi-click.** For `clicks=3` the harness sends one press/release pair with
  `clickCount=3`, not three pairs with counts 1, 2, 3. A page listening to
  `mousedown`/`click` sees one event with `detail=3`.
- **Wheel.** One `mouseWheel` event with no preceding move and no follow-up
  phases; CDP sets `phase = kPhaseBegan`
  ([input_handler.cc](https://chromium.googlesource.com/chromium/src/+/main/content/browser/devtools/protocol/input_handler.cc)).

### Does it apply?

Yes. This harness always teleports and always uses `insertText` for
`type_text`. `fill_input` already types per character with real key events
(`helpers.py:240-241`) but with no delay, then adds untrusted `input`/`change`
events (`helpers.py:242-247`).

The **presence** of behavioral scoring is not publicly documented at the probe
level. Cloudflare's public bot-score page describes "browser signals", "session
characteristics", and a "lightweight, invisible JavaScript injection" but lists
no specific API or timing probe
([Cloudflare bot score docs](https://developers.cloudflare.com/bots/concepts/bot-score/)).
Treat "behavioral models flag this" as community-reported and vendor-implied,
not verified per-site. The mechanics above are verified regardless: any site
that chooses to look can see them.

### Remediation, ranked

1. **Set `buttons` correctly** in `click_at_xy` (`buttons=1` on press,
   `buttons=0` on release). Nearly free, removes a trivial inconsistency.
2. **Dispatch `mouseMoved` events before the press.** A jittered straight line
   is enough to remove "zero movement"; a Bezier path is better. Track the last
   cursor position in a module global so successive clicks move from where the
   previous one ended. `ghost-cursor` is a reference implementation: Bezier
   curves plus Fitts's-law timing, returning timed path vectors
   ([ghost-cursor README](https://github.com/Xetera/ghost-cursor/blob/master/README.md),
   [`src/math.ts`](https://github.com/Xetera/ghost-cursor/blob/master/src/math.ts)).
   Cost: a few dozen lines and 100-400 ms per click. Risk: hover menus and
   drag-sensitive UIs may react.
3. **Randomize the click point inside the element**, not at the exact centre.
   This belongs in the caller (SKILL.md tells agents to use the box centre) or
   as an optional `jitter` argument to `click_at_xy`.
4. **Expand `clicks>1` into `n` press/release pairs** with `clickCount=1..n`,
   matching a physical double/triple click.
5. **Replace `type_text` with per-character `press_key` plus randomized
   inter-key delay** for sensitive fields. Keep `insertText` as an explicit
   fast path for non-sensitive bulk text. The 40-130 ms range in the motivating
   doc has no primary source; it is a heuristic.
6. **Drop the synthetic `input`/`change` re-dispatch in `fill_input`**
   (`helpers.py:242-247`). Real key events already fire native `input`; the
   extra events are `isTrusted=false` and are a detectable signature. If a
   framework truly needs `change`, make it an explicit opt-in.
7. **Add a small randomized delay between actions** at the helper level rather
   than relying on LLM latency. Lower priority; the agent's own latency is
   already non-mechanical.

---

## 4. Other vectors found in this harness

### 4.1 The tab-title horse emoji (deterministic, page-readable)

`daemon.py:130` defines:

```python
TAB_MARKER_JS = "if(!document.title.startsWith('\U0001F434'))document.title='\U0001F434 '+document.title"
```

It is enabled by default (`tab_marker_enabled()`, `daemon.py:133-135`) and runs
on attach, on `switch_tab` (`helpers.py:388-393, 409-427`), and after
`Page.loadEventFired` / `domContentEventFired` (`daemon.py:613-624,
626-633`). Any page script can read `document.title`, see a horse emoji it did
not set, and know a specific agent harness is attached. This is far more
deterministic than any behavioral heuristic and is unique to this codebase.

Remediation: default it off, or keep it only as an explicit opt-in
(`BH_TAB_MARKER=1`). The cost is losing the user-visible "this tab is
controlled" affordance.

### 4.2 Main-world execution and monkey-patch detection

`js()` evaluates with no `contextId`, which means "the context of the
inspected page", i.e. the main world
([js_protocol.json `Runtime.evaluate`](https://github.com/ChromeDevTools/devtools-protocol/blob/master/json/js_protocol.json)).
Page code can replace `document.querySelector`,
`document.getElementsByClassName`, `Document.prototype.readyState`, etc., and
observe calls. Rebrowser's `mainWorldExecution` probe does exactly this and
notes that an isolated world does not hit the page's patched wrapper
([rebrowser-bot-detector](https://github.com/rebrowser/rebrowser-bot-detector/blob/main/index.js)).

This is inherent to reading the page from the main world. It is a weak signal
because frameworks call these APIs too, and the harness's own reads are
low-volume. Remediation is high cost (rewrite helpers to run in an isolated
world) for modest benefit; do not do it just for this.

### 4.3 Isolated-world artifacts and limits

`Page.createIsolatedWorld` "Creates an isolated world for the given frame" and
returns an execution context ID; `worldName` is only reported in the execution
context, and `grantUniveralAccess` is flagged as powerful and dangerous
([browser_protocol.json `Page.createIsolatedWorld`](https://github.com/ChromeDevTools/devtools-protocol/blob/master/json/browser_protocol.json)).
Blink models a world as "a collection of DOM wrappers for a specific world",
with its own `DOMDataStore`
([dom_wrapper_world.h](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/platform/bindings/dom_wrapper_world.h)).

Limits that matter when evaluating the motivating doc's advice:
- It hides the **JS globals and wrappers** of the isolated world from page
  scripts. It does not hide **DOM mutations, network requests, timers, or
  user-visible effects**; those are shared page state. Inference from the
  shared-DOM design; also consistent with Rebrowser's "Page scripts cannot
  observe execution there" while still requiring a world lookup to reach main
  world nodes
  ([rebrowser-patches README](https://github.com/rebrowser/rebrowser-patches)).
- It loses main-world variables: Rebrowser's `alwaysIsolated` mode "costs
  main-world access, `page.exposeFunction()` and Puppeteer web workers".
- Creating the world is not itself page-observable; the CDP session is
  browser-side. I found no primary source showing a page-JS-visible signal
  from `Page.createIsolatedWorld` alone.

So "use `Page.createIsolatedWorld` to fix `Runtime.enable`" is imprecise. The
actual fix for the leak is to **not enable Runtime**; isolated worlds are a
separate decision about where injected code runs.

### 4.4 CDP handshake artifacts (`Target.attachToTarget`, `setAutoAttach`)

The harness attaches with `Target.attachToTarget(flatten=True)` and never calls
`Target.setAutoAttach`
([browser_protocol.json `Target`](https://github.com/ChromeDevTools/devtools-protocol/blob/master/json/browser_protocol.json)).
`setAutoAttach` is the command that can pause new targets
(`waitForDebuggerOnStart`) and is the one with visible timing consequences.
The harness's handshake is browser-side and I found no primary source showing
that the page can detect it. Treat "CDP attach itself is detectable" as
unverified; the documented page-visible leaks come from enabled domains and
injected scripts, not the transport.

### 4.5 Script-origin leaks (not applicable, but worth keeping)

Playwright/Puppeteer leak library identity through `//# sourceURL=pptr:...`
and a `UtilityScript` class, and `Runtime.addBinding` can leave globals
([rebrowser-patches README](https://github.com/rebrowser/rebrowser-patches),
[rebrowser-bot-detector](https://github.com/rebrowser/rebrowser-bot-detector/blob/main/index.js)).
This harness injects no library scripts, uses no `addBinding`, and evaluates
anonymous expressions, so these do not apply. Keep it that way: any future
`Page.addScriptToEvaluateOnNewDocument` or `Runtime.addBinding` reintroduces
them.

### 4.6 Auxiliary things checked and found clean

- No `--enable-automation`, `--headless`, or `--remote-debugging-pipe`
  anywhere in `src/` (grep).
- No `Runtime.addBinding`, `Page.addScriptToEvaluateOnNewDocument`,
  `Target.setAutoAttach`, `Log.enable`, or `Console.enable`.
- `Browser.getVersion` is used only to pick the select-all modifier; it has no
  page-side effect.
- Cookies, WebGL, Canvas, AudioContext, and TLS are the user's real browser
  state because the harness attaches rather than launches. This part of the
  motivating doc is correct in principle.

---

## 5. Recommended concrete changes to browser-harness

Ordered by value per unit of risk. Line numbers are as of this checkout.

1. **`src/browser_harness/daemon.py:563` - remove `"Runtime"` from the enable
   tuple.**
   Nothing consumes Runtime events. `Runtime.evaluate` works without it. This
   is the single highest-impact change and the smallest diff.
   Suggested: `for d in ("Page", "DOM", "Network")`, with a comment explaining
   that `Runtime.enable` exposes console serialization to pages and is not
   needed for evaluate. `DOM.enable` is also removable if desired:
   `DOM.getDocument` auto-enables the DOM agent ("Backward compatibility. Mark
   agent as enabled when it requests document",
   [`inspector_dom_agent.cc`](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/core/inspector/inspector_dom_agent.cc)),
   and nothing consumes DOM events. Keep `Page` for dialog handling and
   `Network` for `wait_for_network_idle`. Verify with a page that counts
   `Error.prepareStackTrace` calls around `console.debug(new Error())`.

2. **`src/browser_harness/daemon.py:130-135` and `helpers.py:388-393,
   409-427` - turn the horse-emoji title marker off by default.**
   Make `BH_TAB_MARKER=1` the opt-in. This removes a deterministic,
   page-readable marker. Only cost is the human affordance.

3. **`src/browser_harness/helpers.py:174-194` - fix mouse synthesis.**
   **Implementation note (verified live):** `Input.dispatchMouseEvent` with
   `type: "mouseMoved"` never returns on a hidden tab — it hangs until the IPC
   timeout, while `mousePressed`, `mouseReleased` and `mouseWheel` return on
   activation only (`mouseWheel` also hangs when hidden, which is pre-existing
   behaviour in `scroll()`). So movement is only safe when
   `document.visibilityState === "visible"`; activating the tab to enable it
   would steal focus, which the harness forbids. Gate the movement on
   visibility and fall back to a direct press.
   Track the last cursor position, send 8-20 `mouseMoved` events along a
   slightly jittered path to the target, then press with `buttons=1` and
   release with `buttons=0`. For `clicks > 1`, send `clicks` pairs with
   `clickCount=1..clicks`. Optional: jitter the final point by a few pixels
   inside the element box. This fixes two verified inconsistencies
   (`mousedown.buttons === 0`, no trajectory) at moderate cost.

4. **`src/browser_harness/helpers.py:196-197 and 240-247` - typing.**
   Add an optional `typing_delay` to `fill_input` (randomized per character),
   and make `type_text` choose `press_key` per character when `typing_delay`
   is set, otherwise keep `insertText`. Remove the synthetic `input`/`change`
   dispatch (or make it opt-in), since it produces `isTrusted=false` events on
   top of the real keystrokes.
   Note the existing `fill_input` docstring already says `insertText` bypasses
   framework listeners; switching sensitive fills to `press_key` improves both
   correctness and stealth.

5. **`src/browser_harness/helpers.py:610-619` (`dispatch_key`) - document it as
   detectable.** It dispatches `new KeyboardEvent(...)` from JS, so
   `isTrusted` is false. Keep it as a compatibility fallback, but the docstring
   should say so and callers should prefer `press_key`.

### What is not worth doing

- **Launch flags / `navigator.webdriver`.** Attach-only on a specific port
  already leaves `webdriver` false by Chromium's explicit design. Do not add
  `--disable-blink-features=AutomationControlled` to the user's browser; it is
  a launch-time switch and has no effect on an attached instance.
- **Rewriting `js()` into an isolated world.** It would break `page_info`,
  element lookups, and any helper that needs main-world state, for little gain
  once `Runtime.enable` is removed. Keep isolated worlds for future *injected*
  scripts, not for the harness's read path.
- **The `Runtime.enable` + `Runtime.disable` trick.** Rebrowser calls it "not
  fully leak-free" and does not recommend it. Removing the enable call is
  simpler and strictly better.
- **Patching Chromium or shipping custom V8 builds** (the browser-use Cloud
  claim). No primary source supports the specific claim, and it is out of
  scope for a thin attach-only harness.
- **Spoofing canvas/WebGL/audio.** The harness uses the user's real browser;
  there is a real fingerprint to inherit and nothing to spoof.
- **Precise behavioral timing tuned to a specific vendor.** No public
  documentation exposes thresholds. Jitter and correct event fields are
  defensible; mimicking a specific model is guesswork.

---

## Implementation status (2026-10-29)

Shipped in this checkout, each verified against a live attached Chrome:

| Change | Verified result |
| --- | --- |
| `Runtime.enable` removed (`daemon.py`) | FPScanner `hasCDP` probe returns `false`; `js()` still works |
| Tab-title marker opt-in (`BH_TAB_MARKER=1`) | `document.title === ""` after attach |
| `DOM.enable` dropped | `upload_file`/`DOM.getDocument` still work (auto-enables) |
| Clicks: `buttons`, movement, multi-click, dwell | trusted `mousedown.buttons === 1`; double-click yields `detail` 1 then 2 |
| `fill_input`: real keys + ~50 ms gap, synthetic `input` removed | React 18 controlled input updates; native `input` events are `isTrusted: true` |
| `scroll(..., steps=n)`, `click_at_xy(..., jitter=n, move=False)` | opt-in; defaults unchanged |

Trade-offs kept deliberately: a synthetic `change` still follows typing
(`fire_change=False` to drop it) because a real change fires only on blur and an
agent usually submits without blurring; and movement costs one CDP round trip
per step, so remote/cloud deployments should pass `move=False` or set
`BH_CLICK_MOVES=0`.

### Focus emulation removes the occlusion constraint

Section 3's implementation note above said movement was impossible on a hidden
tab. That is only true without `Emulation.setFocusEmulationEnabled`. Measured
on a background tab:

| | before | after `setFocusEmulationEnabled(true)` |
| --- | --- | --- |
| `document.visibilityState` | `hidden` | `visible` |
| `document.hasFocus()` | `false` | `true` |
| `mouseMoved` | times out | returns |
| `mouseWheel` | times out | returns |

The daemon now sends it once per session at attach. Notes from measurement:
it is **per-session** (state reverts on detach, so no cleanup on tab switch),
and enabling it fires one `visibilitychange` plus `focus` on the page — which
is exactly the event pair a real tab switch produces, so it reads as a user
switching tabs. The cost is that the controlled tab stops being throttled in
the background. `BH_FOCUS_EMULATION=0` opts out, and movement then falls back
to the visibility gate described in section 3.

### Correction to "wheel phases"

CDP's `Input.dispatchMouseEvent` has no `phase` parameter (the earlier note
about `kPhaseBegan` describes an internal default, not something a client can
set). A trackpad-like gesture is approximated by `scroll(..., steps=n)`, which
sends `n` smaller wheel events.

## Sources

Primary:

- CDP spec, Runtime domain:
  https://github.com/ChromeDevTools/devtools-protocol/blob/master/json/js_protocol.json
- CDP spec, Page/Input/Target domains:
  https://github.com/ChromeDevTools/devtools-protocol/blob/master/json/browser_protocol.json
- V8 inspector:
  [`v8-runtime-agent-impl.cc`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/v8-runtime-agent-impl.cc),
  [`v8-console-message.cc`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/v8-console-message.cc),
  [`injected-script.cc`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/injected-script.cc),
  [`value-mirror.cc`](https://chromium.googlesource.com/v8/v8/+/main/src/inspector/value-mirror.cc)
- Chromium:
  [`content/child/runtime_features.cc`](https://chromium.googlesource.com/chromium/src/+/main/content/child/runtime_features.cc),
  [`navigator.cc`](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/core/frame/navigator.cc),
  [`input_handler.cc`](https://chromium.googlesource.com/chromium/src/+/main/content/browser/devtools/protocol/input_handler.cc),
  [`mouse_event_manager.cc`](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/core/input/mouse_event_manager.cc),
  [`dom_wrapper_world.h`](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/platform/bindings/dom_wrapper_world.h),
  [`inspector_emulation_agent.cc`](https://chromium.googlesource.com/chromium/src/+/main/third_party/blink/renderer/core/inspector/inspector_emulation_agent.cc)
- W3C WebDriver, `NavigatorAutomationInformation`:
  https://w3c.github.io/webdriver/#interface
- WHATWG DOM, `isTrusted`: https://dom.spec.whatwg.org/#dom-event-istrusted

Project sources (used for mechanism/limits, not as neutral documentation):

- rebrowser-patches README: https://github.com/rebrowser/rebrowser-patches
- rebrowser-bot-detector: https://github.com/rebrowser/rebrowser-bot-detector/blob/main/index.js
- patchright README: https://github.com/Kaliiiiiiiiii-Vinyzu/patchright/blob/main/README.md
- nodriver: https://github.com/ultrafunkamsterdam/nodriver
- ghost-cursor: https://github.com/Xetera/ghost-cursor

Vendor docs consulted (do not enumerate probes):

- Cloudflare bot score: https://developers.cloudflare.com/bots/concepts/bot-score/

Could not verify:

- browser-use Cloud running custom-patched Chromium that strips CDP
  serialization at the V8/Blink source level. No public primary source found.
- The claim that a getter trap is used by Cloudflare, DataDome, or Akamai in
  production. Their public docs do not describe the probe. (**Update, same
  day:** FPScanner ships this exact probe as `hasCDP` with public source, and
  it fires against this harness — see section 1. So the technique is in
  production use by at least one detector, though still not documented by the
  major WAF vendors.)
- Any JS-observable page signal from `Target.attachToTarget` or
  `Target.setAutoAttach` themselves.
- The specific 40-130 ms typing cadence and "inner 60%" click box as values
  that evade any particular vendor.
