// src/pages/surveys/new.tsx
import React, { useState, useEffect, useCallback } from 'react';
import AppLayout from '../../components/layout/AppLayout';
import SurveySettings from '../../components/surveys/SurveySettings';
import { useRouter } from 'next/router';
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors,
  DragEndEvent
} from '@dnd-kit/core';
import {
  SortableContext, verticalListSortingStrategy, useSortable,
  arrayMove
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  RiArrowUpSFill, RiSendPlaneFill, RiHeading, RiDraggable, RiCloseFill,
  RiFileCopyFill, RiHashtag, RiStarFill, RiLoader4Line, RiTableFill,
  RiEyeFill, RiArrowLeftFill, RiAlignLeft, RiFontSize, RiEqualizerFill,
  RiAddFill, RiArrowDownSFill, RiSave3Fill, RiDeleteBinFill, RiCheckboxFill,
  RiListUnordered, RiCalendarEventFill, RiText, RiSortAsc, RiPieChartFill,
  RiEqualizerLine, RiEmotionLine, RiArrowDownSLine, RiShuffleLine,
  RiInformationLine, RiShieldCheckLine, RiGitBranchLine, RiFileUploadLine,
  RiContrastLine, RiSearchLine, RiAlertLine, RiSettings3Line,
} from 'react-icons/ri';
import { surveysApi, questionsApi } from '../../lib/api';
import toast from 'react-hot-toast';
import clsx from 'clsx';

// ─── Input sanitiser: strips control chars, normalises unicode ────────────────
const CTRL_CHARS = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]/g;
const sanitiseText = (val: string, maxLen = 500): string =>
  String(val ?? '')
    .replace(CTRL_CHARS, '')       // remove invisible control characters
    .normalize('NFC')              // normalise unicode (avoids mojibake on save)
    .replace(/\s{2,}/g, ' ')      // collapse double spaces
    .trim()
    .slice(0, maxLen);

const sanitiseOption = (val: string) => sanitiseText(val, 200);
const sanitiseVarName = (val: string) =>
  sanitiseText(val, 64)
    .replace(/[^a-zA-Z0-9_]/g, '_') // variable names: only safe chars
    .replace(/^([0-9])/, '_$1');     // must not start with digit

const QUESTION_TYPES = [
  { type: 'short_text',            icon: RiFontSize,          label: 'Short Text',          level: 'nominal',  group: 'Text' },
  { type: 'long_text',             icon: RiAlignLeft,         label: 'Long Text',           level: 'nominal',  group: 'Text' },
  { type: 'single_choice',         icon: RiListUnordered,     label: 'Single Choice',       level: 'nominal',  group: 'Choice' },
  { type: 'multi_choice',          icon: RiCheckboxFill,      label: 'Multi Choice',        level: 'nominal',  group: 'Choice' },
  { type: 'dropdown',              icon: RiArrowDownSLine,    label: 'Dropdown',            level: 'nominal',  group: 'Choice' },
  { type: 'rank_order',            icon: RiSortAsc,           label: 'Rank Order',          level: 'ordinal',  group: 'Scale' },
  { type: 'likert',                icon: RiEqualizerFill,     label: 'Likert Scale',        level: 'ordinal',  group: 'Scale' },
  { type: 'semantic_differential', icon: RiContrastLine,      label: 'Semantic Differential', level: 'interval', group: 'Scale' },
  { type: 'rating',                icon: RiStarFill,          label: 'Rating',              level: 'ordinal',  group: 'Scale' },
  { type: 'nps',                   icon: RiEmotionLine,       label: 'NPS (0–10)',          level: 'ordinal',  group: 'Scale' },
  { type: 'matrix',                icon: RiTableFill,         label: 'Matrix',              level: 'ordinal',  group: 'Scale' },
  { type: 'slider',                icon: RiEqualizerLine,     label: 'Continuous Slider',   level: 'ratio',    group: 'Number' },
  { type: 'constant_sum',          icon: RiPieChartFill,      label: 'Constant Sum',        level: 'ratio',    group: 'Number' },
  { type: 'number',                icon: RiHashtag,           label: 'Number',              level: 'ratio',    group: 'Number' },
  { type: 'date',                  icon: RiCalendarEventFill, label: 'Date',                level: 'interval', group: 'Other' },
  { type: 'file_upload',           icon: RiFileUploadLine,    label: 'File Upload',         level: null,       group: 'Other' },
  { type: 'section_header',        icon: RiHeading,           label: 'Section Header',      level: null,       group: 'Other' },
];

const LIKERT_DEFAULTS = ['Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'];

const CHOICE_TYPES = ['single_choice', 'multi_choice', 'dropdown', 'rank_order'];
const VALIDATION_PRESET_PATTERNS: Record<string, { label: string; regex: string; placeholder: string }> = {
  email:      { label: 'Email',      regex: '^[^@]+@[^@]+\\.[^@]+$',        placeholder: 'e.g. user@example.com' },
  phone:      { label: 'Phone',      regex: '^[+]?[0-9\\s\\-()]{7,20}$',    placeholder: 'e.g. +234 801 234 5678' },
  url:        { label: 'URL',        regex: '^https?://.+',                  placeholder: 'e.g. https://...' },
  student_id: { label: 'Student ID', regex: '^[A-Za-z0-9/\\-]{4,20}$',     placeholder: 'e.g. CSC/2020/001' },
};

