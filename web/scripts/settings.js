const unsafeChars = /[|&;<>()$`"\'!*?~#=%@^,:{}\[\]+]/g;

fetch("/api/version")
  .then((res) => res.json())
  .then((data) => {
    document.getElementById("appVersion").textContent = data.version || "Unknown";
  })
  .catch(() => {
    document.getElementById("appVersion").textContent = "Error";
  });

function initMDBInputs() {
  document.querySelectorAll(".form-outline").forEach((formOutline) => {
    mdb.Input.getOrCreateInstance(formOutline).init();
  });
}

function updateSecurityStatus() {
  const pw = document.getElementById("app_password")?.value || "";
  const badge = document.getElementById("securityStatusBadge");
  const alert = document.getElementById("securityUnprotectedAlert");
  if (!badge) return;

  if (pw.trim() === "") {
    badge.className = "badge px-3 py-2 fw-bold";
    badge.style.cssText =
      "background: rgba(239,68,68,0.18); color: #f87171; border: 1px solid rgba(239,68,68,0.35); letter-spacing: 0.05em; font-size: 0.78rem;";
    badge.innerHTML = '<i class="fas fa-lock-open me-1"></i> UNPROTECTED';
    if (alert) alert.style.removeProperty("display");
  } else {
    badge.className = "badge px-3 py-2 fw-bold";
    badge.style.cssText =
      "background: rgba(52,211,153,0.18); color: #34d399; border: 1px solid rgba(52,211,153,0.35); letter-spacing: 0.05em; font-size: 0.78rem;";
    badge.innerHTML = '<i class="fas fa-lock me-1"></i> PROTECTED';
    if (alert) alert.style.display = "none";
  }
}

function exportData(exportType, filename) {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=io_csv_export:${exportType}`,
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200) {
        const blob = new Blob([data.body], { type: "text/csv;charset=utf-8;" });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();

        showToast("CSV file downloaded successfully.", "bg-success");
      } else {
        showToast("Failed to download CSV file.", "bg-danger");
      }
    })
    .catch((err) => {
      showToast("Failed to download CSV file.", "bg-danger");
    });
}

async function loadSettings(repeater) {
  const res = await fetch("/api/settings");
  const data = await res.json();

  for (const key in data) {
    const input = document.getElementById(key);
    if (input && (input.tagName === "INPUT" || input.tagName === "TEXTAREA" || input.tagName === "SELECT")) {
      input.value = data[key] != null ? data[key] : "";
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }
  }
  initMDBInputs();

  // Handle local_paths - manually add one row per path
  let localPaths = data.local_paths;
  if (typeof localPaths === "string") {
    try {
      localPaths = JSON.parse(localPaths);
    } catch (e) {
      console.warn("Failed to parse local_paths:", e);
      localPaths = [];
    }
  }

  if (Array.isArray(localPaths) && localPaths.length > 0) {
    const listContainer = repeater.find("[data-repeater-list]");

    localPaths.forEach((path, i) => {
      const row = $(`
 <div data-repeater-item class="mb-2">
 <div class="input-group">
 <span class="input-group-text border-0 bg-transparent opacity-50">
 <i class="fas fa-folder"></i>
 </span>
 <input type="text"
 name="folder_paths[${i}][local_paths]"
 class="form-control bg-transparent"
 placeholder="/absolute/path/to/files"
 value="${path.replace(/"/g, "&quot;")}"/>
 <button data-repeater-delete type="button" class="btn btn-link text-danger">
 <i class="fas fa-times"></i>
 </button>
 </div>
 </div>
 `);
      row.find("[data-repeater-delete]").on("click", function () {
        $(this)
          .closest("[data-repeater-item]")
          .slideUp(function () {
            $(this).remove();
          });
      });
      listContainer.append(row);
    });
  }

  testMegaCmd(true);
  testRclone(true);
  updateSecurityStatus();

  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command: "system_rclone_test" }),
  })
    .then((r) => r.json())
    .then((data) => {
      const el = document.getElementById("rcloneConfPath");
      if (el && data.conf_path) el.textContent = data.conf_path;
    })
    .catch(() => {});

  const slider = document.getElementById("login_max_attempts");
  const display = document.getElementById("lockoutAttemptsDisplay");
  if (slider && display) display.textContent = slider.value;
}

