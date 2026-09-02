document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("accountTableBody")) {
    loadAccountTable();
  }

  const verifyModalEl = document.getElementById("verifyAccountModal");
  if (verifyModalEl) {
    verifyModalEl.addEventListener("hidden.mdb.modal", () => {
      document.getElementById("verificationLinkInput").value = "";
    });
  }

  const newAccountModalEl = document.getElementById("newAccountModal");
  if (newAccountModalEl) {
    newAccountModalEl.addEventListener("show.mdb.modal", () => {
      populateNewAccountModal();
    });
  }

  const newAccountBtn = document.getElementById("newAccountBtn");
  if (newAccountBtn) {
    newAccountBtn.addEventListener("click", async () => {
      await populateNewAccountModal();
      const modal =
        mdb.Modal.getInstance(document.getElementById("newAccountModal")) || new mdb.Modal(document.getElementById("newAccountModal"));
      modal.show();
    });
  }

  const fileUploadModal = new mdb.Modal(document.getElementById("fileUploadModal"));
  const fileUploadBtn = document.getElementById("addNewAccountsBtn");
  if (fileUploadBtn) {
    fileUploadBtn.addEventListener("click", () => {
      fileUploadModal.show();
    });
  }

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

  initFilterPanel("accountsFilterToggle", "accountsFilterPanel", "accountsFilterChevron");

  ["filterAccountPicker", "filterStatus", "filterType", "filterActivity"].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", applyAccountFilters);
  });
  document.getElementById("filterFullOnly")?.addEventListener("change", applyAccountFilters);
  document.getElementById("filterOverQuota")?.addEventListener("change", applyAccountFilters);
  document.getElementById("filterCapacity")?.addEventListener("input", () => {
    updateCapacityLabel();
    applyAccountFilters();
  });
  document.getElementById("clearAccountFiltersBtn")?.addEventListener("click", () => {
    ["filterAccountPicker", "filterStatus", "filterType", "filterActivity"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = "all";
    });
    const fullOnly = document.getElementById("filterFullOnly");
    if (fullOnly) fullOnly.checked = false;
    const overQuota = document.getElementById("filterOverQuota");
    if (overQuota) overQuota.checked = false;
    const slider = document.getElementById("filterCapacity");
    if (slider) slider.value = "0";
    updateCapacityLabel();
    applyAccountFilters();
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
        showToast(`Account ${id} refreshed successfully`, "bg-success");
      }

      return fetch("/run-command", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `command=account_get_one:${id}`,
      });
    })
    .then((res) => res.json())
    .then((data) => {
      const acc = { ...data.account, ...computeAccountMeta(data.account) };
      const cacheIdx = allAccountsData.findIndex((a) => a.id === acc.id);
      if (cacheIdx !== -1) {
        allAccountsData[cacheIdx] = acc;
      } else {
        allAccountsData.push(acc);
      }

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
        showToast(`Account ${id} is unverified: ${message}`, "bg-danger");
      } else {
        showToast(`Failed to refresh account ${id}: ${message}`, "bg-danger");
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

let allAccountsData = [];

function computeAccountMeta(acc) {
  const usedQuota = Number(acc.used_quota) || 0;
  const totalQuota = Number(acc.total_quota) || 0;
  const remainingQuota = Math.max(0, totalQuota - usedQuota);
  let usagePercentage = totalQuota > 0 ? (usedQuota / totalQuota) * 100 : 0;
  if (isNaN(usagePercentage)) usagePercentage = 0;

  let daysSinceLogin = null;
  if (acc.last_login) {
    const diffMs = Date.now() - new Date(acc.last_login).getTime();
    daysSinceLogin = diffMs / (1000 * 60 * 60 * 24);
  }

  return {
    _remainingQuota: remainingQuota,
    _usagePercentage: usagePercentage,
    _daysSinceLogin: daysSinceLogin,
  };
}

function updateCapacityLabel() {
  const slider = document.getElementById("filterCapacity");
  const label = document.getElementById("filterCapacityLabel");
  if (!slider || !label) return;

  const valueMB = Number(slider.value) || 0;
  if (valueMB <= 0) {
    label.textContent = "Any";
  } else if (valueMB >= 1024) {
    const gb = valueMB / 1024;
    label.textContent = `${gb % 1 === 0 ? gb.toFixed(0) : gb.toFixed(2)} GB+`;
  } else {
    label.textContent = `${valueMB} MB+`;
  }
}

function populateAccountFilters() {
  const picker = document.getElementById("filterAccountPicker");
  if (picker) {
    const prevVal = picker.value || "all";
    const sorted = [...allAccountsData].sort((a, b) => a.email.localeCompare(b.email));

    picker.innerHTML = "";
    picker.appendChild(new Option("All Accounts", "all"));
    sorted.forEach((acc) => picker.appendChild(new Option(acc.email, String(acc.id))));
    picker.value = [...picker.options].some((o) => o.value === prevVal) ? prevVal : "all";
  }

  const slider = document.getElementById("filterCapacity");
  if (slider) {
    const maxBytes = allAccountsData.reduce((max, acc) => Math.max(max, acc._remainingQuota || 0), 0);
    const maxMB = Math.max(1024, Math.ceil(maxBytes / (1024 * 1024) / 128) * 128);
    const prevVal = Number(slider.value) || 0;

    slider.max = String(maxMB);
    slider.value = String(Math.min(prevVal, maxMB));
    updateCapacityLabel();
  }
}

function applyAccountFilters() {
  const accountVal = document.getElementById("filterAccountPicker")?.value || "all";
  const statusVal = document.getElementById("filterStatus")?.value || "all";
  const typeVal = document.getElementById("filterType")?.value || "all";
  const activityVal = document.getElementById("filterActivity")?.value || "all";
  const fullOnly = document.getElementById("filterFullOnly")?.checked || false;
  const overQuotaOnly = document.getElementById("filterOverQuota")?.checked || false;
  const minCapacityMB = Number(document.getElementById("filterCapacity")?.value) || 0;
  const minCapacityBytes = minCapacityMB * 1024 * 1024;

  const filtered = allAccountsData.filter((acc) => {
    if (accountVal !== "all" && String(acc.id) !== accountVal) return false;
    if (statusVal !== "all" && acc.status !== statusVal) return false;
    if (typeVal === "pro" && !acc.is_pro) return false;
    if (typeVal === "free" && acc.is_pro) return false;
    if (fullOnly && acc._usagePercentage < 95) return false;
    if (overQuotaOnly && acc._usagePercentage <= 100) return false;
    if (minCapacityMB > 0 && acc._remainingQuota < minCapacityBytes) return false;

    if (activityVal !== "all") {
      const days = acc._daysSinceLogin;
      if (activityVal === "never" && days !== null) return false;
      if (activityVal === "active" && (days === null || days >= 30)) return false;
      if (activityVal === "approaching" && (days === null || days < 30 || days >= 60)) return false;
      if (activityVal === "inactive" && (days === null || days < 60)) return false;
    }

    return true;
  });

  const activeCount = [
    accountVal !== "all",
    statusVal !== "all",
    typeVal !== "all",
    activityVal !== "all",
    fullOnly,
    overQuotaOnly,
    minCapacityMB > 0,
  ].filter(Boolean).length;
  updateFilterBadge("accountsFilterActiveBadge", activeCount);

  renderAccountsTable(filtered);
}

function createAccountRowHTML(acc, isStale = false) {
  const usedQuota = Number(acc.used_quota) || 0;
  const totalQuota = Number(acc.total_quota) || 0;
  const remainingQuota = Math.max(0, totalQuota - usedQuota);
  let usagePercentage = totalQuota > 0 ? (usedQuota / totalQuota) * 100 : 0;
  if (isNaN(usagePercentage)) usagePercentage = 0;

  let progressColor = "bg-success";
  if (usagePercentage > 60 && usagePercentage <= 85) progressColor = "bg-warning";
  else if (usagePercentage > 85) progressColor = "bg-danger";

  const staleFlag = isStale ? 1 : 0;

  return `
 <td style="display: none !important;">${staleFlag}</td>
 <td class="text-muted small fw-bold">#${acc.id}</td>
 <td class="fw-bold">
 <div class="d-flex align-items-center gap-2">
 <span>${acc.email}</span>
 ${acc.status === "Pending Verification" ? '<span class="badge bg-warning text-dark x-small py-1 px-2 rounded-pill">PENDING</span>' : ""}
 </div>
 </td>
 <td>
 <div class="d-flex align-items-center gap-2">
 <span id="password-${acc.id}" class="masked-password text-muted" data-password="${acc.password}"
 onclick="copyToClipboard('${acc.password}', 'Password copied to clipboard!')"
 style="letter-spacing: 0.15em; font-family: monospace; cursor: pointer; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.03);" title="Click to copy password">
 ${"•".repeat(Math.min(acc.password ? acc.password.length : 8, 12))}
 </span>
 <button id="toggle-password-${acc.id}" class="btn btn-sm btn-outline-secondary py-0 px-2 shadow-0" onclick="togglePasswordVisibility(${acc.id}); event.stopPropagation();" title="Reveal / Hide Password">
 <i class="fas fa-eye small"></i>
 </button>
 </div>
 </td>
 <td class="text-center">
 ${
   acc.is_pro
     ? '<span class="badge bg-secondary">Pro</span>'
     : '<span class="badge text-muted border border-secondary border-opacity-25">Free</span>'
 }
 </td>
 <td>
 ${
   acc.status === "Pending Verification"
     ? `
 <a href="verify.html" class="btn btn-sm btn-outline-warning py-1 px-2 border-dashed">
 <i class="fas fa-user-check me-1"></i> Verify Now
 </a>
 `
     : `
 <div class="d-flex align-items-center gap-2">
 <div class="progress flex-grow-1" style="height: 6px !important; min-width: 70px;">
 <div class="progress-bar ${progressColor}" role="progressbar" style="width: ${Math.min(100, usagePercentage)}%" aria-valuenow="${usagePercentage}" aria-valuemin="0" aria-valuemax="100"></div>
 </div>
 <span class="small fw-semibold text-muted" style="min-width: 38px; font-size: 0.78rem;">${Math.round(usagePercentage)}%</span>
 </div>
 `
 }
 </td>
 <td class="text-end small fw-bold">${acc.status === "Pending Verification" ? "-" : formatBytes(remainingQuota)}</td>
 <td class="text-muted small">${formatDate(acc.last_login)}</td>
 <td class="text-end">
 <div class="d-flex justify-content-end gap-1">
 <button id="refresh-btn-${acc.id}" class="btn btn-sm btn-outline-secondary shadow-0"${acc.status === "Pending Verification" ? "disabled" : ""} onclick="refreshAccount(${acc.id})" title="Sync Account Quotas">
 <i class="fas fa-sync-alt"></i>
 </button>
 <div class="btn-group dropdown">
 <button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle dropdown-toggle-split shadow-0" data-mdb-toggle="dropdown" aria-expanded="false">
 <i class="fas fa-ellipsis-v"></i>
 </button>
 <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end">
 ${
   acc.status === "Pending Verification"
     ? `
 <li>
 <a class="dropdown-item text-warning" href="verify.html">
 <i class="fas fa-user-check me-2"></i> Activation Page
 </a>
 </li>
 `
     : ""
 }
 <li>
 <a class="dropdown-item text-info" href="#" onclick="showUpdatePasswordModal(${acc.id}, '${acc.email}')">
 <i class="fas fa-key me-2"></i> Update Password
 </a>
 </li>
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

function renderAccountsTable(accounts) {
  const table = $("#accountTable");

  if ($.fn.DataTable.isDataTable("#accountTable")) {
    table.DataTable().clear().destroy();
  }

  const tbody = document.getElementById("accountTableBody");

  const now = new Date();
  const cutoff = new Date(now.setMonth(now.getMonth() - 2));

  const staleAccounts = [];
  const recentAccounts = [];

  accounts.forEach((acc) => {
    const lastLogin = acc.last_login ? new Date(acc.last_login) : null;
    if (lastLogin && lastLogin < cutoff) {
      staleAccounts.push(acc);
    } else {
      recentAccounts.push(acc);
    }
  });

  // Build every row's HTML up-front and assign it in one shot rather than
  // creating + appending elements one at a time, which gets slow as the
  // account list grows.
  const staleRowsHtml = staleAccounts
    .map((acc) => `<tr id="account-row-${acc.id}" class="table-stale">${createAccountRowHTML(acc, true)}</tr>`)
    .join("");
  const recentRowsHtml = recentAccounts.map((acc) => `<tr id="account-row-${acc.id}">${createAccountRowHTML(acc, false)}</tr>`).join("");

  tbody.innerHTML = staleRowsHtml + recentRowsHtml;
  tbody.querySelectorAll(".dropdown-toggle").forEach((toggle) => new mdb.Dropdown(toggle));

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

  const countEl = document.getElementById("accountsFilterResultCount");
  if (countEl) {
    countEl.textContent =
      accounts.length === allAccountsData.length
        ? `Showing all ${accounts.length.toLocaleString()} accounts`
        : `Showing ${accounts.length.toLocaleString()} of ${allAccountsData.length.toLocaleString()} accounts`;
  }
}

function loadAccountTable() {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=account_get_all`,
  })
    .then((res) => res.json())
    .then((data) => {
      const accounts = data.accounts || [];
      allAccountsData = accounts.map((acc) => ({ ...acc, ...computeAccountMeta(acc) }));

      const stats = data.stats || {};
      const totalCapacityBytes = stats.cloud_capacity !== undefined ? stats.cloud_capacity : 0;
      const totalUsedBytes = stats.cloud_used !== undefined ? stats.cloud_used : 0;
      const totalAvailableBytes =
        stats.cloud_available !== undefined ? stats.cloud_available : Math.max(0, totalCapacityBytes - totalUsedBytes);
      const totalAccountsCount = stats.total_accounts !== undefined ? stats.total_accounts : accounts.length;

      const statCapEl = document.getElementById("statTotalCapacity");
      const statUsedEl = document.getElementById("statTotalUsed");
      const statAvailEl = document.getElementById("statTotalAvailable");
      const statAccsEl = document.getElementById("statTotalAccounts");

      if (statCapEl) statCapEl.textContent = formatBytes(totalCapacityBytes);
      if (statUsedEl) statUsedEl.textContent = formatBytes(totalUsedBytes);
      if (statAvailEl) statAvailEl.textContent = formatBytes(totalAvailableBytes);
      if (statAccsEl) statAccsEl.textContent = `${totalAccountsCount.toLocaleString()} Active`;

      populateAccountFilters();
      applyAccountFilters();
    })
    .catch((err) => console.error("Failed to load accounts:", err));
}

