document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("editjob");

    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            // Grab jobId from URL or hidden input
            const jobId = document.getElementById("jobId").value

            const data = {
                user_id: parseInt(document.getElementById("userId").value),
                title: document.getElementById("jobTitle").value,
                company: document.getElementById("companyName").value,
                link: document.getElementById("jobLink").value,
                logo: document.getElementById("companyLogo").value,
                location: document.getElementById("location").value,
                salary: document.getElementById("salary").value,
                employment_type: document.getElementById("employmentType").value,
                seniority_level: document.getElementById("seniorityLevel").value,
                job_function: document.getElementById("jobFunction").value,
                industry: document.getElementById("industry").value,
                posted_on: document.getElementById("postedOn").value,
                description: document.getElementById("jobDescription").value,
                responsibilities: document.getElementById("responsibilities").value,
                requirements: document.getElementById("requirements").value,
                skills: document.getElementById("skillsData").value
                ? document.getElementById("skillsData").value.split(",")
                : [],
                source: document.getElementById("source").value
            };

            try {
                const response = await fetch(`/edit-job/${jobId}`, {
                    method: "PUT",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify(data),
                });
                console.log(response)

                if (response.redirected) {
                    window.location.href = response.url; // handle redirect
                } else {
                    const result = await response.json();
                    console.log(result);
                    alert(result.message || "Job updated!");
                }
            } catch (error) {
                console.error("Error:", error);
                alert("Something went wrong!");
            }
        });
    }
});


document.addEventListener("DOMContentLoaded", function () {
    let skillsString = "{{ job.skills }}";  
    let existingSkills = skillsString ? skillsString.split(",") : [];

    const skillsContainer = document.getElementById("skillsContainer");
    const skillsData = document.getElementById("skillsData");

    function addSkillTag(skill) {
        const tag = document.createElement("span");
        tag.className = "badge bg-primary me-2 mb-2";
        tag.textContent = skill.trim();

        const removeBtn = document.createElement("span");
        removeBtn.className = "ms-2";
        removeBtn.style.cursor = "pointer";
        removeBtn.innerHTML = "&times;";
        removeBtn.onclick = () => {
            tag.remove();
            updateHiddenField();
        };

        tag.appendChild(removeBtn);
        skillsContainer.appendChild(tag);
        updateHiddenField();
    }

    function updateHiddenField() {
        let allSkills = Array.from(skillsContainer.querySelectorAll("span.badge"))
                             .map(tag => tag.childNodes[0].nodeValue.trim()); 
        skillsData.value = allSkills.join(",");
    }

    if (existingSkills && existingSkills.length) {
        existingSkills.forEach(skill => {
            if (skill.trim()) addSkillTag(skill);
        });
    }
});

