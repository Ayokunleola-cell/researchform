import re

path = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\surveys\new.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Import
if 'SurveySettings' not in content:
    content = content.replace("import AppLayout from '../../components/layout/AppLayout';", "import AppLayout from '../../components/layout/AppLayout';\nimport SurveySettings from '../../components/surveys/SurveySettings';")

# Add theme to initial formData
if 'theme: {}' not in content:
    content = re.sub(r'(const \[formData, setFormData\] = useState<any>\(\{)', r'\1\n    theme: {},', content)

# Change step state
content = content.replace("useState<'meta' | 'build'>('meta')", "useState<'meta' | 'build' | 'settings'>('meta')")

# Change mapping array
content = content.replace("(['meta', 'build'] as const).map", "(['meta', 'build', 'settings'] as const).map")
content = content.replace("s === 'meta' ? 'Survey Info' : 'Build Questions'", "s === 'meta' ? 'Survey Info' : s === 'build' ? 'Build Questions' : 'Settings'")

# Render SurveySettings
settings_jsx = """
        {step === 'settings' && (
          <div className="fade-in">
            <div className="mb-6 flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                  <RiEqualizerFill className="text-brand" />
                  Survey Settings
                </h2>
                <p className="text-gray-500 mt-1">Customize the look and feel of your survey.</p>
              </div>
              <button 
                onClick={handleSave}
                disabled={saving}
                className="btn btn-primary"
              >
                {saving ? <RiLoader4Line className="animate-spin" /> : <RiSave3Fill />}
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
if "step === 'settings'" not in content:
    # insert before the final closing div of the main content area
    content = content.replace('      </AppLayout>', settings_jsx + '\n      </AppLayout>')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