function refreshAllAccounts() {
  const btn = document.getElementById("refreshAllBtn");
  const icon = document.getElementById("refreshAllIcon");
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
        btn.innerHTML = `<i class="fas fa-sync-alt me-2 fa-spin" id="refreshAllIcon"></i> Refreshing account ${i + 1} / ${total}...`;

        const success = await refreshAccount(id, { silent: true });
        if (!success) failedCount++;

        // Add a delay between accounts to ensure we are logging in "slowly"
        // and giving the MegaCMD daemon time to settle down between sessions.
        if (i < total - 1) {
          await new Promise((resolve) => setTimeout(resolve, 2000));
        }
      }

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
 This account has <strong>${fileCount}</strong> linked file${fileCount === 1 ? "" : "s"} in this program.
 </span>
 <br />
 <small class="text-muted">
 No files will be deleted from your MEGA drive, but all references to them will be removed from Mega Manager.
 </small>
 `;

      const modal = new mdb.Modal(document.getElementById("deleteAccountModal"));
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
      allAccountsData = allAccountsData.filter((a) => a.id !== id);

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
    body: `command=account_verify:${accountId}|${encodeURIComponent(link)}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        showToast(`Account ${accountId} verified`, "bg-success");
        refreshAccount(accountId);
      } else {
        showToast(`Verification failed: ${data.message}`, "bg-danger");
      }
    })
    .catch((err) => {
      console.error(`Verification error for ${accountId}:`, err);
      showToast("Failed to verify account", "bg-danger");
    });
}

