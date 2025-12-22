// Jane PDF Renamer - Frontend JavaScript

// Format selection
const formatOptions = document.querySelectorAll('.format-option');
let selectedFormat = 'appt_billing';

formatOptions.forEach(option => {
    option.addEventListener('click', () => {
        formatOptions.forEach(o => o.classList.remove('selected'));
        option.classList.add('selected');
        option.querySelector('input').checked = true;
        selectedFormat = option.dataset.format;
    });
});

// Drop zone functionality
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');
const loading = document.getElementById('loading');
const resultsCard = document.getElementById('results-card');
const resultsList = document.getElementById('results-list');
const reviewForm = document.getElementById('review-form');

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    handleFiles(files);
});

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

async function handleFiles(files) {
    loading.classList.add('visible');
    resultsCard.style.display = 'none';
    resultsList.innerHTML = '';
    reviewForm.classList.remove('visible');
    
    const outputFolder = document.getElementById('output-folder').value;
    const loadingProgress = document.getElementById('loading-progress');
    const totalFiles = files.length;
    
    // Update loading text based on count
    const loadingText = document.getElementById('loading-text');
    if (totalFiles === 1) {
        loadingText.textContent = 'Processing PDF...';
        loadingProgress.textContent = '';
    } else {
        loadingText.textContent = `Processing ${totalFiles} PDFs...`;
    }
    
    let processedCount = 0;
    
    for (const file of files) {
        processedCount++;
        
        // Update progress for batch processing
        if (totalFiles > 1) {
            loadingProgress.textContent = `File ${processedCount} of ${totalFiles}`;
        }
        
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            addResult({
                success: false,
                original_name: file.name,
                error: 'Not a PDF file'
            });
            continue;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('format_type', selectedFormat);
        formData.append('output_folder', outputFolder);
        
        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });
            const result = await response.json();
            
            if (result.needs_review) {
                showReviewForm(result);
            } else {
                addResult(result);
            }
        } catch (error) {
            addResult({
                success: false,
                original_name: file.name,
                error: error.message
            });
        }
    }
    
    loading.classList.remove('visible');
    if (resultsList.children.length > 0) {
        resultsCard.style.display = 'block';
    }
}

function addResult(result) {
    const item = document.createElement('div');
    item.className = `result-item ${result.success ? 'success' : 'error'}`;
    
    let pathHtml = '';
    if (result.new_path) {
        pathHtml = `<div class="result-path">📁 ${result.new_path}</div>`;
    }
    
    item.innerHTML = `
        <span class="result-icon">${result.success ? '✅' : '❌'}</span>
        <div class="result-info">
            <div class="result-original">${result.original_name}</div>
            <div class="result-new">${result.success ? result.new_name : result.error}</div>
            ${pathHtml}
        </div>
    `;
    
    resultsList.appendChild(item);
    resultsCard.style.display = 'block';
}

function showReviewForm(result) {
    reviewForm.classList.add('visible');
    document.getElementById('review-filename').value = result.original_name;
    document.getElementById('review-first').value = result.first_name || '';
    document.getElementById('review-last').value = result.last_name || '';
    document.getElementById('review-date').value = result.date_str || '';
}

