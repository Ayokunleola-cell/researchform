// src/pages/analysis/index.tsx
import React, { useEffect, useState, useCallback } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import { useDropzone } from 'react-dropzone';
import { analysisApi, downloadBlob } from '../../lib/api';
import Link from 'next/link';
import { useRouter } from 'next/router';
import {
  Upload, BarChart3, Clock, CheckCircle, AlertCircle, Loader2,
  FileSpreadsheet, File, ArrowRight, Plus, RefreshCw
} from 'lucide-react';
import toast from 'react-hot-toast';
import clsx from 'clsx';

const STATUS_MAP: Record<string, { label: string; cls: string }> = {
  pending:       { label: 'Pending',         cls: 'badge-neutral' },
  decoding:      { label: 'Decoding',        cls: 'badge-brand' },
  decode_review: { label: 'Review Required', cls: 'badge-warning' },
  analysing:     { label: 'Analysing',       cls: 'badge-brand' },
  parsing:       { label: 'Parsing Brief',   cls: 'badge-brand' },
  selecting:     { label: 'Selecting Tests', cls: 'badge-brand' },
  generating:    { label: 'Generating Code', cls: 'badge-brand' },
  executing:     { label: 'Executing',       cls: 'badge-brand' },
  visualising:   { label: 'Visualising',     cls: 'badge-brand' },
  writing:       { label: 'Writing Report',  cls: 'badge-brand' },
  building:      { label: 'Building Doc',    cls: 'badge-brand' },
  complete:      { label: 'Complete',        cls: 'badge-success' },
  failed:        { label: 'Failed',          cls: 'badge-danger' },
};

function FileUploadZone({ onUpload }: { onUpload: (f: File) => void }) {
  const [dragActive, setDragActive] = useState(false);
  const onDrop = useCallback((files: File[]) => { if (files[0]) onUpload(files[0]); }, [onUpload]);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'text/csv': ['.csv'],
      'application/octet-stream': ['.sav'],
    },
    maxFiles: 1,
  });

  return (
    <div
      {...getRootProps()}
      className={clsx(
        'rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition-all',
        isDragActive ? 'drag-over' : ''
      )}
      style={{
        borderColor: isDragActive ? 'var(--brand)' : 'var(--border)',
        background: isDragActive ? 'rgba(99,102,241,0.05)' : 'var(--surface-2)',
      }}
    >
      <input {...getInputProps()} />
      <Upload size={40} className="mx-auto mb-4" style={{ color: isDragActive ? 'var(--brand)' : 'var(--text-3)' }} />
      <p className="font-display font-bold text-base mb-1" style={{ color: 'var(--text)' }}>
        {isDragActive ? 'Drop your file here' : 'Upload Data File'}
      </p>
      <p className="text-sm mb-4" style={{ color: 'var(--text-2)' }}>
        Drag & drop or click to browse
      </p>
      <div className="flex justify-center gap-2 flex-wrap">
        {['.xlsx', '.csv', '.sav', '.xls'].map(ext => (
          <span key={ext} className="badge badge-neutral font-mono text-xs">{ext}</span>
        ))}
      </div>
    </div>
  );
}

