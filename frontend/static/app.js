// API Base URL
const API_BASE = '';

// DOM Elements
const uploadForm = document.getElementById('uploadForm');
const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('file');
const fileDropZone = document.getElementById('fileDropZone');
const filePreview = document.getElementById('filePreview');
const fileName = document.getElementById('fileName');
const fileRemove = document.getElementById('fileRemove');
const progressBar = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');
const resultsSection = document.getElementById('resultsSection');
const resultsContent = document.getElementById('resultsContent');
const projectsList = document.getElementById('projectsList');
const actionItemsList = document.getElementById('actionItemsList');
const projectFilter = document.getElementById('projectFilter');
const statusFilter = document.getElementById('statusFilter');
const refreshProjectsBtn = document.getElementById('refreshProjects');
const refreshActionItemsBtn = document.getElementById('refreshActionItems');
const closeResultsBtn = document.getElementById('closeResults');

// Teams URL form elements
const teamsUrlForm = document.getElementById('teamsUrlForm');
const teamsUrlBtn = document.getElementById('teamsUrlBtn');
const teamsUrlInput = document.getElementById('teamsUrl');
const toggleFileUpload = document.getElementById('toggleFileUpload');
const toggleTeamsUrl = document.getElementById('toggleTeamsUrl');

// Navigation
const navItems = document.querySelectorAll('.nav-item');
const sections = {
    upload: document.getElementById('uploadSection'),
    projects: document.getElementById('projectsSection'),
    'action-items': document.getElementById('actionItemsSection'),
    results: resultsSection
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeNavigation();
    initializeFileUpload();
    initializeTeamsUrlForm();
    initializeInputTypeToggle();
    initializeEventListeners();
    loadProjects();  // This will call updateProjectDropdown with actual projects
    loadActionItems();
});

// Navigation
function initializeNavigation() {
    navItems.forEach(item => {
        item.addEventListener('click', () => {
            const section = item.dataset.section;
            switchSection(section);
            
            // Update active state
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function switchSection(sectionName) {
    Object.values(sections).forEach(section => {
        if (section) {
            section.classList.remove('active');
        }
    });
    
    if (sections[sectionName]) {
        sections[sectionName].classList.add('active');
    }
}

// File Upload with Drag & Drop
function initializeFileUpload() {
    // Click to browse
    fileDropZone.addEventListener('click', () => {
        if (!filePreview.style.display || filePreview.style.display === 'none') {
            fileInput.click();
        }
    });

    // File input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files[0]) {
            showFilePreview(e.target.files[0]);
        }
    });

    // Drag and drop
    fileDropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        fileDropZone.classList.add('dragover');
    });

    fileDropZone.addEventListener('dragleave', () => {
        fileDropZone.classList.remove('dragover');
    });

    fileDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        fileDropZone.classList.remove('dragover');
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            fileInput.files = files;
            showFilePreview(files[0]);
        }
    });

    // Remove file
    fileRemove.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.value = '';
        filePreview.style.display = 'none';
        fileDropZone.querySelector('.drop-zone-content').style.display = 'block';
    });
}

function showFilePreview(file) {
    fileName.textContent = file.name;
    filePreview.style.display = 'flex';
    fileDropZone.querySelector('.drop-zone-content').style.display = 'none';
}

// Input Type Toggle
function initializeInputTypeToggle() {
    if (toggleFileUpload && toggleTeamsUrl) {
        toggleFileUpload.addEventListener('click', () => {
            uploadForm.style.display = 'block';
            teamsUrlForm.style.display = 'none';
            toggleFileUpload.classList.add('active');
            toggleTeamsUrl.classList.remove('active');
            toggleFileUpload.style.background = 'var(--primary, #007bff)';
            toggleFileUpload.style.color = 'white';
            toggleFileUpload.style.borderColor = 'var(--primary, #007bff)';
            toggleTeamsUrl.style.background = 'var(--bg-primary, white)';
            toggleTeamsUrl.style.color = 'var(--text-primary, #333)';
            toggleTeamsUrl.style.borderColor = 'var(--border, #ddd)';
        });
        
        toggleTeamsUrl.addEventListener('click', () => {
            uploadForm.style.display = 'none';
            teamsUrlForm.style.display = 'block';
            toggleTeamsUrl.classList.add('active');
            toggleFileUpload.classList.remove('active');
            toggleTeamsUrl.style.background = 'var(--primary, #007bff)';
            toggleTeamsUrl.style.color = 'white';
            toggleTeamsUrl.style.borderColor = 'var(--primary, #007bff)';
            toggleFileUpload.style.background = 'var(--bg-primary, white)';
            toggleFileUpload.style.color = 'var(--text-primary, #333)';
            toggleFileUpload.style.borderColor = 'var(--border, #ddd)';
            
            // Sync project dropdown
            const projectSelect = document.getElementById('projectName');
            const teamsProjectSelect = document.getElementById('teamsProjectName');
            if (projectSelect && teamsProjectSelect) {
                teamsProjectSelect.innerHTML = projectSelect.innerHTML;
            }
        });
    }
}

// Teams URL Form Initialization
function initializeTeamsUrlForm() {
    // Teams URL form automatically uses SharePoint download
    // No additional initialization needed
}

// Event Listeners
function initializeEventListeners() {
    uploadForm.addEventListener('submit', handleUpload);
    if (teamsUrlForm) {
        teamsUrlForm.addEventListener('submit', handleTeamsUrlSubmit);
    }
    refreshProjectsBtn.addEventListener('click', loadProjects);
    refreshActionItemsBtn.addEventListener('click', loadActionItems);
    projectFilter.addEventListener('change', loadActionItems);
    statusFilter.addEventListener('change', loadActionItems);
    
    if (closeResultsBtn) {
        closeResultsBtn.addEventListener('click', () => {
            resultsSection.classList.remove('active');
            switchSection('upload');
            navItems[0].classList.add('active');
        });
    }
}

