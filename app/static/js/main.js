// Main JavaScript for CloudVault

document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Dark Mode Toggle
    const themeToggleBtn = document.getElementById('theme-toggle');
    const htmlElement = document.documentElement;
    const themeIcon = document.getElementById('theme-icon');

    // Check local storage or system preference
    const currentTheme = localStorage.getItem('theme');
    if (currentTheme) {
        htmlElement.setAttribute('data-bs-theme', currentTheme);
        updateThemeIcon(currentTheme);
    } else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        htmlElement.setAttribute('data-bs-theme', 'dark');
        updateThemeIcon('dark');
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const current = htmlElement.getAttribute('data-bs-theme');
            const target = current === 'dark' ? 'light' : 'dark';
            htmlElement.setAttribute('data-bs-theme', target);
            localStorage.setItem('theme', target);
            updateThemeIcon(target);
        });
    }

    function updateThemeIcon(theme) {
        if (!themeIcon) return;
        if (theme === 'dark') {
            themeIcon.classList.remove('bi-moon-fill');
            themeIcon.classList.add('bi-sun-fill');
            themeIcon.style.color = '#ffc107'; // Sun color
        } else {
            themeIcon.classList.remove('bi-sun-fill');
            themeIcon.classList.add('bi-moon-fill');
            themeIcon.style.color = '#6c757d';
        }
    }

    // 2. Instant Search Filter (DOM based)
    const searchInput = document.getElementById('instant-search');
    const cvCards = document.querySelectorAll('.cv-card[data-search-name]');

    if (searchInput && cvCards.length > 0) {
        searchInput.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            
            cvCards.forEach(card => {
                const name = card.getAttribute('data-search-name').toLowerCase();
                const titleEl = card.querySelector('.cv-card-title');
                const originalName = card.getAttribute('data-search-name');

                if (name.includes(term)) {
                    card.style.display = 'flex';
                    // Highlight text if term is not empty
                    if (term.length > 0) {
                        const regex = new RegExp(`(${term})`, "gi");
                        titleEl.innerHTML = originalName.replace(regex, "<span class='search-highlight'>$1</span>");
                    } else {
                        titleEl.innerHTML = originalName;
                    }
                } else {
                    card.style.display = 'none';
                }
            });
        });
    }

    // 3. Drag and Drop Upload via AJAX
    const dropzone = document.getElementById('upload-dropzone');
    const fileInput = document.getElementById('file-input');
    const uploadForm = document.getElementById('upload-form');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('upload-progress-bar');
    const uploadText = document.getElementById('upload-text');

    if (dropzone && fileInput && uploadForm) {
        
        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, preventDefaults, false);
            document.body.addEventListener(eventName, preventDefaults, false);
        });

        // Highlight dropzone when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            dropzone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropzone.addEventListener(eventName, unhighlight, false);
        });

        // Handle dropped files
        dropzone.addEventListener('drop', handleDrop, false);
        
        // Handle click to browse
        dropzone.addEventListener('click', () => {
            fileInput.click();
        });
        
        fileInput.addEventListener('change', () => {
            if(fileInput.files.length > 0) {
                handleFiles(fileInput.files);
            }
        });

        function preventDefaults (e) {
            e.preventDefault();
            e.stopPropagation();
        }

        function highlight(e) {
            dropzone.classList.add('dragover');
        }

        function unhighlight(e) {
            dropzone.classList.remove('dragover');
        }

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            handleFiles(files);
        }

        function handleFiles(files) {
            if (files.length > 0) {
                uploadFile(files[0]);
            }
        }

        function uploadFile(file) {
            // Transform dropzone into preview mode
            dropzone.style.display = 'none';
            progressContainer.className = 'upload-progress-wrapper';
            progressContainer.style.display = 'block';
            
            // Build the card preview
            let isImage = file.type.startsWith('image/');
            let thumbHtml = isImage 
                ? `<div class="saas-file-preview d-flex justify-content-center align-items-center bg-dark rounded-top-4 overflow-hidden" style="height: 160px;">
                     <img id="preview-img" class="w-100 h-100 object-fit-cover" src="" alt="preview">
                   </div>`
                : `<div class="saas-file-preview d-flex justify-content-center align-items-center bg-dark rounded-top-4" style="height: 160px;">
                     <i class="bi bi-file-earmark-text-fill text-secondary opacity-50" style="font-size: 4rem;"></i>
                   </div>`;
                   
            uploadText.innerHTML = `
                <div class="saas-file-card d-flex flex-column mb-3 text-start">
                    ${thumbHtml}
                    <div class="card-body p-3">
                        <h6 class="fw-bolder text-white text-truncate mb-1">${file.name}</h6>
                        <div class="text-white-50 small fw-medium">${(file.size / (1024*1024)).toFixed(2)} MB</div>
                    </div>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="text-white fw-bold" id="upload-status-text">Uploading...</span>
                    <span class="text-primary fw-bold" id="upload-percent">0%</span>
                </div>
            `;
            
            if (isImage) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const img = document.getElementById('preview-img');
                    if(img) img.src = e.target.result;
                }
                reader.readAsDataURL(file);
            }
            
            progressBar.style.width = '0%';
            progressBar.innerHTML = '';
            
            // Disable clicks
            dropzone.style.pointerEvents = 'none';
            
            const url = uploadForm.action;
            const formData = new FormData(uploadForm);
            
            // Replace the file in formData (in case it was dropped instead of clicked)
            formData.set('file', file);
            
            const xhr = new XMLHttpRequest();
            
            xhr.open('POST', url, true);
            
            // Update progress bar
            xhr.upload.addEventListener("progress", function (e) {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);
                    progressBar.style.width = percentComplete + '%';
                    const percentText = document.getElementById('upload-percent');
                    if (percentText) percentText.innerHTML = percentComplete + '%';
                }
            });
            
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 400) {
                    // Success! Redirect or reload (the backend redirects to dashboard)
                    progressBar.classList.add('bg-success');
                    const statusText = document.getElementById('upload-status-text');
                    const percentText = document.getElementById('upload-percent');
                    if (statusText) statusText.innerHTML = `<i class="bi bi-check-circle-fill text-success me-2"></i>Upload Successful`;
                    if (percentText) percentText.innerHTML = `100%`;
                    
                    // We must reload since the backend probably returned HTML or a redirect
                    // Wait a second for user to see success
                    setTimeout(() => {
                        window.location.href = uploadForm.dataset.redirectUrl || '/dashboard';
                    }, 800);
                } else {
                    // Error
                    progressBar.classList.add('bg-danger');
                    const statusText = document.getElementById('upload-status-text');
                    if (statusText) statusText.innerHTML = `<i class="bi bi-x-circle-fill text-danger me-2"></i>Failed (File may be too large)`;
                    dropzone.style.display = 'block';
                    dropzone.style.pointerEvents = 'auto';
                }
            };
            
            xhr.onerror = function() {
                progressBar.classList.add('bg-danger');
                const statusText = document.getElementById('upload-status-text');
                if (statusText) statusText.innerHTML = `<i class="bi bi-x-circle-fill text-danger me-2"></i>Network Error`;
                dropzone.style.display = 'block';
                dropzone.style.pointerEvents = 'auto';
            };
            
            xhr.send(formData);
        }
    }
});
