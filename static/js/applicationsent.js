document.addEventListener("DOMContentLoaded", () => {
    // Countdown Logic
    const buttons = document.querySelectorAll(".interview-btn");

    buttons.forEach(btn => {
        const interviewTime = new Date(btn.dataset.interviewTime);
        const countdownText = btn.parentElement.querySelector(".countdown-text");

        function updateCountdown() {
            const now = new Date();
            const interviewEnd = new Date(interviewTime.getTime() + 60 * 60 * 1000); // +1 hour

            if (now < interviewTime) {
                // Before interview
                const diff = interviewTime - now;
                const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                
                if (days > 0) {
                    countdownText.textContent = `Interview starts in ${days} day${days !== 1 ? 's' : ''}`;
                } else if (hours > 0) {
                    countdownText.textContent = `Interview starts in ${hours} hour${hours !== 1 ? 's' : ''}`;
                } else {
                    countdownText.textContent = `Interview starts in ${mins} minute${mins !== 1 ? 's' : ''}`;
                }
                
                btn.style.display = "none";
            } else if (now >= interviewTime && now <= interviewEnd) {
                // During interview
                countdownText.textContent = "Interview is open - Join now!";
                btn.style.display = "inline-block";
            } else {
                // After interview
                countdownText.textContent = "Interview ended";
                btn.style.display = "none";
            }
        }

        updateCountdown();
        setInterval(updateCountdown, 30000); // Update every 30 sec
    });

    // Filter functionality
    const filterLinks = document.querySelectorAll('.filter-tabs .nav-link');
    const jobCards = document.querySelectorAll('.job-card');

    filterLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            
            // Update active state
            filterLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            const filter = link.dataset.filter;
            
            // Filter job cards
            jobCards.forEach(card => {
                if (filter === 'all' || card.dataset.status === filter) {
                    card.style.display = 'block';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });

    // Animate progress bars on scroll
    const progressBars = document.querySelectorAll('.progress-fill');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const width = entry.target.style.width;
                entry.target.style.width = '0%';
                setTimeout(() => {
                    entry.target.style.width = width;
                }, 300);
            }
        });
    }, { threshold: 0.5 });
    
    progressBars.forEach(bar => {
        observer.observe(bar);
    });
});