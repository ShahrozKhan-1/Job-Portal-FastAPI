// Show username edit form
function editUsername() {
    document.getElementById('username-form').style.display = 'block';
    document.getElementById('new-username').value = document.getElementById('current-username').textContent.trim();
}

// Cancel editing username
function cancelEdit() {
    document.getElementById('username-form').style.display = 'none';
}

// Save new username (send to backend)
function saveUsername() {
    const newUsername = document.getElementById('new-username').value.trim();

    if (!newUsername) {
        alert("Username cannot be empty!");
        return;
    }

    fetch('/profile', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name: newUsername })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            document.getElementById('current-username').textContent = data.user.name;
            document.getElementById('username-form').style.display = 'none';
            alert(data.success);
        } else {
            alert(data.error || "Something went wrong!");
        }
    })
    .catch(err => {
        console.error("Error updating username:", err);
        alert("Failed to update username. Try again!");
    });
}



// Handle password update form
document.getElementById('password-form').addEventListener('submit', function(e) {
    e.preventDefault();

    const currentPassword = document.getElementById('current-password').value.trim();
    const newPassword = document.getElementById('new-password').value.trim();
    const confirmPassword = document.getElementById('confirm-password').value.trim();

    if (newPassword !== confirmPassword) {
        alert("New passwords do not match!");
        return;
    }

    if (newPassword.length < 8 || newPassword.length > 12) {
        alert("Password must be between 8 and 12 characters!");
        return;
    }

    fetch('/profile', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ new_password: newPassword, current_password:currentPassword })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.success);
            document.getElementById('password-form').reset();
        } else {
            alert(data.error || "Something went wrong!");
        }
    })
    .catch(err => {
        console.error("Error updating password:", err);
        alert("Failed to update password. Try again!");
    });
});
