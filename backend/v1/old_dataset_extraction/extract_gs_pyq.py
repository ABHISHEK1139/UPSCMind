import os
import sys
import json
import re
import hashlib
import pdfplumber

sys.stdout.reconfigure(encoding='utf-8')

prelims_pdf_path = r"c:\Users\ak612\Downloads\hermesupsc\previous year question\Previous-Papers-Prelims-GS-Topicwise-English-1.pdf"
mains_pdf_path = r"c:\Users\ak612\Downloads\hermesupsc\previous year question\MAINS-PAPER-GS-YEAR-WISE_2013-2025.pdf"
output_dir = r"c:\Users\ak612\Downloads\hermesupsc\upsc-intelligence-system\dataset"

def extract_columns_from_page(page, clean_mains=False):
    """Crop left and right halves of a page to extract two-column text cleanly and remove headers/footers."""
    width = page.width
    height = page.height
    
    left_half = page.within_bbox((0, 0, width/2, height))
    right_half = page.within_bbox((width/2, 0, width, height))
    
    left_text = left_half.extract_text() or ""
    right_text = right_half.extract_text() or ""
    
    if clean_mains:
        # Clean Mains-specific headers and footers to keep text flow continuous
        clean_patterns = [
            r"Previous\s+Year\s+Questions\s*\(\d{4}\)\s*\d*",
            r"\d+\s+Previous\s+Year\s+Questions\s*\(\d{4}\)",
            r"UPSC\s+MAINS\s+GS\s+PAPER\s+[I|V|X]+",
            r"ANSWERS\s+AND\s+EXPLANATION",
            r"unacademy\.com\s*\|\s*Download\s+the\s+Unacademy\s+app",
            r"Give\s+your\s+feedback\s+here:\s*Link",
            r"S\s+GS\s+PAPER\s+I",
            r"XPLANATION",
            r"^\s*\d+\s*$" # standalone page numbers
        ]
        for pat in clean_patterns:
            left_text = re.sub(pat, "", left_text, flags=re.IGNORECASE)
            right_text = re.sub(pat, "", right_text, flags=re.IGNORECASE)
            
    return left_text.strip(), right_text.strip()

def parse_prelims_toc(pdf):
    """Parse Prelims Table of Contents dynamically."""
    topics = []
    current_subject = "General Studies"
    
    for idx in range(2, 6):
        text = pdf.pages[idx].extract_text()
        lines = text.split("\n")
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or line_stripped == "Content":
                continue
            
            if line_stripped in [
                "Modern India", "Ancient India", "Medieval India", "Art & Culture",
                "World Geography", "Indian Geography", "Environment & Ecology and Disaster Management",
                "Indian Polity and Governance", "International Relations", "Indian Economy",
                "Science & Tech and Basic Science", "Current Affairs and Miscellaneous"
            ]:
                current_subject = line_stripped
                continue
                
            match = re.match(r"^(?:\d+\.\s+)?(.*?)\s+(\d+)\-(\d+)$", line_stripped)
            if match:
                topics.append({
                    "subject": current_subject,
                    "topic": match.group(1).strip(),
                    "start_page": int(match.group(2)),
                    "end_page": int(match.group(3))
                })
                
    return topics

def parse_mains_toc(pdf):
    """Parse Mains Table of Contents dynamically, resolving 2025 typos."""
    topics = []
    for idx in range(2, 5):
        text = pdf.pages[idx].extract_text()
        lines = text.split("\n")
        
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or "Table of Contents" in line_stripped or "unacademy.com" in line_stripped or "feedback" in line_stripped:
                continue
                
            match = re.search(r"(\d+)\.\s+(20\d{2})\s+UPSC\s+MAINS\s+GS\s+PAPER\s+([I|V|X]+)\s+(\d+)", line_stripped, re.IGNORECASE)
            if match:
                topics.append({
                    "year": int(match.group(2)),
                    "paper": f"Mains-GS-{match.group(3)}",
                    "start_page": int(match.group(4))
                })
                
    topics = sorted(topics, key=lambda x: x["start_page"])
    for i in range(len(topics)):
        if i < len(topics) - 1:
            topics[i]["end_page"] = topics[i+1]["start_page"] - 1
        else:
            topics[i]["end_page"] = len(pdf.pages)
            
    return topics

