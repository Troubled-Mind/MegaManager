document.addEventListener("DOMContentLoaded", () => {
  // Load the account table
  if (document.getElementById("accountTableBody")) {
    loadAccountTable();
  }

  // Initialize the verify modal event
  const verifyModalEl = document.getElementById("verifyAccountModal");
  if (verifyModalEl) {
    verifyModalEl.addEventListener("hidden.mdb.modal", () => {
      document.getElementById("verificationLinkInput").value = "";
    });
  }

  // Initialize the file upload modal
  const fileUploadModal = new mdb.Modal(
    document.getElementById("fileUploadModal")
  );

  // Add event listener to the "Import CSV" button to trigger modal open
  const importCsvButton = document.querySelector('[data-bs-toggle="modal"]');
  importCsvButton.addEventListener("click", function () {
    fileUploadModal.show(); // Show the modal programmatically
  });

  // Handle the form submission for file upload
  const fileUploadForm = document.getElementById("fileUploadForm");

  fileUploadForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const fileInput = document.getElementById("csvFile");
    const file = fileInput.files[0];

    if (!file) {
      alert("Please choose a file to upload");
      return;
    }

    const reader = new FileReader();

    reader.onload = function (event) {
      const csvData = event.target.result;
      const parsedData = parseCSV(csvData);
      addNewAccounts(parsedData); // Process the parsed data
      fileUploadModal.hide(); // Close the modal after uploading
    };

    reader.readAsText(file);
  });
});

function formatDate(isoString) {
  if (!isoString) return "-";
  const date = new Date(isoString);
  const options = {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  };
  return date.toLocaleString("en-GB", options);
}