async function discoverMegaCmd() {
  const btn = document.getElementById("discoverMegaCmdBtn");
  const resultEl = document.getElementById("megacmdTestResult");
  const pathInput = document.getElementById("megacmd_path");

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> Searching...`;
  }
  if (resultEl) {
    resultEl.className = "small mt-1 text-muted";
    resultEl.innerHTML = `<i class="fas fa-search me-1"></i> Searching common install locations...`;
    resultEl.style.display = "block";
  }

  try {
    const res = await fetch("/run-command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: "system_megacmd_discover" }),
    });
    const data = await res.json();

    if (data.found && data.path) {
      if (pathInput) {
        pathInput.value = data.path;
        // Re-initialise MDB floating label so it doesn't overlap the new value
        const outline = pathInput.closest(".form-outline");
        if (outline) mdb.Input.getOrCreateInstance(outline).update();
      }
      if (resultEl) {
        resultEl.className = "small mt-1 text-success";
        resultEl.innerHTML = `<i class="fas fa-check-circle me-1"></i> Found via ${data.method === "PATH" ? "system PATH" : "default install location"}: <code>${data.path}</code>`;
        resultEl.style.display = "block";
      }
      showToast(`Found MEGAcmd at ${data.path}`, "bg-success");
      testMegaCmd(true);
    } else {
      if (resultEl) {
        resultEl.className = "small mt-1 text-warning";
        resultEl.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i> MEGAcmd not found automatically. Please install it or enter the path manually.`;
        resultEl.style.display = "block";
      }
      const downloadBtn = document.getElementById("downloadMegaCmdBtn");
      if (downloadBtn) downloadBtn.style.display = "inline-flex";
      showToast("MEGAcmd not found. Install it or enter the path manually.", "bg-warning");
    }
  } catch (err) {
    if (resultEl) {
      resultEl.className = "small mt-1 text-danger";
      resultEl.innerHTML = `<i class="fas fa-times-circle me-1"></i> Discovery failed: ${err.message}`;
      resultEl.style.display = "block";
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="fas fa-search-location me-1"></i> Auto-discover`;
    }
  }
}

async function testMegaCmd(isSilent = false) {
  const testBtn = document.getElementById("testMegaCmdBtn");
  const discoverBtn = document.getElementById("discoverMegaCmdBtn");
  const downloadBtn = document.getElementById("downloadMegaCmdBtn");
  const badgeEl = document.getElementById("megacmdStatusBadge");
  const resultEl = document.getElementById("megacmdTestResult");
  const pathInput = document.getElementById("megacmd_path")?.value?.trim() || "";

  if (testBtn && !isSilent) {
    testBtn.disabled = true;
    testBtn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> Testing...`;
  }

  try {
    const response = await fetch("/run-command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command: "system_megacmd_test",
        args: { megacmd_path: pathInput },
      }),
    });

    const data = await response.json();

    if (data.status === 200 && data.valid) {
      if (badgeEl) {
        badgeEl.className = "badge bg-success bg-opacity-25 text-success border border-success border-opacity-25 px-2 py-1 small";
        badgeEl.innerHTML = `<i class="fas fa-check-circle me-1"></i> Verified`;
        badgeEl.style.display = "inline-flex";
      }
      if (downloadBtn) downloadBtn.style.display = "none";
      if (testBtn) testBtn.style.display = "none";
      if (discoverBtn) discoverBtn.style.display = "none";
      if (resultEl) {
        resultEl.className = "small mt-1 text-success";
        resultEl.innerHTML = `<i class="fas fa-check-circle me-1"></i> All files present in <code>${data.directory}</code>`;
        resultEl.style.display = "block";
      }
      if (!isSilent) {
        showToast(`MEGAcmd verified in ${data.directory}.`, "bg-success");
      }
    } else {
      const issueDetails =
        data.message || (data.missing_binaries?.length ? `Missing: ${data.missing_binaries.join(", ")}` : "Files not detected");
      if (badgeEl) {
        badgeEl.className = "badge bg-warning bg-opacity-25 text-warning border border-warning border-opacity-25 px-2 py-1 small";
        badgeEl.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i> Not Detected`;
        badgeEl.style.display = "inline-flex";
      }
      if (downloadBtn) downloadBtn.style.display = "inline-flex";
      if (testBtn) testBtn.style.display = "";
      if (discoverBtn) discoverBtn.style.display = "";
      if (resultEl) {
        resultEl.className = "small mt-1 text-danger";
        resultEl.innerHTML = `<i class="fas fa-times-circle me-1"></i> ${issueDetails}`;
        resultEl.style.display = "block";
      }
      if (!isSilent) showToast(`MEGAcmd issue: ${issueDetails}`, "bg-danger");
    }
  } catch (err) {
    if (downloadBtn) downloadBtn.style.display = "inline-flex";
    if (testBtn) testBtn.style.display = "";
    if (discoverBtn) discoverBtn.style.display = "";
    showToast(`MEGAcmd test error: ${err.message || "Unable to connect to server."}`, "bg-danger");
  } finally {
    if (testBtn) {
      testBtn.disabled = false;
      testBtn.innerHTML = `<i class="fas fa-vial me-1"></i> Test MEGAcmd`;
    }
  }
}

$(document).ready(function () {
  let repeater = $("#folder-repeater").repeater({
    initEmpty: true,
    defaultValues: {},
    show: function () {
      $(this).show();
      initMDBInputs();
    },
    hide: function (deleteElement) {
      $(this).slideUp(deleteElement);
    },
  });

  initMDBInputs();
  loadSettings(repeater);

  const TAB_SLUGS = {
    "core-config": "tab-core-link",
    "monitored-folders": "tab-folders-link",
    security: "tab-security-link",
    data: "tab-maintenance-link",
  };
  const SLUG_FROM_ID = Object.fromEntries(Object.entries(TAB_SLUGS).map(([slug, id]) => [id, slug]));

  function activateTab(btn) {
    if (!btn) return;
    const tab = mdb.Tab.getOrCreateInstance(btn);
    tab.show();
  }

  document.querySelectorAll("#settingsTabs button[data-mdb-tab-init]").forEach((tabBtn) => {
    tabBtn.addEventListener("shown.mdb.tab", function () {
      initMDBInputs();
      const slug = SLUG_FROM_ID[this.id];
      if (slug) {
        const url = new URL(window.location);
        url.searchParams.set("tab", slug);
        history.replaceState(null, "", url);
      }
    });
    tabBtn.addEventListener("shown.bs.tab", function () {
      initMDBInputs();
    });
  });

  const urlTab = new URLSearchParams(window.location.search).get("tab");
  if (urlTab && TAB_SLUGS[urlTab]) {
    // Wait a tick for MDB to finish initializing tabs
    setTimeout(() => {
      const btn = document.getElementById(TAB_SLUGS[urlTab]);
      activateTab(btn);
    }, 50);
  }
});

document.getElementById("settingsForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const password = document.getElementById("mega_passwords").value;
  if (unsafeChars.test(password)) {
    showToast("Password contains unsupported characters.", "bg-danger");
    return;
  }

  const data = {
    megacmd_path: document.getElementById("megacmd_path").value,
    rclone_path: document.getElementById("rclone_path")?.value || "",
    mega_email: document.getElementById("mega_email").value,
    mega_passwords: document.getElementById("mega_passwords").value,
    app_password: document.getElementById("app_password").value,
    date_format_full: document.getElementById("date_format_full").value,
    date_format_month: document.getElementById("date_format_month").value,
    date_format_year: document.getElementById("date_format_year").value,
    login_max_attempts: parseInt(document.getElementById("login_max_attempts")?.value || "5", 10),
    local_paths: Array.from(document.querySelectorAll('input[name^="folder_paths"][name$="[local_paths]"]'))
      .map((el) => el.value)
      .filter((v) => v.trim() !== ""),
  };

  const response = await fetch("/run-command", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      command: "system_settings",
      args: data,
    }),
  });

  const result = await response.json();

  const toast = document.getElementById("universalToast");
  const body = document.getElementById("universalToastBody");
  body.textContent = result.message || "Settings updated.";
  new mdb.Toast(toast).show();

  testMegaCmd(true);
  testRclone(true);
  updateSecurityStatus();
});

document.getElementById("mega_passwords").addEventListener("input", function () {
  const value = this.value;
  const warningEl = document.getElementById("passwordWarning");
  if (unsafeChars.test(value)) {
    warningEl.style.display = "block";
    this.classList.add("is-invalid");
  } else {
    warningEl.style.display = "none";
    this.classList.remove("is-invalid");
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const pwField = document.getElementById("app_password");
  if (pwField) pwField.addEventListener("input", updateSecurityStatus);
});

async function discoverRclone() {
  const btn = document.getElementById("discoverRcloneBtn");
  const resultEl = document.getElementById("rcloneTestResult");
  const pathInput = document.getElementById("rclone_path");

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> Searching...`;
  }
  if (resultEl) {
    resultEl.className = "small mt-1 text-muted";
    resultEl.innerHTML = `<i class="fas fa-search me-1"></i> Searching common install locations...`;
    resultEl.style.display = "block";
  }

  try {
    const res = await fetch("/run-command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: "system_rclone_discover" }),
    });
    const data = await res.json();

    if (data.found && data.path) {
      if (pathInput) {
        pathInput.value = data.path;
        const outline = pathInput.closest(".form-outline");
        if (outline) mdb.Input.getOrCreateInstance(outline).update();
      }
      if (resultEl) {
        resultEl.className = "small mt-1 text-success";
        resultEl.innerHTML = `<i class="fas fa-check-circle me-1"></i> Found: <code>${data.path}</code>`;
        resultEl.style.display = "block";
      }
      showToast(`Found rclone at ${data.path}`, "bg-success");
      testRclone(true);
    } else {
      if (resultEl) {
        resultEl.className = "small mt-1 text-warning";
        resultEl.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i> rclone not found automatically. Visit <a href="https://rclone.org/downloads/" target="_blank" class="text-info">rclone.org/downloads</a> to install.`;
        resultEl.style.display = "block";
      }
      showToast("rclone not found. Please install it.", "bg-warning");
    }
  } catch (err) {
    if (resultEl) {
      resultEl.className = "small mt-1 text-danger";
      resultEl.innerHTML = `<i class="fas fa-times-circle me-1"></i> Discovery failed: ${err.message}`;
      resultEl.style.display = "block";
    }
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="fas fa-search-location me-1"></i> Auto-discover`;
    }
  }
}

