document.addEventListener("DOMContentLoaded", () => {
  const statusSelect = document.getElementById("status-select");
  const statusForm = document.getElementById("status-form");
  const confirmModal = document.getElementById("confirm-modal");

  // Bootstrap modal instance
  const interviewModal = new bootstrap.Modal(document.getElementById("interviewModal"));

  // When recruiter selects "Accepted"
  statusSelect.addEventListener("change", () => {
    if (statusSelect.value === "accepted") {
      interviewModal.show();
    }
  });

  // Confirm button adds hidden inputs and submits form
  confirmModal.addEventListener("click", () => {
    const dateInput = document.getElementById("interview-date").value;
    const timeInput = document.getElementById("interview-time").value;

    if (!dateInput || !timeInput) {
      alert("Please select both date and time for the interview.");
      return;
    }

    // Create hidden fields for backend
    const dateField = document.createElement("input");
    dateField.type = "hidden";
    dateField.name = "interview_date";
    dateField.value = dateInput;

    const timeField = document.createElement("input");
    timeField.type = "hidden";
    timeField.name = "interview_time";
    timeField.value = timeInput;

    statusForm.appendChild(dateField);
    statusForm.appendChild(timeField);

    interviewModal.hide();
    statusForm.submit();
  });
});
