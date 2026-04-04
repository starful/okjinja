import os
import csv
import re
import time
import logging
import unicodedata
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# --- 1. 환경 설정 ---
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.dirname(SCRIPT_DIR)
CSV_PATH    = os.path.join(SCRIPT_DIR, 'csv', 'jinja.csv')
LOG_DIR     = os.path.join(SCRIPT_DIR, 'logs')
LOG_PATH    = os.path.join(LOG_DIR, 'processed_jinja.txt')
CONTENT_DIR = os.path.join(BASE_DIR, 'app', 'content')

load_dotenv(os.path.join(BASE_DIR, '.env'))

os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, f"jinja_gen_{datetime.now().strftime('%Y%m%d')}.log"), encoding='utf-8')
    ]
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logging.error("❌ GEMINI_API_KEY not found in .env")
    exit(1)

genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-flash-latest"
model = genai.GenerativeModel(MODEL_NAME)
logging.info(f"✅ Using model: {MODEL_NAME}")

CATEGORY_EN_MAP = {
    '재물': 'Wealth', '사랑': 'Love', '건강': 'Health',
    '학업': 'Success', '안전': 'Safety', '성공': 'Success', '역사': 'History'
}

# --- 2. 헬퍼 함수 ---
def normalize_text(text):
    if not text: return ""
    return unicodedata.normalize('NFKC', str(text)).strip()

def get_target_row():
    processed_items = set()
    if os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, 'r', encoding='utf-8') as f:
                processed_items = set(normalize_text(line) for line in f)
        except Exception:
            pass

    if not os.path.exists(CSV_PATH):
        logging.error(f"❌ CSV file missing: {CSV_PATH}")
        return None, None

    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            shrine_name = row.get('shrine_name', '').strip()
            if shrine_name and normalize_text(shrine_name) not in processed_items:
                return row, shrine_name
    return None, None

# --- 3. 프롬프트 생성 ---
def generate_jinja_prompt(shrine_name, region):
    return f"""
# Role
A passionate solo traveler and storyteller wandering through Japan's hidden shrines.

# Topic: My Journey to "{shrine_name}" (Located in {region})

# Requirements
- Target Audience: Global tourists who love authentic, off-the-beaten-path experiences in Japan.
- Language: **English** (Native, conversational, and warm tone).
- Length: Around 1,200 ~ 1,500 words.
- **Perspective**: 100% First-person ("I", "my"). Tell it like a personal travel essay.
- **Sensory Details**: Describe the crisp air, the smell of incense, the sound of gravel, etc.
- **[CRITICAL - NO ONSEN]**: DO NOT include any recommendations or sections about "Nearby Onsen" or hot springs.
- **[CRITICAL - NO IMAGES]**: DO NOT insert any markdown image tags (e.g., ![alt text](url)) in the body content.
- **[CRITICAL - START]**: Do NOT write any intro. Start directly with the Title (H1).

# Output Format (Markdown)
1. The first line MUST be the Title starting with `#`.
2. The last line MUST be **FILENAME: shrine_name_english_slug**.

---
# Content Structure
# {shrine_name} (Creative English Title)

### 1. ⛩️ My First Impression & History
### 2. 🚶‍♂️ Exploring the Sacred Grounds
### 3. 📜 Unique Goshuin & Omamori
### 4. 💡 My Honest Pro Tips
### 5. 🗺️ Access & Info
(Table: Address, Nearest Station, Hours)
### 6. ✨ Conclusion

---

FILENAME: (English slug here)
"""

