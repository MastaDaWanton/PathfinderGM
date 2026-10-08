/* The player's own preferences for how the app feels: sound levels, Steady mode and
 * Flourishes. `window.PGMPrefs` (docs/herbalism-contracts.md §5.3).
 *
 *   PGMPrefs.get(key)          -> the stored value, or the default
 *   PGMPrefs.set(key, value)   -> the value actually kept (clamped, coerced)
 *   PGMPrefs.on(key, fn)       -> fn(value, key) on every change; returns an off()
 *
 * Kept in localStorage, one entry per key ("pgm.pref.<key>", JSON), because these belong
 * to the machine and the window rather than to a campaign: a quiet room is quiet whatever
 * game is open. One entry per key rather than one blob so the `storage` event (fired in
 * every OTHER window of the same origin when one writes) names the key that changed, and
 * the table and the bench in two windows agree without polling.
 *
 * Every touch of storage is in try/catch, and a failure falls back to an in-memory copy.
 * localStorage throws, rather than returning null, when it is disabled, full, or blocked
 * by a privacy setting; a settings helper that threw would take the page's sound and the
 * bench's games down with it over a preference.
 *
 * No third-party code, as everywhere in play/static/js.
 */
(function () {
  "use strict";

  var PREFIX = "pgm.pref.";

  function reducedMotion() {
    try {
      return !!(window.matchMedia &&
                window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch (e) { return false; }
  }

  // The defaults. `flourishes` is a function because it follows the OS: Short is chosen
  // automatically when the system asks for reduced motion (UI plan §6.9), and only until
  // the player picks one themselves.
  var DEFAULTS = {
    "steady": false,
    "flourishes": function () { return reducedMotion() ? "short" : "full"; },
    "sound.master": 0.8,
    "sound.ui": 0.6,
    "sound.dice": 0.8,
    "sound.bench": 0.8,
    // The Blacksmithing bench's anvil, bellows and quench (sound.js's `forge` bus,
    // blacksmithing UI plan §6.8), at the herb bench's level so neither bench is louder.
    "sound.forge": 0.8,
    // The Enchanting circle's chalk, bowls and phials (sound.js's `enchant` bus,
    // enchanting UI plan §11), at the other benches' level.
    "sound.enchant": 0.8,
    // The Alchemy bench's glassware, bubbles and flame (sound.js's `alchemy` bus, alchemy
    // UI plan §11), at the other benches' level.
    "sound.alchemy": 0.8,
    // The Leatherworking bench's knife, vat and kettle (sound.js's `leather` bus,
    // leatherworking UI plan §11), at the other benches' level.
    "sound.leather": 0.8,
    "sound.ambience": 0.4,
    "sound.combat": 0.7,
    "sound.mute": false,
    // The owner's background music (music.js, 2026-10-02): its own level under master,
    // and an on/off the table's Music button flips without touching the level.
    "sound.music": 0.45,
    "music.on": true,
  };

  function fallback(key) {
    var d = DEFAULTS[key];
    return typeof d === "function" ? d() : d;
  }

  // What a stored value may be. A slider writes a string, a hand-edited localStorage can
  // hold anything, and a volume of 7 or "loud" must not reach a gain node.
  function coerce(key, v) {
    if (key === "steady" || key === "sound.mute" || key === "music.on") {
      return v === true || v === "true" || v === 1 || v === "1";
    }
    if (key === "flourishes") {
      return v === "short" ? "short" : v === "full" ? "full" : fallback(key);
    }
    if (key.indexOf("sound.") === 0) {
      var n = Number(v);
      if (!isFinite(n)) return fallback(key);
      return Math.max(0, Math.min(1, n));
    }
    return v;
  }

  var memory = {};      // what was set when storage would not take it
  var listeners = {};   // key -> [fn]

  function readStored(key) {
    try {
      var raw = window.localStorage.getItem(PREFIX + key);
      if (raw === null || raw === undefined) return undefined;
      return JSON.parse(raw);
    } catch (e) {
      return undefined;
    }
  }

  function get(key) {
    try {
      if (Object.prototype.hasOwnProperty.call(memory, key)) return memory[key];
      var v = readStored(key);
      if (v === undefined) {
        // The old dice-only switch (dice3d.js, `pfgm.dice.mute`) still means what it
        // said: a player who silenced the dice before there was a Settings slider keeps
        // silent dice until they move the slider.
        if (key === "sound.dice") {
          try {
            if (window.localStorage.getItem("pfgm.dice.mute") === "1") return 0;
          } catch (e) { /* storage blocked: the default stands */ }
        }
        return fallback(key);
      }
      return coerce(key, v);
    } catch (e) {
      return fallback(key);
    }
  }

  function fire(key, value) {
    var list = (listeners[key] || []).slice();
    for (var i = 0; i < list.length; i++) {
      try { list[i](value, key); } catch (e) { /* one bad listener stops nobody else */ }
    }
  }

  function set(key, value) {
    try {
      var v = coerce(String(key), value);
      var before = get(key);
      try {
        window.localStorage.setItem(PREFIX + key, JSON.stringify(v));
        delete memory[key];
      } catch (e) {
        memory[key] = v;   // storage refused it: this window still remembers
      }
      if (before !== v) fire(key, v);
      return v;
    } catch (e) {
      return value;
    }
  }

  function on(key, fn) {
    try {
      if (typeof fn !== "function") return function () {};
      (listeners[key] = listeners[key] || []).push(fn);
      return function off() {
        try {
          var list = listeners[key] || [];
          var i = list.indexOf(fn);
          if (i >= 0) list.splice(i, 1);
        } catch (e) { /* nothing to undo */ }
      };
    } catch (e) {
      return function () {};
    }
  }

  // Another window wrote a preference: tell this window's listeners. `e.key` is null when
  // the other window cleared all of storage, and then every key may have changed.
  try {
    window.addEventListener("storage", function (e) {
      try {
        if (e.key === null) {
          Object.keys(DEFAULTS).forEach(function (k) { fire(k, get(k)); });
          return;
        }
        if (typeof e.key !== "string" || e.key.indexOf(PREFIX) !== 0) return;
        var key = e.key.slice(PREFIX.length);
        fire(key, get(key));
      } catch (err) { /* a malformed event changes nothing */ }
    });
  } catch (e) { /* no window events: nothing to sync with */ }

  // The OS changing its reduced-motion setting moves the default Flourishes with it, as
  // long as the player has not chosen one.
  try {
    var mq = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
    var follow = function () {
      if (readStored("flourishes") === undefined && !("flourishes" in memory)) {
        fire("flourishes", get("flourishes"));
      }
    };
    if (mq && mq.addEventListener) mq.addEventListener("change", follow);
    else if (mq && mq.addListener) mq.addListener(follow);
  } catch (e) { /* no media queries: the default is read fresh on every get anyway */ }

  window.PGMPrefs = {
    get: get,
    set: set,
    on: on,
    keys: function () { return Object.keys(DEFAULTS); },
    defaults: function () {
      var out = {};
      Object.keys(DEFAULTS).forEach(function (k) { out[k] = fallback(k); });
      return out;
    },
  };
})();
