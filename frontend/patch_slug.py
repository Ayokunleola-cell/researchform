import re

path = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\s\[slug].tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# I need to wrap the main content with the theme container
# 1. Add theme variables to the style prop of the root div.
# 2. Add header picture and text
# 3. Add background overlay
# We will find the return statement of the component

theme_styles = """
  const theme = survey.theme || {};
  const rootStyle = {
    fontFamily: theme.fontFamily === 'Roboto' ? 'Roboto, sans-serif' : 
               theme.fontFamily === 'Merriweather' ? 'Merriweather, serif' : 
               theme.fontFamily === 'Outfit' ? 'Outfit, sans-serif' : 'Inter, sans-serif',
    backgroundColor: theme.backgroundColor || '#f9fafb',
    backgroundImage: theme.backgroundImageUrl ? `url(${theme.backgroundImageUrl})` : 'none',
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundAttachment: 'fixed',
    minHeight: '100vh',
    position: 'relative' as const
  };

  const overlayStyle = {
    position: 'absolute' as const,
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: `rgba(0,0,0,${theme.overlayOpacity ?? 0.5})`,
    zIndex: 0
  };

  const contentContainerStyle = {
    position: 'relative' as const,
    zIndex: 10,
    fontSize: theme.fontSize === 'small' ? '14px' : theme.fontSize === 'large' ? '18px' : '16px'
  };
"""

header_jsx = """
          {theme.headerPictureUrl && (
            <div className="w-full h-40 sm:h-64 mb-6 rounded-t-xl overflow-hidden shadow-sm">
              <img src={theme.headerPictureUrl} alt="Survey Header" className="w-full h-full object-cover" />
            </div>
          )}
          {theme.headerText && (
            <h1 className="text-3xl font-bold mb-6 text-center" style={{ color: theme.headerColor || '#111827' }}>
              {theme.headerText}
            </h1>
          )}
"""

if 'const theme = survey.theme' not in content:
    # Insert theme styles before `return (`
    content = re.sub(r'(return \(\s*<div[^>]*className="min-h-screen[^>]*>)', r'  ' + theme_styles.strip() + r'\n\n  \1', content)
    
    # Update the root div to use rootStyle
    content = re.sub(r'(return \(\s*<div[^>]*)(className="min-h-screen[^"]*")', r'\1\2 style={rootStyle}', content)

    # Insert overlay after root div
    content = re.sub(r'(return \(\s*<div[^>]*style=\{rootStyle\}[^>]*>)', r'\1\n      {theme.backgroundImageUrl && <div style={overlayStyle}></div>}', content)
    
    # Apply contentContainerStyle to the max-w-3xl container
    content = re.sub(r'(<div className="max-w-3xl mx-auto py-12 px-4 sm:px-6 lg:px-8)', r'<div style={contentContainerStyle} className="max-w-3xl mx-auto py-12 px-4 sm:px-6 lg:px-8', content)

    # Insert header_jsx inside the max-w-3xl container, before the first actual content (e.g. before `<div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">`
    content = content.replace('<div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">', header_jsx + '\n          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