async function testRclone(isSilent = false) {
  const testBtn = document.getElementById("testRcloneBtn");
  const badgeEl = document.getElementById("rcloneStatusBadge");
  const resultEl = document.getElementById("rcloneTestResult");
  const downloadBtn = document.getElementById("downloadRcloneBtn");
  const discoverBtn = document.getElementById("discoverRcloneBtn");
  const pathInput = document.getElementById("rclone_path")?.value?.trim() || "";

  if (testBtn && !isSilent) {
    testBtn.disabled = true;
    testBtn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> Testing...`;
  }

  try {
    const res = await fetch("/run-command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        command: "system_rclone_test",
        args: { rclone_path: pathInput },
      }),
    });
    const data = await res.json();

    if (data.valid) {
      if (badgeEl) {
        badgeEl.className = "badge bg-success bg-opacity-25 text-success border border-success border-opacity-25 px-2 py-1 small";
        badgeEl.innerHTML = `<i class="fas fa-check-circle me-1"></i> Verified`;
        badgeEl.style.display = "inline-flex";
      }
      if (downloadBtn) downloadBtn.style.display = "none";
      if (testBtn) testBtn.style.display = "none";
      if (discoverBtn) discoverBtn.style.display = "none";
      if (resultEl) {
        resultEl.className = "small mt-1 text-success";
        resultEl.innerHTML = `<i class="fas fa-check-circle me-1"></i> ${data.version || "rclone is working"}`;
        resultEl.style.display = "block";
      }
      if (!isSilent) showToast(`rclone verified: ${data.version}`, "bg-success");
    } else {
      if (badgeEl) {
        badgeEl.className = "badge bg-warning bg-opacity-25 text-warning border border-warning border-opacity-25 px-2 py-1 small";
        badgeEl.innerHTML = `<i class="fas fa-exclamation-triangle me-1"></i> Not Detected`;
        badgeEl.style.display = "inline-flex";
      }
      if (downloadBtn) downloadBtn.style.display = "inline-flex";
      if (testBtn) testBtn.style.display = "";
      if (discoverBtn) discoverBtn.style.display = "";
      if (resultEl) {
        resultEl.className = "small mt-1 text-danger";
        resultEl.innerHTML = `<i class="fas fa-times-circle me-1"></i> ${data.message || "rclone not found"}`;
        resultEl.style.display = "block";
      }
      if (!isSilent) showToast(`rclone issue: ${data.message}`, "bg-danger");
    }
  } catch (err) {
    if (!isSilent) showToast(`rclone test error: ${err.message}`, "bg-danger");
  } finally {
    if (testBtn) {
      testBtn.disabled = false;
      testBtn.innerHTML = `<i class="fas fa-vial me-1"></i> Test rclone`;
    }
  }
}

async function rebuildRcloneConfig() {
  const btn = document.getElementById("rebuildRcloneConfigBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin me-1"></i> Syncing...`;
  }
  try {
    const res = await fetch("/run-command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command: "system_rclone_rebuild_config" }),
    });
    const data = await res.json();
    showToast(data.status === 200 ? `${data.message}` : `${data.message}`, data.status === 200 ? "bg-success" : "bg-danger");
  } catch (err) {
    showToast(`Config sync failed: ${err.message}`, "bg-danger");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="fas fa-sync me-1"></i> Sync Config`;
    }
  }
}

let verifyPollInterval = null;

async function verifyAllCloudFiles() {
  const btn = document.getElementById("verifyCloudBtn");
  const container = document.getElementById("verifyProgressContainer");
  const bar = document.getElementById("verifyProgressBar");
  const msgEl = document.getElementById("verifyProgressMessage");
  const countEl = document.getElementById("verifyProgressCount");

  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i> Initializing...`;
  }

  if (container) {
    container.classList.remove("d-none");
    if (bar) bar.style.width = "0%";
    if (msgEl) msgEl.textContent = "Starting verification...";
    if (countEl) countEl.textContent = "0 / 0";
  }

  try {
    const res = await fetch("/run-command", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: " command=account_verify_files:all",
    });

    const data = await res.json();
    if (data.status !== 200) {
      showToast("Verification failed to start: " + data.message, "bg-danger");
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `<i class="fas fa-shield-alt me-2"></i> Verify All`;
      }
      return;
    }

    if (verifyPollInterval) clearInterval(verifyPollInterval);
    verifyPollInterval = setInterval(pollVerificationStatus, 1500);
  } catch (err) {
    showToast("Network error during verification.", "bg-danger");
    console.error(err);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="fas fa-shield-alt me-2"></i> Verify All`;
    }
  }
}

async function pollVerificationStatus() {
  try {
    const res = await fetch("/run-command", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: " command=account_verify_status",
    });
    const data = await res.json();

    const container = document.getElementById("verifyProgressContainer");
    const bar = document.getElementById("verifyProgressBar");
    const msgEl = document.getElementById("verifyProgressMessage");
    const countEl = document.getElementById("verifyProgressCount");
    const btn = document.getElementById("verifyCloudBtn");

    if (data.status === 200) {
      if (btn && data.is_running) {
        btn.innerHTML = `<i class="fas fa-spinner fa-spin me-2"></i> Verifying...`;
      }

      const pct = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
      if (bar) bar.style.width = `${pct}%`;
      if (msgEl) msgEl.textContent = data.message;
      if (countEl) countEl.textContent = `${data.current} / ${data.total}`;

      if (data.done) {
        clearInterval(verifyPollInterval);
        verifyPollInterval = null;
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `<i class="fas fa-shield-alt me-2"></i> Verify All`;
        }
        showToast("Verification completed.", "bg-success");
        setTimeout(() => {
          if (container) container.classList.add("d-none");
        }, 5000); // hide after 5 seconds
      }
    }
  } catch (err) {
    console.error("Error polling verification status", err);
  }
}
