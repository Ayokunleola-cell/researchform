import re

path = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\components\surveys\SurveySettings.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove the headers object from api.post
old_post = """    try {
      const res = await api.post(`/surveys/${surveyId}/upload-media`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });"""

new_post = """    try {
      const res = await api.post(`/surveys/${surveyId}/upload-media`, formData);"""

content = content.replace(old_post, new_post)

# 2. Improve error logging
old_catch = """    } catch (err: any) {
      toast.error("Upload failed");
    } finally {"""

new_catch = """    } catch (err: any) {
      console.error("Upload Error:", err);
      toast.error(err?.response?.data?.detail || err?.message || "Upload failed");
    } finally {"""

content = content.replace(old_catch, new_catch)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
