// src/components/analysis/DataTransformPanel.tsx
// Slide-in drawer for data transformations: recode, compute, bin, reverse score, standardize, dummy
import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../../lib/api';
import toast from 'react-hot-toast';
import {
  RiCloseFill, RiAddCircleLine, RiLoader4Line,
  RiDeleteBinFill, RiRefreshLine, RiCheckboxCircleFill, RiDatabase2Fill,
  RiArrowLeftRightFill, RiAddFill, RiArrowUpDownFill, RiBarChart2Fill,
  RiRuler2Fill, RiCodeBoxFill,
} from 'react-icons/ri';


// ─── Types ────────────────────────────────────────────────────────────────────

type OpType = 'recode' | 'compute' | 'reverse_score' | 'bin' | 'standardize' | 'dummy';

interface ColumnInfo {
  name: string; dtype: string; is_numeric: boolean;
  missing_n: number; unique_n: number; sample: string[];
}

interface Operation {
  id: string; type: OpType; column: string; new_column: string;
  map?: Record<string, string>;
  items?: string[]; agg?: 'mean' | 'sum' | 'min' | 'max';
  breaks?: string; labels?: string;
  method?: 'zscore' | 'minmax';
  reference?: string; scale_max?: number;
}

interface Props {
  jobId: string;
  onClose: () => void;
  onApplied: () => void;
}

const OP_LABELS: Record<OpType, string> = {
  recode:        'Recode Values',
  compute:       'Compute Variable',
  reverse_score: 'Reverse Score',
  bin:           'Visual Binning',
  standardize:   'Standardize',
  dummy:         'Dummy Coding',
};

const OP_ICONS: Record<OpType, React.ElementType> = {
  recode:        RiArrowLeftRightFill,
  compute:       RiAddFill,
  reverse_score: RiArrowUpDownFill,
  bin:           RiBarChart2Fill,
  standardize:   RiRuler2Fill,
  dummy:         RiCodeBoxFill,
};


const OP_DESCRIPTIONS: Record<OpType, string> = {
  recode:        'Map old values to new values (e.g. 1→5 for reverse Likert)',
  compute:       'Create new variable from mean/sum of selected items',
  reverse_score: 'Automatically invert Likert scale (scale_max + 1 − x)',
  bin:           'Convert continuous variable into categorical groups',
  standardize:   'Z-score or min-max normalise a numeric variable',
  dummy:         'Create dummy/indicator variables from a categorical column',
};

function uid() { return Math.random().toString(36).slice(2, 8); }

// ─── Main component ───────────────────────────────────────────────────────────

