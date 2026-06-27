import os
import sys
import json
import re
import hashlib
import pdfplumber

sys.stdout.reconfigure(encoding='utf-8')

pdf_path = r"c:\Users\ak612\Downloads\hermesupsc\previous year question\Topicwise-CSAT-PYQs-2011-2025-1.pdf"
output_dir = r"c:\Users\ak612\Downloads\hermesupsc\upsc-intelligence-system\dataset"

SECTIONS = [
    {
        "name": "Comprehension",
        "question_pages": (4, 81),
        "answer_pages": (82, 115)
    },
    {
        "name": "Interpersonal Skills",
        "question_pages": (116, 116),
        "answer_pages": (117, 117)
    },
    {
        "name": "Logical Reasoning",
        "question_pages": (118, 144),
        "answer_pages": (145, 175)
    },
    {
        "name": "Decision-Making",
        "question_pages": (176, 178),
        "answer_pages": (179, 181)
    },
    {
        "name": "General Mental Ability",
        "question_pages": (182, 189),
        "answer_pages": (190, 202)
    },
    {
        "name": "Basic Numeracy",
        "question_pages": (203, 216),
        "answer_pages": (217, 243)
    },
    {
        "name": "Arithmetic",
        "question_pages": (244, 249),
        "answer_pages": (250, 261)
    },
    {
        "name": "Geometry & Mensuration",
        "question_pages": (262, 263),
        "answer_pages": (264, 267)
    },
    {
        "name": "Permutation & Probability",
        "question_pages": (268, 269),
        "answer_pages": (270, 274)
    },
    {
        "name": "Time and Work / Distance",
        "question_pages": (275, 278),
        "answer_pages": (279, 283)
    },
    {
        "name": "Data Interpretation",
        "question_pages": (284, 293),
        "answer_pages": (294, 301)
    }
]

def extract_columns_from_page(page):
    """Crop left and right halves of a page to extract two-column text cleanly."""
    width = page.width
    height = page.height
    
    left_half = page.within_bbox((0, 0, width/2, height))
    right_half = page.within_bbox((width/2, 0, width, height))
    
    left_text = left_half.extract_text() or ""
    right_text = right_half.extract_text() or ""
    
    return left_text + "\n" + right_text

def parse_questions_text(text, section_name):
    """
    Parse questions, passages, years, and options from the raw page text flow.
    We return a list of parsed question dicts.
    """
    lines = text.split("\n")
    questions = []
    
    current_passage = ""
    in_passage = False
    
    current_q_num = None
    last_q_num = None
    has_completed_q = True
    current_q_text = []
    current_options = {}
    
    # Matching rules
    q_start_re = re.compile(r"^(\d+)\.\s+(.*)")
    option_re = re.compile(r"^\(([a-f])\)\s+(.*)", re.IGNORECASE)
    passage_start_re = re.compile(r"^(Passage\s*(?:-\s*\w+)?\s*$|Directions\s+for\s+the\s+following.*)", re.IGNORECASE)
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        # 1. Detect Passage Boundaries
        if passage_start_re.match(line_stripped):
            if current_q_num is not None:
                # Save previous question
                questions.append({
                    "question_number": current_q_num,
                    "raw_text": "\n".join(current_q_text),
                    "options": current_options,
                    "passage": current_passage if section_name == "Comprehension" else None
                })
                current_q_num = None
                current_q_text = []
                current_options = {}
                has_completed_q = True
            
            in_passage = True
            current_passage = line_stripped
            continue
            
        # 2. Detect Question Starters with range check and completion heuristic
        q_match = q_start_re.match(line_stripped)
        if q_match:
            qn = int(q_match.group(1))
            is_real_q = False
            if last_q_num is None:
                if qn <= 5:
                    is_real_q = True
            else:
                if last_q_num < qn <= last_q_num + 5:
                    if qn > 5 or has_completed_q:
                        is_real_q = True
                    
            if is_real_q:
                if current_q_num is not None:
                    # Save previous question
                    questions.append({
                        "question_number": current_q_num,
                        "raw_text": "\n".join(current_q_text),
                        "options": current_options,
                        "passage": current_passage if section_name == "Comprehension" else None
                    })
                current_q_num = qn
                last_q_num = qn
                has_completed_q = False
                current_q_text = [q_match.group(2)]
                current_options = {}
                in_passage = False
                continue
                
        # 3. Detect Options (handling horizontal options on the same line)
        if current_q_num is not None and re.match(r"^\s*\(([a-f])\)", line_stripped, re.IGNORECASE):
            matches = re.findall(r'\(([a-f])\)\s*(.*?)(?=\s*\([a-f]\)|$)', line_stripped, re.IGNORECASE)
            for m in matches:
                current_options[m[0].lower()] = m[1].strip()
            has_completed_q = True
            continue
            
        # 4. Append to active state
        if in_passage:
            current_passage += "\n" + line_stripped
        elif current_q_num is not None:
            if current_options:
                # Append to last option
                last_lbl = list(current_options.keys())[-1]
                current_options[last_lbl] += " " + line_stripped
            else:
                current_q_text.append(line_stripped)
                
    # Save last question
    if current_q_num is not None:
        questions.append({
            "question_number": current_q_num,
            "raw_text": "\n".join(current_q_text),
            "options": current_options,
            "passage": current_passage if section_name == "Comprehension" else None
        })
        
    return questions

