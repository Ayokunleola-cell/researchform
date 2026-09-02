// src/components/analysis/ResultsTable.tsx
// APA-formatted interactive HTML table with Copy for Word, Copy plain, and Export Excel
import React, { useRef, useCallback } from 'react';
import { RiFileCopyLine, RiFileTextFill, RiDownload2Fill, RiArrowUpDownFill } from 'react-icons/ri';
import toast from 'react-hot-toast';

interface ResultsTableProps {
  htmlContent: string;   // Raw HTML string from backend
  title: string;
  tableKey: string;
}

export default function ResultsTable({ htmlContent, title, tableKey }: ResultsTableProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // ── Copy plain text (tab-separated, pastes into Excel) ─────────────────────
  const copyPlain = useCallback(() => {
    if (!containerRef.current) return;
    const table = containerRef.current.querySelector('table');
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tr'));
    const text = rows.map(r =>
      Array.from(r.querySelectorAll('th,td')).map(c => c.textContent?.trim() ?? '').join('\t')
    ).join('\n');
    navigator.clipboard.writeText(text).then(() => toast.success('Table copied — paste into Excel'));
  }, []);

  // ── Copy for Word (RTF-like HTML, paste directly into Word) ────────────────
  const copyForWord = useCallback(() => {
    if (!containerRef.current) return;
    const table = containerRef.current.querySelector('table');
    if (!table) return;

    // APA Word table style
    const wordHTML = `
<html><body>
<style>
  table { border-collapse: collapse; width: 100%; font-family: 'Times New Roman', serif; font-size: 12pt; }
  thead tr { border-top: 1.5pt solid black; border-bottom: 1pt solid black; }
  th { font-weight: bold; padding: 4pt 8pt; text-align: right; }
  th:first-child { text-align: left; }
  td { padding: 3pt 8pt; text-align: right; border: none; }
  td:first-child { text-align: left; }
  tbody tr:last-child { border-bottom: 1.5pt solid black; }
  caption { text-align: left; font-style: italic; padding-bottom: 4pt; }
</style>
${table.outerHTML}
</body></html>`;

    const blob = new Blob([wordHTML], { type: 'text/html' });
    const clipItem = new ClipboardItem({ 'text/html': blob });
    navigator.clipboard.write([clipItem])
      .then(() => toast.success('APA table copied — paste into Word'))
      .catch(() => {
        // Fallback: copy plain text
        copyPlain();
      });
  }, [copyPlain]);

  // ── Export as CSV ───────────────────────────────────────────────────────────
  const exportCSV = useCallback(() => {
    if (!containerRef.current) return;
    const table = containerRef.current.querySelector('table');
    if (!table) return;
    const rows = Array.from(table.querySelectorAll('tr'));
    const csv = rows.map(r =>
      Array.from(r.querySelectorAll('th,td'))
        .map(c => `"${(c.textContent?.trim() ?? '').replace(/"/g, '""')}"`)
        .join(',')
    ).join('\n');
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url; a.download = `${tableKey}.csv`; a.click();
    URL.revokeObjectURL(url);
    toast.success('CSV downloaded');
  }, [tableKey]);

  return (
    <div style={{
      background: 'var(--surface)', border: '1px solid var(--border)',
      borderRadius: 14, overflow: 'hidden', marginBottom: 16,
    }}>
      {/* Toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 16px', borderBottom: '1px solid var(--border)',
        background: 'var(--surface-2)',
      }}>
        <p style={{ margin: 0, fontSize: 13, fontWeight: 700, color: 'var(--text)' }}>{title}</p>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={copyPlain} title="Copy as tab-separated text (paste into Excel)"
            style={btnStyle('#6366f1')}>
            <RiFileCopyLine size={12} /> Copy Table
          </button>
          <button onClick={copyForWord} title="Copy as APA-formatted table (paste into Word)"
            style={btnStyle('#2563eb')}>
            <RiFileTextFill size={12} /> Copy for Word
          </button>
          <button onClick={exportCSV} title="Download as CSV"
            style={btnStyle('#059669')}>
            <RiDownload2Fill size={12} /> CSV
          </button>
        </div>
      </div>

      {/* Table container */}
      <div
        ref={containerRef}
        style={{ padding: '16px 20px', overflowX: 'auto' }}
        dangerouslySetInnerHTML={{ __html: htmlContent }}
      />
    </div>
  );
}

function btnStyle(color: string): React.CSSProperties {
  return {
    display: 'flex', alignItems: 'center', gap: 4,
    padding: '5px 10px', borderRadius: 8, border: `1px solid ${color}20`,
    background: `${color}10`, color, fontWeight: 600, fontSize: 11,
    cursor: 'pointer', whiteSpace: 'nowrap', transition: 'all 0.15s',
  };
}