export default function DataTransformPanel({ jobId, onClose, onApplied }: Props) {
  const [columns, setColumns]       = useState<ColumnInfo[]>([]);
  const [ops, setOps]               = useState<Operation[]>([]);
  const [preview, setPreview]       = useState<Record<string, unknown>[] | null>(null);
  const [loading, setLoading]       = useState(false);
  const [applying, setApplying]     = useState(false);
  const [loadingCols, setLoadingCols] = useState(true);

  // Load columns on mount
  useEffect(() => {
    api.get(`/analysis/jobs/${jobId}/columns`)
      .then(r => setColumns(r.data.columns || []))
      .catch(() => toast.error('Could not load column info'))
      .finally(() => setLoadingCols(false));
  }, [jobId]);

  const addOp = (type: OpType) => {
    const col = columns[0]?.name || '';
    setOps(prev => [...prev, {
      id: uid(), type, column: col,
      new_column: col ? `${col}_${type}` : '',
      scale_max: 5, agg: 'mean', method: 'zscore',
    }]);
  };

  const updateOp = (id: string, patch: Partial<Operation>) => {
    setOps(prev => prev.map(o => o.id === id ? { ...o, ...patch } : o));
  };

  const removeOp = (id: string) => setOps(prev => prev.filter(o => o.id !== id));

  const buildPayload = (preview_only: boolean) => ({
    preview_only,
    operations: ops.map(op => {
      const base: Record<string, unknown> = { type: op.type, column: op.column, new_column: op.new_column };
      if (op.type === 'recode')        base.map = op.map || {};
      if (op.type === 'compute')       { base.items = op.items || []; base.agg = op.agg; }
      if (op.type === 'reverse_score') base.scale_max = op.scale_max;
      if (op.type === 'bin') {
        base.breaks = op.breaks ? op.breaks.split(',').map(Number) : [];
        base.labels  = op.labels ? op.labels.split(',').map(s => s.trim()) : undefined;
      }
      if (op.type === 'standardize') base.method = op.method;
      if (op.type === 'dummy')       base.reference = op.reference;
      return base;
    }),
  });

  const runPreview = useCallback(async () => {
    if (!ops.length) return;
    setLoading(true);
    try {
      const r = await api.post(`/analysis/jobs/${jobId}/transform`, buildPayload(true));
      setPreview(r.data.preview_rows || []);
    } catch {
      toast.error('Preview failed');
    } finally {
      setLoading(false);
    }
  }, [ops, jobId]);

  const applyAll = useCallback(async () => {
    if (!ops.length) return;
    setApplying(true);
    try {
      const r = await api.post(`/analysis/jobs/${jobId}/transform`, buildPayload(false));
      const applied = r.data.applied || [];
      const errors  = r.data.errors  || [];
      if (applied.length) toast.success(`${applied.length} transformation${applied.length>1?'s':''} applied successfully`);
      if (errors.length)  toast.error(errors[0]);
      if (applied.length) {
        setOps([]);
        setPreview(null);
        onApplied();
      }
    } catch {
      toast.error('Failed to apply transformations');
    } finally {
      setApplying(false);
    }
  }, [ops, jobId, onApplied]);

  const selectStyle: React.CSSProperties = {
    width: '100%', padding: '6px 10px', borderRadius: 8, fontSize: 12,
    border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text)',
    marginBottom: 8,
  };
  const inputStyle: React.CSSProperties = {
    ...selectStyle, marginBottom: 6,
  };

  return (
    <>
      {/* Overlay */}
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 500,
        backdropFilter: 'blur(2px)',
      }} />

      {/* Drawer */}
      <div style={{
        position: 'fixed', right: 0, top: 0, bottom: 0, width: 480, zIndex: 501,
        background: 'var(--surface)', borderLeft: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', boxShadow: '-8px 0 40px rgba(0,0,0,0.15)',
      }}>
        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid var(--border)',
          background: 'var(--surface-2)', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div className="flex items-center gap-2">
            <RiDatabase2Fill size={18} style={{ color: '#6366f1' }} />
            <p style={{ margin: 0, fontWeight: 800, fontSize: 15, color: 'var(--text)' }}>Data Transforms</p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)', padding: 4 }}>
            <RiCloseFill size={20} />
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>

          {/* Add operation buttons */}
          <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
            Add Transformation
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 20 }}>
            {(Object.keys(OP_LABELS) as OpType[]).map(op => {
              const Icon = OP_ICONS[op];
              return (
                <button key={op} onClick={() => addOp(op)}
                  style={{
                    padding: '8px 10px', borderRadius: 10, border: '1px dashed var(--border)',
                    background: 'var(--surface-2)', cursor: 'pointer', textAlign: 'left',
                    color: 'var(--text)', fontSize: 12, fontWeight: 600, transition: 'all 0.15s',
                  }}>
                  <p style={{ margin: '0 0 3px', display: 'flex', alignItems: 'center', gap: 5 }}>
                    <Icon size={13} color="#6366f1" />
                    {OP_LABELS[op]}
                  </p>
                  <p style={{ margin: 0, fontSize: 10, color: 'var(--text-3)', fontWeight: 400 }}>{OP_DESCRIPTIONS[op]}</p>
                </button>
              );
            })}
          </div>

          {/* Staged operations */}
          {ops.length === 0 && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>
              No transformations staged yet.<br />Click a button above to add one.
            </div>
          )}

          {ops.map((op, idx) => (
            <div key={op.id} style={{
              border: '1px solid var(--border)', borderRadius: 12, padding: 14, marginBottom: 12,
              background: 'var(--surface-2)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#6366f1', display: 'flex', alignItems: 'center', gap: 5 }}>
                  {React.createElement(OP_ICONS[op.type], { size: 13 })}
                  {OP_LABELS[op.type]}
                </span>

                <button onClick={() => removeOp(op.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-3)' }}>
                  <RiDeleteBinFill size={14} />
                </button>
              </div>

              {/* Column selector */}
              <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>Source Column</label>
              <select value={op.column} onChange={e => updateOp(op.id, { column: e.target.value, new_column: `${e.target.value}_${op.type}` })} style={selectStyle}>
                {loadingCols ? <option>Loading...</option> :
                  columns.filter(c => ['compute','dummy','recode','reverse_score','bin','standardize'].includes(op.type) ? true : c.is_numeric).map(c => (
                    <option key={c.name} value={c.name}>{c.name} ({c.dtype})</option>
                  ))}
              </select>

              {/* New column name */}
              {op.type !== 'dummy' && (
                <>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>New Column Name</label>
                  <input type="text" value={op.new_column}
                    onChange={e => updateOp(op.id, { new_column: e.target.value })}
                    style={inputStyle} placeholder="e.g. gpa_reversed" />
                </>
              )}

              {/* Operation-specific fields */}
              {op.type === 'recode' && (
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                    Value Mapping (one per line: old=new)
                  </label>
                  <textarea rows={5}
                    defaultValue={Object.entries(op.map || {}).map(([k,v]) => `${k}=${v}`).join('\n') || '1=5\n2=4\n3=3\n4=2\n5=1'}
                    onChange={e => {
                      const m: Record<string,string> = {};
                      e.target.value.split('\n').forEach(line => {
                        const [k,...rest] = line.split('=');
                        if (k && rest.length) m[k.trim()] = rest.join('=').trim();
                      });
                      updateOp(op.id, { map: m });
                    }}
                    style={{ ...inputStyle, height: 100, fontFamily: 'monospace', resize: 'vertical' }} />
                </div>
              )}

              {op.type === 'compute' && (
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600, display: 'block', marginBottom: 4 }}>
                    Items to Aggregate
                  </label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
                    {columns.filter(c => c.is_numeric).map(c => {
                      const sel = (op.items || []).includes(c.name);
                      return (
                        <button key={c.name} onClick={() => {
                          const cur = op.items || [];
                          updateOp(op.id, { items: sel ? cur.filter(x => x !== c.name) : [...cur, c.name] });
                        }}
                          style={{
                            padding: '3px 10px', borderRadius: 20, fontSize: 11, cursor: 'pointer',
                            border: `1px solid ${sel ? '#6366f1' : 'var(--border)'}`,
                            background: sel ? 'rgba(99,102,241,0.1)' : 'transparent',
                            color: sel ? '#6366f1' : 'var(--text-3)', fontWeight: 600,
                          }}>
                          {c.name}
                        </button>
                      );
                    })}
                  </div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>Aggregation</label>
                  <select value={op.agg} onChange={e => updateOp(op.id, { agg: e.target.value as any })} style={selectStyle}>
                    <option value="mean">Mean (average)</option>
                    <option value="sum">Sum (total)</option>
                    <option value="min">Minimum</option>
                    <option value="max">Maximum</option>
                  </select>
                </div>
              )}

              {op.type === 'reverse_score' && (
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>Scale Maximum</label>
                  <select value={op.scale_max} onChange={e => updateOp(op.id, { scale_max: parseInt(e.target.value) })} style={selectStyle}>
                    {[4,5,6,7,8,9,10].map(n => <option key={n} value={n}>{n} (e.g. 1-{n} Likert)</option>)}
                  </select>
                  <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '4px 0 0' }}>
                    Formula: {op.scale_max} + 1 − original value
                  </p>
                </div>
              )}

              {op.type === 'bin' && (
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>Cut Points (comma-separated)</label>
                  <input type="text" value={op.breaks || ''} placeholder="e.g. 18,25,35,45,65"
                    onChange={e => updateOp(op.id, { breaks: e.target.value })} style={inputStyle} />
                  <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>Labels (optional, comma-separated)</label>
                  <input type="text" value={op.labels || ''} placeholder="e.g. Young,Adult,Middle,Senior"
                    onChange={e => updateOp(op.id, { labels: e.target.value })} style={inputStyle} />
                </div>
              )}

              {op.type === 'standardize' && (
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>Method</label>
                  <select value={op.method} onChange={e => updateOp(op.id, { method: e.target.value as any })} style={selectStyle}>
                    <option value="zscore">Z-score (mean=0, SD=1)</option>
                    <option value="minmax">Min-Max (0 to 1)</option>
                  </select>
                </div>
              )}

              {op.type === 'dummy' && (
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-3)', fontWeight: 600 }}>Reference Category (dropped)</label>
                  <input type="text" value={op.reference || ''} placeholder="e.g. Male"
                    onChange={e => updateOp(op.id, { reference: e.target.value })} style={inputStyle} />
                  <p style={{ fontSize: 11, color: 'var(--text-3)', margin: '2px 0 0' }}>
                    {columns.find(c => c.name === op.column)?.sample.slice(0,4).join(', ')}
                  </p>
                </div>
              )}
            </div>
          ))}

          {/* Preview rows */}
          {preview && (
            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
                Preview (first 5 rows)
              </p>
              <div style={{ overflowX: 'auto', fontSize: 11 }}>
                <table style={{ borderCollapse: 'collapse', width: '100%', minWidth: 300 }}>
                  <thead>
                    <tr>
                      {Object.keys(preview[0] || {}).slice(0, 8).map(k => (
                        <th key={k} style={{ padding: '4px 8px', fontWeight: 700, color: 'var(--text-2)', borderBottom: '1px solid var(--border)', textAlign: 'left', whiteSpace: 'nowrap' }}>{k}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.map((row, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                        {Object.values(row).slice(0, 8).map((v, j) => (
                          <td key={j} style={{ padding: '4px 8px', color: 'var(--text)', whiteSpace: 'nowrap' }}>
                            {String(v ?? '—')}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        {ops.length > 0 && (
          <div style={{
            padding: '14px 16px', borderTop: '1px solid var(--border)',
            background: 'var(--surface-2)', display: 'flex', gap: 8,
          }}>
            <button onClick={runPreview} disabled={loading}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 10, border: '1px solid var(--border)',
                background: 'var(--surface)', color: 'var(--text)', fontWeight: 600, fontSize: 13,
                cursor: loading ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}>
              {loading ? <RiLoader4Line className="animate-spin" size={14} /> : <RiRefreshLine size={14} />}
              Preview
            </button>
            <button onClick={applyAll} disabled={applying}
              style={{
                flex: 2, padding: '10px 0', borderRadius: 10, border: 'none',
                background: 'linear-gradient(135deg,#6366f1,#8b5cf6)', color: '#fff',
                fontWeight: 700, fontSize: 13, cursor: applying ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}>
              {applying ? <RiLoader4Line className="animate-spin" size={14} /> : <RiCheckboxCircleFill size={14} />}
              {applying ? 'Applying...' : `Apply ${ops.length} Transform${ops.length>1?'s':''} & Save`}
            </button>
          </div>
        )}
      </div>
    </>
  );
}
