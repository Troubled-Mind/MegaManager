document.addEventListener("DOMContentLoaded", () => {
  // Initialize theme
  const savedTheme = localStorage.getItem('mm-theme') || 'dark';
  document.documentElement.setAttribute('data-mdb-theme', savedTheme);

  // Inject Global UI Elements (Spinner/Lock Overlay)
  const uiOverlay = document.createElement("div");
  uiOverlay.id = "globalSystemOverlay";
  uiOverlay.innerHTML = `
    <div id="bootSpinner" style="display:none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 9999; flex-direction: column; align-items: center; justify-content: center; backdrop-filter: blur(5px);">
      <div class="spinner-border text-info mb-3" style="width: 3rem; height: 3rem;" role="status"></div>
      <h4 class="fw-bold text-white mb-1">MegaManager Is Initializing</h4>
      <p class="text-info small opacity-75">Syncing accounts and verifying cloud sessions...</p>
    </div>
    <div id="uploadLockScreen" style="display:none; position: fixed; bottom: 20px; left: 20px; z-index: 9998; max-width: 300px;">
      <div class="alert alert-warning shadow-lg border-0 d-flex align-items-center gap-3 py-2 px-3 animate__animated animate__fadeInUp">
        <div class="spinner-grow spinner-grow-sm text-warning" role="status"></div>
        <div class="small fw-bold">Account tasks locked while uploads are active.</div>
      </div>
    </div>
  `;
  document.body.appendChild(uiOverlay);

  // Start Status Polling
  pollSystemStatus();
  setInterval(pollSystemStatus, 3000);

  const navbarTarget = document.getElementById("navbarLinks");
  if (navbarTarget) {
    fetch("navbar/links.html")
      .then((res) => res.text())
      .then((html) => {
        navbarTarget.innerHTML = html;
        const currentPage = window.location.pathname.split("/").pop().replace(".html", "") || 'index';
        const links = navbarTarget.querySelectorAll(".nav-link[data-page]");
        links.forEach((link) => {
          if (link.dataset.page === currentPage) link.classList.add("active");
        });
        
        // Check for pending accounts
        checkPendingAccounts();
        setInterval(checkPendingAccounts, 15000);
      });
  }
});

window.pollSystemStatus = function() {
  fetch("/api/status")
    .then(res => res.json())
    .then(state => {
      // 1. Boot Spinner Logic
      const bootSpinner = document.getElementById("bootSpinner");
      if (bootSpinner) {
        bootSpinner.style.display = state.booting ? "flex" : "none";
      }

      // 2. Upload Lock Logic
      const lockUi = document.getElementById("uploadLockScreen");
      if (lockUi) {
        lockUi.style.display = state.uploads_active ? "block" : "none";
      }

      // 3. Disable restricted buttons (Verify, Register, Delete Account)
      const restrictedButtons = document.querySelectorAll('button[onclick*="Verify"], a[href*="verify"], button[onclick*="Register"], button[onclick*="DeleteAccount"]');
      restrictedButtons.forEach(btn => {
        if (state.uploads_active) {
          btn.classList.add("disabled");
          btn.setAttribute("disabled", "true");
          btn.title = "Locked: Ongoing transfers detected.";
        } else if (!state.booting) {
          btn.classList.remove("disabled");
          btn.removeAttribute("disabled");
          // Keep original title if it exists, or clear it
        }
      });
    })
    .catch(err => console.error("Status polling failed:", err));
}

window.checkPendingAccounts = function() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: "command=account_get_pending"
  })
  .then(res => res.json())
  .then(data => {
    const navItem = document.getElementById("verifyNavLink");
    const badge = document.getElementById("pendingVerifyBadge");
    if (!navItem || !badge) return;

    if (data.status === 200 && data.accounts.length > 0) {
      navItem.style.display = "block";
      badge.textContent = data.accounts.length;
      badge.style.display = "block";
    } else {
      navItem.style.display = "none";
    }
  })
  .catch(err => console.error("Verify check failed:", err));
}

window.toggleTheme = function() {
  const current = document.documentElement.getAttribute('data-mdb-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-mdb-theme', next);
  localStorage.setItem('mm-theme', next);
};

window.showToast = function (message, color = "bg-success") {
  const toastEl = document.getElementById("universalToast");
  const toastBody = document.getElementById("universalToastBody");
  if (!toastEl || !toastBody) return;
  toastEl.className = `toast fade ${color} border-0`;
  toastBody.textContent = message;
  const t = new mdb.Toast(toastEl, { delay: 8000, autohide: true });
  t.show();
};
