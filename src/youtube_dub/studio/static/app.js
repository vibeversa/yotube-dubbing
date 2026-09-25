async function fetchJobs() {
    const res = await fetch('/api/jobs');
    const jobs = await res.json();
    renderJobs(jobs);
}

function renderJobs(jobs) {
    const list = document.getElementById('jobsList');
    list.innerHTML = '';

    if (jobs.length === 0) {
        list.innerHTML = '<p>No jobs found.</p>';
        return;
    }

    jobs.forEach(jobData => {
        const manifest = jobData.manifest;
        const failure = jobData.failure;

        let statusClass = '';
        if (manifest.status === 'FAILED') statusClass = 'failed';
        else if (manifest.status === 'COMPLETED') statusClass = 'completed';
        else if (manifest.status === 'RUNNING') statusClass = 'running';

        const card = document.createElement('div');
        card.className = `job-card ${statusClass}`;

        let html = `<strong>Job ID:</strong> ${manifest.job_id} <br>`;
        html += `<strong>Status:</strong> ${manifest.status} <br>`;
        html += `<strong>Stage:</strong> ${manifest.current_stage} <br>`;
        html += `<strong>Langs:</strong> ${manifest.source_language} -> ${manifest.target_language} <br><br>`;

        if (failure) {
            html += `<div style="color: red;">
                        <strong>Error in ${failure.stage}:</strong> ${failure.message}
                     </div>`;
        }

        // Actions
        if (manifest.status === 'CREATED' || manifest.status === 'CANCELLED') {
            html += `<button class="btn" onclick="runJob('${manifest.job_id}')">Run</button>`;
        } else if (manifest.status === 'RUNNING') {
            html += `<button class="btn" onclick="cancelJob('${manifest.job_id}')">Cancel</button>`;
        } else if (manifest.status === 'FAILED') {
            html += `<button class="btn" onclick="retryJob('${manifest.job_id}')">Retry</button>`;
        } else if (manifest.status === 'COMPLETED') {
             html += `<a href="/api/jobs/${manifest.job_id}/artifacts/render" target="_blank"><button class="btn">Download Video</button></a>`;
        }

        card.innerHTML = html;
        list.appendChild(card);
    });
}

async function createJob() {
    const source = document.getElementById('sourceLang').value;
    const target = document.getElementById('targetLang').value;

    await fetch('/api/jobs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({source_language: source, target_language: target})
    });
    fetchJobs();
}

async function runJob(jobId) {
    await fetch(`/api/jobs/${jobId}/run`, { method: 'POST' });
    fetchJobs();
}

async function cancelJob(jobId) {
    await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
    fetchJobs();
}

async function retryJob(jobId) {
    await fetch(`/api/jobs/${jobId}/retry`, { method: 'POST' });
    fetchJobs();
}

// Poll every 3 seconds
setInterval(fetchJobs, 3000);
fetchJobs();
