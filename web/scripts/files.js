document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("filesTableBody")) {
    loadFilesTable();
  }

  initFilterPanel("filesFilterToggle", "filesFilterPanel", "filesFilterChevron");

  document.getElementById("filterLocation")?.addEventListener("change", applyFileFilters);
  document.getElementById("filterAccount")?.addEventListener("change", applyFileFilters);
  document.getElementById("filterSizeDiscrepancy")?.addEventListener("change", applyFileFilters);
  document.getElementById("filterShow")?.addEventListener("change", () => {
    populateTourFilterOptions();
    const tourEl = document.getElementById("filterTour");
    if (tourEl) tourEl.value = "all";
    applyFileFilters();
  });
  document.getElementById("filterTour")?.addEventListener("change", applyFileFilters);
  document.getElementById("clearFileFiltersBtn")?.addEventListener("click", () => {
    ["filterLocation", "filterAccount", "filterShow", "filterTour"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = "all";
    });
    const sizeDiscrepancy = document.getElementById("filterSizeDiscrepancy");
    if (sizeDiscrepancy) sizeDiscrepancy.checked = false;
    populateTourFilterOptions();
    applyFileFilters();
  });
});

function generateSharingLink(fileId) {
  console.log(`Generating sharing link for file ID: ${fileId}`);
  showToast(`Generating link for file #${fileId}...`, "bg-info");

  fetch("/run-command", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      command: `transfer_sharing:${fileId}`,
    }),
  })
    .then((response) => response.json())
    .then((data) => {
      if (data.status === 200) {
        fetchFileDetails(fileId);
      } else {
        showToast(`${data.message}`, "bg-danger");
      }
    })
    .catch((error) => {
      console.error("Error generating sharing link:", error);
      showToast("Failed to generate link due to network error.", "bg-danger");
    });
}

function uploadToCloud(fileId) {
  const modalEl = document.getElementById("uploadToCloudModal");
  const modal = new mdb.Modal(modalEl);
  modal.show();

  modalEl.addEventListener(
    "shown.mdb.modal",
    function handler() {
      // Cleanup the event so it doesn't stack up
      modalEl.removeEventListener("shown.mdb.modal", handler);

      document.getElementById("uploadFileId").value = fileId;

      const dropdown = document.getElementById("megaAccountDropdown");
      const startUploadBtn = document.getElementById("startUploadBtn");

      dropdown.innerHTML = "<option disabled selected>Loading...</option>";
      startUploadBtn.disabled = true;

      fetch("/run-command", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `command=account_get_eligible:${fileId}`,
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.status === 200 && Array.isArray(data.accounts)) {
            dropdown.innerHTML = "";

            data.accounts
              .sort((a, b) => a.available - b.available) // ascending: least free first
              .forEach((acc) => {
                const option = document.createElement("option");
                option.value = acc.id;
                option.textContent = `${acc.email} (${formatBytes(acc.available)} free)`;
                dropdown.appendChild(option);
              });
            startUploadBtn.disabled = false;
          } else {
            dropdown.innerHTML = "<option disabled>No eligible accounts found</option>";
            showToast("No eligible MEGA accounts found.", "bg-warning");
          }
        })
        .catch((err) => {
          console.error("Failed to fetch eligible accounts:", err);
          dropdown.innerHTML = "<option disabled>Error loading accounts</option>";
          showToast("Error loading accounts", "bg-danger");
        });
    },
    { once: true }, // Only run this handler once
  );
}

function confirmFileUpload() {
  const fileId = $("#uploadFileId").val();
  const selectedAccountId = $("#megaAccountDropdown").val();
  console.log(`Confirming upload for file ID: ${fileId} to account ID: ${selectedAccountId}`);

  if (!selectedAccountId) {
    showToast("Please select a MEGA account", "bg-warning");
    return;
  }

  const modal = mdb.Modal.getInstance(document.getElementById("uploadToCloudModal"));
  if (modal) modal.hide();

  showToast(`Uploading file #${fileId} to account #${selectedAccountId}`, "bg-info");

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=transfer_upload:${fileId}:${selectedAccountId}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast("Upload queued in background!", "bg-success");
        loadFilesTable();
      } else {
        showToast(`Upload failed: ${data.message || "Unknown error"}`, "bg-danger");
      }
    })
    .catch((err) => {
      console.error("Upload error:", err);
      showToast("Upload failed due to network error", "bg-danger");
    });
}