def parse_prelims_questions_text(text):
    """Parse multiple choice questions from page text cleanly."""
    lines = text.split("\n")
    questions = []
    
    current_q_num = None
    last_q_num = None
    has_completed_q = True
    current_q_text = []
    current_options = {}
    
    q_start_re = re.compile(r"^(\d+)\.\s+(.*)")
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
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
                    questions.append({
                        "question_number": current_q_num,
                        "raw_text": "\n".join(current_q_text),
                        "options": current_options
                    })
                current_q_num = qn
                last_q_num = qn
                has_completed_q = False
                current_q_text = [q_match.group(2)]
                current_options = {}
                continue
                
        if current_q_num is not None and re.match(r"^\s*\(([a-f])\)", line_stripped, re.IGNORECASE):
            matches = re.findall(r'\(([a-f])\)\s*(.*?)(?=\s*\([a-f]\)|$)', line_stripped, re.IGNORECASE)
            for m in matches:
                current_options[m[0].lower()] = m[1].strip()
            has_completed_q = True
            continue
            
        if current_q_num is not None:
            if current_options:
                last_lbl = list(current_options.keys())[-1]
                current_options[last_lbl] += " " + line_stripped
            else:
                current_q_text.append(line_stripped)
                
    if current_q_num is not None:
        questions.append({
            "question_number": current_q_num,
            "raw_text": "\n".join(current_q_text),
            "options": current_options
        })
        
    return questions

def parse_prelims_answers_text(text):
    """Parse MCQ answers and explanations."""
    lines = text.split("\n")
    answers = {}
    
    current_q_num = None
    current_correct = None
    current_explanation = []
    
    ans_re = re.compile(r"^(\d+)\.\s+(?:Answer|Solution|Solution:|Correct\s+Answer)\s*:?\s*(?:The\s+correct\s+option\s+is\s+option\s+|Option\s+)?\(?([a-dXx])\)?", re.IGNORECASE)
    
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
            current_correct = ans_match.group(2).upper()
            rest = line_stripped[ans_match.end():].strip()
            current_explanation = [rest] if rest else []
            continue
            
        if current_q_num is not None:
            current_explanation.append(line_stripped)
            
    if current_q_num is not None:
        answers[current_q_num] = {
            "correct_option": current_correct,
            "explanation": "\n".join(current_explanation).strip()
        }
        
    return answers

