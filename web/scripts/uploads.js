function fetchOngoingUploads() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=transfer_status`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200 && Array.isArray(data.uploads)) {
        displayOngoingUploads(data.uploads);
      }
    })
    .catch((err) => console.error("❌ Error fetching uploads:", err));
}

function displayOngoingUploads(uploads) {
  const uploadsList = document.getElementById("uploads-list");
  
  if (!uploads || uploads.length === 0) {
    uploadsList.innerHTML = `
      <div class="col-12 empty-state">
        <div class="card p-5 border-dashed">
          <i class="fas fa-satellite-dish opacity-25"></i>
          <h4 class="fw-bold">All Quiet on the Cloud</h4>
          <p class="text-muted">Active transfers and recent failures will appear here.</p>
        </div>
      </div>
    `;
    return;
  }

  uploadsList.innerHTML = "";
  uploads.forEach((upload) => {
    const isFailed = upload.upload_status === "Failed";
    const isQueued = upload.upload_status === "Queued";
    const col = document.createElement("div");
    col.classList.add("col-md-6", "col-lg-4");

    const cardClass = isFailed ? "border-danger border-opacity-25 shadow-intensity" : (isQueued ? "border-info border-opacity-10 opacity-75" : "shadow-lg");
    const statusIcon = isFailed ? 'fa-exclamation-triangle text-danger' : (isQueued ? 'fa-hourglass-start text-warning' : 'fa-spinner fa-spin text-info');
    const statusText = isFailed ? 'CRITICAL FAILURE' : (isQueued ? 'PENDING IN QUEUE...' : 'Transferring Data...');

    col.innerHTML = `
      <div class="card h-100 ${cardClass}">
        <div class="card-body p-4">
          <div class="d-flex justify-content-between align-items-center mb-4">
            <h6 class="fw-bold mb-0 text-truncate" style="max-width: 70%;" title="${upload.file_name}">
              <i class="fas ${statusIcon} me-2"></i> ${upload.file_name}
            </h6>
            <span class="badge rounded-pill bg-dark border border-white border-opacity-10 py-1 px-3 small">
              #${upload.file_id}
            </span>
          </div>
          
          <div class="d-flex justify-content-between align-items-center mb-2">
            <small class="${isFailed ? 'text-danger fw-bold' : (isQueued ? 'text-warning opacity-75' : 'text-muted')}">
              ${statusText}
            </small>
            <div class="text-end">
              ${(!isQueued && upload.speed) ? `<span class="me-2 text-info small"><i class="fas fa-tachometer-alt me-1"></i>${upload.speed}</span>` : ''}
              ${(!isQueued && upload.eta) ? `<span class="text-warning small"><i class="fas fa-clock me-1"></i>${upload.eta}</span>` : ''}
            </div>
          </div>

          <!-- Progress bar removed as requested -->
          <div class="mb-3"></div>
          
            <div class="d-flex align-items-center justify-content-between mt-4 pt-2 border-top border-white border-opacity-10">
            <div class="d-flex align-items-center gap-2">
              <i class="fas fa-info-circle ${isFailed ? 'text-danger' : 'text-info'} opacity-50"></i>
              <small class="text-muted truncate">${isFailed ? 'Process exited with error' : (upload.account_email ? `<span class="text-info">${upload.account_email}</span>` : 'Active background process')}</small>
            </div>
            ${isFailed ? `
              <div class="d-flex gap-2">
                <button class="btn btn-sm btn-outline-danger p-1 px-3" onclick="retryUpload(${upload.file_id})">Retry</button>
                <button class="btn btn-sm btn-outline-secondary p-1 px-3" style="font-size: 0.75rem;" onclick="clearUpload(${upload.file_id})">Clear</button>
              </div>
            ` : ''}
          </div>
        </div>
      </div>
    `;
    uploadsList.appendChild(col);
  });
}

function clearUpload(fileId) {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=file_status_clear:${fileId}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`🗑️ #${fileId} cleared from uploads`, "bg-dark");
        fetchOngoingUploads();
      }
    })
    .catch((err) => console.error("❌ Error clearing upload:", err));
}

function retryUpload(fileId) {
  showToast(`🔁 Retrying upload for #${fileId}...`, "bg-info");
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=file_get_one:${fileId}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200 && data.file.m_account_id) {
        return fetch("/run-command", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: `command=transfer_upload:${fileId}:${data.file.m_account_id}`,
        });
      }
    })
    .then((res) => res?.json())
    .then((resData) => {
      if (resData && resData.status === 200) {
        showToast("✅ Retry queued!", "bg-success");
      }
    });
}

document.addEventListener("DOMContentLoaded", function () {
  fetchOngoingUploads();
  setInterval(fetchOngoingUploads, 2500);
});
