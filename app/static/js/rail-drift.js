// Progressive enhancement of the home row of wines: the whole row (movement panels and cards, in order)
// drifts to the left, slowly and without end. Without this script (or with prefers-reduced-motion) the
// row stays a plain scroll-snap row.
// The motion is a CSS animation of the row's transform (compositor, no scrollLeft): the script only
// clones the sequence once (clones are aria-hidden and not focusable, a click on one opens the same
// dialog) and sets three custom properties: the length of one turn, its duration (a card width every
// SECONDS_PER_CARD) and the phase. CSS pauses it on hover and while a dialog is open. This script
// pauses it on keyboard focus inside the row and with the Pause button; paused, the row is the normal
// scrolling row again (swipe, arrows) and Play resumes from where it is.
(function () {
  var SECONDS_PER_CARD = 7;
  var rail = document.querySelector("[data-rail]");
  var toggle = document.querySelector("[data-rail-toggle]");
  if (!rail || !toggle) return;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (reduce.matches) return;

  var originals = Array.prototype.slice.call(rail.children);
  var cards = rail.querySelectorAll("li.wine");
  if (cards.length < 2) return;
  var arrows = document.querySelectorAll("[data-rail-arrows]");

  var clip = document.createElement("div");
  clip.className = "rail-clip";
  rail.parentNode.insertBefore(clip, rail);
  clip.appendChild(rail);
  rail.classList.add("is-enhanced");

  var clones = [];
  var period = 1; // px of one turn: from an item to its clone
  var duration = 1; // seconds of one turn
  var autoPaused = false;

  function addClones() {
    originals.forEach(function (item) {
      var clone = item.cloneNode(true);
      clone.setAttribute("aria-hidden", "true");
      clone.setAttribute("data-clone", "");
      clone.querySelectorAll("a").forEach(function (a) { a.setAttribute("tabindex", "-1"); });
      rail.appendChild(clone);
      clones.push(clone);
    });
  }

  function removeClones() {
    clones.forEach(function (clone) { clone.remove(); });
    clones = [];
  }

  function drifting() {
    return rail.classList.contains("is-drifting");
  }

  // Distance the row has travelled (px), read from the running animation
  function travelled() {
    return -new DOMMatrixReadOnly(window.getComputedStyle(rail).transform).m41;
  }

  function setPhase(distance) {
    var phase = (((distance % period) + period) % period) / period;
    rail.style.setProperty("--drift-delay", (-phase * duration).toFixed(3) + "s");
  }

  // One set of clones gives the period; more sets if the window is wider than one turn
  function build() {
    removeClones();
    addClones();
    period = clones[0].offsetLeft - originals[0].offsetLeft;
    var step = cards[1].offsetLeft - cards[0].offsetLeft; // a card and its gap
    duration = (period / step) * SECONDS_PER_CARD;
    for (var more = Math.ceil(clip.clientWidth / period) - 1; more > 0; more--) addClones();
    rail.style.setProperty("--drift-distance", period + "px");
    rail.style.setProperty("--drift-duration", duration.toFixed(3) + "s");
  }

  function play(distance) {
    rail.scrollTo({ left: 0, behavior: "instant" });
    rail.classList.add("is-drifting");
    setPhase(distance);
    arrows.forEach(function (box) { box.hidden = true; });
    toggle.setAttribute("aria-pressed", "false");
  }

  // Back to the scrolling row, at the place where the drift stopped
  function pause() {
    if (!drifting()) return;
    var distance = travelled();
    rail.classList.remove("is-drifting");
    var padding = parseFloat(window.getComputedStyle(rail).paddingLeft) || 0;
    rail.scrollTo({ left: distance + padding, behavior: "instant" });
    arrows.forEach(function (box) { box.hidden = false; });
    toggle.setAttribute("aria-pressed", "true");
  }

  function resume() {
    var padding = parseFloat(window.getComputedStyle(rail).paddingLeft) || 0;
    play(rail.scrollLeft - padding);
  }

  toggle.addEventListener("click", function () {
    autoPaused = false;
    if (drifting()) pause();
    else resume();
  });

  // Keyboard focus inside the row: stop, and go on when it leaves (a click is not a keyboard focus)
  rail.addEventListener("focusin", function (e) {
    if (drifting() && e.target.matches(":focus-visible")) {
      autoPaused = true;
      pause();
      e.target.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
  });
  rail.addEventListener("focusout", function (e) {
    if (autoPaused && !rail.contains(e.relatedTarget)) {
      autoPaused = false;
      resume();
    }
  });

  var resizing = 0;
  window.addEventListener("resize", function () {
    window.clearTimeout(resizing);
    resizing = window.setTimeout(function () {
      var running = drifting();
      var distance = running ? travelled() : 0;
      build();
      if (running) setPhase(distance);
    }, 150);
  });

  // The visitor asks for less motion while the page is open: stop for good
  reduce.addEventListener("change", function () {
    if (!reduce.matches) return;
    pause();
    removeClones();
    toggle.hidden = true;
  });

  build();
  toggle.hidden = false;
  // Start where the plain row is: the first item at the left margin of the page
  play(-(parseFloat(window.getComputedStyle(rail).paddingLeft) || 0));
})();
