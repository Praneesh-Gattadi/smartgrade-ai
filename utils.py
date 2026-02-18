import base64


# ── Shared vision OCR helper ──────────────────────────────────────────────────

def _ocr_image_bytes(img_bytes, mime_type="image/jpeg", api_key=None, context=""):
    """
    OCR a raw image (bytes).  Tries Groq Vision first, then Tesseract.
    Returns extracted text string.
    """
    b64 = base64.b64encode(img_bytes).decode("utf-8")

    # Primary: Groq Vision LLM ------------------------------------------------
    if api_key:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)
            ctx_note = f" ({context})" if context else ""
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                        },
                        {
                            "type": "text",
                            "text": (
                                f"You are an expert OCR assistant specialised in reading handwritten text{ctx_note}. "
                                "Carefully transcribe ALL text visible in this image exactly as written — "
                                "preserve question numbers, marks in brackets, and every answer word. "
                                "If something is unclear, make your best guess and mark it with [?]. "
                                "Output ONLY the transcribed text, no commentary."
                            ),
                        },
                    ],
                }],
                max_tokens=4096,
                temperature=0.1,
            )
            text = response.choices[0].message.content.strip()
            if text:
                return text
        except Exception as e:
            print(f"[Vision OCR warning]{' ' + context if context else ''}: {e}")

    # Fallback: Tesseract OCR -------------------------------------------------
    try:
        import io
        from PIL import Image, ImageFilter, ImageEnhance
        import pytesseract

        img = Image.open(io.BytesIO(img_bytes)).convert("L")
        img = ImageEnhance.Contrast(img).enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)

        text = pytesseract.image_to_string(img, config=r"--oem 1 --psm 6").strip()
        if text:
            return text + "\n[Note: Tesseract used — provide Groq API key for better handwriting accuracy]"
        return ""
    except ImportError:
        return (
            "[ERROR] No OCR method available. "
            "Enter your Groq API key (sidebar) for vision-based handwriting recognition, "
            "or run: pip install pytesseract pillow"
        )
    except Exception as e:
        return f"[OCR error: {e}]"


# ── PDF extraction ────────────────────────────────────────────────────────────

def extract_text_from_pdf(uploaded_file, api_key=None):
    """
    Extract text from a PDF.
    • Digital PDFs  → direct text via PyMuPDF (fast, accurate)
    • Scanned/image PDFs (handwriting) → render each page as JPEG and OCR it
    """
    try:
        import fitz
    except ImportError:
        return "[ERROR] PyMuPDF not installed. Run: pip install pymupdf"

    try:
        data = uploaded_file.read()
        doc  = fitz.open(stream=data, filetype="pdf")

        # Try direct text extraction ------------------------------------------
        pages_text = [page.get_text().strip() for page in doc]
        full_text  = "\n".join(pages_text).strip()

        if len(full_text) > 50:
            return full_text          # Digital PDF — done

        # Scanned / image-based PDF → render pages and OCR -------------------
        all_text = []
        for page_num, page in enumerate(doc, 1):
            mat       = fitz.Matrix(200 / 72, 200 / 72)   # 200 DPI
            pix       = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
            img_bytes = pix.tobytes("jpeg")

            page_text = _ocr_image_bytes(
                img_bytes,
                mime_type="image/jpeg",
                api_key=api_key,
                context=f"page {page_num} of {len(doc)}",
            )
            if page_text:
                all_text.append(f"--- Page {page_num} ---\n{page_text}")

        return "\n\n".join(all_text).strip() or "[No text could be extracted from this PDF]"

    except Exception as e:
        return f"[PDF extraction error: {e}]"


# ── Image extraction ──────────────────────────────────────────────────────────

def extract_text_from_image(uploaded_file, api_key=None):
    """
    Extract text from an image (including handwriting).
    Uses Groq Vision LLM first, falls back to Tesseract.
    """
    image_data = uploaded_file.read()
    mime_type  = uploaded_file.type or "image/jpeg"
    return _ocr_image_bytes(image_data, mime_type=mime_type, api_key=api_key)


# ── PDF report generation ─────────────────────────────────────────────────────

def generate_pdf_report(result, model, strictness):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from io import BytesIO

        buffer = BytesIO()
        doc    = SimpleDocTemplate(buffer, pagesize=letter,
                                   topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        story  = []

        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22,
                                     textColor=colors.HexColor('#1e3a5f'),
                                     alignment=TA_CENTER, spaceAfter=10)
        heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=13,
                                       textColor=colors.HexColor('#2e75b6'),
                                       spaceBefore=10, spaceAfter=5)

        story.append(Paragraph("SmartGrade AI - Evaluation Report", title_style))
        story.append(Spacer(1, 0.2*inch))

        te  = result.get("total_earned", 0)
        tm  = result.get("total_max", 0)
        pct = round((te / tm * 100) if tm else 0, 1)

        summary_data = [
            ['Score',      f'{te} / {tm}'],
            ['Percentage', f'{pct}%'],
            ['Grade',      f'{result.get("grade","N/A")} - {result.get("grade_name","N/A")}'],
            ['Model',      model],
            ['Strictness', strictness],
        ]
        summary_table = Table(summary_data, colWidths=[2*inch, 4*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (0,-1), colors.HexColor('#e6f2ff')),
            ('TEXTCOLOR',     (0,0), (-1,-1), colors.black),
            ('FONTNAME',      (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTSIZE',      (0,0), (-1,-1), 10),
            ('GRID',          (0,0), (-1,-1), 0.5, colors.grey),
            ('TOPPADDING',    (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))

        story.append(Paragraph("Overall Feedback", heading_style))
        story.append(Paragraph(result.get("overall_feedback", ""), styles['Normal']))
        story.append(Spacer(1, 0.2*inch))

        story.append(Paragraph("Question-wise Analysis", heading_style))
        story.append(Spacer(1, 0.1*inch))

        questions = result.get("questions", [])
        for i, q in enumerate(questions, 1):
            q_text = q.get('question', '')[:100]
            story.append(Paragraph(f"<b>Q{i}. {q_text}...</b>", styles['Normal']))
            story.append(Spacer(1, 0.05*inch))

            earned = q.get("earned", 0)
            max_m  = q.get("max_marks", 0)
            sim    = q.get("similarity_score", 0)

            q_data = [
                ['Marks',      f'{earned} / {max_m}'],
                ['Similarity', f'{sim}%'],
                ['Feedback',   q.get('feedback', '')],
            ]
            kp = q.get("key_points_covered", [])
            if kp: q_data.append(['Covered', ', '.join(kp)])
            mp = q.get("missing_points", [])
            if mp: q_data.append(['Missing', ', '.join(mp)])

            q_table = Table(q_data, colWidths=[1.2*inch, 4.8*inch])
            q_table.setStyle(TableStyle([
                ('BACKGROUND',    (0,0), (0,-1), colors.HexColor('#f5f5f5')),
                ('FONTNAME',      (0,0), (0,-1), 'Helvetica-Bold'),
                ('FONTSIZE',      (0,0), (-1,-1), 9),
                ('GRID',          (0,0), (-1,-1), 0.5, colors.grey),
                ('VALIGN',        (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING',    (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(q_table)
            story.append(Spacer(1, 0.15*inch))

            if i % 2 == 0 and i < len(questions):
                story.append(PageBreak())

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    except Exception:
        return None