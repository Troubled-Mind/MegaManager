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

  if (!silent && btn) {
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
    .then(() => {
      if (!silent && btn) {
        btn.classList.remove("btn-outline-warning");
        btn.classList.add("btn-success");
      }

      // Fetch the updated data for the account
      return fetch("/run-command", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: `command=mega-get-account:${id}`,
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
              </td>
            `;
          const oldRow = document.getElementById(`account-row-${acc.id}`);
          if (oldRow) oldRow.replaceWith(newRow);

          newRow.classList.add("flash-row");
        });
    })
    .catch((err) => {
      console.error(`Refresh for account ${id} failed:`, err);
      if (!silent && btn) {
        btn.classList.remove("btn-outline-warning");
        btn.classList.add("btn-danger");
      }
    })
    .finally(() => {
      if (!silent && btn) {
        setTimeout(() => {
          btn.classList.remove("btn-success", "btn-danger");
          btn.classList.add("btn-outline-light");
          btn.disabled = false;
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
      console.log("Reloaded account data:", data.accounts);
      const wrapper = document.getElementById("accountTableWrapper");
      const newTable = document.createElement("table");
      newTable.className = "table table-dark table-hover";

      newTable.innerHTML = `
          <thead>
            <tr>
              <th>ID</th>
              <th>Email</th>
              <th>Pro</th>
              <th>Used</th>
              <th>Total</th>
              <th>Last Login</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="accountTableBody"></tbody>
        `;

      wrapper.innerHTML = ""; // Clear the entire wrapper
      wrapper.appendChild(newTable);

      const tbody = newTable.querySelector("tbody");

      data.accounts.forEach((acc) => {
        const buttonId = `refresh-btn-${acc.id}`;
        const row = document.createElement("tr");
        row.id = `account-row-${acc.id}`;
        row.innerHTML = `
            <td>${acc.id}</td>
            <td>${acc.email}</td>
            <td>${acc.is_pro ? "✅" : "❌"}</td>
            <td>${formatBytes(acc.used_quota)}</td>
            <td>${formatBytes(acc.total_quota)}</td>
            <td>${formatDate(acc.last_login)}</td>
            <td>
              <button id="${buttonId}" class="btn btn-sm btn-outline-light" title="Log in and refresh quota"
                onclick="refreshAccount(${acc.id})">
                <i class="fas fa-sync-alt"></i>
              </button>
            </td>
          `;
        tbody.appendChild(row);
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

      for (let i = 0; i < total; i++) {
        const id = ids[i];
        btn.innerHTML = `<i class="fas fa-sync-alt me-2 fa-spin" id="refreshAllIcon"></i> Refreshing account ${
          i + 1
        } / ${total}...`;

        await refreshAccount(id, { silent: true }); // 🔁 reuse the logic
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

// Add new accounts from csv
function addNewAccounts() {
  const btn = document.getElementById("addNewAccountsBtn");
  const icon = document.getElementById("addNewAccountsIcon");

  btn.classList.remove("btn-primary", "btn-success", "btn-danger");
  btn.classList.add("btn-warning");
  icon.classList.add("fa-spin");
  btn.disabled = true;

  const filename = "accounts.csv"; // TODO: replace with actual filename

  return fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=csv-load-accounts:${filename}`,
  }).then((res) => res.json()).then(() => {
    loadAccountTable(); // Reload the account table after adding new accounts

    // Finished
    btn.innerHTML = `<i class="fas fa-check me-2"></i> New accounts added!`;
    btn.classList.remove("btn-warning");
    btn.classList.add("btn-success");
  }).finally(() => {
    icon.classList.remove("fa-spin");
      setTimeout(() => {
        btn.innerHTML = `<i class="fas fa-sync-alt me-2" id="addNewAccountsIcon"></i> Add new accounts`;
        btn.classList.remove("btn-success", "btn-danger");
        btn.classList.add("btn-primary");
        btn.disabled = false;
      }, 4000);
  })
}