function smartReupload(fileId) {
  showToast(`Checking #${fileId} - resuming or moving to an account with room...`, "bg-info");

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=transfer_reupload:${fileId}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`${data.message || "Re-upload queued"}`, "bg-success");
        setTimeout(loadFilesTable, 1500);
      } else {
        showToast(`${data.message || "Smart re-upload failed"}`, "bg-danger");
      }
    })
    .catch((err) => {
      console.error("Smart re-upload error:", err);
      showToast("Smart re-upload failed due to network error", "bg-danger");
    });
}

function generateExpiringLink(fileId) {
  console.log(`Generating expiring link for file ID: ${fileId}`);
  showToast(`Generating expiring link for file #${fileId}...`, "bg-info");
  alert("Not yet implemented. This will be done in future");
}

function generateMissingLinks() {
  showToast(`Starting to generate missing sharing links...`, "bg-success");
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "transfer_missing_links" }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`Missing sharing links generated`, "bg-success");
        loadFilesTable();
      } else {
        showToast(`Failed: ${data.message || "Unknown error"}`, "bg-danger");
      }
    })
    .catch((err) => {
      console.error("Generate missing links error:", err);
      showToast("Failed to generate missing sharing links", "bg-danger");
    });
}

function reorgCloudFiles() {
  showToast(`Starting cloud file reorganization...`, "bg-success");
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "transfer_reorg_cloud" }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`Cloud reorganization started in background`, "bg-success");
        loadFilesTable();
      } else {
        showToast(`Failed: ${data.message || "Unknown error"}`, "bg-danger");
      }
    })
    .catch((err) => {
      console.error("Reorganize cloud files error:", err);
      showToast("Failed to start cloud reorganization", "bg-danger");
    });
}

function updateAllDetails() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "file_local_index" }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`Local library scan started in background...`, "bg-info");
      }
    });

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "file_group_details" }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`Cloud sync started in background...`, "bg-info");
      }
    })
    .catch((err) => {
      console.error("Error during update process:", err);
      showToast("Failed to trigger updates", "bg-danger");
    });

  // Automatically refresh table periodically as background indexing finishes
  setTimeout(loadFilesTable, 2000);
  setTimeout(loadFilesTable, 6000);
  setTimeout(loadFilesTable, 12000);
}

function fetchFileDetails(fileId) {
  console.log(`Checking which source to refresh for file ID: ${fileId}`);

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=file_get_one:${fileId}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status !== 200 || !data.file) {
        throw new Error(data.message || "File not found");
      }

      const file = data.file;
      const promises = [];

      if (file.m_path) {
        promises.push(
          fetch("/run-command", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: `command=file_details:${fileId}`,
          }).then((res) => res.json()),
        );
      }

      if (file.l_path) {
        promises.push(
          fetch("/run-command", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: `command=file_local_details:${fileId}`,
          }).then((res) => res.json()),
        );
      }

      if (promises.length === 0) {
        showToast(`No cloud or local path for file #${fileId}`, "bg-warning");
        return Promise.resolve([]); // Prevents undefined `.then()`below
      }

      return Promise.all(promises);
    })
    .then((results) => {
      if (!results || !Array.isArray(results)) return;

      let finalFile = {};

      for (const result of results) {
        if (result.status === 200 && result.file) {
          for (const [key, value] of Object.entries(result.file)) {
            if (value !== undefined && value !== null) {
              finalFile[key] = value;
            }
          }
        }
      }

      if (Object.keys(finalFile).length) {
        updateRowWithFileData(finalFile);
        showToast(`File details refreshed`, "bg-success");
      } else {
        showToast(`Failed to update details`, "bg-warning");
      }
    })
    .catch((err) => {
      console.error("Error fetching file details:", err);
      showToast("Failed to fetch file details", "bg-danger");
    });
}

let configuredLocalRoots = [];
let allFilesData = [];

