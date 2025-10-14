// static/js/dashboard.js
document.addEventListener("DOMContentLoaded", () => {
    const allJobs = document.querySelectorAll("#all-jobs .job-item");

    // Split jobs by source
    const linkedinJobs = Array.from(allJobs).filter(job => job.dataset.source === "linkedin");
    const rozeeJobs = Array.from(allJobs).filter(job => job.dataset.source === "rozee.pk");
    const userPosted = Array.from(allJobs).filter(job => job.dataset.source === "manual");

    setupPagination(
        linkedinJobs,
        "linkedin-jobs-container",
        "linkedin-pagination",
        "linkedin-prev",
        "linkedin-next",
        "linkedin-info",
        "linkedin-page-size",
        "linkedin-count"
    );

    setupPagination(
        rozeeJobs,
        "rozee-jobs-container",
        "rozee-pagination",
        "rozee-prev",
        "rozee-next",
        "rozee-info",
        "rozee-page-size",
        "rozee-count"
    );

    setupPagination(
        userPosted,
        "user-posted-jobs-container",
        "user-posted-pagination",
        "user-posted-prev",
        "user-posted-next",
        "user-posted-info",
        "user-posted-page-size",
        "user-posted-count"
    );
});

/**
 * Setup pagination for a job source
 */
function setupPagination(jobs, containerId, paginationId, prevBtnId, nextBtnId, infoId, pageSizeId, countBadgeId) {
    const container = document.getElementById(containerId);
    const pagination = document.getElementById(paginationId);
    const prevBtn = document.getElementById(prevBtnId);
    const nextBtn = document.getElementById(nextBtnId);
    const info = document.getElementById(infoId);
    const pageSizeSelect = document.getElementById(pageSizeId);
    const countBadge = document.getElementById(countBadgeId);

    let currentPage = 1;
    let pageSize = parseInt(pageSizeSelect.value);

    countBadge.textContent = jobs.length;

    function renderPage() {
        container.innerHTML = "";

        const start = (currentPage - 1) * pageSize;
        const end = start + pageSize;
        const paginatedJobs = jobs.slice(start, end);

        if (paginatedJobs.length === 0 && currentPage > 1) {
            currentPage--; // go back if last page is empty
            return renderPage();
        }

        paginatedJobs.forEach(job => container.appendChild(job.cloneNode(true)));

        const totalPages = Math.ceil(jobs.length / pageSize);
        info.textContent = `Page ${currentPage} of ${totalPages}`;

        prevBtn.disabled = currentPage === 1;
        nextBtn.disabled = currentPage === totalPages || totalPages === 0;

        pagination.style.display = jobs.length > 0 ? "flex" : "none";
    }

    prevBtn.addEventListener("click", () => {
        if (currentPage > 1) {
            currentPage--;
            renderPage();
        }
    });

    nextBtn.addEventListener("click", () => {
        const totalPages = Math.ceil(jobs.length / pageSize);
        if (currentPage < totalPages) {
            currentPage++;
            renderPage();
        }
    });

    pageSizeSelect.addEventListener("change", () => {
        pageSize = parseInt(pageSizeSelect.value);
        currentPage = 1;
        renderPage();
    });

    renderPage(); // Initial load
}
