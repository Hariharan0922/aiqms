import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Upload, FileText, CheckCircle2, AlertCircle, TriangleAlert, Eye,
  ArrowDownToLine, RefreshCw, X, LoaderCircle, Layers, FileCode2,
  FileCheck2, Database, Sparkles, ExternalLink, ShieldCheck,
  Search, Cpu, Check, Filter, ArrowRight
} from 'lucide-react';
import {
  uploadIngestionFiles,
  fetchIngestedDocuments,
  fetchIngestedDocumentDetail,
  fetchIngestedSections,
  fetchIngestedChunks,
  fetchIngestedJson,
  fetchVectorStatus,
  embedDocumentVectors,
  performSemanticSearch,
  seedIsoClauses,
  verifyDocumentCompliance,
  fetchTraceabilityMatrix,
} from '../lib/api';

export function IngestionPage({ notify }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState(null);
  const [detailDoc, setDetailDoc] = useState(null);
  const [sections, setSections] = useState([]);
  const [chunks, setChunks] = useState([]);
  const [activeTab, setActiveTab] = useState('metadata');
  const [detailLoading, setDetailLoading] = useState(false);
  const [rawJson, setRawJson] = useState(null);
  const fileInputRef = useRef(null);

  // Milestone 3 State: Vectors, Semantic Search & Compliance Matrix
  const [vectorStatus, setVectorStatus] = useState(null);
  const [indexingDocs, setIndexingDocs] = useState({});
  const [seedingIso, setSeedingIso] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchTopK, setSearchTopK] = useState(5);
  const [searchMinScore, setSearchMinScore] = useState(0.35);
  const [searchDocOnly, setSearchDocOnly] = useState(true);
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [matrixData, setMatrixData] = useState(null);
  const [auditing, setAuditing] = useState(false);
  const [matrixFilter, setMatrixFilter] = useState('all');

  const loadVectorStatus = useCallback(async () => {
    try {
      const res = await fetchVectorStatus();
      setVectorStatus(res);
    } catch {
      // Vector status endpoint non-blocking error
    }
  }, []);

  const loadDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetchIngestedDocuments();
      setDocuments(res.documents || []);
    } catch (err) {
      notify(err.message || 'Failed to load ingested documents', 'error');
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadDocuments();
    loadVectorStatus();
  }, [loadDocuments, loadVectorStatus]);

  const handleFiles = async (filesList) => {
    if (!filesList || filesList.length === 0) return;
    try {
      setUploading(true);
      const res = await uploadIngestionFiles(filesList);
      if (res.successful > 0) {
        notify(`Successfully processed ${res.successful} document(s).`, 'success');
      }
      if (res.failed > 0) {
        const failMsgs = res.documents.filter(d => d.upload_status === 'failed' || d.processing_status === 'failed').map(d => d.error_message).filter(Boolean);
        notify(`Failed to process ${res.failed} document(s): ${failMsgs.join('; ')}`, 'error');
      }
      await loadDocuments();
      await loadVectorStatus();
    } catch (err) {
      notify(err.message || 'File upload failed', 'error');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(Array.from(e.dataTransfer.files));
    }
  };

  const viewDetails = async (docId) => {
    setSelectedDocId(docId);
    setDetailLoading(true);
    setActiveTab('metadata');
    setSearchResults(null);
    setSearchQuery('');
    try {
      const [detail, secRes, chkRes, jsonRes, mtxRes] = await Promise.all([
        fetchIngestedDocumentDetail(docId),
        fetchIngestedSections(docId, false),
        fetchIngestedChunks(docId, false),
        fetchIngestedJson(docId).catch(() => null),
        fetchTraceabilityMatrix(docId).catch(() => null),
      ]);
      setDetailDoc(detail);
      setSections(secRes.sections || []);
      setChunks(chkRes.chunks || []);
      setRawJson(jsonRes);
      setMatrixData(mtxRes);
    } catch (err) {
      notify(err.message || 'Failed to fetch document details', 'error');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleIndexDoc = async (docId, e) => {
    if (e) e.stopPropagation();
    try {
      setIndexingDocs(prev => ({ ...prev, [docId]: true }));
      notify(`Generating nomic-embed-text vectors for document ${docId}...`, 'info');
      const res = await embedDocumentVectors(docId);
      notify(`Successfully indexed ${res.indexed_chunks} chunks into ChromaDB!`, 'success');
      await loadDocuments();
      await loadVectorStatus();
      if (selectedDocId === docId) {
        const freshDetail = await fetchIngestedDocumentDetail(docId);
        setDetailDoc(freshDetail);
      }
    } catch (err) {
      notify(err.message || 'Failed to embed document vectors', 'error');
    } finally {
      setIndexingDocs(prev => ({ ...prev, [docId]: false }));
    }
  };

  const handleSeedIso = async () => {
    try {
      setSeedingIso(true);
      notify('Seeding ISO 13485:2016 standard clauses into database and ChromaDB...', 'info');
      const res = await seedIsoClauses();
      notify(res.message || 'ISO 13485 clauses seeded successfully.', 'success');
      await loadVectorStatus();
    } catch (err) {
      notify(err.message || 'Failed to seed ISO clauses', 'error');
    } finally {
      setSeedingIso(false);
    }
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!searchQuery.trim()) return;
    try {
      setSearchLoading(true);
      const res = await performSemanticSearch({
        query: searchQuery.trim(),
        document_id: searchDocOnly && detailDoc ? detailDoc.id : null,
        top_k: Number(searchTopK) || 5,
        min_score: Number(searchMinScore) || 0.35,
      });
      setSearchResults(res);
    } catch (err) {
      notify(err.message || 'Semantic search failed', 'error');
    } finally {
      setSearchLoading(false);
    }
  };

  const handleRunAudit = async (docId) => {
    try {
      setAuditing(true);
      notify('Executing ISO 13485 compliance audit via local Qwen3 AI...', 'info');
      const runRes = await verifyDocumentCompliance(docId);
      notify(`Audit complete! Overall compliance score: ${runRes.overall_compliance_score}%`, 'success');
      const freshMatrix = await fetchTraceabilityMatrix(docId);
      setMatrixData(freshMatrix);
    } catch (err) {
      notify(err.message || 'Audit verification failed', 'error');
    } finally {
      setAuditing(false);
    }
  };

  const downloadJsonArtifact = () => {
    if (!rawJson) return;
    const blob = new Blob([JSON.stringify(rawJson, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${detailDoc?.id || 'document'}_structured.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const sampleQueries = [
    'Cleanroom environmental monitoring and contamination control',
    'Sterilization validation and microbial barrier controls',
    'Design history file and design verification activities',
    'Device master record requirements and packaging specifications',
    'Corrective and preventive action CAPA nonconformity handling',
  ];

  const filteredMatrixRows = (matrixData?.matrix || []).filter((row) => {
    if (matrixFilter === 'all') return true;
    return row.verdict === matrixFilter;
  });

  return (
    <div className="ingestion-container">
      <div className="page-header">
        <div>
          <div className="eyebrow">MILESTONE 3: VECTOR STORAGE, SEMANTIC RETRIEVAL & ISO 13485 TRACEABILITY</div>
          <h1>Document Ingestion & Compliance Intelligence</h1>
          <p>
            Upload QMS standard operating procedures, manuals, and device master files in DOCX or PDF format.
            The engine deterministically extracts content, generates 768-dim vector embeddings via local Ollama (<code>nomic-embed-text</code>), stores them in persistent ChromaDB, and performs automated ISO 13485:2016 traceability gap audits.
          </p>
        </div>
        <div className="page-header-action">
          <button className="btn btn-secondary btn-small" onClick={() => { loadDocuments(); loadVectorStatus(); }} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* Vector Engine Status Strip */}
      <div className="vector-status-strip">
        <div className="vector-status-group">
          <div className="vector-status-item">
            <span className={`vector-status-dot ${vectorStatus?.ollama_embedding_online ? '' : 'offline'}`} />
            <span>Ollama Embedding: <strong>{vectorStatus?.embedding_model || 'nomic-embed-text'}</strong> ({vectorStatus?.ollama_embedding_online ? 'Online' : 'Connecting...'})</span>
          </div>
          <div className="vector-status-item">
            <Database size={15} color="#6366f1" />
            <span>ChromaDB Chunks: <strong>{vectorStatus?.total_chunks_indexed ?? '—'}</strong> indexed</span>
          </div>
          <div className="vector-status-item">
            <ShieldCheck size={15} color="#10b981" />
            <span>ISO 13485 Library: <strong>{vectorStatus?.iso_clauses_indexed ?? '—'}</strong> standard clauses</span>
          </div>
        </div>
        <div className="vector-status-actions">
          <button
            className="btn btn-secondary btn-small"
            onClick={handleSeedIso}
            disabled={seedingIso}
            title="Seed or verify ISO 13485:2016 standard clauses in the local vector database"
          >
            {seedingIso ? <LoaderCircle size={13} className="spin" /> : <Sparkles size={13} />}
            <span>{seedingIso ? 'Seeding...' : 'Seed ISO 13485 Library'}</span>
          </button>
        </div>
      </div>

      {/* Drag & Drop Upload Zone */}
      <div
        className={`upload-dropzone ${isDragOver ? 'dragover' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".docx,.pdf"
          style={{ display: 'none' }}
          onChange={(e) => handleFiles(Array.from(e.target.files || []))}
        />
        <div className="upload-dropzone-icon">
          {uploading ? <LoaderCircle size={26} className="spin" /> : <Upload size={26} />}
        </div>
        <div>
          <h3>{uploading ? 'Processing uploaded files...' : 'Drop QMS documents here, or click to browse'}</h3>
          <p>Files are verified, safely stored, and processed through our rules-first extraction engine without external cloud leakage.</p>
        </div>
        <div className="format-tags">
          <span className="format-tag docx">DOCX Supported</span>
          <span className="format-tag pdf">PDF Supported</span>
          <span className="format-tag xlsx">XLSX (Planned)</span>
          <span className="muted-cell" style={{ fontSize: '10px', marginLeft: '6px' }}>Max: 20 MB</span>
        </div>
      </div>

      {/* Ingested Documents List */}
      <div className="panel doc-list-panel">
        <div className="panel-heading" style={{ padding: '16px 18px', borderBottom: '1px solid #edf0f5' }}>
          <div>
            <h3>Ingested Documents Repository ({documents.length})</h3>
            <p>Documents extracted into structured schema with vector indexing & ISO 13485 audit records.</p>
          </div>
        </div>

        <div className="document-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Document & Filename</th>
                <th>Doc Number</th>
                <th>Rev</th>
                <th>Format</th>
                <th>Processing Status</th>
                <th>Vector Index</th>
                <th>Sections / Chunks</th>
                <th>Upload Date</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 ? (
                <tr>
                  <td colSpan={9}>
                    <div className="empty-state">
                      <div className="empty-icon"><FileCheck2 size={24} /></div>
                      <strong>No documents ingested yet</strong>
                      <p>Drag and drop DOCX or PDF files above to test extraction and metadata identification.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                documents.map((doc) => {
                  const isIndexing = indexingDocs[doc.id];
                  const isIndexed = doc.vector_status === 'indexed';
                  return (
                    <tr key={doc.id} onClick={() => viewDetails(doc.id)}>
                      <td>
                        <div className="table-document">
                          <div className="table-doc-icon">
                            <FileText size={18} />
                          </div>
                          <div>
                            <strong>{doc.filename}</strong>
                            <small>{doc.metadata_summary?.title || doc.id}</small>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="revision-pill">{doc.metadata_summary?.document_number || '—'}</span>
                      </td>
                      <td>
                        <span className="revision-pill">R{doc.metadata_summary?.revision || '0'}</span>
                      </td>
                      <td>
                        <span className={`format-badge ${doc.file_format}`}>{doc.file_format}</span>
                      </td>
                      <td>
                        <span className={`status-pill status-${doc.processing_status === 'completed' ? 'green' : doc.processing_status === 'failed' ? 'red' : 'blue'}`}>
                          <span className="status-dot" />
                          {doc.processing_status}
                        </span>
                        {doc.ocr_required && (
                          <span className="status-pill status-amber" style={{ marginLeft: '4px' }}>
                            OCR Req
                          </span>
                        )}
                      </td>
                      <td>
                        {isIndexing ? (
                          <span className="status-pill status-blue">
                            <LoaderCircle size={10} className="spin" />
                            Indexing...
                          </span>
                        ) : isIndexed ? (
                          <span className="status-pill status-purple" title="Embedded in ChromaDB">
                            <span className="status-dot" />
                            Indexed
                          </span>
                        ) : (
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                            <span className="status-pill status-unindexed">
                              <span className="status-dot" />
                              Unindexed
                            </span>
                            <button
                              className="btn btn-secondary btn-xs"
                              onClick={(e) => handleIndexDoc(doc.id, e)}
                              title="Embed and index this document in ChromaDB"
                            >
                              <Sparkles size={10} /> Index
                            </button>
                          </div>
                        )}
                      </td>
                      <td>
                        <span className="muted-cell">{doc.total_sections} sec / {doc.total_chunks} chk</span>
                      </td>
                      <td>
                        <span className="muted-cell">{doc.created_at ? new Date(doc.created_at).toLocaleDateString() : '—'}</span>
                      </td>
                      <td>
                        <button
                          className="btn btn-secondary btn-small"
                          onClick={(e) => { e.stopPropagation(); viewDetails(doc.id); }}
                        >
                          <Eye size={13} /> View Data
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Document Details Modal */}
      {selectedDocId && (
        <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) setSelectedDocId(null); }}>
          <div className="modal-card" style={{ width: 'min(980px, 96vw)', maxHeight: '92vh', display: 'flex', flexDirection: 'column' }}>
            <div className="modal-head" style={{ borderBottom: '1px solid #edf0f5', paddingBottom: '14px', marginBottom: '14px' }}>
              <div>
                <div className="eyebrow">{detailDoc?.id} · {detailDoc?.file_format}</div>
                <h2>{detailDoc?.filename}</h2>
                <p>{detailDoc?.metadata?.document_title || 'No explicit title identified'}</p>
              </div>
              <button className="icon-button" onClick={() => setSelectedDocId(null)}><X size={18} /></button>
            </div>

            {/* Modal Tabs */}
            <div className="doc-tabs" style={{ marginBottom: '14px' }}>
              <button className={activeTab === 'metadata' ? 'active' : ''} onClick={() => setActiveTab('metadata')}>
                Extracted Metadata
              </button>
              <button className={activeTab === 'sections' ? 'active' : ''} onClick={() => setActiveTab('sections')}>
                Sections ({sections.length})
              </button>
              <button className={activeTab === 'chunks' ? 'active' : ''} onClick={() => setActiveTab('chunks')}>
                Document Chunks ({chunks.length})
              </button>
              <button className={activeTab === 'search' ? 'active' : ''} onClick={() => setActiveTab('search')}>
                Semantic Search
              </button>
              <button className={activeTab === 'compliance' ? 'active' : ''} onClick={() => setActiveTab('compliance')}>
                ISO 13485 Traceability {matrixData?.has_run && <span className="tab-count">{matrixData.overall_score}%</span>}
              </button>
              <button className={activeTab === 'json' ? 'active' : ''} onClick={() => setActiveTab('json')}>
                Structured JSON
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ flex: 1, overflowY: 'auto', paddingRight: '6px' }}>
              {detailLoading ? (
                <div className="loading-state"><LoaderCircle size={24} className="spin" /> Loading document details...</div>
              ) : (
                <>
                  {activeTab === 'metadata' && (
                    <div className="panel" style={{ padding: '16px' }}>
                      <table className="metadata-table">
                        <tbody>
                          <tr>
                            <td className="metadata-label">Document Title</td>
                            <td className="metadata-value">
                              <strong>{detailDoc?.metadata?.document_title || '—'}</strong>
                              {detailDoc?.metadata?.confidence_scores?.document_title && (
                                <span className="metadata-confidence">{(detailDoc.metadata.confidence_scores.document_title * 100).toFixed(0)}% conf</span>
                              )}
                              {detailDoc?.metadata?.source_snippets?.document_title && (
                                <span className="metadata-snippet">{detailDoc.metadata.source_snippets.document_title}</span>
                              )}
                            </td>
                          </tr>
                          <tr>
                            <td className="metadata-label">Document Number</td>
                            <td className="metadata-value">
                              <span className="revision-pill">{detailDoc?.metadata?.document_number || '—'}</span>
                              {detailDoc?.metadata?.confidence_scores?.document_number && (
                                <span className="metadata-confidence">{(detailDoc.metadata.confidence_scores.document_number * 100).toFixed(0)}% conf</span>
                              )}
                              {detailDoc?.metadata?.source_snippets?.document_number && (
                                <span className="metadata-snippet">{detailDoc.metadata.source_snippets.document_number}</span>
                              )}
                            </td>
                          </tr>
                          <tr>
                            <td className="metadata-label">Revision Number</td>
                            <td className="metadata-value">
                              <span className="revision-pill">{detailDoc?.metadata?.revision || '—'}</span>
                              {detailDoc?.metadata?.confidence_scores?.revision && (
                                <span className="metadata-confidence">{(detailDoc.metadata.confidence_scores.revision * 100).toFixed(0)}% conf</span>
                              )}
                              {detailDoc?.metadata?.source_snippets?.revision && (
                                <span className="metadata-snippet">{detailDoc.metadata.source_snippets.revision}</span>
                              )}
                            </td>
                          </tr>
                          <tr>
                            <td className="metadata-label">Effective Date</td>
                            <td className="metadata-value">
                              {detailDoc?.metadata?.effective_date || '—'}
                              {detailDoc?.metadata?.confidence_scores?.effective_date && (
                                <span className="metadata-confidence">{(detailDoc.metadata.confidence_scores.effective_date * 100).toFixed(0)}% conf</span>
                              )}
                              {detailDoc?.metadata?.source_snippets?.effective_date && (
                                <span className="metadata-snippet">{detailDoc.metadata.source_snippets.effective_date}</span>
                              )}
                            </td>
                          </tr>
                          <tr>
                            <td className="metadata-label">Department / Owner</td>
                            <td className="metadata-value">
                              {detailDoc?.metadata?.department || detailDoc?.metadata?.document_owner || '—'}
                              {detailDoc?.metadata?.confidence_scores?.department && (
                                <span className="metadata-confidence">{(detailDoc.metadata.confidence_scores.department * 100).toFixed(0)}% conf</span>
                              )}
                            </td>
                          </tr>
                          <tr>
                            <td className="metadata-label">Prepared By</td>
                            <td className="metadata-value">
                              {detailDoc?.metadata?.prepared_by || '—'}
                              {detailDoc?.metadata?.source_snippets?.prepared_by && (
                                <span className="metadata-snippet">{detailDoc.metadata.source_snippets.prepared_by}</span>
                              )}
                            </td>
                          </tr>
                          <tr>
                            <td className="metadata-label">Reviewed By</td>
                            <td className="metadata-value">
                              {detailDoc?.metadata?.reviewed_by || '—'}
                              {detailDoc?.metadata?.source_snippets?.reviewed_by && (
                                <span className="metadata-snippet">{detailDoc.metadata.source_snippets.reviewed_by}</span>
                              )}
                            </td>
                          </tr>
                          <tr>
                            <td className="metadata-label">Approved By</td>
                            <td className="metadata-value">
                              {detailDoc?.metadata?.approved_by || '—'}
                              {detailDoc?.metadata?.source_snippets?.approved_by && (
                                <span className="metadata-snippet">{detailDoc.metadata.source_snippets.approved_by}</span>
                              )}
                            </td>
                          </tr>
                          <tr>
                            <td className="metadata-label">Purpose Statement</td>
                            <td className="metadata-value">
                              <p style={{ margin: 0, fontSize: '11px', lineHeight: 1.5 }}>
                                {detailDoc?.metadata?.purpose || <span className="muted-cell">Not explicitly stated</span>}
                              </p>
                            </td>
                          </tr>
                          <tr>
                            <td className="metadata-label">Scope Statement</td>
                            <td className="metadata-value">
                              <p style={{ margin: 0, fontSize: '11px', lineHeight: 1.5 }}>
                                {detailDoc?.metadata?.scope || <span className="muted-cell">Not explicitly stated</span>}
                              </p>
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  )}

                  {activeTab === 'sections' && (
                    <div style={{ display: 'grid', gap: '8px' }}>
                      {sections.map((s) => (
                        <div key={s.section_id} className={`panel section-item-row level-${s.level}`} style={{ padding: '12px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong>
                              {s.section_number ? `${s.section_number} ` : ''}
                              {s.section_title}
                            </strong>
                            <span className="revision-pill">Level {s.level} · Order #{s.section_order}</span>
                          </div>
                          {s.content_text ? (
                            <p style={{ fontSize: '10.5px', color: '#475569', margin: '8px 0 0', lineHeight: 1.55 }}>
                              {s.content_text.length > 300 ? s.content_text.slice(0, 300) + '...' : s.content_text}
                            </p>
                          ) : (
                            <span className="muted-cell" style={{ display: 'block', marginTop: '6px' }}>(Section header only)</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {activeTab === 'chunks' && (
                    <div>
                      <div className="assurance-strip" style={{ marginBottom: '14px' }}>
                        <div className="assurance-icon"><Sparkles size={18} /></div>
                        <div>
                          <strong>Vector Embedding Provenance</strong>
                          <span>Chunks are formatted with document provenance, page ranges, and section titles, indexed into ChromaDB with <code>nomic-embed-text</code>.</span>
                        </div>
                        {detailDoc?.vector_status !== 'indexed' && (
                          <button
                            className="btn btn-primary btn-small"
                            onClick={(e) => handleIndexDoc(detailDoc.id, e)}
                            disabled={indexingDocs[detailDoc?.id]}
                          >
                            <Sparkles size={13} /> Index Chunks Now
                          </button>
                        )}
                      </div>
                      {chunks.map((chk) => (
                        <div key={chk.chunk_id} className="chunk-card">
                          <div className="chunk-header">
                            <div>
                              <span className="chunk-seq">Chunk #{chk.chunk_sequence}</span>
                              <strong style={{ marginLeft: '8px', color: '#1e293b' }}>
                                {chk.section_title || 'General Content'}
                              </strong>
                            </div>
                            <span>{chk.character_count} chars (~{chk.token_count_estimate} tokens)</span>
                          </div>
                          <div className="chunk-text-box">{chk.chunk_text}</div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Semantic Search Tab */}
                  {activeTab === 'search' && (
                    <div>
                      <form onSubmit={handleSearch} className="search-controls-bar">
                        <input
                          type="text"
                          className="search-input-field"
                          placeholder="Search QMS content semantically (e.g. cleanroom controls, CAPA, DHF)..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                        <button type="submit" className="btn btn-primary btn-small" disabled={searchLoading || !searchQuery.trim()}>
                          {searchLoading ? <LoaderCircle size={14} className="spin" /> : <Search size={14} />}
                          <span>Search</span>
                        </button>
                        {searchQuery && (
                          <button type="button" className="btn btn-secondary btn-small" onClick={() => { setSearchQuery(''); setSearchResults(null); }}>
                            Clear
                          </button>
                        )}
                      </form>

                      {/* Quick query chips */}
                      <div className="search-quick-queries">
                        <span style={{ fontSize: '9.5px', color: '#64748b' }}>Try:</span>
                        {sampleQueries.map((q, idx) => (
                          <span
                            key={idx}
                            className="quick-query-chip"
                            onClick={() => {
                              setSearchQuery(q);
                              performSemanticSearch({
                                query: q,
                                document_id: searchDocOnly && detailDoc ? detailDoc.id : null,
                                top_k: searchTopK,
                                min_score: searchMinScore,
                              }).then(setSearchResults).catch(() => {});
                            }}
                          >
                            {q}
                          </span>
                        ))}
                      </div>

                      {/* Filter controls */}
                      <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginBottom: '14px', fontSize: '10.5px', color: '#64748b' }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={searchDocOnly}
                            onChange={(e) => setSearchDocOnly(e.target.checked)}
                          />
                          <span>Restrict to this document</span>
                        </label>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>Top K:</span>
                          <select
                            value={searchTopK}
                            onChange={(e) => setSearchTopK(Number(e.target.value))}
                            style={{ height: '26px', fontSize: '10px', padding: '0 4px', borderRadius: '4px', border: '1px solid #dce2ec' }}
                          >
                            <option value={3}>3</option>
                            <option value={5}>5</option>
                            <option value={10}>10</option>
                            <option value={20}>20</option>
                          </select>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>Min Score:</span>
                          <select
                            value={searchMinScore}
                            onChange={(e) => setSearchMinScore(Number(e.target.value))}
                            style={{ height: '26px', fontSize: '10px', padding: '0 4px', borderRadius: '4px', border: '1px solid #dce2ec' }}
                          >
                            <option value={0.20}>0.20 (Broad)</option>
                            <option value={0.35}>0.35 (Balanced)</option>
                            <option value={0.50}>0.50 (Strict)</option>
                          </select>
                        </div>
                      </div>

                      {/* Results display */}
                      {searchLoading ? (
                        <div className="loading-state"><LoaderCircle size={22} className="spin" /> Executing dense vector search via ChromaDB...</div>
                      ) : searchResults ? (
                        <div>
                          <div className="search-results-summary">
                            <span>Found <strong>{searchResults.total_hits}</strong> relevant chunk(s) across indexed documents.</span>
                            <span>Query latency: <strong>{searchResults.search_time_ms} ms</strong></span>
                          </div>

                          {searchResults.results?.length === 0 ? (
                            <div className="empty-state" style={{ padding: '30px' }}>
                              <AlertCircle size={24} color="#94a3b8" />
                              <strong style={{ marginTop: '8px' }}>No matching chunks above score threshold</strong>
                              <p>Try lowering the minimum score or using broader terminology.</p>
                            </div>
                          ) : (
                            searchResults.results.map((r, i) => {
                              const pct = (r.score * 100).toFixed(1);
                              const scoreClass = r.score >= 0.70 ? 'high' : r.score >= 0.45 ? 'medium' : 'low';
                              return (
                                <div key={r.chunk_id || i} className="search-result-card">
                                  <div className="search-result-head">
                                    <div>
                                      <strong style={{ fontSize: '11px', color: '#1e293b' }}>
                                        {r.section_number ? `${r.section_number} ` : ''}
                                        {r.section_title || 'General Content'}
                                      </strong>
                                      <small style={{ display: 'block', color: '#64748b', fontSize: '9.5px', marginTop: '2px' }}>
                                        {r.document_number ? `Doc #${r.document_number} · ` : ''}
                                        {r.page_start ? `Page ${r.page_start} · ` : ''}
                                        Match type: {r.match_type || 'hybrid'}
                                      </small>
                                    </div>
                                    <span className={`score-badge ${scoreClass}`}>
                                      Score: {pct}%
                                    </span>
                                  </div>
                                  <div className="search-result-body">
                                    {r.text}
                                  </div>
                                </div>
                              );
                            })
                          )}
                        </div>
                      ) : (
                        <div className="empty-state" style={{ padding: '35px 20px' }}>
                          <div className="empty-icon"><Search size={22} /></div>
                          <strong>Semantic Search Sandbox</strong>
                          <p>Enter any QMS query or click one of the suggested sample questions above to retrieve dense vector matches with exact provenance.</p>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ISO 13485 Traceability Tab */}
                  {activeTab === 'compliance' && (
                    <div>
                      {/* Score Banner */}
                      <div className="compliance-score-banner">
                        <div className="compliance-score-main">
                          <div className="compliance-score-circle">
                            {matrixData?.has_run ? `${matrixData.overall_score}%` : '—'}
                          </div>
                          <div>
                            <h3 style={{ margin: '0 0 4px', fontSize: '15px' }}>
                              ISO 13485:2016 Traceability Audit
                            </h3>
                            <p style={{ margin: 0, fontSize: '11px', color: '#c7d2fe', lineHeight: 1.5 }}>
                              {matrixData?.has_run
                                ? `Last verified: ${new Date(matrixData.evaluated_at).toLocaleString()}`
                                : 'No compliance verification audit has been recorded yet for this document.'}
                            </p>
                          </div>
                        </div>
                        <button
                          className="btn btn-secondary btn-small"
                          onClick={() => handleRunAudit(detailDoc.id)}
                          disabled={auditing}
                          style={{ background: '#fff', color: '#1e1b4b', fontWeight: 700 }}
                        >
                          {auditing ? <LoaderCircle size={14} className="spin" /> : <ShieldCheck size={14} />}
                          <span>{auditing ? 'Auditing with AI...' : matrixData?.has_run ? 'Re-run ISO Audit' : 'Run ISO 13485 Audit'}</span>
                        </button>
                      </div>

                      {/* Summary Metrics */}
                      {matrixData?.has_run && (
                        <div className="compliance-metrics-row">
                          <div className="compliance-metric-pill green">
                            <b>{(matrixData.matrix || []).filter(m => m.verdict === 'compliant').length}</b>
                            <span>Compliant Clauses</span>
                          </div>
                          <div className="compliance-metric-pill amber">
                            <b>{(matrixData.matrix || []).filter(m => m.verdict === 'partially_compliant').length}</b>
                            <span>Partial Compliance</span>
                          </div>
                          <div className="compliance-metric-pill red">
                            <b>{(matrixData.matrix || []).filter(m => m.verdict === 'gap_detected').length}</b>
                            <span>Gaps Identified</span>
                          </div>
                          <div className="compliance-metric-pill gray">
                            <b>{(matrixData.matrix || []).filter(m => m.verdict === 'not_addressed').length}</b>
                            <span>Not Addressed</span>
                          </div>
                        </div>
                      )}

                      {/* Filter Bar */}
                      <div className="matrix-filter-bar">
                        <span style={{ fontSize: '10px', color: '#64748b', marginRight: '4px' }}>Filter:</span>
                        {[
                          { id: 'all', label: `All (${matrixData?.matrix?.length || 0})` },
                          { id: 'compliant', label: 'Compliant' },
                          { id: 'partially_compliant', label: 'Partial' },
                          { id: 'gap_detected', label: 'Gaps' },
                          { id: 'not_addressed', label: 'Not Addressed' },
                        ].map((btn) => (
                          <button
                            key={btn.id}
                            className={`matrix-filter-btn ${matrixFilter === btn.id ? 'active' : ''}`}
                            onClick={() => setMatrixFilter(btn.id)}
                          >
                            {btn.label}
                          </button>
                        ))}
                      </div>

                      {/* Matrix Table */}
                      <div className="panel" style={{ overflowX: 'auto' }}>
                        <table className="matrix-table">
                          <thead>
                            <tr>
                              <th style={{ width: '22%' }}>ISO 13485 Clause</th>
                              <th style={{ width: '15%' }}>Matched Section</th>
                              <th style={{ width: '12%' }}>Verdict</th>
                              <th style={{ width: '51%' }}>Auditor Findings & Evidence Citation</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredMatrixRows.length === 0 ? (
                              <tr>
                                <td colSpan={4} style={{ textAlign: 'center', padding: '24px', color: '#94a3b8' }}>
                                  No clauses match the selected filter.
                                </td>
                              </tr>
                            ) : (
                              filteredMatrixRows.map((row) => (
                                <tr key={row.clause_number}>
                                  <td>
                                    <strong>{row.clause_number} {row.clause_title}</strong>
                                    <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
                                      {row.requires_procedure && (
                                        <span className="revision-pill" style={{ fontSize: '8px' }}>Procedure Req</span>
                                      )}
                                      {row.requires_record && (
                                        <span className="revision-pill" style={{ fontSize: '8px' }}>Record Req</span>
                                      )}
                                    </div>
                                    <small style={{ color: '#8b94a5', display: 'block', marginTop: '3px' }}>
                                      Category: {row.category}
                                    </small>
                                  </td>
                                  <td>
                                    {row.section_title ? (
                                      <div>
                                        <strong>{row.section_number ? `${row.section_number} ` : ''}{row.section_title}</strong>
                                        {row.page_start && (
                                          <small style={{ display: 'block', color: '#64748b' }}>Page {row.page_start}</small>
                                        )}
                                        {row.similarity_score > 0 && (
                                          <small style={{ color: '#6366f1' }}>
                                            Sim: {(row.similarity_score * 100).toFixed(0)}%
                                          </small>
                                        )}
                                      </div>
                                    ) : (
                                      <span className="muted-cell">No matching section</span>
                                    )}
                                  </td>
                                  <td>
                                    <span className={`verdict-tag ${row.verdict}`}>
                                      {row.verdict === 'compliant' && <Check size={10} />}
                                      {row.verdict === 'gap_detected' && <AlertCircle size={10} />}
                                      {row.verdict === 'partially_compliant' && <TriangleAlert size={10} />}
                                      {row.verdict.replace('_', ' ')}
                                    </span>
                                    {row.severity && row.verdict !== 'compliant' && row.verdict !== 'untested' && (
                                      <small style={{ display: 'block', color: '#b91c1c', marginTop: '3px', textTransform: 'capitalize' }}>
                                        {row.severity} Severity
                                      </small>
                                    )}
                                  </td>
                                  <td>
                                    <div className="reasoning-box">
                                      {row.reasoning || 'Evaluated against ISO 13485:2016 standard criteria.'}
                                    </div>
                                    {row.evidence_quote && (
                                      <div className="evidence-quote-box">
                                        "{row.evidence_quote}"
                                      </div>
                                    )}
                                    {row.gap_description && (
                                      <div style={{ marginTop: '5px', color: '#b91c1c', fontSize: '9.5px' }}>
                                        <strong>Gap:</strong> {row.gap_description}
                                      </div>
                                    )}
                                    {row.recommended_action && (
                                      <div className="recommendation-box">
                                        <strong>Action:</strong> {row.recommended_action}
                                      </div>
                                    )}
                                  </td>
                                </tr>
                              ))
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {activeTab === 'json' && (
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                        <span className="muted-cell">Schema: Draft-07 Validated ISO 13485 JSON Output</span>
                        <button className="btn btn-secondary btn-small" onClick={downloadJsonArtifact}>
                          <ArrowDownToLine size={13} /> Download JSON
                        </button>
                      </div>
                      <pre className="prompt-inspector pre" style={{ maxHeight: '420px', overflow: 'auto', background: '#0f172a', color: '#e2e8f0', padding: '14px', borderRadius: '8px', fontSize: '10px' }}>
                        {JSON.stringify(rawJson, null, 2)}
                      </pre>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setSelectedDocId(null)}>Close</button>
              {activeTab === 'json' && (
                <button className="btn btn-primary" onClick={downloadJsonArtifact}>
                  <ArrowDownToLine size={14} /> Download JSON Artifact
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}