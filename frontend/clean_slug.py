import re

path = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\s\[slug].tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# We want to replace everything from `if (loading || !survey) return` up to `return (` where the main form renders.
# Let's find the start of the rendering section.
start_marker = 'if (loading || !survey) return <div className="flex justify-center items-center h-screen"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div></div>;'

# Let's find where the main rendering starts
end_marker = 'const answered = Object.keys(answers).length;'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers")
    exit(1)

# Here is the clean rendering section
clean_section = """
  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen" style={{ background: 'var(--bg)' }}>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2" style={{ borderColor: 'var(--brand)' }}></div>
      </div>
    );
  }

  const theme = survey?.theme || {};
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

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={rootStyle}>
        {theme.backgroundImageUrl && <div style={overlayStyle}></div>}
        <div className="text-center" style={contentContainerStyle}>
          <div className="bg-white p-8 rounded-2xl shadow-xl max-w-sm w-full mx-4">
            <RiErrorWarningFill size={48} className="mx-auto mb-4" style={{ color: 'var(--danger)' }} />
            <p className="font-display font-bold text-xl mb-2 text-gray-900">{error}</p>
            <p className="text-gray-500">The survey link may be incorrect or the survey has closed.</p>
          </div>
        </div>
      </div>
    );
  }

  if (alreadySubmitted) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={rootStyle}>
        {theme.backgroundImageUrl && <div style={overlayStyle}></div>}
        <div className="text-center max-w-sm px-6 animate-fade-in" style={contentContainerStyle}>
          <div className="bg-white p-8 rounded-2xl shadow-xl w-full mx-4">
            <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6" style={{ background: 'rgba(99,102,241,0.12)' }}>
              <RiErrorWarningFill size={40} style={{ color: 'var(--brand)' }} />
            </div>
            <h1 className="font-display font-bold text-2xl mb-3 text-gray-900">Already Submitted</h1>
            <p className="text-base leading-relaxed text-gray-600">
              Thank you, you have done the survey before.
            </p>
            <p className="text-sm mt-4 text-gray-400">
              Multiple submissions using the same email address are not allowed.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={rootStyle}>
        {theme.backgroundImageUrl && <div style={overlayStyle}></div>}
        <div className="text-center max-w-sm px-6 animate-fade-in" style={contentContainerStyle}>
          <div className="bg-white p-8 rounded-2xl shadow-xl w-full mx-4">
            <div className="w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6" style={{ background: 'rgba(16,185,129,0.12)' }}>
              <RiCheckboxCircleFill size={40} style={{ color: 'var(--success)' }} />
            </div>
            <h1 className="font-display font-bold text-2xl mb-3 text-gray-900">Thank You!</h1>
            <p className="text-sm leading-relaxed text-gray-600">
              Your response to <strong>{survey?.title}</strong> has been recorded successfully.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!survey) return null;

  """

# Wait, `content.find(end_marker)` gives the exact position of `const answered = ...`
new_content = content[:start_idx] + clean_section + content[end_idx:]

# Additionally, let's remove any stray `const theme = survey.theme || {};` that might have been pushed after the end_marker
# Wait, my previous code replaced `if (error) const theme = ...` all the way up to line 405.
# `end_idx` is at line 394 in my python view output:
# 394:   const answered = Object.keys(answers).length;
# But wait, lines 398-405 were ALSO declaring `theme` and `rootStyle`!
# So `clean_section` will be inserted BEFORE line 394.
# Then lines 398-405 will STILL contain `const theme = ...`!
# That will cause "Identifier 'theme' has already been declared".

# So I must also delete the declarations of `theme`, `rootStyle`, `overlayStyle`, `contentContainerStyle` from the part AFTER `end_marker` up to `return (`

final_return_marker = 'return (\n    <div className="min-h-screen"'
final_return_idx = new_content.find(final_return_marker, start_idx + len(clean_section))

if final_return_idx != -1:
    # Delete everything between `const progress = ...` and `return (`
    progress_marker = 'const progress = required > 0 ? Math.round((answered / required) * 100) : 100;'
    progress_idx = new_content.find(progress_marker)
    if progress_idx != -1:
        end_of_progress = progress_idx + len(progress_marker)
        # Delete from end_of_progress to final_return_idx
        new_content = new_content[:end_of_progress] + '\n\n  ' + new_content[final_return_idx:]

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
