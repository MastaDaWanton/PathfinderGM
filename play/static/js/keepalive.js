/**
 * "This window is still open." Loaded by every page, and it does nothing else.
 *
 * The packaged exe has no way to learn that the browser it opened has gone: a WSGI
 * server is told that no request arrived, never that its last client left, and a player
 * who is reading looks identical. Measured 2026-09-01 — the exe was double-clicked at
 * 10:35, the browser closed at 12:01, and the server was still holding port 8917 and an
 * exclusive handle on its own file four hours later, which is what broke the next build
 * with WinError 5. `pathfindergm/liveness.py` carries the full measurement and the
 * designs that were refused.
 *
 * Deliberately unconditional. It keeps beating while the tab is hidden, minimised or
 * behind another app, because those are all things a player does mid-session and none of
 * them mean the game is over. Only the page actually going away stops it — which is the
 * whole signal, and the reason there is no `visibilitychange` handler here.
 *
 * Chrome throttles timers in a hidden tab to once per minute after five minutes, so the
 * fifteen-second interval below is a floor rather than a promise. The server's grace is
 * 180 seconds precisely so that a throttled window still counts as open.
 */
(function () {
  var every = 15000;
  var timer = null;

  function beat() {
    // `no-store` on both sides: a cached 200 would keep the page happy while the server
    // heard nothing, and silence is the only thing this file is for.
    fetch('/api/alive', { cache: 'no-store', credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        // The server owns the interval, so the two halves cannot drift apart when one
        // of them is edited. A nonsense answer is ignored rather than trusted.
        if (d && typeof d.every === 'number' && d.every >= 1 && d.every <= 3600) {
          var wanted = d.every * 1000;
          if (wanted !== every) {
            every = wanted;
            clearInterval(timer);
            timer = setInterval(beat, every);
          }
        }
      })
      .catch(function () {
        // The server is gone, or a turn is saturating it. Neither is this file's
        // business: the next beat is already scheduled, and a console error every
        // fifteen seconds would bury the ones that matter.
      });
  }

  // The interval is armed BEFORE the first beat, not after. The other order leaves a
  // window where the first response can come back, reschedule, and then be overwritten
  // by the outer assignment — two live timers, one of them unreachable and unstoppable.
  timer = setInterval(beat, every);
  beat();
})();