function makeQuestion(type: string, position: number) {
  let defaultOptions: string[] = [];
  if (type === 'likert') defaultOptions = LIKERT_DEFAULTS;
  else if (CHOICE_TYPES.includes(type) || type === 'constant_sum') {
    defaultOptions = type === 'constant_sum' ? ['Category A', 'Category B', 'Category C']
      : type === 'rank_order' ? ['First Choice', 'Second Choice', 'Third Choice']
      : ['Option 1', 'Option 2'];
  } else if (type === 'slider') {
    defaultOptions = ['Minimum', 'Maximum'];
  } else if (type === 'nps') {
    defaultOptions = ['Not at all likely', 'Extremely likely'];
  } else if (type === 'semantic_differential') {
    defaultOptions = ['Negative Pole', 'Positive Pole'];
  }

  return {
    id: `q_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    type,
    text: '',
    required: type !== 'section_header',
    options: defaultOptions,
    scale_min: type === 'slider' ? 0 : type === 'nps' ? 0 : type === 'semantic_differential' ? 1 : 1,
    scale_max: type === 'slider' ? 100 : type === 'nps' ? 10 : type === 'constant_sum' ? 100
      : type === 'semantic_differential' ? 7 : 5,
    position,
    variable_name: '',
    measurement_level: QUESTION_TYPES.find(t => t.type === type)?.level || 'nominal',
    rows: type === 'matrix' ? ['Row 1', 'Row 2'] : [],
    columns: type === 'matrix' ? ['Column 1', 'Column 2'] : [],
    helper_text: '',
    randomize_options: false,
    validation_rules: {} as Record<string, any>,
    logic_rules: [] as any[],
    is_attention_check: false,
    correct_answer: null as any,
    _new: true,
  };
}

// ─── Validation Rules Panel ───────────────────────────────────────────────────
function ValidationPanel({ question, onUpdate }: { question: any; onUpdate: (id: string, patch: any) => void }) {
  const vr = question.validation_rules || {};
  const set = (key: string, val: any) => {
    onUpdate(question.id, { validation_rules: { ...vr, [key]: val } });
  };

  if (['short_text', 'long_text'].includes(question.type)) {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Min Characters</label>
            <input type="number" className="input" min={0} value={vr.min_length ?? ''} onChange={e => set('min_length', e.target.value ? +e.target.value : undefined)} placeholder="0" />
          </div>
          <div>
            <label className="label">Max Characters</label>
            <input type="number" className="input" min={0} value={vr.max_length ?? ''} onChange={e => set('max_length', e.target.value ? +e.target.value : undefined)} placeholder="e.g. 500" />
          </div>
        </div>
        <div>
          <label className="label">Format Preset</label>
          <select className="input" value={vr.preset || ''} onChange={e => {
            const p = e.target.value;
            if (p && VALIDATION_PRESET_PATTERNS[p]) {
              onUpdate(question.id, { validation_rules: { ...vr, preset: p, regex: VALIDATION_PRESET_PATTERNS[p].regex } });
            } else {
              const nr = { ...vr }; delete nr.preset; delete nr.regex;
              onUpdate(question.id, { validation_rules: nr });
            }
          }}>
            <option value="">None</option>
            {Object.entries(VALIDATION_PRESET_PATTERNS).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
            <option value="custom">Custom Regex</option>
          </select>
        </div>
        {(vr.preset === 'custom' || (!vr.preset && vr.regex)) && (
          <div>
            <label className="label">Custom Regex Pattern</label>
            <input className="input font-mono text-sm" placeholder="^[A-Za-z0-9]+$" value={vr.regex || ''} onChange={e => set('regex', e.target.value)} />
          </div>
        )}
      </div>
    );
  }

  if (question.type === 'number') {
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Min Value</label>
            <input type="number" className="input" value={vr.min_val ?? ''} onChange={e => set('min_val', e.target.value !== '' ? +e.target.value : undefined)} />
          </div>
          <div>
            <label className="label">Max Value</label>
            <input type="number" className="input" value={vr.max_val ?? ''} onChange={e => set('max_val', e.target.value !== '' ? +e.target.value : undefined)} />
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer">
          <input type="checkbox" checked={!!vr.integer_only} onChange={e => set('integer_only', e.target.checked)} className="w-4 h-4 accent-[var(--brand)]" />
          <span className="text-sm" style={{ color: 'var(--text-2)' }}>Whole numbers only</span>
        </label>
      </div>
    );
  }

  return <p className="text-sm" style={{ color: 'var(--text-3)' }}>No validation rules available for this question type.</p>;
}

// ─── Skip Logic Panel ─────────────────────────────────────────────────────────
function LogicPanel({ question, allQuestions, onUpdate }: { question: any; allQuestions: any[]; onUpdate: (id: string, patch: any) => void }) {
  const rules: any[] = question.logic_rules || [];
  const priorQs = allQuestions.filter(q => q.id !== question.id && q.position < question.position && q.type !== 'section_header');

  const addRule = () => {
    if (priorQs.length === 0) return;
    onUpdate(question.id, {
      logic_rules: [...rules, { condition_q_id: priorQs[0].id, operator: 'equals', value: '', action: 'show' }]
    });
  };

  const updateRule = (i: number, patch: any) => {
    const updated = rules.map((r, idx) => idx === i ? { ...r, ...patch } : r);
    onUpdate(question.id, { logic_rules: updated });
  };

  const deleteRule = (i: number) => {
    onUpdate(question.id, { logic_rules: rules.filter((_, idx) => idx !== i) });
  };

  if (priorQs.length === 0) {
    return <p className="text-sm" style={{ color: 'var(--text-3)' }}>Add more questions above this one to create logic rules.</p>;
  }

  return (
    <div className="space-y-3">
      <p className="text-xs" style={{ color: 'var(--text-3)' }}>
        Rules control when this question is shown. Without rules, it is always visible.
      </p>
      {rules.map((rule, i) => {
        const condQ = allQuestions.find(q => q.id === rule.condition_q_id);
        const hasOptions = condQ && ['single_choice', 'multi_choice', 'dropdown', 'likert', 'rating', 'nps'].includes(condQ.type);
        return (
          <div key={i} className="p-3 rounded-xl space-y-2" style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold" style={{ color: 'var(--text-3)' }}>IF</span>
              <select className="input input-sm flex-1 min-w-0" value={rule.condition_q_id} onChange={e => updateRule(i, { condition_q_id: e.target.value, value: '' })}>
                {priorQs.map((q, qi) => (
                  <option key={q.id} value={q.id}>Q{qi + 1}: {q.text?.slice(0, 40) || `(untitled)`}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <select className="input input-sm" value={rule.operator} onChange={e => updateRule(i, { operator: e.target.value })}>
                <option value="equals">equals</option>
                <option value="not_equals">does not equal</option>
                <option value="contains">contains</option>
                <option value="greater_than">is greater than</option>
                <option value="less_than">is less than</option>
              </select>
              {hasOptions && condQ?.options?.length ? (
                <select className="input input-sm flex-1" value={rule.value} onChange={e => updateRule(i, { value: e.target.value })}>
                  <option value="">— select value —</option>
                  {condQ.options.map((opt: string) => <option key={opt} value={opt}>{opt}</option>)}
                </select>
              ) : (
                <input className="input input-sm flex-1" placeholder="value" value={rule.value} onChange={e => updateRule(i, { value: e.target.value })} />
              )}
            </div>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold" style={{ color: 'var(--text-3)' }}>THEN</span>
                <select className="input input-sm" value={rule.action} onChange={e => updateRule(i, { action: e.target.value })}>
                  <option value="show">Show this question</option>
                  <option value="hide">Hide this question</option>
                </select>
              </div>
              <button className="btn btn-ghost btn-icon btn-sm" onClick={() => deleteRule(i)} style={{ color: 'var(--danger)' }}>
                <RiCloseFill size={14} />
              </button>
            </div>
          </div>
        );
      })}
      <button className="btn btn-ghost btn-sm" onClick={addRule}>
        <RiAddFill size={14} /> Add Rule
      </button>
    </div>
  );
}

// ─── Sortable Question Card ───────────────────────────────────────────────────
function QuestionCard({ question, allQuestions, onUpdate, onDelete, onDuplicate, index }: any) {
  const [expanded, setExpanded] = useState(question._new);
  const [activeTab, setActiveTab] = useState<'content' | 'logic' | 'validation' | 'advanced'>('content');
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: question.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const typeInfo = QUESTION_TYPES.find(t => t.type === question.type);
  const Icon = typeInfo?.icon || RiText;
  const hasLogic = (question.logic_rules || []).length > 0;
  const hasValidation = Object.keys(question.validation_rules || {}).some(k => (question.validation_rules)[k] !== undefined && (question.validation_rules)[k] !== '');

  return (
    <div ref={setNodeRef} style={style} className={clsx('card mb-3 overflow-hidden transition-all', isDragging && 'shadow-lg')}>
      {/* Header */}
      <div className="flex items-center gap-3 p-4 cursor-pointer" onClick={() => setExpanded(!expanded)}>
        <div {...attributes} {...listeners} onClick={e => e.stopPropagation()}>
          <RiDraggable size={18} className="drag-handle" />
        </div>
        <div className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0" style={{ background: 'rgba(99,102,241,0.12)' }}>
          <Icon size={15} style={{ color: 'var(--brand)' }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate" style={{ color: 'var(--text)' }}>
            {question.text || `Q${index + 1} — ${typeInfo?.label}`}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs" style={{ color: 'var(--text-3)' }}>
              {typeInfo?.label} {typeInfo?.level ? `· ${typeInfo.level}` : ''}
              {question.required ? ' · Required' : ' · Optional'}
            </p>
            {question.randomize_options && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(99,102,241,0.1)', color: 'var(--brand)' }}>Randomized</span>}
            {hasLogic && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(245,158,11,0.1)', color: '#d97706' }}>Logic</span>}
            {question.is_attention_check && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(239,68,68,0.1)', color: '#dc2626' }}>Attention Check</span>}
            {hasValidation && <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'rgba(16,185,129,0.1)', color: '#059669' }}>Validated</span>}
          </div>
        </div>
        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => onDuplicate(question)}>
            <RiFileCopyFill size={14} />
          </button>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => onDelete(question.id)} style={{ color: 'var(--danger)' }}>
            <RiDeleteBinFill size={14} />
          </button>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => setExpanded(!expanded)}>
            {expanded ? <RiArrowUpSFill size={16} style={{ color: 'var(--text-3)' }} /> : <RiArrowDownSFill size={16} style={{ color: 'var(--text-3)' }} />}
          </button>
        </div>
      </div>

      {/* Expanded editor */}
      {expanded && (
        <div className="border-t" style={{ borderColor: 'var(--border)' }}>
          {/* Tab bar */}
          {question.type !== 'section_header' && (
            <div className="flex border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface-2)' }}>
              {[
                { key: 'content',    icon: RiSettings3Line,    label: 'Content' },
                { key: 'logic',      icon: RiGitBranchLine,    label: 'Logic' },
                { key: 'validation', icon: RiShieldCheckLine,  label: 'Validation' },
                { key: 'advanced',   icon: RiAlertLine,        label: 'Advanced' },
              ].map(({ key, icon: TabIcon, label }) => (
                <button
                  key={key}
                  onClick={() => setActiveTab(key as any)}
                  className="flex items-center gap-1.5 px-4 py-2.5 text-xs font-semibold transition-all relative"
                  style={{
                    color: activeTab === key ? 'var(--brand)' : 'var(--text-3)',
                    borderBottom: activeTab === key ? '2px solid var(--brand)' : '2px solid transparent',
                    marginBottom: -1,
                  }}
                >
                  <TabIcon size={13} />
                  {label}
                </button>
              ))}
            </div>
          )}

          <div className="px-4 pb-4 pt-3 space-y-4">
            {/* ══ CONTENT TAB ══ */}
            {(activeTab === 'content' || question.type === 'section_header') && (
              <>
                {/* Question text */}
                <div>
                  <label className="label">{question.type === 'section_header' ? 'Section Title' : 'Question Text *'}</label>
                  <input
                    className="input"
                    placeholder={question.type === 'section_header' ? 'Section heading...' : 'Enter your question...'}
                    value={question.text}
                    onChange={e => onUpdate(question.id, { text: e.target.value })}
                  />
                </div>

                {/* Helper text */}
                {question.type !== 'section_header' && (
                  <div>
                    <label className="label">Helper Text <span style={{ color: 'var(--text-3)', fontWeight: 400 }}>(optional subtext shown to respondents)</span></label>
                    <input
                      className="input"
                      placeholder="e.g. Please select all that apply..."
                      value={question.helper_text || ''}
                      onChange={e => onUpdate(question.id, { helper_text: e.target.value })}
                    />
                  </div>
                )}

                {/* Variable name + Required */}
                {question.type !== 'section_header' && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="label">Variable Name (optional)</label>
                      <input
                        className="input font-mono text-sm"
                        placeholder={`q${index + 1}_variable`}
                        value={question.variable_name}
                        onChange={e => onUpdate(question.id, { variable_name: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
                      />
                    </div>
                    <div className="flex items-end gap-3 pb-1">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={question.required}
                          onChange={e => onUpdate(question.id, { required: e.target.checked })}
                          className="w-4 h-4 accent-[var(--brand)]"
                        />
                        <span className="text-sm" style={{ color: 'var(--text-2)' }}>Required</span>
                      </label>
                    </div>
                  </div>
                )}

                {/* ── Choice options ── */}
                {['single_choice', 'multi_choice', 'dropdown', 'rank_order', 'constant_sum'].includes(question.type) && (
                  <div>
                    <div className="flex justify-between items-center mb-1">
                      <label className="label mb-0">
                        {question.type === 'constant_sum' ? 'Categories / Items' : question.type === 'rank_order' ? 'Items to Rank' : 'Options'}
                      </label>
                      {question.type === 'constant_sum' && (
                        <div className="flex items-center gap-2">
                          <span className="text-xs" style={{ color: 'var(--text-3)' }}>Target Sum:</span>
                          <input type="number" className="input w-20 py-1 text-xs" value={question.scale_max || 100} onChange={e => onUpdate(question.id, { scale_max: +e.target.value })} />
                        </div>
                      )}
                    </div>
                    {/* Randomize toggle */}
                    {['single_choice', 'multi_choice', 'dropdown', 'rank_order'].includes(question.type) && (
                      <label className="flex items-center gap-2 cursor-pointer mb-2">
                        <input
                          type="checkbox"
                          checked={question.randomize_options}
                          onChange={e => onUpdate(question.id, { randomize_options: e.target.checked })}
                          className="w-4 h-4 accent-[var(--brand)]"
                        />
                        <RiShuffleLine size={14} style={{ color: 'var(--brand)' }} />
                        <span className="text-sm" style={{ color: 'var(--text-2)' }}>Randomize option order</span>
                        <span className="text-xs" style={{ color: 'var(--text-3)' }}>(eliminates position bias)</span>
                      </label>
                    )}
                    <div className="space-y-2">
                      {question.options.map((opt: string, i: number) => (
                        <div key={i} className="flex gap-2">
                          <input
                            className="input"
                            value={opt}
                            onChange={e => {
                              const opts = [...question.options]; opts[i] = e.target.value;
                              onUpdate(question.id, { options: opts });
                            }}
                            placeholder={`Item ${i + 1}`}
                          />
                          <button className="btn btn-ghost btn-icon" onClick={() => onUpdate(question.id, { options: question.options.filter((_: any, j: number) => j !== i) })}>
                            <RiCloseFill size={14} />
                          </button>
                        </div>
                      ))}
                      <button className="btn btn-ghost btn-sm" onClick={() => onUpdate(question.id, { options: [...question.options, `Item ${question.options.length + 1}`] })}>
                        <RiAddFill size={14} /> Add Item
                      </button>
                    </div>
                  </div>
                )}

                {/* ── Slider ── */}
                {question.type === 'slider' && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="label">Min Value</label>
                        <input type="number" className="input" value={question.scale_min ?? 0} onChange={e => onUpdate(question.id, { scale_min: +e.target.value })} />
                      </div>
                      <div>
                        <label className="label">Max Value</label>
                        <input type="number" className="input" value={question.scale_max ?? 100} onChange={e => onUpdate(question.id, { scale_max: +e.target.value })} />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="label">Min Label</label>
                        <input type="text" className="input" value={question.options?.[0] || ''} onChange={e => { const opts = [...(question.options || ['', ''])]; opts[0] = e.target.value; onUpdate(question.id, { options: opts }); }} placeholder="e.g. Minimum" />
                      </div>
                      <div>
                        <label className="label">Max Label</label>
                        <input type="text" className="input" value={question.options?.[1] || ''} onChange={e => { const opts = [...(question.options || ['', ''])]; opts[1] = e.target.value; onUpdate(question.id, { options: opts }); }} placeholder="e.g. Maximum" />
                      </div>
                    </div>
                  </div>
                )}

                {/* ── NPS ── */}
                {question.type === 'nps' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="label">Low End Label (0)</label>
                      <input type="text" className="input" value={question.options?.[0] || ''} onChange={e => { const opts = [...(question.options || ['', ''])]; opts[0] = e.target.value; onUpdate(question.id, { options: opts }); }} placeholder="Not at all likely" />
                    </div>
                    <div>
                      <label className="label">High End Label (10)</label>
                      <input type="text" className="input" value={question.options?.[1] || ''} onChange={e => { const opts = [...(question.options || ['', ''])]; opts[1] = e.target.value; onUpdate(question.id, { options: opts }); }} placeholder="Extremely likely" />
                    </div>
                  </div>
                )}

                {/* ── Likert ── */}
                {question.type === 'likert' && (
                  <div>
                    <label className="label">Likert Scale Labels ({question.options.length}-point)</label>
                    <div className="space-y-2">
                      {question.options.map((opt: string, i: number) => (
                        <div key={i} className="flex items-center gap-2">
                          <span className="w-6 text-center text-sm font-mono" style={{ color: 'var(--text-3)' }}>{i + 1}</span>
                          <input className="input" value={opt} onChange={e => { const opts = [...question.options]; opts[i] = e.target.value; onUpdate(question.id, { options: opts }); }} />
                        </div>
                      ))}
                      <div className="flex gap-2">
                        <button className="btn btn-ghost btn-sm" onClick={() => onUpdate(question.id, { options: [...question.options, ''] })}>
                          <RiAddFill size={14} /> Add Point
                        </button>
                        {question.options.length > 2 && (
                          <button className="btn btn-ghost btn-sm" onClick={() => onUpdate(question.id, { options: question.options.slice(0, -1) })}>
                            Remove Last
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* ── Semantic Differential ── */}
                {question.type === 'semantic_differential' && (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="label">Left Pole (negative)</label>
                        <input className="input" placeholder="e.g. Difficult" value={question.options?.[0] || ''} onChange={e => { const opts = [...(question.options || ['', ''])]; opts[0] = e.target.value; onUpdate(question.id, { options: opts }); }} />
                      </div>
                      <div>
                        <label className="label">Right Pole (positive)</label>
                        <input className="input" placeholder="e.g. Easy" value={question.options?.[1] || ''} onChange={e => { const opts = [...(question.options || ['', ''])]; opts[1] = e.target.value; onUpdate(question.id, { options: opts }); }} />
                      </div>
                    </div>
                    <div>
                      <label className="label">Scale Points</label>
                      <select className="input w-40" value={question.scale_max} onChange={e => onUpdate(question.id, { scale_min: 1, scale_max: +e.target.value })}>
                        <option value={5}>5-point</option>
                        <option value={7}>7-point</option>
                      </select>
                    </div>
                    <div className="p-3 rounded-xl text-sm" style={{ background: 'rgba(99,102,241,0.06)', color: 'var(--text-2)' }}>
                      <strong>Preview:</strong> {question.options?.[0] || 'Left Pole'}
                      {Array.from({ length: question.scale_max || 7 }, (_, i) => (
                        <span key={i} className="inline-block w-8 text-center mx-0.5">·{i+1}·</span>
                      ))}
                      {question.options?.[1] || 'Right Pole'}
                    </div>
                  </div>
                )}

                {/* ── Rating ── */}
                {question.type === 'rating' && (
                  <div>
                    <label className="label">Rating Scale</label>
                    <div className="flex items-center gap-3">
                      <span className="text-sm" style={{ color: 'var(--text-2)' }}>1 to</span>
                      <select className="input w-24" value={question.scale_max} onChange={e => onUpdate(question.id, { scale_max: +e.target.value })}>
                        {[5, 7, 10].map(n => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </div>
                  </div>
                )}

                {/* ── Matrix ── */}
                {question.type === 'matrix' && (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="label">Rows (Statements)</label>
                      <div className="space-y-2">
                        {question.rows?.map((r: string, i: number) => (
                          <input key={i} className="input" value={r} onChange={e => { const rows = [...question.rows]; rows[i] = e.target.value; onUpdate(question.id, { rows }); }} />
                        ))}
                        <button className="btn btn-ghost btn-sm" onClick={() => onUpdate(question.id, { rows: [...(question.rows || []), ''] })}>
                          <RiAddFill size={14} /> Add Row
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className="label">Columns (Scale)</label>
                      <div className="space-y-2">
                        {question.columns?.map((c: string, i: number) => (
                          <input key={i} className="input" value={c} onChange={e => { const cols = [...question.columns]; cols[i] = e.target.value; onUpdate(question.id, { columns: cols }); }} />
                        ))}
                        <button className="btn btn-ghost btn-sm" onClick={() => onUpdate(question.id, { columns: [...(question.columns || []), ''] })}>
                          <RiAddFill size={14} /> Add Column
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* ── File Upload ── */}
                {question.type === 'file_upload' && (
                  <div className="space-y-3">
                    <div>
                      <label className="label">Accepted File Types</label>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        {[
                          { key: 'images', label: 'Images (JPG, PNG)' },
                          { key: 'pdf', label: 'PDF Documents' },
                          { key: 'audio', label: 'Audio Files' },
                          { key: 'docs', label: 'Word Documents' },
                        ].map(({ key, label }) => (
                          <label key={key} className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={(question.validation_rules?.accepted_types || ['images', 'pdf']).includes(key)}
                              onChange={e => {
                                const current = question.validation_rules?.accepted_types || ['images', 'pdf'];
                                const updated = e.target.checked ? [...current, key] : current.filter((k: string) => k !== key);
                                onUpdate(question.id, { validation_rules: { ...question.validation_rules, accepted_types: updated } });
                              }}
                              className="w-4 h-4 accent-[var(--brand)]"
                            />
                            <span style={{ color: 'var(--text-2)' }}>{label}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="w-40">
                      <label className="label">Max File Size</label>
                      <select className="input" value={question.validation_rules?.max_size_mb || 10} onChange={e => onUpdate(question.id, { validation_rules: { ...question.validation_rules, max_size_mb: +e.target.value } })}>
                        <option value={5}>5 MB</option>
                        <option value={10}>10 MB</option>
                        <option value={20}>20 MB</option>
                      </select>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* ══ LOGIC TAB ══ */}
            {activeTab === 'logic' && question.type !== 'section_header' && (
              <LogicPanel question={question} allQuestions={allQuestions} onUpdate={onUpdate} />
            )}

            {/* ══ VALIDATION TAB ══ */}
            {activeTab === 'validation' && question.type !== 'section_header' && (
              <ValidationPanel question={question} onUpdate={onUpdate} />
            )}

            {/* ══ ADVANCED TAB ══ */}
            {activeTab === 'advanced' && question.type !== 'section_header' && (
              <div className="space-y-4">
                <div className="p-4 rounded-xl" style={{ background: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.2)' }}>
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={question.is_attention_check}
                      onChange={e => onUpdate(question.id, { is_attention_check: e.target.checked, correct_answer: e.target.checked ? question.correct_answer : null })}
                      className="w-4 h-4 accent-[var(--brand)] mt-0.5 flex-shrink-0"
                    />
                    <div>
                      <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Attention Check / Trap Question</p>
                      <p className="text-xs mt-1" style={{ color: 'var(--text-3)', lineHeight: 1.5 }}>
                        Respondents who answer incorrectly will be flagged in your dataset. Use for choice questions with a single correct answer to detect bots or speeders.
                      </p>
                    </div>
                  </label>
                  {question.is_attention_check && (
                    <div className="mt-3">
                      <label className="label">Correct Answer</label>
                      {['single_choice', 'multi_choice', 'dropdown'].includes(question.type) && question.options?.length ? (
                        <select className="input" value={question.correct_answer || ''} onChange={e => onUpdate(question.id, { correct_answer: e.target.value })}>
                          <option value="">— Select correct answer —</option>
                          {question.options.map((opt: string) => <option key={opt} value={opt}>{opt}</option>)}
                        </select>
                      ) : (
                        <input className="input" placeholder="Exact correct answer value" value={question.correct_answer || ''} onChange={e => onUpdate(question.id, { correct_answer: e.target.value })} />
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function NewSurveyPage() {
  const router = useRouter();
  const [step, setStep] = useState<'meta' | 'build' | 'settings'>('meta');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [questions, setQuestions] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const [autoSaving, setAutoSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [theme, setTheme] = useState<any>({});
  const [allowMultiple, setAllowMultiple] = useState(false);
  const [requireEmail, setRequireEmail] = useState(true);
  const [surveyId, setSurveyId] = useState<string | null>(null);
  const [typePickerOpen, setTypePickerOpen] = useState(false);
  const [typePickerGroup, setTypePickerGroup] = useState<string>('all');
  const surveyIdRef = React.useRef<string | null>(null);

  React.useEffect(() => { surveyIdRef.current = surveyId; }, [surveyId]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const autoSaveSurvey = React.useCallback(async (opts: { currentTitle?: string; currentTheme?: any; publish?: boolean } = {}) => {
    const t = sanitiseText(opts.currentTitle ?? title, 200);
    if (!t) return null;
    setAutoSaving(true);
    try {
      const payload = {
        title: t,
        description: sanitiseText(description, 1000),
        status: opts.publish ? 'active' : 'draft',
        theme: opts.currentTheme ?? theme,
        require_email: requireEmail,
        allow_multiple: allowMultiple,
      };
      let id = surveyIdRef.current;
      if (!id) {
        const res = await surveysApi.create(payload);
        id = res.data.id;
        setSurveyId(id);
        surveyIdRef.current = id;
      } else {
        await surveysApi.update(id, payload);
      }
      setLastSaved(new Date());
      return id;
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Auto-save failed';
      console.warn('[Survey Builder] autoSave error:', msg);
      return surveyIdRef.current;  // return existing id so builder keeps working
    } finally {
      setAutoSaving(false);
    }
  }, [title, description, theme, requireEmail, allowMultiple]);

  const autosaveQsTimer = React.useRef<any>(null);
  const autosaveQuestions = React.useCallback((qs: any[], sid: string) => {
    clearTimeout(autosaveQsTimer.current);
    autosaveQsTimer.current = setTimeout(async () => {
      setAutoSaving(true);
      try {
        for (let i = 0; i < qs.length; i++) {
          const q = { ...qs[i], position: i };
          delete q._new;
          // Sanitise all text fields before sending to API
          q.text         = sanitiseText(q.text || '', 500);
          q.helper_text  = sanitiseText(q.helper_text || '', 300);
          q.variable_name = sanitiseVarName(q.variable_name || '');
          if (Array.isArray(q.options)) {
            q.options = q.options.map(sanitiseOption).filter(Boolean);
          }
          if (Array.isArray(q.rows))    q.rows    = q.rows.map(sanitiseOption).filter(Boolean);
          if (Array.isArray(q.columns)) q.columns = q.columns.map(sanitiseOption).filter(Boolean);
          try {
            if (q.id.startsWith('q_')) {
              const res = await questionsApi.create(sid, q);
              setQuestions(prev => prev.map(x => x.id === qs[i].id ? { ...x, id: res.data.id } : x));
            } else {
              await questionsApi.update(sid, q.id, q);
            }
          } catch (qErr: any) {
            // Non-fatal per-question failure — log and continue with other questions
            console.warn(`[Survey Builder] Failed to save question ${q.id}:`, qErr?.message);
          }
        }
        setLastSaved(new Date());
      } catch (err: any) {
        console.warn('[Survey Builder] autosaveQuestions error:', err?.message);
      } finally {
        setAutoSaving(false);
      }
    }, 1500);
  }, []);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIdx = questions.findIndex(q => q.id === active.id);
      const newIdx = questions.findIndex(q => q.id === over.id);
      setQuestions(arrayMove(questions, oldIdx, newIdx));
    }
  };

  const addQuestion = async (type: string) => {
    const newQ = makeQuestion(type, questions.length);
    const updated = [...questions, newQ];
    setQuestions(updated);
    setTypePickerOpen(false);
    let sid = surveyIdRef.current;
    if (!sid) sid = await autoSaveSurvey();
    if (sid) autosaveQuestions(updated, sid);
  };

  const updateQuestion = async (id: string, patch: any) => {
    const updated = questions.map(q => q.id === id ? { ...q, ...patch } : q);
    setQuestions(updated);
    const sid = surveyIdRef.current;
    if (sid) autosaveQuestions(updated, sid);
  };

  const deleteQuestion = async (id: string) => {
    if (!id.startsWith('q_') && surveyIdRef.current) {
      try {
        await questionsApi.delete(surveyIdRef.current, id);
      } catch (err: any) {
        const msg = err?.response?.data?.detail || err?.message || 'Could not delete question';
        toast.error(`Delete failed: ${msg}`);
        return; // keep question in list if server delete failed
      }
    }
    setQuestions(prev => prev.filter(q => q.id !== id));
  };

  const duplicateQuestion = async (q: any) => {
    const dup = { ...q, id: `q_${Date.now()}`, _new: true };
    const idx = questions.findIndex(x => x.id === q.id);
    const next = [...questions];
    next.splice(idx + 1, 0, dup);
    setQuestions(next);
    const sid = surveyIdRef.current;
    if (sid) autosaveQuestions(next, sid);
  };

  const goToBuild = async () => {
    if (!title.trim()) { toast.error('Please enter a survey title first'); return; }
    await autoSaveSurvey();
    setStep('build');
  };

  const goToSettings = async () => {
    if (!surveyIdRef.current) await autoSaveSurvey();
    setStep('settings');
  };

  const handleSave = async (publish = false) => {
    // ── Client-side validation ────────────────────────────────────────
    const cleanTitle = sanitiseText(title, 200);
    if (!cleanTitle) { toast.error('Survey title is required'); return; }
    if (questions.length === 0) { toast.error('Please add at least one question before saving'); return; }

    // Warn about blank question texts (don't block, but inform)
    const blankQs = questions.filter(q => q.type !== 'section_header' && !q.text?.trim());
    if (blankQs.length > 0) {
      toast(`${blankQs.length} question(s) have no text — they will be saved as blank.`, { icon: '⚠️' });
    }

    setSaving(true);
    try {
      const id = await autoSaveSurvey({ publish });
      if (!id) throw new Error('Could not create or update survey — please check your connection and try again.');

      // Save any remaining new questions not yet synced
      const unsyncedQs = questions.filter(q => q.id.startsWith('q_'));
      for (let i = 0; i < unsyncedQs.length; i++) {
        const q = { ...unsyncedQs[i], position: questions.indexOf(unsyncedQs[i]) };
        delete q._new;
        q.text         = sanitiseText(q.text || '', 500);
        q.helper_text  = sanitiseText(q.helper_text || '', 300);
        q.variable_name = sanitiseVarName(q.variable_name || '');
        if (Array.isArray(q.options)) q.options = q.options.map(sanitiseOption).filter(Boolean);
        try {
          const res = await questionsApi.create(id, q);
          setQuestions(prev => prev.map(x => x.id === unsyncedQs[i].id ? { ...x, id: res.data.id } : x));
        } catch (qErr: any) {
          console.warn('[Survey Builder] Failed to save question on publish:', qErr?.message);
        }
      }

      toast.success(publish ? '🎉 Survey published successfully!' : '✅ Survey saved as draft');
      if (publish) router.push(`/surveys/${id}`);
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Save failed';
      toast.error(`Could not save survey: ${detail}`);
      console.error('[Survey Builder] handleSave error:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleThemeChange = async (newTheme: any) => {
    setTheme(newTheme);
    const sid = surveyIdRef.current;
    if (sid) {
      try { await surveysApi.saveSettings(sid, { theme: newTheme }); setLastSaved(new Date()); } catch { }
    }
  };

  // Group question types for picker
  const groups = ['Choice', 'Scale', 'Number', 'Text', 'Other'];
  const filteredTypes = typePickerGroup === 'all' ? QUESTION_TYPES : QUESTION_TYPES.filter(t => t.group === typePickerGroup);

  // Attach positions to questions for logic panel
  const questionsWithPositions = questions.map((q, i) => ({ ...q, position: i }));

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto">
        {/* Top bar */}
        <div className="flex items-center gap-4 mb-6">
          <button className="btn btn-ghost btn-icon" onClick={() => router.back()}>
            <RiArrowLeftFill size={18} />
          </button>
          <div className="flex-1">
            <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text)' }}>
              {title || 'New Survey'}
            </h1>
            <p className="text-sm flex items-center gap-2" style={{ color: 'var(--text-3)' }}>
              {questions.length} question{questions.length !== 1 ? 's' : ''}
              {autoSaving && <span className="text-xs" style={{ color: 'var(--brand)' }}>● Saving...</span>}
              {!autoSaving && lastSaved && <span className="text-xs">· Saved {lastSaved.toLocaleTimeString()}</span>}
            </p>
          </div>
          <div className="flex gap-2">
            <button className="btn btn-secondary btn-sm" onClick={() => handleSave(false)} disabled={saving}>
              <RiSave3Fill size={14} />
              {saving ? 'Saving...' : 'Save Draft'}
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => handleSave(true)} disabled={saving}>
              <RiSendPlaneFill size={14} />
              Publish
            </button>
          </div>
        </div>

        {/* Step tabs */}
        <div className="flex gap-1 p-1 rounded-xl mb-6" style={{ background: 'var(--surface-3)' }}>
          {(['meta', 'build', 'settings'] as const).map((s, i) => (
            <button
              key={s}
              onClick={() => {
                if (s === 'build') goToBuild();
                else if (s === 'settings') goToSettings();
                else setStep(s);
              }}
              className={clsx('flex-1 py-2 rounded-lg text-sm font-semibold transition-all', step === s ? 'bg-white shadow text-brand-color' : 'text-secondary')}
              style={step === s ? { background: 'var(--surface)', color: 'var(--brand)', boxShadow: 'var(--shadow)' } : { color: 'var(--text-2)' }}
            >
              {i + 1}. {s === 'meta' ? 'Survey Info' : s === 'build' ? 'Edit Questions' : 'Settings'}
            </button>
          ))}
        </div>

        {/* ── Step 1: Meta ── */}
        {step === 'meta' && (
          <div className="card p-6 space-y-5 animate-fade-in">
            <div>
              <label className="label">Survey Title *</label>
              <input className="input text-lg" placeholder="e.g. Impact of Social Media on Academic Performance" value={title} onChange={e => setTitle(e.target.value)} />
            </div>
            <div>
              <label className="label">Description / Introduction</label>
              <textarea className="input" rows={4} placeholder="What is this survey about? Give respondents context..." value={description} onChange={e => setDescription(e.target.value)} style={{ resize: 'vertical' }} />
            </div>

            {/* Submission Restrictions */}
            <div style={{ border: '1.5px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
              <div style={{ padding: '14px 18px', background: 'var(--surface-2)', borderBottom: '1px solid var(--border)' }}>
                <p className="font-semibold text-sm" style={{ color: 'var(--text)' }}>Submission Restrictions</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>Control who can submit and how often</p>
              </div>
              <div style={{ padding: '4px 0' }}>
                <label style={{ display: 'flex', alignItems: 'flex-start', gap: 14, padding: '16px 18px', cursor: 'pointer', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ flex: 1 }}>
                    <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Prevent Multiple Submissions</p>
                    <p className="text-xs mt-1" style={{ color: 'var(--text-3)', lineHeight: 1.5 }}>Disallow participants from taking the survey more than once.</p>
                  </div>
                  <button type="button" role="switch" aria-checked={!allowMultiple} onClick={() => setAllowMultiple(v => !v)}
                    style={{ flexShrink: 0, width: 44, height: 24, borderRadius: 99, border: 'none', background: !allowMultiple ? '#4f46e5' : '#d1d5db', position: 'relative', cursor: 'pointer', transition: 'background 0.2s', marginTop: 2 }}>
                    <span style={{ position: 'absolute', top: 3, left: !allowMultiple ? 23 : 3, width: 18, height: 18, borderRadius: '50%', background: '#fff', boxShadow: '0 1px 4px rgba(0,0,0,0.2)', transition: 'left 0.2s' }} />
                  </button>
                </label>
                <label style={{ display: 'flex', alignItems: 'flex-start', gap: 14, padding: '16px 18px', cursor: 'pointer' }}>
                  <div style={{ flex: 1 }}>
                    <p className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Require Email for Verification</p>
                    <p className="text-xs mt-1" style={{ color: 'var(--text-3)', lineHeight: 1.5 }}>Participants must provide an email to verify they haven't submitted before.</p>
                  </div>
                  <button type="button" role="switch" aria-checked={requireEmail} onClick={() => setRequireEmail(v => !v)}
                    style={{ flexShrink: 0, width: 44, height: 24, borderRadius: 99, border: 'none', background: requireEmail ? '#4f46e5' : '#d1d5db', position: 'relative', cursor: 'pointer', transition: 'background 0.2s', marginTop: 2 }}>
                    <span style={{ position: 'absolute', top: 3, left: requireEmail ? 23 : 3, width: 18, height: 18, borderRadius: '50%', background: '#fff', boxShadow: '0 1px 4px rgba(0,0,0,0.2)', transition: 'left 0.2s' }} />
                  </button>
                </label>
              </div>
            </div>

            <button className="btn btn-primary" onClick={goToBuild}>
              Continue to Build Questions
            </button>
          </div>
        )}

        {/* ── Step 2: Build ── */}
        {step === 'build' && (
          <div className="animate-fade-in">
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={questions.map(q => q.id)} strategy={verticalListSortingStrategy}>
                {questions.map((q, i) => (
                  <QuestionCard
                    key={q.id}
                    question={q}
                    allQuestions={questionsWithPositions}
                    index={i}
                    onUpdate={updateQuestion}
                    onDelete={deleteQuestion}
                    onDuplicate={duplicateQuestion}
                  />
                ))}
              </SortableContext>
            </DndContext>

            {/* Add question button */}
            <div className="relative">
              <button
                className="btn btn-secondary w-full"
                style={{ border: '2px dashed var(--border)' }}
                onClick={() => setTypePickerOpen(!typePickerOpen)}
              >
                <RiAddFill size={16} />
                Add Question
              </button>

              {typePickerOpen && (
                <div className="absolute top-full left-0 right-0 z-20 card mt-2 p-4 animate-slide-up" style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.15)' }}>
                  {/* Group filter tabs */}
                  <div className="flex gap-1 mb-3 flex-wrap">
                    {['all', ...groups].map(g => (
                      <button
                        key={g}
                        onClick={() => setTypePickerGroup(g)}
                        className="px-3 py-1 rounded-full text-xs font-semibold transition-all"
                        style={{
                          background: typePickerGroup === g ? 'var(--brand)' : 'var(--surface-2)',
                          color: typePickerGroup === g ? '#fff' : 'var(--text-2)',
                        }}
                      >
                        {g === 'all' ? 'All' : g}
                      </button>
                    ))}
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {filteredTypes.map(({ type, icon: Icon, label, level }) => (
                      <button
                        key={type}
                        onClick={() => addQuestion(type)}
                        className="flex flex-col items-center gap-1.5 p-3 rounded-xl text-center transition-all"
                        style={{ background: 'var(--surface-2)', color: 'var(--text-2)' }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(99,102,241,0.08)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'var(--surface-2)')}
                      >
                        <Icon size={18} style={{ color: 'var(--brand)' }} />
                        <span className="text-xs font-medium leading-tight">{label}</span>
                        {level && <span className="text-xs" style={{ color: 'var(--text-3)', fontSize: '9px' }}>{level}</span>}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Step 3: Settings ── */}
        {step === 'settings' && (
          <div className="animate-fade-in space-y-6">
            {autoSaving && (
              <div className="flex items-center gap-2 text-sm px-1" style={{ color: 'var(--brand)' }}>
                <RiLoader4Line className="animate-spin" size={14} /> Saving changes...
              </div>
            )}
            <SurveySettings theme={theme} onChange={handleThemeChange} surveyId={surveyId || 'new'} />
            <div className="mt-8 flex justify-end gap-3">
              <button onClick={() => handleSave(true)} disabled={saving} className="btn btn-primary">
                <RiSendPlaneFill size={14} />
                {saving ? 'Publishing...' : 'Publish Survey'}
              </button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