def parse_answers_text(text):
    """
    Parse correct options and detailed explanations from raw page text flow.
    We return a dictionary of parsed answers by question number.
    """
    lines = text.split("\n")
    answers = {}
    
    current_q_num = None
    current_correct = None
    current_explanation = []
    
    # Matches "41. Answer: (d) is correct." or "44. Solution: (c)" or "33. Answer: Option (d) is correct:" or "213. Answer:(b)"
    ans_re = re.compile(r"^(\d+)\.\s+(?:Answer|Solution|Solution|Correct\s+Answer)\s*:?\s*(?:The\s+correct\s+option\s+is\s+option\s+|Option\s+)?\(?([a-d])\)?", re.IGNORECASE)
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        ans_match = ans_re.match(line_stripped)
        if ans_match:
            if current_q_num is not None:
                answers[current_q_num] = {
                    "correct_option": current_correct,
                    "explanation": "\n".join(current_explanation).strip()
                }
            current_q_num = int(ans_match.group(1))
            current_correct = ans_match.group(2).lower()
            # Strip off the matched answer part from the line for explanation
            rest = line_stripped[ans_match.end():].strip()
            current_explanation = [rest] if rest else []
            continue
            
        if current_q_num is not None:
            current_explanation.append(line_stripped)
            
    # Save last answer
    if current_q_num is not None:
        answers[current_q_num] = {
            "correct_option": current_correct,
            "explanation": "\n".join(current_explanation).strip()
        }
        
    return answers

def find_year_in_question(q_obj, year_re):
    # Search in raw_text
    match = year_re.search(q_obj["raw_text"])
    if match:
        return int(match.group(1))
    # Search in options
    for opt_txt in q_obj["options"].values():
        match = year_re.search(opt_txt)
        if match:
            return int(match.group(1))
    return None

