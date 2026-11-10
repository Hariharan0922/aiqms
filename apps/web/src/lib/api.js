const rawBase = import.meta.env.VITE_API_BASE_URL;
const BASE = (rawBase !== undefined && rawBase !== ''
  ? (rawBase.startsWith('http://') || rawBase.startsWith('https://') ? rawBase : `https://${rawBase}`)
  : (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://localhost:8000' : '')
).replace(/\/$/, '');
let actorRole = 'author';

export function setActorRole(role) { actorRole = role; }
export function actorHeaders(extra = {}) {
  return {
    'X-Actor-Email': `demo.${actorRole}@example.local`,
    'X-Actor-Role': actorRole,
    'X-Organization-Id': 'demo-org',
    ...extra,
  };
}

export async function api(path, options = {}) {
  const headers = actorHeaders(options.headers || {});
  const hasBody = options.body !== undefined && !(options.body instanceof FormData);
  if (hasBody && !headers['Content-Type']) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${BASE}/api/v1${path}`, { ...options, headers });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try { const payload = await response.json(); message = payload.detail || message; } catch { /* ignore non-JSON errors */ }
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }
  const type = response.headers.get('content-type') || '';
  return type.includes('application/json') ? response.json() : response;
}

export async function downloadExport(documentId, format) {
  const response = await api(`/documents/${documentId}/export?format=${format}`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${documentId}.${format}`;
  document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
}

export async function uploadEvidence(documentId, file) {
  const form = new FormData(); form.append('file', file);
  return api(`/documents/${documentId}/evidence`, { method: 'POST', body: form });
}

export async function uploadIngestionFiles(files) {
  const form = new FormData();
  for (const f of files) {
    form.append('files', f);
  }
  return api('/documents/upload', { method: 'POST', body: form });
}

export async function fetchIngestedDocuments(params = {}) {
  const query = new URLSearchParams(params).toString();
  return api(`/documents/ingested${query ? `?${query}` : ''}`);
}

export async function fetchIngestedDocumentDetail(documentId) {
  return api(`/documents/ingested/${documentId}`);
}

export async function fetchIngestedSections(documentId, tree = false) {
  return api(`/documents/ingested/${documentId}/sections?tree=${tree}`);
}

export async function fetchIngestedChunks(documentId, forEmbedding = false) {
  return api(`/documents/ingested/${documentId}/chunks?for_embedding=${forEmbedding}`);
}

export async function fetchIngestedJson(documentId) {
  return api(`/documents/ingested/${documentId}/json`);
}

export async function fetchVectorStatus() {
  return api('/vectors/status');
}

export async function embedDocumentVectors(documentId) {
  return api(`/vectors/embed/document/${documentId}`, { method: 'POST' });
}

export async function performSemanticSearch(payload) {
  return api('/search/semantic', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchIsoClauses() {
  return api('/compliance/iso13485/clauses');
}

export async function seedIsoClauses() {
  return api('/compliance/iso13485/seed', { method: 'POST' });
}

export async function verifyDocumentCompliance(documentId) {
  return api(`/compliance/verify/${documentId}`, { method: 'POST' });
}

export async function fetchComplianceRun(runId) {
  return api(`/compliance/runs/${runId}`);
}

export async function fetchTraceabilityMatrix(documentId) {
  return api(`/compliance/matrix/${documentId}`);
}

export async function generateTraceability(documentId, similarityThreshold = 0.45) {
  return api(`/compliance/traceability/${documentId}?similarity_threshold=${similarityThreshold}`, {
    method: 'POST',
  });
}

export async function fetchTraceabilityItem(itemId) {
  return api(`/compliance/traceability/items/${itemId}`);
}

export async function submitTraceabilityItem(itemId) {
  return api(`/compliance/traceability/items/${itemId}/submit`, { method: 'POST' });
}

export async function reviewTraceabilityItem(itemId, payload) {
  return api(`/compliance/traceability/items/${itemId}/review`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function setTraceabilityNotApplicable(itemId, justification) {
  return api(`/compliance/traceability/items/${itemId}/not-applicable`, {
    method: 'POST',
    body: JSON.stringify({ justification }),
  });
}

export async function analyzeTraceabilityItemLLM(itemId, modelName = 'qwen3:4b') {
  return api(`/compliance/traceability/items/${itemId}/analyze?model_name=${encodeURIComponent(modelName)}`, {
    method: 'POST',
  });
}

export async function validateTraceabilityItemRules(itemId) {
  return api(`/compliance/traceability/items/${itemId}/validate`, { method: 'POST' });
}

// ISO 13485 Machine Learning Model Endpoints
export async function predictISOClause(text, top_k = 5) {
  return api('/compliance/ml/predict-clause', {
    method: 'POST',
    body: JSON.stringify({ text, top_k }),
  });
}

export async function auditISOTerm(text, targetClause = null) {
  return api('/compliance/ml/audit', {
    method: 'POST',
    body: JSON.stringify({ text, target_clause: targetClause }),
  });
}

export async function fetchISOMLModelInfo() {
  return api('/compliance/ml/model-info');
}

export async function trainISOMLModel(force = false) {
  return api('/compliance/ml/train', {
    method: 'POST',
    body: JSON.stringify({ force_retrain: force }),
  });
}

export async function fetchSFTDatasetSample(limit = 5) {
  return api(`/compliance/ml/dataset/sft?limit=${limit}`);
}

export async function verifyAndGenerateML(payload) {
  return api('/compliance/ml/verify-and-generate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}


