// Talks to the local Flask server: uploads the chosen recording, then streams
// the output of transcribe.py into the page.

const el = (id) => document.getElementById(id);

const ui = {
  choose: el('choose'),
  file: el('file'),
  fileInfo: el('file-info'),
  uploadBar: el('upload-bar'),
  transcribe: el('transcribe'),
  transcribeInfo: el('transcribe-info'),
  downloadsPath: el('downloads-path'),
  consoleCard: el('console-card'),
  console: el('console'),
  result: el('result'),
  savedNote: el('saved-note'),
  text: el('text'),
  status: el('status'),
  warnings: el('warnings'),
};

const state = {
  token: null,
  name: null,
  busy: false,
};

// ── UI helpers ───────────────────────────────────────────────────────────────

function setStatus(message, isError = false) {
  ui.status.textContent = message;
  ui.status.classList.toggle('error', isError);
}

function refreshButtons() {
  ui.choose.disabled = state.busy;
  ui.transcribe.disabled = state.busy || !state.token;
}

function markDone(stepId) {
  el(stepId).classList.add('done');
}

function formatMB(bytes) {
  return `${(bytes / 1e6).toFixed(0)} מ״ב`;
}

function resetConsole() {
  ui.console.textContent = '';
  ui.consoleCard.classList.remove('hidden');
}

function log(line) {
  ui.console.textContent += `${line}\n`;
  ui.console.scrollTop = ui.console.scrollHeight;
}

/**
 * Consume a Server-Sent Events endpoint. Returns a promise that settles when
 * the server reports success or failure.
 */
function streamEvents(url, { onLog } = {}) {
  return new Promise((resolve, reject) => {
    const source = new EventSource(url);

    source.addEventListener('log', (event) => {
      const { line } = JSON.parse(event.data);
      log(line);
      onLog?.(line);
    });
    source.addEventListener('started', (event) => {
      const { command } = JSON.parse(event.data);
      log(`$ ${command}\n`);
    });
    source.addEventListener('finished', (event) => {
      source.close();
      resolve(JSON.parse(event.data));
    });
    source.addEventListener('succeeded', () => {
      source.close();
      resolve({});
    });
    source.addEventListener('failed', (event) => {
      source.close();
      reject(new Error(JSON.parse(event.data).message));
    });
    source.addEventListener('error', () => {
      // Fires on a dropped connection, which for us means the server died.
      if (source.readyState === EventSource.CLOSED) {
        reject(new Error('החיבור לשרת המקומי נקטע.'));
      }
    });
  });
}

// ── Startup checks ───────────────────────────────────────────────────────────

async function checkEnvironment() {
  try {
    const info = await (await fetch('/api/environment')).json();
    ui.downloadsPath.textContent = info.downloads;
    if (info.problems.length) {
      ui.warnings.classList.remove('hidden');
      ui.warnings.innerHTML = `<strong>צריך לתקן קודם:</strong><ul>${
        info.problems.map((p) => `<li dir="ltr">${p}</li>`).join('')
      }</ul>`;
    } else {
      const label = {
        cuda: 'כרטיס הגרפי של NVIDIA',
        mps: 'כרטיס הגרפי של Apple',
        cpu: 'מעבד',
      }[info.device];
      setStatus(
        info.device === 'cpu'
          ? 'לא זוהה כרטיס גרפי. התמלול ירוץ על המעבד ויהיה איטי.'
          : `מוכן. התמלול ירוץ על ה${label}.`,
      );
    }
  } catch {
    setStatus('אין חיבור לשרת המקומי. בדקו ש-python app.py עדיין רץ.', true);
  }
}

// ── Actions ──────────────────────────────────────────────────────────────────

/** Upload with XHR rather than fetch, because we want real progress on big files. */
function uploadRecording(file) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append('file', file);

    const request = new XMLHttpRequest();
    request.open('POST', '/api/recording');

    request.upload.addEventListener('progress', (event) => {
      if (!event.lengthComputable) return;
      ui.uploadBar.classList.remove('hidden');
      ui.uploadBar.querySelector('.fill').style.width =
        `${Math.round((event.loaded / event.total) * 100)}%`;
    });
    request.addEventListener('load', () => {
      const body = JSON.parse(request.responseText || '{}');
      if (request.status === 200) resolve(body);
      else reject(new Error(body.error ?? `ההעלאה נכשלה (${request.status})`));
    });
    request.addEventListener('error', () => reject(new Error('ההעלאה נכשלה.')));
    request.send(form);
  });
}

ui.choose.addEventListener('click', () => ui.file.click());

ui.file.addEventListener('change', async () => {
  const [file] = ui.file.files;
  if (!file) return;

  state.busy = true;
  state.token = null;
  refreshButtons();
  ui.result.classList.add('hidden');
  ui.fileInfo.textContent = `מכין את ${file.name}…`;

  try {
    const { token, name, size } = await uploadRecording(file);
    state.token = token;
    state.name = name;
    ui.fileInfo.textContent = `${name} (${formatMB(size)})`;
    ui.uploadBar.classList.add('hidden');
    markDone('step-choose');
    setStatus('');
  } catch (error) {
    ui.fileInfo.textContent = 'לא נבחר קובץ.';
    ui.uploadBar.classList.add('hidden');
    setStatus(error.message, true);
  } finally {
    state.busy = false;
    refreshButtons();
  }
});

ui.transcribe.addEventListener('click', async () => {
  if (!state.token) return;

  state.busy = true;
  refreshButtons();
  resetConsole();
  ui.result.classList.add('hidden');
  setStatus(
    'מריץ תמלול. זה לוקח זמן בהקלטות ארוכות, ויותר מזה אם המודל עוד לא ירד.',
  );

  const query = new URLSearchParams({ token: state.token, name: state.name });
  try {
    const { output, name } = await streamEvents(`/api/transcribe?${query}`);
    markDone('step-transcribe');
    ui.savedNote.textContent = `נשמר אל ${output}`;

    const response = await fetch(`/api/transcript?name=${encodeURIComponent(name)}`);
    const text = response.ok ? (await response.json()).text : '';
    ui.text.value = text;
    ui.result.classList.remove('hidden');

    if (text.trim()) {
      setStatus(`סיום. ${name} נשמר לתיקיית ההורדות.`);
    } else {
      // An empty file is a real outcome, not a crash. Say so rather than
      // showing an empty box next to a success message.
      setStatus(
        'המודל לא החזיר טקסט, ולכן התמליל ריק. הסיבות האפשריות מופיעות ביומן שלמעלה.',
        true,
      );
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    state.busy = false;
    refreshButtons();
  }
});

checkEnvironment();
refreshButtons();
