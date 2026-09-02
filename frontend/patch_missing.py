import re

# Fix new.tsx
path_new = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\surveys\new.tsx'
with open(path_new, 'r', encoding='utf-8') as f:
    content_new = f.read()

settings_jsx_new = """
        {step === 'settings' && (
          <div className="fade-in">
            <div className="mb-6 flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                  Survey Settings
                </h2>
                <p className="text-gray-500 mt-1">Customize the look and feel of your survey.</p>
              </div>
              <button 
                onClick={handleSave}
                disabled={saving}
                className="btn btn-primary"
              >
                Save Survey
              </button>
            </div>
            <SurveySettings 
              theme={formData.theme} 
              onChange={(theme) => setFormData({...formData, theme})} 
              surveyId="new" 
            />
          </div>
        )}
"""
if "step === 'settings'" not in content_new:
    content_new = content_new.replace('    </AppLayout>', settings_jsx_new + '\n    </AppLayout>')
    with open(path_new, 'w', encoding='utf-8') as f:
        f.write(content_new)

# Fix edit.tsx
path_edit = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\surveys\[id]\edit.tsx'
with open(path_edit, 'r', encoding='utf-8') as f:
    content_edit = f.read()

settings_jsx_edit = """
        {step === 'settings' && (
          <div className="fade-in">
            <div className="mb-6 flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                  Survey Settings
                </h2>
                <p className="text-gray-500 mt-1">Customize the look and feel of your survey.</p>
              </div>
              <button 
                onClick={handleSave}
                disabled={saving}
                className="btn btn-primary"
              >
                Save Survey
              </button>
            </div>
            <SurveySettings 
              theme={survey.theme || {}} 
              onChange={(theme) => setSurvey({...survey, theme})} 
              surveyId={survey.id} 
            />
          </div>
        )}
"""
if "step === 'settings'" not in content_edit:
    content_edit = content_edit.replace('    </AppLayout>', settings_jsx_edit + '\n    </AppLayout>')
    with open(path_edit, 'w', encoding='utf-8') as f:
        f.write(content_edit)