// refresh login for an account
function refreshAccount(id, options = {}) {
  const btn = document.getElementById(`refresh-btn-${id}`);
  const silent = options.silent || false;
  const icon = btn?.querySelector("i");

  if (!silent && btn) {
    icon?.classList.add("fa-spin");
    btn.disabled = true;
    btn.classList.remove("btn-outline-light", "btn-success", "btn-danger");
    btn.classList.add("btn-outline-warning");
  }

  return fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=mega-login:${id}`,
  })
    .then((res) => res.json())
    .then((result) => {
      if (!result || result.status !== 200) {
        throw new Error(result.message || "Unknown login error");
      }

      if (!silent && btn) {
        btn.classList.remove("btn-outline-warning");
        btn.classList.add("btn-success");
        icon?.classList.remove("fa-spin");
      }

      if (!silent) {
        showToast(`✅ Account ${id} refreshed successfully`, "bg-success");
      }

      return fetch("/run-command", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `command=mega-get-account:${id}`,
      });
    })
    .then((res) => res.json())
    .then((data) => {
      const acc = data.account;
      const usedQuota = acc.used_quota;
      const totalQuota = acc.total_quota;
      const remainingQuota = totalQuota - usedQuota;
      let usagePercentage = (usedQuota / totalQuota) * 100;
      if (isNaN(usagePercentage)) {
        usagePercentage = 0;
      }
      let progressColor = "success";
      if (usagePercentage > 50 && usagePercentage <= 80) {
        progressColor = "warning";
      } else if (usagePercentage > 80) {
        progressColor = "danger";
      }
      const newRow = document.createElement("tr");

      const maskedPassword = acc.password.replace(/./g, "•");

      newRow.id = `account-row-${acc.id}`;
      newRow.innerHTML = `
        <td>${acc.id}</td>
        <td>${acc.email}</td>
        <td>
        <span id="password-${acc.id}" class="masked-password" data-password="${
        acc.password
      }">
        ${"•".repeat(acc.password.length)}
        </span>
        <button id="toggle-password-${
          acc.id
        }" class="btn btn-sm btn-pwreveal btn-link" onclick="togglePasswordVisibility(${
        acc.id
      })">
          <i class="fas fa-eye"></i>
        </button>
        </td>
        <td>${acc.is_pro ? "✅" : "❌"}</td>
        <td>
            <div class="progress" style="height: 20px;">
              <div class="progress-bar bg-${progressColor}" role="progressbar" style="width: ${usagePercentage}%" aria-valuenow="${usagePercentage}" aria-valuemin="0" aria-valuemax="100">
                ${Math.round(usagePercentage)}%
              </div>
            </div>
        </td>
        <td>${formatBytes(remainingQuota)}</td>
        <td>${formatDate(acc.last_login)}</td>
        <td>
          <button id="refresh-btn-${
            acc.id
          }" class="btn btn-sm btn-outline-light" title="Log in and refresh quota" onclick="refreshAccount(${
        acc.id
      })">
            <i class="fas fa-sync-alt"></i>
          </button>
          <div class="btn-group dropdown">
            <button type="button" class="btn btn-sm btn-tertiary dropdown-toggle dropdown-toggle-split" data-mdb-toggle="dropdown" aria-expanded="false">
              <i class="fas fa-ellipsis-v"></i>
            </button>
            <ul class="dropdown-menu dropdown-menu-dark">
              <li id="verify-${
                acc.id
              }" class="verify-button" style="display: none;">
                <a class="dropdown-item text-warning" href="#" onclick="openVerifyModal(${
                  acc.id
                }, '${acc.email}')">
                  <i class="fas fa-user-check me-2"></i> Verify Account
                </a>
              </li>
              <li>
                <a class="dropdown-item text-danger" href="#" onclick="confirmDeleteAccount(${
                  acc.id
                }, '${acc.email}')">
                  <i class="fas fa-trash-alt me-2"></i> Delete Account
                </a>
              </li>
            </ul>
          </div>
        </td>
      `;

      const oldRow = document.getElementById(`account-row-${acc.id}`);
      if (oldRow) oldRow.replaceWith(newRow);

      new mdb.Dropdown(
        document.querySelector(`#account-row-${acc.id} .dropdown-toggle`)
      );
      newRow.classList.add("flash-row");
    })
    .catch((err) => {
      console.error(`Refresh for account ${id} failed:`, err);

      const message = err.message || "Unknown error";
      console.log("Error Message:", message);

      // If the error message contains "unconfirmed account", add the class and show the verify button
      if (message.toLowerCase().includes("unconfirmed account")) {
        const row = document.getElementById(`account-row-${id}`);
        if (row) {
          row.classList.add("table-unverified");
        }
        showToast(`❌ Account ${id} is unverified: ${message}`, "bg-danger");
      } else {
        showToast(
          `❌ Failed to refresh account ${id}: ${message}`,
          "bg-danger"
        );
      }

      if (!silent && btn) {
        btn.classList.remove("btn-outline-warning");
        btn.classList.add("btn-danger");
        icon?.classList.remove("fa-spin");
      }

      const row = document.getElementById(`account-row-${id}`);
      if (row) {
        row.classList.remove("flash-row");
        row.classList.add("table-error");
      }
    })
    .finally(() => {
      if (!silent && btn) {
        setTimeout(() => {
          btn.classList.remove("btn-success", "btn-danger");
          btn.classList.add("btn-outline-light");
          btn.disabled = false;
          icon?.classList.remove("fa-spin");
        }, 3000);
      }
    });
}

