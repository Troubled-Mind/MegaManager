function initMDBInputs() {
  document.querySelectorAll(".form-outline").forEach((formOutline) => {
    mdb.Input.getOrCreateInstance(formOutline).init();
  });
}

async function loadSettings() {
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

  $(".repeater").repeater(
    "setList",
    localPaths.map((p) => ({ local_paths: p }))
  );
  initMDBInputs();
}

$(document).ready(function () {
  $(".repeater").repeater({
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
  loadSettings();
});

document
  .getElementById("settingsForm")
  .addEventListener("submit", async (e) => {
    e.preventDefault();

    const data = {
      megacmd_path: document.getElementById("megacmd_path").value,
      mega_email: document.getElementById("mega_email").value,
      mega_passwords: document.getElementById("mega_passwords").value,
      app_password: document.getElementById("app_password").value,
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
