// src/pages/surveys/new.tsx
import React, { useState, useEffect } from 'react';
import AppLayout from '../../components/layout/AppLayout';
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
  GripVertical, Trash2, Plus, Copy, ChevronDown, ChevronUp,
  Type, AlignLeft, List, CheckSquare, Star, Hash, Calendar,
  Sliders, Table2, Heading1, Eye, Save, Send, ArrowLeft, X
} from 'lucide-react';
import { surveysApi, questionsApi } from '../../lib/api';
import toast from 'react-hot-toast';
import clsx from 'clsx';

const QUESTION_TYPES = [
  { type: 'short_text',      icon: Type,       label: 'Short Text',      level: 'nominal' },
  { type: 'long_text',       icon: AlignLeft,   label: 'Long Text',       level: 'nominal' },
  { type: 'single_choice',   icon: List,        label: 'Single Choice',   level: 'nominal' },
  { type: 'multi_choice',    icon: CheckSquare, label: 'Multi Choice',    level: 'nominal' },
  { type: 'likert',          icon: Sliders,     label: 'Likert Scale',    level: 'ordinal' },
  { type: 'rating',          icon: Star,        label: 'Rating',          level: 'ordinal' },
  { type: 'matrix',          icon: Table2,      label: 'Matrix',          level: 'ordinal' },
  { type: 'number',          icon: Hash,        label: 'Number',          level: 'ratio' },
  { type: 'date',            icon: Calendar,    label: 'Date',            level: 'interval' },
  { type: 'section_header',  icon: Heading1,    label: 'Section Header',  level: null },
];

const LIKERT_DEFAULTS = [
  'Strongly Disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly Agree'
];

function makeQuestion(type: string, position: number) {
  return {
    id: `q_${Date.now()}_${Math.random().toString(36).slice(2,7)}`,
    type,
    text: '',
    required: type !== 'section_header',
    options: type === 'likert' ? LIKERT_DEFAULTS : type === 'single_choice' || type === 'multi_choice' ? ['Option 1', 'Option 2'] : [],
    scale_min: 1,
    scale_max: type === 'rating' ? 5 : 5,
    position,
    variable_name: '',
    measurement_level: QUESTION_TYPES.find(t => t.type === type)?.level || 'nominal',
    rows: type === 'matrix' ? ['Row 1', 'Row 2'] : [],
    columns: type === 'matrix' ? ['Column 1', 'Column 2'] : [],
    _new: true,
  };
}

