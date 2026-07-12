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
            // Update UI to show progress
            uploadText.innerHTML = `Uploading <strong>${file.name}</strong>...`;
            progressContainer.style.display = 'block';
            progressBar.style.width = '0%';
            progressBar.innerHTML = '0%';
            
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
                    progressBar.innerHTML = percentComplete + '%';
                }
            });
            
            xhr.onload = function() {
                if (xhr.status >= 200 && xhr.status < 400) {
                    // Success! Redirect or reload (the backend redirects to dashboard)
                    progressBar.classList.add('bg-success');
                    progressBar.innerHTML = 'Complete!';
                    uploadText.innerHTML = `<i class="bi bi-check-circle-fill text-success"></i> Upload Successful! Redirecting...`;
                    
                    // We must reload since the backend probably returned HTML or a redirect
                    // Wait a second for user to see success
                    setTimeout(() => {
                        window.location.href = uploadForm.dataset.redirectUrl || '/dashboard';
                    }, 800);
                } else {
                    // Error
                    progressBar.classList.add('bg-danger');
                    progressBar.innerHTML = 'Error';
                    uploadText.innerHTML = `<span class="text-danger">Upload failed. File might be too large.</span>`;
                    dropzone.style.pointerEvents = 'auto';
                }
            };
            
            xhr.onerror = function() {
                progressBar.classList.add('bg-danger');
                progressBar.innerHTML = 'Error';
                uploadText.innerHTML = `<span class="text-danger">Network Error</span>`;
                dropzone.style.pointerEvents = 'auto';
            };
            
            xhr.send(formData);
        }
    }
});
