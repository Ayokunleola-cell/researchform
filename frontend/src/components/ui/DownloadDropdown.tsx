import React, { useState, useRef, useEffect } from 'react';
import { RiDownload2Fill, RiLoader4Line, RiArrowDownSLine } from 'react-icons/ri';

type DownloadDropdownProps = {
  onDownloadWord: () => void;
  onDownloadPdf: () => void;
  downloading: boolean;
};

export default function DownloadDropdown({ onDownloadWord, onDownloadPdf, downloading }: DownloadDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={downloading}
        className="btn btn-primary btn-sm"
        style={{ cursor: downloading ? 'not-allowed' : 'pointer', margin: 0, gap: '4px' }}
      >
        {downloading ? <RiLoader4Line size={14} className="animate-spin" /> : <RiDownload2Fill size={14} />}
        Download
        <RiArrowDownSLine size={14} />
      </button>

      {isOpen && (
        <div 
          className="absolute right-0 bottom-full mb-2 shadow-2xl z-50 overflow-hidden"
          style={{ width: 230, background: 'var(--surface)', borderRadius: 16, border: '1px solid var(--border)' }}
        >
          <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
            <span className="text-xs font-medium" style={{ color: 'var(--text-3)' }}>Download</span>
          </div>
          <div className="flex flex-col py-2">
            <button 
              type="button"
              onClick={() => { setIsOpen(false); onDownloadPdf(); }}
              className="flex items-center justify-between w-full px-4 py-2 transition-colors text-left group download-item"
              style={{ background: 'none', border: 'none', cursor: 'pointer' }}
            >
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center rounded" style={{ width: 22, height: 22, background: 'var(--danger)', color: '#fff', flexShrink: 0 }}>
                  <span style={{ fontSize: 8, fontWeight: 800 }}>PDF</span>
                </div>
                <span className="text-sm font-medium transition-colors" style={{ color: 'var(--text)' }}>PDF document</span>
              </div>
              <span className="text-xs" style={{ color: 'var(--text-3)' }}>.pdf</span>
            </button>
            <button 
              type="button"
              onClick={() => { setIsOpen(false); onDownloadWord(); }}
              className="flex items-center justify-between w-full px-4 py-2 transition-colors text-left group download-item"
              style={{ background: 'none', border: 'none', cursor: 'pointer' }}
            >
              <div className="flex items-center gap-3">
                <div className="flex items-center justify-center rounded" style={{ width: 22, height: 22, background: 'var(--info)', color: '#fff', flexShrink: 0 }}>
                  <span style={{ fontSize: 12, fontWeight: 800, fontFamily: 'serif' }}>W</span>
                </div>
                <span className="text-sm font-medium transition-colors" style={{ color: 'var(--text)' }}>Microsoft Word</span>
              </div>
              <span className="text-xs" style={{ color: 'var(--text-3)' }}>.docx</span>
            </button>
          </div>
        </div>
      )}
      <style>{`
        .download-item:hover { background: var(--surface-2) !important; }
      `}</style>
    </div>
  );
}