// Handle file upload
async function handleUpload(e) {
    e.preventDefault();
    
    // Edge case: Validate file selected
    if (!fileInput.files[0]) {
        showToast('Please select a file', 'error');
        return;
    }
    
    // Edge case: Validate file size (client-side check)
    const file = fileInput.files[0];
    const maxSize = 500 * 1024 * 1024; // 500MB
    if (file.size > maxSize) {
        showToast(`File too large. Maximum size: ${(maxSize / 1024 / 1024).toFixed(0)}MB`, 'error');
        return;
    }
    
    // Edge case: Validate file type
    const allowedTypes = ['audio/', 'video/', 'text/', 'application/octet-stream'];
    const fileType = file.type || '';
    const fileName = file.name.toLowerCase();
    const hasValidExtension = fileName.endsWith('.mp3') || fileName.endsWith('.wav') || 
                              fileName.endsWith('.mp4') || fileName.endsWith('.txt') || 
                              fileName.endsWith('.md') || fileName.endsWith('.m4a');
    
    if (!hasValidExtension && !allowedTypes.some(type => fileType.startsWith(type))) {
        showToast('Invalid file type. Please upload audio, video, or text files.', 'error');
        return;
    }
    
    const formData = new FormData(uploadForm);
    formData.append('file', file);
    
    // Get project name from dropdown or input
    const projectSelect = document.getElementById('projectName');
    const projectInput = document.getElementById('projectNameInput');
    let projectName = '';
    
    if (projectSelect && projectSelect.value) {
        projectName = projectSelect.value;
    } else if (projectInput && projectInput.value.trim()) {
        projectName = projectInput.value.trim();
    } else {
        showToast('Please select or enter a project name', 'error');
        return;
    }
    
    formData.set('project_name', projectName);
    
    // UI Updates - Show loading state on button
    uploadBtn.disabled = true;
    const uploadBtnText = uploadBtn.querySelector('.btn-text');
    const uploadBtnLoader = uploadBtn.querySelector('.btn-loader');
    if (uploadBtnText) uploadBtnText.style.display = 'none';
    if (uploadBtnLoader) uploadBtnLoader.style.display = 'flex';
    
    // Show progress bar
    progressBar.style.display = 'block';
    progressFill.style.width = '0%';
    
    const progressPercentage = document.getElementById('progressPercentage');
    const progressMessage = document.getElementById('progressMessage');
    if (progressPercentage) progressPercentage.textContent = '0%';
    if (progressMessage) progressMessage.textContent = 'Preparing to upload...';
    let processId = null;
    let progressPollInterval = null;
    
    try {
        showToast('Processing transcript... This may take a few minutes.', 'info');
        
        const response = await fetch(`${API_BASE}/api/transcripts/process`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Check if confirmation is required for old meeting or duplicate file
            if (data.requires_confirmation) {
                progressBar.style.display = 'none';
                uploadBtn.disabled = false;
                const uploadBtnText = uploadBtn.querySelector('.btn-text');
                const uploadBtnLoader = uploadBtn.querySelector('.btn-loader');
                if (uploadBtnText) uploadBtnText.style.display = 'inline';
                if (uploadBtnLoader) uploadBtnLoader.style.display = 'none';
                showConfirmationDialog(data.process_id, data.confirmation_prompt || data.message);
                return;
            }
            
            if (data.success) {
                // Processing is complete - show results immediately
                if (window.currentProgressInterval) {
                    clearInterval(window.currentProgressInterval);
                }
                progressFill.style.width = '100%';
                if (progressPercentage) progressPercentage.textContent = '100%';
                
                setTimeout(() => {
                    progressBar.style.display = 'none';
                    showToast('✓ Transcript processed successfully!', 'success');
                    if (data.summary_id) {
                        loadFullSummary(data.summary_id);
                    } else if (data.summary) {
                        displayResults(data);
                    }
                    switchSection('results');
                    navItems.forEach(nav => nav.classList.remove('active'));
                    const resultsNav = Array.from(navItems).find(nav => nav.dataset.section === 'results');
                    if (resultsNav) resultsNav.classList.add('active');
                    loadProjects();
                    loadActionItems();
                }, 500);
            } else if (data.process_id) {
                // Processing is in progress - start polling
                processId = data.process_id;
                if (progressPercentage) {
                    startProgressPolling(processId, progressPercentage);
                } else {
                    // Fallback: simulate progress if element not found
                    simulateProgress(document.getElementById('progressPercentage'));
                }
            } else {
                // No process ID and not successful - show error
                progressBar.style.display = 'none';
                // Reset button state on error
                uploadBtn.disabled = false;
                const uploadBtnText = uploadBtn.querySelector('.btn-text');
                const uploadBtnLoader = uploadBtn.querySelector('.btn-loader');
                if (uploadBtnText) uploadBtnText.style.display = 'inline';
                if (uploadBtnLoader) uploadBtnLoader.style.display = 'none';
                showToast(`Error: ${data.detail || data.message || 'Unknown error'}`, 'error');
            }
        } else {
            progressBar.style.display = 'none';
            // Reset button state on error
            uploadBtn.disabled = false;
            const uploadBtnText = uploadBtn.querySelector('.btn-text');
            const uploadBtnLoader = uploadBtn.querySelector('.btn-loader');
            if (uploadBtnText) uploadBtnText.style.display = 'inline';
            if (uploadBtnLoader) uploadBtnLoader.style.display = 'none';
            showToast(`Error: ${data.detail || data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        if (progressPollInterval) clearInterval(progressPollInterval);
        progressBar.style.display = 'none';
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        // Reset button state
        uploadBtn.disabled = false;
        const uploadBtnText = uploadBtn.querySelector('.btn-text');
        const uploadBtnLoader = uploadBtn.querySelector('.btn-loader');
        if (uploadBtnText) uploadBtnText.style.display = 'inline';
        if (uploadBtnLoader) uploadBtnLoader.style.display = 'none';
    }
}

// Poll for processing progress
function startProgressPolling(processId, progressElement) {
    // Prevent duplicate polling for the same process_id
    if (window.currentPollingProcessId === processId && window.currentProgressInterval) {
        console.log('Already polling for process_id:', processId, '- skipping duplicate');
        return;
    }
    
    // Clear any existing polling interval first
    if (window.currentProgressInterval) {
        console.log('Clearing existing polling interval');
        clearInterval(window.currentProgressInterval);
        window.currentProgressInterval = null;
        window.currentPollingProcessId = null;
    }
    
    // Store the current process_id being polled
    window.currentPollingProcessId = processId;
    
    if (!progressElement) {
        progressElement = document.getElementById('progressPercentage');
    }
    
    const progressMessageEl = document.getElementById('progressMessage');
    const progressBarEl = document.getElementById('progressBar');
    
    // Ensure progress bar is visible
    if (progressBarEl) {
        progressBarEl.style.display = 'block';
    }
    
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/transcripts/process/${processId}/progress`);
            if (!response.ok) {
                clearInterval(pollInterval);
                if (progressElement) {
                    progressElement.textContent = 'Error';
                    progressElement.style.color = 'var(--error)';
                }
                if (progressMessageEl) {
                    progressMessageEl.textContent = 'Failed to fetch progress';
                    progressMessageEl.style.color = 'var(--error)';
                }
                return;
            }
            
            const progress = await response.json();
            const percentage = Math.min(progress.progress || 0, 99);
            const statusMessage = progress.message || 'Processing...';
            
            // Check if process not found (status === 'unknown')
            if (progress.status === 'unknown') {
                console.warn('Process not found, stopping polling');
                clearInterval(pollInterval);
                window.currentProgressInterval = null;
                window.currentPollingProcessId = null;
                if (progressMessageEl) {
                    progressMessageEl.textContent = 'Process not found - may have completed or timed out';
                    progressMessageEl.style.color = 'var(--error)';
                }
                return;
            }
            
            // Update progress bar
            if (progressFill) {
                progressFill.style.width = percentage + '%';
            }
            if (progressElement) {
                progressElement.textContent = `${percentage}%`;
            }
            
            // Update status message
            if (progressMessageEl) {
                progressMessageEl.textContent = statusMessage;
                progressMessageEl.style.color = 'var(--text-secondary)';
                
                // Color code based on status
                if (progress.status === 'error') {
                    progressMessageEl.style.color = 'var(--error)';
                } else if (progress.status === 'completed') {
                    progressMessageEl.style.color = 'var(--success)';
                } else if (progress.status === 'processing') {
                    progressMessageEl.style.color = 'var(--primary)';
                }
            }
            
            if (progress.status === 'completed') {
                clearInterval(pollInterval);
                window.currentProgressInterval = null; // Clear the reference
                window.currentPollingProcessId = null; // Clear the process_id reference
                if (progressFill) progressFill.style.width = '100%';
                if (progressElement) progressElement.textContent = '100%';
                if (progressMessageEl) {
                    progressMessageEl.textContent = progress.message || 'Processing complete!';
                    progressMessageEl.style.color = 'var(--success)';
                }
                
                // Show completion message and reload
                setTimeout(() => {
                    if (progressBarEl) progressBarEl.style.display = 'none';
                    const completionMsg = progress.message || '✓ Processing completed successfully!';
                    showToast(completionMsg, 'success');
                    // Reload to show new meeting
                    loadProjects();
                    loadActionItems();
                }, 1000);
                return; // Exit early to prevent further polling
            } else if (progress.status === 'error') {
                clearInterval(pollInterval);
                window.currentProgressInterval = null; // Clear the reference
                window.currentPollingProcessId = null; // Clear the process_id reference
                if (progressElement) {
                    progressElement.textContent = 'Error';
                    progressElement.style.color = 'var(--error)';
                }
                if (progressMessageEl) {
                    progressMessageEl.textContent = progress.message || 'Processing failed';
                    progressMessageEl.style.color = 'var(--error)';
                }
                showToast(`Error: ${progress.message || 'Processing failed'}`, 'error');
            }
        } catch (error) {
            console.error('Error polling progress:', error);
            clearInterval(pollInterval);
            window.currentProgressInterval = null; // Clear the reference
            window.currentPollingProcessId = null; // Clear the process_id reference
            if (progressElement) {
                progressElement.textContent = 'Error';
                progressElement.style.color = 'var(--error)';
            }
            if (progressMessageEl) {
                progressMessageEl.textContent = 'Error fetching progress';
                progressMessageEl.style.color = 'var(--error)';
            }
        }
    }, 1000); // Poll every second
    
    // Store interval for cleanup
    window.currentProgressInterval = pollInterval;
    
    // Also add a timeout to prevent infinite polling (max 30 minutes)
    setTimeout(() => {
        if (window.currentProgressInterval === pollInterval) {
            console.warn('Progress polling timeout - stopping after 30 minutes');
            clearInterval(pollInterval);
            window.currentProgressInterval = null;
            window.currentPollingProcessId = null;
            if (progressMessageEl) {
                progressMessageEl.textContent = 'Processing timeout - please check backend logs';
                progressMessageEl.style.color = 'var(--error)';
            }
        }
    }, 30 * 60 * 1000); // 30 minutes
}

// Fallback progress simulation
function simulateProgress(progressElement) {
    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 5 + 2;
        if (progress > 95) {
            progress = 95;
            clearInterval(interval);
        }
        
        progressFill.style.width = progress + '%';
        progressElement.textContent = `${Math.round(progress)}%`;
    }, 800);
    
    window.currentProgressInterval = interval;
}

