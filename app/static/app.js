/**
 * ConsultBae AI Automation Platform - Frontend Application Logic
 * Audio Recording, Web Audio API Visualizer, Submissions Explorer, Unified Candidates Table
 */

document.addEventListener('DOMContentLoaded', () => {
  // Global State
  let currentAudioBlob = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let audioContext = null;
  let analyser = null;
  let animationFrameId = null;
  let recordingStartTime = null;
  let timerInterval = null;
  let isRecording = false;

  // DOM Elements - Nav
  const navTabs = document.querySelectorAll('.nav-tab');
  const tabPanels = document.querySelectorAll('.tab-panel');
  const submissionsCountBadge = document.getElementById('submissions-count');
  const candidatesCountBadge = document.getElementById('candidates-count');

  // DOM Elements - Audio Submission Form
  const audioForm = document.getElementById('audio-submit-form');
  const workerNameInput = document.getElementById('worker_name');
  const phoneInput = document.getElementById('phone');
  const btnModeMic = document.getElementById('btn-mode-mic');
  const btnModeFile = document.getElementById('btn-mode-file');
  const recordingArea = document.getElementById('recording-area');
  const uploadArea = document.getElementById('upload-area');
  const btnStartRecord = document.getElementById('btn-start-record');
  const btnStopRecord = document.getElementById('btn-stop-record');
  const btnResetRecord = document.getElementById('btn-reset-record');
  const recordingTimer = document.getElementById('recording-timer');
  const visualizerCanvas = document.getElementById('audio-visualizer');
  const micPreviewContainer = document.getElementById('mic-preview-container');
  const micAudioPlayer = document.getElementById('mic-audio-player');
  const dropZone = document.getElementById('audio-drop-zone');
  const audioFileInput = document.getElementById('audio_file_input');
  const fileInfoPreview = document.getElementById('file-info-preview');
  const selectedFileName = document.getElementById('selected-file-name');
  const selectedFileSize = document.getElementById('selected-file-size');
  const btnClearFile = document.getElementById('btn-clear-file');
  const btnSubmitAudio = document.getElementById('btn-submit-audio');

  // DOM Elements - Results Card
  const resultsPlaceholder = document.getElementById('results-placeholder');
  const resultsDisplay = document.getElementById('results-display');
  const resVerdictBanner = document.getElementById('res-verdict-banner');
  const resVerdictTitle = document.getElementById('res-verdict-title');
  const resVerdictNotes = document.getElementById('res-verdict-notes');
  const resDuration = document.getElementById('res-duration');
  const resSampleRate = document.getElementById('res-sample-rate');
  const resBitrate = document.getElementById('res-bitrate');
  const resLoudness = document.getElementById('res-loudness');
  const resSnr = document.getElementById('res-snr');
  const resClipping = document.getElementById('res-clipping');
  const resDbLinkText = document.getElementById('res-db-link-text');
  const btnViewInExplorer = document.getElementById('btn-view-in-explorer');

  // DOM Elements - Tables
  const submissionsTbody = document.getElementById('submissions-tbody');
  const filterSubmissionsInput = document.getElementById('filter-submissions-input');
  const candidatesTbody = document.getElementById('candidates-tbody');
  const filterCandidatesInput = document.getElementById('filter-candidates-input');
  const btnReingestDb = document.getElementById('btn-reingest-db');

  // DOM Elements - n8n Automation Test Tab
  const n8nTestForm = document.getElementById('n8n-test-form');
  const n8nTestName = document.getElementById('n8n-test-name');
  const n8nTestEmail = document.getElementById('n8n-test-email');
  const n8nTestPhone = document.getElementById('n8n-test-phone');
  const n8nTestCity = document.getElementById('n8n-test-city');
  const n8nTestExp = document.getElementById('n8n-test-exp');
  const n8nTestSkills = document.getElementById('n8n-test-skills');
  const btnLoadDupSample = document.getElementById('btn-load-dup-sample');
  const btnLoadNewSample = document.getElementById('btn-load-new-sample');
  const btnRunN8nFlow = document.getElementById('btn-run-n8n-flow');
  const btnDownloadN8nJson = document.getElementById('btn-download-n8n-json');
  const btnClearTerminal = document.getElementById('btn-clear-terminal');
  const n8nTerminalBody = document.getElementById('n8n-terminal-body');
  const terminalFooter = document.getElementById('terminal-footer');
  const termStatusBadge = document.getElementById('term-status-badge');
  const termTimeElapsed = document.getElementById('term-time-elapsed');

  // -------------------------------------------------------------
  // 1. NAVIGATION TAB SWITCHING
  // -------------------------------------------------------------
  navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetTabId = tab.getAttribute('data-tab');
      navTabs.forEach(t => t.classList.remove('active'));
      tabPanels.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetPanel = document.getElementById(targetTabId);
      if (targetPanel) targetPanel.classList.add('active');

      if (targetTabId === 'tab-submissions') {
        loadSubmissions();
      } else if (targetTabId === 'tab-candidates') {
        loadCandidates();
      }
    });
  });

  if (btnViewInExplorer) {
    btnViewInExplorer.addEventListener('click', () => {
      document.getElementById('nav-submissions-btn').click();
    });
  }

  // -------------------------------------------------------------
  // 2. INPUT MODE SWITCHING (MIC vs FILE UPLOAD)
  // -------------------------------------------------------------
  btnModeMic.addEventListener('click', () => {
    btnModeMic.classList.add('active');
    btnModeFile.classList.remove('active');
    recordingArea.style.display = 'block';
    uploadArea.style.display = 'none';
    checkSubmitReady();
  });

  btnModeFile.addEventListener('click', () => {
    btnModeFile.classList.add('active');
    btnModeMic.classList.remove('active');
    recordingArea.style.display = 'none';
    uploadArea.style.display = 'block';
    checkSubmitReady();
  });

  // -------------------------------------------------------------
  // 3. LIVE AUDIO RECORDING & WEBAUDIO VISUALIZER
  // -------------------------------------------------------------
  const canvasCtx = visualizerCanvas.getContext('2d');

  function drawEmptyVisualizer() {
    canvasCtx.fillStyle = '#060911';
    canvasCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);
    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = 'rgba(99, 102, 241, 0.4)';
    canvasCtx.beginPath();
    const midY = visualizerCanvas.height / 2;
    canvasCtx.moveTo(0, midY);
    canvasCtx.lineTo(visualizerCanvas.width, midY);
    canvasCtx.stroke();
  }
  drawEmptyVisualizer();

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];

      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      function drawLiveWave() {
        if (!isRecording) return;
        animationFrameId = requestAnimationFrame(drawLiveWave);
        analyser.getByteFrequencyData(dataArray);

        canvasCtx.fillStyle = '#060911';
        canvasCtx.fillRect(0, 0, visualizerCanvas.width, visualizerCanvas.height);

        const barWidth = (visualizerCanvas.width / bufferLength) * 1.6;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
          const barHeight = (dataArray[i] / 255) * (visualizerCanvas.height - 10);
          const r = 99 + Math.floor((barHeight / 80) * 100);
          const g = 102;
          const b = 241 + Math.floor((barHeight / 80) * 14);

          canvasCtx.fillStyle = `rgb(${r}, ${g}, ${b})`;
          canvasCtx.fillRect(x, visualizerCanvas.height - barHeight, barWidth - 1, barHeight);
          x += barWidth;
        }
      }

      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        currentAudioBlob = new Blob(audioChunks, { type: mimeType });
        const audioUrl = URL.createObjectURL(currentAudioBlob);
        micAudioPlayer.src = audioUrl;
        micPreviewContainer.style.display = 'block';
        btnResetRecord.style.display = 'inline-flex';
        checkSubmitReady();

        // Stop mic tracks
        stream.getTracks().forEach(track => track.stop());
        if (audioContext && audioContext.state !== 'closed') {
          audioContext.close();
        }
      };

      mediaRecorder.start(100);
      isRecording = true;
      recordingStartTime = Date.now();

      btnStartRecord.disabled = true;
      btnStopRecord.disabled = false;
      btnResetRecord.style.display = 'none';
      micPreviewContainer.style.display = 'none';

      // Start timer
      timerInterval = setInterval(() => {
        const elapsed = (Date.now() - recordingStartTime) / 1000;
        const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const secs = Math.floor(elapsed % 60).toString().padStart(2, '0');
        const tenths = Math.floor((elapsed * 10) % 10);
        recordingTimer.textContent = `${mins}:${secs}.${tenths}`;
      }, 100);

      drawLiveWave();
    } catch (err) {
      alert('Microphone access error: ' + err.message);
      console.error(err);
    }
  }

  function stopRecording() {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      isRecording = false;
      clearInterval(timerInterval);
      if (animationFrameId) cancelAnimationFrame(animationFrameId);
      btnStartRecord.disabled = false;
      btnStopRecord.disabled = true;
    }
  }

  function resetRecording() {
    currentAudioBlob = null;
    audioChunks = [];
    recordingTimer.textContent = '00:00.0';
    micAudioPlayer.src = '';
    micPreviewContainer.style.display = 'none';
    btnResetRecord.style.display = 'none';
    btnStartRecord.disabled = false;
    btnStopRecord.disabled = true;
    drawEmptyVisualizer();
    checkSubmitReady();
  }

  btnStartRecord.addEventListener('click', startRecording);
  btnStopRecord.addEventListener('click', stopRecording);
  btnResetRecord.addEventListener('click', resetRecording);

  // -------------------------------------------------------------
  // 4. FILE DRAG & DROP UPLOAD
  // -------------------------------------------------------------
  dropZone.addEventListener('click', () => audioFileInput.click());

  dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));

  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
      handleSelectedFile(e.dataTransfer.files[0]);
    }
  });

  audioFileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  });

  function handleSelectedFile(file) {
    if (!file.type.startsWith('audio/') && !file.name.match(/\.(wav|mp3|webm|ogg|m4a)$/i)) {
      alert('Please upload a valid audio file (WAV, MP3, WebM, OGG, M4A).');
      return;
    }
    currentAudioBlob = file;
    selectedFileName.textContent = file.name;
    selectedFileSize.textContent = `${(file.size / 1024).toFixed(1)} KB`;
    fileInfoPreview.style.display = 'flex';
    checkSubmitReady();
  }

  btnClearFile.addEventListener('click', () => {
    currentAudioBlob = null;
    audioFileInput.value = '';
    fileInfoPreview.style.display = 'none';
    checkSubmitReady();
  });

  // Check form completeness to enable submit button
  function checkSubmitReady() {
    const hasName = workerNameInput.value.trim().length > 0;
    const hasPhone = phoneInput.value.trim().length >= 8;
    const hasAudio = currentAudioBlob !== null;
    btnSubmitAudio.disabled = !(hasName && hasPhone && hasAudio);
  }

  workerNameInput.addEventListener('input', checkSubmitReady);
  phoneInput.addEventListener('input', checkSubmitReady);

  // -------------------------------------------------------------
  // 5. AUDIO SUBMISSION & EXTRACTION HANDLER
  // -------------------------------------------------------------
  audioForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!currentAudioBlob) return;

    btnSubmitAudio.disabled = true;
    btnSubmitAudio.innerHTML = `
      <span class="status-dot"></span> Processing & Analyzing Signal Properties...
    `;

    const formData = new FormData();
    formData.append('worker_name', workerNameInput.value.trim());
    formData.append('phone', phoneInput.value.trim());

    // Determine filename
    let filename = 'recording.wav';
    if (currentAudioBlob.name) {
      filename = currentAudioBlob.name;
    } else if (currentAudioBlob.type.includes('webm')) {
      filename = 'recording.webm';
    }
    formData.append('audio_file', currentAudioBlob, filename);

    try {
      const response = await fetch('/api/audio/submit', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Submission failed.');
      }

      // Display Extracted Metrics
      const sub = data.submission;
      resDuration.textContent = `${sub.duration_seconds}s`;
      resSampleRate.textContent = `${sub.sample_rate_khz} kHz`;
      resBitrate.textContent = `${sub.bitrate_kbps} kbps`;
      resLoudness.textContent = `${sub.loudness_dbfs} dBFS`;
      resSnr.textContent = sub.snr_db !== null ? `${sub.snr_db} dB` : 'N/A';
      resClipping.textContent = `${sub.clipping_ratio}%`;

      resVerdictTitle.textContent = sub.quality_verdict;
      resVerdictNotes.textContent = sub.quality_notes || 'Extracted via ConsultBae Signal Analysis Engine.';

      // Banner style based on verdict
      resVerdictBanner.className = 'verdict-banner';
      if (sub.quality_verdict.includes('Studio')) {
        // success
      } else if (sub.quality_verdict.includes('Moderate') || sub.quality_verdict.includes('Noise')) {
        resVerdictBanner.classList.add('warning');
      } else if (sub.quality_verdict.includes('Distorted') || sub.quality_verdict.includes('Poor')) {
        resVerdictBanner.classList.add('danger');
      }

      resDbLinkText.textContent = `Linked to Unified Candidate ID #${sub.candidate_id || 'New'} (${sub.worker_name})`;

      resultsPlaceholder.style.display = 'none';
      resultsDisplay.style.display = 'block';

      // Update counters
      loadSubmissions();
    } catch (err) {
      alert('Audio processing error: ' + err.message);
      console.error(err);
    } finally {
      btnSubmitAudio.disabled = false;
      btnSubmitAudio.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
        Submit & Extract Audio Signal Properties
      `;
    }
  });

  // -------------------------------------------------------------
  // 6. SUBMISSIONS EXPLORER TABLE (TASK 3)
  // -------------------------------------------------------------
  let allSubmissions = [];

  async function loadSubmissions() {
    try {
      const response = await fetch('/api/audio/submissions');
      const data = await response.json();
      allSubmissions = data.submissions || [];
      submissionsCountBadge.textContent = allSubmissions.length;
      renderSubmissionsTable(allSubmissions);
    } catch (err) {
      console.error('Error fetching submissions:', err);
    }
  }

  function renderSubmissionsTable(submissions) {
    if (submissions.length === 0) {
      submissionsTbody.innerHTML = `
        <tr>
          <td colspan="11" style="text-align: center; color: var(--text-muted); padding: 2rem;">
            No audio submissions yet. Record or upload an audio file above to see submissions listed here.
          </td>
        </tr>
      `;
      return;
    }

    submissionsTbody.innerHTML = submissions.map(s => {
      let badgeClass = 'badge-success';
      if (s.quality_verdict.includes('Moderate') || s.quality_verdict.includes('Noise')) {
        badgeClass = 'badge-warning';
      } else if (s.quality_verdict.includes('Distorted') || s.quality_verdict.includes('Poor')) {
        badgeClass = 'badge-danger';
      }

      return `
        <tr>
          <td><strong>#${s.id}</strong></td>
          <td><strong>${s.worker_name}</strong></td>
          <td><code>${s.phone}</code></td>
          <td style="min-width: 220px;">
            <audio controls src="${s.playback_url}" preload="none" style="height: 32px;"></audio>
          </td>
          <td>${s.duration_seconds}s</td>
          <td>${s.sample_rate_khz} kHz</td>
          <td>${s.bitrate_kbps} kbps</td>
          <td><code>${s.loudness_dbfs} dBFS</code></td>
          <td><strong style="color: var(--accent-cyan);">${s.snr_db !== null ? s.snr_db + ' dB' : 'N/A'}</strong></td>
          <td><span class="badge ${badgeClass}">${s.quality_verdict}</span></td>
          <td style="color: var(--text-muted); font-size: 0.75rem;">${new Date(s.submitted_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</td>
        </tr>
      `;
    }).join('');
  }

  if (filterSubmissionsInput) {
    filterSubmissionsInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      const filtered = allSubmissions.filter(s =>
        s.worker_name.toLowerCase().includes(q) ||
        s.phone.includes(q) ||
        s.quality_verdict.toLowerCase().includes(q)
      );
      renderSubmissionsTable(filtered);
    });
  }

  // -------------------------------------------------------------
  // 7. UNIFIED CANDIDATES DIRECTORY (TASK 1)
  // -------------------------------------------------------------
  let allCandidates = [];

  async function loadCandidates() {
    try {
      const response = await fetch('/api/candidates');
      const data = await response.json();
      allCandidates = data.candidates || [];
      candidatesCountBadge.textContent = allCandidates.length;
      renderCandidatesTable(allCandidates);
    } catch (err) {
      console.error('Error fetching candidates:', err);
    }
  }

  function renderCandidatesTable(candidates) {
    if (candidates.length === 0) {
      candidatesTbody.innerHTML = `
        <tr>
          <td colspan="10" style="text-align: center; color: var(--text-muted); padding: 2rem;">
            No candidates in database. Run ingestion pipeline.
          </td>
        </tr>
      `;
      return;
    }

    candidatesTbody.innerHTML = candidates.map(c => {
      const skillsHtml = (c.skills || []).map(s => `<span class="skill-tag-pill">${s}</span>`).join(' ');
      const sourcesHtml = (c.sources_merged || []).map(src => {
        const cleanName = src.replace('source', 'S').replace('_', ' ');
        const isS3 = src.includes('source3');
        return `<span class="badge-source ${isS3 ? 's3' : ''}">${cleanName}</span>`;
      }).join('');

      const verifiedBadge = c.verified === true
        ? '<span class="badge badge-success">Verified</span>'
        : (c.verified === false ? '<span class="badge badge-danger">Unverified</span>' : '<span style="color:var(--text-muted); font-size:0.75rem;">N/A</span>');

      let ctcDisplay = 'N/A';
      if (c.current_ctc_lpa) {
        ctcDisplay = `${c.current_ctc_lpa} LPA`;
      }

      let ratesDisplay = '-';
      if (c.hourly_rate_inr) {
        ratesDisplay = `₹${c.hourly_rate_inr}/hr`;
      } else if (c.monthly_rate_inr) {
        ratesDisplay = `₹${Math.round(c.monthly_rate_inr)}/mo`;
      }

      return `
        <tr>
          <td><strong>#${c.id}</strong></td>
          <td><strong>${c.full_name}</strong></td>
          <td><code>${c.phone || '-'}</code></td>
          <td style="font-size: 0.8rem;">${c.email || '-'}</td>
          <td>${c.city || 'Unknown'}</td>
          <td>${sourcesHtml}</td>
          <td>
            <div>${c.experience_years ? c.experience_years + ' yrs' : '-'}</div>
            <div style="font-size: 0.75rem; color: var(--accent-cyan);">${ctcDisplay}</div>
          </td>
          <td><code>${ratesDisplay}</code></td>
          <td>${verifiedBadge}</td>
          <td style="max-width: 250px;">${skillsHtml}</td>
        </tr>
      `;
    }).join('');
  }

  if (filterCandidatesInput) {
    filterCandidatesInput.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      const filtered = allCandidates.filter(c =>
        c.full_name.toLowerCase().includes(q) ||
        (c.email && c.email.toLowerCase().includes(q)) ||
        (c.phone && c.phone.includes(q)) ||
        (c.city && c.city.toLowerCase().includes(q)) ||
        (c.skills && c.skills.some(s => s.toLowerCase().includes(q)))
      );
      renderCandidatesTable(filtered);
    });
  }

  if (btnReingestDb) {
    btnReingestDb.addEventListener('click', async () => {
      btnReingestDb.disabled = true;
      btnReingestDb.textContent = 'Merging Data...';
      try {
        const res = await fetch('/api/pipeline/run', { method: 'POST' });
        const data = await res.json();
        alert(`Ingestion complete! ${data.metrics.unified_candidates_count} master candidates unified.`);
        loadCandidates();
      } catch (err) {
        alert('Pipeline error: ' + err.message);
      } finally {
        btnReingestDb.disabled = false;
        btnReingestDb.textContent = 'Re-run Task 1 Merge';
      }
    });
  }

  // -------------------------------------------------------------
  // 8. N8N AUTOMATION INTERACTIVE TERMINAL EMULATOR (TASK 2)
  // -------------------------------------------------------------
  function logToTerminal(text, className = '') {
    if (!n8nTerminalBody) return;
    const line = document.createElement('div');
    line.className = 'term-line ' + className;
    line.textContent = text;
    n8nTerminalBody.appendChild(line);
    n8nTerminalBody.scrollTop = n8nTerminalBody.scrollHeight;
  }

  function logBlockToTerminal(obj) {
    if (!n8nTerminalBody) return;
    const block = document.createElement('pre');
    block.className = 'term-block';
    block.textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
    n8nTerminalBody.appendChild(block);
    n8nTerminalBody.scrollTop = n8nTerminalBody.scrollHeight;
  }

  function highlightPipelineNode(nodeNum, state = 'active') {
    for (let i = 1; i <= 6; i++) {
      const el = document.getElementById(`p-node-${i}`);
      if (el) {
        if (i === nodeNum) {
          el.className = `pipeline-node node-${state}`;
        } else if (i < nodeNum) {
          el.className = 'pipeline-node node-success';
        } else {
          el.className = 'pipeline-node';
        }
      }
    }
  }

  function resetPipelineNodes() {
    for (let i = 1; i <= 6; i++) {
      const el = document.getElementById(`p-node-${i}`);
      if (el) el.className = 'pipeline-node';
    }
  }

  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

  if (btnClearTerminal) {
    btnClearTerminal.addEventListener('click', () => {
      if (n8nTerminalBody) {
        n8nTerminalBody.innerHTML = `
          <div class="term-line term-dim">// n8n Workflow Simulation Engine Ready.</div>
          <div class="term-line term-dim">// Click "Execute n8n Pipeline" or select a preset to stream execution logs.</div>
        `;
      }
      if (terminalFooter) terminalFooter.style.display = 'none';
      resetPipelineNodes();
    });
  }

  if (btnDownloadN8nJson) {
    btnDownloadN8nJson.addEventListener('click', () => {
      window.location.href = '/api/automation/workflow-json';
    });
  }

  if (btnLoadDupSample) {
    btnLoadDupSample.addEventListener('click', (e) => {
      e.preventDefault();
      n8nTestName.value = 'Tanvi Gupta';
      n8nTestEmail.value = 'tanvi.gupta31@example.com';
      n8nTestPhone.value = '+919000000254';
      if (n8nTestCity) n8nTestCity.value = 'Bengaluru';
      if (n8nTestExp) n8nTestExp.value = '4.2';
      n8nTestSkills.value = 'n8n, Python, Docker';
      logToTerminal('[Preset Loaded] Tanvi Gupta (Known candidate from Source 1, 2, 3 - will test duplicate alert path).', 'term-amber');
    });
  }

  if (btnLoadNewSample) {
    btnLoadNewSample.addEventListener('click', (e) => {
      e.preventDefault();
      const randomId = Math.floor(1000 + Math.random() * 9000);
      n8nTestName.value = 'Harsh Vardhan';
      n8nTestEmail.value = `harsh.vardhan.${randomId}@ai-consultbae.io`;
      n8nTestPhone.value = `+91-98765${randomId}`;
      if (n8nTestCity) n8nTestCity.value = 'Bengaluru';
      if (n8nTestExp) n8nTestExp.value = '4.5';
      n8nTestSkills.value = 'n8n, LangChain, Zapier, Python, FastAPI, Web Scraping';
      logToTerminal(`[Preset Loaded] Harsh Vardhan (Unique applicant email/phone - will test AI classification path).`, 'term-cyan');
    });
  }

  if (n8nTestForm) {
    n8nTestForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      if (btnRunN8nFlow) {
        btnRunN8nFlow.disabled = true;
        btnRunN8nFlow.textContent = 'Running Workflow...';
      }

      if (n8nTerminalBody) n8nTerminalBody.innerHTML = '';
      if (terminalFooter) terminalFooter.style.display = 'none';

      const startTime = Date.now();
      const timestamp = () => new Date().toISOString().substring(11, 19);

      const name = n8nTestName.value.trim();
      const email = n8nTestEmail.value.trim();
      const phone = n8nTestPhone.value.trim();
      const city = n8nTestCity ? n8nTestCity.value.trim() : 'Unknown';
      const exp = n8nTestExp ? parseFloat(n8nTestExp.value) || 2.5 : 2.5;
      const skills = n8nTestSkills.value.split(',').map(s => s.trim()).filter(Boolean);

      try {
        // Step 1: Webhook Ingest
        highlightPipelineNode(1, 'active');
        logToTerminal(`[${timestamp()}] [Step 1: Webhook Ingest Node] Webhook trigger fired (POST /webhook/candidate-submission)`, 'term-cyan');
        logBlockToTerminal({ name, email, phone, city, experience_years: exp, skills });
        await delay(350);

        // Step 2: Data Cleaning & Normalization
        highlightPipelineNode(2, 'active');
        logToTerminal(`[${timestamp()}] [Step 2: Code Node / Normalizer] Standardizing phone, lowercase email, canonical skills...`, 'term-purple');
        await delay(350);

        // Step 3: Database Query (Duplicate Check)
        highlightPipelineNode(3, 'active');
        logToTerminal(`[${timestamp()}] [Step 3: SQLite Query Node] Checking database for matching phone or email...`, 'term-cyan');

        const dupRes = await fetch('/api/candidates/check-duplicate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, phone, name })
        });
        const dupData = await dupRes.json();
        await delay(400);

        if (dupData.is_duplicate) {
          // Branch A: Duplicate detected
          highlightPipelineNode(4, 'warning');
          logToTerminal(`[${timestamp()}] [Step 4: Router Node] ⛔ DUPLICATE DETECTED! Matched candidate ID #${dupData.matched_candidate.id} (${dupData.matched_candidate.full_name})`, 'term-rose');
          await delay(300);

          logToTerminal(`[${timestamp()}] [Step 4a: Slack / Discord Alert Node] Dispatched duplicate notification:`, 'term-amber');
          const alertPayload = {
            alert_type: 'DUPLICATE_CANDIDATE_DETECTED',
            candidate_name: name,
            email: email,
            phone: phone,
            matched_candidate_id: dupData.matched_candidate.id,
            matched_sources: dupData.matched_candidate.sources_merged,
            action_taken: 'Notification sent to Slack #recruitment-alerts; duplicate insertion suppressed.'
          };
          logBlockToTerminal(alertPayload);

          if (terminalFooter) {
            terminalFooter.style.display = 'flex';
            termStatusBadge.className = 'term-badge term-badge-warning';
            termStatusBadge.textContent = 'DUPLICATE SUPPRESSED';
            termTimeElapsed.textContent = `Execution Time: ${Date.now() - startTime}ms`;
          }
        } else {
          // Branch B: Unique Candidate -> AI Classification & Writeback
          highlightPipelineNode(4, 'success');
          logToTerminal(`[${timestamp()}] [Step 4: Router Node] ✅ Candidate is unique. Routing to AI Enrichment...`, 'term-emerald');
          await delay(300);

          highlightPipelineNode(5, 'active');
          logToTerminal(`[${timestamp()}] [Step 5: AI / LLM Skill Auto-Tagger Node] Calling AI classifier...`, 'term-purple');

          const enrichRes = await fetch('/api/candidates/enrich', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              full_name: name,
              email: email,
              phone: phone,
              city: city,
              skills: skills,
              experience_years: exp,
              source: 'n8n_interactive_console'
            })
          });
          const enrichData = await enrichRes.json();
          await delay(400);

          const classification = enrichData.classification || {};
          const classifierUsed = enrichData.classifier_used || 'rule-based';
          logToTerminal(`[${timestamp()}] [Step 5: AI Classification Result] [${classifierUsed}]`, 'term-emerald');
          logToTerminal(`   • Primary Category : ${classification.primary_category || 'automation-heavy'}`);
          logToTerminal(`   • Seniority Level  : ${classification.seniority_level || 'Senior'}`);
          logToTerminal(`   • Secondary Tags   : ${(classification.secondary_tags || []).join(', ')}`);
          logToTerminal(`   • Reasoning        : ${classification.reasoning || 'Automated skill categorization'}`);
          await delay(300);

          highlightPipelineNode(6, 'success');
          logToTerminal(`[${timestamp()}] [Step 6: SQLite Writeback Node] Successfully inserted Master Profile ID #${enrichData.candidate.id}!`, 'term-emerald');
          logBlockToTerminal({
            status: 'ENRICHED_AND_SAVED',
            candidate_id: enrichData.candidate.id,
            candidate_name: enrichData.candidate.full_name,
            sources_merged: enrichData.candidate.sources_merged,
            skills: enrichData.candidate.skills
          });

          if (terminalFooter) {
            terminalFooter.style.display = 'flex';
            termStatusBadge.className = 'term-badge term-badge-success';
            termStatusBadge.textContent = 'PROFILE ENRICHED & SAVED';
            termTimeElapsed.textContent = `Execution Time: ${Date.now() - startTime}ms`;
          }

          loadCandidates();
        }
      } catch (err) {
        logToTerminal(`[ERROR] Simulation failure: ${err.message}`, 'term-rose');
      } finally {
        if (btnRunN8nFlow) {
          btnRunN8nFlow.disabled = false;
          btnRunN8nFlow.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            Execute n8n Pipeline
          `;
        }
      }
    });
  }

  // Initial Data Fetch
  loadSubmissions();
  loadCandidates();
});

