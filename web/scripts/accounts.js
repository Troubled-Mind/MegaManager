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
            title="Log in and refresh quota" onclick="refreshAccount(${
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
      console.log("Error Message:", message); // Log error message for debugging

      // If the error message contains "unconfirmed account", add the class and show the verify button
      if (message.toLowerCase().includes("unconfirmed account")) {
        const row = document.getElementById(`account-row-${id}`);
        if (row) {
          row.classList.add("table-unverified"); // Add the table-unverified class here
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
        const isStale = acc.last_login && acc.last_login < cutoff;
        const staleFlag = isStale ? 1 : 0;
        row.id = `account-row-${acc.id}`;
        row.innerHTML = `
          <td style="display: none !important;">${staleFlag}</td>
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
