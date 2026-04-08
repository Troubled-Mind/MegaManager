document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("importBtn").onclick = async () => {
        showToast(`⚠️ Import starting...`, "bg-info");
        await importLinks();
        showToast(`✅ Import completed!`, "bg-success");
    }
});

async function importLinks() {
    const links = document.getElementById('linksInput').value
        .split('\n')
        .map(l => l.trim())
        .filter(l => l.length > 0);

    if (!links.length) {
        alert('Please enter at least one MEGA link.');
        return;
    }

    document.getElementById('importedTableBody').innerHTML = '';
    document.getElementById('failedTableBody').innerHTML = '';

    // Call backend API
    const res = await fetch('/run-command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            command: "file_import_links",
            args: { links }
        })
    });
    const data = await res.json();

    console.log(data);

    // Display imported links
    if (data.imported && data.imported.length) {
        let rows = "";
        data.imported.forEach((item, idx) => {
            const hasLink = item.link && item.link.trim() !== "";
            const copyBtnColor = hasLink ? "btn-success" : "btn-tertiary";
            const displaySize = (item.size === null || item.size === undefined) ? "Unknown" : formatBytes(item.size);
            rows += `<tr>
                <td>${item.account || ''}</td>
                <td>
                    <div class="mb-1"><i class="fas fa-folder me-2 text-info opacity-75"></i> ${item.path || "-"}</div>
                </td>
                <td>
                    ${hasLink ? `<a href="${item.link}" target="_blank">${item.link}</a>` : "-"}
                </td>
                <td>${displaySize || "-"}</td>
                <td>
                    <button class="btn btn-sm ${copyBtnColor} shadow-0" ${!hasLink ? "disabled" : ""}
                        title="Copy Sharing Link"
                        onclick="copySharingLink('${item.link}', 'imported-${idx}')">
                        <i class="fas fa-link"></i>
                    </button>
                </td>
            </tr>`;
        });
        document.getElementById('importedTableBody').innerHTML = rows;
    } else {
        document.getElementById('importedTableBody').innerHTML = "";
    }

    // Display failed links
    if (data.failed && data.failed.length) {
        let failedRows = "";
        data.failed.forEach((item, idx) => {
            const hasLink = item.link && item.link.trim() !== "";
            const copyBtnColor = hasLink ? "btn-success" : "btn-tertiary";
            const displaySize = (item.size === null || item.size === undefined) ? "Unknown" : formatBytes(item.size);
            failedRows += `<tr>
                <td>
                    ${hasLink ? `<a href="${item.link}" target="_blank">${item.link}</a>` : "-"}
                </td>
                <td>${displaySize || "-"}</td>
                <td>
                    <button class="btn btn-sm ${copyBtnColor} shadow-0" ${!hasLink ? "disabled" : ""}
                        title="Copy Sharing Link"
                        onclick="copySharingLink('${item.link}', 'failed-${idx}')">
                        <i class="fas fa-link"></i>
                    </button>
                </td>
            </tr>`;
        });

        document.getElementById('failedTableBody').innerHTML = failedRows;
    }
}

function copySharingLink(link, rowId) {
    if (!link || link.trim() === "") {
        alert("⚠️ No sharing link available.");
        return;
    }
    navigator.clipboard
        .writeText(link)
        .catch((err) => {
            console.error("❌ Clipboard copy failed:", err);
            alert("Failed to copy link");
        });
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