// Show confirmation dialog for old meetings
function showConfirmationDialog(processId, message) {
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; display: flex; align-items: center; justify-content: center;';
    
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'confirmation-modal';
    modal.style.cssText = 'background: white; padding: 30px; border-radius: 12px; max-width: 500px; width: 90%; box-shadow: 0 10px 40px rgba(0,0,0,0.2);';
    
    // Determine if this is a duplicate file or old meeting
    const isDuplicate = message.includes('already processed') || message.includes('processed before');
    const title = isDuplicate ? '⚠️ Duplicate File Detected' : '⚠️ Old Meeting Detected';
    
    modal.innerHTML = `
        <h2 style="margin-top: 0; color: var(--text-primary);">${title}</h2>
        <p style="color: var(--text-secondary); margin-bottom: 20px; white-space: pre-line;">${escapeHtml(message)}</p>
        <div style="margin: 20px 0;">
            <label style="display: flex; align-items: center; margin-bottom: 15px; cursor: pointer;">
                <input type="checkbox" id="confirmTrello" checked style="margin-right: 10px; width: 20px; height: 20px;">
                <span>Add action items to Trello</span>
            </label>
            <label style="display: flex; align-items: center; cursor: pointer;">
                <input type="checkbox" id="confirmConfluence" checked style="margin-right: 10px; width: 20px; height: 20px;">
                <span>Add summary to Confluence</span>
            </label>
        </div>
        <div style="display: flex; gap: 10px; justify-content: flex-end; flex-wrap: wrap;">
            <button id="skipFile" class="btn btn-secondary" style="padding: 10px 20px; background: #dc3545; color: white;">Skip File</button>
            <button id="cancelConfirm" class="btn btn-secondary" style="padding: 10px 20px;">Cancel</button>
            <button id="confirmProcess" class="btn btn-primary" style="padding: 10px 20px;">Continue Processing</button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Handle confirm button
    document.getElementById('confirmProcess').addEventListener('click', async () => {
        const addToTrello = document.getElementById('confirmTrello').checked;
        const addToConfluence = document.getElementById('confirmConfluence').checked;
        
        // Show progress bar
        progressBar.style.display = 'block';
        progressFill.style.width = '0%';
        progressPercentage.textContent = '0%';
        const progressMessage = document.getElementById('progressMessage');
        if (progressMessage) progressMessage.textContent = 'Starting upload...';
        
        overlay.remove();
        
        try {
            const response = await fetch(`${API_BASE}/api/transcripts/process/confirm`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    process_id: processId,
                    add_to_trello: addToTrello,
                    add_to_confluence: addToConfluence
                })
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                if (data.process_id) {
                    startProgressPolling(data.process_id, progressPercentage);
                }
                
                setTimeout(() => {
                    if (window.currentProgressInterval) clearInterval(window.currentProgressInterval);
                    progressFill.style.width = '100%';
                    progressPercentage.textContent = '100%';
                    
                    setTimeout(() => {
                        progressBar.style.display = 'none';
                        showToast('✓ Old meeting processed successfully!', 'success');
                        if (data.summary_id) {
                            loadFullSummary(data.summary_id);
                        }
                        switchSection('results');
                        navItems.forEach(nav => nav.classList.remove('active'));
                        const resultsNav = Array.from(navItems).find(nav => nav.dataset.section === 'results');
                        if (resultsNav) resultsNav.classList.add('active');
                        loadProjects();
                        loadActionItems();
                    }, 500);
                }, 2000);
            } else {
                progressBar.style.display = 'none';
                showToast(`Error: ${data.detail || data.message || 'Unknown error'}`, 'error');
            }
        } catch (error) {
            progressBar.style.display = 'none';
            showToast(`Error: ${error.message}`, 'error');
        }
    });
    
    // Handle skip file button
    document.getElementById('skipFile').addEventListener('click', async () => {
        overlay.remove();
        
        try {
            // Call skip endpoint to clean up
            await fetch(`${API_BASE}/api/transcripts/process/${processId}/skip`, {
                method: 'POST'
            });
        } catch (error) {
            console.error('Error skipping file:', error);
        }
        
        // Reset UI
        uploadBtn.disabled = false;
        const uploadBtnText = uploadBtn.querySelector('.btn-text');
        const uploadBtnLoader = uploadBtn.querySelector('.btn-loader');
        if (uploadBtnText) uploadBtnText.style.display = 'inline';
        if (uploadBtnLoader) uploadBtnLoader.style.display = 'none';
        progressBar.style.display = 'none';
        fileInput.value = ''; // Clear file input
        
        // Reset file preview if exists
        const filePreview = document.getElementById('filePreview');
        if (filePreview) {
            filePreview.style.display = 'none';
        }
        const fileName = document.getElementById('fileName');
        if (fileName) {
            fileName.textContent = '';
        }
        
        showToast('File skipped', 'info');
    });
    
    // Handle cancel button
    document.getElementById('cancelConfirm').addEventListener('click', () => {
        overlay.remove();
        uploadBtn.disabled = false;
        const uploadBtnText = uploadBtn.querySelector('.btn-text');
        const uploadBtnLoader = uploadBtn.querySelector('.btn-loader');
        if (uploadBtnText) uploadBtnText.style.display = 'inline';
        if (uploadBtnLoader) uploadBtnLoader.style.display = 'none';
        showToast('Processing cancelled', 'info');
    });
}

// Display processing results
// Helper function to get meeting type label
function getMeetingTypeLabel(meetingType) {
    const labels = {
        'discussion': 'Discussion',
        'KT': 'Knowledge Transfer',
        'decision_making': 'Decision Making',
        'general': 'General'
    };
    return labels[meetingType] || meetingType || 'General';
}

function displayResults(data) {
    if (!data.summary) return;
    
    const summary = data.summary;
    const date = new Date(summary.meeting_date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
    
    // If we have summary_id, fetch full details
    if (data.summary_id) {
        loadFullSummary(data.summary_id);
        return;
    }
    
    renderSummaryCard(summary, date);
}

// Display multiple summaries (for multiple recordings processed)
function displayMultipleResults(summaries, summaryIds) {
    if (!summaries || summaries.length === 0) return;
    
    resultsContent.innerHTML = '<div style="margin-bottom: 20px;"><h2>Processing Results</h2><p>Successfully processed ' + summaries.length + ' recording(s):</p></div>';
    
    summaries.forEach((summary, index) => {
        const date = new Date(summary.meeting_date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        
        // If we have summary_id, fetch full details, otherwise render card
        if (summaryIds && summaryIds[index]) {
            // Create a wrapper div and load full summary
            const wrapperDiv = document.createElement('div');
            wrapperDiv.id = `summary-wrapper-${summaryIds[index]}`;
            wrapperDiv.style.marginBottom = '24px';
            resultsContent.appendChild(wrapperDiv);
            
            // Load full summary for this ID
            setTimeout(() => {
                loadFullSummary(summaryIds[index], wrapperDiv);
            }, index * 100); // Stagger loading slightly
        } else {
            // Render summary card directly
            const cardDiv = document.createElement('div');
            resultsContent.appendChild(cardDiv);
            renderSummaryCard(summary, date, false, cardDiv);
        }
    });
}

// Load full summary details
async function loadFullSummary(summaryId, targetElement = null) {
    try {
        const loadingTarget = targetElement || resultsContent;
        loadingTarget.innerHTML = '<div class="loading-state"><div class="spinner-large"></div><p>Loading full details...</p></div>';
        
        const response = await fetch(`${API_BASE}/api/summaries/${summaryId}?full_details=true`);
        const summary = await response.json();
        
        const date = new Date(summary.meeting_date).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        
        // If targetElement is provided, render into that element (for multiple summaries)
        // Otherwise, render into resultsContent (single summary)
        if (targetElement) {
            renderSummaryCard(summary, date, true, targetElement);
        } else {
            renderSummaryCard(summary, date, true);
        }
    } catch (error) {
        const errorTarget = targetElement || resultsContent;
        errorTarget.innerHTML = `<div class="error-message"><p>Error loading summary: ${error.message}</p></div>`;
        showToast(`Error loading full details: ${error.message}`, 'error');
        resultsContent.innerHTML = `<div class="loading-state"><p style="color: var(--error);">Error: ${error.message}</p></div>`;
    }
}

// Make loadFullSummary available globally
window.loadFullSummary = loadFullSummary;

// Render summary card with expandable sections
function renderSummaryCard(summary, date, isExpanded = false, targetElement = null) {
    const content = `
        <div class="summary-card" style="position: relative;">
            <div class="summary-header">
                <div>
                    <div class="summary-title">${escapeHtml(summary.meeting_title)}</div>
                    <div class="summary-meta">
                        <span class="meta-item">📁 ${escapeHtml(summary.project_name)}</span>
                        <span class="meta-item">📅 ${date}</span>
                        ${summary.meeting_type ? `<span class="meta-item">🏷️ ${getMeetingTypeLabel(summary.meeting_type)}</span>` : ''}
                        ${summary.duration_minutes ? `<span class="meta-item">⏱️ ${summary.duration_minutes.toFixed(1)} min</span>` : ''}
                        ${summary.participants && summary.participants.length > 0 ? `<span class="meta-item">👥 ${summary.participants.length} participant${summary.participants.length !== 1 ? 's' : ''}</span>` : ''}
                        ${summary.metadata && summary.metadata.original_file_name ? `<span class="meta-item">📎 ${escapeHtml(summary.metadata.original_file_name)}</span>` : ''}
                    </div>
                    ${summary.metadata && summary.metadata.is_empty_meeting ? `
                    <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 12px; border-radius: 4px; margin: 16px 0;">
                        <strong>⚠️ Note:</strong> This meeting appears to be empty or contains no meaningful content. The transcript may be incomplete, corrupted, or the meeting may not have had substantial discussion.
                    </div>
                    ` : ''}
                </div>
                <div class="summary-actions">
                    ${summary.confluence_url ? `<a href="${escapeHtml(summary.confluence_url)}" target="_blank" class="btn btn-secondary btn-icon"><span class="btn-icon">🔗</span>View in Confluence</a>` : ''}
                    ${summary.trello_board_url ? `<a href="${escapeHtml(summary.trello_board_url)}" target="_blank" class="btn btn-secondary btn-icon"><span class="btn-icon">📋</span>View Trello Board</a>` : ''}
                    <button 
                        class="btn-delete-meeting" 
                        onclick="confirmDeleteMeeting('${summary.id}', '${escapeHtml(summary.meeting_title)}', '${escapeHtml(summary.project_name)}')"
                        title="Delete this meeting"
                        style="background: #dc3545 !important; color: white !important; border: none !important; border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: 14px; display: inline-flex !important; align-items: center; gap: 4px; transition: background 0.2s; margin-left: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"
                        onmouseover="this.style.background='#c82333'; this.style.boxShadow='0 2px 6px rgba(0,0,0,0.3)';"
                        onmouseout="this.style.background='#dc3545'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.2)';"
                    >
                        🗑️ Delete
                    </button>
                </div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card clickable-stat" data-section="action-items">
                    <div class="stat-value">${summary.action_items_count}</div>
                    <div class="stat-label">Action Items</div>
                   
                </div>
                <div class="stat-card clickable-stat" data-section="decisions">
                    <div class="stat-value">${summary.decisions_count}</div>
                    <div class="stat-label">Decisions</div>
                    
                </div>
                <div class="stat-card clickable-stat" data-section="risks">
                    <div class="stat-value">${summary.risks_count}</div>
                    <div class="stat-label">Risks</div>
                    
                </div>
            </div>
            
            <div class="summary-content">
                <h3>Summary</h3>
                <p>${escapeHtml(summary.overall_summary).replace(/\n/g, '<br>')}</p>
                
                ${summary.tags && summary.tags.length > 0 ? `
                    <h3>Tags</h3>
                    <div class="action-item-tags">
                        ${summary.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                    </div>
                ` : ''}
            </div>
            
            <!-- Expandable Sections -->
            ${summary.all_action_items && summary.all_action_items.length > 0 ? `
                <div class="expandable-section">
                    <div class="expandable-header" onclick="toggleSection(this)">
                        <h3>📋 Action Items (${summary.all_action_items.length})</h3>
                        <span class="expand-icon">▼</span>
                    </div>
                    <div class="expandable-content" style="display: ${isExpanded ? 'block' : 'none'}">
                        ${summary.all_action_items.map((item, index) => renderActionItem(item, index)).join('')}
                    </div>
                </div>
            ` : ''}
            
            ${summary.all_decisions && summary.all_decisions.length > 0 ? `
                <div class="expandable-section">
                    <div class="expandable-header" onclick="toggleSection(this)">
                        <h3>✅ Decisions (${summary.all_decisions.length})</h3>
                        <span class="expand-icon">▼</span>
                    </div>
                    <div class="expandable-content" style="display: ${isExpanded ? 'block' : 'none'}">
                        ${summary.all_decisions.map((decision, index) => renderDecision(decision, index)).join('')}
                    </div>
                </div>
            ` : ''}
            
            ${summary.all_risks && summary.all_risks.length > 0 ? `
                <div class="expandable-section">
                    <div class="expandable-header" onclick="toggleSection(this)">
                        <h3>⚠️ Risks (${summary.all_risks.length})</h3>
                        <span class="expand-icon">▼</span>
                    </div>
                    <div class="expandable-content" style="display: ${isExpanded ? 'block' : 'none'}">
                        ${summary.all_risks.map((risk, index) => renderRisk(risk, index)).join('')}
                    </div>
                </div>
            ` : ''}
        </div>
    `;
    
    // Set content to target element or default resultsContent
    if (targetElement) {
        targetElement.innerHTML = content;
    } else {
        resultsContent.innerHTML = content;
    }
    
    // Add click handlers for stat cards (use targetElement or document)
    const container = targetElement || document;
    container.querySelectorAll('.clickable-stat').forEach(card => {
        card.addEventListener('click', () => {
            const section = card.dataset.section;
            const expandable = document.querySelector(`.expandable-section .expandable-header h3`);
            if (expandable && expandable.textContent.includes(section === 'action-items' ? 'Action Items' : section === 'decisions' ? 'Decisions' : 'Risks')) {
                const header = expandable.closest('.expandable-header');
                toggleSection(header);
                header.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        });
    });
}

// Render action item
function renderActionItem(item, index) {
    const deadline = item.deadline 
        ? new Date(item.deadline).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        })
        : 'No deadline';
    
    const statusClass = `status-${item.status.replace('_', '-')}`;
    const trelloLink = item.external_id 
        ? `<a href="https://trello.com/c/${item.external_id}" target="_blank" class="trello-link">🔗 View on Trello</a>`
        : '';
    
    return `
        <div class="detail-item-card">
            <div class="detail-item-header">
                <div class="detail-item-number">#${index + 1}</div>
                <div class="detail-item-content">
                    <div class="detail-item-description">${escapeHtml(item.description)}</div>
                    <div class="detail-item-meta">
                        <span>👤 ${escapeHtml(item.owner)}</span>
                        <span>📅 ${deadline}</span>
                        <span class="action-item-status ${statusClass}">${escapeHtml(item.status)}</span>
                        ${trelloLink}
                    </div>
                    ${item.tags && item.tags.length > 0 ? `
                        <div class="action-item-tags" style="margin-top: 8px;">
                            ${item.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                        </div>
                    ` : ''}
                    ${item.dependencies && item.dependencies.length > 0 ? `
                        <div style="margin-top: 8px; font-size: 0.85rem; color: var(--text-secondary);">
                            <strong>Dependencies:</strong> ${item.dependencies.map(dep => escapeHtml(dep)).join(', ')}
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

// Render decision
function renderDecision(decision, index) {
    const timestamp = decision.timestamp 
        ? new Date(decision.timestamp).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        })
        : '';
    
    return `
        <div class="detail-item-card">
            <div class="detail-item-header">
                <div class="detail-item-number">#${index + 1}</div>
                <div class="detail-item-content">
                    <div class="detail-item-description">${escapeHtml(decision.description)}</div>
                    ${decision.context ? `<div style="margin-top: 8px; color: var(--text-secondary);">${escapeHtml(decision.context)}</div>` : ''}
                    <div class="detail-item-meta">
                        ${decision.decision_makers && decision.decision_makers.length > 0 ? `<span>👥 ${decision.decision_makers.map(d => escapeHtml(d)).join(', ')}</span>` : ''}
                        ${timestamp ? `<span>📅 ${timestamp}</span>` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Render risk
function renderRisk(risk, index) {
    const severityClass = `severity-${risk.severity.toLowerCase()}`;
    
    return `
        <div class="detail-item-card">
            <div class="detail-item-header">
                <div class="detail-item-number">#${index + 1}</div>
                <div class="detail-item-content">
                    <div class="detail-item-description">${escapeHtml(risk.description)}</div>
                    <div class="detail-item-meta">
                        <span class="risk-severity ${severityClass}">${escapeHtml(risk.severity)}</span>
                        ${risk.owner ? `<span>👤 ${escapeHtml(risk.owner)}</span>` : ''}
                    </div>
                    ${risk.impact ? `<div style="margin-top: 8px; color: var(--text-secondary);"><strong>Impact:</strong> ${escapeHtml(risk.impact)}</div>` : ''}
                    ${risk.mitigation ? `<div style="margin-top: 8px; color: var(--text-secondary);"><strong>Mitigation:</strong> ${escapeHtml(risk.mitigation)}</div>` : ''}
                </div>
            </div>
        </div>
    `;
}

// Toggle expandable section
function toggleSection(header) {
    const content = header.nextElementSibling;
    const icon = header.querySelector('.expand-icon');
    
    if (content.style.display === 'none') {
        content.style.display = 'block';
        icon.textContent = '▲';
    } else {
        content.style.display = 'none';
        icon.textContent = '▼';
    }
}

// Make toggleSection available globally
window.toggleSection = toggleSection;

// Load projects
async function loadProjects() {
    if (projectsList) {
        projectsList.innerHTML = '<div class="loading-state"><div class="spinner-large"></div><p>Loading projects...</p></div>';
    }
    
    try {
        console.log('Loading projects from:', `${API_BASE}/api/projects`);
        const response = await fetch(`${API_BASE}/api/projects`);
        console.log('Projects API response status:', response.status);
        
        if (!response.ok) {
            console.error('Failed to load projects:', response.status, response.statusText);
            if (projectsList) {
                projectsList.innerHTML = `<div class="loading-state"><p style="color: var(--error);">Error loading projects: ${response.status} ${response.statusText}</p></div>`;
            }
            return;
        }
        
        const projects = await response.json();
        console.log('Projects loaded:', projects);
        
        // Update project dropdown (for upload form)
        if (projects && Array.isArray(projects)) {
            updateProjectDropdown(projects);
        } else {
            console.warn('Projects is not an array:', projects);
        }
        
        // Update project filter (for action items section)
        if (projectFilter && projects && Array.isArray(projects)) {
            updateProjectFilter(projects);
        }
        
        if (projectsList) {
            if (projects.length === 0) {
                projectsList.innerHTML = '<div class="loading-state"><p>No projects found. Upload a transcript to create one!</p></div>';
            } else {
                projectsList.innerHTML = projects.map(project => {
                    const date = project.latest_meeting_date 
                        ? new Date(project.latest_meeting_date).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric'
                        })
                        : 'No meetings';
                    
            return `
                <div class="project-card">
                    <div class="project-card-header" onclick="loadProjectSummaries('${escapeHtml(project.name)}')">
                        <div class="project-name">${escapeHtml(project.name)}</div>
                        <div class="project-meta">
                            <div>📊 ${project.meeting_count} meeting${project.meeting_count !== 1 ? 's' : ''}</div>
                            <div>📅 Latest: ${date}</div>
                        </div>
                    </div>
                    <div class="project-card-actions">

                    <!--
                    // <button class="btn btn-small btn-secondary" onclick="event.stopPropagation(); extractProjectEmails('${escapeHtml(project.name)}')" title="Extract emails from Trello/Confluence">
                        //     📧 Extract Emails
                        // </button>
                    // -->
                        
                        <!--
                        // <button class="btn btn-small btn-secondary" onclick="event.stopPropagation(); syncConfluence('${escapeHtml(project.name)}')" title="Sync Confluence pages">
                        //     🔄 Sync Confluence
                        // </button>
                        // -->
                        <button class="btn btn-small btn-danger" onclick="event.stopPropagation(); confirmDeleteProject('${escapeHtml(project.name)}')" title="Delete project">
                            🗑️ Delete
                        </button>
                    </div>
                </div>
            `;
                }).join('');
            }
        }
    } catch (error) {
        console.error('Error loading projects:', error);
        if (projectsList) {
            projectsList.innerHTML = `<div class="loading-state"><p style="color: var(--error);">Error loading projects: ${error.message}</p></div>`;
        }
    }
}

// Load project summaries
async function loadProjectSummaries(projectName) {
    try {
        switchSection('results');
        navItems.forEach(nav => nav.classList.remove('active'));
        const resultsNav = Array.from(navItems).find(nav => nav.dataset.section === 'results');
        if (resultsNav) resultsNav.classList.add('active');
        
        resultsContent.innerHTML = '<div class="loading-state"><div class="spinner-large"></div><p>Loading summaries...</p></div>';
        
        const response = await fetch(`${API_BASE}/api/summaries/project/${encodeURIComponent(projectName)}`);
        const summaries = await response.json();
        
        if (summaries.length === 0) {
            resultsContent.innerHTML = '<p>No summaries found for this project.</p>';
            return;
        }
        
        const summariesHtml = summaries.map(summary => {
            const date = new Date(summary.meeting_date).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
            return `
                <div class="summary-card" style="margin-bottom: 16px; position: relative;">
                    <div class="clickable-summary" style="cursor: pointer; padding-right: 50px;" onclick="loadFullSummary('${summary.id}')">
                        <div class="summary-title">${escapeHtml(summary.meeting_title)}</div>
                        <div class="summary-meta">
                            <span>📅 ${date}</span>
                            ${summary.meeting_type ? `<span>🏷️ ${getMeetingTypeLabel(summary.meeting_type)}</span>` : ''}
                            <span>📋 ${summary.action_items_count} action items</span>
                            <span>✅ ${summary.decisions_count} decisions</span>
                            <span>⚠️ ${summary.risks_count} risks</span>
                        </div>
                        <p style="margin-top: 12px;">${escapeHtml(summary.overall_summary.substring(0, 200))}...</p>
                        <div style="margin-top: 12px; color: var(--primary); font-weight: 500;">Click to view full details →</div>
                    </div>
                    <button 
                        class="btn-delete-meeting" 
                        onclick="event.stopPropagation(); confirmDeleteMeeting('${summary.id}', '${escapeHtml(summary.meeting_title)}', '${escapeHtml(summary.project_name)}')"
                        title="Delete this meeting"
                        style="position: absolute; top: 12px; right: 12px; background: #dc3545 !important; color: white !important; border: none !important; border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: 14px; display: flex !important; align-items: center; gap: 4px; transition: background 0.2s; z-index: 1000; box-shadow: 0 2px 4px rgba(0,0,0,0.2);"
                        onmouseover="this.style.background='#c82333'; this.style.boxShadow='0 2px 6px rgba(0,0,0,0.3)';"
                        onmouseout="this.style.background='#dc3545'; this.style.boxShadow='0 2px 4px rgba(0,0,0,0.2)';"
                    >
                        🗑️ Delete
                    </button>
                </div>
            `;
        }).join('');
        
        resultsContent.innerHTML = `
            <h3 style="margin-bottom: 20px; color: var(--text-primary);">Summaries for: ${escapeHtml(projectName)}</h3>
            ${summariesHtml}
        `;
    } catch (error) {
        showToast(`Error loading summaries: ${error.message}`, 'error');
    }
}

// Load action items
async function loadActionItems() {
    actionItemsList.innerHTML = '<div class="loading-state"><div class="spinner-large"></div><p>Loading action items...</p></div>';
    
    const params = new URLSearchParams();
    if (projectFilter.value) {
        params.append('project_name', projectFilter.value);
    }
    if (statusFilter.value) {
        params.append('status', statusFilter.value);
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/action-items/?${params.toString()}`);
        const items = await response.json();
        
        if (items.length === 0) {
            actionItemsList.innerHTML = '<div class="loading-state"><p>No action items found.</p></div>';
            return;
        }
        
        actionItemsList.innerHTML = items.map((item, index) => {
            const deadline = item.deadline 
                ? new Date(item.deadline).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                })
                : 'No deadline';
            
            const statusClass = `status-${item.status.replace('_', '-')}`;
            const trelloLink = item.external_id 
                ? `<a href="https://trello.com/c/${item.external_id}" target="_blank" class="trello-link">🔗 View on Trello</a>`
                : '';
            
            return `
                <div class="action-item-card expandable-action-item">
                    <div class="action-item-header" onclick="toggleActionItem(this)">
                        <div class="action-item-content">
                            <div class="action-item-description">${escapeHtml(item.description)}</div>
                            <div class="action-item-meta">
                                <span>👤 ${escapeHtml(item.owner)}</span>
                                <span>📅 ${deadline}</span>
                                <span class="action-item-status ${statusClass}">${escapeHtml(item.status)}</span>
                                ${trelloLink}
                            </div>
                        </div>
                        <span class="expand-icon">▼</span>
                    </div>
                    <div class="action-item-details" style="display: none;">
                        ${item.tags && item.tags.length > 0 ? `
                            <div class="action-item-tags" style="margin-top: 12px;">
                                ${item.tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join('')}
                            </div>
                        ` : ''}
                        ${item.dependencies && item.dependencies.length > 0 ? `
                            <div style="margin-top: 12px; font-size: 0.85rem; color: var(--text-secondary);">
                                <strong>Dependencies:</strong> ${item.dependencies.map(dep => escapeHtml(dep)).join(', ')}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
        
        // Add click handlers
        document.querySelectorAll('.expandable-action-item .action-item-header').forEach(header => {
            header.style.cursor = 'pointer';
        });
    } catch (error) {
        actionItemsList.innerHTML = `<div class="loading-state"><p style="color: var(--error);">Error loading action items: ${error.message}</p></div>`;
    }
}

// Toggle action item details
function toggleActionItem(header) {
    const details = header.nextElementSibling;
    const icon = header.querySelector('.expand-icon');
    
    if (details.style.display === 'none') {
        details.style.display = 'block';
        icon.textContent = '▲';
    } else {
        details.style.display = 'none';
        icon.textContent = '▼';
    }
}

window.toggleActionItem = toggleActionItem;

// Update project dropdown (for upload form)
function updateProjectDropdown(projects) {
    const projectSelect = document.getElementById('projectName');
    const projectInput = document.getElementById('projectNameInput');
    const addProjectBtn = document.getElementById('addProjectBtn');
    
    // Also update Teams form dropdown
    const teamsProjectSelect = document.getElementById('teamsProjectName');
    const teamsProjectInput = document.getElementById('teamsProjectNameInput');
    const teamsAddProjectBtn = document.getElementById('teamsAddProjectBtn');
    
    if (!projectSelect) {
        console.warn('Project dropdown not found');
        return;
    }
    
    // Store current value
    const currentValue = projectSelect.value;
    
    // Clear and populate dropdown
    projectSelect.innerHTML = '<option value="">Select or add project...</option>';
    
    // Also update Teams form dropdown
    if (teamsProjectSelect) {
        teamsProjectSelect.innerHTML = '<option value="">Select or add project...</option>';
    }
    
    if (projects && Array.isArray(projects) && projects.length > 0) {
        console.log(`Loading ${projects.length} projects into dropdown`);
        projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.name;
            option.textContent = `${project.name} (${project.meeting_count} meetings)`;
            projectSelect.appendChild(option);
            
            // Also add to Teams form dropdown
            if (teamsProjectSelect) {
                const teamsOption = option.cloneNode(true);
                teamsProjectSelect.appendChild(teamsOption);
            }
        });
        
        // Restore selection if still valid
        if (currentValue) {
            const optionExists = Array.from(projectSelect.options).some(opt => opt.value === currentValue);
            if (optionExists) {
                projectSelect.value = currentValue;
                if (teamsProjectSelect) {
                    teamsProjectSelect.value = currentValue;
                }
            }
        }
    } else {
        console.log('No projects to display or projects is not an array:', projects);
    }
    
    // Handle "Add New" button (only attach once)
    if (addProjectBtn && !addProjectBtn.dataset.listenerAttached) {
        addProjectBtn.dataset.listenerAttached = 'true';
        addProjectBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (projectInput.style.display === 'none' || projectInput.style.display === '') {
                // Show input field
                projectInput.style.display = 'block';
                projectSelect.style.display = 'none';
                addProjectBtn.textContent = 'Save';
                projectInput.focus();
            } else {
                // Save new project
                const newProjectName = projectInput.value.trim();
                if (!newProjectName) {
                    showToast('Please enter a project name', 'error');
                    return;
                }
                
                // Disable button during save
                addProjectBtn.disabled = true;
                addProjectBtn.textContent = 'Saving...';
                
                try {
                    console.log('Creating project:', newProjectName);
                    const response = await fetch(`${API_BASE}/api/projects`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ project_name: newProjectName })
                    });
                    
                    console.log('Response status:', response.status);
                    
                    if (response.ok) {
                        const newProject = await response.json();
                        console.log('Project created:', newProject);
                        
                        // Reset UI first
                        projectInput.value = '';
                        projectInput.style.display = 'none';
                        projectSelect.style.display = 'block';
                        addProjectBtn.textContent = '+ Add New';
                        addProjectBtn.disabled = false;
                        
                        showToast(`Project "${newProject.name}" created successfully!`, 'success');
                        
                        // Reload projects to get updated list (this will refresh dropdown)
                        await loadProjects();
                        
                        // Select the newly created project
                        if (projectSelect) {
                            projectSelect.value = newProject.name;
                        }
                        if (teamsProjectSelect) {
                            teamsProjectSelect.value = newProject.name;
                        }
                    } else {
                        const errorData = await response.json().catch(() => ({ detail: 'Failed to create project' }));
                        console.error('Error creating project:', errorData);
                        showToast(`Error: ${errorData.detail || 'Failed to create project'}`, 'error');
                        addProjectBtn.disabled = false;
                        addProjectBtn.textContent = 'Save';
                    }
                } catch (error) {
                    console.error('Error creating project:', error);
                    showToast(`Error: ${error.message}`, 'error');
                    addProjectBtn.disabled = false;
                    addProjectBtn.textContent = 'Save';
                }
            }
        });
    }
    
    // Handle Teams form "Add New" button (only attach once)
    if (teamsAddProjectBtn && !teamsAddProjectBtn.dataset.listenerAttached) {
        teamsAddProjectBtn.dataset.listenerAttached = 'true';
        teamsAddProjectBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            if (teamsProjectInput.style.display === 'none' || teamsProjectInput.style.display === '') {
                // Show input field
                teamsProjectInput.style.display = 'block';
                teamsProjectSelect.style.display = 'none';
                teamsAddProjectBtn.textContent = 'Save';
                teamsProjectInput.focus();
            } else {
                // Save new project
                const newProjectName = teamsProjectInput.value.trim();
                if (!newProjectName) {
                    showToast('Please enter a project name', 'error');
                    return;
                }
                
                // Disable button during save
                teamsAddProjectBtn.disabled = true;
                teamsAddProjectBtn.textContent = 'Saving...';
                
                try {
                    console.log('Creating project:', newProjectName);
                    const response = await fetch(`${API_BASE}/api/projects`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ project_name: newProjectName })
                    });
                    
                    console.log('Response status:', response.status);
                    
                    if (response.ok) {
                        const newProject = await response.json();
                        console.log('Project created:', newProject);
                        
                        // Reset UI first
                        teamsProjectInput.value = '';
                        teamsProjectInput.style.display = 'none';
                        teamsProjectSelect.style.display = 'block';
                        teamsAddProjectBtn.textContent = '+ Add New';
                        teamsAddProjectBtn.disabled = false;
                        
                        showToast(`Project "${newProject.name}" created successfully!`, 'success');
                        
                        // Reload projects to get updated list (this will refresh dropdown)
                        await loadProjects();
                        
                        // Select the newly created project
                        if (projectSelect) {
                            projectSelect.value = newProject.name;
                        }
                        if (teamsProjectSelect) {
                            teamsProjectSelect.value = newProject.name;
                        }
                    } else {
                        const errorData = await response.json().catch(() => ({ detail: 'Failed to create project' }));
                        console.error('Error creating project:', errorData);
                        showToast(`Error: ${errorData.detail || 'Failed to create project'}`, 'error');
                        teamsAddProjectBtn.disabled = false;
                        teamsAddProjectBtn.textContent = 'Save';
                    }
                } catch (error) {
                    console.error('Error creating project:', error);
                    showToast(`Error: ${error.message}`, 'error');
                    teamsAddProjectBtn.disabled = false;
                    teamsAddProjectBtn.textContent = 'Save';
                }
            }
        });
    }
    
    // Handle dropdown change
    if (!projectSelect.dataset.listenerAttached) {
        projectSelect.dataset.listenerAttached = 'true';
        projectSelect.addEventListener('change', function() {
            if (this.value === '' && projectInput) {
                projectInput.style.display = 'block';
                projectSelect.style.display = 'none';
                if (addProjectBtn) addProjectBtn.textContent = 'Save';
            }
        });
    }
    
    // Handle input blur and Enter key
    if (projectInput && !projectInput.dataset.listenerAttached) {
        projectInput.dataset.listenerAttached = 'true';
        projectInput.addEventListener('blur', function() {
            if (!this.value.trim()) {
                this.style.display = 'none';
                projectSelect.style.display = 'block';
                if (addProjectBtn) addProjectBtn.textContent = '+ Add New';
            }
        });
        
        projectInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (addProjectBtn) addProjectBtn.click();
            }
        });
    }
}

// Update project filter dropdown (for action items section)
function updateProjectFilter(projects) {
    if (!projectFilter) return;
    
    const currentValue = projectFilter.value;
    projectFilter.innerHTML = '<option value="">All Projects</option>';
    
    projects.forEach(project => {
        const option = document.createElement('option');
        option.value = project.name;
        option.textContent = project.name;
        projectFilter.appendChild(option);
    });
    
    if (currentValue) {
        projectFilter.value = currentValue;
    }
}

// Popup Notification Modal
function showToast(message, type = 'info') {
    // Escape HTML to prevent XSS
    const escapedMessage = escapeHtml(message);
    
    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.className = 'notification-modal-overlay';
    overlay.style.cssText = 'position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000; display: flex; align-items: center; justify-content: center; animation: fadeIn 0.2s ease-out;';
    
    // Create modal popup
    const modal = document.createElement('div');
    modal.className = `notification-modal notification-${type}`;
    
    // Determine icon and title based on type
    let icon, title, borderColor;
    switch(type) {
        case 'success':
            icon = '✓';
            title = 'Success';
            borderColor = 'var(--success)';
            break;
        case 'error':
            icon = '✕';
            title = 'Error';
            borderColor = 'var(--error)';
            break;
        case 'warning':
            icon = '⚠';
            title = 'Warning';
            borderColor = '#ff9800';
            break;
        case 'info':
        default:
            icon = 'ℹ';
            title = 'Information';
            borderColor = 'var(--primary)';
            break;
    }
    
    modal.style.cssText = `
        background: var(--bg-primary);
        padding: 0;
        border-radius: 12px;
        max-width: 500px;
        width: 90%;
        max-height: 80vh;
        box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        border-top: 4px solid ${borderColor};
        animation: slideDown 0.3s ease-out;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    `;
    
    modal.innerHTML = `
        <div style="padding: 24px 24px 16px 24px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 1.5rem; color: ${borderColor};">${icon}</span>
                <h2 style="margin: 0; color: var(--text-primary); font-size: 1.25rem; font-weight: 600;">${title}</h2>
            </div>
            <button class="notification-close-btn" style="background: none; border: none; font-size: 1.5rem; color: var(--text-secondary); cursor: pointer; padding: 0; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border-radius: 4px; transition: all 0.2s;" title="Close">
                ×
            </button>
        </div>
        <div style="padding: 20px 24px 24px 24px; color: var(--text-primary); white-space: pre-line; overflow-y: auto; max-height: calc(80vh - 100px);">
            ${escapedMessage}
        </div>
        <div style="padding: 16px 24px; border-top: 1px solid var(--border); display: flex; justify-content: flex-end;">
            <button class="notification-ok-btn btn btn-primary" style="padding: 10px 24px; min-width: 100px;">
                OK
            </button>
        </div>
    `;
    
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    
    // Track if modal is closing to prevent multiple closes
    let isClosing = false;
    
    // Close function with guard
    const closeModal = () => {
        // Prevent multiple closes
        if (isClosing) {
            return;
        }
        isClosing = true;
        
        // Disable buttons to prevent further clicks
        const closeBtn = modal.querySelector('.notification-close-btn');
        const okBtn = modal.querySelector('.notification-ok-btn');
        if (closeBtn) closeBtn.disabled = true;
        if (okBtn) okBtn.disabled = true;
        
        // Animate out
        overlay.style.animation = 'fadeOut 0.2s ease-out';
        modal.style.animation = 'slideUp 0.3s ease-out';
        
        // Remove from DOM after animation
        setTimeout(() => {
            if (overlay.parentNode) {
                overlay.parentNode.removeChild(overlay);
            }
            // Clean up event listeners
            document.removeEventListener('keydown', handleEscape);
        }, 300);
    };
    
    // Close button click and hover effects
    const closeBtn = modal.querySelector('.notification-close-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            closeModal();
        });
        closeBtn.addEventListener('mouseenter', () => {
            if (!isClosing) {
                closeBtn.style.background = 'var(--bg-secondary)';
                closeBtn.style.color = 'var(--text-primary)';
            }
        });
        closeBtn.addEventListener('mouseleave', () => {
            if (!isClosing) {
                closeBtn.style.background = 'none';
                closeBtn.style.color = 'var(--text-secondary)';
            }
        });
    }
    
    // OK button click
    const okBtn = modal.querySelector('.notification-ok-btn');
    if (okBtn) {
        okBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            closeModal();
        });
    }
    
    // Close on overlay click (outside modal)
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay && !isClosing) {
            closeModal();
        }
    });
    
    // Prevent modal clicks from closing
    modal.addEventListener('click', (e) => {
        e.stopPropagation();
    });
    
    // Close on Escape key
    const handleEscape = (e) => {
        if (e.key === 'Escape' && !isClosing) {
            closeModal();
        }
    };
    document.addEventListener('keydown', handleEscape);
    
    // Focus the OK button for accessibility
    setTimeout(() => {
        if (okBtn && !isClosing) {
            okBtn.focus();
        }
    }, 100);
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Delete meeting with confirmation
async function confirmDeleteMeeting(meetingId, meetingTitle, projectName) {
    const confirmed = confirm(
        `⚠️ WARNING: This will permanently delete:\n\n` +
        `• Meeting: "${meetingTitle}"\n` +
        `• All Trello cards associated with this meeting\n` +
        `• Confluence page for this meeting\n` +
        `• All action items and decisions\n` +
        `• Meeting files (transcript, summary)\n\n` +
        `This action cannot be undone!\n\n` +
        `Are you sure you want to delete this meeting?`
    );
    
    if (!confirmed) {
        return;
    }
    
    try {
        showToast('Deleting meeting...', 'info');
        
        const response = await fetch(`${API_BASE}/api/summaries/${encodeURIComponent(meetingId)}?confirm=true`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            const result = await response.json();
            showToast(
                `Meeting deleted! Trello: ${result.trello.cards} cards, Confluence: ${result.confluence.page_deleted ? 'page deleted' : 'no page'}`,
                'success'
            );
            // Reload project summaries or go back to projects list
            await loadProjectSummaries(projectName);
            // If we're viewing full summary, switch back to projects view
            switchSection('projects');
            await loadProjects();
        } else {
            const error = await response.json().catch(() => ({ detail: 'Failed to delete meeting' }));
            showToast(`Error: ${error.detail || 'Failed to delete meeting'}`, 'error');
        }
    } catch (error) {
        console.error('Error deleting meeting:', error);
        showToast(`Error: ${error.message}`, 'error');
    }
}

// Make delete function available globally
window.confirmDeleteMeeting = confirmDeleteMeeting;

// Delete project with confirmation
async function confirmDeleteProject(projectName) {
    const confirmed = confirm(
        `⚠️ WARNING: This will permanently delete:\n\n` +
        `• All Trello boards, lists, and cards\n` +
        `• All Confluence pages\n` +
        `• All meeting summaries and action items\n` +
        `• All project files\n\n` +
        `This action cannot be undone!\n\n` +
        `Are you sure you want to delete "${projectName}"?`
    );
    
    if (!confirmed) {
        return;
    }
    
    // Double confirmation
    const doubleConfirm = confirm(
        `Final confirmation: Delete "${projectName}"?\n\n` +
        `Type OK to confirm deletion.`
    );
    
    if (!doubleConfirm) {
        return;
    }
    
    try {
        showToast('Deleting project...', 'info');
        
        const response = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectName)}?confirm=true`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            const result = await response.json();
            showToast(
                `Project deleted! Trello: ${result.trello.boards} boards, Confluence: ${result.confluence.pages} pages`,
                'success'
            );
            await loadProjects(); // Reload project list
        } else {
            const error = await response.json().catch(() => ({ detail: 'Failed to delete project' }));
            showToast(`Error: ${error.detail || 'Failed to delete project'}`, 'error');
        }
    } catch (error) {
        console.error('Error deleting project:', error);
        showToast(`Error: ${error.message}`, 'error');
    }
}

// Extract emails from Trello and Confluence
async function extractProjectEmails(projectName) {
    try {
        showToast('Extracting emails...', 'info');
        
        const response = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectName)}/extract-emails`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            showToast(
                `Extracted ${result.total} emails (Trello: ${result.trello}, Confluence: ${result.confluence})`,
                'success'
            );
            
            // Show email mappings
            await showEmailMappings(projectName);
        } else {
            const error = await response.json().catch(() => ({ detail: 'Failed to extract emails' }));
            showToast(`Error: ${error.detail || 'Failed to extract emails'}`, 'error');
        }
    } catch (error) {
        console.error('Error extracting emails:', error);
        showToast(`Error: ${error.message}`, 'error');
    }
}

// Sync Confluence pages
async function syncConfluence(projectName) {
    try {
        showToast('Syncing Confluence pages...', 'info');
        
        const response = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectName)}/sync-confluence`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const result = await response.json();
            showToast(
                `Synced ${result.checked} pages, removed ${result.removed} deleted pages from DB`,
                'success'
            );
        } else {
            const error = await response.json().catch(() => ({ detail: 'Failed to sync Confluence' }));
            showToast(`Error: ${error.detail || 'Failed to sync Confluence'}`, 'error');
        }
    } catch (error) {
        console.error('Error syncing Confluence:', error);
        showToast(`Error: ${error.message}`, 'error');
    }
}

