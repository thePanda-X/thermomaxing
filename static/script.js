function startImport() {
    const urlInput = document.getElementById('recipe-url');
    const url = urlInput.value.trim();
    const btn = document.getElementById('import-btn');
    const errorMsg = document.getElementById('error-message');
    const statusContainer = document.getElementById('status-container');
    const aiContainer = document.getElementById('ai-container'); // Renamed for consistency
    const statusLog = document.getElementById('status-log');
    const codeBlock = document.getElementById('ai-code-block'); // Get the code block directly

    if (!url) {
        errorMsg.textContent = "Please enter a valid URL";
        return;
    }

    // Reset UI
    errorMsg.textContent = "";
    statusLog.innerHTML = "";
    // --- THIS IS THE FIX ---
    // Instead of clearing the parent div, clear the text of the code block
    codeBlock.innerText = ""; 
    // ----------------------
    statusContainer.classList.remove('hidden');
    aiContainer.classList.remove('hidden');
    btn.classList.add('loading');
    btn.disabled = true;
    urlInput.disabled = true;

    const eventSource = new EventSource(`/import?url=${encodeURIComponent(url)}`);

    eventSource.onmessage = function (event) {
        const data = JSON.parse(event.data);
        console.log("Received event:", data);
        if (data.message && !(data.message == "DONE")) {
            addLog(data.message);
        } else if (data.ai) {
            addAiLog(data.ai);
        } else if (data.error) {
            addLog(`Error: ${data.error}`, 'error');
            eventSource.close();
            btn.classList.remove('loading');
            btn.disabled = false;
            urlInput.disabled = false;
        } else if (data.message == "DONE") {
            addLog("Import completed successfully!", 'success');
            eventSource.close();
            btn.classList.remove('loading');
            setTimeout(() => {
                document.getElementById('success-overlay').classList.remove('hidden');
            }, 500);
        }
    };

    eventSource.onerror = function () {
        addLog("Connection lost.", 'error');
        eventSource.close();
        btn.classList.remove('loading');
        btn.disabled = false;
        urlInput.disabled = false;
    };
}

// No changes needed for the functions below
function addLog(message, type = 'info') {
    const log = document.getElementById('status-log');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `> ${message}`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function addAiLog(message, type = 'info') {
    const log = document.getElementById('ai-log');
    const codeBlock = document.getElementById('ai-code-block');
    codeBlock.innerText += message;
    log.scrollTop = log.scrollHeight;
}

function resetUI() {
    document.getElementById('success-overlay').classList.add('hidden');
    document.getElementById('status-container').classList.add('hidden');
    document.getElementById('ai-container').classList.add('hidden');
    document.getElementById('recipe-url').value = "";
    document.getElementById('recipe-url').disabled = false;
    document.getElementById('import-btn').disabled = false;
}