// load all accounts from database
function loadAccountTable() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=mega-get-accounts`,
  })
    .then((res) => res.json())
    .then((data) => {
      const table = $("#accountTable");

      if ($.fn.DataTable.isDataTable("#accountTable")) {
        table.DataTable().clear().destroy();
      }

      const tbody = document.getElementById("accountTableBody");
      tbody.innerHTML = "";

      const now = new Date();
      const cutoff = new Date(now.setMonth(now.getMonth() - 2));

      const staleAccounts = [];
      const recentAccounts = [];

      data.accounts.forEach((acc) => {
        const lastLogin = acc.last_login ? new Date(acc.last_login) : null;
        if (lastLogin && lastLogin < cutoff) {
          staleAccounts.push(acc);
        } else {
          recentAccounts.push(acc);
        }
      });

      const sortedAccounts = [...staleAccounts, ...recentAccounts];

      sortedAccounts.forEach((acc) => {
        const row = document.createElement("tr");
        const usedQuota = acc.used_quota;
        const totalQuota = acc.total_quota;
        const remainingQuota = totalQuota - usedQuota;
        let usagePercentage = (usedQuota / totalQuota) * 100;
        if (isNaN(usagePercentage)) {
          usagePercentage = 0;
        }
        let progressColor = "success";
        if (usagePercentage > 50 && usagePercentage <= 80) {
          progressColor = "warning";
        } else if (usagePercentage > 80) {
          progressColor = "danger";
        }
        const isStale = acc.last_login && acc.last_login < cutoff;
        const staleFlag = isStale ? 1 : 0;
        const maskedPassword = acc.password.replace(/./g, "•");
        row.id = `account-row-${acc.id}`;
        row.innerHTML = `
          <td style="display: none !important;">${staleFlag}</td>
          <td>${acc.id}</td>
          <td>${acc.email}</td>
          <td>
          <span id="password-${
            acc.id
          }" class="masked-password" data-password="${acc.password}">
          ${"•".repeat(acc.password.length)}
        </span>
        <button id="toggle-password-${
          acc.id
        }" class="btn btn-sm btn-pwreveal btn-link" onclick="togglePasswordVisibility(${
          acc.id
        })">
          <i class="fas fa-eye"></i>
        </button>
          </td>
          <td>${acc.is_pro ? "✅" : "❌"}</td>
          <td>
            <div class="progress" style="height: 20px;">
              <div class="progress-bar bg-${progressColor}" role="progressbar" style="width: ${usagePercentage}%" aria-valuenow="${usagePercentage}" aria-valuemin="0" aria-valuemax="100">
                ${Math.round(usagePercentage)}%
              </div>
            </div>
          </td>
          <td>${formatBytes(remainingQuota)}</td>
          <td>${formatDate(acc.last_login)}</td>
          <td>
            <button id="refresh-btn-${
              acc.id
            }" class="btn btn-sm btn-outline-light" onclick="refreshAccount(${
          acc.id
        })">
              <i class="fas fa-sync-alt"></i>
            </button>
            <div class="btn-group dropdown">
                  <button type="button" class="btn btn-sm btn-tertiary dropdown-toggle dropdown-toggle-split" data-mdb-toggle="dropdown" aria-expanded="false">
                    <i class="fas fa-ellipsis-v"></i>
                  </button>
                  <ul class="dropdown-menu dropdown-menu-dark">
                    <li id="verify-${
                      acc.id
                    }" class="verify-button" style="display: none;">
                      <a class="dropdown-item text-warning" href="#" onclick="openVerifyModal(${
                        acc.id
                      }, '${acc.email}')">
                        <i class="fas fa-user-check me-2"></i> Verify Account
                      </a>
                    </li>
                    <li>
                      <a class="dropdown-item text-danger" href="#" onclick="confirmDeleteAccount(${
                        acc.id
                      }, '${acc.email}')">
                        <i class="fas fa-trash-alt me-2"></i> Delete Account
                      </a>
                    </li>
                  </ul>
                </div>
          </td>
        `;

        if (staleAccounts.includes(acc)) {
          row.classList.add("table-stale");
        }

        tbody.appendChild(row);
        const dropdownToggle = row.querySelector(".dropdown-toggle");
        if (dropdownToggle) new mdb.Dropdown(dropdownToggle);
      });

      $("#accountTable").DataTable({
        responsive: true,
        order: [[0, "desc"]],
        columnDefs: [
          {
            targets: 0,
            visible: false,
            searchable: false,
          },
        ],
      });
    })
    .catch((err) => console.error("Failed to load accounts:", err));
}

function refreshAllAccounts() {
  const btn = document.getElementById("refreshAllBtn");
  const icon = document.getElementById("refreshAllIcon");

  btn.classList.remove("btn-primary", "btn-success", "btn-danger");
  btn.classList.add("btn-warning");
  icon.classList.add("fa-spin");
  btn.disabled = true;

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=mega-login:all`,
  })
    .then((res) => res.json())
    .then(async (data) => {
      const ids = data.account_ids || [];
      const total = ids.length;

      let failedCount = 0;

      for (let i = 0; i < total; i++) {
        const id = ids[i];
        btn.innerHTML = `<i class="fas fa-sync-alt me-2 fa-spin" id="refreshAllIcon"></i> Refreshing account ${
          i + 1
        } / ${total}...`;

        const success = await refreshAccount(id, { silent: true });
        if (!success) failedCount++;
      }

      // ✅ Finished
      btn.innerHTML = `<i class="fas fa-check me-2"></i> All accounts refreshed!`;
      btn.classList.remove("btn-warning");
      btn.classList.add("btn-success");
    })
    .catch((err) => {
      console.error("Refresh all failed:", err);
      btn.innerHTML = `<i class="fas fa-exclamation-triangle me-2"></i> Refresh failed`;
      btn.classList.remove("btn-warning");
      btn.classList.add("btn-danger");
    })
    .finally(() => {
      icon.classList.remove("fa-spin");
      setTimeout(() => {
        btn.innerHTML = `<i class="fas fa-sync-alt me-2" id="refreshAllIcon"></i> Refresh login for all accounts`;
        btn.classList.remove("btn-success", "btn-danger");
        btn.classList.add("btn-primary");
        btn.disabled = false;
      }, 4000);
    });
}

