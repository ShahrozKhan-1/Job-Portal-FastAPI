
document.addEventListener("DOMContentLoaded", function () {
  const step1 = document.getElementById("step1");
  const step2 = document.getElementById("step2");
  const step3 = document.getElementById("step3");
  const nextToStep2 = document.getElementById("nextToStep2");
  const nextToStep3 = document.getElementById("nextToStep3");
  const backToStep1 = document.getElementById("backToStep1");
  const backToStep2 = document.getElementById("backToStep2");
  const addQuestionBtn = document.getElementById("addQuestion");
  const questionList = document.getElementById("questionList");
  const form = document.getElementById("interviewForm");

  const previewTitle = document.getElementById("previewTitle");
  const previewCategory = document.getElementById("previewCategory");
  const previewDescription = document.getElementById("previewDescription");
  const previewQuestions = document.getElementById("previewQuestions");
  const statusToggle = document.getElementById("statusToggle");

  // ➕ Add Question
  addQuestionBtn.addEventListener("click", () => {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "form-control mb-2";
    input.placeholder = `Enter question ${questionList.children.length + 1}`;
    questionList.appendChild(input);
  });

  // ➡️ Next to Step 2
  nextToStep2.addEventListener("click", () => {
    step1.style.display = "none";
    step2.style.display = "block";
  });

  // ➡️ Next to Step 3 (preview)
  nextToStep3.addEventListener("click", () => {
    step2.style.display = "none";
    step3.style.display = "block";

    previewTitle.textContent = document.getElementById("title").value;
    previewCategory.textContent = document.getElementById("category").value;
    previewDescription.textContent = document.getElementById("description").value;

    previewQuestions.innerHTML = "";
    Array.from(questionList.children).forEach((input, index) => {
      const p = document.createElement("p");
      p.textContent = `${index + 1}. ${input.value}`;
      previewQuestions.appendChild(p);
    });
  });

  // ⬅️ Back buttons
  backToStep1.addEventListener("click", () => {
    step2.style.display = "none";
    step1.style.display = "block";
  });

  backToStep2.addEventListener("click", () => {
    step3.style.display = "none";
    step2.style.display = "block";
  });

  document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.getElementById("statusToggle");
    const label = document.getElementById("statusLabel");
    toggle.addEventListener("change", () => {
      label.textContent = toggle.checked ? "Open" : "Closed";
    });
  });

  // ✅ Submit form
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = {
      title: document.getElementById("title").value,
      category: document.getElementById("category").value,
      description: document.getElementById("description").value,
      status: statusToggle.checked, // ✅ boolean
      questions: Array.from(questionList.children).map(input => input.value.trim()).filter(q => q)
    };

    try {
      const response = await fetch("/create-public-interview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        alert("✅ Public interview created successfully!");
        window.location.reload();
      } else {
        const error = await response.json();
        alert("❌ Error: " + (error.detail || "Failed to create interview"));
      }
    } catch (err) {
      console.error(err);
      alert("❌ Network error while creating interview.");
    }
  });
});