export default function AnalysisIndexPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [brief, setBrief] = useState({
    topic: '', objectives: [''], hypotheses: [''], study_type: 'quantitative',
    dependent_variable: '', independent_variable: '', population: '',
  });

  const fetchJobs = () => {
    analysisApi.listJobs().then(r => setJobs(r.data || [])).finally(() => setLoading(false));
  };

  useEffect(() => { fetchJobs(); }, []);

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('project_brief', JSON.stringify(brief));
      const res = await analysisApi.startFromFile(fd);
      toast.success('File uploaded — analysis starting!');
      router.push(`/analysis/${res.data.id}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <AppLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-display font-bold text-2xl" style={{ color: 'var(--text)' }}>Analysis Jobs</h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-2)' }}>9-stage AI-powered statistical analysis pipeline</p>
          </div>
          <div className="flex gap-2">
            <button className="btn btn-ghost btn-icon" onClick={fetchJobs} title="Refresh">
              <RefreshCw size={16} />
            </button>
            <button className="btn btn-primary" onClick={() => setShowUpload(!showUpload)}>
              <Plus size={16} />
              New Analysis
            </button>
          </div>
        </div>

        {/* Upload panel */}
        {showUpload && (
          <div className="card p-6 space-y-5 animate-slide-up">
            <h2 className="font-display font-semibold" style={{ color: 'var(--text)' }}>Upload File for Analysis</h2>

            {/* Brief fields */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Project Topic</label>
                <input className="input" placeholder="Full project title" value={brief.topic} onChange={e => setBrief(b => ({ ...b, topic: e.target.value }))} />
              </div>
              <div>
                <label className="label">Study Type</label>
                <select className="input" value={brief.study_type} onChange={e => setBrief(b => ({ ...b, study_type: e.target.value }))}>
                  {['quantitative', 'qualitative', 'mixed', 'descriptive', 'experimental', 'correlation'].map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="label">Dependent Variable</label>
                <input className="input" placeholder="e.g. Academic Performance" value={brief.dependent_variable} onChange={e => setBrief(b => ({ ...b, dependent_variable: e.target.value }))} />
              </div>
              <div>
                <label className="label">Independent Variable</label>
                <input className="input" placeholder="e.g. Social Media Usage" value={brief.independent_variable} onChange={e => setBrief(b => ({ ...b, independent_variable: e.target.value }))} />
              </div>
            </div>

            <div>
              <label className="label">Objective (main)</label>
              <input className="input" placeholder="To examine the relationship between..." value={brief.objectives[0]} onChange={e => setBrief(b => ({ ...b, objectives: [e.target.value, ...b.objectives.slice(1)] }))} />
            </div>

            <div>
              <label className="label">Hypothesis (H1)</label>
              <input className="input" placeholder="There is no significant relationship between..." value={brief.hypotheses[0]} onChange={e => setBrief(b => ({ ...b, hypotheses: [e.target.value, ...b.hypotheses.slice(1)] }))} />
            </div>

            {uploading ? (
              <div className="flex items-center justify-center py-10 gap-3">
                <Loader2 className="animate-spin" style={{ color: 'var(--brand)' }} />
                <span style={{ color: 'var(--text-2)' }}>Uploading and starting analysis...</span>
              </div>
            ) : (
              <FileUploadZone onUpload={handleFileUpload} />
            )}
          </div>
        )}

        {/* Jobs list */}
        {loading ? (
          <div className="space-y-3">
            {[1,2,3].map(i => <div key={i} className="skeleton h-20 rounded-2xl" />)}
          </div>
        ) : jobs.length === 0 && !showUpload ? (
          <div className="card p-16 text-center">
            <BarChart3 size={48} className="mx-auto mb-4" style={{ color: 'var(--text-3)' }} />
            <p className="font-display font-bold text-lg mb-2" style={{ color: 'var(--text)' }}>No analyses yet</p>
            <p className="text-sm mb-6" style={{ color: 'var(--text-2)' }}>
              Upload a data file (Excel, CSV, SPSS) or run analysis from a survey
            </p>
            <button className="btn btn-primary" onClick={() => setShowUpload(true)}>
              <Upload size={16} /> Upload Data File
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job: any) => {
              const status = STATUS_MAP[job.status] || STATUS_MAP.pending;
              const isRunning = !['complete', 'failed', 'decode_review'].includes(job.status);
              return (
                <Link key={job.id} href={`/analysis/${job.id}`}>
                  <div className="card p-5 card-hover flex items-center gap-4 cursor-pointer">
                    <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ background: 'rgba(99,102,241,0.1)' }}>
                      {job.source_type === 'excel' ? <FileSpreadsheet size={22} style={{ color: 'var(--brand)' }} /> :
                       <File size={22} style={{ color: 'var(--brand)' }} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <p className="font-semibold truncate" style={{ color: 'var(--text)' }}>
                          {job.survey_title || job.source_filename || 'Uploaded File Analysis'}
                        </p>
                        <span className={`badge ${status.cls} text-xs flex-shrink-0`}>
                          {isRunning && <Loader2 size={10} className="animate-spin mr-1" />}
                          {status.label}
                        </span>
                      </div>
                      <p className="text-xs" style={{ color: 'var(--text-3)' }}>
                        {job.n_rows ? `${job.n_rows} rows · ${job.n_columns} variables` : ''}
                        {job.created_at ? ` · ${new Date(job.created_at).toLocaleDateString()}` : ''}
                      </p>
                    </div>
                    <ArrowRight size={18} style={{ color: 'var(--text-3)' }} />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
