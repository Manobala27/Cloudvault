// Main JavaScript for CloudVault
console.log("1. main.js loaded");

document.addEventListener('DOMContentLoaded', () => {
    console.log("2. DOMContentLoaded fired");
    
    // Initialize tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
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
    
    console.log("3. uploadForm found:", !!uploadForm);
    console.log("4. fileInput found:", !!fileInput);

    if (dropzone && fileInput && uploadForm) {
        console.log("6. change listener attached to fileInput");
        
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
        
        fileInput.addEventListener('change', function() {
            console.log("8. file input change event fired! Files:", this.files);
            handleFiles(this.files);
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
            console.log("9. handleFiles() entered with files:", files);
            if (files.length > 0) {
                uploadFile(files[0]);
            }
        }

        function uploadFile(file) {
            console.log("uploadFile entered BEFORE");
            console.log("10. uploadFile() entered for file:", file.name);
            console.log("uploadFile entered AFTER");
            const queueContainer = document.getElementById('upload-queue-container');
            const queueList = document.getElementById('upload-queue-list');
            const emptyState = document.getElementById('upload-empty-state');
            
            // Show queue, hide empty state
            if(queueContainer) queueContainer.style.display = 'block';
            if(emptyState) emptyState.style.display = 'none';
            
            const fileId = 'upload-' + Math.random().toString(36).substr(2, 9);
            const isImage = file.type.startsWith('image/');
            const iconHtml = isImage 
                ? `<i class="bi bi-image text-primary fs-3"></i>`
                : `<i class="bi bi-file-earmark-text-fill text-secondary fs-3"></i>`;
                
            const queueItemHtml = `
                <div id="${fileId}" class="saas-folder-card p-3 rounded-4 d-flex flex-column gap-2" style="height: auto !important; border: 1px solid var(--cv-surface-border);">
                    <div class="d-flex align-items-center justify-content-between">
                        <div class="d-flex align-items-center gap-3 overflow-hidden">
                            <div class="bg-dark rounded-3 d-flex align-items-center justify-content-center flex-shrink-0" style="width: 48px; height: 48px;">
                                ${iconHtml}
                            </div>
                            <div class="text-truncate">
                                <h6 class="text-white mb-1 fw-bold text-truncate" title="${file.name}">${file.name}</h6>
                                <div class="small text-white-50 d-flex gap-2">
                                    <span>${(file.size / (1024*1024)).toFixed(2)} MB</span>
                                    <span class="text-white-50">&bull;</span>
                                    <span id="status-${fileId}" class="text-info fw-medium">Uploading...</span>
                                </div>
                            </div>
                        </div>
                        <div class="d-flex align-items-center gap-3 flex-shrink-0">
                            <span id="percent-${fileId}" class="text-white fw-bold">0%</span>
                            <button type="button" class="btn btn-sm btn-outline-danger rounded-circle p-1" style="width: 32px; height: 32px;" title="Cancel Upload" id="cancel-${fileId}">
                                <i class="bi bi-x-lg"></i>
                            </button>
                        </div>
                    </div>
                    <div class="progress rounded-pill bg-dark mt-2" style="height: 6px;">
                        <div id="progress-${fileId}" class="progress-bar progress-bar-striped progress-bar-animated bg-primary" role="progressbar" style="width: 0%;"></div>
                    </div>
                </div>
            `;
            
            if (queueList) {
                queueList.insertAdjacentHTML('afterbegin', queueItemHtml);
                console.log("11. queue HTML inserted into queueList");
            } else {
                console.log("FAILED: queueList is null, cannot insert HTML");
            }
            console.log("queue created AFTER");
            
            const progressBar = document.getElementById(`progress-${fileId}`);
            const percentText = document.getElementById(`percent-${fileId}`);
            const statusText = document.getElementById(`status-${fileId}`);
            const cancelBtn = document.getElementById(`cancel-${fileId}`);
            
            if (!uploadForm) return; // Prevent upload if form is missing
            
            console.log("FormData created BEFORE");
            const url = uploadForm.action;
            const formData = new FormData(uploadForm);
            formData.set('file', file);
            console.log("12. FormData created");
            console.log("FormData created AFTER");
            
            console.log("xhr created BEFORE");
            const xhr = new XMLHttpRequest();
            console.log("13. xhr created");
            console.log("xhr created AFTER");
            
            if (cancelBtn) {
                cancelBtn.addEventListener('click', () => {
                    xhr.abort();
                    if (progressBar) progressBar.classList.replace('bg-primary', 'bg-danger');
                    if (statusText) {
                        statusText.className = 'text-danger fw-medium';
                        statusText.innerHTML = 'Cancelled';
                    }
                    cancelBtn.style.display = 'none';
                });
            }
            
            console.log("xhr.open BEFORE");
            xhr.open('POST', url, true);
            console.log("14. xhr.open called");
            console.log("xhr.open AFTER");
            
            console.log("xhr headers set BEFORE");
            xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
            console.log("xhr headers set AFTER");
            
            let startTime = Date.now();
            let lastLoaded = 0;
            
            xhr.upload.addEventListener("progress", function (e) {
                if (e.lengthComputable) {
                    const percentComplete = Math.round((e.loaded / e.total) * 100);
                    if (progressBar) progressBar.style.width = percentComplete + '%';
                    if (percentText) percentText.innerHTML = percentComplete + '%';
                    
                    const currentTime = Date.now();
                    if (currentTime - startTime > 1000) {
                        const bytesPerSec = (e.loaded - lastLoaded) / ((currentTime - startTime) / 1000);
                        const mbPerSec = (bytesPerSec / (1024 * 1024)).toFixed(1);
                        if (statusText && statusText.innerHTML !== 'Cancelled') {
                            statusText.innerHTML = `Uploading (${mbPerSec} MB/s)`;
                        }
                        startTime = currentTime;
                        lastLoaded = e.loaded;
                    }
                }
            });
            
            xhr.onload = function() {
                console.log("xhr.onload BEFORE");
                if (cancelBtn) cancelBtn.style.display = 'none';
                if (xhr.status >= 200 && xhr.status < 400) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        if (response.success === true) {
                            if (progressBar) {
                                progressBar.classList.replace('bg-primary', 'bg-success');
                                progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');
                            }
                            if (statusText) {
                                statusText.className = 'text-success fw-bold';
                                statusText.innerHTML = `<i class="bi bi-check-circle-fill me-1"></i>Completed`;
                            }
                            if (percentText) percentText.innerHTML = `100%`;
                            
                            setTimeout(() => {
                                window.location.href = response.redirect || uploadForm.dataset.redirectUrl || '/dashboard';
                            }, 1000);
                        } else {
                            throw new Error(response.message || 'Upload failed');
                        }
                    } catch (e) {
                        if (progressBar) progressBar.classList.replace('bg-primary', 'bg-danger');
                        if (statusText) {
                            statusText.className = 'text-danger fw-bold';
                            statusText.innerHTML = `<i class="bi bi-x-circle-fill me-1"></i>Failed`;
                        }
                    }
                } else {
                    if (progressBar) progressBar.classList.replace('bg-primary', 'bg-danger');
                    if (statusText) {
                        statusText.className = 'text-danger fw-bold';
                        statusText.innerHTML = `<i class="bi bi-x-circle-fill me-1"></i>Failed`;
                    }
                }
                console.log("xhr.onload AFTER");
            };
            
            xhr.onerror = function() {
                console.log("xhr.onerror BEFORE");
                if (progressBar) progressBar.classList.replace('bg-primary', 'bg-danger');
                if (statusText) {
                    statusText.className = 'text-danger fw-bold';
                    statusText.innerHTML = `<i class="bi bi-x-circle-fill me-1"></i>Network Error`;
                }
                console.log("xhr.onerror AFTER");
            };
            
            xhr.onabort = function() {
                console.log("xhr.onabort BEFORE");
                console.log("Upload aborted by user or script");
                console.log("xhr.onabort AFTER");
            };
            
            console.log("xhr.send called BEFORE");
            console.log("15. xhr.send called");
            xhr.send(formData);
            console.log("xhr.send called AFTER");
        }
    }
});
