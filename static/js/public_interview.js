document.addEventListener("DOMContentLoaded", function () {
    // Sample data - in real application, this would come from your API
    const interviews = [
        {
            id: 1,
            title: "Senior Frontend Developer Technical Assessment",
            description: "Comprehensive technical interview covering JavaScript, React, and modern frontend development practices.",
            category: "Technical",
            status: "open",
            questions_count: 8,
            attempts_count: 24,
            created_at: "2023-11-10",
            avg_score: 82
        },
        {
            id: 2,
            title: "Product Manager Behavioral Interview",
            description: "Behavioral questions focused on product thinking, stakeholder management, and decision-making processes.",
            category: "Behavioral",
            status: "open",
            questions_count: 6,
            attempts_count: 15,
            created_at: "2023-11-05",
            avg_score: 76
        },
        {
            id: 3,
            title: "Junior Developer Coding Test",
            description: "Basic programming concepts and problem-solving skills assessment for entry-level developers.",
            category: "Technical",
            status: "closed",
            questions_count: 5,
            attempts_count: 42,
            created_at: "2023-10-20",
            avg_score: 65
        },
        {
            id: 4,
            title: "Sales Executive Role Play",
            description: "Simulated sales scenarios and objection handling exercises for sales candidates.",
            category: "Sales",
            status: "open",
            questions_count: 7,
            attempts_count: 8,
            created_at: "2023-11-12",
            avg_score: 71
        },
        {
            id: 5,
            title: "Team Leadership Assessment",
            description: "Evaluation of leadership capabilities, team management, and conflict resolution skills.",
            category: "Management",
            status: "closed",
            questions_count: 9,
            attempts_count: 18,
            created_at: "2023-10-15",
            avg_score: 79
        }
    ];

    // DOM elements
    const interviewsList = document.getElementById('interviewsList');
    const emptyState = document.getElementById('emptyState');
    const searchInput = document.getElementById('searchInput');
    const applyFiltersBtn = document.getElementById('applyFilters');
    const totalInterviews = document.getElementById('totalInterviews');
    const activeInterviews = document.getElementById('activeInterviews');
    const totalAttempts = document.getElementById('totalAttempts');
    const avgScore = document.getElementById('avgScore');

    // Initialize statistics
    function updateStatistics() {
        const activeCount = interviews.filter(i => i.status === 'open').length;
        const totalAttemptsCount = interviews.reduce((sum, i) => sum + i.attempts_count, 0);
        const averageScore = interviews.reduce((sum, i) => sum + i.avg_score, 0) / interviews.length;
        
        totalInterviews.textContent = interviews.length;
        activeInterviews.textContent = activeCount;
        totalAttempts.textContent = totalAttemptsCount;
        avgScore.textContent = Math.round(averageScore) + '%';
    }

    // Render interviews
    function renderInterviews(interviewsToRender) {
        if (interviewsToRender.length === 0) {
            interviewsList.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }

        interviewsList.style.display = 'block';
        emptyState.style.display = 'none';

        const interviewsHTML = interviewsToRender.map(interview => `
            <div class="col-12">
                <div class="card card-custom interview-card ${interview.status === 'closed' ? 'closed' : ''}">
                    <div class="card-body">
                        <div class="row align-items-center">
                            <div class="col-md-8">
                                <div class="d-flex align-items-center mb-2">
                                    <h5 class="card-title mb-0 me-3">${interview.title}</h5>
                                    <span class="status-badge status-${interview.status}">
                                        ${interview.status === 'open' ? 'Open' : 'Closed'}
                                    </span>
                                </div>
                                <p class="card-text text-muted mb-2">${interview.description}</p>
                                <div class="d-flex align-items-center">
                                    <span class="category-badge me-2">${interview.category}</span>
                                    <small class="text-muted me-3">
                                        <i class="fas fa-question-circle me-1"></i>${interview.questions_count} questions
                                    </small>
                                    <small class="text-muted me-3">
                                        <i class="fas fa-users me-1"></i>${interview.attempts_count} attempts
                                    </small>
                                    <small class="text-muted">
                                        <i class="fas fa-clock me-1"></i>Created ${formatDate(interview.created_at)}
                                    </small>
                                </div>
                            </div>
                            <div class="col-md-4 text-md-end">
                                <div class="action-buttons mt-3 mt-md-0">
                                    <button class="btn btn-outline-primary-custom btn-sm" onclick="viewInterview(${interview.id})">
                                        <i class="fas fa-eye me-1"></i>View
                                    </button>
                                    <button class="btn btn-outline-secondary btn-sm" onclick="viewAnalytics(${interview.id})">
                                        <i class="fas fa-chart-bar me-1"></i>Analytics
                                    </button>
                                    ${interview.status === 'open' ? 
                                        `<button class="btn btn-outline-danger btn-sm" onclick="closeInterview(${interview.id})">
                                            <i class="fas fa-times me-1"></i>Close
                                        </button>` :
                                        `<button class="btn btn-outline-success btn-sm" onclick="reopenInterview(${interview.id})">
                                            <i class="fas fa-play me-1"></i>Reopen
                                        </button>`
                                    }
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        interviewsList.innerHTML = `<div class="row">${interviewsHTML}</div>`;
    }

    // Format date relative to now
    function formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffTime = Math.abs(now - date);
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        if (diffDays === 1) return 'yesterday';
        if (diffDays < 7) return `${diffDays} days ago`;
        if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
        return `${Math.floor(diffDays / 30)} months ago`;
    }

    // Filter and search functionality
    function filterInterviews() {
        const searchTerm = searchInput.value.toLowerCase();
        const statusOpen = document.getElementById('filterOpen').checked;
        const statusClosed = document.getElementById('filterClosed').checked;
        const categoryTechnical = document.getElementById('filterTechnical').checked;
        const categoryBehavioral = document.getElementById('filterBehavioral').checked;
        const categoryManagement = document.getElementById('filterManagement').checked;

        const filtered = interviews.filter(interview => {
            const matchesSearch = interview.title.toLowerCase().includes(searchTerm) || 
                                    interview.description.toLowerCase().includes(searchTerm);
            
            const matchesStatus = (interview.status === 'open' && statusOpen) || 
                                    (interview.status === 'closed' && statusClosed);
            
            const matchesCategory = (interview.category === 'Technical' && categoryTechnical) ||
                                    (interview.category === 'Behavioral' && categoryBehavioral) ||
                                    (interview.category === 'Management' && categoryManagement) ||
                                    (!['Technical', 'Behavioral', 'Management'].includes(interview.category));
            
            return matchesSearch && matchesStatus && matchesCategory;
        });

        renderInterviews(filtered);
    }

    // Event listeners
    searchInput.addEventListener('input', filterInterviews);
    applyFiltersBtn.addEventListener('click', filterInterviews);

    // Action functions
    window.viewInterview = function(id) {
        alert(`View interview ${id}`);
        // In real app: window.location.href = `/interview/${id}`;
    };

    window.viewAnalytics = function(id) {
        alert(`View analytics for interview ${id}`);
        // In real app: window.location.href = `/interview/${id}/analytics`;
    };

    window.closeInterview = function(id) {
        if (confirm('Are you sure you want to close this interview? New attempts will not be allowed.')) {
            alert(`Interview ${id} closed`);
            // In real app: API call to update status
        }
    };

    window.reopenInterview = function(id) {
        alert(`Interview ${id} reopened`);
        // In real app: API call to update status
    };

    // Initialize
    updateStatistics();
    renderInterviews(interviews);
});

document.addEventListener("DOMContentLoaded", () => {
  const modal = new bootstrap.Modal(document.getElementById("resumeUploadModal"));
  const resumeForm = document.getElementById("resumeUploadForm");
  const resumeInput = document.getElementById("resumeFile");
  const selectedInterviewInput = document.getElementById("selectedInterviewId");

  // When user clicks "Start Interview"
  document.querySelectorAll(".start-interview-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const interviewId = btn.getAttribute("data-interview-id");
      selectedInterviewInput.value = interviewId;
      resumeInput.value = ""; // reset previous file
      modal.show();
    });
  });

  // On resume upload form submit
  resumeForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const interviewId = selectedInterviewInput.value;
    const file = resumeInput.files[0];
    if (!file) {
      alert("Please select a resume file.");
      return;
    }

    const formData = new FormData();
    formData.append("resume", file);
    formData.append("interview_id", interviewId);

    try {
      const response = await fetch(`/upload-resume/${interviewId}`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Failed to upload resume.");
      }

      const data = await response.json();

      // Redirect to public interview chat page
      window.location.href = `/public-interview/start/${interviewId}?attempt_id=${data.attempt_id}`;

    } catch (error) {
      alert("Error uploading resume: " + error.message);
    }
  });
});
