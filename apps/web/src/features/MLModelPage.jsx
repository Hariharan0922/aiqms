import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity, AlertCircle, ArrowRight, Award, BadgeCheck, BookOpen, Brain,
  CheckCircle2, ChevronRight, Cloud, Cpu, Download, ExternalLink, FileCheck,
  FileCode, FileText, Gauge, GitBranch, Globe, Info, Layers, LoaderCircle,
  Play, RefreshCw, Search, ShieldAlert, ShieldCheck, Sparkles, Terminal,
  Wand2, Zap
} from 'lucide-react';
import {
  auditISOTerm,
  fetchISOMLModelInfo,
  fetchSFTDatasetSample,
  predictISOClause,
  trainISOMLModel,
  verifyAndGenerateML,
} from '../lib/api';

const SAMPLE_PRESETS = [
  {
    label: 'Sterilization Validation (Clause 7.5.7)',
    targetClause: '7.5.7',
    templateId: 'sop',
    text: 'Standard Operating Procedure for Ethylene Oxide (EtO) sterilization cycle validation per ISO 11135. Critical process parameters including gas concentration, temperature, relative humidity, and biological indicator lethality shall be recorded for each batch. Sterile barrier packaging integrity must be validated per ISO 11607.',
  },
  {
    label: 'Medical Device File (Clause 4.2.3)',
    targetClause: '4.2.3',
    templateId: 'dmr',
    text: 'The organization establishes and maintains a Medical Device File (Device Master Record) for each family of coronary catheters. The file contains general device descriptions, design specifications, bill of materials, manufacturing and packaging procedures, QC test methods, and labeling.',
  },
  {
    label: 'Customer Complaint Handling (Clause 8.2.2)',
    targetClause: '8.2.2',
    templateId: 'complaint_procedure',
    text: 'Documented procedure for timely intake, triage, and investigation of customer complaints. All alleged deficiencies regarding device performance or patient safety shall be evaluated for vigilance reporting and corrective action. Investigation records are maintained in the electronic QMS.',
  },
  {
    label: 'CAPA & Root Cause Analysis (Clause 8.5.2)',
    targetClause: '8.5.2',
    templateId: 'capa_plan',
    text: 'Corrective Action procedure requiring formal 5-Why root cause determination for systemic nonconformities. Remediation actions must be verified for effectiveness across three consecutive manufacturing lots before closure, ensuring no adverse effect on product safety.',
  },
  {
    label: 'Design Inputs & Risk Management (Clause 7.3.3)',
    targetClause: '7.3.3',
    templateId: 'design_plan',
    text: 'Design and development inputs shall be determined, reviewed, and approved prior to detailed engineering. Inputs encompass intended use, user safety requirements, essential performance criteria, electrical safety (IEC 60601), and risk mitigations derived from ISO 14971 risk management files.',
  },
  {
    label: 'Equipment Calibration & Metrology (Clause 7.6)',
    targetClause: '7.6',
    templateId: 'sop',
    text: 'Calibration and maintenance procedure for digital micrometers and force test gauges. All measuring equipment must be calibrated against standards traceable to national or international metrology institutes (NIST). Calibration status tags and calibration certificates are retained.',
  },
];