function computeFileMeta(file) {
  const isLocal = !!file.is_local;
  const isCloud = !!file.is_cloud;
  const location = isLocal && isCloud ? "both" : isLocal ? "local" : isCloud ? "cloud" : "none";

  let relPath = "";
  if (file.l_path) {
    const stripped = stripLocalPrefix(file.l_path);
    relPath = stripped === "-" ? "" : stripped;
  } else if (file.m_path) {
    relPath = file.m_path;
  }

  const parts = relPath.split("/").filter(Boolean);

  // A cloud size of 0 means "not measured yet" in this app's data, not a real
  // empty folder (matches the "Unmeasured" cloud-status badge's own > 0
  // check) - treating 0 as "measured" here made every not-yet-synced
  // local-only file show up as a false "discrepancy".
  const localSize = file.l_folder_size != null ? Number(file.l_folder_size) : null;
  const cloudSize = file.m_folder_size != null ? Number(file.m_folder_size) : null;
  const hasBothSizes = localSize != null && localSize > 0 && cloudSize != null && cloudSize > 0;
  const sizeDiscrepancy = hasBothSizes && localSize !== cloudSize;

  return {
    _location: location,
    _show: parts[0] || null,
    _tour: parts[1] || null,
    _sizeDiscrepancy: sizeDiscrepancy,
  };
}

function populateFileFilters() {
  const accountSelect = document.getElementById("filterAccount");
  if (accountSelect) {
    const prevVal = accountSelect.value || "all";
    const accountMap = new Map();
    allFilesData.forEach((f) => {
      if (f.m_account_id && f.cloud_email) {
        accountMap.set(String(f.m_account_id), f.cloud_email);
      }
    });
    const sortedAccounts = [...accountMap.entries()].sort((a, b) => a[1].localeCompare(b[1]));

    accountSelect.innerHTML = "";
    accountSelect.appendChild(new Option("All Accounts", "all"));
    sortedAccounts.forEach(([id, email]) => accountSelect.appendChild(new Option(email, id)));
    accountSelect.value = [...accountSelect.options].some((o) => o.value === prevVal) ? prevVal : "all";
  }

  const showSelect = document.getElementById("filterShow");
  if (showSelect) {
    const prevVal = showSelect.value || "all";
    const shows = new Set();
    allFilesData.forEach((f) => {
      if (f._show) shows.add(f._show);
    });
    const sortedShows = [...shows].sort((a, b) => a.localeCompare(b));

    showSelect.innerHTML = "";
    showSelect.appendChild(new Option("All Shows", "all"));
    sortedShows.forEach((show) => showSelect.appendChild(new Option(show, show)));
    showSelect.value = [...showSelect.options].some((o) => o.value === prevVal) ? prevVal : "all";
  }

  populateTourFilterOptions();
}

function populateTourFilterOptions() {
  const tourSelect = document.getElementById("filterTour");
  if (!tourSelect) return;

  const showVal = document.getElementById("filterShow")?.value || "all";
  const prevVal = tourSelect.value || "all";

  const tours = new Set();
  allFilesData.forEach((f) => {
    if (!f._tour) return;
    if (showVal !== "all" && f._show !== showVal) return;
    tours.add(f._tour);
  });
  const sortedTours = [...tours].sort((a, b) => a.localeCompare(b));

  tourSelect.innerHTML = "";
  tourSelect.appendChild(new Option("All Tours / Productions", "all"));
  sortedTours.forEach((tour) => tourSelect.appendChild(new Option(tour, tour)));
  tourSelect.value = [...tourSelect.options].some((o) => o.value === prevVal) ? prevVal : "all";
}

function applyFileFilters() {
  const locationVal = document.getElementById("filterLocation")?.value || "all";
  const accountVal = document.getElementById("filterAccount")?.value || "all";
  const showVal = document.getElementById("filterShow")?.value || "all";
  const tourVal = document.getElementById("filterTour")?.value || "all";
  const sizeDiscrepancyOnly = document.getElementById("filterSizeDiscrepancy")?.checked || false;

  const filtered = allFilesData.filter((file) => {
    if (locationVal !== "all" && file._location !== locationVal) return false;
    if (accountVal !== "all" && String(file.m_account_id || "") !== accountVal) return false;
    if (showVal !== "all" && file._show !== showVal) return false;
    if (tourVal !== "all" && file._tour !== tourVal) return false;
    if (sizeDiscrepancyOnly && !file._sizeDiscrepancy) return false;
    return true;
  });

  const activeCount = [locationVal, accountVal, showVal, tourVal].filter((v) => v !== "all").length + (sizeDiscrepancyOnly ? 1 : 0);
  updateFilterBadge("filesFilterActiveBadge", activeCount);

  renderFilesTable(filtered);
}

