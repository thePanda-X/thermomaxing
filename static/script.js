const STEPS = [
    { id: 'fetch_recipe', label: 'Fetching recipe page' },
    { id: 'extract_ingredients', label: 'Extracting ingredients' },
    { id: 'analyze_instructions', label: 'Analyzing instructions' },
    { id: 'save_to_collection', label: 'Saving to your collection' }
];

const STATUS_COPY = {
    pending: 'Pending',
    in_progress: 'In progress',
    completed: 'Completed',
    failed: 'Failed'
};

let eventSource;

// Initialize icons on load
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
});

function startImport() {
    cleanupStream();
    const urlInput = document.getElementById('recipe-url');
    const url = urlInput.value.trim();
    const btn = document.getElementById('import-btn');
    const progressContainer = document.getElementById('progress-container');

    if (!url) {
        handleFailure("Please enter a valid URL");
        return;
    }

    // Reset UI
    renderSteps();
    progressContainer.classList.remove('hidden');
    btn.classList.add('loading');
    btn.disabled = true;
    urlInput.disabled = true;

    eventSource = new EventSource(`/import?url=${encodeURIComponent(url)}`);

    eventSource.onmessage = function (event) {
        const data = JSON.parse(event.data);

        if (data.error) {
            handleFailure(data.error);
            return;
        }

        if (data.step && data.status) {
            updateStepStatus(data.step, data.status, data.detail);
            if (data.status === 'failed') {
                handleFailure(data.detail || 'Import failed');
            }
            return;
        }

        if (data.event === 'done') {
            handleSuccess();
        }
    };

    eventSource.onerror = function () {
        handleFailure('Connection lost.');
    };
}

function renderSteps() {
    const list = document.getElementById('steps-list');
    list.innerHTML = '';

    STEPS.forEach((step, index) => {
        const li = document.createElement('li');
        li.className = 'step pending';
        li.dataset.step = step.id;

        li.innerHTML = `
            <div class="step-main">
                <div class="step-icon-wrapper">
                    <div class="step-number">${index + 1}</div>
                    <div class="step-spinner hidden"><i data-lucide="loader-2" width="16" height="16"></i></div>
                    <div class="step-check hidden"><i data-lucide="check" width="16" height="16"></i></div>
                    <div class="step-error hidden"><i data-lucide="x" width="16" height="16"></i></div>
                </div>
                <div class="step-text">
                    <div class="step-label">${step.label}</div>
                    <div class="step-sub">${STATUS_COPY.pending}</div>
                </div>
            </div>
        `;

        list.appendChild(li);
    });
    lucide.createIcons();
}

function updateStepStatus(stepId, status, detail) {
    const stepEl = document.querySelector(`[data-step="${stepId}"]`);
    if (!stepEl) return;

    ['pending', 'in_progress', 'completed', 'failed'].forEach(s => stepEl.classList.remove(s));
    stepEl.classList.add(status);

    const sub = stepEl.querySelector('.step-sub');
    sub.textContent = detail || STATUS_COPY[status] || '';

    // Icon handling
    const numberEl = stepEl.querySelector('.step-number');
    const spinnerEl = stepEl.querySelector('.step-spinner');
    const checkEl = stepEl.querySelector('.step-check');
    const errorEl = stepEl.querySelector('.step-error');

    if (status === 'completed') {
        numberEl.classList.add('hidden');
        spinnerEl.classList.add('hidden');
        checkEl.classList.remove('hidden');
        errorEl.classList.add('hidden');
    } else if (status === 'failed') {
        numberEl.classList.add('hidden');
        spinnerEl.classList.add('hidden');
        checkEl.classList.add('hidden');
        errorEl.classList.remove('hidden');
    } else if (status === 'in_progress') {
        numberEl.classList.add('hidden');
        spinnerEl.classList.remove('hidden');
        checkEl.classList.add('hidden');
        errorEl.classList.add('hidden');
    } else {
        numberEl.classList.remove('hidden');
        spinnerEl.classList.add('hidden');
        checkEl.classList.add('hidden');
        errorEl.classList.add('hidden');
    }
    
    // Re-initialize icons for the newly visible spinner
    lucide.createIcons();
}

function handleSuccess() {
    cleanupStream();
    const btn = document.getElementById('import-btn');
    const urlInput = document.getElementById('recipe-url');
    btn.classList.remove('loading');
    urlInput.disabled = false;
    btn.disabled = false;
    setTimeout(() => {
        document.getElementById('success-overlay').classList.remove('hidden');
        lucide.createIcons();
    }, 250);
}

function handleFailure(message) {
    cleanupStream();
    const btn = document.getElementById('import-btn');
    const urlInput = document.getElementById('recipe-url');
    const errorModal = document.getElementById('error-overlay');
    const errorMsg = document.getElementById('error-modal-message');
    
    errorMsg.textContent = message || 'Something went wrong.';
    errorModal.classList.remove('hidden');
    
    btn.classList.remove('loading');
    btn.disabled = false;
    urlInput.disabled = false;
    lucide.createIcons();
}

function cleanupStream() {
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
}

function resetUI() {
    cleanupStream();
    document.getElementById('success-overlay').classList.add('hidden');
    document.getElementById('error-overlay').classList.add('hidden');
    document.getElementById('progress-container').classList.add('hidden');
    document.getElementById('recipe-url').value = '';
    document.getElementById('recipe-url').disabled = false;
    document.getElementById('import-btn').disabled = false;
}