document.addEventListener("DOMContentLoaded", function () {
  // Elements
  const step1 = document.getElementById("step1");
  const step2 = document.getElementById("step2");
  const step3 = document.getElementById("step3");
  const nextToStep2 = document.getElementById("nextToStep2");
  const nextToStep3 = document.getElementById("nextToStep3");
  const backToStep1 = document.getElementById("backToStep1");
  const backToStep2 = document.getElementById("backToStep2");
  const form = document.getElementById("interviewForm");

  // Skill management
  const skillsInput = document.getElementById("skillsInput");
  const addSkillBtn = document.getElementById("addSkill");
  const skillsContainer = document.getElementById("skillsContainer");
  const skillsHidden = document.getElementById("skills");

  // Preview elements
  const previewTitle = document.getElementById("previewTitle");
  const previewRole = document.getElementById("previewRole");
  const previewSkills = document.getElementById("previewSkills");
  const previewCategory = document.getElementById("previewCategory");
  const previewDescription = document.getElementById("previewDescription");
  const statusToggle = document.getElementById("statusToggle");
  const statusLabel = document.getElementById("statusLabel");

  // Character counters
  const titleCount = document.getElementById("titleCount");
  const descriptionCount = document.getElementById("descriptionCount");
  const titleInput = document.getElementById("title");
  const descriptionInput = document.getElementById("description");

  // Skills array
  let skills = [];

  // Initialize character counters
  titleCount.textContent = titleInput.value.length;
  descriptionCount.textContent = descriptionInput.value.length;

  // Character count updates
  titleInput.addEventListener("input", () => {
    titleCount.textContent = titleInput.value.length;
    updateCharacterCountStyle(titleCount, titleInput.value.length, 255);
  });

  descriptionInput.addEventListener("input", () => {
    descriptionCount.textContent = descriptionInput.value.length;
    updateCharacterCountStyle(descriptionCount, descriptionInput.value.length, 2000);
  });

  function updateCharacterCountStyle(element, count, max) {
    element.classList.remove('warning', 'danger');
    if (count > max * 0.9) {
      element.classList.add('danger');
    } else if (count > max * 0.75) {
      element.classList.add('warning');
    }
  }

  // Skill management functions
  function addSkill(skillText) {
    const skill = skillText.trim();
    if (skill && !skills.includes(skill)) {
      skills.push(skill);
      updateSkillsDisplay();
      skillsInput.value = '';
    }
  }

  function removeSkill(skill) {
    skills = skills.filter(s => s !== skill);
    updateSkillsDisplay();
  }

  function updateSkillsDisplay() {
    skillsContainer.innerHTML = '';
    skills.forEach(skill => {
      const tag = document.createElement('div');
      tag.className = 'skill-tag';
      tag.innerHTML = `
        ${skill}
        <button type="button" class="remove-skill" onclick="removeSkill('${skill}')">
          ×
        </button>
      `;
      skillsContainer.appendChild(tag);
    });
    skillsHidden.value = JSON.stringify(skills);
  }

  // Add skill events
  addSkillBtn.addEventListener('click', () => addSkill(skillsInput.value));
  skillsInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addSkill(skillsInput.value);
    }
  });

  // Step navigation
  nextToStep2.addEventListener("click", () => {
    if (!titleInput.value.trim()) {
      alert('Please enter an interview title');
      titleInput.focus();
      return;
    }
    
    step1.style.display = "none";
    step2.style.display = "block";
    updateStepIndicator(2);
  });

  nextToStep3.addEventListener("click", () => {
    step2.style.display = "none";
    step3.style.display = "block";
    updateStepIndicator(3);
    updatePreview();
  });

  backToStep1.addEventListener("click", () => {
    step2.style.display = "none";
    step1.style.display = "block";
    updateStepIndicator(1);
  });

  backToStep2.addEventListener("click", () => {
    step3.style.display = "none";
    step2.style.display = "block";
    updateStepIndicator(2);
  });

  // Status toggle
  statusToggle.addEventListener("change", () => {
    const isActive = statusToggle.checked;
    statusLabel.textContent = isActive ? 'Active' : 'Inactive';
    statusLabel.className = `status-badge ${isActive ? 'status-active' : 'status-inactive'} ms-2`;
  });

  // Update preview
  function updatePreview() {
    previewTitle.textContent = titleInput.value || 'Not provided';
    previewRole.textContent = document.getElementById("role").value || 'Not specified';
    previewCategory.textContent = document.getElementById("category").value || 'Not selected';
    previewDescription.textContent = descriptionInput.value || 'No description provided';

    // Update skills preview
    previewSkills.innerHTML = '';
    if (skills.length === 0) {
      previewSkills.innerHTML = '<span class="text-muted">No skills specified</span>';
    } else {
      skills.forEach(skill => {
        const skillTag = document.createElement('span');
        skillTag.className = 'skill-preview-tag';
        skillTag.textContent = skill;
        previewSkills.appendChild(skillTag);
      });
    }
  }

  // Update step indicator
  function updateStepIndicator(activeStep) {
    document.querySelectorAll('.step').forEach((step, index) => {
      const stepNumber = index + 1;
      step.classList.remove('active', 'completed');
      
      if (stepNumber === activeStep) {
        step.classList.add('active');
      } else if (stepNumber < activeStep) {
        step.classList.add('completed');
      }
    });
  }

  // Form submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const formData = {
      title: titleInput.value.trim(),
      role: document.getElementById("role").value.trim(),
      skills: skills,
      category: document.getElementById("category").value,
      description: descriptionInput.value.trim(),
      status: statusToggle.checked
    };

    // Validation
    if (!formData.title) {
      alert('Please enter an interview title');
      titleInput.focus();
      return;
    }

    try {
      const response = await fetch("/create-public-interview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        alert("✅ Public interview created successfully!");
        window.location.href = "/recruiter-public-interview"; // Redirect to dashboard
      } else {
        const error = await response.json();
        alert("❌ Error: " + (error.detail || "Failed to create interview"));
      }
    } catch (err) {
      console.error(err);
      alert("❌ Network error while creating interview.");
    }
  });

  // Make removeSkill function available globally
  window.removeSkill = removeSkill;
});