let currentRevealedPasswordId = null;

function togglePasswordVisibility(accountId) {
  const passwordElement = document.getElementById(`password-${accountId}`);
  if (!passwordElement) return;

  const toggleButton = document.getElementById(`toggle-password-${accountId}`);
  const password = passwordElement.getAttribute("data-password");

  if (!password) {
    showToast("Could not retrieve password for this row.", "bg-warning");
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

  if (passwordElement.classList.contains("masked-password")) {
    passwordElement.textContent = password;
    toggleButton.innerHTML = '<i class="fas fa-eye-slash"></i>';
    passwordElement.classList.remove("masked-password");
    currentRevealedPasswordId = accountId;

    setTimeout(() => {
      passwordElement.textContent = maskedPassword;
      toggleButton.innerHTML = '<i class="fas fa-eye"></i>';
      passwordElement.classList.add("masked-password");
      currentRevealedPasswordId = null;
    }, 10000);
  } else {
    passwordElement.textContent = maskedPassword;
    toggleButton.innerHTML = '<i class="fas fa-eye"></i>';
    passwordElement.classList.add("masked-password");
    currentRevealedPasswordId = null;
  }
}

async function copyToClipboard(text, message = "Copied to clipboard!") {
  try {
    await navigator.clipboard.writeText(text);
    showToast(`${message}`, "bg-info");
  } catch (err) {
    console.error("Failed to copy text:", err);
    showToast("Failed to copy to clipboard", "bg-danger");
  }
}

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

async function addNewAccounts(parsedData) {
  const btn = document.getElementById("addNewAccountsBtn");
  btn.disabled = true;

  try {
    // Only drop the first row if it isn't itself a valid email,password pair -
    // CSVs may or may not include a header row, and the backend expects every
    // remaining row to be real data.
    const firstCol = (parsedData[0] || "").split(",")[0]?.trim() || "";
    const looksLikeHeader = parsedData.length > 0 && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(firstCol);
    const rows = looksLikeHeader ? parsedData.slice(1) : parsedData;

    showRegistrationProgress(`Importing ${rows.length} accounts from CSV...`, 20, `0 / ${rows.length}`);

    const res = await fetch("/run-command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        command: "account_import_csv",
        args: rows,
      }),
    });

    const data = await res.json();
    const ids = data.account_ids || [];
    const total = ids.length;

    loadAccountTable();

    for (let i = 0; i < total; i++) {
      const id = ids[i];
      const pct = 20 + ((i + 1) / total) * 75;
      updateRegistrationProgress(pct, `${i + 1} / ${total}`, `Validating and refreshing imported account [${i + 1}/${total}]...`);
      await refreshAccount(id, { silent: true });
    }

    updateRegistrationProgress(100, `${total} / ${total}`, `Successfully imported and verified ${total} accounts!`, true, false);
    showToast(`${total} accounts imported successfully!`, "bg-success");
    loadAccountTable();
    hideRegistrationProgress(4000);
  } catch (err) {
    console.error("Adding new accounts failed:", err);
    updateRegistrationProgress(100, "Error", "CSV Import failed", false, true);
    showToast("CSV Import failed", "bg-danger");
    hideRegistrationProgress(4000);
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

function setRegistrationMode(mode) {
  const isBulk = mode === "bulk";
  const toggle = document.getElementById("bulkModeToggle");
  if (toggle) toggle.checked = isBulk;

  const tabSingle = document.getElementById("tabSingleMode");
  const tabBulk = document.getElementById("tabBulkMode");
  const singleInputs = document.getElementById("singleModeInputs");
  const bulkInputs = document.getElementById("bulkModeInputs");

  if (isBulk) {
    if (tabSingle) tabSingle.className = "btn btn-sm flex-fill fw-semibold py-2 rounded-2 btn-link text-muted shadow-0";
    if (tabBulk) tabBulk.className = "btn btn-sm flex-fill fw-semibold py-2 rounded-2 btn-primary shadow-0";
    if (singleInputs) singleInputs.classList.add("d-none");
    if (bulkInputs) bulkInputs.classList.remove("d-none");
  } else {
    if (tabSingle) tabSingle.className = "btn btn-sm flex-fill fw-semibold py-2 rounded-2 btn-primary shadow-0";
    if (tabBulk) tabBulk.className = "btn btn-sm flex-fill fw-semibold py-2 rounded-2 btn-link text-muted shadow-0";
    if (singleInputs) singleInputs.classList.remove("d-none");
    if (bulkInputs) bulkInputs.classList.add("d-none");
  }

  updateFinalEmailPreview();
}

async function populateNewAccountModal() {
  try {
    const res = await fetch("/api/settings");
    const settings = await res.json();

    const passwordBadge = document.getElementById("passwordSourceBadge");
    const passwordText = document.getElementById("passwordSourceText");
    const hasPassword = !!(settings.mega_passwords || settings.mega_password);

    if (passwordBadge && passwordText) {
      if (hasPassword) {
        passwordBadge.className = "badge bg-success bg-opacity-25 text-success small";
        passwordText.textContent = "Pre-Set Password Active";
      } else {
        passwordBadge.className = "badge bg-warning bg-opacity-25 text-warning small";
        passwordText.textContent = "Auto Random Password";
      }
    }

    if (settings.mega_email && settings.mega_email.trim() !== "") {
      const emailTemplate = settings.mega_email.trim();
      const emailParts = emailTemplate.split("@");
      const beforeAt = emailParts[0] || "";
      const domain = emailParts[1] || "";

      let prefix = beforeAt;
      let suffix = "";
      let bulkPrefixVal = beforeAt.replace(/[*#]/g, "");

      if (beforeAt.includes("+")) {
        const plusParts = beforeAt.split("+");
        prefix = plusParts[0].replace(/[*#]/g, "");
        const rawSuffix = plusParts.slice(1).join("+");
        const suffixBase = rawSuffix.replace(/[*#]/g, "");

        // If suffix had wildcard, add 1 for single mode default
        suffix = rawSuffix.includes("*") || rawSuffix.includes("#") ? (suffixBase ? `${suffixBase}1` : "1") : suffixBase;
        bulkPrefixVal = `${prefix}+${suffixBase}`;
      } else {
        prefix = beforeAt.replace(/[*#]/g, "");
        suffix = "1";
        bulkPrefixVal = prefix;
      }

      const emailPrefixEl = document.getElementById("emailPrefix");
      const emailSuffixEl = document.getElementById("emailSuffix");
      const emailDomainEl = document.getElementById("emailDomain");

      if (emailPrefixEl) emailPrefixEl.value = prefix;
      if (emailSuffixEl) emailSuffixEl.value = suffix || "1";
      if (emailDomainEl) emailDomainEl.value = domain;

      const bulkPrefixEl = document.getElementById("bulkPrefix");
      const bulkStartEl = document.getElementById("bulkStart");
      const bulkEndEl = document.getElementById("bulkEnd");
      const bulkDomainEl = document.getElementById("bulkDomain");

      if (bulkPrefixEl) bulkPrefixEl.value = bulkPrefixVal;
      if (bulkStartEl && !bulkStartEl.value) bulkStartEl.value = "1";
      if (bulkEndEl && !bulkEndEl.value) bulkEndEl.value = "20";
      if (bulkDomainEl) bulkDomainEl.value = domain;

      updateFinalEmailPreview();
    }
  } catch (err) {
    console.error("Failed to populate new account modal from settings:", err);
  }
}

function updateFinalEmailPreview() {
  const isBulk = document.getElementById("bulkModeToggle")?.checked;
  let final = "";

  if (isBulk) {
    const prefix = document.getElementById("bulkPrefix")?.value?.trim() || "";
    const start = parseInt(document.getElementById("bulkStart")?.value || "1", 10);
    const end = parseInt(document.getElementById("bulkEnd")?.value || "20", 10);
    const domain = document.getElementById("bulkDomain")?.value?.trim() || "";

    const count = !isNaN(start) && !isNaN(end) && end >= start ? end - start + 1 : 0;
    const summaryEl = document.getElementById("bulkBatchSummary");
    if (summaryEl) summaryEl.textContent = `${count} accounts`;

    if (prefix && domain) {
      const separator = prefix.includes("+") ? "" : "+";
      final = `${prefix}${separator}[${start} to ${end}]@${domain}`;
    }
  } else {
    const prefix = document.getElementById("emailPrefix")?.value?.trim() || "";
    const suffix = document.getElementById("emailSuffix")?.value?.trim() || "";
    const domain = document.getElementById("emailDomain")?.value?.trim() || "";
    if (prefix && domain) {
      final = suffix ? `${prefix}+${suffix}@${domain}` : `${prefix}@${domain}`;
    }
  }
  const previewEl = document.getElementById("finalEmailPreview");
  if (previewEl) {
    previewEl.textContent = final || "...";
  }
}

function showRegistrationProgress(statusText = "Registering accounts...", percent = 0, badgeText = "0%") {
  const section = document.getElementById("registrationProgressSection");
  const bar = document.getElementById("registrationProgressBar");
  const textEl = document.getElementById("registrationStatusText");
  const countBadge = document.getElementById("registrationCountBadge");
  const percentEl = document.getElementById("registrationPercentText");
  const spinner = document.getElementById("registrationSpinner");

  if (section) {
    section.style.display = "block";
    $(section).stop(true, true).show();
  }
  if (bar) {
    bar.className = "progress-bar progress-bar-striped progress-bar-animated bg-info";
    bar.style.width = `${percent}%`;
  }
  if (textEl) textEl.textContent = statusText;
  if (countBadge) countBadge.textContent = badgeText;
  if (percentEl) percentEl.textContent = `${Math.round(percent)}%`;
  if (spinner) spinner.style.display = "inline-block";
}

function updateRegistrationProgress(percent, badgeText, statusText, isSuccess = false, isError = false) {
  const bar = document.getElementById("registrationProgressBar");
  const textEl = document.getElementById("registrationStatusText");
  const countBadge = document.getElementById("registrationCountBadge");
  const percentEl = document.getElementById("registrationPercentText");
  const spinner = document.getElementById("registrationSpinner");

  if (bar) {
    bar.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    if (isSuccess) {
      bar.className = "progress-bar bg-success";
    } else if (isError) {
      bar.className = "progress-bar bg-danger";
    } else {
      bar.className = "progress-bar progress-bar-striped progress-bar-animated bg-info";
    }
  }
  if (textEl && statusText) textEl.textContent = statusText;
  if (countBadge && badgeText) countBadge.textContent = badgeText;
  if (percentEl) percentEl.textContent = `${Math.round(percent)}%`;
  if (spinner && (isSuccess || isError)) spinner.style.display = "none";
}

function hideRegistrationProgress(delayMs = 4000) {
  setTimeout(() => {
    const section = document.getElementById("registrationProgressSection");
    if (section) $(section).fadeOut(400);
  }, delayMs);
}

document.getElementById("bulkModeToggle")?.addEventListener("change", (e) => {
  const isBulk = e.target.checked;
  document.getElementById("singleModeInputs").classList.toggle("d-none", isBulk);
  document.getElementById("bulkModeInputs").classList.toggle("d-none", !isBulk);
  updateFinalEmailPreview();
});

["emailPrefix", "emailSuffix", "emailDomain", "bulkPrefix", "bulkStart", "bulkEnd", "bulkDomain"].forEach((id) => {
  const input = document.getElementById(id);
  if (input) input.addEventListener("input", updateFinalEmailPreview);
});

document.getElementById("submitNewAccountBtn")?.addEventListener("click", async () => {
  const isBulk = document.getElementById("bulkModeToggle").checked;
  const btn = document.getElementById("submitNewAccountBtn");
  const modalEl = document.getElementById("newAccountModal");
  const modal = mdb.Modal.getInstance(modalEl) || new mdb.Modal(modalEl);

  if (isBulk) {
    const prefix = document.getElementById("bulkPrefix").value.trim();
    const startStr = document.getElementById("bulkStart").value.trim();
    const endStr = document.getElementById("bulkEnd").value.trim();
    const domain = document.getElementById("bulkDomain").value.trim();

    const start = parseInt(startStr, 10);
    const end = parseInt(endStr, 10);

    if (!prefix || isNaN(start) || isNaN(end) || !domain) {
      showToast("Please fill out all bulk range fields", "bg-warning");
      return;
    }

    if (start > end) {
      showToast("Start index cannot be greater than end index", "bg-warning");
      return;
    }

    const count = end - start + 1;
    if (count > 50) {
      showToast("Bulk registration is limited to 50 accounts per batch", "bg-warning");
      return;
    }

    modal.hide();
    showToast(`Registering ${count} accounts in background...`, "bg-info");
    showRegistrationProgress(`Initializing registration for ${count} accounts...`, 5, `0 / ${count}`);

    let successCount = 0;
    let failCount = 0;

    for (let i = start; i <= end; i++) {
      const index = i - start + 1;
      const separator = prefix.includes("+") ? "" : "+";
      const email = `${prefix}${separator}${i}@${domain}`;
      const pct = ((index - 1) / count) * 90 + 5;

      updateRegistrationProgress(pct, `${index} / ${count}`, `[${index}/${count}] Registering ${email}...`);

      try {
        const res = await fetch("/run-command", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ command: "account_register", args: [encodeURIComponent(email)] }),
        });
        const result = await res.json();
        if (result.status === 200) {
          successCount++;
          // Live populate the table as each account registers
          await loadAccountTable();
        } else {
          failCount++;
          console.warn(`Registration failed for ${email}:`, result.message);
        }
      } catch (err) {
        failCount++;
        console.error(`Error registering ${email}:`, err);
      }

      // Slight throttle between requests
      await new Promise((r) => setTimeout(r, 400));
    }

    if (successCount > 0) {
      updateRegistrationProgress(
        100,
        `${successCount}/${count}`,
        `Bulk registration complete! (${successCount} succeeded, ${failCount} failed)`,
        failCount === 0,
        failCount > 0 && successCount === 0,
      );
      showToast(`Finished: ${successCount} account(s) registered successfully!`, "bg-success");
    } else {
      updateRegistrationProgress(100, `0/${count}`, `Bulk registration failed (${failCount} errors)`, false, true);
      showToast(`Failed to register accounts`, "bg-danger");
    }

    await loadAccountTable();
    hideRegistrationProgress(4500);
  } else {
    const prefix = document.getElementById("emailPrefix").value.trim();
    const suffix = document.getElementById("emailSuffix").value.trim();
    const domain = document.getElementById("emailDomain").value.trim();

    if (!prefix || !domain) {
      showToast("Please fill out prefix and domain fields", "bg-warning");
      return;
    }

    const email = suffix ? `${prefix}+${suffix}@${domain}` : `${prefix}@${domain}`;

    modal.hide();
    showToast(`Registering ${email}...`, "bg-info");
    showRegistrationProgress(`Registering ${email}...`, 30, "1 / 1");

    try {
      const res = await fetch("/run-command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ command: "account_register", args: [encodeURIComponent(email)] }),
      });

      const result = await res.json();

      if (result.status === 200) {
        updateRegistrationProgress(100, "1 / 1", `Account registered: ${email}`, true, false);
        showToast(`${result.message}`, "bg-success");
        loadAccountTable();
      } else {
        updateRegistrationProgress(100, "Failed", `${result.message}`, false, true);
        showToast(`Failed: ${result.message}`, "bg-danger");
      }
    } catch (err) {
      console.error("Registration error:", err);
      updateRegistrationProgress(100, "Error", `Network error during registration`, false, true);
      showToast("An error occurred during registration", "bg-danger");
    } finally {
      hideRegistrationProgress(4000);
    }
  }
});

let updatePasswordTargetId = null;
let updatePasswordTargetEmail = null;

function showUpdatePasswordModal(accountId, email) {
  updatePasswordTargetId = accountId;
  updatePasswordTargetEmail = email;
  
  document.getElementById("updatePasswordEmail").textContent = email;
  document.getElementById("newPasswordInput").value = "";
  
  const modal = new mdb.Modal(document.getElementById("updatePasswordModal"));
  modal.show();
}

async function updateAccountPassword() {
  const newPassword = document.getElementById("newPasswordInput").value.trim();
  
  if (!newPassword) {
    showToast("Please enter a new password", "warning");
    return;
  }
  
  const submitBtn = document.getElementById("submitUpdatePasswordBtn");
  const originalBtnHTML = submitBtn.innerHTML;
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Updating...';
  
  try {
    const response = await fetch("/run-command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command: "account:update_password",
        args: `${updatePasswordTargetId}:${newPassword}`
      }),
    });
    
    const result = await response.json();
    
    if (result.status === 200) {
      showToast(`Password updated for ${updatePasswordTargetEmail}`, "success");
      const modal = mdb.Modal.getInstance(document.getElementById("updatePasswordModal"));
      modal.hide();
      loadAccountTable(); // Refresh the table
    } else {
      showToast(result.message || "Failed to update password", "danger");
    }
  } catch (error) {
    console.error("Error updating password:", error);
    showToast("An error occurred while updating the password", "danger");
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalBtnHTML;
  }
}
