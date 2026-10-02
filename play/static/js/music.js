/* Background music: `window.Music`. The owner's own tracks (2026-10-02, made with Suno as
 * djsolideo; docs/asset-licences.md), looped as two playlists:
 *
 *   ambient   eight calm pieces, under everything that is not a fight
 *   battle    five fight pieces, while the table's scene is in an encounter
 *
 *   Music.mode("ambient" | "battle")   crossfade to that playlist (no-op if already there)
 *   Music.start()                      begin, or resume where the last page left off
 *   Music.stop()
 *
 * HOW IT PLAYS. Two <audio> elements, A and B, so one track can fade out while the next
 * fades in: 4 seconds between tracks, 2.5 when a fight starts or ends. Each playlist is
 * shuffled, played through without a repeat, then shuffled again with the last track kept
 * off the front, so the same piece is never heard twice in a row.
 *
 * WHY BLOBS. Django's static view answers a file whole and ignores HTTP Range, and an
 * <audio> element cannot seek a stream it cannot range-request, so "carry on where the
 * home page left off" would restart every song. Each track (3 to 7 MB, served locally) is
 * fetched whole into a blob URL instead, which is seekable at once; only the one or two
 * playing are held.
 *
 * VOLUME is the Sound and motion settings': master x music, or nothing when muted, read
 * live through PGMPrefs. A browser (and Electron) will not start audio before the first
 * gesture, so a refused play() waits for the first click or key and tries again.
 *
 * NO LIBRARY, no loop of its own: the fade is stepped by a timer that runs only while a
 * fade is in progress, and the page asks nothing of it while a song simply plays.
 */
