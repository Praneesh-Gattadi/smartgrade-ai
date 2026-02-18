import json, re
from groq import Groq

class AnswerEvaluator:
    STRICTNESS_RULES = {
        "Lenient": """
- Award 80-100% for answers showing basic understanding, even if incomplete
- Award 60-80% for partially correct answers with some key concepts
- Award 40-60% for vague answers that touch on the topic
- Only give 0-40% for completely wrong or off-topic answers""",
        
        "Moderate": """
- Award 80-100% only for well-explained answers covering main concepts
- Award 60-80% for correct but shallow explanations
- Award 40-60% for incomplete answers missing key points
- Award 20-40% for minimal understanding
- Give 0-20% for wrong or off-topic answers""",
        
        "Strict": """
- Award 80-100% ONLY for complete, precise, well-detailed answers
- Award 60-80% for mostly correct but lacking some depth or examples
- Award 40-60% for partially correct with significant gaps
- Award 20-40% for weak understanding with major errors
- Give 0-20% for incomplete or incorrect answers"""
    }

    def __init__(self, api_key, model="llama-3.3-70b-versatile", strictness="Moderate", partial_credit=True):
        self.client         = Groq(api_key=api_key)
        self.model          = model
        self.strictness     = strictness
        self.partial_credit = partial_credit

    def evaluate(self, question_paper, answer_sheet):
        partial_note = "Award partial marks proportionally based on similarity score." if self.partial_credit else "Award FULL marks if similarity ≥ 70%, otherwise give ZERO."
        
        prompt = f"""You are an expert examiner evaluating student answers.

STRICTNESS MODE: {self.strictness}
{self.STRICTNESS_RULES[self.strictness]}

PARTIAL CREDIT: {partial_note}

QUESTION PAPER:
{question_paper}

STUDENT ANSWER SHEET:
{answer_sheet}

INSTRUCTIONS:
1. Parse questions (detect marks like "(5 marks)" or "[3]", default 5)
2. Match each question to student's answer
3. Assign similarity_score (0-100) following the {self.strictness} rules above
4. Calculate marks: (similarity_score / 100) × max_marks

Respond ONLY with valid JSON — no markdown, no extra text:

{{
  "total_earned": <number>,
  "total_max": <number>,
  "overall_feedback": "<2-3 sentence summary>",
  "questions": [{{
    "question_number": 1,
    "question": "<text>",
    "max_marks": <number>,
    "student_answer": "<text>",
    "earned": <decimal>,
    "similarity_score": <0-100 following {self.strictness} rules>,
    "feedback": "<one line>",
    "key_points_covered": ["<pt>"],
    "missing_points": ["<pt>"]
  }}]
}}"""
        try:
            raw  = self.client.chat.completions.create(
                model=self.model, 
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=4096
            ).choices[0].message.content
            raw  = re.sub(r"```(?:json)?", "", raw).strip().strip("`")
            data = json.loads(raw)
            qs   = data.get("questions", [])
            
            # Recalculate to ensure consistency
            total_earned = 0
            for q in qs:
                sim   = q.get("similarity_score", 0)
                max_m = q.get("max_marks", 5)
                if self.partial_credit:
                    earned = round((sim / 100) * max_m, 1)
                else:
                    earned = max_m if sim >= 70 else 0
                q["earned"] = earned
                total_earned += earned
            
            data["total_max"]    = sum(q.get("max_marks", 5) for q in qs)
            data["total_earned"] = round(total_earned, 1)
            return data
        except Exception as e:
            return {"error": str(e)}