// Show email mappings
async function showEmailMappings(projectName) {
    try {
        const response = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(projectName)}/email-mappings`);
        
        if (response.ok) {
            const result = await response.json();
            const mappings = result.mappings;
            
            if (Object.keys(mappings).length === 0) {
                showToast('No email mappings found for this project', 'info');
                return;
            }
            
            // Create a simple display
            const mappingList = Object.entries(mappings)
                .map(([name, email]) => `${name}: ${email}`)
                .join('\n');
            
            alert(`Email Mappings for "${projectName}":\n\n${mappingList}`);
        }
    } catch (error) {
        console.error('Error getting email mappings:', error);
    }
}

// Handle Teams URL form submission
async function handleTeamsUrlSubmit(e) {
    e.preventDefault();
    
    const teamsUrl = teamsUrlInput.value.trim();
    if (!teamsUrl) {
        showToast('Please enter a Teams meeting URL', 'error');
        return;
    }
    
    // Validate Teams URL format (basic check - backend will do detailed validation)
    if (!teamsUrl.includes('teams.microsoft.com') && !teamsUrl.includes('microsoft.com/l/')) {
        showToast('Please enter a valid Teams meeting URL. URL must contain "teams.microsoft.com" or "microsoft.com/l/"', 'error');
        return;
    }
    
    // Check for meetup-join in URL
    if (!teamsUrl.includes('/meetup-join/')) {
        showToast('Invalid Teams meeting URL format. URL must contain "/meetup-join/"', 'error');
        return;
    }
    
    // Get project name
    const projectSelect = document.getElementById('teamsProjectName');
    const projectInput = document.getElementById('teamsProjectNameInput');
    let projectName = '';
    
    if (projectSelect && projectSelect.value) {
        projectName = projectSelect.value;
    } else if (projectInput && projectInput.value.trim()) {
        projectName = projectInput.value.trim();
    } else {
        showToast('Please select or enter a project name', 'error');
        return;
    }
    
    // UI Updates
    teamsUrlBtn.disabled = true;
    const btnText = teamsUrlBtn.querySelector('.btn-text');
    const btnLoader = teamsUrlBtn.querySelector('.btn-loader');
    if (btnText) btnText.style.display = 'none';
    if (btnLoader) btnLoader.style.display = 'flex';
    progressBar.style.display = 'block';
    progressFill.style.width = '0%';
    
    const progressPercentage = document.getElementById('progressPercentage');
    const progressMessage = document.getElementById('progressMessage');
    if (progressMessage) progressMessage.textContent = 'Preparing to process Teams URL...';
    
    try {
        showToast('Downloading recordings/transcripts from SharePoint...', 'info');
        
        // Get form values
        const meetingTitle = document.getElementById('teamsMeetingTitle')?.value || '';
        const meetingDate = document.getElementById('teamsMeetingDate')?.value || '';
        const participants = document.getElementById('teamsParticipants')?.value || '';
        const skipSync = document.getElementById('teamsSkipSync')?.checked || false;
        const analyzeProject = document.getElementById('teamsAnalyzeProject')?.checked !== false; // Default to true
        
        const formData = new FormData(teamsUrlForm);
        formData.set('teams_url', teamsUrl);
        formData.set('project_name', projectName);
        formData.set('prefer_transcript', 'true'); // Default to prefer transcript
        
        // Always use SharePoint download endpoint for Teams URLs
        const endpoint = `${API_BASE}/api/transcripts/process-sharepoint-url`;
        
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        // Debug logging
        console.log('Response status:', response.status, response.ok);
        console.log('Response data:', JSON.stringify(data, null, 2));
        console.log('requires_selection:', data.requires_selection, 'type:', typeof data.requires_selection);
        console.log('recordings:', data.recordings);
        console.log('recordings is array:', Array.isArray(data.recordings));
        console.log('recordings length:', data.recordings?.length);
        
        // Check if selection is required FIRST (regardless of response.ok or success)
        // Handle both boolean true and string "true" for requires_selection
        const requiresSelection = data.requires_selection === true || data.requires_selection === 'true' || data.requires_selection === 1;
        const hasRecordings = data.recordings && Array.isArray(data.recordings) && data.recordings.length > 0;
        
        console.log('Selection check:', {
            requiresSelection,
            hasRecordings,
            recordingsCount: data.recordings?.length
        });
        
        if (requiresSelection && hasRecordings) {
            // Hide progress bar
            progressBar.style.display = 'none';
            
            // Show recording selection modal
            try {
                console.log('Attempting to show recording selection modal with', data.recordings.length, 'recordings');
                showRecordingSelectionModal(
                    data.recordings, 
                    data.transcripts || [], 
                    data.process_id, 
                    teamsUrl, 
                    projectName, 
                    meetingTitle, 
                    meetingDate, 
                    participants, 
                    skipSync, 
                    analyzeProject
                );
                console.log('Modal display function called successfully');
                return; // Important: return here to prevent further processing
            } catch (error) {
                console.error('Error showing recording selection modal:', error);
                console.error('Error stack:', error.stack);
                showToast(`Error displaying recording selection: ${error.message}`, 'error');
                return; // Return even on error to prevent showing generic error
            }
        } else {
            console.warn('Selection check failed - will NOT show modal:', {
                requires_selection: data.requires_selection,
                requiresSelection,
                has_recordings: !!data.recordings,
                is_array: Array.isArray(data.recordings),
                length: data.recordings?.length,
                message: data.message
            });
            
            // If the message indicates selection is needed but we didn't show modal, try to show it anyway
            if (data.message && data.message.includes('Found') && data.message.includes('recording') && data.message.includes('Please select')) {
                console.warn('Message indicates selection needed but requires_selection flag not set. Attempting to show modal anyway.');
                if (data.recordings && Array.isArray(data.recordings) && data.recordings.length > 0) {
                    try {
                        progressBar.style.display = 'none';
                        showRecordingSelectionModal(
                            data.recordings, 
                            data.transcripts || [], 
                            data.process_id, 
                            teamsUrl, 
                            projectName, 
                            meetingTitle, 
                            meetingDate, 
                            participants, 
                            skipSync, 
                            analyzeProject
                        );
                        return;
                    } catch (error) {
                        console.error('Error showing modal from message fallback:', error);
                    }
                }
            }
        }
        
        if (response.ok) {
            
            if (data.success) {
                progressFill.style.width = '100%';
                if (progressPercentage) progressPercentage.textContent = '100%';
                
                setTimeout(() => {
                    progressBar.style.display = 'none';
                    showToast('✓ Meeting recordings/transcripts downloaded and processed successfully!', 'success');
                    
                    if (data.summary_id) {
                        loadFullSummary(data.summary_id);
                    } else if (data.summary) {
                        displayResults(data);
                    } else if (data.meeting_details) {
                        // Show meeting details if no transcript was processed
                        displayTeamsMeetingDetails(data.meeting_details);
                    }
                    
                    switchSection('results');
                    navItems.forEach(nav => nav.classList.remove('active'));
                    const resultsNav = Array.from(navItems).find(nav => nav.dataset.section === 'results');
                    if (resultsNav) resultsNav.classList.add('active');
                    loadProjects();
                    loadActionItems();
                }, 500);
            } else if (data.process_id) {
                // Processing is in progress - start polling
                startProgressPolling(data.process_id, progressPercentage);
            } else {
                progressBar.style.display = 'none';
                // Don't show error if it's just a selection requirement message
                const requiresSelection = data.requires_selection === true || data.requires_selection === 'true' || data.requires_selection === 1;
                if (!requiresSelection) {
                    // Check if message indicates selection is needed
                    const message = data.detail || data.message || 'Unknown error';
                    if (!(message.includes('Found') && message.includes('recording') && message.includes('Please select'))) {
                        showToast(`Error: ${message}`, 'error');
                    }
                }
            }
        } else {
            progressBar.style.display = 'none';
            
            // Don't show error if selection is required (should have been handled above)
            if (data.requires_selection) {
                console.warn('Selection required but modal not shown. Data:', data);
                return;
            }
            
            const errorMessage = data.detail || data.message || 'Unknown error';
            
            // Provide user-friendly error messages for common cases
            let friendlyMessage = errorMessage;
            if (errorMessage.includes('Found') && errorMessage.includes('recording') && errorMessage.includes('Please select')) {
                // This is a selection requirement message, not an error
                console.warn('Selection message treated as error. Data:', data);
                return;
            } else if (errorMessage.includes('No recordings or transcripts found')) {
                friendlyMessage = 'No recordings or transcripts found for this meeting.\n\n' +
                    'Possible reasons:\n' +
                    '• Recording may not be available yet (can take a few hours after meeting ends)\n' +
                    '• Recording may be stored in a different location\n' +
                    '• Meeting title may not match exactly\n' +
                    '• Recording may have been deleted or moved';
            } else if (errorMessage.includes('too short') || errorMessage.includes('less than 10 seconds')) {
                friendlyMessage = 'Recording is too short (less than 10 seconds).\n\n' +
                    'This usually means:\n' +
                    '• The recording may be incomplete\n' +
                    '• The file may be corrupted\n' +
                    '• Please ensure the meeting recording is complete';
            } else if (errorMessage.includes('Invalid Teams meeting URL') || errorMessage.includes('Invalid URL')) {
                friendlyMessage = 'Invalid Teams meeting URL format.\n\n' +
                    'Please ensure:\n' +
                    '• URL contains "teams.microsoft.com" or "microsoft.com/l/"\n' +
                    '• URL contains "/meetup-join/"\n' +
                    '• URL is a complete Teams meeting join link';
            }
            
            showToast(friendlyMessage, 'error');
        }
    } catch (error) {
        progressBar.style.display = 'none';
        let errorMessage = error.message || 'An unexpected error occurred';
        
        // Handle network errors
        if (error.message.includes('fetch') || error.message.includes('network')) {
            errorMessage = 'Network error. Please check your connection and try again.';
        }
        
        showToast(`Error: ${errorMessage}`, 'error');
    } finally {
        teamsUrlBtn.disabled = false;
        if (btnText) btnText.style.display = 'inline';
        if (btnLoader) btnLoader.style.display = 'none';
    }
}

// Recording Selection Modal Functions
let currentRecordingsData = null;
let currentSelectionContext = null;

function showRecordingSelectionModal(recordings, transcripts, processId, teamsUrl, projectName, meetingTitle, meetingDate, participants, skipSync, analyzeProject) {
    console.log('showRecordingSelectionModal called with:', {
        recordingsCount: recordings?.length,
        processId,
        hasModal: !!document.getElementById('recordingSelectionModal')
    });
    
    const modal = document.getElementById('recordingSelectionModal');
    const messageEl = document.getElementById('recordingSelectionMessage');
    const recordingsContainer = document.getElementById('recordingsList');
    
    if (!modal) {
        console.error('Modal element not found: recordingSelectionModal');
        showToast('Error: Could not display recording selection modal - modal element missing', 'error');
        return;
    }
    
    if (!messageEl) {
        console.error('Message element not found: recordingSelectionMessage');
        showToast('Error: Could not display recording selection modal - message element missing', 'error');
        return;
    }
    
    if (!recordingsContainer) {
        console.error('Recordings container not found: recordingsList');
        showToast('Error: Could not display recording selection modal - recordings container missing', 'error');
        return;
    }
    
    if (!recordings || !Array.isArray(recordings) || recordings.length === 0) {
        console.error('Invalid recordings data:', recordings);
        showToast('Error: No recordings data provided', 'error');
        return;
    }
    
    currentRecordingsData = recordings;
    currentSelectionContext = {
        processId,
        teamsUrl,
        projectName,
        meetingTitle,
        meetingDate,
        participants,
        skipSync,
        analyzeProject
    };
    
    // Set initial message for "Latest Only" filter (default)
    messageEl.textContent = `Found 1 recording(s) matching the filter. All matching recordings will be processed automatically.`;
    
    // Render recordings list
    try {
        renderRecordingsList(recordings, 'latest');
    } catch (error) {
        console.error('Error rendering recordings list:', error);
        showToast('Error rendering recordings list', 'error');
        return;
    }
    
    // Show modal
    try {
        modal.style.display = 'flex';
        console.log('Modal displayed successfully');
    } catch (error) {
        console.error('Error displaying modal:', error);
        showToast('Error displaying modal', 'error');
        return;
    }
    
    // Setup filter buttons
    try {
        setupFilterButtons(recordings);
    } catch (error) {
        console.error('Error setting up filter buttons:', error);
    }
    
    // Setup confirm/cancel buttons
    try {
        setupSelectionButtons();
    } catch (error) {
        console.error('Error setting up selection buttons:', error);
    }
}

function renderRecordingsList(recordings, filterType) {
    const container = document.getElementById('recordingsList');
    container.innerHTML = '';
    
    let filteredRecordings = [...recordings];
    const now = new Date();
    
    // Determine if this is a manual selection mode
    const isManualMode = filterType === 'manual';
    
    // Apply filter
    if (filterType === 'latest') {
        // Sort by modified date (newest first) and take first
        const sorted = [...recordings].sort((a, b) => {
            return new Date(b.modified) - new Date(a.modified);
        });
        filteredRecordings = [sorted[0]];
    } else if (filterType === '7days') {
        const cutoffDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        filteredRecordings = recordings.filter(r => new Date(r.modified) >= cutoffDate);
    } else if (filterType === '30days') {
        const cutoffDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        filteredRecordings = recordings.filter(r => new Date(r.modified) >= cutoffDate);
    } else if (filterType === '90days') {
        const cutoffDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
        filteredRecordings = recordings.filter(r => new Date(r.modified) >= cutoffDate);
    } else if (filterType === 'all') {
        filteredRecordings = recordings;
    } else if (filterType === 'manual') {
        // Show all recordings for manual selection
        filteredRecordings = recordings;
    }
    
    // Sort by modified date (newest first)
    filteredRecordings.sort((a, b) => new Date(b.modified) - new Date(a.modified));
    
    // For non-manual filters, automatically select all filtered recordings
    const shouldAutoSelect = !isManualMode;
    
    filteredRecordings.forEach((recording, idx) => {
        const recordingEl = document.createElement('div');
        recordingEl.className = 'recording-item';
        const cursorStyle = isManualMode ? 'cursor: pointer;' : 'cursor: default;';
        recordingEl.style.cssText = `padding: 12px; margin-bottom: 8px; border: 2px solid var(--border, #ddd); border-radius: 8px; ${cursorStyle} transition: all 0.2s;`;
        recordingEl.dataset.index = recording.index;
        
        // Parse modified date safely
        let modifiedDateStr = 'Unknown';
        let sizeMB = '0.00';
        try {
            if (recording.modified) {
                const modifiedDate = new Date(recording.modified);
                modifiedDateStr = modifiedDate.toLocaleString();
            }
        } catch (e) {
            modifiedDateStr = recording.modified || 'Unknown';
        }
        
        try {
            if (recording.size && recording.size > 0) {
                sizeMB = (recording.size / 1024 / 1024).toFixed(2);
            }
        } catch (e) {
            sizeMB = '0.00';
        }
        
        // Auto-select for non-manual filters
        const isChecked = shouldAutoSelect ? 'checked' : '';
        const checkboxDisabled = shouldAutoSelect ? 'disabled' : '';
        const checkboxStyle = shouldAutoSelect 
            ? 'margin-top: 4px; width: 20px; height: 20px; cursor: not-allowed; opacity: 0.6;'
            : 'margin-top: 4px; width: 20px; height: 20px; cursor: pointer;';
        
        recordingEl.innerHTML = `
            <div style="display: flex; align-items: start; gap: 12px;">
                <input type="checkbox" class="recording-checkbox" data-index="${recording.index}" 
                       style="${checkboxStyle}"
                       ${isChecked} ${checkboxDisabled}>
                <div style="flex: 1;">
                    <div style="font-weight: 600; margin-bottom: 4px;">${escapeHtml(recording.name || 'Unknown')}</div>
                    <div style="font-size: 0.875rem; color: var(--text-secondary);">
                        <span>📅 ${modifiedDateStr}</span> | 
                        <span>📊 ${sizeMB} MB</span> | 
                        <span>📍 ${escapeHtml(recording.source || 'Unknown')}</span>
                    </div>
                </div>
            </div>
        `;
        
        // Only allow clicking/toggling in manual mode
        if (isManualMode) {
            recordingEl.addEventListener('click', (e) => {
                if (e.target.type !== 'checkbox') {
                    const checkbox = recordingEl.querySelector('.recording-checkbox');
                    checkbox.checked = !checkbox.checked;
                    updateSelectionCount();
                }
            });
            
            recordingEl.querySelector('.recording-checkbox').addEventListener('change', updateSelectionCount);
        }
        
        container.appendChild(recordingEl);
    });
    
    updateSelectionCount();
}