(function () {
  "use strict";

  var BASE = (function () {
    try {
      var src = (document.currentScript && document.currentScript.src) || "";
      var at = src.indexOf("/js/music.js");
      if (at > 0) return src.slice(0, at) + "/audio/music/";
    } catch (e) { /* fall through */ }
    return "/static/audio/music/";
  })();

  var LISTS = {
    ambient: ["ambient-1", "ambient-2", "ambient-3", "ambient-4", "ambient-5",
              "alone-in-the-garden-1", "alone-in-the-garden-2", "alone-in-the-garden-3"],
    battle: ["against-all-odds-1", "against-all-odds-2", "against-all-odds-3",
             "epic-sad-1", "epic-sad-2"],
  };
  var BETWEEN_TRACKS = 4.0;     // seconds of crossfade from one song into the next
  var BETWEEN_MODES = 2.5;      // a fight starting or ending
  var BACK_TO_CALM_MS = 3000;   // a fight must stay over this long before the calm returns
  var SAVE_KEY = "pgm.music.at";

  var decks = [], live = 0;     // two <audio> elements; `live` is the one fading in
  var mode = null, order = { ambient: [], battle: [] }, lastPlayed = {};
  var started = false, wanted = false, calmTimer = 0, fadeTimer = 0;
  var urls = {};                // track id -> blob URL, for the decks that hold one

  function pref(key, dflt) {
    try {
      var p = window.PGMPrefs;
      if (!p || typeof p.get !== "function") return dflt;
      var v = p.get(key);
      return v === undefined || v === null ? dflt : v;
    } catch (e) { return dflt; }
  }
  function level() {
    if (pref("sound.mute", false) || !pref("music.on", true)) return 0;
    var m = Number(pref("sound.master", 0.8)), v = Number(pref("sound.music", 0.45));
    if (!isFinite(m)) m = 0.8;
    if (!isFinite(v)) v = 0.45;
    return Math.max(0, Math.min(1, m)) * Math.max(0, Math.min(1, v));
  }

  function deck(i) {
    if (!decks[i]) {
      var a = new Audio();
      a.preload = "auto";
      a.volume = 0;
      a.addEventListener("ended", function () { if (i === live) next(BETWEEN_TRACKS); });
      a.addEventListener("timeupdate", function () {
        // Start the next song while this one is still sounding, so they overlap.
        if (i !== live || !a.duration || a.dataset.leaving === "1") return;
        if (a.duration - a.currentTime <= BETWEEN_TRACKS) {
          a.dataset.leaving = "1";
          next(BETWEEN_TRACKS);
        }
      });
      decks[i] = a;
    }
    return decks[i];
  }

  function shuffled(list, avoid) {
    var out = list.slice();
    for (var i = out.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = out[i]; out[i] = out[j]; out[j] = t;
    }
    if (avoid && out.length > 1 && out[0] === avoid) { out.push(out.shift()); }
    return out;
  }
  function take(m) {
    if (!order[m].length) order[m] = shuffled(LISTS[m], lastPlayed[m]);
    var id = order[m].shift();
    lastPlayed[m] = id;
    return id;
  }

  function blobFor(id) {
    if (urls[id]) return Promise.resolve(urls[id]);
    return fetch(BASE + (LISTS.battle.indexOf(id) >= 0 ? "battle/" : "ambient/") + id + ".mp3")
      .then(function (r) { if (!r.ok) throw new Error("music " + r.status); return r.blob(); })
      .then(function (b) { urls[id] = URL.createObjectURL(b); return urls[id]; });
  }
  function release(id) {
    // Let a blob go once no deck plays it; a long session should not hold every song.
    if (!id || !urls[id]) return;
    if (decks.some(function (d) { return d && d.dataset.track === id; })) return;
    try { URL.revokeObjectURL(urls[id]); } catch (e) { /* */ }
    delete urls[id];
  }

  // One fade at a time: the incoming deck rises to the level, every other deck falls to
  // nothing and stops. Stepped by a timer that exists only for the fade.
  function fade(seconds) {
    clearInterval(fadeTimer);
    var start = Date.now(), dur = Math.max(0.05, seconds) * 1000;
    var from = decks.map(function (d) { return d ? d.volume : 0; });
    fadeTimer = setInterval(function () {
      var t = Math.min(1, (Date.now() - start) / dur), to = level();
      decks.forEach(function (d, i) {
        if (!d) return;
        var target = i === live ? to : 0;
        d.volume = Math.max(0, Math.min(1, from[i] + (target - from[i]) * t));
      });
      if (t >= 1) {
        clearInterval(fadeTimer);
        fadeTimer = 0;
        decks.forEach(function (d, i) {
          if (d && i !== live && !d.paused) {
            var gone = d.dataset.track;
            d.pause();
            d.dataset.track = "";
            release(gone);
          }
        });
      }
    }, 50);
  }

  function playOn(i, id, at, seconds) {
    var d = deck(i);
    d.dataset.leaving = "";
    return blobFor(id).then(function (url) {
      if (!wanted) return;
      d.src = url;
      d.dataset.track = id;
      d.volume = 0;
      var go = function () {
        if (at) { try { d.currentTime = at; } catch (e) { /* the start will do */ } }
        var p = d.play();
        if (p && typeof p.then === "function") {
          p.then(function () { fade(seconds); }, function () { waitForGesture(); });
        } else { fade(seconds); }
      };
      if (d.readyState >= 1) go();
      else d.addEventListener("loadedmetadata", go, { once: true });
    }).catch(function () { /* a missing track is silence, never an error on the page */ });
  }

  function next(seconds) {
    if (!wanted || !mode) return;
    live = live === 0 ? 1 : 0;
    playOn(live, take(mode), 0, seconds);
  }

  var gestureWait = false;
  function waitForGesture() {
    if (gestureWait) return;
    gestureWait = true;
    var kinds = ["pointerdown", "keydown", "touchstart"];
    var once = function () {
      kinds.forEach(function (k) { window.removeEventListener(k, once, true); });
      gestureWait = false;
      var d = decks[live];
      if (d && d.src && wanted) {
        var p = d.play();
        if (p && typeof p.then === "function") p.then(function () { fade(BETWEEN_MODES); }, function () { /* */ });
      }
    };
    kinds.forEach(function (k) { window.addEventListener(k, once, { capture: true, passive: true }); });
  }

  // Where the music was, for the next page: same playlist, same song, same second.
  function save() {
    try {
      var d = decks[live];
      if (!d || !d.dataset.track) return;
      sessionStorage.setItem(SAVE_KEY, JSON.stringify({
        mode: mode, track: d.dataset.track, at: d.currentTime || 0, order: order,
      }));
    } catch (e) { /* private window: the next page starts a fresh song */ }
  }
  function restore() {
    try { return JSON.parse(sessionStorage.getItem(SAVE_KEY) || "null"); }
    catch (e) { return null; }
  }

  function setMode(m) {
    if (!LISTS[m]) return;
    if (m === "ambient" && mode === "battle") {
      // The calm returns only once the fight has stayed over, so a turn that briefly
      // reads as no encounter does not flicker the music.
      if (calmTimer) return;
      calmTimer = setTimeout(function () { calmTimer = 0; switchTo("ambient"); }, BACK_TO_CALM_MS);
      return;
    }
    clearTimeout(calmTimer);
    calmTimer = 0;
    if (m !== mode) switchTo(m);
  }
  function switchTo(m) {
    mode = m;
    if (!wanted) return;
    live = live === 0 ? 1 : 0;
    playOn(live, take(m), 0, BETWEEN_MODES);
  }

  function start(m) {
    if (started) { if (m) setMode(m); return; }
    started = true;
    wanted = true;
    var was = restore();
    if (was && was.order) {
      ["ambient", "battle"].forEach(function (k) {
        if (Array.isArray(was.order[k])) {
          order[k] = was.order[k].filter(function (id) { return LISTS[k].indexOf(id) >= 0; });
        }
      });
    }
    var want = m || (was && LISTS[was.mode] ? was.mode : "ambient");
    mode = want;
    if (was && was.mode === want && LISTS[want].indexOf(was.track) >= 0) {
      lastPlayed[want] = was.track;
      playOn(live, was.track, Number(was.at) || 0, 1.5);
    } else {
      playOn(live, take(want), 0, 1.5);
    }
  }

  function stop() {
    wanted = false;
    clearTimeout(calmTimer);
    clearInterval(fadeTimer);
    decks.forEach(function (d) { if (d) { d.pause(); d.volume = 0; } });
  }

  // Volume follows the settings live; the save follows the page out.
  try {
    var p = window.PGMPrefs;
    if (p && typeof p.on === "function") {
      var relevel = function () {
        if (fadeTimer) return;           // the fade reads the level itself every step
        var d = decks[live];
        if (d && !d.paused) d.volume = level();
      };
      ["sound.master", "sound.music", "sound.mute", "music.on"].forEach(function (k) { p.on(k, relevel); });
    }
  } catch (e) { /* no prefs: the defaults stand */ }
  window.addEventListener("pagehide", save);
  window.addEventListener("beforeunload", save);
  setInterval(save, 5000);

  window.Music = {
    start: start,
    stop: stop,
    mode: setMode,
    playing: function () {
      var d = decks[live];
      return d && !d.paused ? {
        mode: mode, track: d.dataset.track, at: d.currentTime, volume: d.volume,
        others: decks.filter(function (x, i) { return x && i !== live && !x.paused; }).length,
      } : null;
    },
    lists: function () { return JSON.parse(JSON.stringify(LISTS)); },
  };
})();
