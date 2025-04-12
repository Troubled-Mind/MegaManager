function fetchOngoingUploads() {
  fetch("/run-command", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      command: "get-ongoing-uploads",
    }),
  })
    .then((res) => res.json())
    .then((data) => {
      if (data.status === 200 && Array.isArray(data.uploads)) {
        displayOngoingUploads(data.uploads);
      } else {
        console.error("❌ Error fetching ongoing uploads:", data.message);
      }
    })
    .catch((err) => {
      console.error("❌ Error fetching ongoing uploads:", err);
    });
}

function displayOngoingUploads(uploads) {
  const uploadsList = document.getElementById("uploads-list");
  uploadsList.innerHTML = ""; // Clear the list before displaying new uploads

  uploads.forEach((upload) => {
    // Only display uploads that are in progress
    if (upload.upload_status === "In Progress") {
      const uploadItem = document.createElement("div");
      uploadItem.classList.add("upload-item");
      uploadItem.classList.add("mb-4");

      // Determine the class for the progress bar based on the progress percentage
      let progressClass = "";

      if (upload.progress <= 25) {
        progressClass = "bg-danger"; // Red for 0-25%
      } else if (upload.progress <= 75) {
        progressClass = "bg-warning"; // Yellow for 25-75%
      } else {
        progressClass = "bg-success"; // Green for 75-100%
      }

      // Create the progress bar using MDBootstrap
      uploadItem.innerHTML = `
            <p><strong>File ID: ${upload.file_id}</strong> - ${upload.file_name}</p>
            <div class="progress">
              <div id="progress-bar-${upload.file_id}" class="progress-bar progress-bar-striped progress-bar-animated ${progressClass}" role="progressbar" style="width: ${upload.progress}%; height:auto" aria-valuenow="${upload.progress}" aria-valuemin="0" aria-valuemax="100">${upload.progress}%</div>
            </div>
            <span id="progress-text-${upload.file_id}">${upload.progress}%</span>
          `;
      uploadsList.appendChild(uploadItem);
    }
  });
}

document.addEventListener("DOMContentLoaded", function () {
  fetchOngoingUploads();

  setInterval(fetchOngoingUploads, 2000); // Poll for updates every 2s
});
