function fetchPendingAccounts() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: "command=account_get_pending"
  })
  .then(res => res.json())
  .then(data => {
    const container = document.getElementById("pendingContainer");
    const emptyState = document.getElementById("emptyState");
    container.innerHTML = "";
    
    if (data.status === 200 && data.accounts.length > 0) {
      emptyState.classList.add("d-none");
      data.accounts.forEach(acc => {
        const col = document.createElement("div");
        col.className = "col-12 col-lg-6 mb-4";
        col.innerHTML = `
          <div class="card bg-dark border border-white border-opacity-10 h-100 shadow-sm hover-shadow">
            <div class="card-body p-4">
              <div class="d-flex justify-content-between align-items-center mb-3">
                <h6 class="fw-bold mb-0 text-white"><i class="fas fa-envelope text-info me-2"></i> ${acc.email}</h6>
                <span class="badge badge-warning me-2">AWAITING LINK</span>
              </div>
              <div class="input-group mb-2">
                <input type="text" class="form-control bg-dark text-white border-white border-opacity-25 py-2" id="verify-link-${acc.id}" placeholder="Paste MEGA confirmation link here...">
                <button class="btn btn-info px-3" onclick="confirmAccount(${acc.id})" id="btn-verify-${acc.id}">
                    <i class="fas fa-check-circle me-1"></i> Verify
                </button>
              </div>
              <p class="text-muted mb-0 truncate-small">
                 <i class="fas fa-info-circle opacity-50 me-1"></i> Paste the full URL from the MEGA verification email.
              </p>
            </div>
          </div>
        `;
        container.appendChild(col);
      });
    } else {
      emptyState.classList.remove("d-none");
    }
  })
  .catch(err => console.error("Error fetching pending accounts:", err));
}

function confirmAccount(accountId) {
  const linkInput = document.getElementById(`verify-link-${accountId}`);
  const verifyBtn = document.getElementById(`btn-verify-${accountId}`);
  const link = encodeURIComponent(linkInput.value.trim());

  if (!linkInput.value.trim()) {
    showToast("⚠️ Please paste a valid verification link.", "bg-warning");
    return;
  }

  // Visual feedback during processing
  verifyBtn.disabled = true;
  verifyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Processing...';
  linkInput.disabled = true;

  showToast(`🔐 Processing verification for ID #${accountId}...`, "bg-info");
  
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=account_confirm:${accountId}|${link}`
  })
  .then(res => res.json())
  .then(data => {
    if (data.status === 200) {
      showToast("✅ Registration finalized!", "bg-success");
      fetchPendingAccounts();
      if (window.checkPendingAccounts) window.checkPendingAccounts();
    } else {
      showToast("❌ " + data.message, "bg-danger");
      // Re-enable on failure
      verifyBtn.disabled = false;
      verifyBtn.innerHTML = '<i class="fas fa-check-circle me-1"></i> Verify';
      linkInput.disabled = false;
    }
  })
  .catch(err => {
    showToast("❌ Connection error during verification.", "bg-danger");
    verifyBtn.disabled = false;
    verifyBtn.innerHTML = '<i class="fas fa-check-circle me-1"></i> Verify';
    linkInput.disabled = false;
  });
}

document.addEventListener("DOMContentLoaded", fetchPendingAccounts);