function stripLocalPrefix(path) {
  if (!path || path === "-") return "-";
  let cleanPath = path;

  for (const root of configuredLocalRoots) {
    if (!root) continue;
    const normalizedRoot = root.replace(/\/+$/, "");
    if (cleanPath === normalizedRoot) {
      return "/";
    }
    if (cleanPath.startsWith(normalizedRoot + "/")) {
      const remainder = cleanPath.slice(normalizedRoot.length);
      return remainder.startsWith("/") ? remainder : "/" + remainder;
    }
  }
  return cleanPath;
}

function buildCloudStatusHtml(file) {
  if (!file.is_cloud) {
    return '<span class="text-muted opacity-50 small">-</span>';
  }

  const clickableAttrs = `style="cursor: pointer;" title="Account: ${file.cloud_email || "Unknown"}" onclick="handleCloudStatusClick(${file.id}, '${file.l_folder_name || file.m_folder_name}', '${file.cloud_email || ""}')"`;
  const status = file.upload_status || null;

  // Active-transfer states take priority - a file mid-upload or just
  // stopped/failed shouldn't be shown as any flavor of "synced".
  if (status === "In Progress") {
    const pct = Number(file.upload_progress) || 0;
    return `<span class="badge-cloud" title="Uploading - see the Uploads page for live progress"><i class="fas fa-spinner fa-spin me-1"></i> Uploading ${pct}%</span>`;
  }
  if (status === "Queued") {
    return `<span class="badge-cloud"><i class="fas fa-hourglass-half me-1"></i> Queued</span>`;
  }
  if (status === "Stopped") {
    return `<span class="badge bg-secondary bg-opacity-25 text-muted small" title="Upload was cancelled"><i class="fas fa-pause me-1"></i> Stopped</span>`;
  }
  if (status && status.toLowerCase().startsWith("failed")) {
    return `<span class="badge-failed" title="${status}"><i class="fas fa-exclamation-triangle me-1"></i> Failed</span>`;
  }

  const localSize = file.l_folder_size != null ? Number(file.l_folder_size) : null;
  const cloudSize = file.m_folder_size != null ? Number(file.m_folder_size) : null;
  const hasCloudSize = cloudSize != null && cloudSize > 0;

  if (hasCloudSize && localSize != null && localSize > 0 && localSize !== cloudSize) {
    // Cloud has *something* recorded, but it doesn't match local - a
    // partial/stale upload, not a real sync. Distinct from "Unmeasured"
    // (which means we don't know yet) and from "Synced" (which means it
    // actually matches).
    return `<span class="badge-cloud"${clickableAttrs} title="Local: ${formatBytes(localSize)} · Cloud: ${formatBytes(cloudSize)} - sizes don't match"><i class="fas fa-triangle-exclamation me-1"></i> Mismatch</span>`;
  }

  if (hasCloudSize) {
    return `<span class="badge-synced"${clickableAttrs}><i class="fas fa-cloud-check me-1"></i> ${file.cloud_email ? file.cloud_email.split("@")[0] : "Synced"}</span>`;
  }

  // Cloud-linked (e.g. discovered via an account scan) but no size recorded
  // yet, and nothing actively in flight - not "syncing", just unmeasured.
  return `<span class="badge-cloud"${clickableAttrs}><i class="fas fa-ruler me-1"></i> Unmeasured</span>`;
}