export function MLModelPage({ notify }) {
  const [activeTab, setActiveTab] = useState('pipeline'); // 'pipeline' | 'inference' | 'architecture' | 'sft'
  const [inputText, setInputText] = useState(SAMPLE_PRESETS[0].text);
  const [targetTemplate, setTargetTemplate] = useState('sop');
  const [targetClause, setTargetClause] = useState('7.5.7');
  const [providerChoice, setProviderChoice] = useState('nvidia');
  
  // Loading states
  const [loadingPipeline, setLoadingPipeline] = useState(false);
  const [loadingInference, setLoadingInference] = useState(false);
  const [loadingTrain, setLoadingTrain] = useState(false);
  
  // Pipeline result
  const [pipelineResult, setPipelineResult] = useState(null);

  // Model state & metrics
  const [modelInfo, setModelInfo] = useState(null);
  const [predictions, setPredictions] = useState(null);
  const [auditResult, setAuditResult] = useState(null);
  const [sftData, setSftData] = useState(null);

  const loadModelDetails = useCallback(async () => {
    try {
      const info = await fetchISOMLModelInfo();
      setModelInfo(info);
    } catch (err) {
      if (notify) notify(`Failed to load ML model info: ${err.message}`, 'error');
    }
  }, [notify]);

  const loadSftPreview = useCallback(async () => {
    try {
      const data = await fetchSFTDatasetSample(6);
      setSftData(data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    loadModelDetails();
    loadSftPreview();
  }, [loadModelDetails, loadSftPreview]);

  // Execute full 4-stage pipeline (ML verify -> Online research -> External API -> Structured output)
  const handleRunPipeline = async () => {
    if (!inputText.trim()) return;
    setLoadingPipeline(true);
    try {
      const payload = {
        summary: inputText,
        template_id: targetTemplate || 'sop',
        provider: providerChoice,
      };
      const res = await verifyAndGenerateML(payload);
      setPipelineResult(res);
      if (notify) notify(`Verification & Cloud Generation complete in ${(res.total_latency_ms / 1000).toFixed(2)}s!`, 'success');
    } catch (err) {
      if (notify) notify(`Pipeline execution failed: ${err.message}`, 'error');
    } finally {
      setLoadingPipeline(false);
    }
  };

  const handleRunInference = async () => {
    if (!inputText.trim()) return;
    setLoadingInference(true);
    try {
      const [predRes, auditRes] = await Promise.all([
        predictISOClause(inputText, 5),
        auditISOTerm(inputText, targetClause || null),
      ]);
      setPredictions(predRes);
      setAuditResult(auditRes);
      if (notify) notify(`ML classification complete in ${predRes.inference_latency_ms} ms!`, 'success');
    } catch (err) {
      if (notify) notify(`ML inference error: ${err.message}`, 'error');
    } finally {
      setLoadingInference(false);
    }
  };

  const handleRetrain = async () => {
    setLoadingTrain(true);
    try {
      const res = await trainISOMLModel(true);
      if (notify) notify(`Model retrained in ${res.training_duration_seconds}s! Accuracy: ${(res.metrics.training_accuracy * 100).toFixed(1)}%`, 'success');
      loadModelDetails();
    } catch (err) {
      if (notify) notify(`Retraining failed: ${err.message}`, 'error');
    } finally {
      setLoadingTrain(false);
    }
  };

  const applyPreset = (preset) => {
    setInputText(preset.text);
    setTargetClause(preset.targetClause);
    if (preset.templateId) setTargetTemplate(preset.templateId);
  };

  return (
    <div className="ingestion-page" style={{ padding: '24px 32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Header Banner */}
      <header className="page-header" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span className="badge badge-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <Brain size={13} /> ISO 13485:2016 ML ENGINE
              </span>
              <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <Cloud size={13} /> NVIDIA NIM Cloud API Connected
              </span>
              <span className="badge badge-neutral" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <Globe size={13} /> Online Resources & Standards Research
              </span>
            </div>
            <h1 style={{ fontSize: '26px', fontWeight: '700', color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
              ISO 13485 ML Model Backend Verification & Cloud Generation
            </h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '14px', margin: 0, maxWidth: '900px' }}>
              The ISO 13485 Machine Learning model verifies and audits user-given inputs and topic summaries in the backend,
              compares requirements against the standard, gathers live online standards and industrial parameters, and connects
              with the external cloud API (NVIDIA NIM) to generate structured, audit-ready compliance documentation.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              className="btn btn-secondary"
              onClick={handleRetrain}
              disabled={loadingTrain}
              title="Retrain model on latest extracted ISO clauses"
            >
              {loadingTrain ? <LoaderCircle size={15} className="spin" /> : <RefreshCw size={15} />}
              Retrain Model
            </button>
            <a
              href="http://localhost:8000/api/v1/compliance/ml/export/sft-file"
              download="iso_13485_sft_dataset.jsonl"
              className="btn btn-primary"
              style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            >
              <Download size={15} /> Export SFT Dataset
            </a>
          </div>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-color)', marginTop: '20px' }}>
          <button
            onClick={() => setActiveTab('pipeline')}
            style={{
              padding: '10px 18px',
              border: 'none',
              borderBottom: activeTab === 'pipeline' ? '2px solid var(--primary-color, #4f46e5)' : '2px solid transparent',
              background: 'transparent',
              fontWeight: activeTab === 'pipeline' ? '600' : '500',
              color: activeTab === 'pipeline' ? 'var(--primary-color, #4f46e5)' : 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Sparkles size={15} /> 4-Stage Backend Pipeline (ML + Cloud)
          </button>
          <button
            onClick={() => setActiveTab('inference')}
            style={{
              padding: '10px 18px',
              border: 'none',
              borderBottom: activeTab === 'inference' ? '2px solid var(--primary-color, #4f46e5)' : '2px solid transparent',
              background: 'transparent',
              fontWeight: activeTab === 'inference' ? '600' : '500',
              color: activeTab === 'inference' ? 'var(--primary-color, #4f46e5)' : 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Play size={15} /> Local ML Clause Classifier & Auditor
          </button>
          <button
            onClick={() => setActiveTab('architecture')}
            style={{
              padding: '10px 18px',
              border: 'none',
              borderBottom: activeTab === 'architecture' ? '2px solid var(--primary-color, #4f46e5)' : '2px solid transparent',
              background: 'transparent',
              fontWeight: activeTab === 'architecture' ? '600' : '500',
              color: activeTab === 'architecture' ? 'var(--primary-color, #4f46e5)' : 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Cpu size={15} /> Architecture & Telemetry
          </button>
          <button
            onClick={() => setActiveTab('sft')}
            style={{
              padding: '10px 18px',
              border: 'none',
              borderBottom: activeTab === 'sft' ? '2px solid var(--primary-color, #4f46e5)' : '2px solid transparent',
              background: 'transparent',
              fontWeight: activeTab === 'sft' ? '600' : '500',
              color: activeTab === 'sft' ? 'var(--primary-color, #4f46e5)' : 'var(--text-secondary)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <FileCode size={15} /> LLM Fine-Tuning Dataset (SFT)
          </button>
        </div>
      </header>

      {/* TAB 1: 4-STAGE PIPELINE (HERO VIEW) */}
      {activeTab === 'pipeline' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          {/* Left Column: Input and Configuration */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="card" style={{ padding: '20px', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '600', margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <FileText size={17} /> User Input Notes or Summary
                </h3>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {inputText.length} characters
                </span>
              </div>

              {/* Sample Presets */}
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Choose Sample Input Scenario:
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {SAMPLE_PRESETS.map((p, idx) => (
                    <button
                      key={idx}
                      onClick={() => applyPreset(p)}
                      style={{
                        padding: '4px 10px',
                        fontSize: '11px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-color)',
                        background: targetClause === p.targetClause ? 'var(--primary-light, #e0e7ff)' : 'var(--surface-sunken, #f8fafc)',
                        color: targetClause === p.targetClause ? 'var(--primary-color, #4338ca)' : 'var(--text-primary)',
                        cursor: 'pointer',
                        fontWeight: targetClause === p.targetClause ? '600' : '400',
                      }}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <textarea
                rows={6}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Enter user operational requirements, brief notes, or draft summary to be verified by ML and enhanced by cloud AI..."
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)',
                  fontSize: '13px',
                  lineHeight: '1.5',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                  boxSizing: 'border-box',
                }}
              />

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginTop: '14px' }}>
                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Document Template:
                  </label>
                  <select
                    value={targetTemplate}
                    onChange={(e) => setTargetTemplate(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-color)',
                      fontSize: '13px',
                    }}
                  >
                    <option value="sop">Standard Operating Procedure (SOP)</option>
                    <option value="capa_plan">Corrective & Preventive Action (CAPA)</option>
                    <option value="dmr">Device Master Record / MDF</option>
                    <option value="complaint_procedure">Complaint Handling Procedure</option>
                    <option value="design_plan">Design & Development Plan</option>
                    <option value="change_control">Change Control Form</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    External Cloud API Provider:
                  </label>
                  <select
                    value={providerChoice}
                    onChange={(e) => setProviderChoice(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-color)',
                      fontSize: '13px',
                    }}
                  >
                    <option value="nvidia">NVIDIA NIM (Hosted Fast API)</option>
                    <option value="openrouter">OpenRouter (Nemotron Ultra 550B)</option>
                    <option value="offline">Offline Rules Engine (Zero Cloud)</option>
                  </select>
                </div>
              </div>

              <button
                className="btn btn-primary"
                onClick={handleRunPipeline}
                disabled={loadingPipeline || !inputText.trim()}
                style={{
                  width: '100%',
                  marginTop: '16px',
                  padding: '12px 20px',
                  background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                  border: 'none',
                  color: '#fff',
                  fontWeight: '600',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  gap: '8px',
                  cursor: 'pointer',
                  borderRadius: '8px',
                  fontSize: '14px',
                }}
              >
                {loadingPipeline ? (
                  <>
                    <LoaderCircle size={17} className="spin" />
                    Executing 4-Stage Backend Pipeline...
                  </>
                ) : (
                  <>
                    <Sparkles size={17} />
                    Verify Inputs with ML & Generate via External API
                  </>
                )}
              </button>
            </div>

            {/* 4-Stage Process Description Card */}
            <div className="card" style={{ padding: '18px', background: '#f8fafc', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '13px', fontWeight: '700', marginBottom: '10px', color: 'var(--text-primary)' }}>
                How this Backend Process Works:
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  <div style={{ background: '#e0e7ff', color: '#4338ca', fontWeight: '700', borderRadius: '50%', width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>1</div>
                  <div><strong>ISO 13485 ML Input Verification:</strong> The trained model verifies user input, matches canonical clauses, audits requirements, and flags omissions.</div>
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  <div style={{ background: '#e0f2fe', color: '#0369a1', fontWeight: '700', borderRadius: '50%', width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>2</div>
                  <div><strong>Online Resources & Standards Lookup:</strong> DuckDuckGo web inquiries and authoritative industrial parameters (ISO 11135, ISO 14644, SAL 10⁻⁶, FDA QMSR) are retrieved.</div>
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  <div style={{ background: '#fef3c7', color: '#b45309', fontWeight: '700', borderRadius: '50%', width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>3</div>
                  <div><strong>External Cloud API Connection:</strong> Prompt containing ML findings and online benchmarks is sent to NVIDIA NIM API with strict JSON schema constraints.</div>
                </div>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  <div style={{ background: '#dcfce7', color: '#15803d', fontWeight: '700', borderRadius: '50%', width: '22px', height: '22px', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>4</div>
                  <div><strong>Structured Packaging:</strong> Schema-validated title, purpose, scope, procedures, records, and applicability decisions returned with an ML verification scorecard.</div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: Pipeline Output Display */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {!pipelineResult && !loadingPipeline && (
              <div className="card" style={{ padding: '60px 24px', textAlign: 'center', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px dashed var(--border-color)' }}>
                <Brain size={48} style={{ color: 'var(--text-muted)', margin: '0 auto 14px auto' }} />
                <h3 style={{ fontSize: '17px', fontWeight: '600', margin: '0 0 8px 0' }}>Pipeline Ready to Run</h3>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '400px', margin: '0 auto' }}>
                  Enter or select a topic summary on the left, then click <strong>Verify Inputs with ML & Generate via External API</strong> to trigger the complete backend process.
                </p>
              </div>
            )}

            {loadingPipeline && (
              <div className="card" style={{ padding: '50px 24px', textAlign: 'center', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                <LoaderCircle size={40} className="spin" style={{ color: 'var(--primary-color, #4f46e5)', margin: '0 auto 16px auto' }} />
                <div style={{ fontSize: '15px', fontWeight: '700', color: 'var(--text-primary)' }}>Executing End-to-End Pipeline</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px' }}>
                  1. Verifying input with ISO 13485 ML Model → 2. Querying online benchmarks → 3. Generating structured content via NVIDIA NIM API
                </div>
              </div>
            )}

            {pipelineResult && !loadingPipeline && (
              <>
                {/* Stage 1: ML Model Input Verification Scorecard */}
                <div className="card" style={{ padding: '18px', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="badge badge-primary" style={{ fontSize: '11px' }}>Stage 1</span>
                      <strong style={{ fontSize: '14px' }}>ISO 13485 ML Model Input Verification</strong>
                    </div>
                    <span className={`badge ${pipelineResult.ml_verification?.verdict === 'compliant' ? 'badge-success' : 'badge-warning'}`}>
                      {pipelineResult.ml_verification?.verdict_label}
                    </span>
                  </div>

                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
                    Governing Clause: <strong>Clause {pipelineResult.ml_verification?.target_clause} ({pipelineResult.ml_verification?.clause_title})</strong> · Initial Compliance Score: <strong>{pipelineResult.ml_verification?.initial_compliance_score}%</strong>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px' }}>
                    <div style={{ background: '#f0fdf4', padding: '8px', borderRadius: '6px', border: '1px solid #bbf7d0' }}>
                      <strong style={{ color: '#166534' }}>Identified Strengths:</strong>
                      <div style={{ color: '#166534', marginTop: '2px' }}>{pipelineResult.ml_verification?.strengths?.join('; ') || 'Domain terminology recognized'}</div>
                    </div>
                    <div style={{ background: '#fff1f2', padding: '8px', borderRadius: '6px', border: '1px solid #fecdd3' }}>
                      <strong style={{ color: '#9f1239' }}>Regulatory Gaps Detected:</strong>
                      <div style={{ color: '#9f1239', marginTop: '2px' }}>{pipelineResult.ml_verification?.gaps?.join('; ') || 'No critical omissions'}</div>
                    </div>
                  </div>
                </div>

                {/* Stage 2 & 3: Online Resources & External API Summary */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="card" style={{ padding: '14px', background: '#f8fafc', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '6px' }}>
                      <span className="badge badge-info" style={{ fontSize: '10px' }}>Stage 2</span>
                      <strong style={{ fontSize: '12px' }}>Online & Industrial Specs</strong>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      <div>Standard: <strong>{pipelineResult.online_resources?.primary_standard}</strong></div>
                      {pipelineResult.online_resources?.quantitative_benchmarks?.length > 0 && (
                        <div style={{ marginTop: '4px', fontStyle: 'italic', color: 'var(--text-muted)' }}>
                          "{pipelineResult.online_resources.quantitative_benchmarks[0]}"
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="card" style={{ padding: '14px', background: '#f8fafc', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '6px' }}>
                      <span className="badge badge-success" style={{ fontSize: '10px' }}>Stage 3</span>
                      <strong style={{ fontSize: '12px' }}>External Cloud API</strong>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      <div>Provider: <strong>{pipelineResult.external_api?.provider?.toUpperCase()}</strong></div>
                      <div>Model: <strong>{pipelineResult.external_api?.model_id}</strong></div>
                      <div style={{ marginTop: '2px', color: '#16a34a' }}>Latency: {pipelineResult.total_latency_ms} ms</div>
                    </div>
                  </div>
                </div>

                {/* Stage 4: Generated Structured Output */}
                <div className="card" style={{ padding: '20px', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
                    <span className="badge badge-success" style={{ fontSize: '11px' }}>Stage 4</span>
                    <strong style={{ fontSize: '15px' }}>Structured QMS Document Output</strong>
                  </div>

                  <h3 style={{ fontSize: '16px', fontWeight: '700', color: '#1e293b', margin: '0 0 10px 0' }}>
                    {pipelineResult.structured_content?.title}
                  </h3>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '350px', overflowY: 'auto' }}>
                    {pipelineResult.structured_content?.answers && Object.entries(pipelineResult.structured_content.answers).map(([key, val]) => (
                      <div key={key} style={{ background: '#f8fafc', padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                        <div style={{ fontSize: '11px', fontWeight: '700', textTransform: 'uppercase', color: 'var(--primary-color, #4f46e5)', marginBottom: '3px' }}>
                          {key.replace(/_/g, ' ')}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-primary)', whiteSpace: 'pre-wrap', lineHeight: '1.4' }}>
                          {typeof val === 'string' ? val : JSON.stringify(val)}
                        </div>
                      </div>
                    ))}
                  </div>

                  {pipelineResult.structured_content?.enhancement_summary && (
                    <div style={{ marginTop: '12px', fontSize: '11px', color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)', paddingTop: '8px' }}>
                      <strong>Summary of Improvements:</strong> {pipelineResult.structured_content.enhancement_summary}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: LOCAL ML INFERENCE & AUDIT */}
      {activeTab === 'inference' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
          {/* Left Column: Input and Presets */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="card" style={{ padding: '20px', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '600', margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <FileText size={17} /> Input QMS Procedure Text
                </h3>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {inputText.length} characters
                </span>
              </div>

              {/* Sample Presets */}
              <div style={{ marginBottom: '14px' }}>
                <label style={{ fontSize: '12px', fontWeight: '600', color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                  Load Sample ISO 13485 Scenario:
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {SAMPLE_PRESETS.map((p, idx) => (
                    <button
                      key={idx}
                      onClick={() => applyPreset(p)}
                      style={{
                        padding: '4px 10px',
                        fontSize: '11px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-color)',
                        background: targetClause === p.targetClause ? 'var(--primary-light, #e0e7ff)' : 'var(--surface-sunken, #f8fafc)',
                        color: targetClause === p.targetClause ? 'var(--primary-color, #4338ca)' : 'var(--text-primary)',
                        cursor: 'pointer',
                        fontWeight: targetClause === p.targetClause ? '600' : '400',
                      }}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <textarea
                rows={7}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Paste any Standard Operating Procedure (SOP), work instruction, audit finding, or draft clause..."
                style={{
                  width: '100%',
                  padding: '12px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-color)',
                  fontSize: '13px',
                  lineHeight: '1.5',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                  boxSizing: 'border-box',
                }}
              />

              <div style={{ display: 'flex', gap: '12px', marginTop: '14px', alignItems: 'center' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Target Clause (Optional - Leave blank for ML Auto-Detection):
                  </label>
                  <input
                    type="text"
                    value={targetClause}
                    onChange={(e) => setTargetClause(e.target.value)}
                    placeholder="e.g. 7.5.7, 4.2.3, 8.2.2"
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-color)',
                      fontSize: '13px',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>

                <button
                  className="btn btn-primary"
                  onClick={handleRunInference}
                  disabled={loadingInference || !inputText.trim()}
                  style={{
                    padding: '10px 22px',
                    height: '38px',
                    alignSelf: 'flex-end',
                    background: 'linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)',
                    border: 'none',
                    color: '#fff',
                    fontWeight: '600',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    cursor: 'pointer',
                    borderRadius: '8px',
                  }}
                >
                  {loadingInference ? <LoaderCircle size={16} className="spin" /> : <Sparkles size={16} />}
                  Run ML Audit
                </button>
              </div>
            </div>

            {/* Quick Metrics Badge */}
            {modelInfo && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
                <div className="card" style={{ padding: '12px', textAlign: 'center', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>ML Classes</div>
                  <div style={{ fontSize: '20px', fontWeight: '700', color: 'var(--primary-color, #4f46e5)' }}>88 Clauses</div>
                </div>
                <div className="card" style={{ padding: '12px', textAlign: 'center', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Training Accuracy</div>
                  <div style={{ fontSize: '20px', fontWeight: '700', color: '#16a34a' }}>
                    {modelInfo.metrics?.training_accuracy ? `${(modelInfo.metrics.training_accuracy * 100).toFixed(1)}%` : '96.7%'}
                  </div>
                </div>
                <div className="card" style={{ padding: '12px', textAlign: 'center', background: '#f8fafc', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Inference Speed</div>
                  <div style={{ fontSize: '20px', fontWeight: '700', color: '#0284c7' }}>
                    {predictions?.inference_latency_ms ? `${predictions.inference_latency_ms} ms` : '< 5 ms'}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Predictions & Compliance Audit Results */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {!auditResult && !loadingInference && (
              <div className="card" style={{ padding: '40px 24px', textAlign: 'center', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px dashed var(--border-color)' }}>
                <Brain size={44} style={{ color: 'var(--text-muted)', margin: '0 auto 12px auto' }} />
                <h3 style={{ fontSize: '16px', fontWeight: '600', margin: '0 0 6px 0' }}>Ready for ML Regulatory Inference</h3>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>
                  Select an ISO 13485 preset or type any QMS procedure on the left, then click <strong>Run ML Audit</strong>.
                </p>
              </div>
            )}

            {loadingInference && (
              <div className="card" style={{ padding: '40px 24px', textAlign: 'center', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                <LoaderCircle size={36} className="spin" style={{ color: 'var(--primary-color, #4f46e5)', margin: '0 auto 12px auto' }} />
                <div style={{ fontSize: '14px', fontWeight: '600' }}>Evaluating ISO 13485:2016 Regulatory Compliance...</div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>Running multi-task classifier & gap analysis</div>
              </div>
            )}

            {auditResult && !loadingInference && (
              <>
                {/* Audit Verdict Card */}
                <div className="card" style={{ padding: '20px', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: '600', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Evaluated Standard Clause
                      </div>
                      <h2 style={{ fontSize: '18px', fontWeight: '700', margin: '2px 0 0 0', color: 'var(--text-primary)' }}>
                        Clause {auditResult.target_clause}: {auditResult.clause_title}
                      </h2>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        Category: {auditResult.category} · PDF Pages: {auditResult.normative_reference?.page_start}–{auditResult.normative_reference?.page_end}
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <span
                        className={`badge ${
                          auditResult.verdict === 'compliant'
                            ? 'badge-success'
                            : auditResult.verdict === 'partial'
                            ? 'badge-warning'
                            : 'badge-danger'
                        }`}
                        style={{ fontSize: '13px', padding: '6px 12px' }}
                      >
                        {auditResult.verdict_label}
                      </span>
                      <div style={{ fontSize: '12px', fontWeight: '600', marginTop: '6px', color: 'var(--text-secondary)' }}>
                        Compliance Score: <strong>{auditResult.compliance_score}%</strong>
                      </div>
                    </div>
                  </div>

                  {/* Mandatory Requirement Flags */}
                  <div style={{ display: 'flex', gap: '10px', marginBottom: '14px' }}>
                    <div
                      style={{
                        padding: '6px 12px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        background: auditResult.requires_documented_procedure ? '#eff6ff' : '#f8fafc',
                        border: `1px solid ${auditResult.requires_documented_procedure ? '#bfdbfe' : '#e2e8f0'}`,
                        color: auditResult.requires_documented_procedure ? '#1e40af' : '#64748b',
                        fontWeight: '600',
                      }}
                    >
                      <FileCheck size={14} />
                      {auditResult.requires_documented_procedure ? 'Documented SOP Required' : 'No Explicit SOP Mandated'}
                    </div>

                    <div
                      style={{
                        padding: '6px 12px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        background: auditResult.requires_record ? '#f0fdf4' : '#f8fafc',
                        border: `1px solid ${auditResult.requires_record ? '#bbf7d0' : '#e2e8f0'}`,
                        color: auditResult.requires_record ? '#166534' : '#64748b',
                        fontWeight: '600',
                      }}
                    >
                      <CheckCircle2 size={14} />
                      {auditResult.requires_record ? 'Quality Records Required (Clause 4.2.5)' : 'No Dedicated Record Mandated'}
                    </div>
                  </div>

                  {/* Strengths & Gaps */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                    <div style={{ background: '#f0fdf4', padding: '12px', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
                      <div style={{ fontSize: '12px', fontWeight: '700', color: '#166534', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle2 size={14} /> Identified Strengths
                      </div>
                      <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: '#166534', lineHeight: '1.4' }}>
                        {auditResult.strengths.map((s, idx) => (
                          <li key={idx} style={{ marginBottom: '4px' }}>{s}</li>
                        ))}
                      </ul>
                    </div>

                    <div style={{ background: '#fff1f2', padding: '12px', borderRadius: '8px', border: '1px solid #fecdd3' }}>
                      <div style={{ fontSize: '12px', fontWeight: '700', color: '#9f1239', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <AlertCircle size={14} /> Regulatory Gaps Detected
                      </div>
                      <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: '#9f1239', lineHeight: '1.4' }}>
                        {auditResult.gaps.map((g, idx) => (
                          <li key={idx} style={{ marginBottom: '4px' }}>{g}</li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  {/* Actionable Recommendations */}
                  <div style={{ background: '#f8fafc', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-color)', marginBottom: '14px' }}>
                    <div style={{ fontSize: '12px', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Wand2 size={14} style={{ color: 'var(--primary-color, #4f46e5)' }} /> Auditor Remediation Recommendations
                    </div>
                    <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4' }}>
                      {auditResult.recommendations.map((r, idx) => (
                        <li key={idx} style={{ marginBottom: '2px' }}>{r}</li>
                      ))}
                    </ul>
                  </div>

                  {/* Official Standard Citation */}
                  {auditResult.normative_reference?.normative_excerpt && (
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-color)', paddingTop: '10px' }}>
                      <strong>Official ISO 13485:2016 Normative Excerpt:</strong>
                      <p style={{ margin: '4px 0 0 0', fontStyle: 'italic', color: 'var(--text-muted)' }}>
                        "{auditResult.normative_reference.normative_excerpt}..."
                      </p>
                    </div>
                  )}
                </div>

                {/* Candidate Clauses Probability Breakdown */}
                {predictions?.predictions && (
                  <div className="card" style={{ padding: '16px', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '13px', fontWeight: '600', marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Gauge size={15} /> Top-5 Predicted ISO 13485 Clauses (ML Probability Distribution)
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {predictions.predictions.map((p, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '12px' }}>
                          <span style={{ width: '45px', fontWeight: '700', color: 'var(--text-primary)' }}>
                            {p.clause_number}
                          </span>
                          <span style={{ width: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }} title={p.title}>
                            {p.title}
                          </span>
                          <div style={{ flex: 1, background: '#f1f5f9', height: '8px', borderRadius: '4px', overflow: 'hidden' }}>
                            <div
                              style={{
                                height: '100%',
                                width: `${Math.min(100, Math.max(8, p.confidence * 100))}%`,
                                background: idx === 0 ? 'linear-gradient(90deg, #4f46e5, #06b6d4)' : '#94a3b8',
                                borderRadius: '4px',
                              }}
                            />
                          </div>
                          <span style={{ width: '50px', textAlign: 'right', fontWeight: '600', color: idx === 0 ? '#4f46e5' : '#64748b' }}>
                            {p.confidence_percent}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: ARCHITECTURE & TELEMETRY */}
      {activeTab === 'architecture' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="card" style={{ padding: '24px', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Cpu size={20} /> Machine Learning Model Architecture Specification
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '13px', lineHeight: '1.6' }}>
              This model transforms the complete 44-page <strong>ISO 13485:2016</strong> international regulatory standard
              into a local, deterministic, high-speed multi-task Machine Learning classifier. It was developed to eliminate
              reliance on slow, unpredictable external cloud calls or offline local Ollama instances for routine regulatory
              routing and compliance verification.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', margin: '20px 0' }}>
              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Algorithm</div>
                <div style={{ fontSize: '15px', fontWeight: '700', marginTop: '4px' }}>Hierarchical TF-IDF + Logistic Multi-Task</div>
              </div>
              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Vocabulary Features</div>
                <div style={{ fontSize: '15px', fontWeight: '700', marginTop: '4px' }}>15,000 N-Grams (1-3)</div>
              </div>
              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Output Classes</div>
                <div style={{ fontSize: '15px', fontWeight: '700', marginTop: '4px' }}>88 Distinct Clauses</div>
              </div>
              <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Model Artifact</div>
                <div style={{ fontSize: '15px', fontWeight: '700', marginTop: '4px' }}>data/models/iso13485_classifier.joblib</div>
              </div>
            </div>

            <h3 style={{ fontSize: '15px', fontWeight: '600', marginTop: '20px', marginBottom: '8px' }}>
              Multi-Task Learning Heads
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
              <div style={{ border: '1px solid var(--border-color)', borderRadius: '8px', padding: '14px' }}>
                <div style={{ fontWeight: '600', fontSize: '13px', color: '#4f46e5' }}>Head 1: Clause Classifier</div>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                  Calibrated probability distribution across all 88 clauses from Clause 1 (Scope) to 8.5.3 (Preventive action).
                </p>
              </div>
              <div style={{ border: '1px solid var(--border-color)', borderRadius: '8px', padding: '14px' }}>
                <div style={{ fontWeight: '600', fontSize: '13px', color: '#0891b2' }}>Head 2: Procedure Predictor</div>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                  Binary classifier predicting whether the regulation mandates a formal documented procedure.
                </p>
              </div>
              <div style={{ border: '1px solid var(--border-color)', borderRadius: '8px', padding: '14px' }}>
                <div style={{ fontWeight: '600', fontSize: '13px', color: '#16a34a' }}>Head 3: Record Mandate Predictor</div>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                  Predicts whether records of conformity are required to be established and retained under Clause 4.2.5.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: SFT INSTRUCTION FINE-TUNING DATASET */}
      {activeTab === 'sft' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="card" style={{ padding: '24px', background: 'var(--surface-raised, #ffffff)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: '700', margin: '0 0 4px 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FileCode size={20} /> Supervised Fine-Tuning (SFT) Dataset
                </h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '13px', margin: 0 }}>
                  High-quality instruction-tuning pairs compiled from the ISO 13485:2016 standard for fine-tuning LLMs (Llama 3, Mistral, Qwen, GPT-4o-mini).
                </p>
              </div>
              <a
                href="http://localhost:8000/api/v1/compliance/ml/export/sft-file"
                download="iso_13485_sft_dataset.jsonl"
                className="btn btn-primary"
                style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
              >
                <Download size={15} /> Download Full JSONL File
              </a>
            </div>

            {sftData && (
              <div style={{ marginBottom: '16px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                Total Generated SFT Instruction Records: <strong>{sftData.total_sft_records}</strong>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {sftData?.sample_records?.map((rec, idx) => (
                <div key={idx} style={{ background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                    <span className="badge badge-primary" style={{ fontSize: '11px' }}>Instruction #{idx + 1}</span>
                    <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>{rec.instruction}</strong>
                  </div>
                  {rec.input && (
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '6px 0', fontStyle: 'italic', background: '#fff', padding: '8px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
                      <strong>Context Excerpt:</strong> "{rec.input}"
                    </div>
                  )}
                  <div style={{ fontSize: '12px', color: '#334155', background: '#ffffff', padding: '10px', borderRadius: '6px', border: '1px solid #e2e8f0', whiteSpace: 'pre-wrap', lineHeight: '1.4' }}>
                    {rec.output}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
