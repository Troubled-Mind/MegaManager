document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("filesTableBody")) {
    loadFilesTable();
  }
});

function generateSharingLink(fileId) {
  console.log(`🔗 Generate sharing link for file ID: ${fileId}`);
  showToast(`Generating link for file #${fileId}...`, "bg-info");
  // TODO: implement backend command
}

function uploadToCloud(fileId) {
  console.log(`☁️ Upload to cloud for file ID: ${fileId}`);
  showToast(`Uploading file #${fileId}...`, "bg-success");
  // TODO: implement backend command
}

function deleteFromCloud(fileId) {
  console.log(`🗑️ Delete from cloud for file ID: ${fileId}`);
  showToast(`Deleting cloud copy of file #${fileId}...`, "bg-danger");
  // TODO: implement backend command
}

function fetchFileDetails(fileId) {
  console.log(`🔍 Fetching details for file ID: ${fileId}`);
  showToast(`Fetching details for file #${fileId}...`, "bg-secondary");

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=mega-get-file-details:${fileId}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200 && data.file) {
        showToast(`File details updated for #${fileId}`, "bg-success");

        const file = data.file;
        const row = [...document.querySelectorAll("#filesTableBody tr")].find(
          (r) => r.children[0]?.textContent.trim() == fileId
        );
        if (!row) return;

        const hasLink = file.sharing_link && file.sharing_link.trim() !== "";
        const copyBtnColor = hasLink ? "btn-success" : "btn-outline-light";
        const sharingLink = file.sharing_link || "";

        row.innerHTML = `
          <td style="display:none">${file.id}</td>
          <td class="small text-muted">
            <div><i class="fas fa-hdd me-1 text-info"></i> ${
              file.local_path || "-"
            }</div>
            <div><i class="fas fa-cloud me-1 text-warning"></i> ${
              file.cloud_path || "-"
            }</div>
          </td>
          <td>${file.folder_name || "-"}</td>
          <td>${formatBytes(file.folder_size) || "-"}</td>
          <td>${file.is_local ? "✅" : "❌"}</td>
          <td>
            <span
              class="d-inline-block"
              ${
                file.cloud_email
                  ? `data-mdb-toggle="tooltip" title="${file.cloud_email}"`
                  : ""
              }
              onclick="handleCloudStatusClick(${file.id}, '${
          file.folder_name
        }', '${file.cloud_email || ""}')"
              style="cursor: pointer;"
            >
              ${file.is_cloud ? "✅" : "❌"}
            </span>
          </td>
          <td>
            <button class="btn btn-sm ${copyBtnColor} me-1" ${
          !hasLink ? "disabled" : ""
        } title="Copy Sharing Link" onclick="copySharingLink('${sharingLink}', ${
          file.id
        })">
              <i class="fas fa-link"></i>
            </button>
            <div class="btn-group dropdown">
              <button type="button" class="btn btn-sm btn-tertiary dropdown-toggle dropdown-toggle-split" data-mdb-toggle="dropdown" aria-expanded="false">
                <i class="fas fa-ellipsis-v"></i>
              </button>
              <ul class="dropdown-menu dropdown-menu-dark">
                <li><a class="dropdown-item" href="#" onclick="generateSharingLink(${
                  file.id
                })"><i class="fas fa-link me-2"></i> Generate Sharing Link</a></li>
                <li><a class="dropdown-item text-success" href="#" onclick="uploadToCloud(${
                  file.id
                })"><i class="fas fa-cloud-upload-alt me-2"></i> Upload to Cloud</a></li>
                <li><a class="dropdown-item text-danger" href="#" onclick="deleteFromCloud(${
                  file.id
                })"><i class="fas fa-cloud-meatball me-2"></i> Delete from Cloud</a></li>
                <li><a class="dropdown-item text-info" href="#" onclick="fetchFileDetails(${
                  file.id
                })"><i class="fas fa-info-circle me-2"></i> Fetch File Details</a></li>
              </ul>
            </div>
          </td>
        `;

        const dropdownToggle = row.querySelector(".dropdown-toggle");
        if (dropdownToggle) new mdb.Dropdown(dropdownToggle);
      } else {
        showToast(`Failed: ${data.message}`, "bg-danger");
      }
    })
    .catch((err) => {
      console.error("❌ Failed to fetch file details:", err);
      showToast("Failed to fetch file details", "bg-danger");
    });
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
    body: `command=db-fetch-files`,
  })
    .then((res) => res.json())
    .then((data) => {
      const table = $("#filesTable");

      if ($.fn.DataTable.isDataTable("#filesTable")) {
        table.DataTable().clear().destroy();
      }

      const tbody = document.getElementById("filesTableBody");
      tbody.innerHTML = "";

      data.files.forEach((file) => {
        const row = document.createElement("tr");
        const hasLink = file.sharing_link && file.sharing_link.trim() !== "";
        const copyBtnColor = hasLink ? "btn-success" : "btn-outline-light";
        const sharingLink = file.sharing_link || "";

        row.innerHTML = `
            <td style="display:none">${file.id}</td>
            <td class="small text-muted">
              <div><i class="fas fa-hdd me-1 text-info"></i> ${
                file.local_path || "-"
              }</div>
              <div><i class="fas fa-cloud me-1 text-warning"></i> ${
                file.cloud_path || "-"
              }</div>
            </td>
            <td>${file.folder_name || "-"}</td>
            <td>${formatBytes(file.folder_size) || "-"}</td>
            <td>${file.is_local ? "✅" : "❌"}</td>
            <td>
              <span
                class="d-inline-block"
                ${
                  file.cloud_email
                    ? `data-mdb-toggle="tooltip" title="${file.cloud_email}"`
                    : ""
                }
                onclick="handleCloudStatusClick(${file.id}, '${
          file.folder_name
        }', '${file.cloud_email || ""}')"
                style="cursor: pointer;"
              >
                ${file.is_cloud ? "✅" : "❌"}
              </span>
            </td>
            <td>
            
              <button class="btn btn-sm ${copyBtnColor} me-1" ${
          !hasLink ? "disabled" : ""
        } title="Copy Sharing Link" onclick="copySharingLink('${sharingLink}', ${
          file.id
        })">
                <i class="fas fa-link"></i>
              </button>
              <div class="btn-group dropdown">
                <button type="button" class="btn btn-sm btn-tertiary dropdown-toggle dropdown-toggle-split" data-mdb-toggle="dropdown" aria-expanded="false">
                  <i class="fas fa-ellipsis-v"></i>
                </button>
                <ul class="dropdown-menu dropdown-menu-dark">
                  <li>
                    <a class="dropdown-item" href="#" onclick="generateSharingLink(${
                      file.id
                    })">
                      <i class="fas fa-link me-2"></i> Generate Sharing Link
                    </a>
                  </li>
                  <li>
                    <a class="dropdown-item text-success" href="#" onclick="uploadToCloud(${
                      file.id
                    })">
                      <i class="fas fa-cloud-upload-alt me-2"></i> Upload to Cloud
                    </a>
                  </li>
                  <li>
                    <a class="dropdown-item text-danger" href="#" onclick="deleteFromCloud(${
                      file.id
                    })">
                      <i class="fas fa-cloud-meatball me-2"></i> Delete from Cloud
                    </a>
                  </li>
                  <li>
                    <a class="dropdown-item text-info" href="#" onclick="fetchFileDetails(${
                      file.id
                    })">
                      <i class="fas fa-info-circle me-2"></i> Fetch File Details
                    </a>
                  </li>
                </ul>
              </div>
            </td>
          `;

        tbody.appendChild(row);
        const dropdownToggle = row.querySelector(".dropdown-toggle");
        if (dropdownToggle) {
          new mdb.Dropdown(dropdownToggle);
        }
      });

      $("#filesTable").DataTable({
        responsive: true,
        lengthMenu: [50, 100, 250, 500, "All"],
        order: [[0, "desc"]],
        columnDefs: [
          {
            targets: [6], // "Actions" column
            orderable: false,
          },
        ],
      });
    })
    .catch((err) => console.error("Failed to load files:", err));
}

// format the bytes to human-readable format
function formatBytes(bytes) {
  if (bytes == null || isNaN(bytes)) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i++;
  }
  return `${bytes.toFixed(2)} ${units[i]}`;
}