function buildFileRowHTML(file) {
  const hasLink = file.m_sharing_link && file.m_sharing_link.trim() !== "";
  const copyBtnColor = hasLink ? "btn-outline-success" : "btn-outline-secondary";

  const isSynced = file.is_local && file.is_cloud;
  const localStatusHtml = file.is_local
    ? '<span class="badge-local"><i class="fas fa-check me-1"></i> Local</span>'
    : '<span class="text-muted opacity-50 small">-</span>';

  const cloudStatusHtml = buildCloudStatusHtml(file);

  const displayLocalPath = stripLocalPrefix(file.l_path);

  const html = `
 <td style="display:none">${file.id}</td>
 <td class="path-column">
 <div class="mb-1 text-truncate" style="max-width: 480px;" title="${file.l_path || "-"}"><i class="fas fa-folder me-2 text-info opacity-75"></i> ${displayLocalPath || "-"}</div>
 <div class="small text-muted text-truncate" style="max-width: 480px;" title="${file.m_path || "-"}"><i class="fas fa-cloud me-2 text-warning opacity-75"></i> ${file.m_path || "-"}</div>
 </td>
 <td class="fw-bold">${file.l_folder_name || file.m_folder_name || "-"}</td>
 <td class="text-end" data-order="${file.l_folder_size || 0}">${
   formatBytes(file.l_folder_size || 0) === "0.00 B" ? "-" : formatBytes(file.l_folder_size)
 }</td>
 <td class="text-end ${Math.abs((file.l_folder_size || 0) - (file.m_folder_size || 0)) > 1024 * 1024 ? "text-warning fw-bold" : ""}" data-order="${file.m_folder_size || 0}">${
   formatBytes(file.m_folder_size || 0) === "0.00 B" ? "-" : formatBytes(file.m_folder_size)
 }</td>
 <td class="text-center">${localStatusHtml}</td>
 <td class="text-center">${cloudStatusHtml}</td>
 <td class="text-end">
 <div class="d-flex justify-content-end gap-1">
 <button class="btn btn-sm ${copyBtnColor} shadow-0"${
   !hasLink ? "disabled" : ""
 } title="${hasLink ? "Copy Sharing Link" : "No link generated"}" onclick="copySharingLink('${file.m_sharing_link}', ${file.id})">
 <i class="fas fa-link"></i>
 </button>
 <div class="btn-group dropdown">
 <button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle dropdown-toggle-split shadow-0" data-mdb-toggle="dropdown" aria-expanded="false">
 <i class="fas fa-ellipsis-v"></i>
 </button>
 <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end">
 ${
   file.is_cloud
     ? `<li><a class="dropdown-item" href="#" onclick="generateSharingLink(${file.id})"><i class="fas fa-link me-2 text-info"></i> Generate Sharing Link</a></li>`
     : ""
 }
 ${
   file.pro_account
     ? `<li><a class="dropdown-item" href="#" onclick="generateExpiringLink(${file.id})"><i class="fas fa-clock me-2 text-warning"></i> Generate Expiring Link</a></li>`
     : ""
 }
 <li><a class="dropdown-item ${file.is_cloud ? "text-warning" : "text-success"}" href="#" onclick="uploadToCloud(${file.id})"><i class="fas fa-cloud-upload-alt me-2"></i> ${file.is_cloud ? "Re-upload to Cloud" : "Upload to Cloud"}</a></li>
 ${
   file.is_local && file.is_cloud
     ? `<li><a class="dropdown-item text-info" href="#" onclick="smartReupload(${file.id})" title="Resumes on the current account if it has room, otherwise clears the partial upload and moves to an account that does"><i class="fas fa-magic me-2"></i> Smart Re-upload</a></li>`
     : ""
 }
 <li><hr class="dropdown-divider"></li>
 <li><a class="dropdown-item text-secondary small" href="#" onclick="fetchFileDetails(${file.id})"><i class="fas fa-sync-alt me-2"></i> Refresh Details</a></li>
 </ul>
 </div>
 </div>
 </td>
 `;

  return html;
}

// Used for single-row refreshes (e.g. after "Refresh Details"). Bulk table
// renders go through renderFilesTable() instead, which avoids the per-row
// DOM search here for O(n) performance on large tables.
function updateRowWithFileData(file) {
  const cacheIdx = allFilesData.findIndex((f) => f.id === file.id);
  if (cacheIdx !== -1) {
    const merged = { ...allFilesData[cacheIdx], ...file };
    allFilesData[cacheIdx] = { ...merged, ...computeFileMeta(merged) };
  }

  let row = document.getElementById(`file-row-${file.id}`);
  const html = buildFileRowHTML(file);

  if (row) {
    row.innerHTML = html;
  } else {
    row = document.createElement("tr");
    row.id = `file-row-${file.id}`;
    row.innerHTML = html;
    document.getElementById("filesTableBody").appendChild(row);
  }

  const dropdownToggle = row.querySelector(".dropdown-toggle");
  if (dropdownToggle) new mdb.Dropdown(dropdownToggle);
}

function handleCloudStatusClick(fileId, folderName, email) {
  if (email && email.trim()) {
    showToast(`File #${fileId} - ${folderName} is uploaded to account ${email}`, "bg-success");
  } else {
    showToast(`File #${fileId} is not uploaded to any cloud account`, "bg-warning");
  }
}

