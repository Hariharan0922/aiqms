import React, { useState, useEffect, useCallback } from 'react';
import {
  Search, FileText, Sparkles, Filter, Database, AlertCircle,
  SlidersHorizontal, CheckCircle2, LoaderCircle, ArrowRight,
  RefreshCw, Layers, ShieldCheck, Tag, X, ChevronRight
} from 'lucide-react';
import { performSemanticSearch, fetchIngestedDocuments, fetchVectorStatus } from '../lib/api';

export function SearchPage({ notify }) {
  const [query, setQuery] = useState('');
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState('');
  const [selectedFormat, setSelectedFormat] = useState('');
  const [topK, setTopK] = useState(5);
  const [minScore, setMinScore] = useState(0.35);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [vectorHealth, setVectorHealth] = useState(null);

  const sampleQueries = [
    { label: 'Device Assembly Spring', query: 'How to attach the spring during medical device assembly?' },
    { label: 'Performance Test Planning', query: 'Test planning and execution for functionality performance testing' },
    { label: 'DripSet Intended Use', query: 'What is the intended use and risk classification of DripSet?' },
    { label: 'Cleanroom Gowning', query: 'Cleanroom contamination control and operator gowning procedures' },
    { label: 'ISO 13485 Process Validation', query: 'ISO 13485 Clause 7.5.6 validation of processes for production' },
    { label: 'Nonconforming Product', query: 'Control of nonconforming product and quarantine procedures' },
  ];

  const loadInitialData = useCallback(async () => {
    try {
      const [docsRes, healthRes] = await Promise.all([
        fetchIngestedDocuments().catch(() => ({ documents: [] })),
        fetchVectorStatus().catch(() => null),
      ]);
      setDocuments(docsRes.documents || []);
      setVectorHealth(healthRes);
    } catch {
      // Non-blocking
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  const handleSearch = async (overrideQuery = null) => {
    const q = (overrideQuery !== null ? overrideQuery : query).trim();
    if (!q) return;

    try {
      setLoading(true);
      const payload = {
        query: q,
        document_id: selectedDocId || null,
        file_format: selectedFormat || null,
        top_k: Number(topK),
        min_score: Number(minScore),
      };
      const res = await performSemanticSearch(payload);
      setResults(res);
      if (res.results.length === 0) {
        notify('No chunks matched the threshold criteria. Try lowering the minimum similarity score.', 'warning');
      }
    } catch (err) {
      notify(err.message || 'Semantic search failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setQuery('');
    setResults(null);
  };

  return (
    <div className="search-page-container">
      <div className="page-header">
        <div>
          <div className="eyebrow">MILESTONE 3.3: SEMANTIC RETRIEVAL ENGINE</div>
          <h1>Semantic Search & QMS Intelligence</h1>
          <p>
            Perform natural-language dense vector search across all ingested QMS documents, procedures, Device Master Files, and ISO 13485 standards.
            Embeddings are generated locally via <code>nomic-embed-text</code> and matched against ChromaDB with authoritative PostgreSQL source resolution.
          </p>
        </div>
        <div className="page-header-action">
          <div className="vector-status-item" style={{ background: '#fff', border: '1px solid #e2e8f0', padding: '6px 12px', borderRadius: '8px' }}>
            <span className={`vector-status-dot ${vectorHealth?.ollama_embedding_online ? '' : 'offline'}`} />
            <span style={{ fontSize: '10.5px' }}>
              Ollama: <strong>{vectorHealth?.embedding_model || 'nomic-embed-text'}</strong> · <strong>{vectorHealth?.total_chunks_indexed || 0}</strong> chunks indexed
            </span>
          </div>
        </div>
      </div>

      {/* Search Input Box & Sample Chips */}
      <div className="panel" style={{ padding: '20px', marginBottom: '20px' }}>
        <form
          onSubmit={(e) => { e.preventDefault(); handleSearch(); }}
          style={{ display: 'flex', gap: '10px', alignItems: 'center', marginBottom: '14px' }}
        >
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={17} style={{ position: 'absolute', left: '12px', top: '11px', color: '#94a3b8' }} />
            <input
              type="text"
              className="search-input-field"
              style={{ width: '100%', paddingLeft: '38px', height: '42px', fontSize: '12.5px' }}
              placeholder="Ask any natural-language compliance or QMS question..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && (
              <button
                type="button"
                onClick={handleClear}
                style={{ position: 'absolute', right: '10px', top: '12px', background: 'transparent', border: 0, color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            )}
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            style={{ height: '42px', padding: '0 18px' }}
            disabled={loading || !query.trim()}
          >
            {loading ? <LoaderCircle size={16} className="spin" /> : <Search size={16} />}
            <span>Search</span>
          </button>
        </form>

        {/* Sample queries */}
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '10px', fontWeight: 700, color: '#64748b' }}>Quick Queries:</span>
          {sampleQueries.map((item, idx) => (
            <button
              key={idx}
              type="button"
              className="quick-query-chip"
              onClick={() => {
                setQuery(item.query);
                handleSearch(item.query);
              }}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filter and Configuration Controls */}
      <div className="panel" style={{ padding: '14px 18px', marginBottom: '20px', display: 'flex', gap: '20px', alignItems: 'center', flexWrap: 'wrap', background: '#f8fafc' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter size={14} color="#64748b" />
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>Scope:</span>
          <select
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
            style={{ height: '32px', fontSize: '11px', padding: '0 8px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#fff' }}
          >
            <option value="">All Ingested Documents ({documents.length})</option>
            {documents.map((d) => (
              <option key={d.id} value={d.id}>
                {d.filename} ({d.metadata_summary?.document_number || d.id})
              </option>
            ))}
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>Format:</span>
          <select
            value={selectedFormat}
            onChange={(e) => setSelectedFormat(e.target.value)}
            style={{ height: '32px', fontSize: '11px', padding: '0 8px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#fff' }}
          >
            <option value="">All Formats</option>
            <option value="DOCX">DOCX Only</option>
            <option value="PDF">PDF Only</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>Top-K:</span>
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            style={{ height: '32px', fontSize: '11px', padding: '0 8px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#fff' }}
          >
            <option value={3}>Top 3</option>
            <option value={5}>Top 5</option>
            <option value={10}>Top 10</option>
            <option value={20}>Top 20</option>
          </select>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#475569' }}>Min Score:</span>
          <select
            value={minScore}
            onChange={(e) => setMinScore(Number(e.target.value))}
            style={{ height: '32px', fontSize: '11px', padding: '0 8px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#fff' }}
          >
            <option value={0.20}>0.20 (Broad Recall)</option>
            <option value={0.35}>0.35 (Balanced)</option>
            <option value={0.50}>0.50 (High Precision)</option>
            <option value={0.65}>0.65 (Strict)</option>
          </select>
        </div>

        {results && (
          <div style={{ marginLeft: 'auto', fontSize: '10.5px', color: '#64748b' }}>
            <span>Found <strong>{results.total_hits}</strong> results in <strong>{results.execution_time_ms} ms</strong></span>
          </div>
        )}
      </div>

      {/* Results Section */}
      {loading ? (
        <div className="panel" style={{ padding: '60px 20px', textAlign: 'center' }}>
          <LoaderCircle size={28} className="spin" color="#4f46e5" style={{ margin: '0 auto 12px' }} />
          <strong>Embedding query and searching ChromaDB...</strong>
          <p style={{ fontSize: '11px', color: '#64748b', margin: '4px 0 0' }}>Resolving dense vectors with PostgreSQL authoritative sources</p>
        </div>
      ) : results ? (
        results.results.length === 0 ? (
          <div className="panel" style={{ padding: '50px 20px', textAlign: 'center' }}>
            <AlertCircle size={32} color="#94a3b8" style={{ margin: '0 auto 12px' }} />
            <strong>No matching chunks found above threshold ({minScore})</strong>
            <p style={{ fontSize: '11px', color: '#64748b', maxWidth: '380px', margin: '6px auto 14px' }}>
              The dense semantic vector similarity did not meet the configured minimum score. Try broadening your query or selecting 0.20 Min Score.
            </p>
            <button
              className="btn btn-secondary btn-small"
              onClick={() => { setMinScore(0.20); handleSearch(); }}
            >
              Lower Threshold to 0.20 & Search Again
            </button>
          </div>
        ) : (
          <div className="search-results-list">
            {results.results.map((r, idx) => {
              const pct = (r.similarity_score * 100).toFixed(1);
              const scoreClass = r.similarity_score >= 0.70 ? 'high' : r.similarity_score >= 0.45 ? 'medium' : 'low';
              return (
                <div key={r.chunk_id || idx} className="search-result-card" style={{ padding: '18px', marginBottom: '14px' }}>
                  <div className="search-result-head">
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span className={`format-badge ${r.file_format}`}>{r.file_format}</span>
                        <strong style={{ fontSize: '12px', color: '#1e293b' }}>
                          {r.document_name}
                        </strong>
                        <span className="revision-pill">{r.document_number} · Rev {r.document_revision}</span>
                      </div>
                      <div style={{ fontSize: '11px', color: '#475569' }}>
                        <strong>{r.section_number ? `${r.section_number} ` : ''}{r.section_title}</strong>
                        {r.page_start && (
                          <span style={{ color: '#64748b', marginLeft: '8px' }}>
                            (Page {r.page_start}{r.page_end && r.page_end !== r.page_start ? `–${r.page_end}` : ''})
                          </span>
                        )}
                        <span style={{ color: '#94a3b8', marginLeft: '8px' }}>· Chunk #{r.chunk_sequence}</span>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <span className={`score-badge ${scoreClass}`} style={{ fontSize: '11px', padding: '4px 10px' }}>
                        {pct}% Match
                      </span>
                      <small style={{ display: 'block', color: '#94a3b8', fontSize: '9px', marginTop: '3px' }}>
                        Distance: {r.cosine_distance} · {r.match_type === 'hybrid' ? 'Hybrid Bonus' : 'Dense Vector'}
                      </small>
                    </div>
                  </div>

                  <div className="search-result-body" style={{ marginTop: '12px', fontSize: '11.5px', lineHeight: 1.65 }}>
                    {r.text}
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        <div className="panel" style={{ padding: '60px 20px', textAlign: 'center' }}>
          <div className="empty-icon" style={{ margin: '0 auto 14px' }}><Sparkles size={24} /></div>
          <strong>Ask a Natural-Language Compliance Question</strong>
          <p style={{ fontSize: '11.5px', color: '#64748b', maxWidth: '440px', margin: '6px auto 16px', lineHeight: 1.55 }}>
            Retrieve precise paragraphs and procedures across Medical Device Files, SOPs, Test Protocols, and ISO 13485:2016 standards with verified citations and provenance.
          </p>
          <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap' }}>
            {sampleQueries.slice(0, 3).map((item, idx) => (
              <button
                key={idx}
                className="btn btn-secondary btn-small"
                onClick={() => { setQuery(item.query); handleSearch(item.query); }}
              >
                {item.label} <ArrowRight size={12} />
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
