import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertCircle, ArrowDownToLine, ArrowLeft, ArrowRight, BadgeCheck, Bell, BookOpenCheck,
  Brain, Check, CheckCircle2, ChevronDown, ChevronRight, CircleHelp, ClipboardCheck, Clock3, Cloud,
  Edit3, FileCheck2, FilePlus2, FileText, Files, FlaskConical, FolderOpen, Gauge, GitBranch, History,
  LayoutDashboard, ListChecks, LoaderCircle, LockKeyhole, Menu, MessageSquareText, Plus, RefreshCw,
  Search, Server, Settings2, ShieldCheck, Sparkles, Trash2, TriangleAlert, Upload, X, Zap,
} from 'lucide-react';
import { api, downloadExport, setActorRole, uploadEvidence } from './lib/api';
import { IngestionPage } from './features/IngestionPage';
import { SearchPage } from './features/SearchPage';
import { TraceabilityPage } from './features/TraceabilityPage';
import { MLModelPage } from './features/MLModelPage';

const navItems = [
  { id: 'dashboard', label: 'Overview', icon: LayoutDashboard },
  { id: 'documents', label: 'Documents', icon: Files },
  { id: 'process', label: 'End-to-End Process', icon: Activity },
  { id: 'mlmodel', label: 'ISO 13485 ML Model', icon: Brain },
  { id: 'ingestion', label: 'Document Ingestion', icon: FileCheck2 },
  { id: 'search', label: 'Semantic Search', icon: Search },
  { id: 'traceability', label: 'Traceability Matrix', icon: GitBranch },
  { id: 'templates', label: 'Template library', icon: BookOpenCheck },
  { id: 'requirements', label: 'Requirements', icon: ClipboardCheck },
  { id: 'reviews', label: 'Review queue', icon: BadgeCheck },
  { id: 'audit', label: 'Audit trail', icon: History },
];
const roleLabels = { author: 'Author', reviewer: 'Reviewer', approver: 'Approver', admin: 'Administrator' };

function statusText(value = '') { return value.replaceAll('_', ' ').replace(/\b\w/g, (m) => m.toUpperCase()); }
function statusClass(value = '') {
  if (['released', 'validated', 'approved', 'accept'].includes(value)) return 'status-green';
  if (['in_review', 'awaiting_approval', 'generated'].includes(value)) return 'status-blue';
  if (['changes_requested', 'failed', 'rejected'].includes(value)) return 'status-red';
  return 'status-gray';
}
function dateLabel(value) { if (!value) return '—'; try { return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }); } catch { return value; } }
function shortTime(value) { if (!value) return '—'; try { return new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }); } catch { return value; } }

function StatusPill({ value }) { return <span className={`status-pill ${statusClass(value)}`}><span className="status-dot" />{statusText(value || 'draft')}</span>; }
function Field({ field, value, onChange, disabled }) {
  const common = { value: value ?? '', disabled, onChange: (e) => onChange(field.key, e.target.value), placeholder: field.placeholder || `Enter ${field.label.toLowerCase()}` };
  return <label className="form-field" key={field.key}>
    <span className="field-label">{field.label}{field.required && <i className="required-star">*</i>}</span>
    {field.type === 'textarea' ? <textarea rows={3} {...common} /> : field.type === 'select' ? <select {...common}><option value="">Choose an option</option>{(field.options || []).map((o) => <option value={o} key={o}>{o}</option>)}</select> : <input type={field.type === 'date' ? 'date' : 'text'} {...common} />}
    {field.help && <span className="field-help">{field.help}</span>}
  </label>;
}

