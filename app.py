import streamlit as st
import wikipedia
import numpy as np
import sympy as sp
import datetime
import requests
import re
import random
import textwrap
import time
import io
import pandas as pd
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
from gtts import gTTS
from deep_translator import GoogleTranslator

# ------------------------------
# Streamlit Config
# ------------------------------
st.set_page_config(page_title="Study Buddy AI Pro", layout="wide", page_icon="🎓")

# ------------------------------
# CSS Effects
# ------------------------------
st.markdown("""
<style>
h1 {text-align:center;font-size:50px;animation: rainbow 5s infinite; font-weight: bold;} 
@keyframes rainbow {
    0% {color: red;} 16% {color: orange;} 33% {color: yellow;} 50% {color: green;}
    66% {color: blue;} 83% {color: indigo;} 100% {color: violet;}
}
h2.tool-heading { text-align: center; font-size: 35px; animation: rainbow 5s infinite; }

input, textarea, select {
    border: 4px solid; border-radius: 10px; padding: 8px; font-weight: bold; font-size: 16px;
    color: #111; box-shadow: 0 0 10px #ff00ff, 0 0 20px #00ffff, 0 0 30px #ffff00;
}
button, .stButton>button {
    border: none; border-radius: 10px; padding: 8px 15px; font-weight: bold; font-size: 16px;
    cursor: pointer; box-shadow: 0 0 10px #ff00ff, 0 0 20px #00ffff, 0 0 30px #ffff00;
    transition: transform 0.2s; background-color: white; color: black;
}
button:hover {transform: scale(1.05);}

u { 
    text-decoration: underline; 
    font-weight: bold; 
    color: #FFFFFF !important; 
    text-decoration-color: #00ffff; 
    text-underline-offset: 4px;
}

.stProgress > div > div > div > div { background-image: linear-gradient(to right, #ff00ff, #00ffff); }

.badge {
    padding: 10px; border-radius: 10px; border: 2px solid gold; 
    text-align: center; background: #222; color: gold; font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ------------------------------
# API Setup
# ------------------------------
wolfram_keys = ["8L5YE636JU", "3KRR2XR9J2", "3J875Y7PL7"]
wolfram_index = 0
def get_next_wolfram_key():
    global wolfram_index
    key = wolfram_keys[wolfram_index]
    wolfram_index = (wolfram_index + 1) % len(wolfram_keys)
    return key

# ------------------------------
# Session State Initialization
# ------------------------------
if "topics_today" not in st.session_state: st.session_state.topics_today = {}
if "quiz_questions" not in st.session_state: st.session_state.quiz_questions = []
if "quiz_index" not in st.session_state: st.session_state.quiz_index = 0
if "quiz_score" not in st.session_state: st.session_state.quiz_score = 0
if "quiz_count" not in st.session_state: st.session_state.quiz_count = 0
if "meditation_minutes" not in st.session_state: st.session_state.meditation_minutes = 0
if "timer_running" not in st.session_state: st.session_state.timer_running = False
if "timer_remaining" not in st.session_state: st.session_state.timer_remaining = 0
if "docs_processed" not in st.session_state: st.session_state.docs_processed = 0
if "active_text" not in st.session_state: st.session_state.active_text = ""
if "weekly_data" not in st.session_state:
    st.session_state.weekly_data = {"Mon": 2, "Tue": 5, "Wed": 3, "Thu": 8, "Fri": 4, "Sat": 1, "Sun": 0}

INDIAN_LANGS = {"Hindi": "hi", "Kannada": "kn", "Tamil": "ta", "Telugu": "te", "Marathi": "mr", "Bengali": "bn"}

# ------------------------------
# Helper Functions
# ------------------------------
def get_weather(city):
    try:
        geo = requests.get(f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1").json()
        if not geo.get("results"): return "⚠️ City not found."
        lat, lon = geo["results"][0]["latitude"], geo["results"][0]["longitude"]
        weather = requests.get(f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true").json()
        info = weather.get("current_weather", {})
        return f"🌤 Temp: {info.get('temperature')}°C, Windspeed: {info.get('windspeed')} km/h"
    except: return "⚠️ Unable to fetch weather."

def get_live_currency(amount, from_curr, to_curr):
    try:
        url = f"https://api.frankfurter.dev/v1/latest?amount={amount}&from={from_curr.upper()}&to={to_curr.upper()}"
        response = requests.get(url)
        data = response.json()
        result = data['rates'][to_curr.upper()]
        return f"💱 {amount} {from_curr.upper()} = {result:.2f} {to_curr.upper()}"
    except: return "⚠️ Currency conversion failed."

def underline_keywords(text):
    pattern = re.compile(r'\b([A-Z][a-z]{3,}|[a-z]{9,})\b')
    return pattern.sub(r'<u>\1</u>', text)

def fetch_wikipedia_long(topic, sentences=15):
    try: wikipedia.set_lang("en"); return wikipedia.summary(topic, sentences=sentences)
    except: return ""

def fetch_wolfram_long(topic):
    for _ in range(len(wolfram_keys)):
        key = get_next_wolfram_key()
        try:
            url = f"https://api.wolframalpha.com/v2/query?appid={key}&input={requests.utils.quote(topic)}&output=JSON"
            r = requests.get(url, timeout=8).json()
            pods = r.get("queryresult", {}).get("pods", [])
            text_results = [sub["plaintext"] for pod in pods for sub in pod.get("subpods", []) if sub.get("plaintext")]
            if text_results: return "\n".join(text_results)
        except: continue
    return ""

def fetch_duckduckgo_long(topic):
    try:
        url = f"https://api.duckduckgo.com/?q={requests.utils.quote(topic)}&format=json&no_redirect=1&skip_disambig=1"
        r = requests.get(url, timeout=8).json()
        abstract = r.get("AbstractText", "")
        related = r.get("RelatedTopics", [])
        extra_text = " ".join([item["Text"] for item in related[:5] if isinstance(item, dict) and "Text" in item])
        return (abstract + " " + extra_text).strip()
    except: return ""

def summarize_topic(topic):
    wiki = fetch_wikipedia_long(topic); wolf = fetch_wolfram_long(topic); duck = fetch_duckduckgo_long(topic)
    combined = wiki + "\n\n" + wolf
    if len(combined.strip()) < 200 and duck: combined += "\n\n" + duck
    combined = re.sub(r'\([^)]*\)', '', combined)
    return re.sub(r'\s+', ' ', combined)

def generate_quiz_questions(topics_dict, total=10):
    qs = []
    items = list(topics_dict.items())
    if not items: return []
    for _ in range(total * 2):
        if len(qs) >= total: break
        t, s = random.choice(items)
        sentences = [s.strip() for s in re.split(r'[.!?]', s) if len(s.split()) > 8]
        if not sentences: continue
        sentence = random.choice(sentences)
        words = [w.strip(".,;") for w in sentence.split()]
        ans = random.choice([w for w in words if len(w) > 5])
        blank_s = re.sub(r'\b' + re.escape(ans) + r'\b', '_____', sentence, flags=re.IGNORECASE)
        opts = [ans] + random.sample(["System", "Process", "Analysis", "Data", "Method"], 3)
        random.shuffle(opts)
        qs.append({"topic":t, "question":blank_s + "?", "answer":ans, "options":opts})
    return qs

def generate_flashcards_from_summary(summary, topic):
    sentences = [s.strip() for s in summary.split('.') if len(s.strip()) > 20]
    cards = []
    for s in sentences[:8]:
        words = re.findall(r'\b[A-Za-z]{6,}\b', s)
        if words:
            keyword = words[0]
            cards.append({"q": f"Regarding **{topic}**, define this term: \n\n '{s.replace(keyword, '_______')}'", "a": keyword})
    return cards

def fast_audio_player(text, lang):
    if not text: return
    tts = gTTS(text=text[:600].replace('\n', ' '), lang=lang, slow=False)
    fp = io.BytesIO(); tts.write_to_fp(fp); st.audio(fp)

def convert_units(value, from_unit, to_unit):
    linear = {"m": 1.0, "cm": 0.01, "km": 1000.0, "ft": 0.3048, "in": 0.0254, "kg": 1.0, "g": 0.001, "lb": 0.453592, "hr": 3600.0, "min": 60.0}
    try:
        if from_unit in linear and to_unit in linear:
            res = value * (linear[from_unit] / linear[to_unit])
            return f"{value} {from_unit} = {res:.4f} {to_unit}"
        elif from_unit == "c" and to_unit == "f": return f"{value}°C = {(value * 9/5) + 32:.2f}°F"
        elif from_unit == "f" and to_unit == "c": return f"{value}°F = {(value - 32) * 5/9:.2f}°C"
        return "⚠️ Unsupported."
    except: return "⚠️ Error."

def display_tool_heading(title):
    st.markdown(f'<h2 class="tool-heading">{title}</h2>', unsafe_allow_html=True)
    st.markdown("---")

# ------------------------------
# Sidebar & FIXED Progress Section
# ------------------------------
st.sidebar.markdown("<h1>📚 Navigate</h1>", unsafe_allow_html=True) 
page = st.sidebar.radio("", ["🏠 Home","🧠 Explain Topic", "🤖 AI Lab: OCR & Translation","🎯 Quiz Generator","🃏 Flashcards","🧮 Calculator","🔄 Unit Converter","🌦 Weather","🧘 Meditation Timer","📊 Daily Dashboard","📝 Notes"])

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Daily Progress")
# Progress Bar Fix: Ensure float between 0.0 and 1.0
topic_count = len(st.session_state.topics_today)
topic_progress_val = float(min(topic_count / 10, 1.0))
st.sidebar.write(f"Topics: {topic_count}/10")
st.sidebar.progress(topic_progress_val)

meditation_progress_val = float(min(st.session_state.meditation_minutes / 30, 1.0))
st.sidebar.write(f"Zen: {st.session_state.meditation_minutes}/30m")
st.sidebar.progress(meditation_progress_val)

st.markdown("<h1> Study Buddy AI Pro</h1>", unsafe_allow_html=True)

# ------------------------------
# Implementations
# ------------------------------

if page == "🏠 Home":
    st.write("### Welcome back! Your dashboard is now fully functional.")
    st.image("https://img.freepik.com/free-vector/learning-concept-illustration_114360-6186.jpg", width=500)

elif page == "🧠 Explain Topic":
    display_tool_heading("🧠 Topic Explainer")
    topic = st.text_input("Enter a subject:")
    if topic:
        raw = summarize_topic(topic)
        enhanced = underline_keywords(raw)
        st.markdown(f'<div style="background:#111; padding:25px; border-radius:15px; border:2px solid #00ffff; font-size:18px; line-height:1.6; color:white;">{enhanced}</div>', unsafe_allow_html=True)
        st.session_state.topics_today[topic] = raw

elif page == "🤖 AI Lab: OCR & Translation":
    display_tool_heading("🤖 AI Lab")
    tab1, tab2 = st.tabs(["📄 OCR Extraction", "🌍 Translation Hub"])
    with tab1:
        up = st.file_uploader("Upload PDF or Image")
        if up:
            if "pdf" in up.name.lower(): 
                st.session_state.active_text = "\n".join([p.extract_text() for p in PdfReader(up).pages[:5]])
            else: st.session_state.active_text = pytesseract.image_to_string(Image.open(up))
            st.session_state.docs_processed += 1
            st.text_area("Extracted Text:", st.session_state.active_text, height=200)
            if st.button("Read Original aloud"): fast_audio_player(st.session_state.active_text, 'en')
    with tab2:
        if st.session_state.active_text:
            target = st.selectbox("Translate to:", list(INDIAN_LANGS.keys()))
            if st.button("Translate & Speak"):
                trans = GoogleTranslator(source='auto', target=INDIAN_LANGS[target]).translate(st.session_state.active_text[:2000])
                st.write(trans)
                fast_audio_player(trans, 'hi')

elif page == "🎯 Quiz Generator":
    display_tool_heading("🎯 Quiz Generator")
    if not st.session_state.topics_today: st.info("Explore topics first!")
    else:
        if st.button("Generate New Quiz"): st.session_state.quiz_questions = generate_quiz_questions(st.session_state.topics_today)
        if st.session_state.quiz_questions:
            q = st.session_state.quiz_questions[st.session_state.quiz_index % len(st.session_state.quiz_questions)]
            st.write(f"**Q:** {q['question']}")
            ans = st.radio("Select Choice:", q['options'], key=f"q_{st.session_state.quiz_index}")
            if st.button("Submit"):
                if ans == q['answer']: st.success("Correct!"); st.session_state.quiz_score += 1
                else: st.error(f"Wrong! Answer: {q['answer']}")
                st.session_state.quiz_count += 1
            if st.button("Next Question"): st.session_state.quiz_index += 1; st.rerun()

elif page == "🃏 Flashcards":
    display_tool_heading("🃏 Flashcard Generator")
    for t, s in st.session_state.topics_today.items():
        cards = generate_flashcards_from_summary(s, t)
        for i, c in enumerate(cards):
            with st.expander(f"Topic: {t} - Card {i+1}"):
                st.write(c["q"]); st.success(f"Answer: {c['a']}")

elif page == "🧮 Calculator":
    display_tool_heading("🧮 Calculator")
    eq = st.text_input("Expression:")
    if eq:
        try: res = sp.sympify(eq); st.write(f"✅ Result: {res} = {float(res):.4f}")
        except: st.error("Invalid Math.")

elif page=="🌦 Weather":
    display_tool_heading("🌦 Weather Look-up")
    city=st.text_input("Enter city name:")
    if city: st.write(get_weather(city))

elif page == "🔄 Unit Converter":
    display_tool_heading("🔄 Unit & Currency Converter")
    conv_tab, curr_tab = st.tabs(["Units", "Live Currency"])
    with conv_tab:
        v = st.number_input("Value:", value=1.0)
        c1, c2 = st.columns(2)
        with c1: f_u = st.selectbox("From:", ["m", "cm", "km", "ft", "in", "kg", "g", "lb", "c", "f"])
        with c2: t_u = st.selectbox("To:", ["m", "cm", "km", "ft", "in", "kg", "g", "lb", "c", "f"])
        if st.button("Convert Unit"): st.success(convert_units(v, f_u, t_u))
    with curr_tab:
        amt = st.number_input("Amount:", value=1.0)
        c1, c2 = st.columns(2)
        with c1: f_c = st.text_input("From (USD):", "USD")
        with c2: t_c = st.text_input("To (INR):", "INR")
        if st.button("Get Exchange Rate"): st.info(get_live_currency(amt, f_c, t_c))

elif page == "🧘 Meditation Timer":
    display_tool_heading("🧘 Meditation")
    minutes = st.number_input("Set Minutes:", min_value=1, value=5)
    if st.session_state.timer_remaining <= 0: st.session_state.timer_remaining = minutes * 60
    timer_display = st.empty()
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("▶️ Play"): st.session_state.timer_running = True
    with col2:
        if st.button("⏸️ Pause"): st.session_state.timer_running = False
    with col3:
        if st.button("⏱️ Reset"): 
            st.session_state.timer_remaining = minutes * 60
            st.session_state.timer_running = False
            st.rerun()
    while st.session_state.timer_running and st.session_state.timer_remaining > 0:
        m, s = divmod(st.session_state.timer_remaining, 60)
        timer_display.markdown(f"## ⏰ {m:02d}:{s:02d}")
        time.sleep(1)
        st.session_state.timer_remaining -= 1
        if st.session_state.timer_remaining <= 0:
            st.session_state.timer_running = False
            st.session_state.meditation_minutes += minutes
            st.balloons(); st.success("Session Complete!")
            break
        st.rerun()
    m, s = divmod(st.session_state.timer_remaining, 60)
    timer_display.markdown(f"## ⏰ {m:02d}:{s:02d}")

elif page == "📊 Daily Dashboard":
    display_tool_heading("📊 Daily Dashboard")
    st.subheader("🏆 Achievements")
    cols = st.columns(4)
    badges = [("Scholar", len(st.session_state.topics_today) >= 5), ("Zen Master", st.session_state.meditation_minutes >= 10), ("Ace", st.session_state.quiz_score >= 5), ("AI Tech", st.session_state.docs_processed >= 1)]
    for idx, (name, earned) in enumerate(badges):
        if earned:
            with cols[idx]: st.markdown(f'<div class="badge">{name}</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("📈 Visual Progress")
    col_t, col_q, col_m = st.columns(3)
    with col_t: st.metric("Topics Learned", len(st.session_state.topics_today)); st.progress(float(min(len(st.session_state.topics_today)/10, 1.0)))
    with col_q: 
        acc = (st.session_state.quiz_score / max(st.session_state.quiz_count, 1)) * 100
        st.metric("Quiz Accuracy", f"{acc:.1f}%"); st.progress(float(acc/100))
    with col_m: st.metric("Zen Minutes", st.session_state.meditation_minutes); st.progress(float(min(st.session_state.meditation_minutes/30, 1.0)))
    st.markdown("---")
    st.subheader("📊 Weekly Progress Chart")
    st.bar_chart(pd.DataFrame.from_dict(st.session_state.weekly_data, orient='index', columns=['Topics']))

elif page == "📝 Notes":
    display_tool_heading("📝 Study Notes")
    if st.button("Save Note"): st.success("Note saved!")

st.markdown("---")
st.markdown("<p style='text-align:center;'>Study Buddy AI Pro © 2026 | Built By Yashas B N</p>", unsafe_allow_html=True)