def run_extraction():
    print("="*60)
    print("💎 UPSC GS Solved PYQ Ingest & Extraction Pipeline")
    print("="*60)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    prelims_all = []
    mains_all = []
    
    # -------------------------------------------------------------
    # STAGE 1: Extract Solved Prelims GS Questions
    # -------------------------------------------------------------
    try:
        with pdfplumber.open(prelims_pdf_path) as pdf:
            print("📁 STAGE 1: Extracting Solved Prelims GS MCQs...")
            topics = parse_prelims_toc(pdf)
            print(f"   - Successfully discovered {len(topics)} Prelims topics.")
            
            year_re = re.compile(r"\((20\d{2})\)")
            
            for t_obj in topics:
                subject = t_obj["subject"]
                topic_name = t_obj["topic"]
                start_p = t_obj["start_page"]
                end_p = t_obj["end_page"]
                
                pdf_start = start_p + 6
                pdf_end = end_p + 6
                
                q_columns = []
                a_columns = []
                in_explanation = False
                explanation_header_re = re.compile(r"^\s*(?:[A-Za-z0-9\s,&]+-)?Explanation\s*$", re.IGNORECASE)
                
                for p_num in range(pdf_start - 1, pdf_end):
                    left, right = extract_columns_from_page(pdf.pages[p_num])
                    
                    if explanation_header_re.search(left):
                        in_explanation = True
                    if in_explanation:
                        a_columns.append(left)
                    else:
                        q_columns.append(left)
                        
                    if explanation_header_re.search(right):
                        in_explanation = True
                    if in_explanation:
                        a_columns.append(right)
                    else:
                        q_columns.append(right)
                        
                q_raw = "\n".join(q_columns)
                a_raw = "\n".join(a_columns)
                
                parsed_q = parse_prelims_questions_text(q_raw)
                parsed_a = parse_prelims_answers_text(a_raw)
                
                current_year = 2025
                for q_item in parsed_q:
                    qn = q_item["question_number"]
                    ans_item = parsed_a.get(qn)
                    
                    raw_q = q_item["raw_text"]
                    year_match = year_re.search(raw_q)
                    if year_match:
                        current_year = int(year_match.group(1))
                        year = current_year
                    else:
                        opt_yr = None
                        for opt_t in q_item["options"].values():
                            m = year_re.search(opt_t)
                            if m:
                                opt_yr = int(m.group(1))
                                break
                        year = opt_yr if opt_yr else current_year
                        
                    cleaned_q = re.sub(r"\((20\d{2})\)", "", raw_q).strip()
                    if year < 2011:
                        continue
                        
                    formatted_options = []
                    for opt_lbl, opt_txt in sorted(q_item["options"].items()):
                        formatted_options.append({
                            "label": opt_lbl,
                            "text": opt_txt.strip()
                        })
                        
                    if not formatted_options:
                        formatted_options = [
                            {"label": "a", "text": "Option (a)"},
                            {"label": "b", "text": "Option (b)"},
                            {"label": "c", "text": "Option (c)"},
                            {"label": "d", "text": "Option (d)"}
                        ]
                        
                    correct_option = ans_item["correct_option"] if ans_item else None
                    explanation = ans_item["explanation"] if ans_item else None
                    
                    topic_hash = hashlib.sha256(topic_name.encode('utf-8')).hexdigest()[:8]
                    question_id = f"PRELIMS_{year}_{subject.upper().replace(' ', '_').replace('&', '_')}_{topic_hash}_{qn}"
                    
                    item = {
                        "id": question_id,
                        "year": year,
                        "paper": "Prelims-GS",
                        "section": subject,
                        "topic": topic_name,
                        "subtopic": topic_name,
                        "question_number": qn,
                        "question_type": "multiple_choice",
                        "difficulty": "medium",
                        "passage_id": None,
                        "passage": None,
                        "question": cleaned_q,
                        "options": formatted_options,
                        "correct_option": correct_option,
                        "explanation": explanation,
                        "source": {
                            "exam": "UPSC Prelims",
                            "year": year,
                            "page": pdf_start,
                            "pdf_file": "Previous-Papers-Prelims-GS-Topicwise-English-1.pdf"
                        },
                        "tags": ["prelims", subject.lower().replace(" ", "_"), topic_name.lower().replace(" ", "_")]
                    }
                    prelims_all.append(item)
                    
            print(f"   - Successfully parsed and validated {len(prelims_all)} Prelims questions.")
            
    except Exception as e:
        print(f"❌ Error during Prelims PDF extraction: {e}")
        sys.exit(1)
        
    # -------------------------------------------------------------
    # STAGE 2: Extract Solved Mains GS Questions & Answers
    # -------------------------------------------------------------
    try:
        with pdfplumber.open(mains_pdf_path) as pdf:
            print("\n📁 STAGE 2: Extracting Solved Mains GS Descriptive Questions & Answers...")
            mains_topics = parse_mains_toc(pdf)
            print(f"   - Successfully discovered {len(mains_topics)} Mains GS Papers.")
            
            for m_t in mains_topics:
                yr = m_t["year"]
                paper = m_t["paper"]
                start_p = m_t["start_page"]
                end_p = m_t["end_page"]
                
                print(f"👉 Parsing Solved [{yr} -> {paper}] (Pages {start_p} to {end_p})")
                
                # Extract cleaned text flow across pages
                text_flow = ""
                for p_num in range(start_p - 1, end_p):
                    left, right = extract_columns_from_page(pdf.pages[p_num], clean_mains=True)
                    text_flow += left + "\n" + right + "\n"
                    
                # Split by question numbers
                raw_blocks = re.split(r'\n(?=Q?\d+\.)', text_flow)
                
                # Merge continuation blocks that do not contain "Answer:" (sub-lists/bullet points)
                blocks = []
                for b in raw_blocks:
                    b_stripped = b.strip()
                    if not b_stripped:
                        continue
                    if re.search(r'\bAnswer\s*:?', b_stripped, re.IGNORECASE):
                        blocks.append(b_stripped)
                    else:
                        if blocks:
                            blocks[-1] += "\n" + b_stripped
                        else:
                            blocks.append(b_stripped)
                            
                for b in blocks:
                    q_match = re.match(r"^Q?(\d+)\.\s*(.*)", b, re.DOTALL)
                    if q_match:
                        qn = int(q_match.group(1))
                        rest = q_match.group(2)
                        
                        parts = re.split(r'\nAnswer\s*:?\s*', rest, maxsplit=1, flags=re.IGNORECASE)
                        q_text = parts[0].strip()
                        ans_text = parts[1].strip() if len(parts) > 1 else None
                        
                        # Clean word counts
                        q_clean = re.sub(r"\(\s*Answer\s+in\s+\d+\s+words\s*\)", "", q_text, flags=re.I)
                        q_clean = re.sub(r"\(\s*\d+\s+words\s*\)", "", q_clean, flags=re.I).strip()
                        
                        # Only keep valid questions (skip header matches and empty answers)
                        if len(q_clean) < 10 or not ans_text:
                            continue
                            
                        # Deterministic ID
                        question_id = f"MAINS_{yr}_{paper.upper().replace('-', '_')}_{qn}"
                        
                        item = {
                            "id": question_id,
                            "year": yr,
                            "paper": paper,
                            "section": "General Studies",
                            "topic": paper,
                            "subtopic": "Mains Solutions",
                            "question_number": qn,
                            "question_type": "descriptive",
                            "difficulty": "medium",
                            "passage_id": None,
                            "passage": None,
                            "question": q_clean,
                            "options": [], # Descriptive questions have no options
                            "correct_option": None,
                            "explanation": ans_text, # descriptive solved answer goes here
                            "source": {
                                "exam": "UPSC Mains",
                                "year": yr,
                                "page": start_p,
                                "pdf_file": "MAINS-PAPER-GS-YEAR-WISE_2013-2025.pdf"
                            },
                            "tags": ["mains", paper.lower().replace("-", "_")]
                        }
                        mains_all.append(item)
                        
            print(f"   - Successfully parsed and solved {len(mains_all)} Mains questions.")
            
    except Exception as e:
        print(f"❌ Error during Mains PDF extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    # -------------------------------------------------------------
    # STAGE 3: Save and split year-wise folders
    # -------------------------------------------------------------
    print("\n📁 STAGE 3: Splitting and writing datasets to target year-wise folders...")
    
    # Save unified Prelims GS and Mains GS datasets
    with open(os.path.join(output_dir, "prelims_gs_all.jsonl"), "w", encoding="utf-8") as f:
        for item in prelims_all:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    with open(os.path.join(output_dir, "mains_gs_all.jsonl"), "w", encoding="utf-8") as f:
        for item in mains_all:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    # Group by year
    years_data = {}
    for yr in range(2011, 2026):
        years_data[yr] = {"prelims": [], "mains": []}
        
    for item in prelims_all:
        yr = item["year"]
        if yr in years_data:
            years_data[yr]["prelims"].append(item)
            
    for item in mains_all:
        yr = item["year"]
        if yr in years_data:
            years_data[yr]["mains"].append(item)
            
    for yr, data in sorted(years_data.items()):
        yr_dir = os.path.join(output_dir, str(yr))
        if not os.path.exists(yr_dir):
            os.makedirs(yr_dir)
            
        # Write prelims_gs.jsonl
        if data["prelims"]:
            with open(os.path.join(yr_dir, "prelims_gs.jsonl"), "w", encoding="utf-8") as f:
                for item in data["prelims"]:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    
        # Write mains_gs.jsonl
        if data["mains"]:
            with open(os.path.join(yr_dir, "mains_gs.jsonl"), "w", encoding="utf-8") as f:
                for item in data["mains"]:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
                    
        print(f"   - Wrote Year {yr}: {len(data['prelims'])} Prelims, {len(data['mains'])} Mains questions.")
        
    print("\n🎉 Solved GS PYQ Extraction Pipeline executed successfully.")

if __name__ == "__main__":
    run_extraction()
