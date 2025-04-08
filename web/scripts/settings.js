document.addEventListener("DOMContentLoaded", async () => {
  const res = await fetch("/api/settings");
  const data = await res.json();
  for (const key in data) {
    const input = document.getElementById(key);
    if (input) {
      if (input.type === "password") {
        input.value = data[key];
      } else if (input.type === "text") {
        input.value = data[key];
      } else if (input.type === "email") {
        input.value = data[key];
      }
      input.focus();
    }
  }
  document.activeElement.blur();
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
    };

    const response = await fetch("/run-command", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        command: "settings-update",
        args: {
          megacmd_path: data.megacmd_path,
          mega_email: data.mega_email,
          mega_passwords: data.mega_passwords,
          app_password: data.app_password,
        },
      }),
    });

    const result = await response.json();

    const toast = document.getElementById("universalToast");
    const body = document.getElementById("universalToastBody");
    body.textContent = result.message || "Settingsa updated.";
    new mdb.Toast(toast).show();
  });