# --- 4. 마크다운 저장 (image_prompt 추가) ---
def save_to_markdown(title, content, row_data, filename_slug):
    os.makedirs(CONTENT_DIR, exist_ok=True)
    filename = f"{filename_slug}.md"
    filepath = os.path.join(CONTENT_DIR, filename)

    body = re.sub(r'#.*?\n', '', content).strip()
    excerpt = body[:160].replace('\n', ' ') + "..."

    kor_cat = row_data.get('Category', '역사')
    eng_cat = CATEGORY_EN_MAP.get(kor_cat, 'History')
    categories = [eng_cat]
    tags = ["Japan", "Shrine", "Travel", eng_cat, "SoloTravel"]

    region_raw = row_data.get('Region', '')
    region_match = re.search(r'\((.*?)\)', region_raw)
    if region_match:
        tags.append(region_match.group(1))

    lat  = row_data.get('lat', '35.6895')
    lng  = row_data.get('lng', '139.6917')
    addr = row_data.get('Address', row_data.get('shrine_name', ''))

    image_path = f"/content/images/{filename_slug}.webp"

    # ✅ image_prompt: 카테고리/지역별 특성을 반영한 맞춤 프롬프트
    shrine_display = title.replace('"', '')
    region_en = region_match.group(1) if region_match else "Japan"

    category_features = {
        'Wealth': "golden koban coin offerings, rows of vermilion torii gates, fox (kitsune) statues draped in red bibs",
        'Love':   "heart-shaped ema wishing plaques, enmusubi red thread, romantic stone couple statues, pink flowers",
        'Health': "sacred healing spring water, ancient zelkova trees, medicinal herb garden, serene pond",
        'Success':"ume plum blossom trees, rows of student ema wishing plaques, ancient scholarly wooden halls",
        'Safety': "powerful guardian lion-dog (komainu) statues, giant shimenawa sacred rope, protective stone walls",
        'History':"ancient weathered wooden architecture, deeply moss-covered stone lanterns, centuries-old cedar forest",
    }
    features = category_features.get(eng_cat, "traditional Shinto torii gates, stone lanterns, ancient sacred forest")

    image_prompt = (
        f"A breathtaking photorealistic view of {shrine_display} Shinto shrine in {region_en}, Japan. "
        f"Key visual elements: {features}. "
        f"No people, sacred serene atmosphere, cinematic professional travel photography."
    )

    md_content = f"""---
layout: post
title: "{title}"
date: {datetime.now().strftime('%Y-%m-%d')}
categories: {categories}
tags: {tags}
thumbnail: {image_path}
lat: {lat}
lng: {lng}
address: "{addr}"
excerpt: "{excerpt}"
image_prompt: "{image_prompt}"
humanized: true
---

{content}
"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        logging.info(f"💾 Saved: {filepath}")
        return True
    except Exception as e:
        logging.error(f"❌ Save Failed: {e}")
        return False

# --- 5. 메인 실행 ---
if __name__ == "__main__":
    TARGET_COUNT = 2

    logging.info(f"🚀 Generator Started (Target: {TARGET_COUNT})")

    success_count = 0
    for i in range(TARGET_COUNT):
        row, shrine_name = get_target_row()
        if not shrine_name:
            logging.info("🎉 All shrines processed.")
            break

        logging.info(f"[{i+1}/{TARGET_COUNT}] Generating: {shrine_name}")

        try:
            region = "Japan"
            if '(' in row.get('Region', ''):
                region = row['Region'].split('(')[1].replace(')', '')

            prompt = generate_jinja_prompt(shrine_name, region)
            resp = model.generate_content(prompt)
            content = resp.text

            header_match = re.search(r'^#\s+.+', content, re.MULTILINE)
            content = content[header_match.start():] if header_match else f"# {shrine_name}\n\n" + content

            filename_slug = f"shrine_{int(time.time())}"
            file_match = re.search(r'FILENAME:\s*([\w_]+)', content)
            if file_match:
                filename_slug = file_match.group(1).strip().lower()
                content = content.replace(file_match.group(0), '').strip()

            t_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = t_match.group(1).strip().replace('**', '') if t_match else shrine_name
            content = re.sub(r'^#\s+.*?\n', '', content, count=1).strip()

            content = re.sub(r'([^\n])\n\*\s', r'\1\n\n* ', content)
            content = re.sub(r'([^\n])\n-\s', r'\1\n\n- ', content)
            content = re.sub(r'!\[.*?\]\(.*?\)', '', content)  # 가짜 이미지 태그 제거

            if save_to_markdown(title, content, row, filename_slug):
                with open(LOG_PATH, 'a', encoding='utf-8') as f:
                    f.write(f"{normalize_text(shrine_name)}\n")
                success_count += 1

        except Exception as e:
            logging.error(f"❌ Error: {e}")
            continue

    logging.info(f"✨ Done. Generated {success_count} articles.")