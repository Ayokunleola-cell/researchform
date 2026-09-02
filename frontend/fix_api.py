import re

path = r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\components\surveys\SurveySettings.tsx'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if "import { api } from '../../lib/api';" not in content:
    content = content.replace(
        "import toast from 'react-hot-toast';",
        "import toast from 'react-hot-toast';\nimport { api } from '../../lib/api';"
    )

old_fetch = """    try {
      const res = await fetch(`/api/surveys/${surveyId}/upload-media`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
      });
      const data = await res.json();
      
      if (res.ok) {
        if (type === 'bg') handleUpdate({ backgroundImageUrl: data.url });
        else handleUpdate({ headerPictureUrl: data.url });
        toast.success("Image uploaded successfully");
      } else {
        toast.error(data.detail || "Upload failed");
      }
    } catch (err) {"""

new_axios = """    try {
      const res = await api.post(`/api/surveys/${surveyId}/upload-media`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      
      if (res.data && res.data.url) {
        let url = res.data.url;
        // prepend backend URL because NEXT.JS expects absolute or relative to proxy
        if (url.startsWith('/api/')) {
            url = api.defaults.baseURL + url.replace('/api/', '/');
        } else {
            url = api.defaults.baseURL + url;
        }
        if (type === 'bg') handleUpdate({ backgroundImageUrl: url });
        else handleUpdate({ headerPictureUrl: url });
        toast.success("Image uploaded successfully");
      }
    } catch (err: any) {"""

content = content.replace(old_fetch, new_axios)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