document.getElementById('review-submit').addEventListener('click', async () => {
    const formData = new FormData();
    formData.append('filename', document.getElementById('review-filename').value);
    formData.append('first_name', document.getElementById('review-first').value);
    formData.append('last_name', document.getElementById('review-last').value);
    formData.append('date_str', document.getElementById('review-date').value);
    formData.append('format_type', selectedFormat);
    formData.append('output_folder', document.getElementById('output-folder').value);
    
    try {
        const response = await fetch('/rename-manual', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        addResult(result);
        reviewForm.classList.remove('visible');
    } catch (error) {
        addResult({
            success: false,
            original_name: document.getElementById('review-filename').value,
            error: error.message
        });
    }
});

// Folder picker functionality
const btnBrowse = document.getElementById('btn-browse');
const folderInput = document.getElementById('output-folder');
const folderName = document.getElementById('folder-name');
const folderHint = document.getElementById('folder-hint');

// Store the directory handle for later use
let selectedDirHandle = null;

// Check if File System Access API is available
const hasFileSystemAccess = 'showDirectoryPicker' in window;

if (!hasFileSystemAccess) {
    // Fallback: show text input instead
    const folderDisplay = document.getElementById('folder-display');
    folderDisplay.innerHTML = `<input type="text" id="output-folder-text" value="${folderInput.value}" 
        style="flex:1; background:transparent; border:none; color:var(--text-primary); 
        font-family:'Space Mono',monospace; font-size:0.85rem;"
        placeholder="Enter folder path...">`;
    
    document.getElementById('output-folder-text').addEventListener('input', (e) => {
        folderInput.value = e.target.value;
    });
    
    btnBrowse.style.display = 'none';
    folderHint.textContent = 'Enter the full path to your output folder.';
}

btnBrowse.addEventListener('click', async () => {
    if (!hasFileSystemAccess) return;
    
    try {
        // Request directory access
        selectedDirHandle = await window.showDirectoryPicker({
            id: 'jane-pdf-output',
            mode: 'readwrite',
            startIn: 'downloads'
        });
        
        // Update display
        folderName.textContent = selectedDirHandle.name;
        folderName.classList.remove('placeholder');
        
        // Store the path (we'll need to resolve it on the server side)
        folderInput.value = selectedDirHandle.name;
        
        folderHint.innerHTML = `<span style="color: var(--accent-primary);">✓</span> Folder selected: <strong>${selectedDirHandle.name}</strong>`;
        
        // Store handle globally so we can write to it later
        window.selectedOutputDir = selectedDirHandle;
        
    } catch (err) {
        if (err.name !== 'AbortError') {
            console.error('Error selecting folder:', err);
            folderHint.textContent = 'Could not select folder. Please try again.';
        }
    }
});

// Override file handling to use selected directory when available
const originalHandleFiles = handleFiles;
handleFiles = async function(files) {
    // If we have a directory handle, we need to handle files differently
    if (window.selectedOutputDir) {
        loading.classList.add('visible');
        resultsCard.style.display = 'none';
        resultsList.innerHTML = '';
        reviewForm.classList.remove('visible');
        
        const loadingProgress = document.getElementById('loading-progress');
        const totalFiles = files.length;
        const loadingText = document.getElementById('loading-text');
        
        if (totalFiles === 1) {
            loadingText.textContent = 'Processing PDF...';
            loadingProgress.textContent = '';
        } else {
            loadingText.textContent = `Processing ${totalFiles} PDFs...`;
        }
        
        let processedCount = 0;
        
        for (const file of files) {
            processedCount++;
            
            if (totalFiles > 1) {
                loadingProgress.textContent = `File ${processedCount} of ${totalFiles}`;
            }
            
            if (!file.name.toLowerCase().endsWith('.pdf')) {
                addResult({
                    success: false,
                    original_name: file.name,
                    error: 'Not a PDF file'
                });
                continue;
            }
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('format_type', selectedFormat);
            formData.append('output_folder', '');  // Process without output folder first
            
            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                
                if (result.needs_review) {
                    showReviewForm(result);
                } else if (result.success) {
                    // Now write the file to the selected directory
                    try {
                        const tempResponse = await fetch(`/download/${encodeURIComponent(result.new_name)}`);
                        if (tempResponse.ok) {
                            const fileBlob = await tempResponse.blob();
                            const fileHandle = await window.selectedOutputDir.getFileHandle(result.new_name, { create: true });
                            const writable = await fileHandle.createWritable();
                            await writable.write(fileBlob);
                            await writable.close();
                            
                            result.new_path = `${window.selectedOutputDir.name}/${result.new_name}`;
                        }
                    } catch (writeErr) {
                        console.error('Error writing to selected folder:', writeErr);
                    }
                    addResult(result);
                } else {
                    addResult(result);
                }
            } catch (error) {
                addResult({
                    success: false,
                    original_name: file.name,
                    error: error.message
                });
            }
        }
        
        loading.classList.remove('visible');
        if (resultsList.children.length > 0) {
            resultsCard.style.display = 'block';
        }
    } else {
        // Use original behavior with server-side path
        await originalHandleFiles(files);
    }
};

