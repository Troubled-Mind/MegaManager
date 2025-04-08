document.addEventListener("DOMContentLoaded", () => {
  const navbarTarget = document.getElementById("navbarLinks");
  if (!navbarTarget) {
    console.warn("navbarLinks element not found on this page.");
    return;
  }

  fetch("navbar/links.html")
    .then((res) => res.text())
    .then((html) => {
      navbarTarget.innerHTML = html;

      // Highlight current page
      const currentPage = window.location.pathname
        .split("/")
        .pop()
        .replace(".html", "");
      const links = navbarTarget.querySelectorAll("a[data-page]");

      links.forEach((link) => {
        if (link.dataset.page === currentPage) {
          link.classList.add("active", "text-primary");
        }
      });
    })
    .catch((err) => console.error("Failed to load navbar links:", err));
});

window.showToast = function (message, color = "bg-success") {
  const toastEl = document.getElementById("universalToast");
  const toastBody = document.getElementById("universalToastBody");

  // Reset any old color classes
  toastEl.className = "toast fade";
  toastBody.className = "toast-body text-white";

  // Apply new color
  toastEl.classList.add(color);
  toastBody.textContent = message;

  // Show the toast
  const toast = new mdb.Toast(toastEl);
  toast.show();
};