function setupFilterButtons(recordings) {
    const filterButtons = document.querySelectorAll('.filter-btn');
    const messageEl = document.getElementById('recordingSelectionMessage');
    
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            // Update active state
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Re-render list with new filter
            const filterType = btn.dataset.filter;
            renderRecordingsList(recordings, filterType);
            
            // Update message based on filter type
            if (filterType === 'manual') {
                messageEl.textContent = `Found ${recordings.length} recording(s). Please select which ones to process.`;
            } else {
                const filteredCount = getFilteredCount(recordings, filterType);
                messageEl.textContent = `Found ${filteredCount} recording(s) matching the filter. All matching recordings will be processed automatically.`;
            }
        });
    });
}

function getFilteredCount(recordings, filterType) {
    const now = new Date();
    
    if (filterType === 'latest') {
        return 1;
    } else if (filterType === '7days') {
        const cutoffDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        return recordings.filter(r => new Date(r.modified) >= cutoffDate).length;
    } else if (filterType === '30days') {
        const cutoffDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
        return recordings.filter(r => new Date(r.modified) >= cutoffDate).length;
    } else if (filterType === '90days') {
        const cutoffDate = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
        return recordings.filter(r => new Date(r.modified) >= cutoffDate).length;
    } else if (filterType === 'all') {
        return recordings.length;
    } else {
        return recordings.length;
    }
}

