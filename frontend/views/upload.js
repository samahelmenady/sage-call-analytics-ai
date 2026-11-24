import { escapeHtml } from '../components/escape.js';
import { t } from '../components/i18n.js';
import { mountCallDetailView } from './call-detail.js';

const MAX_BYTES = 25 * 1024 * 1024;

export function mountUploadView(container, { onAnalysisComplete } = {}) {
  container.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px;margin-bottom:20px">
      <div>
        <h1 style="margin:0 0 6px">${escapeHtml(t('heroTitle'))}</h1>
        <p style="color:var(--mu);margin:0">${escapeHtml(t('heroSub'))}</p>
      </div>
    </div>

    <div class="upload-grid">
      <div class="card">
        <h3 class="section-title">${escapeHtml(t('audioTitle'))}</h3>
        <div class="dropzone" id="dropzone">
          <strong>${escapeHtml(t('dropTitle'))}</strong>
          <p style="color:var(--mu);font-size:13px;margin-top:6px">${escapeHtml(t('dropHint'))}</p>
          <input type="file" id="audioInput" accept="audio/*,.wav,.mp3,.m4a,.ogg,.flac,.webm" hidden />
        </div>
        <div id="audioPreviewWrap" style="margin-top:12px" hidden>
          <div id="audioFileLabel" style="font-size:12px;font-weight:700;color:var(--mu);margin-bottom:6px"></div>
          <audio id="audioPlayer" controls style="width:100%"></audio>
        </div>
      </div>

      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:10px">
          <h3 class="section-title" style="margin:0">${escapeHtml(t('txTitle'))}</h3>
          <select id="langSelect" class="select" style="width:auto;min-width:155px" aria-label="Transcript Language">
            <option value="ar">Arabic / Egyptian (ar)</option>
            <option value="en">English (en)</option>
            <option value="auto">Auto-detect</option>
          </select>
        </div>
        <textarea id="transcriptInput" class="textarea" dir="auto" placeholder="${escapeHtml(t('txPh'))}"></textarea>
        <div style="display:flex;justify-content:space-between;margin-top:8px;font-size:12px;color:var(--mu)">
          <span id="wordCount">0 words</span>
          <span>${escapeHtml(t('minWords'))}</span>
        </div>
      </div>
    </div>

    <div id="pipelineSteps" class="pipeline-steps" hidden>
      <span id="stepStt" class="step-pill">${escapeHtml(t('step1'))}</span>
      <span id="stepAi" class="step-pill">${escapeHtml(t('step2'))}</span>
      <span id="stepDash" class="step-pill">${escapeHtml(t('step3'))}</span>
    </div>

    <div id="statusAlert" class="alert" hidden></div>

    <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px;flex-wrap:wrap">
      <button id="analyzeBtn" class="btn" disabled>${escapeHtml(t('analyzeBtn'))}</button>
      <button id="clearBtn" class="btn btn-secondary btn-sm">${escapeHtml(t('clearBtn'))}</button>
    </div>

    <div id="inlineResult"></div>
  `;

  const dropzone = container.querySelector('#dropzone');
  const audioInput = container.querySelector('#audioInput');
  const audioPreviewWrap = container.querySelector('#audioPreviewWrap');
  const audioFileLabel = container.querySelector('#audioFileLabel');
  const audioPlayer = container.querySelector('#audioPlayer');
  const transcriptInput = container.querySelector('#transcriptInput');
  const langSelect = container.querySelector('#langSelect');
  const wordCount = container.querySelector('#wordCount');
  const analyzeBtn = container.querySelector('#analyzeBtn');
  const clearBtn = container.querySelector('#clearBtn');
  const pipelineSteps = container.querySelector('#pipelineSteps');
  const stepStt = container.querySelector('#stepStt');
  const stepAi = container.querySelector('#stepAi');
  const stepDash = container.querySelector('#stepDash');
  const statusAlert = container.querySelector('#statusAlert');
  const inlineResult = container.querySelector('#inlineResult');

  let currentSource = 'text';
  let currentFilename = null;
  let objectUrl = null;
  let busy = false;

  function showAlert(message, type = 'info') {
    if (!message) {
      statusAlert.hidden = true;
      return;
    }
    statusAlert.className = `alert alert-${type}`;
    statusAlert.textContent = message;
    statusAlert.hidden = false;
  }

  function setPipelineState(stt, ai, dash) {
    pipelineSteps.hidden = false;
    stepStt.className = `step-pill ${stt}`;
    stepAi.className = `step-pill ${ai}`;
    stepDash.className = `step-pill ${dash}`;
  }

  function syncBtn() {
    const words = transcriptInput.value.trim().split(/\s+/).filter(Boolean).length;
    wordCount.textContent = `${words} words`;
    analyzeBtn.disabled = busy || words < 3;
  }

  transcriptInput.addEventListener('input', () => {
    currentSource = 'text';
    syncBtn();
  });

  async function runAnalyze(sourceOverride = null) {
    const text = transcriptInput.value.trim();
    const words = text.split(/\s+/).filter(Boolean).length;
    if (words < 3) {
      showAlert('Transcript must contain at least 3 words before analysis.', 'error');
      return;
    }

    busy = true;
    syncBtn();
    const usedSource = sourceOverride || currentSource;
    setPipelineState(usedSource === 'audio' ? 'done' : '', 'active', '');
    showAlert('Running Generative AI analysis, grounding checks, and risk rules...', 'info');

    const payload = {
      transcript: text,
      language: langSelect.value,
      source: usedSource,
      call_metadata: currentFilename ? { filename: currentFilename } : null,
    };

    try {
      const resp = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        throw new Error(data.detail || `Analysis failed (${resp.status})`);
      }

      setPipelineState(usedSource === 'audio' ? 'done' : '', 'done', 'active');
      mountCallDetailView(inlineResult, data, {
        audioPlayer,
        onBack: () => { inlineResult.innerHTML = ''; },
      });

      if (onAnalysisComplete) {
        await onAnalysisComplete(data);
      }

      setPipelineState(usedSource === 'audio' ? 'done' : '', 'done', 'done');
      showAlert(`Analysis complete for ${data.call_id} — Dashboard updated.`, 'success');
    } catch (err) {
      setPipelineState(usedSource === 'audio' ? 'done' : '', 'error', '');
      showAlert(`Analysis error: ${err.message}`, 'error');
    } finally {
      busy = false;
      syncBtn();
    }
  }

  async function handleAudio(file) {
    if (!file || busy) return;
    if (file.size === 0) {
      showAlert('Uploaded audio file is empty.', 'error');
      return;
    }
    if (file.size > MAX_BYTES) {
      showAlert(`File exceeds the 25 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`, 'error');
      return;
    }

    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = URL.createObjectURL(file);
    audioPlayer.src = objectUrl;
    audioFileLabel.innerHTML = `Selected: <span>${escapeHtml(file.name)}</span> (${(file.size / 1024).toFixed(0)} KB)`;
    audioPreviewWrap.hidden = false;

    busy = true;
    currentSource = 'audio';
    currentFilename = file.name;
    syncBtn();
    setPipelineState('active', '', '');
    showAlert(`Transcribing "${file.name}" with Cohere STT...`, 'info');

    const fd = new FormData();
    fd.append('file', file);

    try {
      const resp = await fetch('/api/transcribe', { method: 'POST', body: fd });
      const data = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        if (resp.status === 413) {
          throw new Error('Audio file exceeds the 4.5 MB serverless upload limit. Please use a smaller clip or paste the transcript.');
        }
        throw new Error(data.detail || `Transcription failed (${resp.status})`);
      }
      transcriptInput.value = data.transcript || '';
      busy = false;
      syncBtn();
      await runAnalyze('audio');
    } catch (err) {
      busy = false;
      setPipelineState('error', '', '');
      showAlert(`Transcription error: ${err.message}`, 'error');
      syncBtn();
    }
  }

  dropzone.addEventListener('click', () => {
    audioInput.value = '';
    audioInput.click();
  });
  audioInput.addEventListener('change', e => handleAudio(e.target.files[0]));
  dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('dragover'); });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
  dropzone.addEventListener('drop', e => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    handleAudio(e.dataTransfer.files[0]);
  });

  analyzeBtn.addEventListener('click', () => runAnalyze());
  clearBtn.addEventListener('click', () => {
    transcriptInput.value = '';
    currentSource = 'text';
    currentFilename = null;
    audioPreviewWrap.hidden = true;
    audioPlayer.removeAttribute('src');
    pipelineSteps.hidden = true;
    statusAlert.hidden = true;
    inlineResult.innerHTML = '';
    syncBtn();
  });

  return {
    showCall(call) {
      mountCallDetailView(inlineResult, call, {
        audioPlayer,
        onBack: () => { inlineResult.innerHTML = ''; },
      });
      inlineResult.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },
  };
}
