import React, { useState } from 'react';
import { RiImageAddLine, RiUploadCloud2Line, RiCloseCircleFill } from 'react-icons/ri';
import toast from 'react-hot-toast';
import { api, surveysApi } from '../../lib/api';

interface SurveySettingsProps {
  theme: any;
  onChange: (theme: any) => void;
  surveyId: string;
}

export default function SurveySettings({ theme, onChange, surveyId }: SurveySettingsProps) {
  const [uploadingBg, setUploadingBg] = useState(false);
  const [uploadingHeader, setUploadingHeader] = useState(false);

  const t = theme || {};

  const handleUpdate = (updates: any) => {
    onChange({ ...t, ...updates });
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>, type: 'bg' | 'header') => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    if (type === 'bg') setUploadingBg(true);
    else setUploadingHeader(true);

    const formData = new FormData();
    formData.append('file', file);

    // Can't upload media until the survey is saved and has a real ID
    if (surveyId === 'new') {
      toast.error('Please save your survey first before uploading images.');
      if (type === 'bg') setUploadingBg(false);
      else setUploadingHeader(false);
      return;
    }

    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('rf_token='))?.split('=')[1];
      const res = await fetch(`${api.defaults.baseURL}/surveys/${surveyId}/upload-media`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });
      
      if (!res.ok) {
        let errMsg = `Upload failed (${res.status})`;
        try {
          const errData = await res.json();
          if (errData?.detail) errMsg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
        } catch {}
        throw new Error(errMsg);
      }
      
      const data = await res.json();
      
      if (data && data.url) {
        let url = data.url;
        // Backend returns relative path like /storage/uploads/xxx.png — prepend backend base URL
        if (url.startsWith('/')) {
          url = api.defaults.baseURL + url;
        }
        const newTheme = type === 'bg'
          ? { ...t, backgroundImageUrl: url }
          : { ...t, headerPictureUrl: url };

        // Update local state immediately
        onChange(newTheme);

        // Persist to DB right away via safe endpoint (won't touch survey status)
        if (surveyId && surveyId !== 'new') {
          try {
            await surveysApi.saveSettings(surveyId, { theme: newTheme });
            toast.success('Image uploaded and saved! ✓');
          } catch {
            toast.success('Image uploaded! Click Save Settings to apply.');
          }
        } else {
          toast.success('Image uploaded! Save your survey to apply.');
        }
      }
    } catch (err: any) {
      console.error('Upload Error:', err);
      toast.error(err?.message || 'Upload failed');
    } finally {
      if (type === 'bg') setUploadingBg(false);
      else setUploadingHeader(false);
    }
  };

  return (
    <div className="space-y-6 w-full">
      
      {/* TYPOGRAPHY SECTION */}
      <div className="card p-6 space-y-5">
        <h3 className="text-lg font-bold" style={{ color: 'var(--text-1)' }}>Typography</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <label className="label">Font Family</label>
            <select 
              value={t.fontFamily || 'Inter'} 
              onChange={e => handleUpdate({ fontFamily: e.target.value })}
              className="input w-full"
            >
              <option value="Inter">Inter (Sans-serif)</option>
              <option value="Roboto">Roboto</option>
              <option value="Merriweather">Merriweather (Serif)</option>
              <option value="Outfit">Outfit</option>
            </select>
          </div>
          
          <div className="space-y-2">
            <label className="label">Font Size</label>
            <select 
              value={t.fontSize || 'medium'} 
              onChange={e => handleUpdate({ fontSize: e.target.value })}
              className="input w-full"
            >
              <option value="small">Small</option>
              <option value="medium">Medium</option>
              <option value="large">Large</option>
            </select>
          </div>
        </div>
      </div>

      {/* HEADER DESIGN SECTION */}
      <div className="card p-6 space-y-5">
        <h3 className="text-lg font-bold" style={{ color: 'var(--text-1)' }}>Header Styling</h3>

        <div className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-1 space-y-2">
              <label className="label">Header Text</label>
              <input 
                type="text" 
                value={t.headerText || ''} 
                onChange={e => handleUpdate({ headerText: e.target.value })}
                className="input w-full"
                placeholder="E.g., 2026 Customer Feedback"
              />
            </div>
            <div className="space-y-2">
              <label className="label">Header Text Color</label>
              <div className="flex items-center gap-3 input w-full">
                <input 
                  type="color" 
                  value={t.headerColor || '#111827'} 
                  onChange={e => handleUpdate({ headerColor: e.target.value })}
                  className="w-8 h-8 rounded cursor-pointer border-0 p-0 bg-transparent"
                />
                <span className="text-sm font-mono uppercase" style={{ color: 'var(--text-2)' }}>{t.headerColor || '#111827'}</span>
              </div>
            </div>
            <div className="space-y-2">
              <label className="label">Body Text Color</label>
              <div className="flex items-center gap-3 input w-full">
                <input 
                  type="color" 
                  value={t.textColor || '#111827'} 
                  onChange={e => handleUpdate({ textColor: e.target.value })}
                  className="w-8 h-8 rounded cursor-pointer border-0 p-0 bg-transparent"
                />
                <span className="text-sm font-mono uppercase" style={{ color: 'var(--text-2)' }}>{t.textColor || '#111827'}</span>
              </div>
            </div>
          </div>


          <div className="space-y-2">
            <label className="label">Header Cover Image (1600x400)</label>
            <div className="flex flex-col sm:flex-row gap-6 items-start">
              <label className="flex-1 w-full cursor-pointer rounded-xl border-2 border-dashed flex flex-col items-center justify-center text-center p-6 transition-colors"
                style={{ borderColor: 'var(--border-color)', background: 'var(--surface-2)' }}
                onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--brand)'}
                onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-color)'}
              >
                <input type="file" accept="image/*" className="hidden" onChange={e => handleUpload(e, 'header')} />
                <RiUploadCloud2Line size={28} className="mb-2" style={{ color: 'var(--text-3)' }} />
                <p className="text-sm font-semibold mb-1" style={{ color: 'var(--text-2)' }}>
                  {uploadingHeader ? 'Uploading...' : 'Click to upload cover'}
                </p>
              </label>

              {t.headerPictureUrl && (
                <div className="w-full sm:w-64 h-32 rounded-xl border overflow-hidden relative" style={{ borderColor: 'var(--border-color)' }}>
                  <img src={t.headerPictureUrl} alt="Header Cover" className="w-full h-full object-cover" />
                  <button 
                    onClick={() => handleUpdate({ headerPictureUrl: null })} 
                    className="absolute top-2 right-2 bg-red-500 text-white p-1.5 rounded-full hover:bg-red-600 transition-colors"
                  >
                    <RiCloseCircleFill size={20} />
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* BACKGROUND SECTION */}
      <div className="card p-6 space-y-5">
        <h3 className="text-lg font-bold" style={{ color: 'var(--text-1)' }}>Environment</h3>

        <div className="space-y-6">
          <div className="flex flex-col md:flex-row gap-6">
            <div className="flex-1 space-y-2">
              <label className="label">Background Image</label>
              <div className="flex gap-4 items-start">
                <label className="flex-1 cursor-pointer rounded-xl border-2 border-dashed flex flex-col items-center justify-center text-center p-6 transition-colors"
                  style={{ borderColor: 'var(--border-color)', background: 'var(--surface-2)' }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--brand)'}
                  onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border-color)'}
                >
                  <input type="file" accept="image/*" className="hidden" onChange={e => handleUpload(e, 'bg')} />
                  <RiImageAddLine size={28} className="mb-2" style={{ color: 'var(--text-3)' }} />
                  <span className="text-sm font-medium" style={{ color: 'var(--text-2)' }}>
                    {uploadingBg ? 'Uploading...' : 'Choose image'}
                  </span>
                </label>
                
                {t.backgroundImageUrl && (
                  <div className="w-32 h-32 rounded-xl border overflow-hidden relative shrink-0" style={{ borderColor: 'var(--border-color)' }}>
                    <img src={t.backgroundImageUrl} alt="Background" className="w-full h-full object-cover" />
                    <button 
                      onClick={() => handleUpdate({ backgroundImageUrl: null })} 
                      className="absolute top-2 right-2 bg-red-500 text-white p-1.5 rounded-full hover:bg-red-600 transition-colors"
                    >
                      <RiCloseCircleFill size={20} />
                    </button>
                  </div>
                )}
              </div>
            </div>

            <div className="md:w-64 space-y-2">
              <label className="label">Fallback Color</label>
              <div className="input w-full flex items-center justify-between p-3 h-32">
                <div className="flex flex-col gap-2 items-center w-full justify-center">
                  <input 
                    type="color" 
                    value={t.backgroundColor || '#f9fafb'} 
                    onChange={e => handleUpdate({ backgroundColor: e.target.value })}
                    className="w-12 h-12 rounded cursor-pointer border-0 p-0 bg-transparent"
                  />
                  <span className="text-xs font-mono uppercase" style={{ color: 'var(--text-2)' }}>{t.backgroundColor || '#f9fafb'}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-2 p-4 rounded-xl" style={{ background: 'var(--surface-2)' }}>
            <div className="flex justify-between items-center mb-2">
              <label className="label m-0">Backdrop Dimming</label>
              <span className="text-sm font-semibold" style={{ color: 'var(--brand)' }}>
                {Math.round((t.overlayOpacity ?? 0.5) * 100)}%
              </span>
            </div>
            <p className="text-xs mb-3" style={{ color: 'var(--text-3)' }}>Darkens the background image to keep your questions readable.</p>
            <input 
              type="range" 
              min="0" max="1" step="0.05"
              value={t.overlayOpacity ?? 0.5} 
              onChange={e => handleUpdate({ overlayOpacity: parseFloat(e.target.value) })}
              className="w-full cursor-pointer"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