function renderFilesTable(files) {
  const table = $("#filesTable");

  if ($.fn.DataTable.isDataTable("#filesTable")) {
    table.DataTable().clear().destroy();
  }

  const tbody = document.getElementById("filesTableBody");

  // Build every row's HTML up-front and assign it in one shot. Appending
  // rows one at a time (or searching the DOM for each row as it's added)
  // is O(n^2) and gets very slow once there are a few hundred+ folders.
  tbody.innerHTML = files.map((file) => `<tr id="file-row-${file.id}">${buildFileRowHTML(file)}</tr>`).join("");

  tbody.querySelectorAll(".dropdown-toggle").forEach((toggle) => new mdb.Dropdown(toggle));

  $("#filesTable").DataTable({
    responsive: true,
    lengthMenu: [50, 100, 250, 500, 1000],
    order: [[0, "desc"]],
    columnDefs: [
      {
        targets: [7],
        orderable: false,
      },
    ],
  });

  const countEl = document.getElementById("filesFilterResultCount");
  if (countEl) {
    countEl.textContent =
      files.length === allFilesData.length
        ? `Showing all ${files.length.toLocaleString()} folders`
        : `Showing ${files.length.toLocaleString()} of ${allFilesData.length.toLocaleString()} folders`;
  }
}

function loadFilesTable() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=file_db_fetch`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (Array.isArray(data.local_paths)) {
        configuredLocalRoots = data.local_paths;
      }

      const files = data.files || [];
      allFilesData = files.map((file) => ({ ...file, ...computeFileMeta(file) }));

      const stats = data.stats || {};
      const totalLocalBytes = stats.total_local_size !== undefined ? stats.total_local_size : 0;
      const totalCloudBytes = stats.total_cloud_size !== undefined ? stats.total_cloud_size : 0;
      const totalFilesCount = stats.total_files !== undefined ? stats.total_files : files.length;
      const syncedCount = stats.synced_files !== undefined ? stats.synced_files : 0;

      const statLocalEl = document.getElementById("statTotalLocalSize");
      const statCloudEl = document.getElementById("statTotalCloudSize");
      const statCountEl = document.getElementById("statTotalFilesCount");
      const statSyncedEl = document.getElementById("statSyncedFilesCount");

      if (statLocalEl) statLocalEl.textContent = formatBytes(totalLocalBytes);
      if (statCloudEl) statCloudEl.textContent = formatBytes(totalCloudBytes);
      if (statCountEl) statCountEl.textContent = totalFilesCount.toLocaleString();
      if (statSyncedEl) statSyncedEl.textContent = `${syncedCount.toLocaleString()} / ${totalFilesCount.toLocaleString()}`;

      populateFileFilters();
      applyFileFilters();
    })
    .catch((err) => console.error("Failed to load files:", err));
}

function formatBytes(bytes) {
  bytes = Number(bytes);
  if (!isFinite(bytes)) return "-";

  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i++;
  }
  return `${bytes.toFixed(2)} ${units[i]}`;
}

function copySharingLink(link, fileId) {
  if (!link || link.trim() === "") {
    showToast(`No sharing link available for file #${fileId}`, "bg-warning");
    return;
  }

  navigator.clipboard
    .writeText(link)
    .then(() => {
      showToast(`Sharing link copied for file #${fileId}`, "bg-success");
    })
    .catch((err) => {
      console.error("Clipboard copy failed:", err);
      showToast("Failed to copy link", "bg-danger");
    });
}

async function startBatchUpload() {
  const modalEl = document.getElementById("batchUploadModal");
  const modal = new mdb.Modal(modalEl);
  modal.show();

  document.getElementById("confirmBatchUploadBtn").onclick = async () => {
    modal.hide();
    const btn = document.getElementById("batchUploadBtn");
    const originalHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Initialising...`;

    try {
      const res = await fetch("/run-command", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `command=file_batch_sync`,
      });

      const result = await res.json();
      if (result.status === 200) {
        showToast("Auto-Batch upload started in background!", "bg-info");
        setTimeout(loadFilesTable, 3000);
      } else {
        showToast(`Failed: ${result.message}`, "bg-danger");
      }
    } catch (err) {
      console.error("Batch upload error:", err);
      showToast("Connection error during batch upload start.", "bg-danger");
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  };
}
