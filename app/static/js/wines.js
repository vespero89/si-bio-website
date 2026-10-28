// Progressive enhancement of the row of wines: after HTMX swaps in another wine, focus moves to its
// title so keyboard and screen reader users land on the new content.
document.addEventListener("htmx:afterSettle", function (event) {
  var stage = document.getElementById("wine-stage");
  if (!stage || event.detail.target !== stage) return;
  var title = stage.querySelector("[tabindex='-1']");
  if (title) title.focus();
});
