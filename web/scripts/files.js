document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("filesTableBody")) {
    loadFilesTable();
  }
});

function generateSharingLink(fileId) {
  console.log(`🔗 Generating sharing link for file ID: ${fileId}`);
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
        showToast(`❌ ${data.message}`, "bg-danger");
      }
    })
    .catch((error) => {
      console.error("Error generating sharing link:", error);
      showToast(
        "❌ Failed to generate link due to network error.",
        "bg-danger"
      );
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

      // Set file ID in hidden input
      document.getElementById("uploadFileId").value = fileId;

      const dropdown = document.getElementById("megaAccountDropdown");
      const startUploadBtn = document.getElementById("startUploadBtn");

      // Disable while loading
      dropdown.innerHTML = "<option disabled selected>Loading...</option>";
      startUploadBtn.disabled = true;

      // Fetch eligible accounts
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
                option.textContent = `${acc.email} (${formatBytes(
                  acc.available
                )} free)`;
                dropdown.appendChild(option);
              });
            startUploadBtn.disabled = false;
          } else {
            dropdown.innerHTML =
              "<option disabled>No eligible accounts found</option>";
            showToast("❌ No eligible MEGA accounts found.", "bg-warning");
          }
        })
        .catch((err) => {
          console.error("❌ Failed to fetch eligible accounts:", err);
          dropdown.innerHTML =
            "<option disabled>Error loading accounts</option>";
          showToast("❌ Error loading accounts", "bg-danger");
        });
    },
    { once: true } // Only run this handler once
  );
}

function confirmFileUpload() {
  const fileId = $("#uploadFileId").val();
  const selectedAccountId = $("#megaAccountDropdown").val();
  console.log(
    `📤 Confirming upload for file ID: ${fileId} to account ID: ${selectedAccountId}`
  );

  if (!selectedAccountId) {
    showToast("⚠️ Please select a MEGA account", "bg-warning");
    return;
  }

  const modal = mdb.Modal.getInstance(
    document.getElementById("uploadToCloudModal")
  );
  if (modal) modal.hide();

  showToast(
    `📤 Uploading file #${fileId} to account #${selectedAccountId}`,
    "bg-info"
  );

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=transfer_upload:${fileId}:${selectedAccountId}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast("✅ Upload queued!", "bg-success");

        return fetch("/run-command", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: `command=account_login:${selectedAccountId}`,
        })
          .then((res) => res.json())
          .then((loginData) => {
            if (loginData.status === 200) {
              showToast("🔄 Account refreshed after upload", "bg-info");
            } else {
              showToast(
                `⚠️ Upload done but refresh failed: ${loginData.message}`,
                "bg-warning"
              );
            }
            fetchFileDetails(fileId);
          });
      } else {
        showToast(`❌ Upload failed: ${data.message}`, "bg-danger");
      }
    })
    .catch((err) => {
      console.error("❌ Upload error:", err);
      showToast("❌ Upload failed due to network error", "bg-danger");
    });
}

function generateExpiringLink(fileId) {
  console.log(`🔗 Generating expiring link for file ID: ${fileId}`);
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
        showToast(`✅ Missing sharing links generated`, "bg-success");
        loadFilesTable();
      } else {
        showToast(`❌ Failed: ${data.message || "Unknown error"}`, "bg-danger");
      }
    })
    .catch((err) => {
      console.error("❌ Generate missing links error:", err);
      showToast("❌ Failed to generate missing sharing links", "bg-danger");
    });
}

function updateAllDetails() {
  // Trigger local indexing
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "file_local_index" }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`📂 Local scan started in background`, "bg-info");
      }
    });

  // Trigger MEGA details update
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "file_group_details" }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`☁️ MEGA scan started in background`, "bg-info");
      }
    })
    .catch((err) => {
      console.error("❌ Error during update process:", err);
      showToast("❌ Failed to trigger updates", "bg-danger");
    });
}

function fetchFileDetails(fileId) {
  console.log(`🔍 Checking which source to refresh for file ID: ${fileId}`);

  // Step 1: Get the full file object first
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
          }).then((res) => res.json())
        );
      }

      if (file.l_path) {
        promises.push(
          fetch("/run-command", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: `command=file_local_details:${fileId}`,
          }).then((res) => res.json())
        );
      }

      if (promises.length === 0) {
        showToast(
          `⚠️ No cloud or local path for file #${fileId}`,
          "bg-warning"
        );
        return Promise.resolve([]); // Prevents undefined `.then()` below
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
        showToast(`✅ File details refreshed`, "bg-success");
      } else {
        showToast(`⚠️ Failed to update details`, "bg-warning");
      }
    })
    .catch((err) => {
      console.error("❌ Error fetching file details:", err);
      showToast("❌ Failed to fetch file details", "bg-danger");
    });
}

