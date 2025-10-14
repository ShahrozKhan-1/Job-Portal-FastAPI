document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("addjob");
    const skillInput = document.getElementById("skillInput");
    const skillsContainer = document.getElementById("skillsContainer");
    const skillsData = document.getElementById("skillsData");


    let skills = [];

    // Add skills when pressing Enter
    skillInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            const skill = skillInput.value.trim();
            if (skill && !skills.includes(skill)) {
                skills.push(skill);
                updateSkillsUI();
                updateHiddenField();
                skillInput.value = "";
            }
        }
    });

    // Remove skill when clicking "x"
    function updateSkillsUI() {
        skillsContainer.innerHTML = "";
        skills.forEach((skill, index) => {
            const tag = document.createElement("span");
            tag.className = "badge bg-primary me-2 mb-2";
            tag.innerHTML = `${skill} <i class="fas fa-times ms-1" style="cursor:pointer"></i>`;
            tag.querySelector("i").addEventListener("click", () => {
                skills.splice(index, 1);
                updateSkillsUI();
                updateHiddenField();
            });
            skillsContainer.appendChild(tag);
        });
    }

    function updateHiddenField() {
        skillsData.value = JSON.stringify(skills);
    }

    // Handle form submit
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const formData = {
            title: document.getElementById("jobTitle")?.value || "",
            company: document.getElementById("companyName")?.value || "",
            link: document.getElementById("jobLink")?.value || "",
            logo: document.getElementById("companyLogo")?.value || "",
            location: document.getElementById("location")?.value || "",
            salary: document.getElementById("salary")?.value || "",
            employment_type: document.getElementById("employmentType")?.value || "",
            seniority_level: document.getElementById("seniorityLevel")?.value || "",
            job_function: document.getElementById("jobFunction")?.value || "",
            industry: document.getElementById("industry")?.value || "",
            posted_on: document.getElementById("postedOn")?.value || "",
            description: document.getElementById("jobDescription")?.value || "",
            responsibilities: document.getElementById("responsibilities")?.value || "",
            requirements: document.getElementById("requirements")?.value || "",
            skills: skills.length > 0 ? skills : [],
            source: "manual"
        };

        console.log("Submitting Job Data:", formData); 

        try {
            const response = await fetch("/add-job", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(formData)
            });

            console.log("Response Status:", response.status);

            if (response.ok) {
                const data = await response.json();
                alert("Job posted successfully!");
                window.location.href = "/dashboard";
            } else {
                const error = await response.json();
                console.error("Error Response:", error); 
                alert(" Error " + (error.msg || "Failed to add job"));
            }
        } catch (err) {
            alert("Something went wrong while posting the job.");
        }
    });
});