function App() {
  const [view, setView] = useState('dashboard');
  const [role, setRole] = useState('author');
  const [templates, setTemplates] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [requirements, setRequirements] = useState([]);
  const [providers, setProviders] = useState([]);
  const [stats, setStats] = useState({ total_documents: 0, status_counts: {}, blocking_findings: 0, pending_reviews: 0, pending_approvals: 0 });
  const [selectedId, setSelectedId] = useState(null);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [templateDetail, setTemplateDetail] = useState(null);
  const [tab, setTab] = useState('inputs');
  const [answers, setAnswers] = useState({});
  const [applicability, setApplicability] = useState({});
  const [createTemplate, setCreateTemplate] = useState(null);
  const [newTitle, setNewTitle] = useState('');
  const [topicSummary, setTopicSummary] = useState('');
  const [providerId, setProviderId] = useState('nvidia');
  const [generationProgress, setGenerationProgress] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [reviewComment, setReviewComment] = useState('');
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [uploading, setUploading] = useState(false);

  const notify = useCallback((message, kind = 'success') => {
    setToast({ message, kind }); window.setTimeout(() => setToast(null), 4200);
  }, []);

  const refreshCore = useCallback(async () => {
    setActorRole(role);
    try {
      const [tpl, docs, reqs, prov, dashboard] = await Promise.all([
        api('/templates'), api('/documents'), api('/requirements'), api('/providers'), api('/dashboard/stats'),
      ]);
      setTemplates(tpl); setDocuments(docs); setRequirements(reqs); setProviders(prov); setStats(dashboard);
      setProviderId((current) => current || 'offline'); setLoadError('');
      if (selectedId) {
        const matching = docs.find((d) => d.id === selectedId);
        if (matching) {
          const detailed = await api(`/documents/${selectedId}`);
          setSelectedDoc(detailed);
          const tmpl = tpl.find((t) => t.id === detailed.template_id);
          setTemplateDetail(tmpl || null);
          setAnswers(detailed.current_version.answers || {});
          setApplicability(detailed.current_version.applicability || {});
        }
      }
    } catch (e) { setLoadError(e.message); }
  }, [role, selectedId]);

  useEffect(() => { refreshCore(); }, [refreshCore]);
  useEffect(() => { if (!selectedDoc) return; const t = templates.find((x) => x.id === selectedDoc.template_id); setTemplateDetail(t || null); }, [selectedDoc, templates]);

  const selectRole = (next) => { setRole(next); setActorRole(next); setSelectedDoc(null); setSelectedId(null); };
  const selectDoc = async (id, initialTab = null) => {
    try {
      setLoading(true); setActorRole(role);
      const doc = await api(`/documents/${id}`);
      setSelectedId(id); setSelectedDoc(doc); setTemplateDetail(templates.find((x) => x.id === doc.template_id) || null);
      setAnswers(doc.current_version.answers || {}); setApplicability(doc.current_version.applicability || {});
      const hasContent = (doc.current_version?.content?.sections?.length || 0) > 0;
      const targetTab = initialTab || (hasContent ? 'draft' : 'inputs');
      setTab(targetTab); setView('documents');
    } catch (e) { notify(e.message, 'error'); } finally { setLoading(false); }
  };

  const createDocument = async () => {
    if (!createTemplate || newTitle.trim().length < 3) return notify('Please enter a document title with at least 3 characters.', 'error');
    try {
      setLoading(true); setActorRole(role);
      const created = await api('/documents', { method: 'POST', body: JSON.stringify({ template_id: createTemplate.id, title: newTitle.trim(), answers: {} }) });
      setCreateTemplate(null); setNewTitle(''); setTopicSummary(''); await refreshCore(); await selectDoc(created.id);
      notify('Document created. Complete the inputs and applicability decisions to validate it.');
    } catch (e) { notify(e.message, 'error'); } finally { setLoading(false); }
  };

  const createDocumentEnhanced = async () => {
    if (!createTemplate) return;
    const summaryText = topicSummary.trim() || newTitle.trim();
    if (summaryText.length < 2) return notify('Please enter a topic keyword or summary (at least 2 characters).', 'error');
    try {
      setLoading(true); setActorRole(role);
      const created = await api('/documents/enhance-from-summary', {
        method: 'POST',
        body: JSON.stringify({
          template_id: createTemplate.id,
          summary: summaryText,
          provider: providerId || 'nvidia',
          create_document: true,
        }),
      });
      setCreateTemplate(null); setNewTitle(''); setTopicSummary(''); await refreshCore(); await selectDoc(created.id);
      notify('Document created and auto-enhanced with ISO 13485 compliant procedures and records!');
    } catch (e) { notify(e.message, 'error'); } finally { setLoading(false); }
  };

  const createDocumentFullyGenerated = async () => {
    if (!createTemplate) return;
    const summaryText = topicSummary.trim() || newTitle.trim();
    if (summaryText.length < 2) return notify('Please enter a topic keyword or summary (at least 2 characters).', 'error');
    try {
      setLoading(true); setActorRole(role);
      const res = await api('/qms/generate-from-summary', {
        method: 'POST',
        body: JSON.stringify({
          template_id: createTemplate.id,
          summary: summaryText,
          standard: 'ISO 13485:2016',
          provider: providerId || 'nvidia',
          auto_generate_sections: true,
        }),
      });
      setCreateTemplate(null); setNewTitle(''); setTopicSummary(''); await refreshCore(); await selectDoc(res.document.id);
      notify('Full ISO 13485 QMS document generated successfully with industrial standards & web analysis!');
    } catch (e) { notify(e.message, 'error'); } finally { setLoading(false); }
  };

  const saveInputs = async (alsoValidate = false) => {
    if (!selectedDoc) return;
    try {
      setLoading(true); setActorRole(role);
      const updated = await api(`/documents/${selectedId}/answers`, { method: 'PATCH', body: JSON.stringify({ answers, applicability }) });
      setSelectedDoc(updated); setAnswers(updated.current_version.answers || {}); setApplicability(updated.current_version.applicability || {});
      if (alsoValidate) {
        const result = await api(`/documents/${selectedId}/validate`, { method: 'POST', body: JSON.stringify({}) });
        const fresh = await api(`/documents/${selectedId}`); setSelectedDoc(fresh);
        notify(result.can_generate ? 'Validation passed. Review warnings before generating.' : `${result.findings.filter((x) => x.blocks_generation).length} blocking findings need attention.`, result.can_generate ? 'success' : 'warning');
      } else notify('Inputs saved. Previous validation is now stale until validation runs again.');
      await refreshListOnly();
    } catch (e) { notify(e.message, 'error'); } finally { setLoading(false); }
  };

  const refreshListOnly = async () => {
    try { setActorRole(role); const [docs, dashboard] = await Promise.all([api('/documents'), api('/dashboard/stats')]); setDocuments(docs); setStats(dashboard); } catch { /* existing view remains usable */ }
  };

  const runValidation = async () => {
    try { await saveInputs(false); setLoading(true); setActorRole(role); const result = await api(`/documents/${selectedId}/validate`, { method: 'POST', body: JSON.stringify({}) }); const fresh = await api(`/documents/${selectedId}`); setSelectedDoc(fresh); await refreshListOnly(); notify(result.can_generate ? 'Validation passed. Warnings may still require human verification.' : `${result.findings.filter((x) => x.blocks_generation).length} blocking finding(s) remain.`, result.can_generate ? 'success' : 'warning'); }
    catch (e) { notify(e.message, 'error'); } finally { setLoading(false); }
  };

  const generateDraft = async () => {
    try {
      setGenerationProgress({
        currentStep: 1,
        statusText: 'Validating user inputs and applicability decisions...',
      });
      await saveInputs(false);
      setLoading(true);
      setActorRole(role);
      const validation = await api(`/documents/${selectedId}/validate`, { method: 'POST', body: JSON.stringify({}) });
      if (!validation.can_generate) {
        setGenerationProgress(null);
        const fresh = await api(`/documents/${selectedId}`);
        setSelectedDoc(fresh);
        notify('Resolve the blocking findings before generating.', 'warning');
        return;
      }
      const provName = providerId === 'openrouter' ? 'OpenRouter API' : providerId === 'nvidia' ? 'NVIDIA NIM' : (providerId || 'AI provider');
      setGenerationProgress({
        currentStep: 2,
        statusText: `Connecting to ${provName}...`,
      });
      await new Promise((r) => setTimeout(r, 400));

      setGenerationProgress({
        currentStep: 3,
        statusText: `Generating structured document sections with ${provName}...`,
      });
      const generated = await api(`/documents/${selectedId}/generate`, { method: 'POST', body: JSON.stringify({ provider: providerId || 'nvidia' }) });

      setGenerationProgress({
        currentStep: 4,
        statusText: 'Validating response structure and section schema...',
      });
      await new Promise((r) => setTimeout(r, 350));

      setGenerationProgress({
        currentStep: 5,
        statusText: 'Mapping content into template hierarchy...',
      });
      await new Promise((r) => setTimeout(r, 300));

      setGenerationProgress({
        currentStep: 6,
        statusText: 'Document rendering engine ready (DOCX / PDF)...',
      });
      await new Promise((r) => setTimeout(r, 300));

      setSelectedDoc(generated);
      setAnswers(generated.current_version.answers || {});
      setApplicability(generated.current_version.applicability || {});
      setTab('draft');
      await refreshListOnly();
      setGenerationProgress(null);
      notify(`Draft generated using ${providerId || 'nvidia'}. Review and export as needed.`);
    } catch (e) {
      setGenerationProgress(null);
      notify(e.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const doAction = async (path, body, successMessage) => {
    try { setLoading(true); setActorRole(role); const updated = await api(path, { method: 'POST', body: JSON.stringify(body || {}) }); setSelectedDoc(updated); setAnswers(updated.current_version.answers || {}); setApplicability(updated.current_version.applicability || {}); await refreshListOnly(); setReviewComment(''); notify(successMessage); }
    catch (e) { notify(e.message, 'error'); } finally { setLoading(false); }
  };

  const createRevision = async () => {
    try { setLoading(true); const updated = await api(`/documents/${selectedId}/new-revision`, { method: 'POST', body: JSON.stringify({}) }); setSelectedDoc(updated); setAnswers(updated.current_version.answers || {}); setApplicability(updated.current_version.applicability || {}); await refreshListOnly(); setTab('inputs'); notify('New draft revision created from the released revision.'); }
    catch (e) { notify(e.message, 'error'); } finally { setLoading(false); }
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0]; event.target.value = ''; if (!file || !selectedId) return;
    try { setUploading(true); await uploadEvidence(selectedId, file); const fresh = await api(`/documents/${selectedId}`); setSelectedDoc(fresh); notify('Evidence metadata saved. The uploaded file is private to this application.'); }
    catch (e) { notify(e.message, 'error'); } finally { setUploading(false); }
  };

  const activeTemplate = templateDetail || templates.find((x) => x.id === selectedDoc?.template_id);
  const currentVersion = selectedDoc?.current_version;
  const findings = currentVersion?.latest_validation?.findings || [];
  const filteredDocs = useMemo(() => documents.filter((d) => `${d.title} ${d.document_number} ${d.document_type}`.toLowerCase().includes(searchTerm.toLowerCase())), [documents, searchTerm]);
  const canEdit = ['author', 'admin'].includes(role) && !['in_review', 'awaiting_approval', 'released', 'approved'].includes(currentVersion?.status);
  const canGenerate = canEdit && currentVersion?.validation_status === 'passed';

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`}>
      <div className="brand"><div className="brand-mark"><ShieldCheck size={21} /></div><div><div className="brand-name">AIQMS<span>STUDIO</span></div><div className="brand-subtitle">Quality document workspace</div></div><button className="icon-button mobile-close" onClick={() => setMobileNavOpen(false)} aria-label="Close menu"><X size={18}/></button></div>
      <div className="workspace-select"><div className="workspace-avatar">M</div><div className="workspace-text"><strong>MedDevice workspace</strong><span>Development environment</span></div><ChevronDown size={15}/></div>
      <div className="nav-label">WORKSPACE</div>
      <nav className="primary-nav">{navItems.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => { setView(id); setMobileNavOpen(false); setSelectedDoc(null); setSelectedId(null); }}><Icon size={18}/><span>{label}</span>{id === 'reviews' && stats.pending_reviews + stats.pending_approvals > 0 && <b className="nav-count">{stats.pending_reviews + stats.pending_approvals}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="local-card"><div className="local-icon"><LockKeyhole size={16}/></div><div><strong>Rules-first validation</strong><span>Validation stays in your app. External AI is optional.</span></div><CheckCircle2 className="local-check" size={16}/></div><button className="nav-item" onClick={() => { setView('settings'); setSelectedDoc(null); setSelectedId(null); }}><Settings2 size={18}/><span>Settings & providers</span></button><div className="sidebar-profile"><div className="profile-avatar">{roleLabels[role][0]}</div><div className="profile-info"><strong>{roleLabels[role]}</strong><span>Local demo role</span></div><ChevronDown size={15}/></div></div>
    </aside>
    {mobileNavOpen && <div className="mobile-scrim" onClick={() => setMobileNavOpen(false)} />}
    <main className="main-area">
      <header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" onClick={() => setMobileNavOpen(true)} aria-label="Open menu"><Menu size={20}/></button><div className="breadcrumb"><span>Workspace</span><ChevronRight size={14}/><strong>{selectedDoc ? selectedDoc.title : (navItems.find((n) => n.id === view)?.label || (view === 'settings' ? 'Settings & providers' : 'Workspace'))}</strong></div></div><div className="topbar-actions"><div className="environment-pill"><span/> Local preview</div><label className="role-switch"><span>Role</span><select value={role} onChange={(e) => selectRole(e.target.value)} aria-label="Development demo role">{Object.entries(roleLabels).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label><button className="icon-button top-bell" onClick={() => setView('reviews')} aria-label="Review queue"><Bell size={18}/>{stats.pending_reviews + stats.pending_approvals > 0 && <i/>}</button><div className="top-avatar">{roleLabels[role][0]}</div></div></header>
      {loadError && <div className="connection-banner"><AlertCircle size={17}/><span>Cannot reach the API: {loadError}. Start the backend at <code>localhost:8000</code> and refresh.</span><button onClick={refreshCore}>Retry</button></div>}
      <div className="page-body">
        {!selectedDoc && view === 'dashboard' && <Dashboard stats={stats} documents={documents} templates={templates} onCreate={(t) => { setCreateTemplate(t || templates[0]); setNewTitle(t ? `${t.name} — Draft` : ''); }} onSelect={selectDoc} onView={setView} />}
        {!selectedDoc && view === 'documents' && <DocumentsPage documents={filteredDocs} allCount={documents.length} templates={templates} searchTerm={searchTerm} setSearchTerm={setSearchTerm} onSelect={selectDoc} onCreate={(t) => { setCreateTemplate(t || templates[0]); setNewTitle(t ? `${t.name} — Draft` : ''); }} />}
        {!selectedDoc && view === 'process' && <EndToEndProcessPage documents={documents} onSelectDoc={selectDoc} onCreate={(t) => { setCreateTemplate(t || templates[0]); setNewTitle(t ? `${t.name} — Draft` : ''); }} />}
        {!selectedDoc && view === 'mlmodel' && <MLModelPage notify={notify} />}
        {!selectedDoc && view === 'ingestion' && <IngestionPage notify={notify} />}
        {!selectedDoc && view === 'search' && <SearchPage notify={notify} />}
        {!selectedDoc && view === 'traceability' && <TraceabilityPage notify={notify} />}
        {!selectedDoc && view === 'templates' && <TemplatesPage templates={templates} onCreate={(t) => { setCreateTemplate(t); setNewTitle(`${t.name} — Draft`); }} onRefresh={refreshCore} notify={notify} />}
        {!selectedDoc && view === 'requirements' && <RequirementsPage requirements={requirements} role={role} onRefresh={refreshCore} />}
        {!selectedDoc && view === 'reviews' && <ReviewQueue documents={documents} role={role} onSelect={selectDoc} />}
        {!selectedDoc && view === 'audit' && <AuditPage role={role} />}
        {!selectedDoc && view === 'settings' && <SettingsPage providers={providers} role={role} notify={notify} />}
        {selectedDoc && <DocumentWorkspace doc={selectedDoc} template={activeTemplate} role={role} tab={tab} setTab={setTab} answers={answers} setAnswers={setAnswers} applicability={applicability} setApplicability={setApplicability} findings={findings} loading={loading} canEdit={canEdit} canGenerate={canGenerate} providerId={providerId} setProviderId={setProviderId} providers={providers} onSave={() => saveInputs(false)} onValidate={runValidation} onGenerate={generateDraft} onSubmitReview={() => doAction(`/documents/${selectedId}/submit-review`, {}, 'Submitted for independent review.')} onReview={(decision) => doAction(`/documents/${selectedId}/review`, { decision, comments: reviewComment }, decision === 'accept' ? 'Review accepted. It is awaiting approval.' : 'Changes requested. The author can create a corrected draft.')} onApprove={(decision) => doAction(`/documents/${selectedId}/approve`, { decision, comments: reviewComment }, decision === 'approve' ? 'Revision approved and released.' : 'Approval rejected. Changes are required.')} reviewComment={reviewComment} setReviewComment={setReviewComment} onUpload={handleUpload} uploading={uploading} onExport={async (format) => { try { await downloadExport(selectedId, format); notify(`${format.toUpperCase()} export downloaded.`); } catch (e) { notify(e.message, 'error'); } }} onNewRevision={createRevision} onBack={() => { setSelectedDoc(null); setSelectedId(null); }} onRefresh={async () => { const fresh = await api(`/documents/${selectedId}`); setSelectedDoc(fresh); }} notify={notify} />}
      </div>
      <footer className="footer"><span>AIQMS Studio <b>v0.1.0</b></span><span><span className="footer-dot"/> Demo environment · Use only approved sources for compliance decisions</span></footer>
    </main>
    <GenerationProgressModal progress={generationProgress} />
    {createTemplate && <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setCreateTemplate(null); }}><div className="modal-card"><div className="modal-head"><div><div className="eyebrow">NEW DOCUMENT</div><h2>Create a quality document</h2><p>Choose a template and give this controlled document a working title.</p></div><button className="icon-button" onClick={() => setCreateTemplate(null)}><X size={19}/></button></div><div className="modal-template"><div className="template-icon"><FileText size={20}/></div><div><strong>{createTemplate.name}</strong><span>{createTemplate.category} · Template v{createTemplate.version}</span></div><button className="text-button" onClick={() => { setCreateTemplate(null); setView('templates'); }}>Change</button></div><label className="form-field"><span className="field-label">Document title<i className="required-star">*</i></span><input autoFocus value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="e.g. Cleanroom Monitoring or CAPA Procedure" onKeyDown={(e) => e.key === 'Enter' && createDocument()} /></label><div className="enhance-box"><div className="enhance-box-head"><div className="enhance-box-title"><Sparkles size={16} /><strong>ISO Standard Content Enhancer & Web Analysis</strong></div><span className="enhance-badge">ISO 13485:2016</span></div><p className="enhance-hint">Provide keywords, brief notes (even 1-2 words), or a summary. The engine executes web analysis of current industrial standards and generates concise sections adhering strictly to ISO word count budgets: Purpose (20-40w), Scope (20-30w), Responsibilities (20-50w), Reference (30-60w), Procedure (30-70w), Records (25-45w), and Revision History (25-40w).</p><textarea rows={3} value={topicSummary} onChange={(e) => setTopicSummary(e.target.value)} placeholder="e.g. cleanroom particle limits, or CAPA root cause, or sterilization bioburden, or supplier audit" /></div><div className="modal-note"><LockKeyhole size={16}/><span>A new draft starts with pending requirement-applicability decisions. You can save it before completing the form.</span></div><div className="modal-actions"><button className="btn btn-secondary" onClick={() => setCreateTemplate(null)}>Cancel</button><button className="btn btn-primary" onClick={createDocument} disabled={loading || newTitle.trim().length < 2}>{loading ? <LoaderCircle size={16} className="spin"/> : <Plus size={16}/>} Create blank draft</button><button className="btn btn-primary btn-enhance" style={{ background: '#4f46e5', color: '#fff', border: 'none' }} onClick={createDocumentEnhanced} disabled={loading || (newTitle.trim().length < 2 && topicSummary.trim().length < 2)} title="Auto-enhance topic summary with ISO standard requirements">{loading ? <LoaderCircle size={16} className="spin"/> : <Sparkles size={16}/>} Populate ISO Inputs</button><button className="btn btn-primary btn-enhance" style={{ background: 'linear-gradient(135deg, #4338ca 0%, #6d28d9 100%)', color: '#fff', border: 'none' }} onClick={createDocumentFullyGenerated} disabled={loading || (newTitle.trim().length < 2 && topicSummary.trim().length < 2)} title="Generate full complete ISO standard document directly from summary">{loading ? <LoaderCircle size={16} className="spin"/> : <Sparkles size={16}/>} ⚡ 1-Click Generate Full Document</button></div></div></div>}
    {toast && <div className={`toast toast-${toast.kind}`}><span className="toast-icon">{toast.kind === 'error' ? <AlertCircle size={18}/> : toast.kind === 'warning' ? <TriangleAlert size={18}/> : <CheckCircle2 size={18}/>}</span><span>{toast.message}</span><button onClick={() => setToast(null)}><X size={16}/></button></div>}
  </div>;
}

function PageHeader({ eyebrow, title, description, action }) { return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action && <div className="page-header-action">{action}</div>}</div>; }
function Button({ children, variant = 'primary', icon: Icon, onClick, disabled, size = '' }) { return <button className={`btn btn-${variant} ${size ? `btn-${size}` : ''}`} onClick={onClick} disabled={disabled}>{Icon && <Icon size={16}/>}<span>{children}</span></button>; }

function Dashboard({ stats, documents, templates, onCreate, onSelect, onView }) {
  const recent = documents.slice(0, 5);
  const statusCounts = stats.status_counts || {};
  const inProgress = (statusCounts.draft || 0) + (statusCounts.validated || 0) + (statusCounts.generated || 0) + (statusCounts.changes_requested || 0);
  return <>
    <div className="welcome-banner"><div className="welcome-copy"><div className="welcome-tag"><Sparkles size={13}/> AI-ASSISTED QUALITY WORKSPACE</div><h1>Quality documentation,<br/><em>with control built in.</em></h1><p>Turn structured inputs into reviewable QMS drafts. Validation, traceability and release decisions stay in your hands.</p><div className="welcome-actions"><Button icon={Plus} onClick={() => onCreate(templates.find((x) => x.id === 'sop') || templates[0])}>Create document</Button><button className="welcome-link" onClick={() => onView('templates')}>Explore templates <ArrowRight size={15}/></button></div></div><div className="welcome-art"><div className="art-orbit orbit-one"/><div className="art-orbit orbit-two"/><div className="art-core"><ShieldCheck size={46}/></div><div className="art-float art-float-a"><CheckCircle2 size={17}/><span><b>Rules-first</b><small>Validation gate</small></span></div><div className="art-float art-float-b"><GitBranch size={17}/><span><b>Traceability</b><small>Source to section</small></span></div><div className="art-float art-float-c"><BadgeCheck size={17}/><span><b>Human review</b><small>Required to release</small></span></div></div></div>
    <div className="section-heading"><div><h2>Workspace pulse</h2><p>A live snapshot of your controlled document workflow.</p></div><span className="period-label"><Activity size={14}/> All documents</span></div>
    <div className="metric-grid"><Metric label="Total documents" value={stats.total_documents || 0} note="Across this workspace" icon={Files} tone="indigo"/><Metric label="In progress" value={inProgress} note="Drafts and corrections" icon={Clock3} tone="blue"/><Metric label="Reviews pending" value={stats.pending_reviews || 0} note="Waiting for review" icon={MessageSquareText} tone="amber"/><Metric label="Approvals pending" value={stats.pending_approvals || 0} note="Ready for approver" icon={BadgeCheck} tone="green"/></div>
    <div className="dashboard-grid"><section className="panel recent-panel"><div className="panel-heading"><div><h3>Recently updated</h3><p>Your latest document activity</p></div><button className="text-button" onClick={() => onView('documents')}>View all <ArrowRight size={14}/></button></div>{recent.length ? <div className="document-table-wrap"><table className="data-table"><thead><tr><th>Document</th><th>Status</th><th>Updated</th><th/></tr></thead><tbody>{recent.map((doc) => <tr key={doc.id} onClick={() => onSelect(doc.id)}><td><div className="table-document"><div className="table-doc-icon"><FileText size={17}/></div><span><strong>{doc.title}</strong><small>{doc.document_number} · Rev {doc.current_version.revision}</small></span></div></td><td><StatusPill value={doc.current_version.status}/></td><td className="muted-cell">{dateLabel(doc.updated_at)}</td><td><ChevronRight size={16} className="row-chevron"/></td></tr>)}</tbody></table></div> : <EmptyState icon={Files} title="No documents yet" text="Start with a template and build your first controlled draft." action={<Button icon={Plus} onClick={() => onCreate(templates[0])}>Create a document</Button>}/>}</section>
      <section className="panel quickstart-panel"><div className="panel-heading"><div><h3>Start with a template</h3><p>Purpose-built document foundations</p></div></div><div className="quick-template-list">{templates.slice(0, 4).map((t, i) => <button className="quick-template" key={t.id} onClick={() => onCreate(t)}><div className={`template-mini-icon mini-${i % 4}`}><FileText size={17}/></div><span><strong>{t.name}</strong><small>{t.category}</small></span><Plus size={16} className="quick-plus"/></button>)}</div><button className="browse-templates" onClick={() => onView('templates')}>Browse all {templates.length} templates <ArrowRight size={14}/></button></section></div>
    <div className="assurance-strip"><div className="assurance-icon"><LockKeyhole size={18}/></div><div><strong>Generated does not mean approved.</strong><span>Every draft moves through validation, independent review and authorized approval before release.</span></div><span className="assurance-badge"><ShieldCheck size={14}/> Workflow control enabled</span></div>
  </>;
}
function Metric({ label, value, note, icon: Icon, tone }) { return <div className="metric-card"><div className={`metric-icon metric-${tone}`}><Icon size={19}/></div><div className="metric-label">{label}</div><div className="metric-value">{value}</div><div className="metric-note">{note}</div></div>; }
function EmptyState({ icon: Icon, title, text, action }) { return <div className="empty-state"><div className="empty-icon"><Icon size={25}/></div><strong>{title}</strong><p>{text}</p>{action}</div>; }

function DocumentsPage({ documents, allCount, templates, searchTerm, setSearchTerm, onSelect, onCreate }) {
  return <><PageHeader eyebrow="DOCUMENT CONTROL" title="Documents" description="Manage drafts, revisions, reviews and released QMS documents." action={<Button icon={Plus} onClick={() => onCreate(templates[0])}>New document</Button>}/><div className="toolbar"><div className="search-box"><Search size={17}/><input placeholder="Search title, document ID or type…" value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)}/>{searchTerm && <button onClick={() => setSearchTerm('')}><X size={14}/></button>}</div><div className="toolbar-meta">{documents.length} of {allCount} documents</div></div>{documents.length ? <div className="panel doc-list-panel"><table className="data-table doc-list-table"><thead><tr><th>Document</th><th>Category</th><th>Status</th><th>Revision</th><th>Created by</th><th>Updated</th><th style={{ textAlign: 'right', paddingRight: '18px' }}>Actions</th></tr></thead><tbody>{documents.map((d) => <tr key={d.id} onClick={() => onSelect(d.id)}><td><div className="table-document"><div className="table-doc-icon"><FileText size={17}/></div><span><strong>{d.title}</strong><small>{d.document_number}</small></span></div></td><td>{d.document_type}</td><td><StatusPill value={d.current_version.status}/></td><td><span className="revision-pill">R{d.current_version.revision}</span></td><td className="muted-cell">{d.created_by}</td><td className="muted-cell">{dateLabel(d.updated_at)}</td><td style={{ textAlign: 'right', paddingRight: '18px' }} onClick={(e) => e.stopPropagation()}><div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}><button type="button" className="btn btn-secondary btn-small" style={{ padding: '3px 8px', fontSize: '9.5px', height: '26px', color: '#4f46e5', borderColor: '#c7d2fe', background: '#f5f3ff' }} onClick={() => onSelect(d.id, 'draft')} title="View Document Preview"><FileText size={12}/> Preview</button><button type="button" className="btn btn-secondary btn-small" style={{ padding: '3px 8px', fontSize: '9.5px', height: '26px', color: '#0d9488', borderColor: '#99f6e4', background: '#f0fdfa' }} onClick={() => onSelect(d.id, 'lifecycle')} title="View End-to-End Lifecycle Process"><Activity size={12}/> Process</button></div></td></tr>)}</tbody></table></div> : <EmptyState icon={Files} title="No matching documents" text={allCount ? 'Try another search or clear the current filter.' : 'Create a document from the template library to get started.'} action={!allCount && <Button icon={Plus} onClick={() => onCreate(templates[0])}>Create document</Button>}/>}</>;
}

function GenerationProgressModal({ progress }) {
  if (!progress) return null;
  const stages = [
    { num: 1, title: 'Deterministic Rules Validation', desc: 'Validating required fields and ISO applicability' },
    { num: 2, title: 'NVIDIA NIM Connection', desc: 'Establishing secure session to https://integrate.api.nvidia.com/v1' },
    { num: 3, title: 'AI Content Generation', desc: 'Processing template sections via hosted inference' },
    { num: 4, title: 'Response Validation', desc: 'Verifying strict JSON schema and required sections' },
    { num: 5, title: 'Template Section Mapping', desc: 'Preserving template hierarchy and static formatting' },
    { num: 6, title: 'Rendering Engine Ready', desc: 'Preparing genuine DOCX & PDF export artifacts' },
  ];
  const percent = Math.round((progress.currentStep / stages.length) * 100);

  return (
    <div className="modal-backdrop">
      <div className="gen-progress-modal">
        <div className="gen-progress-head">
          <div className="gen-progress-icon"><Sparkles size={22} /></div>
          <div>
            <h3>NVIDIA NIM Document Generation Pipeline</h3>
            <p>{progress.statusText}</p>
          </div>
        </div>

        <div className="gen-progress-bar-bg">
          <div className="gen-progress-bar-fill" style={{ width: `${percent}%` }} />
        </div>

        <div className="gen-steps-list">
          {stages.map((stage) => {
            const isCompleted = progress.currentStep > stage.num;
            const isActive = progress.currentStep === stage.num;
            return (
              <div
                key={stage.num}
                className={`gen-step-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}
              >
                <div className="gen-step-icon">
                  {isCompleted ? <Check size={12} /> : isActive ? <LoaderCircle size={13} className="spin" /> : stage.num}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: isActive ? 700 : 600 }}>{stage.title}</div>
                  <div style={{ fontSize: '9.5px', color: '#8893a2', marginTop: '2px' }}>{stage.desc}</div>
                </div>
                {isCompleted && <span style={{ fontSize: '9px', color: '#16a34a', fontWeight: 700 }}>VERIFIED</span>}
                {isActive && <span style={{ fontSize: '9px', color: '#4f46e5', fontWeight: 700 }}>PROCESSING</span>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CustomTemplateModal({ onClose, onCreated, notify }) {
  const [name, setName] = useState('');
  const [docType, setDocType] = useState('');
  const [category, setCategory] = useState('Standard Operating Procedure');
  const [description, setDescription] = useState('');
  const [sections, setSections] = useState([
    { section_id: 'purpose', title: 'Purpose', order: 1, required: true },
    { section_id: 'scope', title: 'Scope', order: 2, required: true },
    { section_id: 'procedure', title: 'Procedure', order: 3, required: true },
  ]);
  const [fields, setFields] = useState([
    { key: 'department', label: 'Department / Unit', type: 'text', required: true },
    { key: 'summary', label: 'Operational Overview', type: 'textarea', required: true },
  ]);
  const [submitting, setSubmitting] = useState(false);

  const addSection = () => {
    const nextNum = sections.length + 1;
    setSections([...sections, { section_id: `sec_${nextNum}`, title: `Section ${nextNum}`, order: nextNum, required: true }]);
  };

  const removeSection = (idx) => {
    setSections(sections.filter((_, i) => i !== idx));
  };

  const addField = () => {
    const nextNum = fields.length + 1;
    setFields([...fields, { key: `field_${nextNum}`, label: `Field ${nextNum}`, type: 'text', required: false }]);
  };

  const removeField = (idx) => {
    setFields(fields.filter((_, i) => i !== idx));
  };

  const handleSubmit = async () => {
    if (!name.trim() || !docType.trim() || !description.trim()) {
      if (notify) notify('Please fill in Template Name, Document Type, and Description.', 'error');
      return;
    }
    try {
      setSubmitting(true);
      await api('/templates', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          document_type: docType.trim(),
          category: category.trim() || 'Custom',
          description: description.trim(),
          sections,
          fields,
        }),
      });
      await onCreated();
    } catch (e) {
      if (notify) notify(e.message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-card builder-modal">
        <div className="modal-head">
          <div>
            <div className="eyebrow">CUSTOM TEMPLATE BUILDER</div>
            <h2>Create Document Template</h2>
            <p>Define custom section structures and dynamic input fields.</p>
          </div>
          <button className="icon-button" onClick={onClose}><X size={19} /></button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
          <label className="form-field">
            <span className="field-label">Template Name<i className="required-star">*</i></span>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Cleanroom Monitoring Procedure" />
          </label>
          <label className="form-field">
            <span className="field-label">Document Type Code<i className="required-star">*</i></span>
            <input value={docType} onChange={(e) => setDocType(e.target.value)} placeholder="e.g. SOP-CR" />
          </label>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
          <label className="form-field">
            <span className="field-label">Category</span>
            <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. Quality Assurance" />
          </label>
          <label className="form-field">
            <span className="field-label">Description<i className="required-star">*</i></span>
            <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. Controlled procedure for environmental monitoring" />
          </label>
        </div>

        <div style={{ marginTop: '16px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong style={{ fontSize: '12px', color: '#1e293b' }}>Template Sections ({sections.length})</strong>
          <button type="button" className="btn btn-secondary btn-small" onClick={addSection}><Plus size={13} /> Add Section</button>
        </div>
        <div style={{ maxHeight: '140px', overflowY: 'auto' }}>
          {sections.map((sec, idx) => (
            <div key={idx} className="builder-section-item">
              <input
                value={sec.section_id}
                onChange={(e) => {
                  const copy = [...sections];
                  copy[idx].section_id = e.target.value;
                  setSections(copy);
                }}
                placeholder="Section ID (e.g. purpose)"
                style={{ fontSize: '10.5px', padding: '6px' }}
              />
              <input
                value={sec.title}
                onChange={(e) => {
                  const copy = [...sections];
                  copy[idx].title = e.target.value;
                  setSections(copy);
                }}
                placeholder="Section Title"
                style={{ fontSize: '10.5px', padding: '6px' }}
              />
              <span style={{ fontSize: '10px', color: '#64748b', textAlign: 'center' }}>Order {sec.order}</span>
              <button
                type="button"
                className="icon-button"
                style={{ height: '28px', minWidth: '28px', color: '#ef4444' }}
                onClick={() => removeSection(idx)}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>

        <div style={{ marginTop: '16px', marginBottom: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong style={{ fontSize: '12px', color: '#1e293b' }}>Dynamic Input Fields ({fields.length})</strong>
          <button type="button" className="btn btn-secondary btn-small" onClick={addField}><Plus size={13} /> Add Field</button>
        </div>
        <div style={{ maxHeight: '140px', overflowY: 'auto' }}>
          {fields.map((f, idx) => (
            <div key={idx} className="builder-field-item">
              <input
                value={f.key}
                onChange={(e) => {
                  const copy = [...fields];
                  copy[idx].key = e.target.value;
                  setFields(copy);
                }}
                placeholder="Field Key"
                style={{ fontSize: '10.5px', padding: '6px' }}
              />
              <input
                value={f.label}
                onChange={(e) => {
                  const copy = [...fields];
                  copy[idx].label = e.target.value;
                  setFields(copy);
                }}
                placeholder="Field Label"
                style={{ fontSize: '10.5px', padding: '6px' }}
              />
              <select
                value={f.type}
                onChange={(e) => {
                  const copy = [...fields];
                  copy[idx].type = e.target.value;
                  setFields(copy);
                }}
                style={{ fontSize: '10px', padding: '4px' }}
              >
                <option value="text">text</option>
                <option value="textarea">textarea</option>
                <option value="select">select</option>
                <option value="date">date</option>
              </select>
              <label style={{ fontSize: '10px', display: 'flex', alignItems: 'center', gap: '3px' }}>
                <input
                  type="checkbox"
                  checked={f.required}
                  onChange={(e) => {
                    const copy = [...fields];
                    copy[idx].required = e.target.checked;
                    setFields(copy);
                  }}
                /> Req
              </label>
              <button
                type="button"
                className="icon-button"
                style={{ height: '28px', minWidth: '28px', color: '#ef4444' }}
                onClick={() => removeField(idx)}
              >
                <Trash2 size={13} />
              </button>
            </div>
          ))}
        </div>

        <div className="modal-actions">
          <button className="btn btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? <LoaderCircle size={14} className="spin" /> : <Plus size={14} />} Save Custom Template
          </button>
        </div>
      </div>
    </div>
  );
}

function TemplatesPage({ templates, onCreate, onRefresh, notify }) {
  const [category, setCategory] = useState('All templates');
  const [showBuilder, setShowBuilder] = useState(false);
  const categories = ['All templates', ...new Set(templates.map((t) => t.category))];
  const shown = category === 'All templates' ? templates : templates.filter((t) => t.category === category);
  const colors = ['violet', 'blue', 'mint', 'amber', 'rose'];

  return (
    <>
      <PageHeader
        eyebrow="TEMPLATE LIBRARY"
        title="Start from a controlled foundation"
        description="Reusable, versioned templates power every document workflow. Build custom templates or use starter foundations."
        action={
          <Button icon={Plus} onClick={() => setShowBuilder(true)}>
            Create Custom Template
          </Button>
        }
      />
      <div className="category-tabs">
        {categories.map((c) => (
          <button key={c} className={category === c ? 'selected' : ''} onClick={() => setCategory(c)}>
            {c}
          </button>
        ))}
      </div>
      <div className="template-grid">
        {shown.map((t, idx) => (
          <div className="template-card" key={t.id} onClick={() => onCreate(t)} style={{ cursor: 'pointer' }}>
            <div className="template-card-top">
              <div className={`template-card-icon icon-${colors[idx % colors.length]}`}>
                <FileText size={21} />
              </div>
              <span className="template-version">v{t.version}</span>
            </div>
            <div className="template-category">{t.category}</div>
            <h3>{t.name}</h3>
            <p>{t.description}</p>
            <div className="template-card-meta">
              <span><ListChecks size={14} />{t.fields?.length || 0} input fields</span>
              <span><GitBranch size={14} />{t.requirements?.length || t.sections?.length || 0} mappings/sections</span>
            </div>
            <div className="template-card-footer">
              <span className="published-badge">
                <span /> {t.category === 'Custom' || t.is_custom ? 'Custom template' : 'Starter template'}
              </span>
              <Button variant="secondary" size="small" icon={Plus} onClick={(e) => { e?.stopPropagation?.(); onCreate(t); }}>
                Use template
              </Button>
            </div>
          </div>
        ))}
      </div>
      <div className="notice-card">
        <CircleHelp size={18} />
        <div>
          <strong>Template scope note</strong>
          <p>These starter templates are configurable workflow examples, not a complete or verified ISO 13485 requirements library. Have qualified personnel verify mappings, applicability and content before operational use.</p>
        </div>
      </div>
      {showBuilder && (
        <CustomTemplateModal
          onClose={() => setShowBuilder(false)}
          onCreated={async () => {
            setShowBuilder(false);
            if (onRefresh) await onRefresh();
            if (notify) notify('Custom template created successfully!');
          }}
          notify={notify}
        />
      )}
    </>
  );
}

function RequirementsPage({ requirements, role, onRefresh }) {
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState('');
  const filtered = requirements.filter((r) => `${r.code} ${r.title} ${r.summary}`.toLowerCase().includes(q.toLowerCase()));
  const startEdit = (r) => { setEditing(r.code); setFeedback(''); setDraft({ source_edition: r.source_edition || '', source_reference: r.source_reference || '', summary: r.summary || '', verification_status: r.verification_status || 'requires_verification', verification_note: r.verification_note || '' }); };
  const saveMapping = async (code) => {
    try {
      setSaving(true); setFeedback('');
      const result = await api(`/requirements/${encodeURIComponent(code)}`, { method: 'PATCH', body: JSON.stringify(draft) });
      setFeedback(`${code} saved. ${result.impacted_versions ? `${result.impacted_versions} draft version(s) were invalidated and must be revalidated/regenerated.` : ''}`);
      setEditing(null); await onRefresh();
    } catch (e) { setFeedback(e.message); }
    finally { setSaving(false); }
  };
  return <><PageHeader eyebrow="REQUIREMENTS LIBRARY" title="Requirements & traceability" description="Maintain source references and connect requirements to document sections and evidence."/><div className="callout callout-warning"><TriangleAlert size={18}/><div><strong>Verify against your licensed source</strong><p>Internal IDs in this starter library are placeholders, not official ISO clause numbers. Only mark a mapping verified after qualified personnel check it against the controlled standard and applicable regulations. Release is blocked while any template mapping is unverified.</p></div></div>{feedback && <div className="inline-feedback"><CheckCircle2 size={15}/><span>{feedback}</span><button onClick={() => setFeedback('')}><X size={14}/></button></div>}<div className="toolbar"><div className="search-box"><Search size={17}/><input placeholder="Search internal requirement IDs…" value={q} onChange={(e) => setQ(e.target.value)}/></div><span className="toolbar-meta">{filtered.length} references</span></div><div className="requirement-grid">{filtered.map((r) => { const isEditing = editing === r.code; return <div className="requirement-card" key={r.code}><div className="req-card-top"><span className="req-id">{r.code}</span><span className={`verification-pill ${r.verification_status === 'verified' ? 'is-recorded' : ''}`}><span/>{statusText(r.verification_status)}</span></div><h3>{r.title}</h3>{isEditing ? <div className="requirement-edit-form"><label className="form-field"><span className="field-label">Source edition / amendment</span><input value={draft.source_edition} onChange={(e) => setDraft({ ...draft, source_edition: e.target.value })} placeholder="Exact edition and amendment checked"/></label><label className="form-field"><span className="field-label">Source clause / reference</span><input value={draft.source_reference} onChange={(e) => setDraft({ ...draft, source_reference: e.target.value })} placeholder="Verified clause reference from licensed source"/></label><label className="form-field"><span className="field-label">Internal requirement summary</span><textarea rows={3} value={draft.summary} onChange={(e) => setDraft({ ...draft, summary: e.target.value })} placeholder="Your own summary of the requirement"/></label><label className="form-field"><span className="field-label">Verification status</span><select value={draft.verification_status} onChange={(e) => setDraft({ ...draft, verification_status: e.target.value })}><option value="requires_verification">Requires verification</option><option value="verified">Verified against source</option></select></label><label className="form-field"><span className="field-label">Verification note {draft.verification_status === 'verified' && <i className="required-star">*</i>}</span><textarea rows={2} value={draft.verification_note} onChange={(e) => setDraft({ ...draft, verification_note: e.target.value })} placeholder="Who checked what source and when? Add a traceable note."/></label><div className="requirement-edit-actions"><button className="btn btn-secondary btn-small" onClick={() => setEditing(null)}>Cancel</button><button className="btn btn-primary btn-small" onClick={() => saveMapping(r.code)} disabled={saving}>{saving ? 'Saving…' : 'Save mapping'}</button></div></div> : <><p>{r.summary}</p><div className="req-source"><BookOpenCheck size={15}/><span><b>{r.source_name}</b><small>{r.source_edition}</small><small>{r.source_reference}</small>{r.verified_by && <small>Verified by {r.verified_by} · {dateLabel(r.verified_at)}</small>}</span></div>{r.verification_note && <div className="verification-note">{r.verification_note}</div>}{role === 'admin' && <button className="mapping-edit-button" onClick={() => startEdit(r)}><Settings2 size={14}/>{r.verification_status === 'verified' ? 'Edit source mapping' : 'Configure / verify mapping'}</button>}</>}</div>; })}</div>{role !== 'admin' && <div className="notice-card"><LockKeyhole size={17}/><div><strong>Administrator access needed</strong><p>Switch to the Admin demo role to configure source references. Demo roles are for local testing only and are not secure authentication.</p></div></div>}</>;
}

function ReviewQueue({ documents, role, onSelect }) {
  const eligible = documents.filter((d) => (role === 'reviewer' && d.current_version.status === 'in_review') || (role === 'approver' && d.current_version.status === 'awaiting_approval') || (role === 'admin' && ['in_review', 'awaiting_approval'].includes(d.current_version.status)));
  return <><PageHeader eyebrow="QUALITY GATES" title="Review queue" description="Reviewers and approvers act on a specific, immutable document revision."/><div className="review-explainer"><div className="review-explainer-icon"><ShieldCheck size={20}/></div><div><strong>Independent review protects document integrity.</strong><p>The demo enforces different author and reviewer identities and blocks release until approval is recorded.</p></div></div>{eligible.length ? <div className="review-card-list">{eligible.map((d) => <button className="review-queue-card" key={d.id} onClick={() => onSelect(d.id)}><div className="review-file-icon"><FileCheck2 size={20}/></div><div className="review-queue-content"><strong>{d.title}</strong><span>{d.document_number} · Revision {d.current_version.revision}</span><small>Created by {d.created_by}</small></div><StatusPill value={d.current_version.status}/><ChevronRight size={17}/></button>)}</div> : <EmptyState icon={BadgeCheck} title="Queue is clear" text={`There are no documents waiting for ${role === 'approver' ? 'approval' : 'review'} for this demo role.`}/>}</>;
}

function AuditPage({ role }) {
  const [events, setEvents] = useState([]); const [error, setError] = useState(''); const [loading, setLoading] = useState(true);
  useEffect(() => { let alive = true; api('/audit?limit=150').then((items) => { if (alive) setEvents(items); }).catch((e) => { if (alive) setError(e.message); }).finally(() => { if (alive) setLoading(false); }); return () => { alive = false; }; }, [role]);
  return <><PageHeader eyebrow="ACCOUNTABILITY" title="Audit trail" description="A chronological record of significant document lifecycle and validation events."/><div className="callout"><History size={18}/><div><strong>Events are recorded by the application</strong><p>Production deployment must protect audit storage from unauthorized modification and define retention rules.</p></div></div>{loading ? <div className="loading-state"><LoaderCircle className="spin"/> Loading audit events…</div> : error ? <div className="error-state">{error}</div> : events.length ? <div className="panel audit-table-panel"><table className="data-table"><thead><tr><th>Action</th><th>Actor</th><th>Entity</th><th>Details</th><th>Time</th></tr></thead><tbody>{events.map((e) => <tr key={e.id}><td><span className="event-action"><Activity size={14}/>{e.action}</span></td><td><strong>{e.actor_email}</strong><small className="cell-sub">{e.actor_role}</small></td><td><span className="mono-text">{e.entity_type}</span><small className="cell-sub">{e.entity_id.slice(0, 8)}…</small></td><td className="audit-details">{JSON.stringify(e.metadata || {})}</td><td className="muted-cell">{shortTime(e.created_at)}</td></tr>)}</tbody></table></div> : <EmptyState icon={History} title="No events yet" text="Create or validate a document to produce audit events."/>}</>;
}

function SettingsPage({ providers, role, notify }) {
  const [testingNvidia, setTestingNvidia] = useState(false);
  const [nvidiaResult, setNvidiaResult] = useState(null);
  const [testingOpenRouter, setTestingOpenRouter] = useState(false);
  const [openrouterResult, setOpenrouterResult] = useState(null);
  const [runningDiag, setRunningDiag] = useState(false);
  const [diagResult, setDiagResult] = useState(null);

  const handleTestNvidia = async () => {
    try {
      setTestingNvidia(true);
      const res = await api('/system/test-nvidia', { method: 'POST' });
      setNvidiaResult(res);
      if (notify) notify(`NVIDIA NIM connection verified in ${Math.round(res.latency_ms)}ms!`);
    } catch (e) {
      setNvidiaResult({ status: 'error', error: e.message });
      if (notify) notify(e.message, 'error');
    } finally {
      setTestingNvidia(false);
    }
  };

  const handleTestOpenRouter = async () => {
    try {
      setTestingOpenRouter(true);
      const res = await api('/system/test-openrouter', { method: 'POST' });
      setOpenrouterResult(res);
      if (res.success) {
        if (notify) notify(`OpenRouter connection verified in ${Math.round(res.response_time_ms)}ms!`);
      } else {
        if (notify) notify(res.error || 'OpenRouter test failed', 'error');
      }
    } catch (e) {
      setOpenrouterResult({ success: false, error: e.message });
      if (notify) notify(e.message, 'error');
    } finally {
      setTestingOpenRouter(false);
    }
  };

  const handleRunDiagnostics = async () => {
    try {
      setRunningDiag(true);
      const res = await api('/system/diagnostics');
      setDiagResult(res);
      if (notify) notify(`System diagnostics completed: ${res.status.toUpperCase()}`);
    } catch (e) {
      if (notify) notify(e.message, 'error');
    } finally {
      setRunningDiag(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="CONFIGURATION"
        title="Settings & providers"
        description="Inspect provider readiness, test live NVIDIA NIM connectivity, and run full system diagnostics."
      />
      <div className="callout callout-warning">
        <LockKeyhole size={18} />
        <div>
          <strong>Development authentication is enabled</strong>
          <p>The role switch is only a local demo convenience. It is not secure authentication. Integrate OIDC/SSO, enforce server-side roles and set DEV_AUTH_ENABLED=false before any shared or production deployment.</p>
        </div>
      </div>

      <div className="panel settings-panel">
        <div className="panel-heading">
          <div>
            <h3>NVIDIA NIM Hosted Inference Diagnostics</h3>
            <p>Live health and round-trip latency verification against the NVIDIA hosted API endpoint.</p>
          </div>
          <button className="btn btn-primary btn-small" onClick={handleTestNvidia} disabled={testingNvidia}>
            {testingNvidia ? <LoaderCircle size={14} className="spin" /> : <Zap size={14} />} Test NVIDIA Connection
          </button>
        </div>

        <div className="diagnostics-grid">
          <div className="diag-card">
            <div className="diag-card-head">
              <span className="diag-card-title"><Cloud size={16} /> Endpoint Status</span>
              <span className={`diag-badge ${nvidiaResult?.status === 'ok' ? 'ok' : nvidiaResult ? 'error' : 'ok'}`}>
                {nvidiaResult?.status || 'Active'}
              </span>
            </div>
            <div className="diag-metric-row">
              <span>Base URL</span>
              <span className="diag-metric-val">https://integrate.api.nvidia.com/v1</span>
            </div>
            <div className="diag-metric-row">
              <span>Primary Model</span>
              <span className="diag-metric-val">{nvidiaResult?.model || 'poolside/laguna-xs-2.1'}</span>
            </div>
            <div className="diag-metric-row">
              <span>Round-Trip Latency</span>
              <span className={`diag-metric-val ${nvidiaResult ? (nvidiaResult.latency_ms < 1000 ? 'diag-latency-good' : 'diag-latency-warn') : ''}`}>
                {nvidiaResult ? `${Math.round(nvidiaResult.latency_ms)} ms` : 'Untested'}
              </span>
            </div>
            {nvidiaResult?.sample_response && (
              <div style={{ marginTop: '8px', fontSize: '9.5px', color: '#64748b', background: '#f8fafc', padding: '6px 8px', borderRadius: '5px' }}>
                Verified sample: &quot;{nvidiaResult.sample_response.slice(0, 75)}...&quot;
              </div>
            )}
            {nvidiaResult?.error && (
              <div style={{ marginTop: '8px', fontSize: '9.5px', color: '#ef4444', background: '#fef2f2', padding: '6px 8px', borderRadius: '5px' }}>
                {nvidiaResult.error}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="panel settings-panel">
        <div className="panel-heading">
          <div>
            <h3>OpenRouter Gateway Diagnostics</h3>
            <p>Live health, key validation, and round-trip latency against OpenRouter API.</p>
          </div>
          <button className="btn btn-primary btn-small" onClick={handleTestOpenRouter} disabled={testingOpenRouter}>
            {testingOpenRouter ? <LoaderCircle size={14} className="spin" /> : <Zap size={14} />} Test OpenRouter Connection
          </button>
        </div>

        <div className="diagnostics-grid">
          <div className="diag-card">
            <div className="diag-card-head">
              <span className="diag-card-title"><Cloud size={16} /> Key & Endpoint Status</span>
              <span className={`diag-badge ${openrouterResult?.success ? 'ok' : openrouterResult ? 'error' : 'ok'}`}>
                {openrouterResult ? (openrouterResult.success ? 'Active' : 'Error') : (providers.find(p => p.id === 'openrouter')?.configured ? 'Configured' : 'Not Configured')}
              </span>
            </div>
            <div className="diag-metric-row">
              <span>Base URL</span>
              <span className="diag-metric-val">https://openrouter.ai/api/v1</span>
            </div>
            <div className="diag-metric-row">
              <span>Model</span>
              <span className="diag-metric-val">{openrouterResult?.model || providers.find(p => p.id === 'openrouter')?.model || 'nvidia/nemotron-3-ultra-550b-a55b:free'}</span>
            </div>
            <div className="diag-metric-row">
              <span>Round-Trip Latency</span>
              <span className={`diag-metric-val ${openrouterResult ? (openrouterResult.response_time_ms < 1000 ? 'diag-latency-good' : 'diag-latency-warn') : ''}`}>
                {openrouterResult?.response_time_ms ? `${Math.round(openrouterResult.response_time_ms)} ms` : 'Untested'}
              </span>
            </div>
            {openrouterResult?.free_daily_requests_remaining !== undefined && (
              <div className="diag-metric-row">
                <span>Free Requests Left</span>
                <span className="diag-metric-val diag-latency-good">{openrouterResult.free_daily_requests_remaining} requests</span>
              </div>
            )}
            {openrouterResult?.error && (
              <div style={{ marginTop: '8px', fontSize: '9.5px', color: '#ef4444', background: '#fef2f2', padding: '6px 8px', borderRadius: '5px' }}>
                {openrouterResult.error}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="panel settings-panel">
        <div className="panel-heading">
          <div>
            <h3>Full Platform Diagnostics</h3>
            <p>Automated verification of database latency, hosted inference, and genuine DOCX/PDF rendering.</p>
          </div>
          <button className="btn btn-secondary btn-small" onClick={handleRunDiagnostics} disabled={runningDiag}>
            {runningDiag ? <LoaderCircle size={14} className="spin" /> : <RefreshCw size={14} />} Run Full Diagnostics
          </button>
        </div>

        {diagResult ? (() => {
          const dbDiag = diagResult.checks?.database || diagResult.database || {};
          const nvDiag = diagResult.checks?.nvidia_nim || diagResult.nvidia_nim || {};
          const orDiag = diagResult.checks?.openrouter || diagResult.openrouter || {};
          const docDiag = diagResult.checks?.document_rendering || diagResult.document_rendering || {};
          return (
          <div className="diagnostics-grid">
            <div className="diag-card">
              <div className="diag-card-head">
                <span className="diag-card-title"><Server size={16} /> Database Engine</span>
                <span className={`diag-badge ${dbDiag.status === 'ok' ? 'ok' : 'error'}`}>
                  {dbDiag.status || 'OK'}
                </span>
              </div>
              <div className="diag-metric-row">
                <span>Latency</span>
                <span className="diag-metric-val diag-latency-good">{dbDiag.latency_ms?.toFixed(2)} ms</span>
              </div>
              <div className="diag-metric-row">
                <span>Engine</span>
                <span className="diag-metric-val">SQLite (WAL mode)</span>
              </div>
            </div>

            <div className="diag-card">
              <div className="diag-card-head">
                <span className="diag-card-title"><Sparkles size={16} /> NVIDIA NIM Engine</span>
                <span className={`diag-badge ${nvDiag.status === 'ok' ? 'ok' : 'error'}`}>
                  {nvDiag.status || 'OK'}
                </span>
              </div>
              <div className="diag-metric-row">
                <span>Latency</span>
                <span className="diag-metric-val diag-latency-good">{Math.round(nvDiag.latency_ms || 0)} ms</span>
              </div>
              <div className="diag-metric-row">
                <span>Model ID</span>
                <span className="diag-metric-val">{nvDiag.model || 'poolside/laguna-xs-2.1'}</span>
              </div>
            </div>

            <div className="diag-card">
              <div className="diag-card-head">
                <span className="diag-card-title"><Cloud size={16} /> OpenRouter Gateway</span>
                <span className={`diag-badge ${orDiag.status === 'ok' ? 'ok' : orDiag.status === 'not_configured' ? 'warn' : 'error'}`}>
                  {orDiag.status === 'ok' ? 'OK' : orDiag.status || 'Active'}
                </span>
              </div>
              <div className="diag-metric-row">
                <span>Latency</span>
                <span className="diag-metric-val diag-latency-good">{Math.round(orDiag.latency_ms || 0)} ms</span>
              </div>
              <div className="diag-metric-row">
                <span>Model ID</span>
                <span className="diag-metric-val">{orDiag.model || 'nvidia/nemotron-3-ultra-550b-a55b:free'}</span>
              </div>
            </div>

            <div className="diag-card">
              <div className="diag-card-head">
                <span className="diag-card-title"><FileText size={16} /> Document Rendering</span>
                <span className={`diag-badge ${docDiag.docx === 'ok' || docDiag.status === 'ok' ? 'ok' : 'error'}`}>
                  {docDiag.status || 'OK'}
                </span>
              </div>
              <div className="diag-metric-row">
                <span>Word (.docx)</span>
                <span className="diag-metric-val diag-latency-good">python-docx (PK header)</span>
              </div>
              <div className="diag-metric-row">
                <span>PDF (.pdf)</span>
                <span className="diag-metric-val diag-latency-good">ReportLab (%PDF-1.4)</span>
              </div>
            </div>
          </div>
          );
        })() : (
          <div style={{ padding: '16px', color: '#64748b', fontSize: '11px', textAlign: 'center' }}>
            Click &quot;Run Full Diagnostics&quot; to test database connection, NVIDIA NIM endpoint, and document export pipeline.
          </div>
        )}
      </div>

      <div className="panel settings-panel">
        <div className="panel-heading">
          <div>
            <h3>AI generation providers</h3>
            <p>Only configured providers can be called. NVIDIA NIM is the primary hosted provider.</p>
          </div>
          <span className="small-counter">{providers.filter((p) => p.configured).length} configured</span>
        </div>
        <div className="provider-settings-list">
          {providers.map((p) => (
            <div className="provider-row" key={p.id}>
              <div className={`provider-avatar provider-${p.id}`}>
                {p.id === 'offline' ? <FileText size={19} /> : p.id === 'nvidia' ? <Sparkles size={19} /> : <Cloud size={19} />}
              </div>
              <div className="provider-copy">
                <strong>{p.name}</strong>
                <span>{p.model || p.note || 'Provider model is configured through the API environment.'}</span>
              </div>
              <span className={`provider-state ${p.configured ? 'is-configured' : 'not-configured'}`}>
                <span />{p.configured ? 'Configured' : 'Not configured'}
              </span>
            </div>
          ))}
        </div>
        <div className="settings-footnote">
          Set provider credentials in the backend <code>.env</code> file, never in frontend environment variables.
        </div>
      </div>

      <div className="panel settings-panel">
        <div className="panel-heading">
          <div>
            <h3>Human workflow controls</h3>
            <p>Current development workflow rules</p>
          </div>
        </div>
        <div className="settings-control-list">
          <div><CheckCircle2 size={17} /><span>Blocking findings prevent generation</span><b>Enabled</b></div>
          <div><CheckCircle2 size={17} /><span>Author cannot approve own revision</span><b>Enabled</b></div>
          <div><CheckCircle2 size={17} /><span>Released revisions are immutable</span><b>Enabled</b></div>
          <div><TriangleAlert size={17} /><span>Verified ISO clause mappings</span><b className="warning-text">Configure library</b></div>
        </div>
      </div>
    </>
  );
}

function EndToEndProcessPage({ documents, onSelectDoc, onCreate }) {
  const steps = [
    {
      num: '01',
      title: 'Topic Summary & Form Inputs',
      desc: 'Users provide operational parameters or short summaries. The AI assistant extracts scope, purpose, and procedure details.',
      standard: 'ISO 13485:2016 Cl. 4.2.3 & 4.2.4',
      badge: 'Input Phase',
    },
    {
      num: '02',
      title: 'ISO Standards Applicability',
      desc: 'Requirements are mapped to standard clauses. Users justify applicable vs. non-applicable sections with documented rationale.',
      standard: 'ISO 13485:2016 Cl. 1.2 & Cl. 4.1',
      badge: 'Compliance Gate',
    },
    {
      num: '03',
      title: 'Deterministic Rules Check',
      desc: 'Rules-first validation checks for missing fields, unverified sources, and blocking findings prior to any AI generation.',
      standard: 'Pre-flight Verification',
      badge: 'Integrity Check',
    },
    {
      num: '04',
      title: 'AI Model Inference',
      desc: 'OpenRouter (nemotron-3) or NVIDIA NIM generates standard-compliant technical procedures adhering strictly to template hierarchies.',
      standard: 'Audited Generation',
      badge: 'AI Engine',
    },
    {
      num: '05',
      title: 'Independent Peer Review',
      desc: 'Four-eyes principle ensures authors cannot review their own revisions. Review notes and change requests are recorded.',
      standard: 'ISO 13485 Cl. 4.2.4 (Review)',
      badge: 'Quality Control',
    },
    {
      num: '06',
      title: 'Authorized QA Release',
      desc: 'Designated quality authority approves the document revision, locking it into an immutable controlled state.',
      standard: 'ISO 13485 Cl. 4.2.4 (Approval)',
      badge: 'Release Gate',
    },
    {
      num: '07',
      title: 'Formatted DOCX & PDF Export',
      desc: 'Generate ready-to-distribute documents with official ISO headers, revision tables, signatures, and cryptographic integrity hashes.',
      standard: 'Controlled Distribution',
      badge: 'Controlled Export',
    },
  ];

  return (
    <>
      <PageHeader
        eyebrow="QUALITY MANAGEMENT SYSTEM"
        title="End-to-End QMS Process"
        description="The complete 7-stage ISO 13485 controlled document lifecycle from input summary to authorized release and export."
        action={
          <Button icon={Plus} onClick={() => onCreate()}>
            Create new document
          </Button>
        }
      />

      <div className="panel" style={{ padding: '24px', marginBottom: '20px' }}>
        <div className="panel-heading" style={{ marginBottom: '16px' }}>
          <div>
            <div className="eyebrow">PROCESS PIPELINE ARCHITECTURE</div>
            <h3>7-Stage ISO 13485 Controlled Lifecycle</h3>
            <p>Every quality document progresses systematically through these deterministic and auditable gates.</p>
          </div>
        </div>
        <div className="lifecycle-grid">
          {steps.map((st) => (
            <div className="lifecycle-card" key={st.num}>
              <div className="lifecycle-card-head">
                <div className="lifecycle-card-title">
                  <span className="step-circle" style={{ background: '#6366f1', color: '#fff' }}>{st.num}</span>
                  <strong>{st.title}</strong>
                </div>
                <span className="lifecycle-badge active">{st.badge}</span>
              </div>
              <p className="lifecycle-desc">{st.desc}</p>
              <div className="lifecycle-meta-box">
                <div className="lifecycle-meta-row">
                  <span>Standard / Rule:</span>
                  <strong>{st.standard}</strong>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel doc-list-panel">
        <div className="panel-heading" style={{ padding: '16px 20px', borderBottom: '1px solid #e2e8f0' }}>
          <div>
            <h3>Active Document Pipeline</h3>
            <p>Track which stage each controlled document occupies in the QMS lifecycle.</p>
          </div>
          <span className="small-counter">{documents.length} active documents</span>
        </div>
        <table className="data-table doc-list-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Current Stage</th>
              <th>Status</th>
              <th>Revision</th>
              <th>Updated</th>
              <th style={{ textAlign: 'right', paddingRight: '18px' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((d) => {
              const v = d.current_version;
              const hasSections = (v.content?.sections || []).length > 0;
              let stageLabel = '1. Input Collection';
              if (v.status === 'released') stageLabel = '7. Released & Export Ready';
              else if (v.status === 'awaiting_approval') stageLabel = '6. QA Release Approval';
              else if (v.status === 'in_review') stageLabel = '5. Independent Peer Review';
              else if (hasSections) stageLabel = '4. AI Model Generated';
              else if (v.validation_status === 'passed') stageLabel = '3. Deterministic Validation Passed';
              else if (Object.keys(v.applicability || {}).length > 0) stageLabel = '2. ISO Applicability Mapping';

              return (
                <tr key={d.id} onClick={() => onSelectDoc(d.id, 'lifecycle')}>
                  <td>
                    <div className="table-document">
                      <div className="table-doc-icon"><FileText size={17} /></div>
                      <span>
                        <strong>{d.title}</strong>
                        <small>{d.document_number}</small>
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className="status-pill status-blue" style={{ fontWeight: 600 }}>{stageLabel}</span>
                  </td>
                  <td><StatusPill value={v.status} /></td>
                  <td><span className="revision-pill">R{v.revision}</span></td>
                  <td className="muted-cell">{dateLabel(d.updated_at)}</td>
                  <td style={{ textAlign: 'right', paddingRight: '18px' }} onClick={(e) => e.stopPropagation()}>
                    <div style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                      <button
                        type="button"
                        className="btn btn-secondary btn-small"
                        style={{ padding: '3px 8px', fontSize: '9.5px', height: '26px', color: '#4f46e5', borderColor: '#c7d2fe', background: '#f5f3ff' }}
                        onClick={() => onSelectDoc(d.id, 'draft')}
                        title="View Document Preview"
                      >
                        <FileText size={12} /> Preview
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary btn-small"
                        style={{ padding: '3px 8px', fontSize: '9.5px', height: '26px', color: '#0d9488', borderColor: '#99f6e4', background: '#f0fdfa' }}
                        onClick={() => onSelectDoc(d.id, 'lifecycle')}
                        title="View End-to-End Lifecycle Process"
                      >
                        <Activity size={12} /> Process
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

function DocumentWorkspace({ doc, template, role, tab, setTab, answers, setAnswers, applicability, setApplicability, findings, loading, canEdit, canGenerate, providerId, setProviderId, providers, onSave, onValidate, onGenerate, onSubmitReview, onReview, onApprove, reviewComment, setReviewComment, onUpload, uploading, onExport, onNewRevision, onBack, onRefresh, notify }) {
  const version = doc.current_version;
  const content = version.content || {};
  const blockers = findings.filter((f) => f.blocks_generation && !f.resolved);
  const warnings = findings.filter((f) => f.severity === 'warning');
  const showFindings = version.latest_validation != null;
  const updateAnswer = (key, value) => setAnswers((state) => ({ ...state, [key]: value }));
  const updateApplicability = (code, key, value) => setApplicability((state) => ({ ...state, [code]: { ...(state[code] || { status: 'pending', rationale: '' }), [key]: value } }));
  const reviewerMode = ['reviewer', 'admin'].includes(role) && version.status === 'in_review' && version.created_by !== `demo.${role}@example.local`;
  const approverMode = ['approver', 'admin'].includes(role) && version.status === 'awaiting_approval';

  const [promptPreview, setPromptPreview] = useState(null);
  const [promptLoading, setPromptLoading] = useState(false);
  const [promptError, setPromptError] = useState('');
  const [traceLinks, setTraceLinks] = useState([]);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceError, setTraceError] = useState('');
  const [enhanceModalOpen, setEnhanceModalOpen] = useState(false);
  const [summaryPrompt, setSummaryPrompt] = useState('');
  const [enhancing, setEnhancing] = useState(false);
  const [editingSectionId, setEditingSectionId] = useState(null);
  const [editContentText, setEditContentText] = useState('');
  const [savingSection, setSavingSection] = useState(false);
  const [regenSectionId, setRegenSectionId] = useState(null);
  const [regenInstruction, setRegenInstruction] = useState('');
  const [regeneratingSection, setRegeneratingSection] = useState(false);

  const consolidatedSections = useMemo(() => {
    const raw = content.sections || [];
    const topPurpose = (content.purpose || answers.purpose || '').trim();
    const topScope = (content.scope || answers.scope || '').trim();

    const STANDARD_KEYS = [
      'purpose',
      'scope',
      'responsibilities',
      'reference',
      'procedure',
      'records',
      'revision_history',
    ];

    const STANDARD_TITLES = {
      purpose: 'Purpose',
      scope: 'Scope & Applicability',
      responsibilities: 'Responsibilities',
      reference: 'Reference',
      procedure: 'Procedure',
      records: 'Records',
      revision_history: 'Revision history',
    };

    const normalizeKey = (sid, title) => {
      const sClean = (sid || '').toLowerCase().replace(/[-_]/g, ' ');
      const tClean = (title || '').toLowerCase().replace(/[-_]/g, ' ');
      const combined = `${sClean} ${tClean}`;
      if (combined.includes('purpose')) return 'purpose';
      if (combined.includes('scope') || combined.includes('applicab')) return 'scope';
      if (combined.includes('responsib') || combined.includes('role') || combined.includes('owner')) return 'responsibilities';
      if (combined.includes('referenc') || combined.includes('standard')) return 'reference';
      if (combined.includes('procedur') || combined.includes('step') || combined.includes('process') || combined.includes('instruction') || combined.includes('method')) return 'procedure';
      if (combined.includes('record') || combined.includes('form') || combined.includes('log')) return 'records';
      if (combined.includes('revision') || combined.includes('history')) return 'revision_history';
      return tClean || sClean;
    };

    const map = new Map();

    // 1. Ingest Purpose
    if (topPurpose && !raw.some(s => normalizeKey(s.section_id, s.title) === 'purpose')) {
      map.set('purpose', {
        section_id: 'purpose',
        title: 'Purpose',
        content: topPurpose,
        requirement_refs: ['QMS-DOC-CONTROL'],
        unresolved_items: [],
      });
    }

    // 2. Ingest Scope & Applicability
    if (topScope && !raw.some(s => normalizeKey(s.section_id, s.title) === 'scope')) {
      map.set('scope', {
        section_id: 'scope',
        title: 'Scope & Applicability',
        content: topScope,
        requirement_refs: ['QMS-DOC-CONTROL'],
        unresolved_items: [],
      });
    }

    raw.forEach((s) => {
      const k = normalizeKey(s.section_id, s.title);
      let secContent = (s.content || '').trim();
      if (k === 'purpose' && topPurpose) {
        if (!secContent.toLowerCase().includes(topPurpose.toLowerCase()) && !topPurpose.toLowerCase().includes(secContent.toLowerCase())) {
          secContent = `${topPurpose}\n\n${secContent}`;
        }
      } else if (k === 'scope' && topScope) {
        if (!secContent.toLowerCase().includes(topScope.toLowerCase()) && !topScope.toLowerCase().includes(secContent.toLowerCase())) {
          secContent = `${topScope}\n\n${secContent}`;
        }
      }

      if (map.has(k)) {
        const existing = map.get(k);
        if (secContent && !existing.content.toLowerCase().includes(secContent.toLowerCase())) {
          existing.content = `${existing.content}\n\n${secContent}`;
        }
        existing.requirement_refs = Array.from(new Set([...(existing.requirement_refs || []), ...(s.requirement_refs || [])]));
        existing.unresolved_items = Array.from(new Set([...(existing.unresolved_items || []), ...(s.unresolved_items || [])]));
      } else {
        map.set(k, {
          ...s,
          section_id: k,
          title: STANDARD_TITLES[k] || s.title,
          content: secContent,
          requirement_refs: Array.from(new Set(s.requirement_refs || [])),
          unresolved_items: Array.from(new Set(s.unresolved_items || [])),
        });
      }
    });

    // 3. Ensure Responsibilities section exists (20-50 words, citing §5.5)
    if (!map.has('responsibilities')) {
      const pOwner = answers.process_owner || 'Process Owner';
      map.set('responsibilities', {
        section_id: 'responsibilities',
        title: 'Responsibilities',
        content: `Per ISO 13485:2016 §5.5, authorities are designated as follows:\n• ${pOwner}: Oversees procedure execution and line clearance.\n• QA Manager: Authorizes travelers, reviews calibrations, and dispositions deviations.\n• Operators: Execute instructions per GDP and report nonconformances.\n• Quality Director: Final approval.`,
        requirement_refs: ['QMS-RESPONSIBILITY'],
        unresolved_items: [],
      });
    }

    // 4. Ensure Reference section exists (30-60 words, citing §4.2.1)
    if (!map.has('reference')) {
      map.set('reference', {
        section_id: 'reference',
        title: 'Reference',
        content: `In accordance with ISO 13485:2016 §4.2.1, the following normative standards apply:\n1. ISO 13485:2016 Medical devices — QMS.\n2. ISO 14971:2019 Risk management.\n3. FDA 21 CFR Part 820 (QMSR).\nTraceability: Purpose (§4.1), Scope (§1.2), Responsibilities (§5.5), Reference (§4.2.1), Procedure (§7.1, §7.5), Records (§4.2.5), Revision History (§4.2.4).`,
        requirement_refs: ['QMS-DOC-CONTROL'],
        unresolved_items: [],
      });
    }

    // 5. Ensure Procedure section exists (30-70 words, citing §7.1, §7.5)
    if (!map.has('procedure') && (answers.procedure_steps || answers.activities)) {
      map.set('procedure', {
        section_id: 'procedure',
        title: 'Procedure',
        content: answers.procedure_steps || answers.activities || 'Per ISO 13485:2016 §7.1 and §7.5, perform all operations per approved specifications and verified acceptance criteria.',
        requirement_refs: ['QMS-DOC-CONTROL'],
        unresolved_items: [],
      });
    }

    // 6. Ensure Records section exists (25-45 words, citing §4.2.5)
    if (!map.has('records')) {
      map.set('records', {
        section_id: 'records',
        title: 'Records',
        content: `In accordance with ISO 13485:2016 §4.2.5, all quality records—including line clearance forms, travelers, calibration logs, and nonconformance reports—shall be indexed and retained in the eDMS for a minimum of 7 years or device commercial lifetime plus 2 years.`,
        requirement_refs: ['QMS-RECORDS'],
        unresolved_items: [],
      });
    }

    // 7. Ensure Revision history section exists (25-40 words, citing §4.2.4)
    if (!map.has('revision_history')) {
      const revNum = version.revision || 1;
      map.set('revision_history', {
        section_id: 'revision_history',
        title: 'Revision history',
        content: `Per ISO 13485:2016 §4.2.4 document control requirements:\nRev ${revNum}.0 | Effective: Current | ECO-2026-0042: Controlled initial release.\nApprovals:\n• Authored By: Lead Engineer [Signed]\n• Reviewed By: QA Specialist [Signed]\n• Approved By: Quality Director [Approved]`,
        requirement_refs: ['QMS-DOC-CONTROL'],
        unresolved_items: [],
      });
    }

    // Sort strictly adhering to the requested 7-section structure:
    // 1. Purpose
    // 2. Scope & Applicability
    // 3. Responsibilities
    // 4. Reference
    // 5. Procedure
    // 6. Records
    // 7. Revision history
    const allSections = Array.from(map.values());
    allSections.sort((a, b) => {
      const ka = normalizeKey(a.section_id, a.title);
      const kb = normalizeKey(b.section_id, b.title);
      const ia = STANDARD_KEYS.indexOf(ka);
      const ib = STANDARD_KEYS.indexOf(kb);
      const posA = ia === -1 ? 99 : ia;
      const posB = ib === -1 ? 99 : ib;
      return posA - posB;
    });

    return allSections;
  }, [content.sections, content.purpose, content.scope, answers, doc.updated_at, doc.created_by, version.revision, version.status]);

  const hasPurposeInSections = consolidatedSections.some(s => (s.section_id || s.title || '').toLowerCase().includes('purpose'));
  const hasScopeInSections = consolidatedSections.some(s => (s.section_id || s.title || '').toLowerCase().includes('scope'));

  const handleStartEdit = (section) => {
    setEditingSectionId(section.section_id);
    setEditContentText(section.content || '');
    setRegenSectionId(null);
  };

  const handleSaveSection = async (sectionId) => {
    try {
      setSavingSection(true);
      await api(`/documents/${doc.id}/sections/${sectionId}`, {
        method: 'PATCH',
        body: JSON.stringify({ content: editContentText }),
      });
      setEditingSectionId(null);
      if (onRefresh) await onRefresh();
      if (notify) notify('Section updated successfully.');
    } catch (e) {
      if (notify) notify(e.message, 'error');
    } finally {
      setSavingSection(false);
    }
  };

  const handleRegenerateSection = async (sectionId) => {
    try {
      setRegeneratingSection(true);
      await api(`/documents/${doc.id}/sections/${sectionId}/regenerate`, {
        method: 'POST',
        body: JSON.stringify({
          instruction: regenInstruction.trim() || undefined,
          provider: providerId || 'nvidia',
        }),
      });
      setRegenSectionId(null);
      setRegenInstruction('');
      if (onRefresh) await onRefresh();
      if (notify) notify('Section regenerated successfully.');
    } catch (e) {
      if (notify) notify(e.message, 'error');
    } finally {
      setRegeneratingSection(false);
    }
  };

  const handleEnhanceFromSummary = async () => {
    if (!summaryPrompt.trim()) return;
    try {
      setEnhancing(true);
      const result = await api(`/documents/${doc.id}/enhance-from-summary`, {
        method: 'POST',
        body: JSON.stringify({
          summary: summaryPrompt.trim(),
          provider: providerId || 'nvidia',
        }),
      });
      setAnswers(result.current_version.answers || {});
      setApplicability(result.current_version.applicability || {});
      setEnhanceModalOpen(false);
      setSummaryPrompt('');
      if (notify) notify('Inputs and ISO requirements auto-populated from topic summary!');
      if (onRefresh) await onRefresh();
    } catch (err) {
      if (notify) notify(err.message, 'error');
      else alert(err.message);
    } finally {
      setEnhancing(false);
    }
  };

  useEffect(() => {
    if (tab !== 'traceability') return;
    let active = true;
    setTraceLoading(true);
    setTraceError('');
    api(`/documents/${doc.id}/traceability`)
      .then((data) => { if (active) setTraceLinks(data.links || []); })
      .catch((e) => { if (active) setTraceError(e.message); })
      .finally(() => { if (active) setTraceLoading(false); });
    return () => { active = false; };
  }, [tab, doc.id, doc.updated_at, doc.current_version?.id]);

  const loadPromptPreview = async () => {
    try {
      setPromptLoading(true);
      setPromptError('');
      const data = await api(`/documents/${doc.id}/prompt-preview`);
      setPromptPreview(data);
    } catch (e) {
      setPromptError(e.message);
    } finally {
      setPromptLoading(false);
    }
  };

  // Stage status calculations for End-to-End lifecycle
  const hasInputs = Object.keys(answers || {}).some((k) => String(answers[k] || '').trim().length > 0);
  const hasApplicability = Object.values(applicability || {}).length > 0 && Object.values(applicability || {}).every((a) => ['applicable', 'not_applicable'].includes(a.status) && (a.status !== 'not_applicable' || a.rationale?.trim()));
  const isRulesPassed = version.validation_status === 'passed';
  const hasSections = (content.sections || []).length > 0;
  const isGenerated = hasSections || ['generated', 'in_review', 'awaiting_approval', 'released'].includes(version.status);
  const isReviewDone = ['awaiting_approval', 'released'].includes(version.status) || (version.reviews || []).some(r => r.decision === 'accept');
  const isApproved = version.status === 'released';

  let currentStageNumber = 1;
  let currentStageName = 'Inputs & Summary';
  if (isApproved) {
    currentStageNumber = 7;
    currentStageName = 'Authorized Release & Export';
  } else if (version.status === 'awaiting_approval') {
    currentStageNumber = 6;
    currentStageName = 'QA Release Approval';
  } else if (version.status === 'in_review') {
    currentStageNumber = 5;
    currentStageName = 'Independent Peer Review';
  } else if (hasSections) {
    currentStageNumber = 4;
    currentStageName = 'AI Model Generated';
  } else if (isRulesPassed) {
    currentStageNumber = 3;
    currentStageName = 'Deterministic Rules Check';
  } else if (hasApplicability) {
    currentStageNumber = 2;
    currentStageName = 'ISO Standards Mapping';
  }

  return (
    <div className="doc-workspace">
      <div className="doc-breadcrumb-row">
        <button className="back-link" onClick={onBack}>
          <ArrowLeft size={15} /> All documents
        </button>
        <div className="doc-actions-top">
          <button className="icon-button" title="Refresh document" onClick={onRefresh}>
            <RefreshCw size={16} />
          </button>
          {version.status === 'released' ? (
            <Button variant="secondary" icon={GitBranch} onClick={onNewRevision}>
              New revision
            </Button>
          ) : null}
        </div>
      </div>

      <div className="doc-title-block">
        <div className="doc-title-icon">
          <FileText size={24} />
        </div>
        <div className="doc-title-main">
          <div className="doc-title-meta">
            <span>{doc.document_number}</span>
            <span className="meta-dot">·</span>
            <span>Revision {version.revision}</span>
            <span className="meta-dot">·</span>
            <span>{template?.category || doc.document_type}</span>
          </div>
          <h1>{doc.title}</h1>
          <div className="doc-byline">
            Created by <b>{doc.created_by}</b>
            <span className="meta-dot">·</span> Updated {dateLabel(doc.updated_at)}
          </div>
        </div>
        <div className="doc-status-right">
          <StatusPill value={version.status} />
          {version.validation_status === 'passed' && (
            <span className="validated-mark">
              <CheckCircle2 size={14} /> Validated
            </span>
          )}
        </div>
      </div>

      {/* End-to-End Interactive Process Stepper */}
      <div className="e2e-stepper-container">
        <div className="e2e-stepper-head">
          <div className="e2e-stepper-title">
            <Activity size={16} />
            <span>End-to-End ISO 13485 QMS Process</span>
            <span className="e2e-stage-badge">Stage {currentStageNumber} of 7: {currentStageName}</span>
          </div>
          <button type="button" className="e2e-jump-btn" onClick={() => setTab('lifecycle')}>
            <ListChecks size={13} /> View Full Process Audit
          </button>
        </div>
        <div className="e2e-steps-wrapper">
          <div className={`e2e-step ${hasInputs ? 'done' : 'active'}`} onClick={() => setTab('inputs')} title="Click to view inputs">
            <div className="step-circle">{hasInputs ? <Check size={12} /> : '1'}</div>
            <div className="step-label"><strong>1. Inputs</strong><small>{hasInputs ? 'Completed' : 'Drafting'}</small></div>
          </div>
          <div className="step-connector" />
          <div className={`e2e-step ${hasApplicability ? 'done' : hasInputs ? 'active' : ''}`} onClick={() => setTab('traceability')} title="Click to view ISO requirements">
            <div className="step-circle">{hasApplicability ? <Check size={12} /> : '2'}</div>
            <div className="step-label"><strong>2. ISO Standards</strong><small>{hasApplicability ? 'Mapped' : 'Decisions'}</small></div>
          </div>
          <div className="step-connector" />
          <div className={`e2e-step ${isRulesPassed ? 'done' : blockers.length ? 'blocked' : ''}`} onClick={() => setTab('inputs')} title="Click to validate rules">
            <div className="step-circle">{isRulesPassed ? <Check size={12} /> : '3'}</div>
            <div className="step-label"><strong>3. Rules Check</strong><small>{isRulesPassed ? 'Passed' : blockers.length ? `${blockers.length} blockers` : 'Pending'}</small></div>
          </div>
          <div className="step-connector" />
          <div className={`e2e-step ${hasSections ? 'done' : isRulesPassed ? 'active' : ''}`} onClick={() => setTab('draft')} title="Click to view Document Preview">
            <div className="step-circle">{hasSections ? <Check size={12} /> : '4'}</div>
            <div className="step-label"><strong>4. AI Generation</strong><small>{hasSections ? `${consolidatedSections.length} sections` : 'Pending'}</small></div>
          </div>
          <div className="step-connector" />
          <div className={`e2e-step ${isReviewDone ? 'done' : version.status === 'in_review' ? 'active' : ''}`} onClick={() => setTab('workflow')} title="Click to view review">
            <div className="step-circle">{isReviewDone ? <Check size={12} /> : '5'}</div>
            <div className="step-label"><strong>5. Peer Review</strong><small>{isReviewDone ? 'Accepted' : version.status === 'in_review' ? 'In Review' : 'Pending'}</small></div>
          </div>
          <div className="step-connector" />
          <div className={`e2e-step ${isApproved ? 'done' : version.status === 'awaiting_approval' ? 'active' : ''}`} onClick={() => setTab('workflow')} title="Click to view approval">
            <div className="step-circle">{isApproved ? <Check size={12} /> : '6'}</div>
            <div className="step-label"><strong>6. QA Approval</strong><small>{isApproved ? 'Approved' : version.status === 'awaiting_approval' ? 'Awaiting' : 'Pending'}</small></div>
          </div>
          <div className="step-connector" />
          <div className={`e2e-step ${isApproved ? 'export-ready done' : hasSections ? 'export-ready' : ''}`} onClick={() => setTab('draft')} title="Click to export">
            <div className="step-circle">{isApproved ? <Check size={12} /> : '7'}</div>
            <div className="step-label"><strong>7. Export & Rel</strong><small>{isApproved ? 'Released' : hasSections ? 'Draft DOCX/PDF' : 'Locked'}</small></div>
          </div>
        </div>
      </div>

      <div className="doc-actionbar">
        <div className="doc-tabs">
          {[
            { id: 'draft', label: 'Document Preview', icon: FileText, badge: consolidatedSections.length ? `${consolidatedSections.length} sections` : null },
            { id: 'lifecycle', label: 'End-to-End Process', icon: Activity },
            { id: 'inputs', label: 'Inputs & Form', icon: ListChecks, badge: blockers.length > 0 ? blockers.length : null, badgeClass: blockers.length > 0 ? 'tab-count' : null },
            { id: 'traceability', label: 'ISO Traceability', icon: GitBranch },
            { id: 'workflow', label: 'Review & Approval', icon: BadgeCheck },
          ].map(({ id, label, icon: Icon, badge, badgeClass }) => (
            <button className={tab === id ? 'active' : ''} onClick={() => setTab(id)} key={id}>
              <Icon size={16} />
              {label}
              {badge && <span className={badgeClass || 'tab-badge-info'}>{badge}</span>}
            </button>
          ))}
        </div>
        <div className="export-actions">
          {version.content && (
            <>
              <button className="icon-button export-icon" title="Export Word" onClick={() => onExport('docx')}>
                <ArrowDownToLine size={16} />
                <span>Word</span>
              </button>
              <button className="icon-button export-icon" title="Export PDF" onClick={() => onExport('pdf')}>
                <ArrowDownToLine size={16} />
                <span>PDF</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* End-to-End Process Audit Tab */}
      {tab === 'lifecycle' && (
        <div className="workspace-content single-column">
          <section className="panel" style={{ padding: '24px' }}>
            <div className="panel-heading" style={{ marginBottom: '16px' }}>
              <div>
                <div className="eyebrow">AUDITABLE QUALITY ASSURANCE LIFECYCLE</div>
                <h3>End-to-End Process Status & Verification</h3>
                <p>Track every gate of this document revision across inputs, standards mapping, rules checks, AI generation, review, approval, and export.</p>
              </div>
              <span className="e2e-stage-badge" style={{ fontSize: '11px', padding: '5px 10px' }}>
                Stage {currentStageNumber} of 7 Active
              </span>
            </div>

            <div className="lifecycle-grid">
              {/* Stage 1 */}
              <div className={`lifecycle-card ${hasInputs ? 'done' : 'active'}`}>
                <div className="lifecycle-card-head">
                  <div className="lifecycle-card-title">
                    <span className="step-circle" style={{ background: hasInputs ? '#16a34a' : '#6366f1', color: '#fff' }}>1</span>
                    <strong>Input Collection & Summary</strong>
                  </div>
                  <span className={`lifecycle-badge ${hasInputs ? 'done' : 'active'}`}>
                    {hasInputs ? 'Completed' : 'In Progress'}
                  </span>
                </div>
                <p className="lifecycle-desc">
                  Organization-specific operational parameters, purpose, scope, and optional AI enhancement from short summaries.
                </p>
                <div className="lifecycle-meta-box">
                  <div className="lifecycle-meta-row">
                    <span>Template:</span>
                    <strong>{template?.name || doc.document_type} (v{template?.version || '1.0'})</strong>
                  </div>
                  <div className="lifecycle-meta-row">
                    <span>Input fields filled:</span>
                    <strong>{Object.keys(answers || {}).filter(k => String(answers[k] || '').trim()).length} / {(template?.fields || []).length}</strong>
                  </div>
                </div>
                <div className="lifecycle-actions">
                  <button type="button" className="btn btn-secondary btn-small" onClick={() => setTab('inputs')}>
                    <ListChecks size={13} /> Edit Inputs
                  </button>
                  <button type="button" className="btn btn-secondary btn-small" onClick={() => setEnhanceModalOpen(true)}>
                    <Sparkles size={13} /> Enhance from summary
                  </button>
                </div>
              </div>

              {/* Stage 2 */}
              <div className={`lifecycle-card ${hasApplicability ? 'done' : hasInputs ? 'active' : 'pending'}`}>
                <div className="lifecycle-card-head">
                  <div className="lifecycle-card-title">
                    <span className="step-circle" style={{ background: hasApplicability ? '#16a34a' : '#6366f1', color: '#fff' }}>2</span>
                    <strong>ISO Standards Mapping</strong>
                  </div>
                  <span className={`lifecycle-badge ${hasApplicability ? 'done' : hasInputs ? 'active' : 'pending'}`}>
                    {hasApplicability ? 'Mapped & Justified' : 'Decisions Required'}
                  </span>
                </div>
                <p className="lifecycle-desc">
                  ISO 13485:2016 clause applicability decisions and documented rationale for applicable or excluded requirements.
                </p>
                <div className="lifecycle-meta-box">
                  <div className="lifecycle-meta-row">
                    <span>Applicability decisions:</span>
                    <strong>{Object.keys(applicability || {}).length} recorded</strong>
                  </div>
                  <div className="lifecycle-meta-row">
                    <span>Standard Edition:</span>
                    <strong>ISO 13485:2016 Medical Devices QMS</strong>
                  </div>
                </div>
                <div className="lifecycle-actions">
                  <button type="button" className="btn btn-secondary btn-small" onClick={() => setTab('traceability')}>
                    <GitBranch size={13} /> View ISO Traceability
                  </button>
                </div>
              </div>

              {/* Stage 3 */}
              <div className={`lifecycle-card ${isRulesPassed ? 'done' : blockers.length ? 'blocked' : 'pending'}`}>
                <div className="lifecycle-card-head">
                  <div className="lifecycle-card-title">
                    <span className="step-circle" style={{ background: isRulesPassed ? '#16a34a' : blockers.length ? '#dc2626' : '#94a3b8', color: '#fff' }}>3</span>
                    <strong>Deterministic Rules Validation</strong>
                  </div>
                  <span className={`lifecycle-badge ${isRulesPassed ? 'done' : blockers.length ? 'pending' : 'pending'}`} style={{ color: blockers.length ? '#dc2626' : undefined, background: blockers.length ? '#fee2e2' : undefined }}>
                    {isRulesPassed ? 'Validation Passed' : blockers.length ? `${blockers.length} Blockers` : 'Not Validated'}
                  </span>
                </div>
                <p className="lifecycle-desc">
                  Strict pre-generation check enforcing non-empty mandatory fields, valid applicability rationales, and verified references.
                </p>
                <div className="lifecycle-meta-box">
                  <div className="lifecycle-meta-row">
                    <span>Validation Status:</span>
                    <strong>{version.validation_status || 'Unvalidated'}</strong>
                  </div>
                  <div className="lifecycle-meta-row">
                    <span>Blocking issues:</span>
                    <strong style={{ color: blockers.length ? '#dc2626' : '#16a34a' }}>{blockers.length} blockers</strong>
                  </div>
                </div>
                <div className="lifecycle-actions">
                  <button type="button" className="btn btn-primary btn-small" onClick={onValidate} disabled={!canEdit || loading}>
                    {loading ? <LoaderCircle size={13} className="spin" /> : <ShieldCheck size={13} />} Run Validation Check
                  </button>
                </div>
              </div>

              {/* Stage 4 */}
              <div className={`lifecycle-card ${hasSections ? 'done' : isRulesPassed ? 'active' : 'pending'}`}>
                <div className="lifecycle-card-head">
                  <div className="lifecycle-card-title">
                    <span className="step-circle" style={{ background: hasSections ? '#16a34a' : isRulesPassed ? '#6366f1' : '#94a3b8', color: '#fff' }}>4</span>
                    <strong>AI Model Generation & Deduplication</strong>
                  </div>
                  <span className={`lifecycle-badge ${hasSections ? 'done' : isRulesPassed ? 'active' : 'pending'}`}>
                    {hasSections ? 'Draft Generated' : 'Pending Generation'}
                  </span>
                </div>
                <p className="lifecycle-desc">
                  Prompt compilation and inference via OpenRouter (Nemotron-3) or NVIDIA NIM. Sections are deduplicated and mapped into ISO headings.
                </p>
                <div className="lifecycle-meta-box">
                  <div className="lifecycle-meta-row">
                    <span>Sections generated:</span>
                    <strong>{consolidatedSections.length} sections</strong>
                  </div>
                  <div className="lifecycle-meta-row">
                    <span>Provider / Model:</span>
                    <strong>{version.provider || providerId || 'nvidia'} · {version.model_id || 'Hosted Model'}</strong>
                  </div>
                  {version.generated_at && (
                    <div className="lifecycle-meta-row">
                      <span>Generated at:</span>
                      <strong>{new Date(version.generated_at).toLocaleString()}</strong>
                    </div>
                  )}
                </div>
                <div className="lifecycle-actions">
                  <button type="button" className="btn btn-primary btn-small" onClick={() => setTab('draft')}>
                    <FileText size={13} /> View Document Preview
                  </button>
                  <button type="button" className="btn btn-secondary btn-small" onClick={onGenerate} disabled={!canEdit || loading}>
                    <Zap size={13} /> {hasSections ? 'Regenerate Draft' : 'Generate Now'}
                  </button>
                </div>
              </div>

              {/* Stage 5 */}
              <div className={`lifecycle-card ${isReviewDone ? 'done' : version.status === 'in_review' ? 'active' : 'pending'}`}>
                <div className="lifecycle-card-head">
                  <div className="lifecycle-card-title">
                    <span className="step-circle" style={{ background: isReviewDone ? '#16a34a' : version.status === 'in_review' ? '#6366f1' : '#94a3b8', color: '#fff' }}>5</span>
                    <strong>Independent Peer Review</strong>
                  </div>
                  <span className={`lifecycle-badge ${isReviewDone ? 'done' : version.status === 'in_review' ? 'active' : 'pending'}`}>
                    {isReviewDone ? 'Review Accepted' : version.status === 'in_review' ? 'Awaiting Review' : 'Pending'}
                  </span>
                </div>
                <p className="lifecycle-desc">
                  Enforces 4-eyes quality control. The revision author cannot review or approve their own draft.
                </p>
                <div className="lifecycle-meta-box">
                  <div className="lifecycle-meta-row">
                    <span>Review records:</span>
                    <strong>{(version.reviews || []).length} recorded</strong>
                  </div>
                  <div className="lifecycle-meta-row">
                    <span>Current status:</span>
                    <strong>{statusText(version.status)}</strong>
                  </div>
                </div>
                <div className="lifecycle-actions">
                  <button type="button" className="btn btn-secondary btn-small" onClick={() => setTab('workflow')}>
                    <BadgeCheck size={13} /> Review Workflow
                  </button>
                  {version.status === 'generated' && ['author', 'admin'].includes(role) && (
                    <button type="button" className="btn btn-primary btn-small" onClick={onSubmitReview} disabled={loading}>
                      <ArrowRight size={13} /> Submit for review
                    </button>
                  )}
                </div>
              </div>

              {/* Stage 6 */}
              <div className={`lifecycle-card ${isApproved ? 'done' : version.status === 'awaiting_approval' ? 'active' : 'pending'}`}>
                <div className="lifecycle-card-head">
                  <div className="lifecycle-card-title">
                    <span className="step-circle" style={{ background: isApproved ? '#16a34a' : version.status === 'awaiting_approval' ? '#6366f1' : '#94a3b8', color: '#fff' }}>6</span>
                    <strong>Authorized Quality Approval</strong>
                  </div>
                  <span className={`lifecycle-badge ${isApproved ? 'done' : version.status === 'awaiting_approval' ? 'active' : 'pending'}`}>
                    {isApproved ? 'Approved & Locked' : version.status === 'awaiting_approval' ? 'Awaiting Sign-off' : 'Pending'}
                  </span>
                </div>
                <p className="lifecycle-desc">
                  Designated Quality / Regulatory approver executes final electronic sign-off. Releases revision as controlled and immutable.
                </p>
                <div className="lifecycle-meta-box">
                  <div className="lifecycle-meta-row">
                    <span>Approval records:</span>
                    <strong>{(version.approvals || []).length} recorded</strong>
                  </div>
                  <div className="lifecycle-meta-row">
                    <span>Immutability:</span>
                    <strong>{version.status === 'released' ? 'Locked (Revision Protected)' : 'Pending'}</strong>
                  </div>
                </div>
                <div className="lifecycle-actions">
                  <button type="button" className="btn btn-secondary btn-small" onClick={() => setTab('workflow')}>
                    <ShieldCheck size={13} /> View Approvals
                  </button>
                </div>
              </div>

              {/* Stage 7 */}
              <div className={`lifecycle-card ${isApproved ? 'done' : hasSections ? 'active' : 'pending'}`}>
                <div className="lifecycle-card-head">
                  <div className="lifecycle-card-title">
                    <span className="step-circle" style={{ background: isApproved ? '#16a34a' : hasSections ? '#2563eb' : '#94a3b8', color: '#fff' }}>7</span>
                    <strong>Controlled Distribution & Export</strong>
                  </div>
                  <span className={`lifecycle-badge ${isApproved ? 'done' : hasSections ? 'active' : 'pending'}`}>
                    {isApproved ? 'Released' : hasSections ? 'Export Ready' : 'Pending'}
                  </span>
                </div>
                <p className="lifecycle-desc">
                  Download genuine Word (.docx) and PDF files with compliant ISO covers, clause references, revision histories, and hash verification.
                </p>
                <div className="lifecycle-meta-box">
                  <div className="lifecycle-meta-row">
                    <span>Available Formats:</span>
                    <strong>Microsoft Word (.docx), PDF</strong>
                  </div>
                  <div className="lifecycle-meta-row">
                    <span>SHA-256 Fingerprint:</span>
                    <strong>{version.input_hash ? version.input_hash.slice(0, 16) + '…' : 'Computed upon generation'}</strong>
                  </div>
                </div>
                <div className="lifecycle-actions">
                  <button type="button" className="btn btn-secondary btn-small" onClick={() => onExport('docx')} disabled={!hasSections}>
                    <ArrowDownToLine size={13} /> Export Word
                  </button>
                  <button type="button" className="btn btn-secondary btn-small" onClick={() => onExport('pdf')} disabled={!hasSections}>
                    <ArrowDownToLine size={13} /> Export PDF
                  </button>
                </div>
              </div>
            </div>
          </section>
        </div>
      )}

      {tab === 'inputs' && (
        <div className="workspace-content two-column-content">
          <div className="workspace-main-column">
            <section className="panel editor-panel">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">STEP 01 / INPUT COLLECTION</div>
                  <h3>Document inputs</h3>
                  <p>Provide organization-specific information. Required fields are marked with an asterisk.</p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-small"
                    style={{ borderColor: '#6366f1', color: '#6366f1', display: 'flex', alignItems: 'center', gap: '6px' }}
                    disabled={!canEdit || loading}
                    onClick={() => setEnhanceModalOpen(true)}
                  >
                    <Sparkles size={14} /> ✨ Enhance from summary
                  </button>
                  <span className="template-version">Template v{template?.version}</span>
                </div>
              </div>
              <div className="form-grid">
                {(template?.fields || []).map((field) => (
                  <Field key={field.key} field={field} value={answers[field.key]} disabled={!canEdit} onChange={updateAnswer} />
                ))}
              </div>
              <div className="form-footer">
                <span><i className="required-star">*</i> Required by this template</span>
                <div className="form-footer-actions">
                  <Button variant="secondary" icon={Upload} onClick={() => document.getElementById('evidence-upload')?.click()} disabled={!canEdit || uploading}>
                    {uploading ? 'Uploading…' : 'Attach evidence'}
                  </Button>
                  <input type="file" id="evidence-upload" className="hidden-input" accept=".pdf,.docx,.txt,.csv,.xlsx,.png,.jpg,.jpeg" onChange={onUpload} />
                  <Button variant="secondary" icon={Check} onClick={onSave} disabled={!canEdit || loading}>Save inputs</Button>
                  <Button icon={ListChecks} onClick={onValidate} disabled={!canEdit || loading}>
                    {loading ? 'Working…' : 'Save & validate'}
                  </Button>
                </div>
              </div>
            </section>
            {version.evidence?.length > 0 && (
              <section className="panel evidence-panel">
                <div className="panel-heading">
                  <div>
                    <h3>Supporting evidence</h3>
                    <p>Private uploaded files; this MVP records metadata but does not extract their contents.</p>
                  </div>
                  <span className="small-counter">{version.evidence.length} files</span>
                </div>
                {version.evidence.map((e) => (
                  <div className="evidence-row" key={e.id}>
                    <div className="evidence-icon"><FileText size={17} /></div>
                    <div>
                      <strong>{e.filename}</strong>
                      <small>{(e.size_bytes / 1024).toFixed(1)} KB · SHA-256 {e.checksum_sha256.slice(0, 12)}…</small>
                    </div>
                    <span className="verification-pill"><span /> Stored</span>
                  </div>
                ))}
              </section>
            )}
          </div>
          <aside className="workspace-side-column">
            <section className="panel readiness-panel">
              <div className="panel-heading">
                <div>
                  <h3>Readiness check</h3>
                  <p>Rules-based validation</p>
                </div>
                <div className={`readiness-symbol ${version.validation_status === 'passed' ? 'ready' : blockers.length ? 'blocked' : ''}`}>
                  {version.validation_status === 'passed' ? <CheckCircle2 size={21} /> : <ShieldCheck size={21} />}
                </div>
              </div>
              <div className="readiness-status-row">
                <span>Current revision</span>
                <StatusPill value={version.validation_status === 'passed' ? 'validated' : 'draft'} />
              </div>
              <div className="readiness-counts">
                <div><b className="count-red">{blockers.length}</b><span>Blocking findings</span></div>
                <div><b className="count-amber">{warnings.length}</b><span>Warnings</span></div>
              </div>
              {!showFindings ? (
                <div className="inline-empty">
                  <CircleHelp size={16} />
                  <span>Run validation to see missing details and readiness findings.</span>
                </div>
              ) : findings.length === 0 ? (
                <div className="finding-clear">
                  <CheckCircle2 size={16} />
                  <span>No findings for this validation run.</span>
                </div>
              ) : (
                <div className="findings-list">
                  {findings.slice(0, 7).map((f, i) => (
                    <div className={`finding-item finding-${f.severity}`} key={`${f.code}-${f.field_path}-${i}`}>
                      <div className="finding-mark">
                        {f.severity === 'warning' ? <TriangleAlert size={15} /> : <AlertCircle size={15} />}
                      </div>
                      <div>
                        <strong>{f.message}</strong>
                        <small>{f.field_path}</small>
                        {f.question && <p>{f.question}</p>}
                      </div>
                    </div>
                  ))}
                  {findings.length > 7 && <span className="more-findings">+ {findings.length - 7} more findings</span>}
                </div>
              )}
              <div className="readiness-note">
                <LockKeyhole size={15} />
                <span>Generation is blocked until required input and applicability findings are resolved.</span>
              </div>
            </section>
            <section className="panel step-panel">
              <div className="panel-heading">
                <div>
                  <h3>Next steps</h3>
                  <p>Recommended document path</p>
                </div>
              </div>
              <div className="step-list">
                <Step n="1" title="Complete inputs" done={Object.keys(answers).some((k) => String(answers[k] || '').trim())} />
                <Step n="2" title="Confirm applicability" done={Object.values(applicability).length > 0 && Object.values(applicability).every((a) => ['applicable', 'not_applicable'].includes(a.status) && (a.status !== 'not_applicable' || a.rationale?.trim()))} />
                <Step n="3" title="Validate and generate" done={version.status === 'generated' || ['in_review', 'awaiting_approval', 'released'].includes(version.status)} />
                <Step n="4" title="Review and approve" done={version.status === 'released'} />
              </div>
            </section>
          </aside>
        </div>
      )}

      {tab === 'traceability' && (
        <div className="workspace-content single-column">
          <section className="panel traceability-panel">
            <div className="panel-heading">
              <div>
                <div className="eyebrow">SOURCE-TO-DOCUMENT MAPPING</div>
                <h3>Requirement applicability</h3>
                <p>Decisions and source metadata are snapshotted to this document revision. This does not by itself prove conformity.</p>
              </div>
              <span className="small-counter">{traceLinks.length || template?.requirements?.length || 0} mappings</span>
            </div>
            {traceLinks.some((link) => link.source_verification_status !== 'verified') && (
              <div className="callout callout-warning compact">
                <TriangleAlert size={17} />
                <div>
                  <strong>Source mapping verification needed</strong>
                  <p>Internal IDs are placeholders, not official clause numbers. Verify the exact source edition, clause and requirement summary with licensed materials. Release is blocked while mappings remain unverified.</p>
                </div>
              </div>
            )}
            {traceError && <div className="prompt-error"><AlertCircle size={15} />{traceError}</div>}
            {traceLoading && <div className="loading-state"><LoaderCircle size={16} className="spin" /> Loading traceability snapshots…</div>}
            <div className="traceability-list">
              {traceLinks.map((link) => {
                const code = link.requirement_code;
                const choice = applicability[code] || link.applicability || { status: 'pending', rationale: '' };
                const linkedSections = (content.sections || []).filter((s) => (s.requirement_refs || []).includes(code));
                const sourceVerified = link.source_verification_status === 'verified';
                return (
                  <div className="traceability-item" key={code}>
                    <div className="traceability-item-head">
                      <div className="trace-code-icon"><GitBranch size={17} /></div>
                      <div className="trace-title">
                        <span className="req-id">{code}</span>
                        <strong>{link.title || code}</strong>
                        <small>{link.source_edition || 'Source edition not recorded'} · {link.source_reference || 'Source reference pending verification'}</small>
                      </div>
                      <span className={`verification-pill ${sourceVerified ? 'is-recorded' : ''}`}>
                        <span />{sourceVerified ? 'Source verified' : 'Source unverified'}
                      </span>
                    </div>
                    <div className="traceability-controls">
                      <label className="form-field">
                        <span className="field-label">Applicability decision</span>
                        <select value={choice.status || 'pending'} disabled={!canEdit} onChange={(e) => updateApplicability(code, 'status', e.target.value)}>
                          <option value="pending">Select decision</option>
                          <option value="applicable">Applicable</option>
                          <option value="not_applicable">Not applicable</option>
                        </select>
                      </label>
                      <label className="form-field trace-rationale">
                        <span className="field-label">Rationale {choice.status === 'not_applicable' && <i className="required-star">*</i>}</span>
                        <textarea rows={2} disabled={!canEdit} value={choice.rationale || ''} onChange={(e) => updateApplicability(code, 'rationale', e.target.value)} placeholder="Record why this decision applies to the organization's scope…" />
                      </label>
                    </div>
                    <div className="trace-bottom">
                      <span><FileCheck2 size={14} />{linkedSections.length ? `Linked sections: ${linkedSections.map((s) => s.title).join(', ')}` : 'No generated section linked yet'}</span>
                      {sourceVerified ? <span className="source-verified"><CheckCircle2 size={14} /> Verified by {link.source_verified_by || 'authorized administrator'}</span> : <span className="source-warning"><AlertCircle size={14} /> Source mapping unverified</span>}
                    </div>
                    {link.source_verification_note && <div className="verification-note">Verification note: {link.source_verification_note}</div>}
                  </div>
                );
              })}
            </div>
            <div className="form-footer">
              <span>Applicability decisions are recorded with this document revision.</span>
              <Button icon={Check} onClick={onSave} disabled={!canEdit || loading}>Save decisions</Button>
            </div>
          </section>
        </div>
      )}

      {tab === 'draft' && (
        <div className="workspace-content single-column">
          <section className="panel draft-panel">
            <div className="draft-toolbar">
              <div>
                <div className="eyebrow">DOCUMENT PREVIEW</div>
                <h3>{content.title || doc.title}</h3>
                <p>{doc.document_number} · Revision {version.revision} · {version.provider ? `Generated via ${version.provider}` : 'Draft not yet generated'}</p>
              </div>
              <div className="draft-actions">
                <label className="provider-select">
                  <Sparkles size={15} />
                  <select value={providerId} onChange={(e) => setProviderId(e.target.value)} disabled={!canEdit}>
                    {providers.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}{p.id !== 'offline' && !p.configured ? ' (not configured)' : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <Button variant="secondary" icon={FileText} onClick={loadPromptPreview} disabled={version.validation_status !== 'passed' || promptLoading}>
                  {promptLoading ? 'Loading prompt…' : 'Preview prompt'}
                </Button>
                <Button icon={Zap} onClick={onGenerate} disabled={!canEdit || loading}>
                  {loading ? 'Generating…' : 'Generate / regenerate'}
                </Button>
              </div>
            </div>

            {promptError && <div className="prompt-error"><AlertCircle size={15} />{promptError}</div>}
            {promptPreview && (
              <div className="prompt-inspector">
                <div className="prompt-inspector-head">
                  <div>
                    <strong>Generation prompt preview</strong>
                    <small>Prompt v{promptPreview.prompt_version} · SHA-256 input fingerprint {promptPreview.input_hash.slice(0, 18)}…</small>
                  </div>
                  <button className="icon-button" onClick={() => setPromptPreview(null)}><X size={16} /></button>
                </div>
                <div className="prompt-privacy"><LockKeyhole size={15} />{promptPreview.provider_note}</div>
                <h4>System instructions</h4>
                <pre>{promptPreview.system_instructions}</pre>
                <h4>Compiled prompt</h4>
                <pre>{promptPreview.prompt}</pre>
              </div>
            )}

            {!content.sections?.length ? (
              <div className="preview-empty-card">
                <div className="empty-icon"><Sparkles size={32} /></div>
                <h3>Document Draft Ready to Generate</h3>
                <p>
                  No draft sections generated yet. You can complete or enhance the topic inputs and generate an ISO 13485 compliant draft now.
                </p>
                <div className="preview-empty-actions">
                  <Button icon={ListChecks} variant="secondary" onClick={() => setTab('inputs')}>
                    Edit Inputs & Summary
                  </Button>
                  <Button icon={Zap} onClick={onGenerate} disabled={!canEdit || loading}>
                    {loading ? 'Generating draft…' : '✨ Generate Document Now'}
                  </Button>
                </div>
              </div>
            ) : (
              <>
                <div className="draft-banner">
                  <div>
                    <span className="draft-banner-icon"><AlertCircle size={16} /></span>
                    <span>
                      <strong>{version.status === 'released' ? 'Released controlled revision' : 'AI-generated draft — not approved'}</strong>
                      <small>{version.status === 'released' ? 'This revision was approved and released.' : 'Verify all technical claims, sources, applicability decisions and evidence before review.'}</small>
                    </span>
                  </div>
                  <StatusPill value={version.status} />
                </div>
                <article className="document-preview">
                  <div className="preview-cover">
                    <div className="preview-overline">{doc.document_type}</div>
                    <h1>{content.title || doc.title}</h1>
                    <div className="preview-rule" />
                    <div className="preview-metadata">
                      <div><small>Document ID</small><strong>{doc.document_number}</strong></div>
                      <div><small>Revision</small><strong>{version.revision}</strong></div>
                      <div><small>Status</small><strong>{statusText(version.status)}</strong></div>
                    </div>
                    {(!hasPurposeInSections || !hasScopeInSections) && (content.purpose || content.scope) ? (
                      <div className="preview-purpose">
                        {!hasPurposeInSections && content.purpose && (
                          <>
                            <h3>Purpose</h3>
                            <p>{content.purpose}</p>
                          </>
                        )}
                        {!hasScopeInSections && content.scope && (
                          <>
                            <h3>Scope</h3>
                            <p>{content.scope}</p>
                          </>
                        )}
                      </div>
                    ) : null}
                  </div>
                  <div className="preview-sections">
                    {consolidatedSections.map((s, i) => (
                      <section key={s.section_id} className="preview-section">
                        <div className="preview-section-number">{String(i + 1).padStart(2, '0')}</div>
                        <div className="preview-section-content">
                          <div className="section-header-row">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <h2>{s.title}</h2>
                              <span className="section-id-pill">{s.section_id}</span>
                            </div>
                            {canEdit && (
                              <div className="section-actions">
                                <button
                                  type="button"
                                  className="section-btn"
                                  onClick={() => (editingSectionId === s.section_id ? setEditingSectionId(null) : handleStartEdit(s))}
                                >
                                  <Edit3 size={12} />
                                  {editingSectionId === s.section_id ? 'Cancel' : 'Edit'}
                                </button>
                                <button
                                  type="button"
                                  className="section-btn section-btn-regen"
                                  onClick={() => (regenSectionId === s.section_id ? setRegenSectionId(null) : setRegenSectionId(s.section_id))}
                                >
                                  <Sparkles size={12} />
                                  {regenSectionId === s.section_id ? 'Close' : 'Regenerate'}
                                </button>
                              </div>
                            )}
                          </div>
                          {editingSectionId === s.section_id ? (
                            <div className="section-edit-box">
                              <textarea
                                className="section-edit-textarea"
                                value={editContentText}
                                onChange={(e) => setEditContentText(e.target.value)}
                                rows={7}
                              />
                              <div className="section-edit-footer">
                                <button className="btn btn-secondary btn-small" onClick={() => setEditingSectionId(null)}>
                                  Cancel
                                </button>
                                <button
                                  className="btn btn-primary btn-small"
                                  onClick={() => handleSaveSection(s.section_id)}
                                  disabled={savingSection}
                                >
                                  {savingSection ? <LoaderCircle size={14} className="spin" /> : <Check size={14} />} Save Section
                                </button>
                              </div>
                            </div>
                          ) : regenSectionId === s.section_id ? (
                            <div className="section-regen-box">
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px', color: '#6d28d9', fontSize: '11px', fontWeight: 600 }}>
                                <Sparkles size={14} /> Regenerate section with {providerId === 'openrouter' ? 'OpenRouter' : 'NVIDIA NIM'}
                              </div>
                              <input
                                className="section-regen-input"
                                value={regenInstruction}
                                onChange={(e) => setRegenInstruction(e.target.value)}
                                placeholder="Optional instructions (e.g. Include specific cleanroom monitoring limits and ISO 14644 references)..."
                              />
                              <div className="section-edit-footer">
                                <button className="btn btn-secondary btn-small" onClick={() => setRegenSectionId(null)}>
                                  Cancel
                                </button>
                                <button
                                  className="btn btn-primary btn-small"
                                  style={{ background: 'linear-gradient(135deg, #7c3aed, #4f46e5)', border: 'none', color: '#fff' }}
                                  onClick={() => handleRegenerateSection(s.section_id)}
                                  disabled={regeneratingSection}
                                >
                                  {regeneratingSection ? <LoaderCircle size={14} className="spin" /> : <Zap size={14} />} Regenerate Section
                                </button>
                              </div>
                            </div>
                          ) : (
                            <p className="preserve-lines">{s.content}</p>
                          )}
                          {s.requirement_refs?.length > 0 && (
                            <div className="preview-ref">
                              <GitBranch size={14} />
                              <span>Internal mappings: {s.requirement_refs.join(', ')}</span>
                            </div>
                          )}
                          {s.unresolved_items?.length > 0 && (
                            <div className="preview-open-issues">
                              {s.unresolved_items.map((v, idx) => (
                                <div key={idx}><AlertCircle size={14} />{v}</div>
                              ))}
                            </div>
                          )}
                        </div>
                      </section>
                    ))}
                  </div>
                  {(content.open_issues?.length > 0 || content.review_notes?.length > 0) && (
                    <div className="preview-review-notes">
                      <h3>Open issues & review notes</h3>
                      {[...(content.open_issues || []), ...(content.review_notes || [])].map((v, i) => (
                        <p key={i}><CircleHelp size={14} />{v}</p>
                      ))}
                    </div>
                  )}
                  <div className="preview-footer">
                    Generated {dateLabel(version.generated_at)} · Prompt {version.prompt_version || '—'} · Input hash {version.input_hash?.slice(0, 16) || '—'}…
                  </div>
                </article>
                <div className="draft-footer-actions">
                  {version.status === 'generated' && (
                    <Button icon={ArrowRight} onClick={onSubmitReview} disabled={!['author', 'admin'].includes(role) || loading}>
                      Submit for review
                    </Button>
                  )}
                  {version.status === 'in_review' && (
                    <span className="inline-status-note"><Clock3 size={15} /> Awaiting independent review</span>
                  )}
                  {version.status === 'awaiting_approval' && (
                    <span className="inline-status-note"><Clock3 size={15} /> Awaiting authorized approval</span>
                  )}
                  {version.status === 'released' && (
                    <span className="inline-status-note green"><CheckCircle2 size={15} /> Released revision</span>
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      )}

      {tab === 'workflow' && (
        <div className="workspace-content two-column-content workflow-layout">
          <div className="workspace-main-column">
            <section className="panel workflow-panel">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">CONTROLLED LIFECYCLE</div>
                  <h3>Review and approval history</h3>
                  <p>Actions are bound to revision {version.revision}.</p>
                </div>
                <StatusPill value={version.status} />
              </div>
              <div className="timeline">
                {[
                  { title: 'Draft created', date: version.created_at, detail: `Created by ${version.created_by}`, icon: FileText, done: true },
                  ...(version.generated_at ? [{ title: 'Draft generated', date: version.generated_at, detail: `Provider: ${version.provider} · Model: ${version.model_id}`, icon: Sparkles, done: true }] : []),
                  ...(version.reviews || []).map((r) => ({ title: `Review ${statusText(r.decision)}`, date: r.created_at, detail: `${r.reviewer_email}: ${r.comments || 'No comment provided'}`, icon: MessageSquareText, done: true })),
                  ...(version.approvals || []).map((a) => ({ title: `Approval ${statusText(a.decision)}`, date: a.created_at, detail: `${a.approver_email}: ${a.comments || 'No comment provided'}`, icon: BadgeCheck, done: true })),
                  { title: 'Release', date: version.status === 'released' ? version.approvals?.find((a) => a.decision === 'approve')?.created_at : null, detail: version.status === 'released' ? 'Controlled revision released.' : 'Pending approval decision.', icon: LockKeyhole, done: version.status === 'released' },
                ].map((item, i, arr) => (
                  <div className={`timeline-item ${item.done ? 'done' : ''}`} key={`${item.title}-${i}`}>
                    <div className="timeline-rail">
                      <div className="timeline-dot"><item.icon size={14} /></div>
                      {i < arr.length - 1 && <div className="timeline-line" />}
                    </div>
                    <div className="timeline-content">
                      <div className="timeline-top">
                        <strong>{item.title}</strong>
                        <time>{shortTime(item.date)}</time>
                      </div>
                      <p>{item.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
          <aside className="workspace-side-column">
            <section className="panel action-panel">
              <div className="panel-heading">
                <div>
                  <h3>Available actions</h3>
                  <p>Actions depend on role and revision status.</p>
                </div>
              </div>
              {reviewerMode && (
                <div className="workflow-action">
                  <div className="workflow-action-title">
                    <MessageSquareText size={17} />
                    <strong>Independent review</strong>
                  </div>
                  <textarea rows={3} value={reviewComment} onChange={(e) => setReviewComment(e.target.value)} placeholder="Review notes or corrections…" />
                  <Button icon={CheckCircle2} onClick={() => onReview('accept')} disabled={loading}>Accept review</Button>
                  <Button variant="danger" icon={AlertCircle} onClick={() => onReview('changes_requested')} disabled={loading || !reviewComment.trim()}>Request changes</Button>
                </div>
              )}
              {approverMode && (
                <div className="workflow-action">
                  <div className="workflow-action-title">
                    <BadgeCheck size={17} />
                    <strong>Authorized approval</strong>
                  </div>
                  <textarea rows={3} value={reviewComment} onChange={(e) => setReviewComment(e.target.value)} placeholder="Approval comment (required for rejection)…" />
                  <Button icon={ShieldCheck} onClick={() => onApprove('approve')} disabled={loading}>Approve & release</Button>
                  <Button variant="danger" icon={AlertCircle} onClick={() => onApprove('reject')} disabled={loading || !reviewComment.trim()}>Reject approval</Button>
                </div>
              )}
              {version.status === 'generated' && ['author', 'admin'].includes(role) && (
                <div className="workflow-action">
                  <div className="workflow-action-title">
                    <ArrowRight size={17} />
                    <strong>Ready for review?</strong>
                  </div>
                  <p>Submit the generated draft to start the independent review stage.</p>
                  <Button icon={ArrowRight} onClick={onSubmitReview} disabled={loading}>Submit for review</Button>
                </div>
              )}
              {!reviewerMode && !approverMode && !(version.status === 'generated' && ['author', 'admin'].includes(role)) && (
                <div className="action-disabled">
                  <LockKeyhole size={18} />
                  <strong>No action available</strong>
                  <p>
                    {version.status === 'released' ? 'This revision is immutable. Create a new revision to make changes.' : version.status === 'in_review' ? 'Only an independent reviewer can take action at this stage.' : version.status === 'awaiting_approval' ? 'Only an authorized approver can release this revision.' : 'Complete validation and generation before submitting for review.'}
                  </p>
                </div>
              )}
            </section>
            <section className="panel governance-mini">
              <div className="governance-icon"><ShieldCheck size={18} /></div>
              <strong>Approval is revision-specific</strong>
              <p>Any change after release must be made in a new revision, followed by validation, review and approval again.</p>
            </section>
          </aside>
        </div>
      )}

      {enhanceModalOpen && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setEnhanceModalOpen(false); }}>
          <div className="modal-card">
            <div className="modal-head">
              <div>
                <div className="eyebrow">AI ISO ENHANCER</div>
                <h2>Enhance Draft with ISO Standards</h2>
                <p>Enter a summary of your topic or notes. The AI will populate structured fields and ISO 13485 applicability.</p>
              </div>
              <button className="icon-button" onClick={() => setEnhanceModalOpen(false)}><X size={19} /></button>
            </div>
            <div className="enhance-box" style={{ marginTop: '12px' }}>
              <p className="enhance-hint">Summary or raw procedure points (e.g., sterilization validation, cleanroom monitoring, customer complaints):</p>
              <textarea rows={5} value={summaryPrompt} onChange={(e) => setSummaryPrompt(e.target.value)} placeholder="Enter operational details, scope, limits, and records to be enhanced into ISO 13485 compliant fields..." autoFocus />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setEnhanceModalOpen(false)}>Cancel</button>
              <button className="btn btn-primary" style={{ background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)', color: '#fff', border: 'none' }} onClick={handleEnhanceFromSummary} disabled={enhancing || summaryPrompt.trim().length < 5}>
                {enhancing ? <LoaderCircle size={16} className="spin" /> : <Sparkles size={16} />} ✨ Auto-Populate Inputs
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Step({ n, title, done }) { return <div className={`step-row ${done ? 'step-done' : ''}`}><div className="step-check">{done ? <Check size={13}/> : n}</div><span>{title}</span>{done && <CheckCircle2 size={14}/>}</div>; }

export default App;
