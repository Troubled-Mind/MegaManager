function fetchPendingAccounts() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: "command=account_get_pending",
  })
    .then((res) => res.json())
    .then((data) => {
      const container = document.getElementById("pendingContainer");
      const emptyState = document.getElementById("emptyState");
      container.innerHTML = "";

      const bulkCard = document.getElementById("bulkVerifyCard");
      if (bulkCard) {
        if (data.status === 200 && data.accounts.length > 1) {
          bulkCard.classList.remove("d-none");
        } else {
          bulkCard.classList.add("d-none");
        }
      }

      if (data.status === 200 && data.accounts.length > 0) {
        emptyState.classList.add("d-none");
        data.accounts.forEach((acc) => {
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
    .catch((err) => console.error("Error fetching pending accounts:", err));
}

function confirmAccount(accountId) {
  const linkInput = document.getElementById(`verify-link-${accountId}`);
  const verifyBtn = document.getElementById(`btn-verify-${accountId}`);
  const link = encodeURIComponent(linkInput.value.trim());

  if (!linkInput.value.trim()) {
    showToast("Please paste a valid verification link.", "bg-warning");
    return;
  }

  verifyBtn.disabled = true;
  verifyBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Processing...';
  linkInput.disabled = true;

  showToast(`Processing verification for ID #${accountId}...`, "bg-info");

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=account_confirm:${accountId}|${link}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast("Registration finalized!", "bg-success");
        fetchPendingAccounts();
        if (window.checkPendingAccounts) window.checkPendingAccounts();
      } else {
        showToast("" + data.message, "bg-danger");
        verifyBtn.disabled = false;
        verifyBtn.innerHTML = '<i class="fas fa-check-circle me-1"></i> Verify';
        linkInput.disabled = false;
      }
    })
    .catch((err) => {
      showToast("Connection error during verification.", "bg-danger");
      verifyBtn.disabled = false;
      verifyBtn.innerHTML = '<i class="fas fa-check-circle me-1"></i> Verify';
      linkInput.disabled = false;
    });
}

document.addEventListener("DOMContentLoaded", () => {
  fetchPendingAccounts();

  // Setup PDF upload drag & drop and click handlers
  const fileInput = document.getElementById("pdfFileInput");
  const dropzone = document.getElementById("dropzone");
  const uploadStatusText = document.getElementById("uploadStatusText");
  const processingState = document.getElementById("processingState");
  const resultsSection = document.getElementById("resultsSection");
  const resultsTableBody = document.getElementById("resultsTableBody");
  const resultsBadges = document.getElementById("resultsBadges");

  if (!fileInput || !dropzone) return;

  ["dragenter", "dragover"].forEach((eventName) => {
    dropzone.addEventListener(
      eventName,
      (e) => {
        e.preventDefault();
        dropzone.style.borderColor = "#38bdf8";
        dropzone.style.background = "rgba(56, 189, 248, 0.05)";
      },
      false,
    );
  });

  ["dragleave", "drop"].forEach((eventName) => {
    dropzone.addEventListener(
      eventName,
      (e) => {
        e.preventDefault();
        dropzone.style.borderColor = "rgba(255, 255, 255, 0.15)";
        dropzone.style.background = "rgba(255, 255, 255, 0.02)";
      },
      false,
    );
  });

  fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      handlePDFUpload(file);
    }
  });

  function handlePDFUpload(file) {
    if (file.type !== "application/pdf" && !file.name.endsWith(".pdf")) {
      showToast("Only PDF files are supported.", "bg-warning");
      return;
    }

    dropzone.classList.add("d-none");
    processingState.classList.remove("d-none");
    resultsSection.classList.add("d-none");

    const formData = new FormData();
    formData.append("file", file);

    fetch("/api/upload-pdf", {
      method: "POST",
      body: formData,
    })
      .then((res) => {
        if (res.status === 401) {
          throw new Error("Authentication failed. Please login again.");
        }
        if (res.status === 403) {
          throw new Error("Transfers are active. Account verification is locked.");
        }
        return res.json();
      })
      .then((data) => {
        processingState.classList.add("d-none");
        dropzone.classList.remove("d-none");
        fileInput.value = "";

        if (data.status === 200) {
          showToast("" + data.message, "bg-success");
          renderResults(data);
          // Refresh the pending accounts list and global verify check
          fetchPendingAccounts();
          if (window.checkPendingAccounts) window.checkPendingAccounts();
        } else {
          showToast("" + (data.message || "Failed to process PDF"), "bg-danger");
        }
      })
      .catch((err) => {
        processingState.classList.add("d-none");
        dropzone.classList.remove("d-none");
        fileInput.value = "";
        showToast("" + err.message, "bg-danger");
      });
  }

  function renderResults(data) {
    resultsTableBody.innerHTML = "";
    resultsBadges.innerHTML = "";

    const stats = data.stats || { total: 0, success: 0, failed: 0, ignored: 0 };
    resultsBadges.innerHTML = `
 <span class="badge bg-secondary">Total: ${stats.total}</span>
 <span class="badge bg-success">Success: ${stats.success}</span>
 <span class="badge bg-danger">Failed: ${stats.failed}</span>
 <span class="badge bg-warning text-dark">Ignored: ${stats.ignored}</span>
 `;

    if (data.results && data.results.length > 0) {
      data.results.forEach((res) => {
        const row = document.createElement("tr");

        let statusBadge = "";
        if (res.status === "Success") {
          statusBadge = `<span class="badge badge-synced"><i class="fas fa-check-circle me-1"></i> Success</span>`;
        } else if (res.status === "Failed") {
          statusBadge = `<span class="badge badge-failed"><i class="fas fa-times-circle me-1"></i> Failed</span>`;
        } else {
          statusBadge = `<span class="badge badge-cloud"><i class="fas fa-exclamation-triangle me-1"></i> Ignored</span>`;
        }

        row.innerHTML = `
 <td class="fw-bold">${res.email}</td>
 <td>${statusBadge}</td>
 <td class="text-muted small">${res.message}</td>
 `;
        resultsTableBody.appendChild(row);
      });
      resultsSection.classList.remove("d-none");
    }
  }
});
