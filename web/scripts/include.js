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