def run_pipeline():
    print("="*60)
    print("💎 UPSC CSAT Year-Wise Data Extractor Pipeline")
    print("="*60)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
        
    all_dataset = []
    seen_passage_ids = set()
    year_re = re.compile(r"\(CSAT[\s\-_]*(20\d{2})\)", re.IGNORECASE)
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Loaded CSAT PDF successfully. Total Pages: {len(pdf.pages)}\n")
            
            for section in SECTIONS:
                name = section["name"]
                q_start, q_end = section["question_pages"]
                a_start, a_end = section["answer_pages"]
                
                print(f"📁 Processing Section: {name}")
                print(f"   - Questions: Pages {q_start}-{q_end}")
                print(f"   - Answers  : Pages {a_start}-{a_end}")
                
                # 1. Extract Questions Text
                q_text = ""
                for p in range(q_start - 1, q_end):
                    q_text += extract_columns_from_page(pdf.pages[p]) + "\n"
                    
                # 2. Extract Answers Text
                a_text = ""
                for p in range(a_start - 1, a_end):
                    a_text += extract_columns_from_page(pdf.pages[p]) + "\n"
                    
                # 3. Parse Questions and Answers
                parsed_questions = parse_questions_text(q_text, name)
                parsed_answers = parse_answers_text(a_text)
                
                print(f"   - Extracted: {len(parsed_questions)} questions, {len(parsed_answers)} answers.")
                
                # 4. Synthesize
                joined_count = 0
                current_year = 2025 # starting default for the section
                
                for q_obj in parsed_questions:
                    qn = q_obj["question_number"]
                    
                    # Determine year using our inheritance strategy
                    year = find_year_in_question(q_obj, year_re)
                    if year is not None:
                        current_year = year
                    else:
                        year = current_year
                        
                    # Link answer if available
                    ans_obj = parsed_answers.get(qn)
                    correct_option = ans_obj["correct_option"] if ans_obj else None
                    explanation = ans_obj["explanation"] if ans_obj else None
                    
                    # Clean question text from year labels
                    q_raw = q_obj["raw_text"]
                    cleaned_q = re.sub(r"\(CSAT[\s\-_]*20\d{2}\)", "", q_raw, flags=re.IGNORECASE).strip()
                    
                    # Build list of options matching target schema
                    formatted_options = []
                    for opt_lbl, opt_txt in sorted(q_obj["options"].items()):
                        formatted_options.append({
                            "label": opt_lbl,
                            "text": opt_txt.strip()
                        })
                        
                    # Inject standard options if they are completely empty (due to layout omissions or figure questions)
                    if not formatted_options:
                        if "Manisha" in cleaned_q or "age of Manisha" in cleaned_q:
                            formatted_options = [
                                {"label": "a", "text": "Statement-1 alone is sufficient to Answer the question."},
                                {"label": "b", "text": "Statement-2 alone is sufficient to Answer the question."},
                                {"label": "c", "text": "Both Statement-1 and Statement-2 are sufficient to Answer the Question."},
                                {"label": "d", "text": "Both Statement-1 and Statement-2 are not sufficient to Answer the Question."}
                            ]
                        else:
                            formatted_options = [
                                {"label": "a", "text": "Option (a)"},
                                {"label": "b", "text": "Option (b)"},
                                {"label": "c", "text": "Option (c)"},
                                {"label": "d", "text": "Option (d)"}
                            ]
                        
                    # Deterministic ID
                    question_id = f"CSAT_{year}_{name.upper().replace(' ', '_').replace('&', '_').replace('/', '_')}_{qn}"
                    
                    # Handle passage separation and passage ID
                    passage = q_obj["passage"]
                    passage_id = None
                    if passage:
                        p_hash = hashlib.sha256(passage.encode('utf-8')).hexdigest()[:8]
                        passage_id = f"P{year}_{p_hash}"
                        
                        # Deduplicate passage text: only keep the full text for the first occurrence
                        if passage_id in seen_passage_ids:
                            passage = None
                        else:
                            seen_passage_ids.add(passage_id)
                            
                    item = {
                        "id": question_id,
                        "year": year,
                        "paper": "CSAT",
                        "section": name,
                        "topic": name,
                        "subtopic": "PYQ Extraction",
                        "question_number": qn,
                        "question_type": "arithmetic" if name in ["Arithmetic", "Basic Numeracy"] else "logical_reasoning",
                        "difficulty": "medium",
                        "passage_id": passage_id,
                        "passage": passage,
                        "question": cleaned_q,
                        "options": formatted_options,
                        "correct_option": correct_option,
                        "explanation": explanation,
                        "source": {
                            "exam": "UPSC CSAT",
                            "year": year,
                            "page": q_start, # rough estimate based on section start
                            "pdf_file": "Topicwise-CSAT-PYQs-2011-2025-1.pdf"
                        },
                        "tags": [name.lower().replace(" ", "_"), "upsc", "pyq"]
                    }
                    
                    all_dataset.append(item)
                    joined_count += 1
                    
                print(f"   - Successfully synthesized {joined_count} questions.")
                
    except Exception as e:
        print(f"❌ Error during pipeline execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    print(f"\n📂 Ingested {len(all_dataset)} total questions.")
    
    # Write to year-wise folder structure
    years_data = {}
    for item in all_dataset:
        yr = item["year"]
        if yr not in years_data:
            years_data[yr] = []
        years_data[yr].append(item)
        
    for yr, items in sorted(years_data.items()):
        yr_dir = os.path.join(output_dir, str(yr))
        if not os.path.exists(yr_dir):
            os.makedirs(yr_dir)
            
        # Group by section type to create comprehension.jsonl, reasoning.jsonl, arithmetic.jsonl
        sections_grouped = {
            "comprehension": [],
            "reasoning": [],
            "arithmetic": []
        }
        
        for it in items:
            sec = it["section"].lower()
            if "comprehension" in sec:
                sections_grouped["comprehension"].append(it)
            elif "reasoning" in sec or "logic" in sec or "mental" in sec or "decision" in sec or "interpersonal" in sec:
                sections_grouped["reasoning"].append(it)
            else:
                sections_grouped["arithmetic"].append(it)
                
        for file_key, grouped_items in sections_grouped.items():
            if not grouped_items:
                continue
            file_path = os.path.join(yr_dir, f"{file_key}.jsonl")
            with open(file_path, "w", encoding="utf-8") as f:
                for git in grouped_items:
                    f.write(json.dumps(git, ensure_ascii=False) + "\n")
                    
        print(f"   - Wrote Year {yr}: {len(items)} questions grouped by sections.")
        
    # Write metadata schema
    meta_dir = os.path.join(output_dir, "metadata")
    if not os.path.exists(meta_dir):
        os.makedirs(meta_dir)
        
    # Write unified dataset too for completeness
    unified_path = os.path.join(output_dir, "csat_dataset_all.jsonl")
    with open(unified_path, "w", encoding="utf-8") as f:
        for it in all_dataset:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"\n✅ Created unified CSAT dataset at: {unified_path}")
    print("🎉 All extraction tasks completed successfully.")

if __name__ == "__main__":
    run_pipeline()
