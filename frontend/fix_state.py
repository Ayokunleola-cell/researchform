import re

# 1. FIX new.tsx
path_new = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\surveys\new.tsx'
with open(path_new, 'r', encoding='utf-8') as f:
    content_new = f.read()

# Add theme state
if 'const [theme, setTheme]' not in content_new:
    content_new = content_new.replace(
        "const [saving, setSaving] = useState(false);",
        "const [saving, setSaving] = useState(false);\n  const [theme, setTheme] = useState<any>({});"
    )

# Fix JSX props
content_new = content_new.replace("theme={formData.theme}", "theme={theme}")
content_new = content_new.replace("onChange={(theme) => setFormData({...formData, theme})}", "onChange={setTheme}")

# Fix payload
if 'theme,' not in content_new and 'theme:' not in content_new:
    content_new = content_new.replace(
        "status: publish ? 'active' : 'draft',",
        "status: publish ? 'active' : 'draft',\n        theme,"
    )

with open(path_new, 'w', encoding='utf-8') as f:
    f.write(content_new)


# 2. FIX edit.tsx
path_edit = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\surveys\[id]\edit.tsx'
with open(path_edit, 'r', encoding='utf-8') as f:
    content_edit = f.read()

# Add theme state
if 'const [theme, setTheme]' not in content_edit:
    content_edit = content_edit.replace(
        "const [saving, setSaving] = useState(false);",
        "const [saving, setSaving] = useState(false);\n  const [theme, setTheme] = useState<any>({});"
    )

# Fix useEffect
if 'setTheme(sv.data.theme' not in content_edit:
    content_edit = content_edit.replace(
        "setQuestions(qs.data || []);",
        "setQuestions(qs.data || []);\n      setTheme(sv.data.theme || {});"
    )

# Fix JSX props
content_edit = content_edit.replace("theme={survey.theme || {}}", "theme={theme}")
content_edit = content_edit.replace("onChange={(theme) => setSurvey({...survey, theme})}", "onChange={setTheme}")
content_edit = content_edit.replace("surveyId={survey.id}", "surveyId={id as string}")

# Fix payload
if 'theme,' not in content_edit and 'theme:' not in content_edit:
    content_edit = content_edit.replace(
        "require_email: requireEmail,",
        "require_email: requireEmail,\n        theme,"
    )

with open(path_edit, 'w', encoding='utf-8') as f:
    f.write(content_edit)
