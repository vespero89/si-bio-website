// Progressive enhancement of the home row of wines.
// Without this script every bottle is a plain link to its wine page and the arrows stay hidden.
// With it: a click on a bottle opens a native <dialog> filled from <template id="wine-<slug>">,
// rendered by the server in the home page; the arrows scroll the row.
// Esc closes the dialog (native), as do the close button and a click on the backdrop.
(function () {
  var rail = document.querySelector("[data-rail]");
  if (!rail) return;

  // Arrows: shown only when the script runs
  document.querySelectorAll("[data-rail-arrows]").forEach(function (box) {
    box.hidden = false;
    box.addEventListener("click", function (event) {
      var button = event.target.closest("[data-rail-step]");
      if (!button) return;
      var step = Number(button.getAttribute("data-rail-step")) || 1;
      var smooth = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      rail.scrollBy({ left: step * rail.clientWidth * 0.7, behavior: smooth ? "smooth" : "auto" });
    });
  });

  if (typeof HTMLDialogElement !== "function") return; // very old browser: links keep working

  var dialog = document.createElement("dialog");
  dialog.className = "wine-dialog";
  document.body.appendChild(dialog);
  var opener = null;

  function close() {
    if (dialog.open) dialog.close();
  }

  dialog.addEventListener("close", function () {
    document.body.classList.remove("has-dialog");
    dialog.replaceChildren();
    if (opener) opener.focus();
  });

  // A click on the backdrop lands on the dialog element itself
  dialog.addEventListener("click", function (event) {
    if (event.target === dialog || event.target.closest("[data-close]")) close();
  });

  rail.addEventListener("click", function (event) {
    var link = event.target.closest("a[data-wine]");
    if (!link || event.defaultPrevented || event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return; // new tab and the like
    var template = document.getElementById("wine-" + link.getAttribute("data-wine"));
    if (!template) return; // no presentation for this wine: follow the link
    event.preventDefault();
    opener = link;
    dialog.replaceChildren(template.content.cloneNode(true));
    var title = dialog.querySelector("h2");
    if (title) dialog.setAttribute("aria-labelledby", title.id);
    document.body.classList.add("has-dialog");
    dialog.showModal();
    var sheet = dialog.querySelector(".dlg-sheet");
    if (sheet) sheet.scrollTop = 0;
    if (title) title.focus({ preventScroll: true });
  });
})();
