document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("filesTableBody")) {
    loadFilesTable();
  }
});

function loadFilesTable() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=mega-get-files`, //THIS DOES NOT EXIST YET
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

        row.innerHTML = `
            <td>${file.id}</td>
            <td>${file.local_path || "-"}</td>
            <td>${file.cloud_path || "-"}</td>
            <td>${file.folder_name || "-"}</td>
            <td>${file.is_local ? "✅" : "❌"}</td>
            <td>${file.is_cloud ? "✅" : "❌"}</td>
            <td>
              <button class="btn btn-sm btn-outline-light" onclick="handleFileAction(${
                file.id
              })">
                <i class="fas fa-cog"></i>
              </button>
            </td>
          `;

        tbody.appendChild(row);
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

function handleFileAction(fileId) {
  console.log(`Action triggered for file ID: ${fileId}`);
  // Add file-specific actions here
}
