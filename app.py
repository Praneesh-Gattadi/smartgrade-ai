import streamlit as st
import time
from evaluator import AnswerEvaluator
from utils import extract_text_from_pdf, extract_text_from_image, generate_pdf_report

st.set_page_config(page_title="SmartGrade AI", page_icon="🎓", layout="wide")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=JetBrains+Mono&display=swap');
html,body,[class*="css"]{font-family:'Sora',sans-serif}
.stApp{background:#0d1117;color:#e6edf3}
.hero{font-size:2.8rem;font-weight:700;background:linear-gradient(135deg,#58a6ff,#bc8cff,#ff7b72);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center}
.sub{text-align:center;color:#8b949e;margin-bottom:1.5rem}
.card{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:1.4rem;margin-bottom:1rem}
.ring{width:130px;height:130px;border-radius:50%;display:flex;flex-direction:column;
  align-items:center;justify-content:center;margin:0 auto 0.75rem;font-family:'JetBrains Mono',monospace}
.rv{font-size:2rem;font-weight:700;line-height:1} .rl{font-size:.7rem;opacity:.7;margin-top:3px}
.grade-A{border:4px solid #3fb950;background:rgba(63,185,80,.1);color:#3fb950}
.grade-B{border:4px solid #58a6ff;background:rgba(88,166,255,.1);color:#58a6ff}
.grade-C{border:4px solid #d29922;background:rgba(210,153,34,.1);color:#d29922}
.grade-D{border:4px solid #f78166;background:rgba(247,129,102,.1);color:#f78166}
.grade-F{border:4px solid #ff7b72;background:rgba(255,123,114,.1);color:#ff7b72}
.badge{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.75rem;font-weight:600;font-family:'JetBrains Mono',monospace}
.bf{background:rgba(63,185,80,.2);color:#3fb950} .bp{background:rgba(210,153,34,.2);color:#d29922} .bz{background:rgba(255,123,114,.2);color:#ff7b72}
.pbo{background:#21262d;border-radius:4px;height:8px;overflow:hidden}
.pbi{height:100%;border-radius:4px;background:linear-gradient(90deg,#238636,#3fb950)}
.sg{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem;margin-top:.5rem}
.si{text-align:center} .sn{font-size:1.4rem;font-weight:700;font-family:'JetBrains Mono',monospace} .sl{font-size:.72rem;color:#8b949e}
div[data-testid="stSidebarContent"]{background:#0d1117}
.stTextArea textarea,.stTextInput input{background:#161b22!important;color:#e6edf3!important;border:1px solid #30363d!important;border-radius:8px!important}
.stButton>button{background:linear-gradient(135deg,#238636,#2ea043);color:#fff;border:none;border-radius:8px;font-weight:600;width:100%}
hr{border-color:#21262d} label{color:#8b949e!important}
</style>""", unsafe_allow_html=True)

st.markdown('<div class="hero">SmartGrade AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">AI-powered answer sheet evaluation · Powered by Groq</div>', unsafe_allow_html=True)
st.markdown("---")

with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    api_key = st.text_input("🔑 Groq API Key", type="password", placeholder="gsk_...")
    st.caption("🆓 Get free key → [console.groq.com](https://console.groq.com)")
    
    model_choice = st.selectbox("🤖 Model", [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it"
    ])

    st.markdown("---")
    st.markdown("**📊 Grading Scale**")
    grade_a = st.slider("A ≥", 50, 100, 85)
    grade_b = st.slider("B ≥", 40,  90, 70)
    grade_c = st.slider("C ≥", 30,  80, 55)
    grade_d = st.slider("D ≥", 20,  70, 40)
    st.markdown("---")
    strictness     = st.select_slider("🎯 Strictness", ["Lenient", "Moderate", "Strict"], value="Moderate")
    st.caption("**Lenient**: Credit for basic understanding\n**Moderate**: Require clear explanations\n**Strict**: Demand complete details")
    partial_credit = st.toggle("Allow Partial Credit", value=True)

input_mode    = st.radio("📥 Input Method", ["✏️ Manual Text", "📄 Upload Files"], horizontal=True)
col1, col2    = st.columns(2)
question_text = answer_text = ""

def read_file(f):
    if f.type == "application/pdf":   return extract_text_from_pdf(f, api_key=api_key)
    if f.type.startswith("image"):    return extract_text_from_image(f, api_key=api_key)
    return f.read().decode("utf-8")

if input_mode == "✏️ Manual Text":
    with col1:
        st.markdown("#### 📋 Question Paper")
        question_text = st.text_area("qp", height=280, label_visibility="collapsed",
            placeholder="Q1. (5 marks) What is machine learning?\nQ2. (3 marks) Define supervised learning.")
    with col2:
        st.markdown("#### 📝 Answer Sheet")
        answer_text = st.text_area("ans", height=280, label_visibility="collapsed",
            placeholder="Q1. Machine learning is a subset of AI...\nQ2. Supervised learning uses labeled data...")
else:
    for label, key, var in [("📋 Question Paper", "q_up", "q"), ("📝 Answer Sheet", "a_up", "a")]:
        with (col1 if var == "q" else col2):
            st.markdown(f"#### {label}")
            f = st.file_uploader(f"Upload {label}", type=["pdf","png","jpg","jpeg","txt"], key=key)
            if f:
                with st.spinner("Extracting..."):
                    text = read_file(f)
                st.success(f"✅ {len(text)} characters extracted")
                with st.expander("Preview"): st.text(text[:500])
                if var == "q": question_text = text
                else:          answer_text   = text

_, bc, _ = st.columns([1, 2, 1])
with bc:
    run = st.button("🚀 Evaluate Answer Sheet", use_container_width=True)

def get_grade(p):
    for threshold, letter, name in [(grade_a,"A","Excellent"),(grade_b,"B","Good"),(grade_c,"C","Average"),(grade_d,"D","Pass")]:
        if p >= threshold: return letter, name
    return "F", "Fail"

def badge(earned, max_m):
    cls = "bz" if earned == 0 else "bf" if earned >= max_m else "bp"
    return f'<span class="badge {cls}">{earned} / {max_m}</span>'

if run:
    if not api_key:                 st.error("⚠️ Please enter your Groq API key.")
    elif not question_text.strip(): st.error("⚠️ Please provide the question paper.")
    elif not answer_text.strip():   st.error("⚠️ Please provide the answer sheet.")
    else:
        with st.spinner("🔍 Evaluating..."):
            prog = st.progress(0, "Connecting...")
            time.sleep(0.2)
            prog.progress(20, f"{strictness} evaluation...")
            result = AnswerEvaluator(api_key, model_choice, strictness, partial_credit).evaluate(question_text, answer_text)
            prog.progress(100, "Done!"); time.sleep(0.3); prog.empty()

        if "error" in result:
            st.error(f"❌ {result['error']}")
        else:
            te  = result.get("total_earned", 0)
            tm  = result.get("total_max", 0)
            pct = round((te / tm * 100) if tm else 0, 1)
            gl, gn = get_grade(pct)
            qs  = result.get("questions", [])

            st.markdown("---\n## 📊 Evaluation Results")
            s1, s2, s3 = st.columns([1, 1, 2])

            with s1:
                st.markdown(f"""<div class="card" style="text-align:center">
                  <div class="ring grade-{gl}"><div class="rv">{pct}%</div><div class="rl">SCORE</div></div>
                  <div style="font-size:2rem;font-weight:700">{gl}</div>
                  <div style="color:#8b949e;font-size:.85rem">{gn}</div></div>""", unsafe_allow_html=True)

            with s2:
                full = sum(1 for q in qs if q.get("earned",0) >= q.get("max_marks",1))
                part = sum(1 for q in qs if 0 < q.get("earned",0) < q.get("max_marks",1))
                zero = sum(1 for q in qs if q.get("earned",0) == 0)
                st.markdown(f"""<div class="card">
                  <div style="font-weight:600;margin-bottom:.75rem">📈 Breakdown</div>
                  <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                    <span style="font-size:.85rem">Marks</span>
                    <span style="font-family:'JetBrains Mono';font-weight:600">{te} / {tm}</span></div>
                  <div class="pbo"><div class="pbi" style="width:{pct}%"></div></div>
                  <div class="sg">
                    <div class="si"><div class="sn" style="color:#3fb950">{full}</div><div class="sl">Full</div></div>
                    <div class="si"><div class="sn" style="color:#d29922">{part}</div><div class="sl">Partial</div></div>
                    <div class="si"><div class="sn" style="color:#ff7b72">{zero}</div><div class="sl">Zero</div></div>
                  </div></div>""", unsafe_allow_html=True)

            with s3:
                st.markdown(f"""<div class="card" style="height:100%">
                  <div style="font-weight:600;margin-bottom:.75rem">💬 Overall Feedback</div>
                  <div style="color:#cdd9e5;font-size:.9rem;line-height:1.6">{result.get("overall_feedback","")}</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("### 📝 Question-wise Analysis")
            for i, q in enumerate(qs, 1):
                earned, max_m = q.get("earned",0), q.get("max_marks",0)
                sim = q.get("similarity_score", 0)
                sc  = "#3fb950" if sim>=70 else "#d29922" if sim>=40 else "#ff7b72"
                with st.expander(f"Q{i}. {q.get('question','')[:80]}...  {badge(earned,max_m)}", expanded=i<=3):
                    a, b = st.columns(2)
                    with a:
                        st.markdown("**📋 Question**");      st.info(q.get("question",""))
                        st.markdown("**✍️ Student Answer**")
                        ans = q.get("student_answer","").strip()
                        st.warning(ans if ans else "_No answer_")
                    with b:
                        st.markdown(f"""<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:1rem;margin-bottom:.75rem">
                          <div style="display:flex;justify-content:space-between;margin-bottom:8px">
                            <span style="font-size:.85rem;color:#8b949e">Similarity ({strictness})</span>
                            <span style="font-family:'JetBrains Mono';font-weight:700;color:{sc}">{sim}%</span></div>
                          <div class="pbo"><div style="height:100%;border-radius:4px;background:{sc};width:{sim}%"></div></div>
                        </div>""", unsafe_allow_html=True)
                        st.markdown(f"**💡 Feedback:** {q.get('feedback','')}")
                        kp, mp = q.get("key_points_covered",[]), q.get("missing_points",[])
                        if kp: st.markdown("**✅ Covered:** " + " · ".join(kp))
                        if mp: st.markdown("**❌ Missing:** " + " · ".join(mp))

            st.markdown("---")
            
            # Generate PDF
            pdf_data = generate_pdf_report(result, model_choice, strictness)
            if pdf_data:
                st.download_button("📄 Download PDF Report", data=pdf_data,
                                   file_name="evaluation_report.pdf", mime="application/pdf")
            else:
                st.error("⚠️ PDF generation failed. Install: pip install reportlab")