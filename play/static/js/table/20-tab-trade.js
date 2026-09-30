// The play table, part 20 (the Trade tab). Classic script, sharing one global scope.
//
// The tab is the one door to the counter: the footer's Trade button went with the
// rebuild (the mock README, "Also: the footer's duplicate Trade button is gone"). Stage
// 1 carries today's trade window (06, I7's design: what you carry, the deal, their
// wares) into the tab as it is. Where nobody keeps a counter the tab still opens, and
// says why in the words the old button's greyed title used, rather than being a tab that
// does nothing (the owner's rule: a visible reason where a thing is absent).
//
// A purchase said in words ("I buy a coil of rope") opens the counter through 04's
// `openTrade(s.trade.want)`, which comes to this tab by itself (06).

Shell.tab("trade", {
  enter() {
    const who = (STATE && STATE.merchant) || "";
    const none = document.getElementById("trade-none");
    if (none) none.hidden = !!who;
    if (who) { openTrade(); return; }
    const why = document.getElementById("trade-none-why");
    if (why) why.textContent = NO_COUNTER;
  },
  leave() {
    const none = document.getElementById("trade-none");
    if (none) none.hidden = true;
    leaveCounter();
  },
});

document.addEventListener("keydown", e => {
  // Esc from the page that says there is no counter goes back to the Table, as Esc from
  // the counter itself does (06).
  if (e.key !== "Escape" || Shell.mode() !== "trade") return;
  if (!$("#tradepanel").classList.contains("on")) Shell.show("table");
});
