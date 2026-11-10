import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertCircle, ArrowRight, BadgeCheck, CheckCircle2, ChevronRight,
  ClipboardCheck, Clock3, ExternalLink, FileCheck2, FileText, Filter, GitBranch,
  History, Info, Layers, LoaderCircle, LockKeyhole, MessageSquare, Play,
  RefreshCw, Search, ShieldAlert, ShieldCheck, Sparkles, TriangleAlert, UserCheck, X
} from 'lucide-react';
import {
  analyzeTraceabilityItemLLM,
  fetchIngestedDocuments,
  fetchTraceabilityItem,
  fetchTraceabilityMatrix,
  generateTraceability,
  reviewTraceabilityItem,
  setTraceabilityNotApplicable,
  submitTraceabilityItem,
  validateTraceabilityItemRules,
} from '../lib/api';

const STATUS_CONFIG = {
  verified_by_reviewer: { label: 'Verified by Reviewer', color: 'badge-success', bg: 'var(--green-light, #ecfdf5)' },
  evidence_identified: { label: 'Evidence Identified', color: 'badge-primary', bg: 'var(--blue-light, #eff6ff)' },
  pending_review: { label: 'Pending Review', color: 'badge-warning', bg: 'var(--amber-light, #fffbeb)' },
  insufficient_evidence: { label: 'Insufficient Evidence', color: 'badge-danger', bg: 'var(--rose-light, #fff1f2)' },
  not_mapped: { label: 'Not Mapped', color: 'badge-neutral', bg: 'var(--surface-sunken, #f1f5f9)' },
  not_applicable: { label: 'Not Applicable', color: 'badge-info', bg: 'var(--purple-light, #faf5ff)' },
};

function StatusPill({ status }) {
  const conf = STATUS_CONFIG[status] || { label: status || 'Unknown', color: 'badge-neutral' };
  return <span className={`badge ${conf.color}`}>{conf.label}</span>;
}

