// on page load, load all accounts
document.addEventListener("DOMContentLoaded", () => {
  if (document.getElementById("accountTableBody")) {
    loadAccountTable();
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
      console.log(result.status, result.message);
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
      const newRow = document.createElement("tr");
      newRow.id = `account-row-${acc.id}`;
      newRow.innerHTML = `
        <td>${acc.id}</td>
        <td>${acc.email}</td>
        <td>${acc.is_pro ? "✅" : "❌"}</td>
        <td>${formatBytes(acc.used_quota)}</td>
        <td>${formatBytes(acc.total_quota)}</td>
        <td>${formatDate(acc.last_login)}</td>
        <td>
          <button id="refresh-btn-${
            acc.id
          }" class="btn btn-sm btn-outline-light"
            title="Log in and refresh quota"
            onclick="refreshAccount(${acc.id})">
            <i class="fas fa-sync-alt"></i>
          </button>
          <button class="btn btn-sm btn-outline-danger"
            onclick="confirmDeleteAccount(${acc.id}, '${acc.email}')"
            title="Delete this account">
            <i class="fas fa-trash-alt"></i>
          </button>
        </td>
      `;

      const oldRow = document.getElementById(`account-row-${acc.id}`);
      if (oldRow) oldRow.replaceWith(newRow);
      newRow.classList.add("flash-row");
    })
    .catch((err) => {
      console.error(`Refresh for account ${id} failed:`, err);

      const message = err.message || "Unknown error";
      const match = message.match(
        /^Account \d+: ([^ ]+@[^ ]+) - .*?Login failed: (.+?)\]?$/
      );

      if (match) {
        const email = match[1];
        const reason = match[2];
        if (reason.toLowerCase().includes("unconfirmed account")) {
          const row = document.getElementById(`account-row-${id}`);
          const actionCell = row?.querySelector("td:last-child");

          if (message.includes("unconfirmed account")) {
            const row = document.getElementById(`account-row-${id}`);
            if (row) {
              const actionCell = row.querySelector("td:last-child");
              const verifyBtn = document.createElement("button");
              verifyBtn.className = "btn btn-sm btn-outline-warning ms-1";
              verifyBtn.innerHTML = `<i class="fas fa-check-circle"></i>`;
              verifyBtn.title = "Verify this account";
              verifyBtn.onclick = () => openVerifyModal(id);
              actionCell.appendChild(verifyBtn);
            }
          }
        }
        showToast(`❌ ${email} - ${reason}`, "bg-danger");
      } else {
        showToast(`❌ Failed to refresh account ${id}`, "bg-danger");
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
        const isStale = acc.last_login && acc.last_login < cutoff;
        const staleFlag = isStale ? 1 : 0;
        row.id = `account-row-${acc.id}`;
        row.innerHTML = `
          <td style="display: none;">${staleFlag}</td>
          <td>${acc.id}</td>
          <td>${acc.email}</td>
          <td>${acc.is_pro ? "✅" : "❌"}</td>
          <td>${formatBytes(acc.used_quota)}</td>
          <td>${formatBytes(acc.total_quota)}</td>
          <td>${formatDate(acc.last_login)}</td>
          <td>
            <button id="refresh-btn-${
              acc.id
            }" class="btn btn-sm btn-outline-light"
              onclick="refreshAccount(${acc.id})">
              <i class="fas fa-sync-alt"></i>
            </button>
            <button class="btn btn-sm btn-outline-danger"
              onclick="confirmDeleteAccount(${acc.id}, '${acc.email}')"
              title="Delete this account">
              <i class="fas fa-trash-alt"></i>
            </button>
          </td>
        `;

        if (staleAccounts.includes(acc)) {
          row.classList.add("table-stale");
        }

        tbody.appendChild(row);
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
document.addEventListener("DOMContentLoaded", () => {
  const verifyModalEl = document.getElementById("verifyAccountModal");
  if (verifyModalEl) {
    verifyModalEl.addEventListener("hidden.mdb.modal", () => {
      document.getElementById("verificationLinkInput").value = "";
    });
  }
});