// ─── Sortable Question Card ──────────────────────────────────────────
function QuestionCard({ question, onUpdate, onDelete, onDuplicate, index }: any) {
  const [expanded, setExpanded] = useState(question._new);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: question.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const typeInfo = QUESTION_TYPES.find(t => t.type === question.type);
  const Icon = typeInfo?.icon || Type;

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={clsx('card mb-3 overflow-hidden transition-all', isDragging && 'shadow-lg')}
    >
      {/* Header */}
      <div
        className="flex items-center gap-3 p-4 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
        style={{ background: expanded ? 'var(--surface)' : 'var(--surface)' }}
      >
        <div {...attributes} {...listeners} onClick={e => e.stopPropagation()}>
          <GripVertical size={18} className="drag-handle" />
        </div>
        <div
          className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0"
          style={{ background: 'rgba(99,102,241,0.12)' }}
        >
          <Icon size={15} style={{ color: 'var(--brand)' }} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate" style={{ color: 'var(--text)' }}>
            {question.text || `Q${index + 1} — ${typeInfo?.label}`}
          </p>
          <p className="text-xs" style={{ color: 'var(--text-3)' }}>
            {typeInfo?.label} {typeInfo?.level ? `· ${typeInfo.level}` : ''}
            {question.required ? ' · Required' : ' · Optional'}
          </p>
        </div>
        <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => onDuplicate(question)}>
            <Copy size={14} />
          </button>
          <button className="btn btn-ghost btn-icon btn-sm" onClick={() => onDelete(question.id)}
            style={{ color: 'var(--danger)' }}>
            <Trash2 size={14} />
          </button>
          {expanded ? <ChevronUp size={16} style={{ color: 'var(--text-3)' }} /> : <ChevronDown size={16} style={{ color: 'var(--text-3)' }} />}
        </div>
      </div>

      {/* Expanded editor */}
      {expanded && (
        <div className="px-4 pb-4 pt-2 border-t space-y-4" style={{ borderColor: 'var(--border)' }}>
          {/* Question text */}
          {question.type !== 'section_header' ? (
            <div>
              <label className="label">Question Text *</label>
              <input
                className="input"
                placeholder="Enter your question..."
                value={question.text}
                onChange={e => onUpdate(question.id, { text: e.target.value })}
              />
            </div>
          ) : (
            <div>
              <label className="label">Section Title</label>
              <input
                className="input"
                placeholder="Section heading..."
                value={question.text}
                onChange={e => onUpdate(question.id, { text: e.target.value })}
              />
            </div>
          )}

          {/* Variable name */}
          {question.type !== 'section_header' && (
            <div className="grid grid-cols-2 gap-3">
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

          {/* Options for choice/likert */}
          {(question.type === 'single_choice' || question.type === 'multi_choice') && (
            <div>
              <label className="label">Options</label>
              <div className="space-y-2">
                {question.options.map((opt: string, i: number) => (
                  <div key={i} className="flex gap-2">
                    <input
                      className="input"
                      value={opt}
                      onChange={e => {
                        const opts = [...question.options];
                        opts[i] = e.target.value;
                        onUpdate(question.id, { options: opts });
                      }}
                      placeholder={`Option ${i + 1}`}
                    />
                    <button
                      className="btn btn-ghost btn-icon"
                      onClick={() => onUpdate(question.id, { options: question.options.filter((_: any, j: number) => j !== i) })}
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => onUpdate(question.id, { options: [...question.options, `Option ${question.options.length + 1}`] })}
                >
                  <Plus size={14} /> Add Option
                </button>
              </div>
            </div>
          )}

          {/* Likert labels */}
          {question.type === 'likert' && (
            <div>
              <label className="label">Likert Scale Labels ({question.options.length}-point)</label>
              <div className="space-y-2">
                {question.options.map((opt: string, i: number) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-6 text-center text-sm font-mono" style={{ color: 'var(--text-3)' }}>{i + 1}</span>
                    <input
                      className="input"
                      value={opt}
                      onChange={e => {
                        const opts = [...question.options];
                        opts[i] = e.target.value;
                        onUpdate(question.id, { options: opts });
                      }}
                    />
                  </div>
                ))}
                <div className="flex gap-2">
                  <button className="btn btn-ghost btn-sm" onClick={() => onUpdate(question.id, { options: [...question.options, ''] })}>
                    <Plus size={14} /> Add Point
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

          {/* Rating scale */}
          {question.type === 'rating' && (
            <div>
              <label className="label">Rating Scale</label>
              <div className="flex items-center gap-3">
                <span className="text-sm" style={{ color: 'var(--text-2)' }}>1 to</span>
                <select
                  className="input w-24"
                  value={question.scale_max}
                  onChange={e => onUpdate(question.id, { scale_max: +e.target.value })}
                >
                  {[5, 7, 10].map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
            </div>
          )}

          {/* Matrix */}
          {question.type === 'matrix' && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Rows (Statements)</label>
                <div className="space-y-2">
                  {question.rows?.map((r: string, i: number) => (
                    <input key={i} className="input" value={r}
                      onChange={e => {
                        const rows = [...question.rows]; rows[i] = e.target.value;
                        onUpdate(question.id, { rows });
                      }} />
                  ))}
                  <button className="btn btn-ghost btn-sm" onClick={() => onUpdate(question.id, { rows: [...(question.rows || []), ''] })}>
                    <Plus size={14} /> Add Row
                  </button>
                </div>
              </div>
              <div>
                <label className="label">Columns (Scale)</label>
                <div className="space-y-2">
                  {question.columns?.map((c: string, i: number) => (
                    <input key={i} className="input" value={c}
                      onChange={e => {
                        const cols = [...question.columns]; cols[i] = e.target.value;
                        onUpdate(question.id, { columns: cols });
                      }} />
                  ))}
                  <button className="btn btn-ghost btn-sm" onClick={() => onUpdate(question.id, { columns: [...(question.columns || []), ''] })}>
                    <Plus size={14} /> Add Column
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────
export default function NewSurveyPage() {
  const router = useRouter();
  const [step, setStep] = useState<'meta' | 'build' | 'brief'>('meta');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [questions, setQuestions] = useState<any[]>([]);
  const [brief, setBrief] = useState({
    topic: '',
    objectives: [''],
    hypotheses: [''],
    study_type: 'quantitative',
    population: '',
    sample_size: '',
    dependent_variable: '',
    independent_variable: '',
  });
  const [saving, setSaving] = useState(false);
  const [surveyId, setSurveyId] = useState<string | null>(null);
  const [typePickerOpen, setTypePickerOpen] = useState(false);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      const oldIdx = questions.findIndex(q => q.id === active.id);
      const newIdx = questions.findIndex(q => q.id === over.id);
      setQuestions(arrayMove(questions, oldIdx, newIdx));
    }
  };

  const addQuestion = (type: string) => {
    setQuestions(prev => [...prev, makeQuestion(type, prev.length)]);
    setTypePickerOpen(false);
  };

  const updateQuestion = (id: string, patch: any) => {
    setQuestions(prev => prev.map(q => q.id === id ? { ...q, ...patch } : q));
  };

  const deleteQuestion = (id: string) => {
    setQuestions(prev => prev.filter(q => q.id !== id));
  };

  const duplicateQuestion = (q: any) => {
    const dup = { ...q, id: `q_${Date.now()}`, _new: true };
    const idx = questions.findIndex(x => x.id === q.id);
    const next = [...questions];
    next.splice(idx + 1, 0, dup);
    setQuestions(next);
  };

  const handleSave = async (publish = false) => {
    if (!title.trim()) { toast.error('Survey title is required'); return; }
    if (questions.length === 0) { toast.error('Add at least one question'); return; }
    setSaving(true);
    try {
      const payload = {
        title,
        description,
        project_brief: brief,
        status: publish ? 'active' : 'draft',
      };
      let id = surveyId;
      if (!id) {
        const res = await surveysApi.create(payload);
        id = res.data.id;
        setSurveyId(id);
      } else {
        await surveysApi.update(id!, payload);
      }
      // Save questions
      for (let i = 0; i < questions.length; i++) {
        const q = { ...questions[i], position: i };
        delete q._new;
        if (q.id.startsWith('q_')) {
          await questionsApi.create(id!, q);
        }
      }
      toast.success(publish ? 'Survey published! 🎉' : 'Survey saved!');
      if (publish) router.push(`/surveys/${id}`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppLayout>
      <div className="max-w-4xl mx-auto">
        {/* Top bar */}
        <div className="flex items-center gap-4 mb-6">
          <button className="btn btn-ghost btn-icon" onClick={() => router.back()}>
            <ArrowLeft size={18} />
          </button>
          <div className="flex-1">
            <h1 className="font-display font-bold text-xl" style={{ color: 'var(--text)' }}>
              {title || 'New Survey'}
            </h1>
            <p className="text-sm" style={{ color: 'var(--text-3)' }}>
              {questions.length} question{questions.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="flex gap-2">
            <button className="btn btn-secondary btn-sm" onClick={() => handleSave(false)} disabled={saving}>
              <Save size={14} />
              {saving ? 'Saving...' : 'Save Draft'}
            </button>
            <button className="btn btn-primary btn-sm" onClick={() => handleSave(true)} disabled={saving}>
              <Send size={14} />
              Publish
            </button>
          </div>
        </div>

        {/* Step tabs */}
        <div className="flex gap-1 p-1 rounded-xl mb-6" style={{ background: 'var(--surface-2)' }}>
          {(['meta', 'build', 'brief'] as const).map((s, i) => (
            <button
              key={s}
              onClick={() => setStep(s)}
              className={clsx(
                'flex-1 py-2 rounded-lg text-sm font-semibold transition-all',
                step === s
                  ? 'bg-white shadow text-brand-color'
                  : 'text-secondary'
              )}
              style={step === s ? { background: 'var(--surface)', color: 'var(--brand)', boxShadow: 'var(--shadow)' } : { color: 'var(--text-2)' }}
            >
              {i + 1}. {s === 'meta' ? 'Survey Info' : s === 'build' ? 'Build Questions' : 'Research Brief'}
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
              <textarea
                className="input"
                rows={4}
                placeholder="What is this survey about? Give respondents context..."
                value={description}
                onChange={e => setDescription(e.target.value)}
                style={{ resize: 'vertical' }}
              />
            </div>
            <button className="btn btn-primary" onClick={() => setStep('build')}>
              Continue to Build Questions →
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
                    index={i}
                    onUpdate={updateQuestion}
                    onDelete={deleteQuestion}
                    onDuplicate={duplicateQuestion}
                  />
                ))}
              </SortableContext>
            </DndContext>

            {/* Add question */}
            <div className="relative">
              <button
                className="btn btn-secondary w-full border-dashed"
                style={{ border: '2px dashed var(--border)' }}
                onClick={() => setTypePickerOpen(!typePickerOpen)}
              >
                <Plus size={16} />
                Add Question
              </button>

              {typePickerOpen && (
                <div className="absolute top-full left-0 right-0 z-20 card mt-2 p-3 grid grid-cols-3 gap-2 animate-slide-up">
                  {QUESTION_TYPES.map(({ type, icon: Icon, label, level }) => (
                    <button
                      key={type}
                      onClick={() => addQuestion(type)}
                      className="flex flex-col items-center gap-1.5 p-3 rounded-xl text-center transition-all hover:opacity-100"
                      style={{ background: 'var(--surface-2)', color: 'var(--text-2)' }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(99,102,241,0.08)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'var(--surface-2)')}
                    >
                      <Icon size={18} style={{ color: 'var(--brand)' }} />
                      <span className="text-xs font-medium">{label}</span>
                      {level && <span className="text-xs" style={{ color: 'var(--text-3)', fontSize: '9px' }}>{level}</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {questions.length > 0 && (
              <div className="mt-4 flex justify-end">
                <button className="btn btn-primary" onClick={() => setStep('brief')}>
                  Continue to Research Brief →
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Step 3: Research Brief ── */}
        {step === 'brief' && (
          <div className="card p-6 space-y-5 animate-fade-in">
            <div>
              <p className="font-display font-semibold text-base mb-1" style={{ color: 'var(--text)' }}>
                Research Brief
              </p>
              <p className="text-sm" style={{ color: 'var(--text-2)' }}>
                This drives the AI test selection and Chapter 4 generation
              </p>
            </div>

            <div>
              <label className="label">Project Topic</label>
              <input className="input" placeholder="Full project title" value={brief.topic} onChange={e => setBrief(b => ({ ...b, topic: e.target.value }))} />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Study Type</label>
                <select className="input" value={brief.study_type} onChange={e => setBrief(b => ({ ...b, study_type: e.target.value }))}>
                  <option value="quantitative">Quantitative</option>
                  <option value="qualitative">Qualitative</option>
                  <option value="mixed">Mixed Methods</option>
                  <option value="descriptive">Descriptive</option>
                  <option value="experimental">Experimental</option>
                  <option value="correlation">Correlational</option>
                </select>
              </div>
              <div>
                <label className="label">Population / Sample</label>
                <input className="input" placeholder="e.g. 200 undergraduate students" value={brief.population} onChange={e => setBrief(b => ({ ...b, population: e.target.value }))} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Dependent Variable (DV)</label>
                <input className="input" placeholder="e.g. Academic Performance (CGPA)" value={brief.dependent_variable} onChange={e => setBrief(b => ({ ...b, dependent_variable: e.target.value }))} />
              </div>
              <div>
                <label className="label">Independent Variable (IV)</label>
                <input className="input" placeholder="e.g. Social Media Usage" value={brief.independent_variable} onChange={e => setBrief(b => ({ ...b, independent_variable: e.target.value }))} />
              </div>
            </div>

            <div>
              <label className="label">Research Objectives</label>
              <div className="space-y-2">
                {brief.objectives.map((obj, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="w-6 mt-3 text-sm font-mono" style={{ color: 'var(--text-3)' }}>{i + 1}.</span>
                    <input
                      className="input"
                      placeholder={`Objective ${i + 1}`}
                      value={obj}
                      onChange={e => {
                        const arr = [...brief.objectives]; arr[i] = e.target.value;
                        setBrief(b => ({ ...b, objectives: arr }));
                      }}
                    />
                    {i > 0 && (
                      <button className="btn btn-ghost btn-icon" onClick={() => setBrief(b => ({ ...b, objectives: b.objectives.filter((_, j) => j !== i) }))}>
                        <X size={14} />
                      </button>
                    )}
                  </div>
                ))}
                <button className="btn btn-ghost btn-sm" onClick={() => setBrief(b => ({ ...b, objectives: [...b.objectives, ''] }))}>
                  <Plus size={14} /> Add Objective
                </button>
              </div>
            </div>

            <div>
              <label className="label">Hypotheses</label>
              <div className="space-y-2">
                {brief.hypotheses.map((h, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="w-7 mt-3 text-xs font-mono" style={{ color: 'var(--text-3)' }}>H{i + 1}:</span>
                    <input
                      className="input"
                      placeholder={`H${i + 1}: There is no significant...`}
                      value={h}
                      onChange={e => {
                        const arr = [...brief.hypotheses]; arr[i] = e.target.value;
                        setBrief(b => ({ ...b, hypotheses: arr }));
                      }}
                    />
                    {i > 0 && (
                      <button className="btn btn-ghost btn-icon" onClick={() => setBrief(b => ({ ...b, hypotheses: b.hypotheses.filter((_, j) => j !== i) }))}>
                        <X size={14} />
                      </button>
                    )}
                  </div>
                ))}
                <button className="btn btn-ghost btn-sm" onClick={() => setBrief(b => ({ ...b, hypotheses: [...b.hypotheses, ''] }))}>
                  <Plus size={14} /> Add Hypothesis
                </button>
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button className="btn btn-secondary flex-1" onClick={() => setStep('build')}>← Back</button>
              <button className="btn btn-secondary" onClick={() => handleSave(false)} disabled={saving}>
                <Save size={14} /> Save Draft
              </button>
              <button className="btn btn-primary flex-1" onClick={() => handleSave(true)} disabled={saving}>
                <Send size={14} /> {saving ? 'Publishing...' : 'Publish Survey'}
              </button>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
