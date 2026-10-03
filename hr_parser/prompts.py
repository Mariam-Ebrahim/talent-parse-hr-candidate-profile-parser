from langchain_core.prompts import PromptTemplate

from .schemas import FORMAT_INSTRUCTIONS

CV_TEMPLATE = """You are an HR assistant that parses resumes into structured JSON.

Respond ONLY with one JSON object, formatted as follows:
{format_instructions}

Rules:
- Use only information that appears in the resume. Never invent values.
- If a field is missing, use "" for text or [] for lists.
- "year" is a 4-digit integer.
- "years" uses year numbers only, like "2020-2023" or "2023-Present". Never write month names.
- Put one skill per list item.

<example>
Input:
Jane Doe - jane@mail.com
Education: M.Sc. Physics, Stanford, 2019
Skills: Java, SQL
Experience:
- Engineer at Tesla (2019-2022)

Output:
```json
{{
  "full_name": "Jane Doe",
  "email": "jane@mail.com",
  "education": [{{"degree": "M.Sc. Physics", "institution": "Stanford", "year": 2019}}],
  "skills": ["Java", "SQL"],
  "experience": [{{"role": "Engineer", "company": "Tesla", "years": "2019-2022"}}]
}}
```
</example>

Now extract from this resume:
<resume>
{cv_text}
</resume>
"""

prompt_template = PromptTemplate(
    template=CV_TEMPLATE, input_variables=["cv_text", "format_instructions"]
)


def build_prompt(cv_text: str) -> str:
    return prompt_template.format(cv_text=cv_text, format_instructions=FORMAT_INSTRUCTIONS)
