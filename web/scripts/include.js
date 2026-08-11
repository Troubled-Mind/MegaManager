document.addEventListener("DOMContentLoaded", () => {
  const savedTheme = localStorage.getItem('mm-theme') || 'dark';
  document.documentElement.setAttribute('data-mdb-theme', savedTheme);
  document.documentElement.setAttribute('data-bs-theme', savedTheme);

  const uiOverlay = document.createElement("div");
  uiOverlay.id = "globalSystemOverlay";
  uiOverlay.innerHTML = `
    <div id="bootSpinner" style="display:none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 9999; flex-direction: column; align-items: center; justify-content: center; backdrop-filter: blur(5px);">
      <div class="spinner-border text-info mb-3" style="width: 3rem; height: 3rem;" role="status"></div>
      <h4 class="fw-bold text-white mb-1">MegaManager Is Initialising</h4>
      <p class="text-info small opacity-75">Syncing accounts and verifying cloud sessions...</p>
    </div>
    <div id="updateBanner" style="display:none; position: fixed; top: 0; left: 0; width: 100%; z-index: 9998; background: #38bdf8; color: #05202b; padding: 10px 16px; text-align: center; font-weight: 600;">
      <span id="updateBannerText"></span>
      <button id="updateBannerDismiss" style="margin-left: 12px; border: none; background: transparent; color: #05202b; font-weight: 700; cursor: pointer;">&times;</button>
    </div>
  `;
  document.body.appendChild(uiOverlay);

  document.getElementById("updateBannerDismiss").addEventListener("click", () => {
    document.getElementById("updateBanner").style.display = "none";
    sessionStorage.setItem("mm-update-dismissed", "1");
  });

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

        checkPendingAccounts();
        setInterval(checkPendingAccounts, 15000);
      });
  }
});

window.pollSystemStatus = function () {
  fetch("/api/status")
    .then(res => res.json())
    .then(state => {
      const bootSpinner = document.getElementById("bootSpinner");
      if (bootSpinner) {
        bootSpinner.style.display = state.booting ? "flex" : "none";
      }

      const uploadBadge = document.getElementById("globalUploadBadge");
      const totalTransfers = (state.active_count || 0) + (state.queued_count || 0);
      if (uploadBadge) {
        if (totalTransfers > 0) {
          uploadBadge.textContent = totalTransfers;
          uploadBadge.style.display = "inline-block";
        } else {
          uploadBadge.style.display = "none";
        }
      }

      const updateBanner = document.getElementById("updateBanner");
      if (updateBanner && state.update_applied && sessionStorage.getItem("mm-update-dismissed") !== "1") {
        document.getElementById("updateBannerText").textContent =
          `Updated to v${state.update_version} - restart the server to apply it.`;
        updateBanner.style.display = "block";
      }
    })
    .catch(err => console.error("Status polling failed:", err));
}

window.checkPendingAccounts = function () {
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

window.toggleTheme = function () {
  const current = document.documentElement.getAttribute('data-mdb-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  
  document.documentElement.setAttribute('data-mdb-theme', next);
  document.documentElement.setAttribute('data-bs-theme', next); // Support newer Bootstrap versions
  localStorage.setItem('mm-theme', next);
};

window.initFilterPanel = function (toggleId, panelId, chevronId) {
  const toggle = document.getElementById(toggleId);
  const panel = document.getElementById(panelId);
  const chevron = chevronId ? document.getElementById(chevronId) : null;
  if (!toggle || !panel) return;

  const setOpen = (open) => {
    panel.classList.toggle("show", open);
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    if (chevron) chevron.classList.toggle("rotated", open);
  };

  toggle.addEventListener("click", () => setOpen(!panel.classList.contains("show")));
  toggle.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setOpen(!panel.classList.contains("show"));
    }
  });
};

window.updateFilterBadge = function (badgeId, count) {
  const badge = document.getElementById(badgeId);
  if (!badge) return;
  if (count > 0) {
    badge.textContent = count;
    badge.classList.remove("d-none");
  } else {
    badge.classList.add("d-none");
  }
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
