// File upload handling
const fileInput = document.getElementById('resume');
const fileUploadArea = document.querySelector('.file-upload-area');
const fileName = document.getElementById('fileName');

fileInput.addEventListener('change', function(e) {
if (e.target.files.length > 0) {
    const file = e.target.files[0];
    fileName.innerHTML = `<i class="fas fa-file-pdf me-2"></i>Selected: ${file.name}`;
    fileName.style.display = 'block';
    fileUploadArea.style.borderColor = '#10b981';
    fileUploadArea.style.background = 'rgba(16, 185, 129, 0.1)';
}
});

// Drag and drop functionality
fileUploadArea.addEventListener('dragover', function(e) {
e.preventDefault();
fileUploadArea.classList.add('dragover');
});

fileUploadArea.addEventListener('dragleave', function(e) {
e.preventDefault();
fileUploadArea.classList.remove('dragover');
});

fileUploadArea.addEventListener('drop', function(e) {
e.preventDefault();
fileUploadArea.classList.remove('dragover');

const files = e.dataTransfer.files;
if (files.length > 0) {
    fileInput.files = files;
    const file = files[0];
    fileName.innerHTML = `<i class="fas fa-file-pdf me-2"></i>Selected: ${file.name}`;
    fileName.style.display = 'block';
    fileUploadArea.style.borderColor = '#10b981';
    fileUploadArea.style.background = 'rgba(16, 185, 129, 0.1)';
}
});



