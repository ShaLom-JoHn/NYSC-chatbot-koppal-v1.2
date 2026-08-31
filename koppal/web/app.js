/* ============================================================================
   koppal -- app.js   ·   rebuilt against docs/KOPPAL_MASTER_SPEC.md A11
   Talks to koppal_api.py through JSON only; the API owns every engine convention.
   Kept 7-bit clean: every user-visible glyph is a \uXXXX escape, so no server or
   editor can mis-decode this file.
   ============================================================================ */
(function () {
  "use strict";

  var REDUCE = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var $ = function (id) { return document.getElementById(id); };

  var G = {
    dot: "·", next: "›", prev: "‹",
    up: "⌃", close: "✕", minus: "–",
    quote: "“ ", unquote: " ”"
  };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function clear(n) { while (n && n.firstChild) n.removeChild(n.firstChild); }
  function on(n, ev, fn) { if (n) n.addEventListener(ev, fn); }

  var SID = (function () {
    var k = "koppal-session", v = null;
    try { v = localStorage.getItem(k); } catch (e) {}
    if (!v) {
      v = (window.crypto && crypto.randomUUID) ? crypto.randomUUID()
        : "s-" + Date.now() + "-" + Math.random().toString(16).slice(2);
      try { localStorage.setItem(k, v); } catch (e) {}
    }
    return v;
  })();

  async function api(path, opts) {
    opts = opts || {};
    var o = { headers: {} };
    if (opts.method) o.method = opts.method;
    if (opts.signal) o.signal = opts.signal;
    if (opts.body) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(opts.body); }
    var res = await fetch(path, o);
    if (!res.ok) throw new Error(path + " -> " + res.status);
    return res.json();
  }
  /* baked, not random: the board keeps the same hand-piled look on every load (A11.20) */
  var TILT = [-3.0, 2.4, -1.8, 3.2, -2.6];
  var SPINE_TILT = [-1.2, 0.9, -1.5, 1.3, -0.7];
  var SPINE_OFF = [0, 13, 5, 18, 8];
  var EDGE = [212, 158, 244, 128, 196];

  /* ---------- KB text -> DOM (lists + mono for naira amounts and codes) ----------
     Built as nodes, never innerHTML: KB text is data, not markup. */
  var MONO = /(₦\s?[\d,]+(?:\.\d+)?|\b[A-Z]{2,}(?:\/[A-Z0-9.\-]+)+\b|\bNYSC\b|\bPPA\b|\bLGI\b|\bCDS\b|\bSAED\b|\bNERD\b)/g;

  function inline(target, text) {
    var parts = String(text).split(MONO);
    for (var i = 0; i < parts.length; i++) {
      if (!parts[i]) continue;
      if (i % 2) target.appendChild(el("span", "mono", parts[i]));
      else target.appendChild(document.createTextNode(parts[i]));
    }
    return target;
  }

  /* A list item may lead with a short "Label: detail". Render that label in the
     accent so a long enumeration scans instead of reading as a wall of near-identical
     lines. Author-controlled: only fires on a <=40-char colon-led item, so an ordinary
     prose colon is left alone. */
  function listItem(text) {
    var li = el("li"), m = text.match(/^([^:\n]{1,40}):\s+(.+)$/);
    if (m) {
      li.appendChild(el("span", "plabel", m[1]));
      li.appendChild(document.createTextNode(": "));
      inline(li, m[2]);
    } else {
      inline(li, text);
    }
    return li;
  }

  function structure(box, text) {
    var list = null, para = null;
    String(text || "").split("\n").forEach(function (raw) {
      var line = raw.trim();
      if (!line) { list = null; para = null; return; }
      var ol = line.match(/^(\d+)[.)]\s+(.*)$/);
      var ul = line.match(/^[-*•]\s+(.*)$/);
      if (ol || ul) {
        para = null;
        var want = ol ? "ol" : "ul";
        if (!list || list.tagName.toLowerCase() !== want) { list = el(want); box.appendChild(list); }
        list.appendChild(listItem(ol ? ol[2] : ul[1]));
        return;
      }
      list = null;
      if (para) { para.appendChild(document.createTextNode(" ")); inline(para, line); }
      else { para = inline(el("p"), line); box.appendChild(para); }
    });
    return box;
  }

  /* ---------- state ---------- */
  var SCREEN = null;      /* null until something opens a screen — boot's restore relies on it */
  var MILESTONES = null, PLACEHOLDERS = [];
  var thread = $("thread"), menu = $("menu"), scroller = $("scroll");
  var composer = $("composer"), input = $("input");
  var chipRow = null, inFlight = null;
  var THREAD_LOG = [], threadBuilt = false;   /* the chat, persisted so a reload restores it */

  async function milestones() {
    if (!MILESTONES) MILESTONES = await api("/api/milestones");
    return MILESTONES;
  }

  /* ============================================================================
     NAVIGATION -- the browser's own history is the single source of truth.
     Every addressable place (the three screens + Browse's shelf/book/topic depth) is a
     STATE object. commit() RENDERS it and RECORDS it in history, so the device Back button
     and the phone's back-swipe walk the real path the person took instead of dropping out
     of the whole app. This is entirely in the browser -- no server, no backend, no cost.
     Deliberately OUT of history: the menu and modals (they already close on tap-outside /
     the close button) and in-view toggles (a branch card, the full-answer prose, the scroll
     cue) -- Back must never mean "un-expand a card".
     ============================================================================ */
  function slug(s) {
    return String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }
  function screenState(name) {
    return name === "browse" ? { screen: "browse", view: "shelf" } : { screen: name };
  }
  function hashFor(s) {
    if (s.screen === "browse") {
      if (s.view === "topic")
        return "#browse/" + encodeURIComponent(s.milestone) + "/" + encodeURIComponent(s.intent)
          + (s.full ? "?full" : "");
      if (s.view === "book") return "#browse/" + encodeURIComponent(s.milestone);
      return "#browse";
    }
    return "#" + s.screen;
  }
  function stateFromHash() {
    var h = (location.hash || "").replace(/^#/, "");
    if (!h) return null;
    var full = false, qi = h.indexOf("?");
    if (qi >= 0) { full = /(^|&)full(=|&|$)/.test(h.slice(qi + 1)); h = h.slice(0, qi); }
    var p = h.split("/").filter(Boolean).map(decodeURIComponent);
    if (p[0] === "home") return { screen: "home" };
    if (p[0] === "chat") return { screen: "chat" };
    if (p[0] === "browse") {
      if (p.length >= 3) return { screen: "browse", view: "topic", milestone: p[1], intent: p[2], full: full };
      if (p.length === 2) return { screen: "browse", view: "book", milestone: p[1] };
      return { screen: "browse", view: "shelf" };
    }
    return null;
  }

  /* resolve a hash's slug + intent back to the milestone/topic objects the renderers need */
  async function openBookFor(mslug) {
    var ms = await milestones();
    var m = null;
    ms.forEach(function (x) { if (slug(x.milestone) === mslug) m = x; });
    if (!m) return renderShelf();
    openBook(m);
  }
  async function openTopicFor(mslug, intent, full) {
    var ms = await milestones();
    var m = null, t = null;
    ms.forEach(function (x) { if (slug(x.milestone) === mslug) m = x; });
    if (m) m.topics.forEach(function (x) { if (x.intent === intent) t = x; });
    if (!t) return m ? openBook(m) : renderShelf();
    openTopic(t, m, full);
  }

  /* the ONE renderer: state -> DOM. It never touches history itself. */
  function renderState(s) {
    if (!s) s = { screen: "home" };
    PENDING_SCROLL = 0;                  /* never let one screen's offset leak into another */
    if (s.screen === "browse") {
      takeScroll(s);
      setScreen("browse");
      if (s.view === "topic") openTopicFor(s.milestone, s.intent, s.full);
      else if (s.view === "book") openBookFor(s.milestone);
      else renderShelf();
    } else if (s.screen === "chat") {
      setScreen("chat");                           // make the screen visible first...
      ensureThreadBuilt();                         // ...so a restored thread measures correctly
      emptyState(!thread.firstChild);
    } else {
      setScreen("home");
    }
  }

  /* render + record. A new history entry is pushed ONLY when the address actually changes;
     a second chat message keeps the same #chat entry (replace), so Back is never spammed
     with one entry per message. */
  var curKey = null;
  function commit(state, opts) {
    opts = opts || {};
    keepScroll();
    renderState(state);
    var key = hashFor(state);
    if (opts.replace || key === curKey) history.replaceState(state, "", key);
    else history.pushState(state, "", key);
    curKey = key;
  }

  /* Home is the root of every path. On a reload or a shared deep link we SEED the ancestor
     entries (without rendering them) so both the device Back and the in-page back arrow walk
     up cleanly -- shelf, then book, then topic -- instead of falling out of the app. */
  function ancestors(state) {
    if (state.screen === "home") return [{ screen: "home" }];
    var chain = [{ screen: "home" }];
    if (state.screen === "chat") { chain.push({ screen: "chat" }); return chain; }
    chain.push({ screen: "browse", view: "shelf" });
    if (state.view === "book" || state.view === "topic")
      chain.push({ screen: "browse", view: "book", milestone: state.milestone });
    if (state.view === "topic")
      chain.push({ screen: "browse", view: "topic", milestone: state.milestone, intent: state.intent, full: state.full });
    return chain;
  }
  function seedHistory(chain) {
    chain.forEach(function (s, i) {
      var key = hashFor(s);
      if (i === 0) history.replaceState(s, "", key);
      else history.pushState(s, "", key);
      curKey = key;
    });
    renderState(chain[chain.length - 1]);   // render only the destination, not the ancestors
  }

  /* device Back / Forward and the phone back-swipe all arrive here: render the entry the
     browser moved to, and DO NOT push -- the browser already moved the history pointer. */
  /* Scroll memory. Browse re-renders every view from scratch, so walking back up landed you at
     the top of a 44-topic contents page and lost your place. Each address remembers where it was
     scrolled to; the page we are LEAVING is measured before the new one renders (the old DOM and
     the old key are both still current at that moment), and the incoming view applies its own
     saved offset once it has built. */
  var SCROLLPOS = {}, PENDING_SCROLL = 0;
  function keepScroll() { if (curKey) SCROLLPOS[curKey] = scroller.scrollTop; }
  function takeScroll(s) { PENDING_SCROLL = SCROLLPOS[hashFor(s)] || 0; }
  function applyScroll() {
    var y = PENDING_SCROLL;
    PENDING_SCROLL = 0;
    /* after layout, or a tall page has not been measured yet and the offset clamps to 0 */
    requestAnimationFrame(function () { scroller.scrollTop = y; });
  }

  on(window, "popstate", function (e) {
    var s = e.state || stateFromHash() || { screen: "home" };
    keepScroll();
    renderState(s);
    curKey = hashFor(s);
  });

  /* ---------- screens, the switch, the status line ---------- */
  function setScreen(name) {
    var changed = SCREEN !== name;
    SCREEN = name;
    try { localStorage.setItem("koppal-screen", name); } catch (e) {}   /* survives a reload */
    ["home", "chat", "browse"].forEach(function (s) {
      $("screen-" + s).classList.toggle("on", s === name);
    });
    scroller.classList.toggle("snap", name === "home");   // two hard-snapping folds, Home only
    /* Browse hides the composer, so the scroller must not keep the fixed-box floor reserve — that
       reserve is what left a dead band under the shelf. Home drops it via `.scroll.snap`; Browse
       via `.nobox`. Chat keeps it, because there the box really is floating over the thread. */
    scroller.classList.toggle("nobox", name === "browse");
    moveThumb(name);
    closeMenu();
    /* Reset/Undo act on the transcript, so they exist on Chat only — the composer itself
       still travels to Home, but its control row does not. */
    $("convo-actions").hidden = name !== "chat";

    if (name === "browse") {
      composer.hidden = true;                             // a library, not a conversation
    } else {
      composer.hidden = false;
      composer.classList.toggle("floating", name === "chat");
      if (name === "home") {
        var slot = $("home-slot");
        if (composer.parentNode !== slot) slot.appendChild(composer);
      } else if (composer.parentNode !== document.body) {
        document.body.appendChild(composer);
      }
    }
    /* ONLY on an actual screen change. send() calls setScreen("chat") on every message, and an
       unconditional jump-to-top meant every send yanked the thread to the very beginning and
       then scrolled all the way back down — measured as a 625px backwards step. That was the
       up/down glitch, and it got worse the longer the conversation ran. */
    if (changed) scroller.scrollTo({ top: 0, behavior: "auto" });
    syncComposerHeight();       /* the bottom reserve follows the composer, not a guess */
    /* the placeholder types on Home too — the owner asked for it to stay */
    PLACEHOLDER_ON = true;
    requestAnimationFrame(updateFades);
    requestAnimationFrame(fitAllR);   /* whatever this screen just revealed needs --e */
  }

  /* the thumb slides to the active segment and morphs to its width; absent on Home */
  function moveThumb(name) {
    var thumb = $("thumb"), sw = $("switch");
    sw.querySelectorAll("button").forEach(function (b) {
      b.classList.toggle("on", b.getAttribute("data-screen") === name);
    });
    var active = sw.querySelector('button[data-screen="' + name + '"]');
    if (!active) { thumb.style.opacity = "0"; return; }
    thumb.style.opacity = "1";
    thumb.style.width = active.offsetWidth + "px";
    thumb.style.transform = "translateX(" + (active.offsetLeft - 3) + "px)";
  }

  /* There is no status line any more. It was removed on the owner's call: the ask bubble states
     the question directly above the chips, so "still on X" only restated what was already on
     screen, and in the thread it read as clutter. Transient notes went with it — the visible
     outcome is the feedback now (Undo vanishing when there is nothing left to undo, the thread
     emptying and the greeting returning after a reset). If orphaned chips after an interruption
     ever bite again, the fix is to label the chip row in THAT case only, not permanently. */
  /* ---------- the typewriter: mono question text, typed in (A11.2) ---------- */
  function typewriter(node, textOf, opts) {
    opts = opts || {};
    var stopped = false;
    if (REDUCE) { clear(node); node.textContent = textOf() || ""; return function () {}; }
    (function run() {
      if (stopped) return;
      var text = textOf();
      if (text == null) return;
      clear(node);
      var t = document.createTextNode("");
      var caret = el("span", "caret");
      node.appendChild(t); node.appendChild(caret);
      var i = 0;
      (function type() {
        if (stopped) return;
        t.textContent = text.slice(0, ++i);
        if (i < text.length) return setTimeout(type, 26);
        setTimeout(function () {
          if (caret.parentNode) caret.remove();
          if (opts.loop) setTimeout(function () {
            if (opts.advance) opts.advance();
            run();
          }, opts.hold || 3400);
        }, 900);
      })();
    })();
    return function () { stopped = true; };
  }

  /* the chat box placeholder types in, holds, types out, then the next one (A11.22).
     Home shows no placeholder at all, so the loop idles while PLACEHOLDER_ON is false. */
  var PLACEHOLDER_ON = false;
  function startPlaceholder() {
    if (!PLACEHOLDERS.length) return;
    if (REDUCE) { input.placeholder = PLACEHOLDER_ON ? PLACEHOLDERS[0] : ""; return; }
    var i = 0, n = 0, phase = "in";
    (function tick() {
      if (!PLACEHOLDER_ON || document.activeElement === input || input.value) {
        input.placeholder = "";
        return setTimeout(tick, 420);
      }
      var text = PLACEHOLDERS[i % PLACEHOLDERS.length];
      if (phase === "in") {
        input.placeholder = text.slice(0, ++n);
        if (n >= text.length) { phase = "hold"; return setTimeout(tick, 2400); }
        return setTimeout(tick, 48);
      }
      if (phase === "hold") { phase = "out"; return setTimeout(tick, 120); }
      input.placeholder = text.slice(0, Math.max(0, --n));
      if (n <= 0) { phase = "in"; i++; return setTimeout(tick, 300); }
      return setTimeout(tick, 24);
    })();
  }
  /* ================= HOME · the milestone board (A11.13 / A11.20) ================= */
  var stopTypers = [];

  async function renderBoard() {
    var ms = await milestones();
    var notes = $("notes"), rail = $("home-rail");
    stopTypers.forEach(function (f) { f(); });
    stopTypers = [];
    clear(notes); clear(rail);

    var dots = [];
    ms.forEach(function (m, i) {
      if (i) rail.appendChild(el("span", "line"));
      var d = el("button", "dot");
      d.setAttribute("aria-label", m.milestone);
      rail.appendChild(d);
      dots.push(d);
    });

    ms.forEach(function (m, i) {
      var big = i === 0;                            // exactly one large card (A11.3)
      /* every card carries its own tN, the big one included — `big` is layout (it spans the row),
         the tN is which of the shelf's five colours it wears. Card 1 used to get no tN at all,
         which is why it was the only card showing bare glass. */
      var note = el("button", "note paper pile t" + (i + 1) + (big ? " big" : ""));
      note.style.setProperty("--tilt", TILT[i] + "deg");
      note.style.setProperty("--edge-angle", EDGE[i] + "deg");

      /* every card is a pile, and the stack is IDENTICAL on all of them — same three sheets,
         same rotations, same offsets, same opacities. Only the colour differs, and that comes
         from the card itself via background-color:inherit. The scatter lives in custom
         properties so CSS can settle the pile on hover. */
      for (var s = 3; s >= 1; s--) {
        var back = el("span", "sheet-back");
        back.style.setProperty("--sr", (s * 1.6 - 2).toFixed(1) + "deg");
        back.style.setProperty("--sx", (s * 4) + "px");
        back.style.setProperty("--sy", (s * 5) + "px");
        back.style.opacity = String(0.5 - s * 0.1);
        note.appendChild(back);
      }

      note.appendChild(el("span", "label meta", m.step + " " + G.dot + " " + m.milestone));
      var q = el("span", "q");
      note.appendChild(q);

      var at = 0;
      var qs = (m.questions || []).slice();
      if (!qs.length) qs = [m.milestone];
      /* EVERY card types now, not only the first — same typewriter, same hold, same rotation, so
         the five behave alike instead of one being alive and four being posters. The reserved
         height on `.q` is what lets five live cards run without any of them reflowing the board. */
      stopTypers.push(typewriter(q, function () { return qs[at % qs.length]; },
        { loop: true, hold: 3600, advance: function () { at++; swipe(note); } }));

      function lit(state) {
        dots[i].classList.toggle("on", state);
        note.classList.toggle("lit", state);
      }
      note.onmouseenter = function () { lit(true); };
      note.onmouseleave = function () { lit(false); };
      dots[i].onmouseenter = function () { lit(true); };
      dots[i].onmouseleave = function () { lit(false); };
      note.onclick = function () { send(qs[at % qs.length] || m.milestone); };
      touchable(note);
      notes.appendChild(note);
    });
  }

  function swipe(note) {                             // the top sheet slips off behind the pile
    if (REDUCE) return;
    note.querySelectorAll(".sheet-back").forEach(function (b, k) {
      b.style.setProperty("--sr", (k * 2 - 3) + "deg");
      b.style.setProperty("--sx", (k * 5 + 6) + "px");
      b.style.setProperty("--sy", (k * 6 + 4) + "px");
    });
  }
  /* ================= CHAT (A11.4 / A11.16) =================
     Former bubble style -- flat, asymmetric, one squared inner corner on the speaker's
     side -- in the glass material, the same material for both sides. */
  /* Two per-element numbers the material needs, because `.dbox` was measured on a 157px-tall
     box and nothing in the app is that size:
       --e  edge scale, so a 55px bubble does not wear a 9px bevel
       --r  corner, a ratio of the element's own height — and only on bubbles that WRAP.
            Small pills (one-liners, chips, the composer) stay oval; the ratio looks boxy
            and ugly on them. */
  function fitR(node) {
    var cs = getComputedStyle(node);
    var h = node.getBoundingClientRect().height;
    if (!h) return;
    node.style.setProperty("--e", Math.max(.5, Math.min(1, h / 157)).toFixed(2));
    var ratio = parseFloat(cs.getPropertyValue("--r-ratio")) || 0;
    if (ratio && node.classList.contains("bubble") && !node.classList.contains("one"))
      /* CAPPED. The ratio alone meant a tall bubble wore a huge corner: a 200px-high answer
         got a 68px radius, which curls the shape in over its own text and reads as broken.
         The corner is a corner at any height past a point. */
      node.style.setProperty("--r", Math.round(Math.min(h * ratio, 30)) + "px");
    else
      node.style.removeProperty("--r");
  }
  /* re-run on theme flip and on reflow, since heights change with wrapping */
  function fitAllR() { document.querySelectorAll(".lg").forEach(fitR); }
  window.addEventListener("resize", fitAllR);
  /* every render path adds glass at some point (Browse drill-down, the board, the notice).
     One debounced observer beats a fitR() call sprinkled through each of them. */
  (function watchGlass() {
    var queued = false;
    new MutationObserver(function () {
      if (queued) return;
      queued = true;
      requestAnimationFrame(function () { queued = false; fitAllR(); });
    }).observe(document.body, { childList:true, subtree:true });
  })();

  function bubble(kind, text, delay, noReveal) {
    var row = el("div", "row " + (kind === "you" ? "you" : "bot"));
    var b = el("div", "bubble lg " + kind);
    b.style.setProperty("--edge-angle", (kind === "you" ? 150 : 215) + "deg");
    structure(b, text);
    if (!REDUCE && !noReveal) {
      b.classList.add("reveal");
      if (delay) b.style.animationDelay = delay + "ms";
    }
    /* an open follow-up marks its ROW, not its bubble: the waiting signal is the ripple on
       the speaker dot now, and CSS needs the row to reach the dot from the bubble's state */
    if (kind === "ask") row.classList.add("asking");
    // the speaker mark: lime circle for the bot, white for the user (A11.27)
    var mark = el("span", "mark");
    if (kind === "you") { row.appendChild(b); row.appendChild(mark); }
    else { row.appendChild(mark); row.appendChild(b); }
    thread.appendChild(row);
    /* a bubble that fits on one line becomes a full stadium, like the ref's small pills;
       anything that wraps keeps the block radius */
    var cs = getComputedStyle(b);
    var oneLine = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom) +
                  parseFloat(cs.lineHeight) * 1.3;
    if (b.getBoundingClientRect().height <= oneLine) b.classList.add("one");
    fitR(b);
    return b;
  }

  function emptyState(show) { $("hello").classList.toggle("gone", !show); }

  /* The thinking indicator. It is shaped exactly like a bot row — dot, then the dots pill — so
     it stands where the bubble is about to stand and the column never shifts.
     `abortable` is true only while the SERVER is what we are waiting for; the per-bubble
     mimicry is not something you cancel. */
  function composing(on, abortable) {
    var t = $("typing");
    if (on) {
      if (!t) {
        t = el("div", "row bot typing");
        t.id = "typing";
        t.appendChild(el("span", "mark"));
        var dots = el("div", "dots lg");
        dots.style.setProperty("--edge-angle", "215deg");
        dots.appendChild(el("i")); dots.appendChild(el("i")); dots.appendChild(el("i"));
        t.appendChild(dots);
        thread.appendChild(t);
        fitR(dots);
        down();
      }
      var stop = t.querySelector(".readmore");
      if (abortable && !stop) {
        stop = el("button", "readmore lg", "stop");
        stop.onclick = function () { if (inFlight) inFlight.abort(); };
        t.appendChild(stop);
      } else if (!abortable && stop) {
        stop.remove();
      }
    } else if (t) {
      t.remove();
    }
  }

  /* how long to "type" a bubble before it lands: a one-liner arrives quickly, a long answer
     takes longer, the way a person would. Capped so nobody waits on a wall of text. */
  function typePause(text) {
    if (REDUCE) return 0;
    return Math.min(1500, 360 + (text || "").length * 5.5);
  }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  /* chips are filled, never outlines; a resolved row greys out but stays visible (#10 UI half) */
  function renderChips(choices) {
    var row = el("div", "chips");
    choices.forEach(function (c) {
      var chip = el("button", "chip lg", c.label);
      chip.onclick = function () {
        row.querySelectorAll(".chip").forEach(function (n) { n.disabled = true; });
        chip.classList.add("picked");
        /* tagged with the menu it belongs to, so a restored-after-reload chip whose follow-up
           the server has already resolved still answers instead of falling to the classifier */
        send(c.key, c.label, c.intent ? { intent: c.intent, key: c.key } : null);
      };
      row.appendChild(chip);
    });
    thread.appendChild(row);
    chipRow = row;
    row.querySelectorAll(".chip").forEach(fitR);
  }
  /* "Did you mean one of these?" -- the three topics the classifier ranked highest for a
     message it was not confident enough to answer. Cross-validated top-3 is 0.874 against
     top-1 0.716, so roughly one refused question in six already had its answer here.

     Same chip as a follow-up menu, one difference in the tag: a branch chip sends
     {intent, key}, a suggestion sends {intent} alone, and `asked` (the user's ORIGINAL
     message, not this label) rides along as the message. The server forces that topic for
     that message, so the answer is the one the tapped label promised -- and the user's own
     words still reach the engine, which is what lets it skip a follow-up it can already
     answer from them. */
  function renderSuggestions(list, asked) {
    if (!asked) return;                            /* nothing to re-send means nothing to offer */
    var row = el("div", "chips suggest");
    list.forEach(function (s) {
      var chip = el("button", "chip lg", s.label);
      chip.onclick = function () {
        row.querySelectorAll(".chip").forEach(function (n) { n.disabled = true; });
        chip.classList.add("picked");
        send(asked, s.label, { intent: s.intent });
      };
      row.appendChild(chip);
    });
    thread.appendChild(row);
    chipRow = row;
    row.querySelectorAll(".chip").forEach(fitR);
  }

  function retireChips() {    if (!chipRow) return;
    chipRow.querySelectorAll(".chip").forEach(function (n) { n.disabled = true; });
    chipRow = null;
  }

  /* an answered pending question must stop rippling (A11.27) */
  function settleAsk() {
    thread.querySelectorAll(".bubble.ask").forEach(function (n) { n.classList.add("resolved"); });
    thread.querySelectorAll(".row.asking").forEach(function (n) { n.classList.remove("asking"); });
  }

  /* One step back, distinct from Reset. The control is a permanent button beside the
     composer now, so this only toggles its visibility and owns the click. */
  function showUndo(on) { $("undo").hidden = !on; }

  async function doUndo() {
    var b = $("undo");
    b.disabled = true;
    var ok = false;
    try { ok = (await api("/api/session/undo", { method: "POST", body: { session_id: SID } })).ok; }
    catch (e) {}
    b.disabled = false;
    if (!ok) { showUndo(false); return; }          /* the control vanishing IS the feedback */
    // drop everything rendered after the last user turn, then re-open the menu it answered
    var kids = Array.prototype.slice.call(thread.children);
    for (var i = kids.length - 1; i >= 0; i--) {
      var n = kids[i];
      n.remove();
      if (n.classList.contains("row") && n.classList.contains("you")) break;
    }
    var lastChips = thread.querySelectorAll(".chips");
    if (lastChips.length) {
      var live = lastChips[lastChips.length - 1];
      live.querySelectorAll(".chip").forEach(function (c) {
        c.disabled = false; c.classList.remove("picked");
      });
      chipRow = live;
    }
    /* the answered follow-up becomes open again: un-resolve it AND restart its dot ripple */
    thread.querySelectorAll(".bubble.ask").forEach(function (n) {
      n.classList.remove("resolved");
      if (n.parentNode) n.parentNode.classList.add("asking");
    });
    /* nothing of the user's left on screen means nothing left to step back to */
    if (!thread.querySelector(".row.you")) { showUndo(false); emptyState(true); }
    logUndo();                                     // keep the persisted chat in step with the DOM
    down();
  }

  /* One scroll-to-bottom, never a pile of them. The up/down glitch on send was competing
     smooth animations: the indicator, then each bubble, then the chips each asked for a smooth
     scroll while the content height was still changing, so the browser kept re-aiming at a
     moving target. Now calls inside one frame collapse to one, and a request that arrives
     while a smooth scroll is still running snaps instead of starting a second animation. */
  var downQueued = false, lastSmooth = 0;
  function down() {
    if (downQueued) return;
    downQueued = true;
    requestAnimationFrame(function () {
      downQueued = false;
      var now = performance.now();
      var smooth = !REDUCE && now - lastSmooth > 420;
      if (smooth) lastSmooth = now;
      scroller.scrollTo({ top: scroller.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    });
  }
  /* "read the full answer": ONE destination -- the topic's page in Browse, with the full
     answer already open (A11.30.2). In Chat it takes you there; in Browse you are already
     on that page, so openTopic just opens the prose in place. No scroll jumps. */
  function readMoreLink(container, intent) {
    var btn = el("button", "readmore lg");
    btn.appendChild(document.createTextNode("read the full answer"));
    btn.appendChild(el("i", "", G.next));
    btn.onclick = function () { openIntentInBrowse(intent, true); };
    container.appendChild(btn);
    return btn;
  }

  /* Bubbles land one at a time, each preceded by the thinking indicator, and the pause before
     each scales with that bubble's own length. The indicator is already on screen from the
     server wait, so the first bubble does not make it blink out and back in. */
  async function renderReply(d) {
    settleAsk();                                   // the previous pending question settles
    var bubbles = d.bubbles || [];
    for (var i = 0; i < bubbles.length; i++) {
      var b = bubbles[i];
      composing(true, false);                      // mimicry: same row shape, not cancellable
      await wait(typePause(b.text));
      composing(false);
      var kind = b.kind === "ask" ? "ask" : b.kind === "back" ? "back" : "bot";
      bubble(kind, b.text, 0);
      down();
    }
    if (d.choices && d.choices.length) renderChips(d.choices);
    else if (d.suggestions && d.suggestions.length) renderSuggestions(d.suggestions, d.asked);
    if (d.more) readMoreLink(thread, d.more);
    showUndo(true);                                // there is now a turn to step back from
    logReply(d);                                   // persist the turn so a reload restores it
    down();
  }

  /* ---- the chat, persisted across reloads (owner's call: a refresh must not throw the
     conversation away). THREAD_LOG mirrors the thread as an ordered list of turns -- a user
     line {you} or a server reply {reply:d} -- so a reload can replay it verbatim, and the last
     open follow-up's chips come back LIVE because the server session (same session_id) still
     holds the pending slot. Replay is static: no typewriter, no reveal -- it is already history.
     Known v1 limits (for the owner): historical (already-answered) chip rows are not redrawn,
     only the final open one; and a SERVER restart would desync the restored chips from a
     session it no longer holds. ---- */
  var THREAD_KEY = "koppal-thread";
  function saveThread() {
    try { localStorage.setItem(THREAD_KEY, JSON.stringify({ sid: SID, log: THREAD_LOG })); }
    catch (e) {}
  }
  function loadThreadLog() {
    var raw = null;
    try { raw = localStorage.getItem(THREAD_KEY); } catch (e) {}
    if (!raw) return;
    var data = null;
    try { data = JSON.parse(raw); } catch (e) {}
    if (data && data.sid === SID && data.log && data.log.length) THREAD_LOG = data.log;
  }
  function logYou(t) { THREAD_LOG.push({ you: t }); saveThread(); }
  function logReply(d) { THREAD_LOG.push({ reply: d }); saveThread(); }
  /* undo drops the last turn: pop trailing items until (and including) the last user line,
     mirroring the DOM trim in doUndo so the log and the thread never diverge. */
  function logUndo() {
    for (var i = THREAD_LOG.length - 1; i >= 0; i--) {
      var it = THREAD_LOG[i];
      THREAD_LOG.pop();
      if (it && it.you !== undefined) break;
    }
    saveThread();
  }
  /* build the saved thread into the DOM once, when Chat is first shown -- measuring a bubble
     inside a display:none screen misreads the one-line stadium test, so we wait until setScreen
     has made it visible. */
  function ensureThreadBuilt() {
    if (threadBuilt) return;
    threadBuilt = true;
    if (THREAD_LOG.length) replayThread();
  }
  function replayThread() {
    clear(thread);
    chipRow = null;
    var last = null;
    THREAD_LOG.forEach(function (it) {
      if (it.you !== undefined) { bubble("you", it.you, 0, true); return; }
      if (!it.reply) return;
      var d = it.reply;
      (d.bubbles || []).forEach(function (b) {
        var kind = b.kind === "ask" ? "ask" : b.kind === "back" ? "back" : "bot";
        bubble(kind, b.text, 0, true);
      });
      if (d.more) readMoreLink(thread, d.more);
      last = d;
    });
    settleAsk();                                   // history is settled...
    if (last && last.choices && last.choices.length) {
      renderChips(last.choices);                   // ...but the final follow-up comes back LIVE
      var asks = thread.querySelectorAll(".bubble.ask");
      if (asks.length) {
        var la = asks[asks.length - 1];
        la.classList.remove("resolved");
        if (la.parentNode) la.parentNode.classList.add("asking");
      }
    } else if (last && last.suggestions && last.suggestions.length) {
      // A refusal restored from the log keeps its offer: the pick needs only the original
      // message, which was logged with the turn, not a server-side pending slot.
      renderSuggestions(last.suggestions, last.asked);
    }
    if (thread.querySelector(".row.you")) { emptyState(false); showUndo(true); }
    down();
  }

  /* `choice` is the click tag (B10): a chip sends {intent, key} alongside the text, so the
     engine answers the menu the button belongs to instead of re-reading the key as typing.
     Typed messages pass nothing and behave exactly as before. */
  async function send(text, echoLabel, choice) {
    text = (text || "").trim();
    if (!text) return;
    if (inFlight) inFlight.abort();
    retireChips();
    commit({ screen: "chat" });
    emptyState(false);
    bubble("you", echoLabel || text, 0);
    logYou(echoLabel || text);
    composing(true, true);      /* scrolls down itself, which is what moves the thread up */

    var ctrl = new AbortController();
    inFlight = ctrl;
    var d;
    try {
      var payload = { session_id: SID, message: text };
      if (choice) payload.choice = choice;
      d = await api("/api/message", {
        method: "POST", signal: ctrl.signal,
        body: payload
      });
    } catch (e) {
      inFlight = null;
      composing(false);
      bubble("back", e && e.name === "AbortError"
        ? "Stopped. Ask again, or Reset to start clean."
        : "I couldn't reach the server just then. Please try again.", 0);
      return;
    }
    inFlight = null;
    d.asked = text;             /* the pick re-sends this, and it survives a reload with the log */
    await renderReply(d);       /* renderReply owns the indicator from here */
  }

  /* Reset is destructive, so it asks first — in the same on-screen card About and Suggest-a-fix
     use, with red carrying the consequence and white the way out. */
  function confirmReset() {
    modal("Reset this conversation?", function (card) {
      card.appendChild(el("p", "", "Everything in this chat goes away and Koppal forgets what "
        + "you were talking about. Browse and your theme are untouched."));
      var actions = el("div", "actions");
      var cancel = el("button", "btn-cancel", "Cancel");
      var yes = el("button", "btn-danger", "Reset");
      cancel.onclick = function () { card.parentNode.remove(); };
      yes.onclick = function () { card.parentNode.remove(); reset(); };
      actions.appendChild(cancel);
      actions.appendChild(yes);
      card.appendChild(actions);
      /* modal() focuses its own close button after build(), so claim focus for the SAFE
         option on the next tick — a destructive dialog must never open with Reset armed. */
      setTimeout(function () { cancel.focus(); }, 0);
    });
  }

  async function reset() {
    if (inFlight) inFlight.abort();
    try { await api("/api/session/reset", { method: "POST", body: { session_id: SID } }); }
    catch (e) {}
    clear(thread);
    THREAD_LOG = [];
    saveThread();                                  // the persisted chat goes with it
    chipRow = null;
    showUndo(false);                               // nothing left to step back to
    emptyState(true);                              // greeting + big question return (A11.16)
    setScreen("chat");
  }
  /* ================= BROWSE · spines + the interactive rail (A11.5 / A11.10) ================= */
  async function renderShelf() {
    var ms = await milestones();
    var area = $("shelf-area"), rail = $("browse-rail");
    showRail(true);
    clear(area); clear(rail);

    var shelf = el("div", "shelf");
    ms.forEach(function (m, i) {
      if (i) rail.appendChild(el("span", "line"));
      var d = el("button", "dot");
      d.setAttribute("aria-label", "Jump to " + m.milestone);
      rail.appendChild(d);

      var sp = el("button", "spine c" + (i + 1));
      sp.style.setProperty("--tilt", SPINE_TILT[i] + "deg");
      sp.style.setProperty("--off", SPINE_OFF[i] + "px");
      sp.appendChild(el("span", "step", "step " + m.step));
      sp.appendChild(el("span", "name", m.milestone));
      sp.appendChild(el("span", "sub", m.categories.join("  " + G.dot + "  ")));
      sp.onclick = function () { commit({ screen: "browse", view: "book", milestone: slug(m.milestone) }); };
      touchable(sp);
      sp.onmouseenter = function () { d.classList.add("on"); };
      sp.onmouseleave = function () { d.classList.remove("on"); };
      // the rail is a tracker, not a link (A11.28) -- it only ever highlights
      d.disabled = true;
      d.onmouseenter = function () { sp.classList.add("lit"); };
      d.onmouseleave = function () { sp.classList.remove("lit"); };
      shelf.appendChild(sp);
    });
    area.appendChild(shelf);
  }

  /* the outer rail belongs to the shelf only: page 2 tells position with its own sticky chapter
     heads and page 3 has none at all (A11.28). The shelf level is also the only one that is a
     centred single fold — so this is where `.at-shelf` (fold height + vertical centring) and the
     shelf's own description line go on, and where they come off the moment a book opens and the
     page has to flow and scroll. */
  function showRail(on) {
    var rail = $("browse-rail");
    if (!on) clear(rail);
    rail.style.display = on ? "" : "none";
    $("browse-grid").classList.toggle("at-shelf", !!on);
    $("shelf-head").hidden = !on;
  }

  /* Page 2 -- the opened book's CONTENTS page. Chapters are always open: a contents page that
     hides its contents is not one. Position is told by the chapter head, which sticks to the
     top of the scroller while you are inside its section -- that is the job the old scrub
     tracker was doing badly, so the tracker is gone rather than replaced. */
  function openBook(m) {
    var area = $("shelf-area");
    showRail(false);
    clear(area);

    var wrap = el("div", "opened");
    wrap.appendChild(backTo("the shelf", renderShelf));
    wrap.appendChild(el("h1", "display", m.milestone));

    var chapters = m.chapters;
    /* Fallback: if the server hasn't been restarted since `chapters` was added to
       /api/milestones, render every topic in one unnamed section rather than a blank page. */
    if (!chapters || !chapters.length) chapters = [{ chapter: null, topics: m.topics || [] }];

    wrap.appendChild(el("p", "subline", chapters.length > 1
      ? (m.topics.length + " topics  " + G.dot + "  " + chapters.length + " chapters")
      : m.categories.join("  " + G.dot + "  ")));

    var contents = el("div", "contents");
    chapters.forEach(function (c, ci) {
      var sec = el("section", "chapter");
      if (c.chapter) {
        var head = el("div", "chead");
        head.appendChild(el("span", "cnum", (ci + 1 < 10 ? "0" : "") + (ci + 1)));
        head.appendChild(el("span", "cname", c.chapter));
        head.appendChild(el("span", "ccount", String(c.topics.length)));
        sec.appendChild(head);
      }

      var rows = el("div", "crows");
      c.topics.forEach(function (t) {
        var r = el("button", "trow", t.title);
        r.onclick = function () {
          commit({ screen: "browse", view: "topic",
                   milestone: slug(m.milestone), intent: t.intent });
        };
        rows.appendChild(r);
      });
      sec.appendChild(rows);
      contents.appendChild(sec);
    });
    wrap.appendChild(contents);
    area.appendChild(wrap);
    applyScroll();          /* back from a topic lands you where you were, not at the top */
  }

  /* the back control: the small title above, made big enough to read as a button (A11.28) */
  function backTo(label, fn) {
    var b = el("button", "backlink");
    b.appendChild(el("i", "", G.prev));
    /* the label is its own span so hover can underline the WORD and leave the big arrow alone */
    b.appendChild(el("span", "lbl", label));
    /* the back arrow now defers to the browser's own history: it returns to wherever you
       actually came from -- the shelf/book when you drilled in, or Chat when a "read the
       full answer" brought you straight to this topic. The label stays as the usual parent
       for orientation. (fn is kept for call-site compatibility but no longer used.) */
    b.onclick = function () { history.back(); };
    return b;
  }

  /* (Browse used to echo its title into the header's status line once the big one scrolled out of
     view. The status is gone, so the observer went with it. If a sticky mini-title is ever
     wanted, it belongs to Browse itself, not to the chrome.) */
  async function openTopic(t, m, openProse) {
    var area = $("shelf-area");
    showRail(false);
    var d;
    try { d = await api("/api/intent/" + encodeURIComponent(t.intent)); }
    catch (e) { return m ? openBook(m) : renderShelf(); }
    clear(area);

    /* `topic` marks page 3: the back control sticks there (see styles.css) so it doubles as the
       status line once the title scrolls away. The back control names the page one level up --
       the contents page you came from -- so the sub-line under the title is the CHAPTER, not the
       category: repeating the category there said the same thing twice. */
    var wrap = el("div", "opened topic");
    wrap.appendChild(backTo(m ? m.milestone : "the shelf",
      function () { if (m) openBook(m); else renderShelf(); }));

    wrap.appendChild(el("h1", "display", d.title));
    wrap.appendChild(el("p", "subline", d.chapter || d.category));

    var body = el("div", "detail");                 // everything below is a centred column
    if (d.lead) body.appendChild(structure(el("div", "lead"), d.lead));

    /* the page's own voice: a real user's wording, quoted. The engine's `trigger` is not shown
       as a bare line any more -- it has become the heading over a branch group below. */
    if (d.asked_as) body.appendChild(el("p", "quote", G.quote + d.asked_as + G.unquote));

    /* one block per question. A compound intent has two, each with its own branches, instead
       of every branch from both questions dumped into one undifferentiated row. */
    (d.groups || []).forEach(function (g) {
      if (g.ask) body.appendChild(el("p", "qline", g.ask));
      g.branches.forEach(function (b) {
        var card = el("div", "bcard lg");
        var btn = el("button");
        btn.appendChild(el("span", "", b.label));
        var sign = el("i", "", "+");
        btn.appendChild(sign);
        var text = structure(el("div", "body"), b.text);
        text.hidden = true;
        btn.onclick = function () {
          text.hidden = !text.hidden;
          sign.textContent = text.hidden ? "+" : G.minus;
        };
        card.appendChild(btn);
        card.appendChild(text);
        body.appendChild(card);
      });
    });

    /* read on the left, ask on the right, same size (A11.28). The prose is inserted ABOVE this
       row, so expanding it pushes the actions down instead of stranding them mid-page with
       the full answer dumped underneath. */
    var actions = el("div", "detail-actions");
    var prose = null;
    if (d.has_more && d.prose) {
      var btn2 = el("button", "readmore lg");
      btn2.appendChild(document.createTextNode("read the full answer"));
      btn2.appendChild(el("i", "", G.next));
      prose = structure(el("div", "prose"), d.prose);
      prose.hidden = true;
      btn2.onclick = function () {
        prose.hidden = !prose.hidden;
        clear(btn2);
        btn2.appendChild(document.createTextNode(
          prose.hidden ? "read the full answer" : "hide the full answer"));
        btn2.appendChild(el("i", "", prose.hidden ? G.next : G.up));
      };
      actions.appendChild(btn2);
    } else {
      actions.appendChild(el("span"));
    }
    var ask = el("button", "askchat lg", "Ask this in chat");
    ask.onclick = function () { send(d.question || d.title); };
    actions.appendChild(ask);

    if (prose) body.appendChild(prose);
    body.appendChild(actions);
    if (prose && openProse) actions.firstChild.click();

    wrap.appendChild(body);
    area.appendChild(wrap);
    /* a topic normally opens at its title; only a RETURN to one restores where you were reading */
    if (PENDING_SCROLL) applyScroll();
    else scroller.scrollTo({ top: 0, behavior: REDUCE ? "auto" : "smooth" });
  }

  /* Chat's "read the full answer" lands here: the topic's own page, prose already open */
  async function openIntentInBrowse(intent, openProse) {
    var ms = await milestones();
    var home = null;
    ms.forEach(function (m) {
      m.topics.forEach(function (t) { if (t.intent === intent) home = m; });
    });
    if (!home) { commit({ screen: "browse", view: "shelf" }); return; }
    commit({ screen: "browse", view: "topic", milestone: slug(home.milestone), intent: intent, full: !!openProse });
  }

  /* ================= wiring ================= */
  function closeMenu() {
    menu.hidden = true;
    $("menu-btn").setAttribute("aria-expanded", "false");
  }
  function go(name) {
    /* the chrome nav (the Chat/Browse switch and the wordmark) records a history entry via
       commit; the rendering -- including Browse resetting to its shelf, and Chat's greeting
       when the thread is empty -- is handled inside renderState. */
    commit(screenState(name));
  }
  function isDark() { return document.documentElement.classList.contains("dark"); }
  function setTheme(dark) {
    document.documentElement.classList.toggle("dark", dark);
    /* the icon itself is swapped in CSS; only the label needs saying out loud */
    $("theme-btn").setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    try { localStorage.setItem("koppal-theme", dark ? "dark" : "light"); } catch (e) {}
    moveThumb(SCREEN);
    fitAllR();                     /* the corner ratio differs per mode */
  }
  /* The panel is no longer liquid glass (Phase 7): it is opaque and inverts its mode, and the
     blur has moved to the scrim, so nothing behind the dialog reads through the copy. The head
     carries the title plus an optional mono gloss on the same baseline — one title, not three. */
  function modal(title, build, sub) {
    var back = el("div", "modal");
    var card = el("div", "card");
    var head = el("div", "mhead");
    var t = el("div", "mtitle");
    t.appendChild(el("h2", "h2", title));
    if (sub) t.appendChild(el("span", "meta", sub));
    head.appendChild(t);
    var x = el("button", "icon-btn", G.close);
    x.setAttribute("aria-label", "Close");
    x.onclick = function () { back.remove(); };
    head.appendChild(x);
    card.appendChild(head);
    build(card);
    back.appendChild(card);
    back.onclick = function (e) { if (e.target === back) back.remove(); };
    document.body.appendChild(back);
    x.focus();
  }

  function field(card, label, area) {
    var f = el("div", "field");
    var id = "f" + Math.random().toString(16).slice(2);
    var l = el("label", "", label);
    l.setAttribute("for", id);
    var n = el(area ? "textarea" : "input");
    n.id = id;
    if (area) n.rows = 3;
    f.appendChild(l); f.appendChild(n); card.appendChild(f);
    return n;
  }

  function menuAction(a) {
    closeMenu();
    /* theme is no longer in here — it has its own header button (D6) */
    /* About is a spec card, not paragraphs: the wordmark IS the modal title, its gloss sits beside
       it on the same baseline, then one mono label per row with its value beside it. The old copy
       carried a disclaimer that read as a warning-off; provenance now sits in SOURCE, where it
       reads as credibility instead. */
    if (a === "about") return modal("Koppal", function (card) {
      var rows = el("dl", "about-rows");
      /* labels are written in sentence case and uppercased by CSS, so a screen reader says
         "covers" rather than spelling it out */
      [["Covers", "your NYSC journey from start to finish: registration · camp · "
          + "allowance · PPA · relocation · clearance · passing out"],
       ["Source", "official NYSC guides, plus real questions and experiences from corps members"],
       ["Ask", "chat, in your own words"],
       ["Read", "Browse, topic by topic"]].forEach(function (r) {
        rows.appendChild(el("dt", "meta", r[0]));
        rows.appendChild(el("dd", "", r[1]));
      });
      card.appendChild(rows);
    }, "Kopa's pal");
    if (a === "contribute") return modal("Suggest a fix", function (card) {
      var asked = field(card, "What did you ask?");
      var wrong = field(card, "What was wrong or missing?", true);
      var actions = el("div", "actions");
      var msg = el("span", "quiet", "");
      var send1 = el("button", "askchat", "Send");
      send1.onclick = async function () {
        if (!asked.value.trim() && !wrong.value.trim()) {
          msg.textContent = "Add a little detail first.";
          return;
        }
        send1.disabled = true;
        try {
          await api("/api/contribute", { method: "POST",
            body: { category: "", asked: asked.value, wrong: wrong.value } });
          msg.textContent = "Thank you -- logged for review.";
        } catch (e) {
          msg.textContent = "Could not send. Try again.";
          send1.disabled = false;
        }
      };
      actions.appendChild(msg);
      actions.appendChild(send1);
      card.appendChild(actions);
    });
  }
  /* The floating composer sits ON TOP of the scroller, so the scroller has to reserve exactly
     its height at the bottom — otherwise the last thing in the thread (usually the branch
     chips) hides behind it and no amount of scrolling brings it back, because there is nothing
     left to scroll. Measured rather than guessed: a hard-coded 7rem was ~30px short. */
  function syncComposerHeight() {
    var h = composer.hidden || !composer.classList.contains("floating")
      ? 0 : composer.getBoundingClientRect().height;
    document.documentElement.style.setProperty("--composer-h", Math.round(h) + "px");
  }
  if (window.ResizeObserver) new ResizeObserver(syncComposerHeight).observe(composer);
  on(window, "resize", syncComposerHeight);

  /* Touch has no hover, so every signature move on this app — the pile settling flat, a card
     lifting, a spine sliding out of the shelf — was dead on a phone. `.touched` is applied on
     pointerdown and held briefly after release, long enough to read as the same gesture. */
  function touchable(node) {
    var off = null;
    on(node, "pointerdown", function () {
      clearTimeout(off);
      node.classList.add("touched");
    });
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (ev) {
      on(node, ev, function () {
        clearTimeout(off);
        off = setTimeout(function () { node.classList.remove("touched"); }, 550);
      });
    });
  }

  /* the boundary fades only bite when content is actually near an edge (A11.30.3) */
  function updateFades() {
    var top = scroller.scrollTop > 12;
    var bottom = scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop > 12;
    scroller.classList.toggle("fade-top", top);
    scroller.classList.toggle("fade-bottom", bottom);
  }
  on(scroller, "scroll", updateFades, { passive: true });
  on(window, "resize", updateFades);

  /* The chrome is fixed, so a wheel over the header or over the chat box hit nothing and
     the page felt unscrollable unless you used the arrow keys. Forward those events to
     the one scroller. Same for a touch drag started on the chat box. */
  on(document, "wheel", function (e) {
    if (scroller.contains(e.target)) return;                  // real content: leave it alone
    if (menu.contains(e.target)) return;                      // the menu scrolls itself
    if (scroller.scrollHeight - scroller.clientHeight < 2) return;
    scroller.scrollTop += e.deltaY;
    e.preventDefault();
  }, { passive: false });
  var touchY = null;
  on(document, "touchstart", function (e) {
    touchY = scroller.contains(e.target) ? null : e.touches[0].clientY;
  }, { passive: true });
  on(document, "touchmove", function (e) {
    if (touchY === null) return;
    var y = e.touches[0].clientY;
    scroller.scrollTop += touchY - y;
    touchY = y;
  }, { passive: true });

  $("switch").querySelectorAll("button").forEach(function (b) {
    b.onclick = function () { go(b.getAttribute("data-screen")); };
  });
  on($("brand"), "click", function () { go("home"); });
  on($("theme-btn"), "click", function () { setTheme(!isDark()); });
  on($("menu-btn"), "click", function (e) {
    e.stopPropagation();
    var open = menu.hidden;
    menu.hidden = !open;
    $("menu-btn").setAttribute("aria-expanded", String(open));
  });
  on(document, "click", function (e) {
    if (!menu.hidden && !menu.contains(e.target) && e.target !== $("menu-btn")) closeMenu();
  });
  menu.querySelectorAll("button").forEach(function (b) {
    b.onclick = function () { menuAction(b.getAttribute("data-action")); };
  });
  on(document, "keydown", function (e) { if (e.key === "Escape") closeMenu(); });

  on($("form"), "submit", function (e) {
    e.preventDefault();
    var v = input.value;
    input.value = "";
    send(v);
  });
  on($("reset"), "click", confirmReset);
  on($("undo"), "click", doUndo);
  on(window, "resize", function () { moveThumb(SCREEN); });

  /* ---------- boot ---------- */
  (async function boot() {
    setTheme(isDark());
    try {
      var h = await api("/api/health");
      if (!h.classifier_available) {
        $("notice").hidden = false;
        $("notice").textContent = "Classifier not loaded -- typed questions can't be routed "
          + "yet, but Browse works in full.";
      }
    } catch (e) {}
    try { PLACEHOLDERS = await api("/api/placeholders"); }
    catch (e) { PLACEHOLDERS = ["ask about camp, posting, allowance..."]; }
    startPlaceholder();
    loadThreadLog();                               // pull the saved chat in before anything renders
    emptyState(!THREAD_LOG.length);
    await renderBoard();
    /* Reopen the screen you were on. This used to be an unconditional setScreen("home"),
       which is why a reload on Chat or Browse always dumped you back to the launchpad — and
       worse, because it lands at the END of boot's awaits, it also stole the screen back from
       anyone who navigated during startup. Only fall back to Home if nothing is remembered
       and the user has not already chosen. (The transcript IS restored now -- loadThreadLog()
       ran above and replayThread() builds it into the DOM the moment Chat is shown.) */
    var restored = stateFromHash();                // an exact view from the URL wins
    if (!restored) {                               // otherwise fall back to the remembered screen
      var want = null;
      try { want = localStorage.getItem("koppal-screen"); } catch (e) {}
      restored = screenState(want === "chat" || want === "browse" ? want : "home");
    }
    if (SCREEN) return;                            // the user got there first: leave them be
    seedHistory(ancestors(restored));              // seed Home -> ... -> here so Back walks up, not out
  })();

  /* ---- Home's two-fold snap, in JS ------------------------------------------------------------
     CSS `mandatory` jumped a whole screen on the faintest nudge; `proximity` parked mid-scroll.
     We let the gesture run free and, ~120ms after it stops, ease to whichever fold it is NEARER:
     cross past half and you commit to the board, fall short and you settle back where you were.
     The step is MEASURED (sheet-2 top minus sheet-1 top) so it stays exact under the header offset,
     dvh and zoom. Home only; instant under reduced motion. `snapping` guards our own smooth scroll
     from re-triggering the handler. */
  var snapT, scrollEndT, snapping = false;
  function homeStep() {
    var sh = scroller.querySelectorAll("#screen-home .sheet");
    if (sh.length < 2) return scroller.clientHeight;
    return sh[1].getBoundingClientRect().top - sh[0].getBoundingClientRect().top;
  }
  function snapHome() {
    if (SCREEN !== "home") return;
    var step = homeStep(), y = scroller.scrollTop;
    if (step < 40) return;
    var target = y > step * 0.5 ? step : 0;        // nearest of the two folds
    if (Math.abs(target - y) < 2) return;          // already there
    snapping = true;
    scroller.scrollTo({ top: target, behavior: REDUCE ? "auto" : "smooth" });
    clearTimeout(snapT);
    snapT = setTimeout(function () { snapping = false; }, 480);
  }

  /* ---- the home-fold bob ----------------------------------------------------------------------
     NOT a one-shot on load any more (that fired before layout settled and never came back). A
     timer bobs the first fold a few seconds after things go quiet, and again after each fresh
     stretch of inactivity, so the "it scrolls" hint keeps offering itself. Any real interaction
     (scroll, pointer, key) resets the timer; it only plays on Home while you are on screen 1, and
     never under reduced motion. Force a reflow between remove/add so the same class replays. */
  var NUDGE_IDLE = 5500, NUDGE_REPEAT = 11000, nudgeTimer;
  function armNudge(ms) {
    clearTimeout(nudgeTimer);
    if (REDUCE) return;
    nudgeTimer = setTimeout(fireNudge, ms || NUDGE_IDLE);
  }
  function fireNudge() {
    if (REDUCE || SCREEN !== "home" || scroller.scrollTop > 24) { armNudge(); return; }
    var h1 = document.querySelector(".home1");
    if (h1) { h1.classList.remove("nudge"); void h1.offsetWidth; h1.classList.add("nudge"); }
    armNudge(NUDGE_REPEAT);
  }

  on(scroller, "scroll", function () {
    armNudge();                                    // scrolling is activity: reset the bob timer
    if (SCREEN !== "home" || snapping) return;
    clearTimeout(scrollEndT);
    scrollEndT = setTimeout(snapHome, 120);        // snap once the gesture settles
  });
  on(document, "pointerdown", function () { armNudge(); });
  on(document, "keydown", function () { armNudge(); });
  armNudge();










})();
