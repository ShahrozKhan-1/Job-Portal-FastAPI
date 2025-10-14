function removeSavedJob(button) {
    if (confirm('Are you sure you want to remove this job from your saved list?')) {
        const jobCard = button.closest('.job-card');
        jobCard.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        jobCard.style.opacity = '0';
        jobCard.style.transform = 'translateX(-100px)';
        
        setTimeout(() => {
            jobCard.remove();
            updateStats();
        }, 300);
    }
}

function updateStats() {
    const totalSaved = document.querySelectorAll('.job-card').length;
    document.querySelector('.stats-card h4').textContent = totalSaved;
}

// Search functionality
document.querySelector('.search-box').addEventListener('input', function(e) {
    const searchTerm = e.target.value.toLowerCase();
    const jobCards = document.querySelectorAll('.job-card');
    
    jobCards.forEach(card => {
        const jobTitle = card.querySelector('h5').textContent.toLowerCase();
        const company = card.querySelector('.text-muted').textContent.toLowerCase();
        
        if (jobTitle.includes(searchTerm) || company.includes(searchTerm)) {
            card.style.display = 'block';
        } else {
            card.style.display = 'none';
        }
    });
});

// Apply button functionality
document.querySelectorAll('.btn-primary').forEach(button => {
    if (button.textContent.includes('Apply Now')) {
        button.addEventListener('click', function() {
            window.location.href = 'apply-job.html';
        });
    }
});
