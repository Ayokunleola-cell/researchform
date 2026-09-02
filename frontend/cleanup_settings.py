import re

files = [
    (r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\surveys\new.tsx', '"new"'),
    (r'C:\Users\HP\Documents\ResearchForm_Codebase\researchform\frontend\src\pages\surveys\[id]\edit.tsx', '{id as string}')
]

for path, survey_id_prop in files:
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find ALL instances of `{step === 'settings' && (` up to `)}` and remove them
    # Note: re.sub with DOTALL and greedy match might delete too much if there are other `)}`
    # Instead, we will find it exactly by finding the index.
    
    while "{step === 'settings' && (" in content:
        start_idx = content.find("{step === 'settings' && (")
        # Find the matching `)}`
        end_idx = content.find(")}", start_idx) + 2
        # But wait, there might be nested `)}`. Since our block is simple, `)}` usually closes the block.
        # Let's ensure we find the block that ends right before `</AppLayout>` or similar.
        # Actually, since we know what it looks like, let's just use regex with non-greedy match.
        content = re.sub(r'\{step === \'settings\' && \([\s\S]*?\)\}', '', content)

    # Now append the correct block right before the final `</AppLayout>`
    # The user wants to remove the title and move the save button below.
    correct_block = """        {step === 'settings' && (
          <div className="fade-in max-w-4xl mx-auto">
            <SurveySettings 
              theme={theme} 
              onChange={setTheme} 
              surveyId=""" + survey_id_prop + """ 
            />
            <div className="mt-8 flex justify-end">
              <button 
                onClick={handleSave}
                disabled={saving}
                className="btn btn-primary"
              >
                Save
              </button>
            </div>
          </div>
        )}"""

    # insert before `</AppLayout>`
    # Find the last occurrence of `</AppLayout>`
    parts = content.rsplit('</AppLayout>', 1)
    if len(parts) == 2:
        content = parts[0] + correct_block + '\n    </AppLayout>' + parts[1]

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
