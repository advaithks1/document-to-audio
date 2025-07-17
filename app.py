from flask import Flask, render_template, request, url_for, jsonify
from docx import Document
import fitz
from langdetect import detect
from gtts import gTTS
import nltk
import os
import re
from pydub import AudioSegment
import unicodedata
import tamil
import json
from concurrent.futures import ThreadPoolExecutor
from werkzeug.utils import secure_filename
import uuid

nltk.download('punkt')
from nltk.tokenize import sent_tokenize

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
COMBINED_AUDIO_FOLDER = 'static/combined_audio'
TEXT_DATA_FOLDER = 'static/text_data'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(COMBINED_AUDIO_FOLDER, exist_ok=True)
os.makedirs(TEXT_DATA_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'.pdf', '.docx'}

def fix_tamil_spacing(text):
    text = unicodedata.normalize('NFD', text)
    text = re.sub(r'[\u200B\uFEFF\u200C\u200D]', '', text)
    text = ''.join(
        ch for ch in text
        if not unicodedata.combining(ch) or ('\u0BBE' <= ch <= '\u0BCD')
    )
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'([\u0BBE-\u0BCD])\1+', r'\1', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def read_docx(file_path):
    doc = Document(file_path)
    return '\n'.join(para.text for para in doc.paragraphs)

def read_pdf(file_path):
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc:
            page_text = page.get_text()
            page_text = fix_tamil_spacing(page_text)
            text += page_text + " "
    return text.strip()

def extract_text(file_path):
    ext = os.path.splitext(file_path)[-1].lower()
    if ext == ".docx":
        return read_docx(file_path)
    elif ext == ".pdf":
        return read_pdf(file_path)
    else:
        raise ValueError("Unsupported file type. Only .docx and .pdf are supported.")

def text_to_speech(sentence, idx, lang='en'):
    tts = gTTS(text=sentence, lang=lang)
    audio_path = f"{UPLOAD_FOLDER}/output_{idx}.mp3"
    tts.save(audio_path)
    return audio_path

def split_text_sentences(text):
    sentences = sent_tokenize(text)
    transcript = []
    combined_audio = AudioSegment.empty()
    time_accumulated = 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for idx, sent in enumerate(sentences):
            try:
                lang = detect(sent)
            except:
                lang = 'en'

            if lang not in ['en', 'ta', 'kn', 'hi']:
                lang = 'en'

            futures.append(executor.submit(text_to_speech, sent, idx, lang))

        for idx, future in enumerate(futures):
            audio_path = future.result()
            segment = AudioSegment.from_file(audio_path)
            
            transcript.append({
                "index": idx,
                "sentence": sentences[idx],
                "start": time_accumulated,
                "duration": len(segment) / 1000
            })

            combined_audio += segment
            time_accumulated += len(segment) / 1000

    combined_audio.export(f"{COMBINED_AUDIO_FOLDER}/combined_audio.mp3", format="mp3")

    with open(os.path.join(TEXT_DATA_FOLDER, 'transcript.json'), 'w', encoding='utf-8') as f:
        json.dump(transcript, f, ensure_ascii=False)

    # Cleanup temporary TTS files
    for file in os.listdir(UPLOAD_FOLDER):
        if file.startswith("output_") and file.endswith(".mp3"):
            os.remove(os.path.join(UPLOAD_FOLDER, file))

    return transcript

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file = request.files["file"]

        # Validate file type
        ext = os.path.splitext(file.filename)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return "Unsupported file type. Only .pdf and .docx are allowed.", 400

        # Sanitize filename and make it unique
        safe_name = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{safe_name}"
        path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(path)

        try:
            text = extract_text(path)
            split_text_sentences(text)
        finally:
            os.remove(path)  # Clean up uploaded file after processing

        return render_template("index.html", 
                               audio_file=url_for('static', filename='combined_audio/combined_audio.mp3'))
    return render_template("index.html")

@app.route("/transcript")
def get_transcript():
    with open(os.path.join(TEXT_DATA_FOLDER, 'transcript.json'), 'r', encoding='utf-8') as f:
        transcript = json.load(f)
    return jsonify(transcript)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