export function TraceabilityPage({ notify }) {
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState('');
  const [matrixData, setMatrixData] = useState(null);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [loadingMatrix, setLoadingMatrix] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [threshold, setThreshold] = useState(0.45);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [chapterFilter, setChapterFilter] = useState('all');

  // Detail Modal / Drawer
  const [selectedItem, setSelectedItem] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [analyzingLLM, setAnalyzingLLM] = useState(false);
  const [llmResult, setLlmResult] = useState(null);

  // Review & N/A Actions
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [reviewDecision, setReviewDecision] = useState('verified');
  const [reviewComment, setReviewComment] = useState('');
  const [actionLoading, setActionLoading] = useState(false);

  const [showNaModal, setShowNaModal] = useState(false);
  const [naJustification, setNaJustification] = useState('');

  // Load Ingested Documents on mount
  useEffect(() => {
    let alive = true;
    setLoadingDocs(true);
    fetchIngestedDocuments({ limit: 100 })
      .then((res) => {
        if (!alive) return;
        const docs = res.documents || [];
        setDocuments(docs);
        if (docs.length > 0 && !selectedDocId) {
          setSelectedDocId(docs[0].id);
        }
      })
      .catch((e) => {
        if (alive && notify) notify(`Failed to load documents: ${e.message}`, 'error');
      })
      .finally(() => {
        if (alive) setLoadingDocs(false);
      });
    return () => { alive = false; };
  }, []);

  // Load Matrix when document changes
  const loadMatrix = useCallback(async (docId) => {
    if (!docId) return;
    setLoadingMatrix(true);
    try {
      const data = await fetchTraceabilityMatrix(docId);
      setMatrixData(data);
    } catch (e) {
      if (notify) notify(`Could not load traceability matrix: ${e.message}`, 'error');
    } finally {
      setLoadingMatrix(false);
    }
  }, [notify]);

  useEffect(() => {
    if (selectedDocId) {
      loadMatrix(selectedDocId);
    }
  }, [selectedDocId, loadMatrix]);

  // Run Traceability Generation
  const handleGenerate = async () => {
    if (!selectedDocId) return;
    setGenerating(true);
    try {
      const res = await generateTraceability(selectedDocId, threshold);
      if (notify) {
        notify(
          `Traceability mapped across 88 ISO clauses! Identified: ${res.evidence_identified}, Insufficient: ${res.insufficient_evidence}, Unmapped: ${res.not_mapped}`,
          'success'
        );
      }
      await loadMatrix(selectedDocId);
    } catch (e) {
      if (notify) notify(`Traceability generation failed: ${e.message}`, 'error');
    } finally {
      setGenerating(false);
    }
  };

  // Inspect Item Detail
  const handleInspect = async (item) => {
    setDetailLoading(true);
    setLlmResult(null);
    try {
      const detail = await fetchTraceabilityItem(item.id);
      setSelectedItem(detail);
    } catch (e) {
      if (notify) notify(`Failed to load item detail: ${e.message}`, 'error');
    } finally {
      setDetailLoading(false);
    }
  };

  // Run Rules Validation on item
  const handleValidateRules = async () => {
    if (!selectedItem) return;
    setActionLoading(true);
    try {
      const res = await validateTraceabilityItemRules(selectedItem.id);
      notify(`Rules engine executed: ${res.passed ? 'PASSED' : 'FAILED'} with ${res.findings_count} findings.`, res.passed ? 'success' : 'warning');
      const refreshed = await fetchTraceabilityItem(selectedItem.id);
      setSelectedItem(refreshed);
      await loadMatrix(selectedDocId);
    } catch (e) {
      notify(`Rule validation failed: ${e.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Run LLM Evidence Analysis
  const handleAnalyzeLLM = async () => {
    if (!selectedItem) return;
    setAnalyzingLLM(true);
    try {
      const res = await analyzeTraceabilityItemLLM(selectedItem.id, 'qwen3:4b');
      setLlmResult(res.analysis);
      notify(`Lead auditor AI analysis complete: verdict is ${res.verdict}.`, 'success');
      const refreshed = await fetchTraceabilityItem(selectedItem.id);
      setSelectedItem(refreshed);
      await loadMatrix(selectedDocId);
    } catch (e) {
      notify(`LLM analysis error: ${e.message}`, 'error');
    } finally {
      setAnalyzingLLM(false);
    }
  };

  // Submit for Review
  const handleSubmitReview = async () => {
    if (!selectedItem) return;
    setActionLoading(true);
    try {
      await submitTraceabilityItem(selectedItem.id);
      notify('Mapping candidate submitted for independent review.', 'success');
      const refreshed = await fetchTraceabilityItem(selectedItem.id);
      setSelectedItem(refreshed);
      await loadMatrix(selectedDocId);
    } catch (e) {
      notify(`Submission failed: ${e.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Record Review Decision
  const handleRecordReview = async () => {
    if (!selectedItem) return;
    if (reviewComment.trim().length < 2) {
      notify('Please enter a substantive reviewer justification/comment.', 'warning');
      return;
    }
    setActionLoading(true);
    try {
      await reviewTraceabilityItem(selectedItem.id, {
        decision: reviewDecision,
        comment: reviewComment.trim(),
      });
      notify(`Reviewer decision recorded: ${reviewDecision.replace('_', ' ').toUpperCase()}`, 'success');
      setShowReviewModal(false);
      setReviewComment('');
      const refreshed = await fetchTraceabilityItem(selectedItem.id);
      setSelectedItem(refreshed);
      await loadMatrix(selectedDocId);
    } catch (e) {
      notify(`Review recording failed: ${e.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Mark Not Applicable
  const handleMarkNotApplicable = async () => {
    if (!selectedItem) return;
    if (naJustification.trim().length < 15) {
      notify('ISO 13485:2016 Clause 1.2 requires documented rationale of at least 15 characters.', 'warning');
      return;
    }
    setActionLoading(true);
    try {
      await setTraceabilityNotApplicable(selectedItem.id, naJustification.trim());
      notify('Clause marked Not Applicable with documented justification.', 'success');
      setShowNaModal(false);
      setNaJustification('');
      const refreshed = await fetchTraceabilityItem(selectedItem.id);
      setSelectedItem(refreshed);
      await loadMatrix(selectedDocId);
    } catch (e) {
      notify(`Exclusion rejected: ${e.message}`, 'error');
    } finally {
      setActionLoading(false);
    }
  };

  // Filtered Items
  const items = matrixData?.items || [];
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      // Query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesClause = item.clause_number.toLowerCase().includes(q);
        const matchesTitle = item.clause_title.toLowerCase().includes(q);
        const matchesSection = (item.section_title || '').toLowerCase().includes(q);
        if (!matchesClause && !matchesTitle && !matchesSection) return false;
      }
      // Status filter
      if (statusFilter !== 'all' && item.mapping_status !== statusFilter) {
        return false;
      }
      // Chapter filter
      if (chapterFilter !== 'all') {
        if (!item.clause_number.startsWith(`${chapterFilter}.`)) {
          return false;
        }
      }
      return true;
    });
  }, [items, searchQuery, statusFilter, chapterFilter]);

  const metrics = matrixData?.metrics || {
    verified: 0,
    evidence_identified: 0,
    pending_review: 0,
    insufficient_evidence: 0,
    not_mapped: 88,
    not_applicable: 0,
  };

  const hasRun = matrixData?.has_run;

  return (
    <div className="traceability-page">
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="eyebrow">ISO 13485:2016 COMPLIANCE TRACEABILITY</div>
          <h1>Traceability Matrix & Evidence Validation</h1>
          <p>
            Automated clause-to-document mapping, deterministic ISO rule validation, and local lead auditor AI analysis.
          </p>
        </div>

        <div className="trace-header-controls">
          <div className="doc-selector-wrap">
            <span className="selector-label">Target QMS Document:</span>
            <select
              className="select-field"
              value={selectedDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
              disabled={generating || loadingDocs}
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.original_filename} ({d.document_type || 'QMS'}) · Rev {d.document_revision || '00'}
                </option>
              ))}
            </select>
          </div>

          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={generating || !selectedDocId}
          >
            {generating ? (
              <>
                <LoaderCircle className="spin" size={16} />
                <span>Mapping 88 Clauses…</span>
              </>
            ) : (
              <>
                <Play size={16} />
                <span>{hasRun ? 'Re-run Traceability' : 'Generate Traceability'}</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Assurance / Safety Notice */}
      <div className="callout callout-info" style={{ marginBottom: '1.5rem' }}>
        <ShieldCheck size={18} />
        <div>
          <strong>Deterministic Rules Engine & Human Review Verification</strong>
          <p>
            Vector similarity identifies candidate evidence but does <em>not</em> imply compliance. High similarity scores do not auto-approve mappings. Every mapping requires independent reviewer verification before release.
          </p>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="metric-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="metric-card">
          <div className="metric-icon metric-indigo"><Layers size={18} /></div>
          <div className="metric-label">Total Clauses</div>
          <div className="metric-value">{matrixData?.total_clauses || 88}</div>
          <div className="metric-note">ISO 13485:2016 Standard</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon metric-green"><BadgeCheck size={18} /></div>
          <div className="metric-label">Verified by Reviewer</div>
          <div className="metric-value">{metrics.verified}</div>
          <div className="metric-note">Independent review passed</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon metric-blue"><FileCheck2 size={18} /></div>
          <div className="metric-label">Evidence Identified</div>
          <div className="metric-value">{metrics.evidence_identified}</div>
          <div className="metric-note">Candidate evidence found</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon metric-amber"><Clock3 size={18} /></div>
          <div className="metric-label">Pending Review</div>
          <div className="metric-value">{metrics.pending_review}</div>
          <div className="metric-note">Submitted for review</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon metric-rose"><TriangleAlert size={18} /></div>
          <div className="metric-label">Insufficient Evidence</div>
          <div className="metric-value">{metrics.insufficient_evidence}</div>
          <div className="metric-note">Missing procedure/records</div>
        </div>

        <div className="metric-card">
          <div className="metric-icon metric-purple"><ShieldAlert size={18} /></div>
          <div className="metric-label">Not Applicable</div>
          <div className="metric-value">{metrics.not_applicable}</div>
          <div className="metric-note">Justified Clause 1.2 exclusions</div>
        </div>
      </div>

      {/* Toolbar & Filters */}
      <div className="panel" style={{ padding: '1rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="search-box" style={{ flex: '1 1 300px' }}>
            <Search size={16} />
            <input
              type="text"
              placeholder="Search clause number (e.g. 7.5.6), title, or section…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')} className="icon-btn-clean">
                <X size={14} />
              </button>
            )}
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <Filter size={15} className="text-muted" />
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Chapter:</span>
            <select
              className="select-field select-small"
              value={chapterFilter}
              onChange={(e) => setChapterFilter(e.target.value)}
            >
              <option value="all">All Chapters (4 - 8)</option>
              <option value="4">4. Quality Management System</option>
              <option value="5">5. Management Responsibility</option>
              <option value="6">6. Resource Management</option>
              <option value="7">7. Product Realization</option>
              <option value="8">8. Measurement, Analysis & Improvement</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Status:</span>
            <select
              className="select-field select-small"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">All Statuses</option>
              <option value="verified_by_reviewer">Verified by Reviewer</option>
              <option value="evidence_identified">Evidence Identified</option>
              <option value="pending_review">Pending Review</option>
              <option value="insufficient_evidence">Insufficient Evidence</option>
              <option value="not_mapped">Not Mapped</option>
              <option value="not_applicable">Not Applicable</option>
            </select>
          </div>

          <div style={{ marginLeft: 'auto', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Showing <b>{filteredItems.length}</b> of {items.length || 88} clauses
          </div>
        </div>
      </div>

      {/* Main Traceability Matrix Table */}
      {loadingMatrix ? (
        <div className="panel" style={{ padding: '3rem', textAlign: 'center' }}>
          <LoaderCircle className="spin" size={28} style={{ margin: '0 auto 1rem' }} />
          <div>Loading ISO 13485 Traceability Matrix…</div>
        </div>
      ) : !hasRun ? (
        <div className="panel" style={{ padding: '3rem', textAlign: 'center' }}>
          <ClipboardCheck size={42} style={{ margin: '0 auto 1rem', opacity: 0.4 }} />
          <h3>No Traceability Mapping Generated Yet</h3>
          <p style={{ maxWidth: '480px', margin: '0 auto 1.5rem', color: 'var(--text-muted)' }}>
            Run the automated traceability engine to retrieve eligible chunks from <b>{documents.find(d => d.id === selectedDocId)?.original_filename || 'the selected document'}</b>, generate candidate mappings, and execute deterministic ISO 13485 rule checks.
          </p>
          <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
            {generating ? <LoaderCircle className="spin" size={16} /> : <Play size={16} />}
            <span>Generate Traceability Now</span>
          </button>
        </div>
      ) : (
        <div className="panel" style={{ overflow: 'hidden' }}>
          <table className="data-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ width: '110px' }}>Clause</th>
                <th>Requirement Title & Category</th>
                <th>Mapped QMS Evidence</th>
                <th style={{ width: '110px' }}>Rules Validation</th>
                <th style={{ width: '140px' }}>Mapping Status</th>
                <th style={{ width: '100px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr
                  key={item.id}
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleInspect(item)}
                  className={selectedItem?.id === item.id ? 'row-selected' : ''}
                >
                  {/* Clause Number */}
                  <td>
                    <span className="mono-text" style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                      {item.clause_number}
                    </span>
                  </td>

                  {/* Title & Category */}
                  <td>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {item.clause_title}
                    </div>
                    <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.25rem', alignItems: 'center' }}>
                      <span className="badge badge-neutral" style={{ fontSize: '0.72rem' }}>
                        {item.category}
                      </span>
                      {item.requires_procedure && (
                        <span className="badge badge-warning" style={{ fontSize: '0.72rem' }}>
                          Mandatory Procedure
                        </span>
                      )}
                      {item.requires_record && (
                        <span className="badge badge-info" style={{ fontSize: '0.72rem' }}>
                          Mandatory Record
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Mapped Section / Provenance */}
                  <td>
                    {item.section_title ? (
                      <div>
                        <div style={{ fontWeight: 500, fontSize: '0.85rem' }}>
                          {item.section_title}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {item.document_number} · Rev {item.document_revision} · Page {item.page_start}
                          {item.mapping_confidence > 0 && ` (Sim: ${(item.mapping_confidence * 100).toFixed(0)}%)`}
                        </div>
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', fontStyle: 'italic' }}>
                        {item.mapping_status === 'not_applicable' ? 'Not Applicable (Justified)' : 'No candidate evidence found'}
                      </span>
                    )}
                  </td>

                  {/* Rules Engine Status */}
                  <td>
                    {item.rules_validation_status === 'passed' ? (
                      <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                        <CheckCircle2 size={12} /> Passed
                      </span>
                    ) : item.rules_validation_status === 'failed' ? (
                      <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                        <TriangleAlert size={12} /> Failed
                      </span>
                    ) : (
                      <span className="badge badge-neutral">Not Run</span>
                    )}
                  </td>

                  {/* Mapping Status */}
                  <td>
                    <StatusPill status={item.mapping_status} />
                  </td>

                  {/* Actions */}
                  <td style={{ textAlign: 'right' }}>
                    <button
                      className="btn btn-secondary btn-small"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleInspect(item);
                      }}
                    >
                      <span>Inspect</span>
                      <ChevronRight size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detailed Inspection Drawer / Modal */}
      {selectedItem && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setSelectedItem(null); }}>
          <div className="modal-card modal-large" style={{ maxWidth: '880px', maxHeight: '90vh', overflowY: 'auto' }}>
            {/* Modal Header */}
            <div className="modal-head" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
              <div>
                <div className="eyebrow">CLAUSE EVIDENCE & VALIDATION DETAILS</div>
                <h2>Clause {selectedItem.clause_number}: {selectedItem.clause_title}</h2>
                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.4rem', alignItems: 'center' }}>
                  <span className="badge badge-neutral">{selectedItem.category}</span>
                  <StatusPill status={selectedItem.mapping_status} />
                  {selectedItem.requires_procedure && <span className="badge badge-warning">Mandatory Procedure</span>}
                  {selectedItem.requires_record && <span className="badge badge-info">Mandatory Record</span>}
                </div>
              </div>
              <button className="icon-button" onClick={() => setSelectedItem(null)}>
                <X size={18} />
              </button>
            </div>

            {/* Normative ISO Requirement Text */}
            <div style={{ marginTop: '1.2rem' }}>
              <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Normative ISO 13485 Requirement Text:
              </h4>
              <div className="code-box" style={{ background: 'var(--surface-sunken)', padding: '0.85rem', borderRadius: '6px', fontSize: '0.88rem', lineHeight: '1.5' }}>
                {selectedItem.normative_text || 'Normative requirement text stored in knowledge base.'}
              </div>
            </div>

            {/* Supporting QMS Evidence Excerpt & Provenance */}
            <div style={{ marginTop: '1.2rem' }}>
              <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Supporting QMS Evidence & Exact Provenance:
              </h4>
              {selectedItem.section_title ? (
                <div style={{ background: 'var(--surface)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '1rem' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem', marginBottom: '0.75rem', fontSize: '0.82rem' }}>
                    <div><b>Document ID:</b> {selectedItem.document_number}</div>
                    <div><b>Revision:</b> Rev {selectedItem.document_revision}</div>
                    <div><b>Section:</b> {selectedItem.section_title}</div>
                    <div><b>Page:</b> Page {selectedItem.page_start}-{selectedItem.page_end || selectedItem.page_start}</div>
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                    <b>Matched Chunk ID:</b> <code className="mono-text">{selectedItem.matched_chunk_id || 'manual'}</code> · <b>Similarity Confidence:</b> {(selectedItem.mapping_confidence * 100).toFixed(1)}%
                  </div>
                  <blockquote style={{ margin: 0, padding: '0.75rem 1rem', borderLeft: '3px solid var(--color-primary)', background: 'var(--surface-sunken)', fontStyle: 'italic', fontSize: '0.88rem' }}>
                    "{selectedItem.evidence_excerpt}"
                  </blockquote>
                </div>
              ) : selectedItem.na_justification ? (
                <div className="callout callout-warning">
                  <Info size={16} />
                  <div>
                    <strong>Clause Marked Not Applicable</strong>
                    <p>{selectedItem.na_justification}</p>
                  </div>
                </div>
              ) : (
                <div className="empty-state" style={{ padding: '1.5rem', textAlign: 'center' }}>
                  <p style={{ margin: 0, color: 'var(--text-muted)' }}>No candidate evidence currently linked to this clause.</p>
                </div>
              )}
            </div>

            {/* Deterministic Rules Engine Findings */}
            <div style={{ marginTop: '1.2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
                  Deterministic Rules Engine Validation:
                </h4>
                <button
                  className="btn btn-secondary btn-small"
                  onClick={handleValidateRules}
                  disabled={actionLoading}
                >
                  <RefreshCw size={13} className={actionLoading ? 'spin' : ''} />
                  <span>Re-validate Rules</span>
                </button>
              </div>

              <div style={{ background: 'var(--surface-sunken)', borderRadius: '6px', padding: '0.85rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                  {selectedItem.rules_findings?.checks ? (
                    Object.entries(selectedItem.rules_findings.checks).map(([check, passed]) => (
                      <span
                        key={check}
                        className={`badge ${passed ? 'badge-success' : 'badge-danger'}`}
                        style={{ fontSize: '0.72rem' }}
                      >
                        {passed ? '✓' : '✗'} {check}
                      </span>
                    ))
                  ) : (
                    <span className="text-muted" style={{ fontSize: '0.82rem' }}>No automated rule checks recorded yet.</span>
                  )}
                </div>

                {/* Findings list */}
                {selectedItem.rules_findings?.findings && selectedItem.rules_findings.findings.length > 0 ? (
                  <div style={{ marginTop: '0.5rem' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.82rem', marginBottom: '0.25rem' }}>Identified Findings:</div>
                    <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.82rem', color: 'var(--color-danger)' }}>
                      {selectedItem.rules_findings.findings.map((f, i) => (
                        <li key={i}>
                          <b>[{f.rule_id} - {f.severity.toUpperCase()}]:</b> {f.message}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div style={{ fontSize: '0.82rem', color: 'var(--color-success)', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <CheckCircle2 size={14} /> All deterministic rule constraints satisfied.
                  </div>
                )}
              </div>
            </div>

            {/* Local LLM Lead Auditor Analysis (Qwen3 4B) */}
            <div style={{ marginTop: '1.2rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Sparkles size={16} style={{ color: 'var(--color-primary)' }} />
                  <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
                    Local LLM Lead Auditor Reasoning (Qwen3 4B):
                  </h4>
                </div>
                <button
                  className="btn btn-primary btn-small"
                  onClick={handleAnalyzeLLM}
                  disabled={analyzingLLM || !selectedItem.evidence_excerpt}
                >
                  {analyzingLLM ? (
                    <>
                      <LoaderCircle size={13} className="spin" />
                      <span>Auditing Evidence…</span>
                    </>
                  ) : (
                    <>
                      <Sparkles size={13} />
                      <span>Run AI Lead Auditor Analysis</span>
                    </>
                  )}
                </button>
              </div>

              {selectedItem.verdict || llmResult ? (
                <div style={{ background: 'var(--surface-sunken)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '1rem' }}>
                  <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center', marginBottom: '0.75rem' }}>
                    <b>Auditor Verdict:</b>
                    <span className={`badge ${
                      (llmResult?.verdict || selectedItem.verdict) === 'compliant' ? 'badge-success' :
                      (llmResult?.verdict || selectedItem.verdict) === 'partially_compliant' ? 'badge-warning' :
                      'badge-danger'
                    }`}>
                      {(llmResult?.verdict || selectedItem.verdict || '').toUpperCase()}
                    </span>
                    {llmResult?.confidence && (
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        (Confidence: {(llmResult.confidence * 100).toFixed(0)}%)
                      </span>
                    )}
                  </div>

                  <div style={{ fontSize: '0.85rem', marginBottom: '0.75rem', lineHeight: '1.5' }}>
                    <b>Auditor Explanation:</b><br />
                    {llmResult?.explanation || selectedItem.ai_reasoning || 'No explanation available.'}
                  </div>

                  {llmResult?.missing_evidence && llmResult.missing_evidence.length > 0 && (
                    <div style={{ marginBottom: '0.5rem', fontSize: '0.82rem' }}>
                      <b style={{ color: 'var(--color-warning)' }}>Missing Evidence / Gaps:</b>
                      <ul style={{ margin: '0.2rem 0 0 1.2rem', padding: 0 }}>
                        {llmResult.missing_evidence.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {llmResult?.inconsistencies && llmResult.inconsistencies.length > 0 && (
                    <div style={{ marginBottom: '0.5rem', fontSize: '0.82rem' }}>
                      <b style={{ color: 'var(--color-danger)' }}>Inconsistencies / Provenance Flags:</b>
                      <ul style={{ margin: '0.2rem 0 0 1.2rem', padding: 0 }}>
                        {llmResult.inconsistencies.map((item, idx) => (
                          <li key={idx}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {llmResult?.recommended_remediation && (
                    <div style={{ fontSize: '0.82rem', marginTop: '0.5rem', color: 'var(--text-muted)' }}>
                      <b>Recommended Remediation:</b> {llmResult.recommended_remediation}
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ background: 'var(--surface-sunken)', borderRadius: '6px', padding: '1rem', fontSize: '0.85rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                  Click "Run AI Lead Auditor Analysis" to evaluate this evidence excerpt against Clause {selectedItem.clause_number} using strictly local Qwen3 4B.
                </div>
              )}
            </div>

            {/* Human Review & Decision Actions */}
            <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
              <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.75rem' }}>
                Human Workflow Controls & Decisions:
              </h4>

              <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                {/* Submit for review */}
                <button
                  className="btn btn-secondary"
                  onClick={handleSubmitReview}
                  disabled={actionLoading || selectedItem.mapping_status === 'verified_by_reviewer' || selectedItem.mapping_status === 'pending_review'}
                >
                  <Clock3 size={15} />
                  <span>Submit for Review</span>
                </button>

                {/* Record review decision */}
                <button
                  className="btn btn-primary"
                  onClick={() => setShowReviewModal(true)}
                  disabled={actionLoading}
                >
                  <UserCheck size={15} />
                  <span>Record Reviewer Decision</span>
                </button>

                {/* Mark Not Applicable */}
                <button
                  className="btn btn-secondary"
                  onClick={() => setShowNaModal(true)}
                  disabled={actionLoading}
                >
                  <ShieldAlert size={15} />
                  <span>Mark Not Applicable (Clause 1.2)</span>
                </button>
              </div>

              {selectedItem.reviewed_by && (
                <div style={{ marginTop: '0.75rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  <b>Last Review:</b> {selectedItem.reviewer_decision?.toUpperCase()} by {selectedItem.reviewed_by} on {new Date(selectedItem.reviewed_at).toLocaleString()}
                  {selectedItem.reviewer_comment && <div><em>"{selectedItem.reviewer_comment}"</em></div>}
                </div>
              )}
            </div>

            {/* Immutable Audit Trail Log */}
            <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border-color)', paddingTop: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.6rem' }}>
                <History size={15} style={{ color: 'var(--text-muted)' }} />
                <h4 style={{ fontSize: '0.9rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
                  Immutable Audit Trail:
                </h4>
              </div>

              {selectedItem.audit_trail && selectedItem.audit_trail.length > 0 ? (
                <div style={{ maxHeight: '160px', overflowY: 'auto', background: 'var(--surface-sunken)', borderRadius: '6px', padding: '0.5rem' }}>
                  <table style={{ width: '100%', fontSize: '0.78rem' }}>
                    <tbody>
                      {selectedItem.audit_trail.map((entry, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid var(--border-color)' }}>
                          <td style={{ padding: '0.3rem', width: '130px', color: 'var(--text-muted)' }}>
                            {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                          </td>
                          <td style={{ padding: '0.3rem', fontWeight: 600 }}>
                            {entry.action || entry.model || 'event'}
                          </td>
                          <td style={{ padding: '0.3rem', color: 'var(--text-muted)' }}>
                            {entry.actor || 'system'}
                          </td>
                          <td style={{ padding: '0.3rem' }}>
                            {entry.comment || entry.justification || entry.verdict || ''}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>No audit events logged for this item yet.</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Review Decision Dialog */}
      {showReviewModal && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowReviewModal(false); }}>
          <div className="modal-card" style={{ maxWidth: '480px' }}>
            <div className="modal-head">
              <div>
                <div className="eyebrow">QUALITY GATE</div>
                <h3>Record Reviewer Decision</h3>
                <p>Authorized review for Clause {selectedItem?.clause_number}</p>
              </div>
              <button className="icon-button" onClick={() => setShowReviewModal(false)}>
                <X size={18} />
              </button>
            </div>

            <div style={{ marginTop: '1rem' }}>
              <label className="form-field">
                <span className="field-label">Decision:</span>
                <select
                  className="select-field"
                  value={reviewDecision}
                  onChange={(e) => setReviewDecision(e.target.value)}
                >
                  <option value="verified">Verify Mapping (Approve Conformance)</option>
                  <option value="changes_requested">Changes Requested (Gaps Exist)</option>
                  <option value="rejected">Reject Mapping (Invalid / Unrelated)</option>
                </select>
              </label>

              <label className="form-field" style={{ marginTop: '0.75rem' }}>
                <span className="field-label">Reviewer Notes & Justification (Mandatory):</span>
                <textarea
                  rows={3}
                  value={reviewComment}
                  onChange={(e) => setReviewComment(e.target.value)}
                  placeholder="Explain rationale for verification or specify required changes…"
                />
              </label>
            </div>

            <div className="modal-actions" style={{ marginTop: '1.2rem' }}>
              <button className="btn btn-secondary" onClick={() => setShowReviewModal(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleRecordReview}
                disabled={actionLoading || reviewComment.trim().length < 2}
              >
                {actionLoading ? <LoaderCircle className="spin" size={16} /> : <CheckCircle2 size={16} />}
                <span>Record Decision</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Not Applicable Justification Dialog */}
      {showNaModal && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowNaModal(false); }}>
          <div className="modal-card" style={{ maxWidth: '520px' }}>
            <div className="modal-head">
              <div>
                <div className="eyebrow">ISO 13485:2016 CLAUSE 1.2</div>
                <h3>Document Exclusion Justification</h3>
                <p>Clause {selectedItem?.clause_number}: {selectedItem?.clause_title}</p>
              </div>
              <button className="icon-button" onClick={() => setShowNaModal(false)}>
                <X size={18} />
              </button>
            </div>

            <div className="callout callout-warning" style={{ margin: '1rem 0' }}>
              <AlertCircle size={16} />
              <div>
                <strong>Exclusion Restriction</strong>
                <p>
                  Per ISO 13485:2016 Clause 1.2, exclusions are strictly limited to Clause 6, 7, and 8. Requirements in Clause 4 and Clause 5 cannot be excluded from any quality management system.
                </p>
              </div>
            </div>

            <label className="form-field">
              <span className="field-label">Documented Justification (Min 15 chars):</span>
              <textarea
                rows={4}
                value={naJustification}
                onChange={(e) => setNaJustification(e.target.value)}
                placeholder="Document why this requirement is not applicable based on the nature of the medical device or regulatory scope…"
              />
            </label>

            <div className="modal-actions" style={{ marginTop: '1.2rem' }}>
              <button className="btn btn-secondary" onClick={() => setShowNaModal(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleMarkNotApplicable}
                disabled={actionLoading || naJustification.trim().length < 15}
              >
                {actionLoading ? <LoaderCircle className="spin" size={16} /> : <ShieldAlert size={16} />}
                <span>Confirm Exclusion</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
