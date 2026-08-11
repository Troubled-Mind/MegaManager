let lastRenderedLogsCount = 0;

function fetchOngoingUploads() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=transfer_status`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        updateSpeedHeader(data);
        if (Array.isArray(data.uploads)) {
          displayOngoingUploads(data.uploads, data.is_calculating, data.calculating_message, data.queued_total_size);
        }
        if (Array.isArray(data.logs)) {
          renderTransferLogs(data.logs);
        }
      }
    })
    .catch((err) => console.error("Error fetching uploads:", err));
}

function formatBytes(bytes, decimals = 2) {
  if (!bytes || isNaN(bytes) || Number(bytes) === 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB", "TB", "PB"];
  const i = Math.floor(Math.log(Number(bytes)) / Math.log(k));
  return parseFloat((Number(bytes) / Math.pow(k, i)).toFixed(dm)) + "" + sizes[i];
}

function updateSpeedHeader(data) {
  const speedMBS = document.getElementById("speedMBS");
  const speedMBPS = document.getElementById("speedMBPS");
  const speedIcon = document.getElementById("speedIcon");

  const formattedSpeed = data.formatted_speed || "0.00 MB/s";
  const formattedMbps = data.formatted_mbps || "(0.0 Mbps)";
  const speedVal = Number(data.speed_mb_s) || 0;

  if (speedMBS) {
    speedMBS.textContent = formattedSpeed;
    if (speedVal > 0) {
      speedMBS.className = "text-success fw-bold";
    } else {
      speedMBS.className = "text-info";
    }
  }
  if (speedMBPS) speedMBPS.textContent = formattedMbps;

  if (speedIcon) {
    if (speedVal > 0) {
      speedIcon.className = "fas fa-gauge text-success fs-5";
    } else {
      speedIcon.className = "fas fa-gauge text-info fs-5";
    }
  }
}

function displayOngoingUploads(uploads, isCalculating, calculatingMessage, queuedTotalSize) {
  const uploadsList = document.getElementById("uploads-list");
  const pendingList = document.getElementById("pending-list");
  const pendingSection = document.getElementById("pending-section");
  const calculatingBanner = document.getElementById("calculating-banner");
  const calculatingMsgEl = document.getElementById("calculating-message");
  const activeCountEl = document.getElementById("active-transfers-count");
  const pendingCountEl = document.getElementById("pending-queue-count");
  const pendingSizeEl = document.getElementById("pending-queue-size");

  if (isCalculating) {
    if (calculatingBanner) {
      calculatingBanner.classList.remove("d-none");
      if (calculatingMsgEl && calculatingMessage) {
        calculatingMsgEl.textContent = calculatingMessage;
      }
    }
  } else {
    if (calculatingBanner) {
      calculatingBanner.classList.add("d-none");
    }
  }

  if (!uploads || uploads.length === 0) {
    if (isCalculating) {
      uploadsList.innerHTML = `
 <div class="col-12 empty-state">
 <div class="card p-5 border-dashed border-info border-opacity-25" style="background: rgba(56, 189, 248, 0.03);">
 <div class="spinner-border text-info mb-3" style="width: 2.5rem; height: 2.5rem;" role="status"></div>
 <h4 class="fw-bold text-white">Calculating Allocations...</h4>
 <p class="text-muted mb-0">${calculatingMessage || "Working out which files fit into your MEGA accounts..."}</p>
 </div>
 </div>
 `;
    } else {
      uploadsList.innerHTML = `
 <div class="col-12 empty-state">
 <div class="card p-5 border-dashed">
 <i class="fas fa-satellite-dish opacity-25 mb-3 fs-1"></i>
 <h4 class="fw-bold">All Quiet on the Cloud</h4>
 <p class="text-muted">Active transfers and recent failures will appear here.</p>
 </div>
 </div>
 `;
    }
    if (activeCountEl) activeCountEl.textContent = "0 active";
    if (pendingCountEl) pendingCountEl.textContent = "0 queued";
    if (pendingSizeEl) pendingSizeEl.textContent = "0 B";
    pendingList.innerHTML = "";
    pendingSection.classList.add("d-none");
    return;
  }

  const ongoing = uploads.filter((u) => u.upload_status !== "Queued" && u.upload_status !== "Pending");
  const pending = uploads.filter((u) => u.upload_status === "Queued" || u.upload_status === "Pending");

  const trulyActive = ongoing.filter((u) => u.upload_status === "In Progress");

  if (activeCountEl) {
    activeCountEl.textContent = `${trulyActive.length} active`;
  }
  if (pendingCountEl) {
    pendingCountEl.textContent = `${pending.length} queued`;
  }
  if (pendingSizeEl) {
    if (queuedTotalSize) {
      pendingSizeEl.textContent = queuedTotalSize;
    } else {
      const calcBytes = pending.reduce((sum, u) => sum + (parseInt(u.folder_size) || 0), 0);
      pendingSizeEl.textContent = formatBytes(calcBytes);
    }
  }

  // 1. Render Ongoing/Failed
  uploadsList.innerHTML = "";
  if (ongoing.length === 0) {
    uploadsList.innerHTML = `
 <div class="col-12">
 <div class="card p-4 text-center border-dashed border-white border-opacity-10 opacity-50">
 <p class="mb-0 text-muted small">No active or failed transfers detected.</p>
 </div>
 </div>
 `;
  } else {
    const isSingleActive = ongoing.length === 1;
    ongoing.forEach((u) => uploadsList.appendChild(renderUploadItem(u, false, isSingleActive)));
  }

  // 2. Render Pending Queue (Full Width)
  pendingList.innerHTML = "";
  if (pending.length > 0) {
    pendingSection.classList.remove("d-none");
    pending.forEach((u) => pendingList.appendChild(renderUploadItem(u, true, false)));
  } else {
    pendingSection.classList.add("d-none");
  }
}

function renderUploadItem(upload, isPendingQueue = false, isSingleActive = false) {
  const isFailed = upload.upload_status && upload.upload_status.startsWith("Failed");
  const isStopped = upload.upload_status === "Stopped";
  const isPending = upload.upload_status === "Queued" || upload.upload_status === "Pending";
  const progressVal = Math.min(100, Math.max(0, parseInt(upload.progress) || 0));
  const col = document.createElement("div");

  if (isPendingQueue) {
    col.classList.add("col-12", "col-md-6", "col-xl-4", "col-xxl-3");

    col.innerHTML = `
 <div class="card border border-secondary border-opacity-25 shadow-sm h-100" style="background: rgba(255,255,255,0.02); border-radius: 8px;">
 <div class="card-body p-2 d-flex align-items-center justify-content-between gap-2">
 <div class="d-flex align-items-center gap-2 overflow-hidden">
 <div class="d-flex align-items-center justify-content-center rounded bg-secondary bg-opacity-10 text-muted flex-shrink-0" style="width: 28px; height: 28px;">
 <i class="fas fa-clock" style="font-size: 0.75rem;"></i>
 </div>
 <div class="text-truncate">
 <div class="text-white fw-bold text-truncate" style="font-size: 0.8rem;" title="${upload.file_name || "Unnamed Folder"}">
 ${upload.file_name || "Unnamed Folder"}
 </div>
 <div class="text-muted text-truncate" style="font-size: 0.7rem;">
 <i class="fas fa-cloud me-1 opacity-75"></i>${upload.account_email || "Unassigned"}
 ${upload.post_upload_pct ? `<span class="text-info opacity-75 ms-1" style="font-size: 0.65rem;">(${upload.post_upload_pct}% full after upload)</span>` : ""}
 </div>
 </div>
 </div>
 <div class="d-flex flex-column align-items-end flex-shrink-0">
 <span class="badge bg-dark text-warning border border-warning border-opacity-40 py-1 px-2 font-monospace mb-1" style="font-size: 0.7rem;">
 ${upload.folder_size ? formatBytes(upload.folder_size) : "0 B"}
 </span>
 <div class="d-flex align-items-center gap-2 mt-1">
 <span class="text-muted" style="font-size: 0.65rem;">#${upload.file_id}</span>
 <button class="btn btn-link text-danger p-0 m-0" style="line-height: 1;" title="Cancel Upload" onclick="clearUpload(${upload.file_id})">
 <i class="fas fa-times-circle fs-6"></i>
 </button>
 </div>
 </div>
 </div>
 </div>
 `;
    return col;
  }

  if (isSingleActive) {
    col.classList.add("col-12");
  } else {
    col.classList.add("col-12", "col-md-6");
  }

  const cardClass = isFailed
    ? "border-danger border-opacity-25"
    : isStopped
      ? "border-warning border-opacity-25"
      : isPending
        ? "border-secondary border-opacity-25"
        : "border-info border-opacity-30";
  const statusIcon = isFailed
    ? "fa-exclamation-circle text-danger"
    : isStopped
      ? "fa-hand-paper text-warning"
      : isPending
        ? "fa-clock text-muted"
        : "fa-arrow-up text-info";
  const statusText = isFailed ? upload.upload_status : isStopped ? "Stopped" : isPending ? "Queued" : `Uploading (${progressVal}%)`;

  const sizeBadge = upload.folder_size
    ? `<span class="badge bg-dark text-warning border border-warning border-opacity-40 py-1 px-2 small fw-bold font-monospace flex-shrink-0" style="font-size: 0.75rem;">${formatBytes(upload.folder_size)}</span>`
    : "";

  col.innerHTML = `
 <div class="card h-100 ${cardClass} shadow-sm" style="background: rgba(255,255,255,0.02);">
 <div class="card-body p-3 d-flex flex-column justify-content-between">
 <div>
 <div class="d-flex justify-content-between align-items-start gap-2 mb-2">
 <h6 class="fw-bold mb-0 text-white" style="word-break: break-word; overflow-wrap: anywhere; line-height: 1.35; font-size: 0.95rem;">
 <i class="fas ${statusIcon} me-2 flex-shrink-0"></i>${upload.file_name || "Unnamed Folder"}
 </h6>
 <div class="d-flex align-items-center gap-1 flex-shrink-0">
 ${sizeBadge}
 <span class="badge rounded-pill bg-body-tertiary border border-secondary border-opacity-25 py-1 px-2 small text-muted flex-shrink-0">
 #${upload.file_id}
 </span>
 </div>
 </div>

 <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-1">
 <small class="fw-bold ${isFailed ? "text-danger" : isPending ? "text-muted" : "text-info"}" style="font-size: 0.8rem;">
 ${statusText}
 </small>
 <div class="text-end">
 ${
   !isPending && !isFailed && upload.speed
     ? `<span class="me-2 text-muted small"><i class="fas fa-gauge me-1 text-info opacity-75"></i>${upload.speed}</span>`
     : ""
 }
 ${
   !isPending && !isFailed && upload.eta
     ? `<span class="text-muted small"><i class="fas fa-clock me-1 text-info opacity-75"></i>${upload.eta}</span>`
     : ""
 }
 </div>
 </div>

 <!-- Progress Bar -->
 <div class="progress mb-2" style="height: 6px !important; background-color: rgba(255,255,255,0.08);">
 <div class="progress-bar ${
   isFailed ? "bg-danger" : isPending ? "bg-secondary" : "bg-info"
 }" role="progressbar" style="width: ${isPending ? 0 : progressVal}%" aria-valuenow="${progressVal}" aria-valuemin="0" aria-valuemax="100"></div>
 </div>
 </div>

 <div class="d-flex align-items-center justify-content-between mt-2 pt-2 border-top border-white border-opacity-10 gap-2">
 <div class="d-flex align-items-center gap-2" style="min-width: 0; flex: 1;">
 <i class="fas fa-cloud ${isFailed ? "text-danger" : "text-info"} opacity-75 flex-shrink-0"></i>
 <small class="text-muted text-truncate" style="word-break: break-all; overflow-wrap: anywhere; line-height: 1.25;">${
   upload.account_email || "Active process"
 } ${upload.post_upload_pct ? `<span class="text-info opacity-75 ms-1" style="font-size: 0.65rem;">(${upload.post_upload_pct}% full after upload)</span>` : ""}</small>
 </div>
 ${
   isFailed
     ? `
 <div class="d-flex gap-1 flex-shrink-0">
 <button class="btn btn-sm btn-outline-danger py-1 px-2" onclick="retryUpload(${upload.file_id})"><i class="fas fa-redo me-1"></i> Retry</button>
 <button class="btn btn-sm btn-outline-secondary py-1 px-2" onclick="clearUpload(${upload.file_id})">Clear</button>
 </div>
 `
     : isPending
       ? `<span class="badge text-muted border border-secondary border-opacity-25 px-2 py-1 small flex-shrink-0">Queued</span>`
       : `<span class="badge-local flex-shrink-0" style="font-size: 0.75rem;">Uploading</span>`
 }
 </div>
 </div>
 </div>
 `;
  return col;
}

// Matches progress log lines like "#1102 41% (1.695 GiB / 4.127 GiB) @ 10.854 MiB/s"
const PROGRESS_LOG_RE = /^#(\d+)\s+(\d+)%\s+\(([^)]+)\)\s*@\s*(.+)$/;

function buildProgressLogRowHtml(fileId, pct, sizeInfo, speed, time) {
  if (pct >= 100) {
    return `
 <div class="py-1 px-1 border-bottom border-white border-opacity-5 d-flex align-items-center gap-2" style="font-family: SFMono-Regular, Menlo, Monaco, Consolas, monospace;">
 <span class="text-muted opacity-60 flex-shrink-0" style="font-size: 0.72rem;">${time}</span>
 <span class="badge-synced flex-shrink-0" style="font-size: 0.62rem; padding: 0.15em 0.4em;">SUCCESS</span>
 <span class="text-white-50 small">#${fileId} · ${sizeInfo}</span>
 </div>
 `;
  }

  return `
 <div class="py-1 px-1 border-bottom border-white border-opacity-5" style="font-family: SFMono-Regular, Menlo, Monaco, Consolas, monospace;">
 <div class="d-flex align-items-center gap-2 mb-1">
 <span class="text-muted opacity-60 flex-shrink-0" style="font-size: 0.72rem;">${time}</span>
 <span class="badge-local flex-shrink-0" style="font-size: 0.62rem; padding: 0.15em 0.4em;">PROGRESS</span>
 <span class="text-white-50 small">#${fileId} · ${sizeInfo} · ${speed}</span>
 <span class="text-info small fw-semibold ms-auto">${pct}%</span>
 </div>
 <div class="progress">
 <div class="progress-bar bg-info" role="progressbar" style="width: ${pct}%" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100"></div>
 </div>
 </div>
 `;
}

function renderTransferLogs(logs) {
  const container = document.getElementById("transfer-logs-stream");
  if (!container) return;

  if (!logs || logs.length === 0) {
    if (container.children.length === 0) {
      container.innerHTML = `
 <div class="text-muted text-center py-5 small opacity-50">
 <i class="fas fa-terminal mb-2 fs-4 d-block"></i>
 Waiting for stream events...
 </div>
 `;
    }
    return;
  }

  // Check if user is near bottom before updating to decide whether to autoscroll
  const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 60;

  // Collapse repeated progress ticks for the same file into one live-updating
  // row instead of a fresh line per update - with several files uploading at
  // once, ticks would otherwise flood out every other kind of log entry
  // within seconds. These are rendered as their own block, sorted by file ID,
  // rather than interleaved at each tick's chronological position - keeping
  // them interleaved made every row jump around on every poll, since
  // whichever file happened to report last kept hopping to a new spot.
  const latestProgressByFile = new Map();
  const otherLogs = [];
  logs.forEach((log) => {
    if (log.level === "PROGRESS") {
      const m = log.message.match(PROGRESS_LOG_RE);
      if (m) {
        const [, fileId, pct, sizeInfo, speed] = m;
        latestProgressByFile.set(fileId, { fileId, pct: Number(pct), sizeInfo, speed, time: log.time });
        return;
      }
    }
    otherLogs.push(log);
  });

  let html = "";
  otherLogs.forEach((log) => {
    let levelBadgeClass = "badge bg-secondary bg-opacity-25 text-muted";
    if (log.level === "PROGRESS" || log.level === "TRANSFER") {
      levelBadgeClass = "badge-local";
    } else if (log.level === "SUCCESS") {
      levelBadgeClass = "badge-synced";
    } else if (log.level === "ERROR") {
      levelBadgeClass = "badge-failed";
    } else if (log.level === "QUEUE") {
      levelBadgeClass = "badge-cloud";
    } else if (log.level === "AUTH") {
      levelBadgeClass = "badge-auth";
    }

    html += `
 <div class="py-1 px-1 border-bottom border-white border-opacity-5 d-flex align-items-start gap-2" style="font-family: SFMono-Regular, Menlo, Monaco, Consolas, monospace;">
 <span class="text-muted opacity-60 flex-shrink-0" style="font-size: 0.72rem;">${log.time}</span>
 <span class="${levelBadgeClass} flex-shrink-0" style="font-size: 0.62rem; padding: 0.15em 0.4em;">${log.level}</span>
 <span class="text-white-50" style="word-break: break-word; overflow-wrap: anywhere; line-height: 1.35;">${log.message}</span>
 </div>
 `;
  });

  const sortedProgress = [...latestProgressByFile.values()].sort((a, b) => Number(a.fileId) - Number(b.fileId));
  sortedProgress.forEach((p) => {
    html += buildProgressLogRowHtml(p.fileId, p.pct, p.sizeInfo, p.speed, p.time);
  });

  container.innerHTML = html;

  if (isNearBottom || logs.length !== lastRenderedLogsCount) {
    container.scrollTop = container.scrollHeight;
  }
  lastRenderedLogsCount = logs.length;
}

function clearUploadLogs() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=transfer_status:clear_logs`,
  })
    .then((res) => res.json())
    .then(() => {
      const container = document.getElementById("transfer-logs-stream");
      if (container) {
        container.innerHTML = `
 <div class="text-muted text-center py-5 small opacity-50">
 <i class="fas fa-terminal mb-2 fs-4 d-block"></i>
 Logs cleared.
 </div>
 `;
      }
    })
    .catch((err) => console.error("Error clearing logs:", err));
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
        showToast(`#${fileId} cleared from uploads`, "bg-secondary");
        fetchOngoingUploads();
      }
    })
    .catch((err) => console.error("Error clearing upload:", err));
}