function updateSelectionCount() {
    const checkboxes = document.querySelectorAll('.recording-checkbox:checked');
    const count = checkboxes.length;
    document.getElementById('selectedCount').textContent = count;
    
    const confirmBtn = document.getElementById('confirmRecordingSelection');
    confirmBtn.disabled = count === 0;
}

function setupSelectionButtons() {
    const confirmBtn = document.getElementById('confirmRecordingSelection');
    const cancelBtn = document.getElementById('cancelRecordingSelection');
    const closeBtn = document.getElementById('closeRecordingModal');
    
    const closeModal = (keepProgressBar = false) => {
        document.getElementById('recordingSelectionModal').style.display = 'none';
        
        if (!keepProgressBar) {
            // Only reset button state and hide progress bar if not processing
            teamsUrlBtn.disabled = false;
            const btnText = teamsUrlBtn.querySelector('.btn-text');
            const btnLoader = teamsUrlBtn.querySelector('.btn-loader');
            if (btnText) btnText.style.display = 'inline';
            if (btnLoader) btnLoader.style.display = 'none';
            progressBar.style.display = 'none';
        }
    };
    
    cancelBtn.onclick = () => closeModal(false);
    closeBtn.onclick = () => closeModal(false);
    
    confirmBtn.onclick = async () => {
        const checkboxes = document.querySelectorAll('.recording-checkbox:checked');
        const selectedIndices = Array.from(checkboxes).map(cb => cb.dataset.index).join(',');
        
        if (selectedIndices.length === 0) {
            showToast('Please select at least one recording', 'error');
            return;
        }
        
        // Close modal immediately when user clicks "Process Selected"
        // Keep progress bar visible (don't reset button state yet)
        document.getElementById('recordingSelectionModal').style.display = 'none';
        
        // Show progress bar immediately on upload page
        progressBar.style.display = 'block';
        progressFill.style.width = '0%';
        const progressPercentage = document.getElementById('progressPercentage');
        const progressMessage = document.getElementById('progressMessage');
        if (progressPercentage) progressPercentage.textContent = '0%';
        if (progressMessage) progressMessage.textContent = 'Preparing to process selected recordings...';
        
        // Process selected recordings
        await processSelectedRecordings(selectedIndices);
    };
}

