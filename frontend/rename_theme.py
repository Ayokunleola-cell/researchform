path = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\s\[slug].tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Rename the constant declaration
content = content.replace("const theme = survey?.theme || {};", "const surveyTheme = survey?.theme || {};")

# 2. Replace the usages of `theme.`
content = content.replace("theme.fontFamily", "surveyTheme.fontFamily")
content = content.replace("theme.backgroundColor", "surveyTheme.backgroundColor")
content = content.replace("theme.backgroundImageUrl", "surveyTheme.backgroundImageUrl")
content = content.replace("theme.overlayOpacity", "surveyTheme.overlayOpacity")
content = content.replace("theme.fontSize", "surveyTheme.fontSize")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