function retryUpload(fileId) {
  showToast(`Retrying upload for #${fileId}...`, "bg-info");
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
        showToast("Retry queued!", "bg-success");
      }
    });
}

function stopAllUploads() {
  const btn = document.getElementById("stopAllUploadsBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Stopping...';
  }
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: " command=transfer_stop_all",
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast("" + data.message, "bg-success");
        fetchOngoingUploads(); // refresh ui
      } else {
        showToast("" + data.message, "bg-danger");
      }
    })
    .catch((err) => {
      console.error(err);
      showToast("Failed to send stop command", "bg-danger");
    })
    .finally(() => {
      setTimeout(() => {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `<i class="fas fa-stop-circle me-1"></i> Stop All`;
        }
      }, 1000);
    });
}

function clearStoppedUploads() {
  const btn = document.getElementById("clearStoppedBtn");
  if (!btn) return;

  btn.disabled = true;
  btn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> Clearing...`;

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: " command=transfer_clear_stopped",
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast("" + data.message, "bg-success");
        fetchOngoingUploads(); // refresh ui
      } else {
        showToast("" + data.message, "bg-danger");
      }
    })
    .catch((err) => {
      console.error(err);
      showToast("Failed to send clear command", "bg-danger");
    })
    .finally(() => {
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-eraser me-1"></i> Clear Stopped`;
      }, 1000);
    });
}

document.addEventListener("DOMContentLoaded", function () {
  fetchOngoingUploads();
  setInterval(fetchOngoingUploads, 10000);
});
