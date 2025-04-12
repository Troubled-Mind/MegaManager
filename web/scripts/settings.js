const unsafeChars = /[|&;<>()$`"\' !*?~#=%@^,:{}\[\]+]/g;

fetch("/api/version")
  .then((res) => res.json())
  .then((data) => {
    document.getElementById("appVersion").textContent =
      data.version || "Unknown";
  })
  .catch(() => {
    document.getElementById("appVersion").textContent = "Error";
  });

function initMDBInputs() {
  document.querySelectorAll(".form-outline").forEach((formOutline) => {
    mdb.Input.getOrCreateInstance(formOutline).init();
  });
}

function exportData(exportType, filename) {
  fetch("/run-command", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: `command=csv-export-data:${exportType}`,
  }).then(res => res.json()).then(data => {
    if (data.status === 200) {
      const blob = new Blob([data.body], { type: "text/csv;charset=utf-8;" });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();

      showToast("✅ CSV file downloaded successfully.", "bg-success");
    } else {
      showToast("❌ Failed to download CSV file.", "bg-danger");
    }
  }).catch(err => {
    showToast("❌ Failed to download CSV file.", "bg-danger");
  })
}

async function loadSettings(repeater) {
  const res = await fetch("/api/settings");
  const data = await res.json();

  for (const key in data) {
    const input = document.getElementById(key);
    if (input && ["password", "text", "email"].includes(input.type)) {
      input.value = data[key];
      input.focus();
    }
  }

  document.activeElement.blur();

  // Handle local_paths
  let localPaths = data.local_paths;
  if (typeof localPaths === "string") {
    try {
      localPaths = JSON.parse(localPaths);
    } catch (e) {
      console.warn("Failed to parse local_paths:", e);
      localPaths = [];
    }
  }

  arr = Array.from({ length: localPaths.length }, (_, i) => ({
    local_paths: localPaths[i],
  }));
  repeater.setList(arr);
}

$(document).ready(function () {
  let repeater = $(".repeater").repeater({
    initEmpty: true,
    defaultValues: {},
    show: function () {
      $(this).slideDown();
      initMDBInputs();
    },
    hide: function (deleteElement) {
      $(this).slideUp(deleteElement);
    },
  });

  initMDBInputs();
  loadSettings(repeater);
});

document
  .getElementById("settingsForm")
  .addEventListener("submit", async (e) => {
    e.preventDefault();

    const password = document.getElementById("mega_passwords").value;
    if (unsafeChars.test(password)) {
      showToast("❌ Password contains unsupported characters.", "bg-danger");
      return;
    }

    const data = {
      megacmd_path: document.getElementById("megacmd_path").value,
      mega_email: document.getElementById("mega_email").value,
      mega_passwords: document.getElementById("mega_passwords").value,
      app_password: document.getElementById("app_password").value,
      date_format_full: document.getElementById("date_format_full").value,
      date_format_month: document.getElementById("date_format_month").value,
      date_format_year: document.getElementById("date_format_year").value,
      local_paths: Array.from(
        document.querySelectorAll(
          'input[name^="folder_paths"][name$="[local_paths]"]'
        )
      )
        .map((el) => el.value)
        .filter((v) => v.trim() !== ""),
    };

    const response = await fetch("/run-command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        command: "settings-update",
        args: data,
      }),
    });

    const result = await response.json();

    const toast = document.getElementById("universalToast");
    const body = document.getElementById("universalToastBody");
    body.textContent = result.message || "Settings updated.";
    new mdb.Toast(toast).show();
  });

document
  .getElementById("mega_passwords")
  .addEventListener("input", function () {
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
