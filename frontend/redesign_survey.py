import re

path = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\s\[slug].tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Redesign QuestionRenderer inputs (short_text, long_text)
old_short_text = """    case 'short_text':
      return (
        <input
          className="input"
          placeholder="Your answer..."
          value={value || ''}
          onChange={e => onChange(e.target.value)}
        />
      );"""

new_short_text = """    case 'short_text':
      return (
        <input
          className="w-full py-2 text-base transition-colors focus:outline-none"
          style={{ border: 'none', borderBottom: '1px solid var(--border)', borderRadius: 0, background: 'transparent' }}
          placeholder="Your answer"
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          onFocus={e => e.target.style.borderBottom = '2px solid var(--brand)'}
          onBlur={e => e.target.style.borderBottom = '1px solid var(--border)'}
        />
      );"""
content = content.replace(old_short_text, new_short_text)

old_long_text = """    case 'long_text':
      return (
        <textarea
          className="input"
          rows={4}
          placeholder="Your answer..."
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          style={{ resize: 'vertical' }}
        />
      );"""

new_long_text = """    case 'long_text':
      return (
        <textarea
          className="w-full py-2 text-base transition-colors focus:outline-none"
          rows={1}
          placeholder="Your answer"
          value={value || ''}
          onChange={e => {
            e.target.style.height = 'auto';
            e.target.style.height = e.target.scrollHeight + 'px';
            onChange(e.target.value);
          }}
          onFocus={e => e.target.style.borderBottom = '2px solid var(--brand)'}
          onBlur={e => e.target.style.borderBottom = '1px solid var(--border)'}
          style={{ border: 'none', borderBottom: '1px solid var(--border)', borderRadius: 0, background: 'transparent', resize: 'none', overflow: 'hidden', minHeight: '32px' }}
        />
      );"""
content = content.replace(old_long_text, new_long_text)

# Also fix number and date to use similar style
old_number = """    case 'number':
      return (
        <input
          type="number"
          className="input w-48"
          placeholder="0"
          value={value || ''}
          onChange={e => onChange(+e.target.value)}
        />
      );"""

new_number = """    case 'number':
      return (
        <input
          type="number"
          className="w-48 py-2 text-base transition-colors focus:outline-none"
          style={{ border: 'none', borderBottom: '1px solid var(--border)', borderRadius: 0, background: 'transparent' }}
          placeholder="0"
          value={value || ''}
          onChange={e => onChange(+e.target.value)}
          onFocus={e => e.target.style.borderBottom = '2px solid var(--brand)'}
          onBlur={e => e.target.style.borderBottom = '1px solid var(--border)'}
        />
      );"""
content = content.replace(old_number, new_number)

old_date = """    case 'date':
      return (
        <input
          type="date"
          className="input w-56"
          value={value || ''}
          onChange={e => onChange(e.target.value)}
        />
      );"""

new_date = """    case 'date':
      return (
        <input
          type="date"
          className="w-56 py-2 text-base transition-colors focus:outline-none"
          style={{ border: 'none', borderBottom: '1px solid var(--border)', borderRadius: 0, background: 'transparent' }}
          value={value || ''}
          onChange={e => onChange(e.target.value)}
          onFocus={e => e.target.style.borderBottom = '2px solid var(--brand)'}
          onBlur={e => e.target.style.borderBottom = '1px solid var(--border)'}
        />
      );"""
content = content.replace(old_date, new_date)

# 2. Add header image and the required asterisk marker to the main render
# Look for the section inside max-w-3xl

main_header_regex = re.compile(r'(<div className="max-w-3xl mx-auto px-4 sm:px-6 pt-10">.*?)(<div\s+className="rounded-2xl p-8 sm:p-12 mb-8 shadow-sm relative overflow-hidden".*?>)(.*?)(</p>\n\s*</div>)', re.DOTALL)