function updateRowWithFileData(file) {
  let row = [...document.querySelectorAll("#filesTableBody tr")].find(
    (r) => r.children[0]?.textContent.trim() == file.id
  );

  const hasLink = file.m_sharing_link && file.m_sharing_link.trim() !== "";
  const copyBtnColor = hasLink ? "btn-success" : "btn-tertiary";

  const html = `
    <td style="display:none">${file.id}</td>
    <td class="path-column">
      <div class="mb-1"><i class="fas fa-folder me-2 text-info opacity-75"></i> ${file.l_path || "-"}</div>
      <div class="small text-muted"><i class="fas fa-cloud me-2 text-warning opacity-75"></i> ${file.m_path || "-"}</div>
    </td>
    <td class="fw-bold">${file.l_folder_name || file.m_folder_name || "-"}</td>
    <td class="text-end" data-order="${file.l_folder_size || 0}">${
      formatBytes(file.l_folder_size || 0) === "0.00 B"
        ? "-"
        : formatBytes(file.l_folder_size)
    }</td>
    <td class="text-end ${Math.abs((file.l_folder_size || 0) - (file.m_folder_size || 0)) > 1024 * 1024 ? 'text-warning fw-bold' : ''}" data-order="${file.m_folder_size || 0}">${
      formatBytes(file.m_folder_size || 0) === "0.00 B"
        ? "-"
        : formatBytes(file.m_folder_size)
    }</td>
    <td class="text-center">${file.is_local ? '<i class="fas fa-check-circle text-success"></i>' : '<i class="fas fa-times-circle text-muted" style="opacity:0.3"></i>'}</td>
    <td class="text-center">
      <span class="d-inline-block"
        ${
          file.cloud_email
            ? `data-mdb-toggle="tooltip" title="Account: ${file.cloud_email}"`
            : ""
        }
        onclick="handleCloudStatusClick(${file.id}, '${
    file.l_folder_name || file.m_folder_name
  }', '${file.cloud_email || ""}')"
        style="cursor: pointer;">
        ${file.is_cloud 
           ? (Number(file.m_folder_size) > 0 
              ? '<i class="fas fa-check-circle text-success"></i>' 
              : '<i class="fas fa-cloud text-warning" title="Partial/Empty Sync"></i>')
           : '<i class="fas fa-times-circle text-muted" style="opacity:0.3"></i>'}
      </span>
    </td>
    <td class="text-end">
      <div class="d-flex justify-content-end gap-1">
        <button class="btn btn-sm ${copyBtnColor} shadow-0" ${
    !hasLink ? "disabled" : ""
  } title="Copy Sharing Link" onclick="copySharingLink('${
    file.m_sharing_link
  }', ${file.id})">
          <i class="fas fa-link"></i>
        </button>
        <div class="btn-group dropdown">
          <button type="button" class="btn btn-sm btn-tertiary dropdown-toggle dropdown-toggle-split shadow-0" data-mdb-toggle="dropdown" aria-expanded="false">
            <i class="fas fa-ellipsis-v"></i>
          </button>
          <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end">
            ${
              file.is_cloud
                ? `<li><a class="dropdown-item" href="#" onclick="generateSharingLink(${file.id})"><i class="fas fa-link me-2"></i> Generate Sharing Link</a></li>`
                : ""
            }
            ${
              file.pro_account
                ? `<li><a class="dropdown-item" href="#" onclick="generateExpiringLink(${file.id})"><i class="fas fa-clock me-2"></i> Generate Expiring Link</a></li>`
                : ""
            }
            <li><a class="dropdown-item ${file.is_cloud ? 'text-warning' : 'text-success'}" href="#" onclick="uploadToCloud(${file.id})"><i class="fas fa-cloud-upload-alt me-2"></i> ${file.is_cloud ? 'Re-upload to Cloud' : 'Upload to Cloud'}</a></li>
            <li><hr class="dropdown-divider"></li>
            <li><a class="dropdown-item text-secondary small" href="#" onclick="fetchFileDetails(${file.id})"><i class="fas fa-info-circle me-2"></i> Fetch File Details</a></li>
          </ul>
        </div>
      </div>
    </td>
  `;

  if (row) {
    row.innerHTML = html;
  } else {
    row = document.createElement("tr");
    row.innerHTML = html;
    document.getElementById("filesTableBody").appendChild(row);
  }

  const dropdownToggle = row.querySelector(".dropdown-toggle");
  if (dropdownToggle) new mdb.Dropdown(dropdownToggle);
}

function handleCloudStatusClick(fileId, folderName, email) {
  if (email && email.trim()) {
    showToast(
      `📂 File #${fileId} - ${folderName} is uploaded to account ${email}`,
      "bg-success"
    );
  } else {
    showToast(
      `📂 File #${fileId} is not uploaded to any cloud account`,
      "bg-warning"
    );
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
      console.log(data);
      const table = $("#filesTable");

      if ($.fn.DataTable.isDataTable("#filesTable")) {
        table.DataTable().clear().destroy();
      }

      const tbody = document.getElementById("filesTableBody");
      tbody.innerHTML = "";

      data.files.forEach(updateRowWithFileData);

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
    showToast(`⚠️ No sharing link available for file #${fileId}`, "bg-warning");
    return;
  }

  navigator.clipboard
    .writeText(link)
    .then(() => {
      showToast(`🔗 Sharing link copied for file #${fileId}`, "bg-success");
    })
    .catch((err) => {
      console.error("❌ Clipboard copy failed:", err);
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
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Initializing...`;

    try {
      const res = await fetch("/run-command", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `command=file_batch_sync`,
      });
      
      const result = await res.json();
      if (result.status === 200) {
        showToast("🚀 Auto-Batch upload started in background!", "bg-info");
        setTimeout(loadFilesTable, 3000);
      } else {
        showToast(`❌ Failed: ${result.message}`, "bg-danger");
      }
    } catch (err) {
      console.error("Batch upload error:", err);
      showToast("❌ Connection error during batch upload start.", "bg-danger");
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  };
}
