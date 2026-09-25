async function fetchJobs() {
    const res = await fetch('/api/jobs');
    const jobs = await res.json();
    renderJobs(jobs);
}

const pipelineStages = [
    'SOURCE_READY',
    'TRANSCRIBED',
    'SEGMENTED',
    'TRANSLATED',
    'TTS_PARTIAL',
    'TIMED',
    'MIXED',
    'RENDERED',
    'COMPLETED'
];

function renderJobs(jobs) {
    const list = document.getElementById('jobsList');
    list.innerHTML = '';

    if (jobs.length === 0) {
        list.textContent = 'No jobs found.';
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

        const infoDiv = document.createElement('div');
        infoDiv.innerHTML = `<strong>Job ID:</strong> <span class="job-id"></span> <br>
                             <strong>Status:</strong> <span class="job-status"></span> <br>
                             <strong>Langs:</strong> <span class="job-langs"></span> <br>
                             <strong>Created At:</strong> <span class="job-created"></span> <br>
                             <strong>Updated At:</strong> <span class="job-updated"></span> <br><br>`;
        infoDiv.querySelector('.job-id').textContent = manifest.job_id;
        infoDiv.querySelector('.job-status').textContent = manifest.status;
        infoDiv.querySelector('.job-langs').textContent = `${manifest.source_language} -> ${manifest.target_language}`;
        infoDiv.querySelector('.job-created').textContent = manifest.created_at;
        infoDiv.querySelector('.job-updated').textContent = manifest.updated_at;
        card.appendChild(infoDiv);

        // Pipeline Stepper
        const stepperDiv = document.createElement('div');
        stepperDiv.style.marginBottom = '15px';
        stepperDiv.style.fontSize = '0.9em';
        stepperDiv.style.color = '#555';

        const currentStageIndex = pipelineStages.indexOf(manifest.current_stage);

        let stepperHTML = '<strong>Pipeline:</strong> ';
        pipelineStages.forEach((stage, index) => {
            let stageStyle = '';
            if (index < currentStageIndex) {
                stageStyle = 'color: green;';
            } else if (index === currentStageIndex) {
                stageStyle = 'font-weight: bold; color: blue;';
                if (manifest.status === 'FAILED') {
                    stageStyle = 'font-weight: bold; color: red;';
                }
            }
            stepperHTML += `<span style="${stageStyle}">${stage}</span>`;
            if (index < pipelineStages.length - 1) {
                stepperHTML += ' &rarr; ';
            }
        });
        stepperDiv.innerHTML = stepperHTML;
        card.appendChild(stepperDiv);

        if (failure) {
            const errorDiv = document.createElement('div');
            errorDiv.style.color = 'red';
            errorDiv.style.marginBottom = '10px';
            errorDiv.innerHTML = `<strong>Error in <span class="fail-stage"></span>:</strong> <span class="fail-message"></span>`;
            errorDiv.querySelector('.fail-stage').textContent = failure.stage;
            errorDiv.querySelector('.fail-message').textContent = failure.message;
            card.appendChild(errorDiv);
        }

        const actionsDiv = document.createElement('div');

        // Actions
        if (manifest.status === 'CREATED' || manifest.status === 'CANCELLED') {
            const runBtn = document.createElement('button');
            runBtn.className = 'btn';
            runBtn.textContent = 'Run';
            runBtn.onclick = () => runJob(manifest.job_id);
            actionsDiv.appendChild(runBtn);
        } else if (manifest.status === 'RUNNING') {
            const cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.onclick = () => cancelJob(manifest.job_id);
            actionsDiv.appendChild(cancelBtn);
        } else if (manifest.status === 'FAILED') {
            const retryBtn = document.createElement('button');
            retryBtn.className = 'btn';
            retryBtn.textContent = 'Retry';
            retryBtn.onclick = () => retryJob(manifest.job_id);
            actionsDiv.appendChild(retryBtn);
        } else if (manifest.status === 'COMPLETED') {
            const downloadLink = document.createElement('a');
            downloadLink.href = `/api/jobs/${manifest.job_id}/artifacts/render`;
            downloadLink.target = '_blank';
            const downloadBtn = document.createElement('button');
            downloadBtn.className = 'btn';
            downloadBtn.textContent = 'Download Video';
            downloadLink.appendChild(downloadBtn);
            actionsDiv.appendChild(downloadLink);
        }

        card.appendChild(actionsDiv);
        list.appendChild(card);
    });
}

async function createJob() {
    const source = document.getElementById('sourceLang').value;
    const target = document.getElementById('targetLang').value;
    const sourceUrl = document.getElementById('sourceUrl').value;
    const localPath = document.getElementById('localPath').value;

    const btn = document.getElementById('createBtn');
    const status = document.getElementById('createStatus');
    const error = document.getElementById('createError');

    btn.disabled = true;
    status.textContent = 'Creating job...';
    error.textContent = '';

    try {
        const body = {
            source_language: source,
            target_language: target
        };
        if (sourceUrl) body.source_url = sourceUrl;
        if (localPath) body.local_path = localPath;

        const response = await fetch('/api/jobs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Failed to create job');
        }

        // Clear inputs on success
        document.getElementById('sourceUrl').value = '';
        document.getElementById('localPath').value = '';
        status.textContent = 'Success!';
        setTimeout(() => status.textContent = '', 3000);
    } catch (err) {
        error.textContent = err.message;
        status.textContent = '';
    } finally {
        btn.disabled = false;
        fetchJobs();
    }
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
