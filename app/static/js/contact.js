// Progressive enhancement: adds a "Copy" button next to the written address. Without this
// script the address and the mailto link are all there is.
(function () {
  document.querySelectorAll(".contact-block").forEach(function (block) {
    var email = block.querySelector(".contact-email");
    if (!email || !navigator.clipboard || block.querySelector(".copy-button")) return;
    var button = document.createElement("button");
    button.type = "button";
    button.className = "copy-button";
    button.textContent = block.dataset.copy;
    var live = document.createElement("span");
    live.className = "copy-live";
    live.setAttribute("aria-live", "polite");
    button.addEventListener("click", function () {
      navigator.clipboard.writeText(email.textContent.trim()).then(function () {
        button.textContent = block.dataset.copied;
        live.textContent = block.dataset.copied;
        setTimeout(function () {
          button.textContent = block.dataset.copy;
          live.textContent = "";
        }, 2000);
      });
    });
    email.parentNode.appendChild(document.createTextNode(" "));
    email.parentNode.appendChild(button);
    email.parentNode.appendChild(live);
  });
})();
