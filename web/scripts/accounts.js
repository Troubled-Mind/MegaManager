document.addEventListener("DOMContentLoaded", () => {
  // Load the account table
  if (document.getElementById("accountTableBody")) {
    loadAccountTable();
  }

  // Reset verification modal input on close
  const verifyModalEl = document.getElementById("verifyAccountModal");
  if (verifyModalEl) {
    verifyModalEl.addEventListener("hidden.mdb.modal", () => {
      document.getElementById("verificationLinkInput").value = "";
    });
  }

  // Reset new account modal fields on close (optional)
  const newAccountModalEl = document.getElementById("newAccountModal");
  if (newAccountModalEl) {
    newAccountModalEl.addEventListener("hidden.mdb.modal", () => {
      document.getElementById("emailPrefix").value = "";
      document.getElementById("emailSuffix").value = "";
      document.getElementById("emailDomain").value = "";
      document.getElementById("bulkPrefix").value = "";
      document.getElementById("bulkStart").value = "";
      document.getElementById("bulkEnd").value = "";
      document.getElementById("bulkDomain").value = "";
      document.getElementById("finalEmailPreview").textContent = "";
    });
  }

  // Init and show new account modal manually
  const newAccountModal = new mdb.Modal(
    document.getElementById("newAccountModal")
  );
  newAccountBtn.addEventListener("click", async () => {
    const modal = mdb.Modal.getInstance(document.getElementById("newAccountModal")) || new mdb.Modal(document.getElementById("newAccountModal"));
    modal.show();

    try {
      const res = await fetch("/api/settings");
      const settings = await res.json();

      if (settings.mega_email) {
        const emailParts = settings.mega_email.split("@");
        const prefix = emailParts[0] || "";
        const domain = emailParts[1] || "";
        
        // Single Mode
        document.getElementById("emailPrefix").value = prefix;
        document.getElementById("emailDomain").value = domain;
        
        // Bulk Mode
        document.getElementById("bulkPrefix").value = prefix;
        document.getElementById("bulkDomain").value = domain;
        document.getElementById("bulkStart").value = "1";
        document.getElementById("bulkEnd").value = "20";
        
        document.getElementById("finalEmailPreview").textContent = settings.mega_email;
      }
    } catch (err) {
      console.error("Failed to load mega_email setting:", err);
    }
  });

  // Init and show file upload modal manually
  const fileUploadModal = new mdb.Modal(
    document.getElementById("fileUploadModal")
  );
  const fileUploadBtn = document.getElementById("addNewAccountsBtn");
  if (fileUploadBtn) {
    fileUploadBtn.addEventListener("click", () => {
      fileUploadModal.show();
    });
  }

  // File upload form handling
  const fileUploadForm = document.getElementById("fileUploadForm");
  if (fileUploadForm) {
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
        addNewAccounts(parsedData);
        fileUploadModal.hide();
      };
      reader.readAsText(file);
    });
  }
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

  if (btn) {
    icon?.classList.add("fa-spin");
    btn.disabled = true;
    btn.classList.remove("btn-outline-light", "btn-success", "btn-danger");
    btn.classList.add("btn-outline-warning");
  }

  return fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=account_login:${id}`,
  })
    .then((res) => res.json())
    .then((result) => {
      if (!result || result.status !== 200) {
        throw new Error(result.message || "Unknown login error");
      }

      if (btn) {
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
        body: `command=account_get_one:${id}`,
      });
    })
    .then((res) => res.json())
    .then((data) => {
      const acc = data.account;
      const newRow = document.createElement("tr");

      newRow.id = `account-row-${acc.id}`;
      newRow.innerHTML = createAccountRowHTML(acc);
      
      const oldRow = document.getElementById(`account-row-${acc.id}`);
      if (oldRow) oldRow.replaceWith(newRow);

      const dropdownToggle = newRow.querySelector(".dropdown-toggle");
      if (dropdownToggle) new mdb.Dropdown(dropdownToggle);
      
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

      if (btn) {
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
      if (btn) {
        setTimeout(() => {
          btn.classList.remove("btn-success", "btn-danger");
          btn.classList.add("btn-outline-light");
          btn.disabled = false;
          icon?.classList.remove("fa-spin");
        }, 3000);
      }
    });
}

function createAccountRowHTML(acc, isStale = false) {
  const usedQuota = acc.used_quota;
  const totalQuota = acc.total_quota;
  const remainingQuota = totalQuota - usedQuota;
  let usagePercentage = (usedQuota / totalQuota) * 100;
  if (isNaN(usagePercentage)) usagePercentage = 0;

  let progressColor = "success";
  if (usagePercentage > 50 && usagePercentage <= 80) progressColor = "warning";
  else if (usagePercentage > 80) progressColor = "danger";

  const staleFlag = isStale ? 1 : 0;
  
  return `
    <td style="display: none !important;">${staleFlag}</td>
    <td class="text-muted small">${acc.id}</td>
    <td class="fw-bold">
      ${acc.email}
      ${acc.status === "Pending Verification" ? '<br><span class="badge badge-warning x-small">PENDING VERIFICATION</span>' : ''}
    </td>
    <td>
      <div class="d-flex align-items-center">
        <span id="password-${acc.id}" class="masked-password text-muted" data-password="${acc.password}" style="letter-spacing: 0.1em; font-family: monospace;">
          ${"•".repeat(Math.min(acc.password.length, 12))}
        </span>
        <button id="toggle-password-${acc.id}" class="btn btn-sm btn-pwreveal shadow-0" onclick="togglePasswordVisibility(${acc.id})" title="Toggle Password">
          <i class="fas fa-eye"></i>
        </button>
      </div>
    </td>
    <td class="text-center">
      ${acc.is_pro 
        ? '<i class="fas fa-gem text-warning" data-mdb-toggle="tooltip" title="Pro Account"></i>' 
        : '<i class="fas fa-user text-muted opacity-25" data-mdb-toggle="tooltip" title="Free Account"></i>'}
    </td>
    <td>
      ${acc.status === "Pending Verification" ? `
        <a href="verify.html" class="btn btn-sm btn-outline-warning py-1 px-2 border-dashed">
          <i class="fas fa-user-check me-1"></i> Verify Now
        </a>
      ` : `
        <div class="d-flex align-items-center gap-2">
          <div class="progress flex-grow-1" style="height: 6px !important;">
            <div class="progress-bar bg-${progressColor}" role="progressbar" style="width: ${usagePercentage}%" aria-valuenow="${usagePercentage}" aria-valuemin="0" aria-valuemax="100"></div>
          </div>
          <span class="small text-muted" style="min-width: 35px;">${Math.round(usagePercentage)}%</span>
        </div>
      `}
    </td>
    <td class="text-end small fw-bold">${acc.status === "Pending Verification" ? '-' : formatBytes(remainingQuota)}</td>
    <td class="text-muted small">${formatDate(acc.last_login)}</td>
    <td class="text-end">
      <div class="d-flex justify-content-end gap-1">
        <button id="refresh-btn-${acc.id}" class="btn btn-sm btn-tertiary shadow-0" ${acc.status === "Pending Verification" ? 'disabled' : ''} onclick="refreshAccount(${acc.id})" title="Sync Account">
          <i class="fas fa-sync-alt"></i>
        </button>
        <div class="btn-group dropdown">
          <button type="button" class="btn btn-sm btn-tertiary dropdown-toggle dropdown-toggle-split shadow-0" data-mdb-toggle="dropdown" aria-expanded="false">
            <i class="fas fa-ellipsis-v"></i>
          </button>
          <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end">
            ${acc.status === "Pending Verification" ? `
              <li>
                <a class="dropdown-item text-warning" href="verify.html">
                  <i class="fas fa-user-check me-2"></i> Activation Page
                </a>
              </li>
            ` : ""}
            <li>
              <a class="dropdown-item text-danger" href="#" onclick="confirmDeleteAccount(${acc.id}, '${acc.email}')">
                <i class="fas fa-trash-alt me-2"></i> Delete Account
              </a>
            </li>
          </ul>
        </div>
      </div>
    </td>
  `;
}

// load all accounts from database
function loadAccountTable() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=account_get_all`,
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
        const isStale = staleAccounts.includes(acc);
        const row = document.createElement("tr");
        row.id = `account-row-${acc.id}`;
        row.innerHTML = createAccountRowHTML(acc, isStale);

        if (isStale) {
          row.classList.add("table-stale");
        }

        tbody.appendChild(row);
        const dropdownToggle = row.querySelector(".dropdown-toggle");
        if (dropdownToggle) new mdb.Dropdown(dropdownToggle);
      });

      $("#accountTable").DataTable({
        responsive: true,
        lengthMenu: [50, 100, 250, 500, 1000],
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
  // Disable all individual refresh buttons temporarily
  document.querySelectorAll('[id^="refresh-btn-"]').forEach((el) => {
    el.disabled = true;
  });

  btn.classList.add("btn-warning");
  if (icon) icon.classList.add("fa-spin");
  btn.disabled = true;

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=account_fetch_ids`,
  })
    .then((res) => res.json())
    .then(async (data) => {
      const accountIds = data.account_ids || [];
      const total = accountIds.length;

      let failedCount = 0;

      for (let i = 0; i < total; i++) {
        const id = accountIds[i];
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
        btn.innerHTML = `<i class="fas fa-sync-alt me-2" id="refreshAllIcon"></i> Refresh all`;
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
    body: `command=account_get_one:${id}`,
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
    body: `command=account_delete:${id}`,
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
    body: `command=account_verify:${accountId}|${encodeURIComponent(
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
  if (!passwordElement) return;
  
  const toggleButton = document.getElementById(`toggle-password-${accountId}`);
  const password = passwordElement.getAttribute("data-password");

  if (!password) {
    showToast("⚠️ Could not retrieve password for this row.", "bg-warning");
    return;
  }

  const maskedPassword = "•".repeat(password.length);

  // If another password is already revealed, hide it first
  if (currentRevealedPasswordId && currentRevealedPasswordId !== accountId) {
    const prevEl = document.getElementById(`password-${currentRevealedPasswordId}`);
    const prevBtn = document.getElementById(`toggle-password-${currentRevealedPasswordId}`);

    if (prevEl && prevBtn) {
       const prevPass = prevEl.getAttribute("data-password");
       if (prevPass) {
          prevEl.textContent = "•".repeat(prevPass.length);
          prevBtn.innerHTML = '<i class="fas fa-eye"></i>';
          prevEl.classList.add("masked-password");
       }
    }
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
  if (bytes == null || isNaN(bytes)) return "-";
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
        command: "account_import_csv",
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

function updateFinalEmailPreview() {
  const isBulk = document.getElementById("bulkModeToggle").checked;
  let final = "";

  if (isBulk) {
    const prefix = document.getElementById("bulkPrefix").value.trim();
    const start = document.getElementById("bulkStart").value;
    const end = document.getElementById("bulkEnd").value;
    const domain = document.getElementById("bulkDomain").value.trim();
    if (prefix && start && end && domain) {
      const separator = prefix.includes("+") ? "" : "+";
      final = `${prefix}${separator}[${start} to ${end}]@${domain}`;
    }
  } else {
    const prefix = document.getElementById("emailPrefix").value.trim();
    const suffix = document.getElementById("emailSuffix").value.trim();
    const domain = document.getElementById("emailDomain").value.trim();
    if (prefix && suffix && domain) {
      final = `${prefix}+${suffix}@${domain}`;
    }
  }
  document.getElementById("finalEmailPreview").textContent = final || "...";
}

// Wire up events
document.getElementById("bulkModeToggle").addEventListener("change", (e) => {
  const isBulk = e.target.checked;
  document.getElementById("singleModeInputs").classList.toggle("d-none", isBulk);
  document.getElementById("bulkModeInputs").classList.toggle("d-none", !isBulk);
  updateFinalEmailPreview();
});

["emailPrefix", "emailSuffix", "emailDomain", "bulkPrefix", "bulkStart", "bulkEnd", "bulkDomain"].forEach((id) => {
  const input = document.getElementById(id);
  if (input) input.addEventListener("input", updateFinalEmailPreview);
});

document
  .getElementById("submitNewAccountBtn")
  .addEventListener("click", async () => {
    const isBulk = document.getElementById("bulkModeToggle").checked;
    const btn = document.getElementById("submitNewAccountBtn");
    const originalText = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span> Processing...`;

    try {
      let command = "account_register";
      let args = [];

      if (isBulk) {
        const prefix = document.getElementById("bulkPrefix").value.trim();
        const start = document.getElementById("bulkStart").value;
        const end = document.getElementById("bulkEnd").value;
        const domain = document.getElementById("bulkDomain").value.trim();

        if (!prefix || !start || !end || !domain) {
          showToast("Please fill out all bulk range fields", "bg-warning");
          btn.disabled = false;
          btn.innerHTML = originalText;
          return;
        }
        command = "account_bulk_register";
        args = [`${prefix}|${start}|${end}|${domain}`];
      } else {
        const prefix = document.getElementById("emailPrefix").value.trim();
        const suffix = document.getElementById("emailSuffix").value.trim();
        const domain = document.getElementById("emailDomain").value.trim();

        if (!prefix || !suffix || !domain) {
          showToast("Please fill out all fields", "bg-warning");
          btn.disabled = false;
          btn.innerHTML = originalText;
          return;
        }
        args = [`${prefix}+${suffix}@${domain}`];
      }

      const res = await fetch("/run-command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command, args }),
      });

      const result = await res.json();

      if (result.status === 200) {
        showToast(`✅ ${result.message}`, "bg-success");
        const modal = mdb.Modal.getInstance(document.getElementById("newAccountModal"));
        if (modal) modal.hide();
        loadAccountTable();
      } else {
        showToast(`❌ Failed: ${result.message}`, "bg-danger");
      }
    } catch (err) {
      console.error("Registration error:", err);
      showToast("❌ An error occurred during registration", "bg-danger");
    } finally {
      btn.disabled = false;
      btn.innerHTML = originalText;
    }
  });