async function processSelectedRecordings(selectedIndices) {
    const ctx = currentSelectionContext;
    if (!ctx) return;
    
    // Ensure button shows loading state
    teamsUrlBtn.disabled = true;
    const btnText = teamsUrlBtn.querySelector('.btn-text');
    const btnLoader = teamsUrlBtn.querySelector('.btn-loader');
    if (btnText) btnText.style.display = 'none';
    if (btnLoader) btnLoader.style.display = 'flex';
    
    // Ensure progress bar is visible (should already be visible from modal close)
    progressBar.style.display = 'block';
    progressFill.style.width = '5%';
    
    const progressPercentage = document.getElementById('progressPercentage');
    const progressMessage = document.getElementById('progressMessage');
    if (progressPercentage) progressPercentage.textContent = '5%';
    if (progressMessage) progressMessage.textContent = 'Processing selected recordings...';
    
    try {
        showToast('Processing selected recordings...', 'info');
        
        const formData = new FormData(teamsUrlForm);
        formData.set('teams_url', ctx.teamsUrl);
        formData.set('project_name', ctx.projectName);
        formData.set('selected_recording_indices', selectedIndices);
        if (ctx.meetingTitle) formData.set('meeting_title', ctx.meetingTitle);
        if (ctx.meetingDate) formData.set('meeting_date', ctx.meetingDate);
        if (ctx.participants) formData.set('participants', ctx.participants);
        formData.set('skip_sync', ctx.skipSync);
        formData.set('analyze_project', ctx.analyzeProject);
        formData.set('prefer_transcript', 'true'); // Default to prefer transcript
        
        const response = await fetch(`${API_BASE}/api/transcripts/process-sharepoint-url`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            if (data.success) {
                // Clear any existing polling if processing completed immediately
                if (window.currentProgressInterval) {
                    clearInterval(window.currentProgressInterval);
                    window.currentProgressInterval = null;
                    window.currentPollingProcessId = null;
                }
                
                progressFill.style.width = '100%';
                if (progressPercentage) progressPercentage.textContent = '100%';
                
                setTimeout(() => {
                    progressBar.style.display = 'none';
                    const selectedCount = selectedIndices.split(',').length;
                    showToast(`✓ Successfully processed ${selectedCount} recording(s) sequentially!`, 'success');
                    
                    // Display all summaries if multiple were processed
                    if (data.summaries && data.summaries.length > 1) {
                        displayMultipleResults(data.summaries, data.summary_ids || []);
                    } else if (data.summary_id) {
                        loadFullSummary(data.summary_id);
                    } else if (data.summary) {
                        displayResults(data);
                    }
                    
                    switchSection('results');
                    navItems.forEach(nav => nav.classList.remove('active'));
                    const resultsNav = Array.from(navItems).find(nav => nav.dataset.section === 'results');
                    if (resultsNav) resultsNav.classList.add('active');
                    loadProjects();
                    loadActionItems();
                }, 500);
            } else if (data.process_id && !data.success) {
                // Processing is in progress - start polling for progress updates
                // Only start polling if success is false (processing still ongoing)
                console.log('Processing in progress, starting polling for process_id:', data.process_id);
                startProgressPolling(data.process_id, progressPercentage);
            } else {
                progressBar.style.display = 'none';
                showToast(`Error: ${data.detail || data.message || 'Unknown error'}`, 'error');
            }
        } else {
            progressBar.style.display = 'none';
            showToast(`Error: ${data.detail || data.message || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        progressBar.style.display = 'none';
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        teamsUrlBtn.disabled = false;
        if (btnText) btnText.style.display = 'inline';
        if (btnLoader) btnLoader.style.display = 'none';
    }
}

// Display Teams meeting details (when no transcript file provided)
function displayTeamsMeetingDetails(meetingDetails) {
    const startDate = meetingDetails.startDateTime 
        ? new Date(meetingDetails.startDateTime).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        })
        : 'Unknown';
    
    const endDate = meetingDetails.endDateTime 
        ? new Date(meetingDetails.endDateTime).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        })
        : 'Unknown';
    
    resultsContent.innerHTML = `
        <div class="summary-card">
            <div class="summary-header">
                <div>
                    <div class="summary-title">${escapeHtml(meetingDetails.subject || 'Teams Meeting')}</div>
                    <div class="summary-meta">
                        <span class="meta-item">📅 Start: ${startDate}</span>
                        <span class="meta-item">📅 End: ${endDate}</span>
                        ${meetingDetails.participants && meetingDetails.participants.length > 0 
                            ? `<span class="meta-item">👥 ${meetingDetails.participants.length} participant${meetingDetails.participants.length !== 1 ? 's' : ''}</span>` 
                            : ''}
                    </div>
                </div>
                <div class="summary-actions">
                    ${meetingDetails.joinWebUrl 
                        ? `<a href="${escapeHtml(meetingDetails.joinWebUrl)}" target="_blank" class="btn btn-secondary btn-icon"><span class="btn-icon">🔗</span>Open in Teams</a>` 
                        : ''}
                </div>
            </div>
            
            <div class="summary-content">
                <h3>Meeting Details</h3>
                
                ${meetingDetails.organizer && meetingDetails.organizer.displayName 
                    ? `<p><strong>Organizer:</strong> ${escapeHtml(meetingDetails.organizer.displayName)}</p>` 
                    : ''}
                
                ${meetingDetails.participants && meetingDetails.participants.length > 0 
                    ? `
                    <h3>Participants</h3>
                    <ul style="list-style: none; padding: 0;">
                        ${meetingDetails.participants.map(p => `<li style="padding: 8px 0; border-bottom: 1px solid var(--border);">👤 ${escapeHtml(p)}</li>`).join('')}
                    </ul>
                    ` 
                    : ''}
                
                ${meetingDetails.recording 
                    ? `
                    <h3>Recording</h3>
                    <p>A recording is available for this meeting.</p>
                    ` 
                    : '<p><em>No transcript file was provided. Upload a transcript file to generate a summary.</em></p>'}
            </div>
        </div>
    `;
}

// Make functions available globally
window.loadProjectSummaries = loadProjectSummaries;
window.confirmDeleteProject = confirmDeleteProject;
window.extractProjectEmails = extractProjectEmails;
window.syncConfluence = syncConfluence;