let deleteTargetAccountId = null;

function confirmDeleteAccount(id, email) {
  deleteTargetAccountId = id;

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=mega-get-account:${id}`,
  })
    .then((res) => res.json())
    .then((data) => {
      const fileCount = data.account.linked_files || 0;
      const modalBody = document.getElementById("deleteAccountModalBody");

      modalBody.innerHTML = `
        Are you sure you wish to delete the account:<br />
        <strong>${email}</strong>?
        <br /><br />
        <span class="text-danger">
          This account has <strong>${fileCount}</strong> linked file${
        fileCount === 1 ? "" : "s"
      } in this program.
        </span>
        <br />
        <small class="text-muted">
          No files will be deleted from your MEGA drive, but all references to them will be removed from Mega Manager.
        </small>
      `;

      const modal = new mdb.Modal(
        document.getElementById("deleteAccountModal")
      );
      modal.show();

      const confirmBtn = document.getElementById("confirmDeleteBtn");
      confirmBtn.onclick = () => {
        deleteAccount(deleteTargetAccountId);
        modal.hide();
      };
    });
}

function deleteAccount(id) {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=mega-delete-account:${id}`,
  })
    .then((res) => res.json())
    .then(() => {
      const row = document.getElementById(`account-row-${id}`);
      if (row) row.remove();

      const table = $("#accountTable").DataTable();
      table.row(`#account-row-${id}`).remove().draw();
      showToast("Account deleted successfully!", "bg-success");
      console.log(`Account ${id} deleted.`);
    })
    .catch((err) => {
      console.error(`Failed to delete account ${id}:`, err);
      showToast("Account failed to delete!", "bg-danger");
      alert("An error occurred while deleting the account.");
    });
}

let verifyTargetId = null;

function openVerifyModal(accountId) {
  verifyTargetId = accountId;
  const modal = new mdb.Modal(document.getElementById("verifyAccountModal"));
  modal.show();

  document.getElementById("submitVerifyBtn").onclick = () => {
    const link = document.getElementById("verificationLinkInput").value.trim();
    if (!link) {
      showToast("Please paste a valid verification link", "bg-warning");
      return;
    }

    verifyAccount(verifyTargetId, link);
    modal.hide();
  };
}