match = main_header_regex.search(content)
if match:
    # We want to inject the header image right before the Title Card
    part1 = match.group(1) # container start
    title_card_start = match.group(2) # div start for title card
    title_card_inner = match.group(3) # inside the title card
    part4 = match.group(4) # closing tag of title card (Wait, it might be the closing of <p>)

    # Let's do a more robust string replacement
    
# Actually, let's just find the exact string
old_layout_header = """      <div className="max-w-3xl mx-auto px-4 sm:px-6 pt-10">
        {/* Header Card */}
        <div 
          className="rounded-2xl p-8 sm:p-12 mb-8 shadow-sm relative overflow-hidden" 
          style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          {/* Decorative accent top border */}
          <div className="absolute top-0 left-0 right-0 h-2" style={{ background: 'linear-gradient(90deg, var(--brand), #8b5cf6, #ec4899)' }} />
          
          <p className="text-xs font-bold tracking-widest mb-3 uppercase" style={{ color: 'var(--brand)' }}>Research Survey</p>
          <h1 className="font-display font-bold text-3xl sm:text-4xl mb-4" style={{ color: 'var(--text)', lineHeight: 1.2 }}>{survey?.title}</h1>
          {survey?.description && (
            <p className="text-base sm:text-lg leading-relaxed" style={{ color: 'var(--text-2)' }}>{survey.description}</p>
          )}
        </div>"""

new_layout_header = """      <div className="max-w-3xl mx-auto px-4 sm:px-6 pt-10">
        {/* Header Image Banner (Like Google Forms) */}
        {surveyTheme.headerPictureUrl && (
          <div className="w-full h-48 sm:h-64 mb-4 rounded-t-2xl overflow-hidden shadow-sm" style={{ border: '1px solid var(--border)' }}>
            <img src={surveyTheme.headerPictureUrl} alt="Survey Header" className="w-full h-full object-cover" />
          </div>
        )}
        
        {/* Header Card */}
        <div 
          className="rounded-b-2xl rounded-t-none p-8 sm:p-12 mb-8 shadow-sm relative overflow-hidden" 
          style={{ 
            background: 'var(--surface)', 
            border: '1px solid var(--border)',
            borderTop: 'none',
            borderRadius: surveyTheme.headerPictureUrl ? '0 0 1rem 1rem' : '1rem' 
          }}
        >
          {/* Decorative accent top border */}
          <div className="absolute top-0 left-0 right-0 h-2" style={{ background: 'linear-gradient(90deg, var(--brand), #8b5cf6, #ec4899)' }} />
          
          <h1 className="font-display font-bold text-3xl sm:text-4xl mb-4" style={{ color: 'var(--text)', lineHeight: 1.2 }}>{survey?.title}</h1>
          {survey?.description && (
            <p className="text-base sm:text-lg leading-relaxed mb-6" style={{ color: 'var(--text-2)' }}>{survey.description}</p>
          )}
          
          <div className="pt-4 mt-2" style={{ borderTop: '1px solid var(--border)' }}>
            <p className="text-sm font-medium" style={{ color: 'var(--danger)' }}>* Indicates required question</p>
          </div>
        </div>"""

content = content.replace(old_layout_header, new_layout_header)

# Make the cards look more like the screenshot (pure white, distinct border)
old_card = """              <div 
                key={q.id} 
                className="card p-6 sm:p-8 animate-slide-up shadow-sm transition-all hover:shadow-md" 
                style={{ animationDelay: `${i * 0.05}s`, border: '1px solid var(--border)' }}
              >"""

new_card = """              <div 
                key={q.id} 
                className="p-6 sm:p-8 animate-slide-up transition-all hover:shadow-md" 
                style={{ 
                  animationDelay: `${i * 0.05}s`, 
                  border: '1px solid var(--border)',
                  background: 'var(--surface)',
                  borderRadius: '0.75rem',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                }}
              >"""

content = content.replace(old_card, new_card)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