function verifyAccount(accountId, link) {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=mega-verify-account:${accountId}|${encodeURIComponent(
      link
    )}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`✅ Account ${accountId} verified`, "bg-success");
        refreshAccount(accountId);
      } else {
        showToast(`❌ Verification failed: ${data.message}`, "bg-danger");
      }
    })
    .catch((err) => {
      console.error(`Verification error for ${accountId}:`, err);
      showToast("❌ Failed to verify account", "bg-danger");
    });
}

let currentRevealedPasswordId = null;

function togglePasswordVisibility(accountId) {
  const passwordElement = document.getElementById(`password-${accountId}`);
  const toggleButton = document.getElementById(`toggle-password-${accountId}`);
  const password = passwordElement.getAttribute("data-password");

  const maskedPassword = "•".repeat(password.length);

  // If another password is already revealed, hide it first
  if (currentRevealedPasswordId && currentRevealedPasswordId !== accountId) {
    const previouslyRevealedPasswordElement = document.getElementById(
      `password-${currentRevealedPasswordId}`
    );
    const previouslyRevealedToggleButton = document.getElementById(
      `toggle-password-${currentRevealedPasswordId}`
    );

    // Hide the previously revealed password
    previouslyRevealedPasswordElement.textContent = "•".repeat(
      previouslyRevealedPasswordElement.getAttribute("data-password").length
    );
    previouslyRevealedToggleButton.innerHTML = '<i class="fas fa-eye"></i>';
    previouslyRevealedPasswordElement.classList.add("masked-password");
  }

  // Reveal or hide the current password
  if (passwordElement.classList.contains("masked-password")) {
    // Reveal password
    passwordElement.textContent = password;
    toggleButton.innerHTML = '<i class="fas fa-eye-slash"></i>';
    passwordElement.classList.remove("masked-password");

    // Set this as the currently revealed password
    currentRevealedPasswordId = accountId;

    // Hide the password after 10 seconds
    setTimeout(() => {
      passwordElement.textContent = maskedPassword;
      toggleButton.innerHTML = '<i class="fas fa-eye"></i>';
      passwordElement.classList.add("masked-password");
      currentRevealedPasswordId = null;
    }, 10000);
  } else {
    // Hide password
    passwordElement.textContent = maskedPassword;
    toggleButton.innerHTML = '<i class="fas fa-eye"></i>';
    passwordElement.classList.add("masked-password");

    // Clear the revealed password tracking
    currentRevealedPasswordId = null;
  }
}

// format the bytes to human-readable format
function formatBytes(bytes) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (bytes >= 1024 && i < units.length - 1) {
    bytes /= 1024;
    i++;
  }
  return `${bytes.toFixed(2)} ${units[i]}`;
}

// Add new accounts from csv
async function addNewAccounts(parsedData) {
  const btn = document.getElementById("addNewAccountsBtn");
  btn.disabled = true;

  try {
    // We need to ensure parsedData contains only the rows (no headers)
    const rows = parsedData.slice(1); // Remove header row if included

    const res = await fetch("/run-command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json", // Use JSON content type
      },
      body: JSON.stringify({
        command: "csv-load-accounts",
        args: rows, // Pass only the rows of CSV data
      }),
    });

    const data = await res.json();
    const ids = data.account_ids || [];
    const total = ids.length;

    loadAccountTable(); // Reload the account table after adding new accounts

    // Iterate over account ids and refresh them one by one
    for (let i = 0; i < total; i++) {
      const id = ids[i];
      await refreshAccount(id, { silent: true });
    }

    showToast("New accounts added!", "bg-success");
  } catch (err) {
    console.error("Adding new accounts failed:", err);
    showToast("Add failed", "bg-danger");
  } finally {
    setTimeout(() => {
      btn.disabled = false;
    }, 4000);
  }
}

function parseCSV(csvData) {
  const lines = csvData.split("\n");
  const result = [];

  lines.forEach((line) => {
    if (line.trim() === "") return; // Skip empty lines
    result.push(line); // Push each row as a string
  });

  return result;
}
