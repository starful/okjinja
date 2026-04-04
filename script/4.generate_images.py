import os
import time
import random
import frontmatter
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ==========================================
# ⚙️ 설정
# ==========================================
load_dotenv()

GCP_PROJECT  = os.environ.get("GCP_PROJECT", "starful-258005")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.dirname(SCRIPT_DIR)
CONTENT_DIR = os.path.join(BASE_DIR, 'app', 'content')
IMAGES_DIR  = os.path.join(BASE_DIR, 'app', 'content', 'images')  # 신사는 /content/images/

PROTECTED = {'logo.jpg', 'favicon.ico', 'Torii.png', 'omikuji_box.png'}

# ==========================================
# 🎨 다양성을 위한 랜덤 변수 풀 (신사 특화)
# ==========================================
CAMERA_ANGLES = [
    "wide-angle shot looking through the torii gate tunnel toward the main hall",
    "low angle shot looking up at a single grand torii gate against the sky",
    "overhead drone view of the shrine grounds and surrounding forest",
    "close-up shot of stone lanterns lining the pathway, leading lines",
    "three-quarter view of the main hall (honden) with worshippers' area",
    "framed shot through ancient cedar trees toward the shrine",
    "reflection shot in a temizuya water basin",
]

MOODS = [
    "mystical early morning mist, golden sunrise filtering through trees",
    "dramatic autumn foliage, vivid red and orange maple leaves",
    "serene winter scene, fresh snow on stone lanterns and torii gates",
    "lush green summer, vibrant moss and dense forest canopy",
    "soft cherry blossom spring, pale pink petals falling gently",
    "golden hour sunset, long shadows and warm amber light",
    "moody overcast day, diffused soft light, contemplative atmosphere",
]

LENS_STYLES = [
    "shot on 16mm ultra-wide lens, dramatic perspective, vast sky",
    "shot on 24mm lens, environmental storytelling, sense of scale",
    "shot on 50mm lens, natural human perspective, balanced composition",
    "shot on 85mm lens, compressed perspective, shallow depth of field",
    "shot on 200mm telephoto lens, compressed layers of torii gates",
]

DETAILS = [
    "ema wooden wishing plaques hanging in the breeze",
    "shimenawa sacred rope with white zigzag paper decorations",
    "stone fox (kitsune) statue partially covered in moss",
    "offerings of sake barrels stacked near the main hall",
    "incense smoke drifting through the sacred air",
    "traditional red lanterns swaying gently",
    "gravel path raked in perfect patterns",
]

def get_random_style():
    return (
        random.choice(CAMERA_ANGLES),
        random.choice(MOODS),
        random.choice(LENS_STYLES),
        random.choice(DETAILS),
    )

# ==========================================
# 🖼️ Imagen 이미지 생성 (Vertex AI)
# ==========================================
def generate_image(image_prompt, save_path):
    client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT,
        location=GCP_LOCATION,
    )

    angle, mood, lens, detail = get_random_style()

    enhanced_prompt = (
        f"{image_prompt}. "
        f"Composition: {angle}. "
        f"Mood: {mood}. "
        f"{lens}. "
        f"Include: {detail}. "
        "Photorealistic, ultra-detailed, professional travel photography, "
        "cinematic quality, no people, no text, no watermark, 8K resolution."
    )

    try:
        response = client.models.generate_images(
            model='imagen-4.0-fast-generate-001',
            prompt=enhanced_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",
                output_mime_type='image/jpeg',
                person_generation="dont_allow",
            )
        )

        if response.generated_images:
            image_bytes = response.generated_images[0].image.image_bytes
            with open(save_path, 'wb') as f:
                f.write(image_bytes)
            size_kb = len(image_bytes) / 1024
            print(f"  🖼️  생성 완료 ({size_kb:.0f}KB) | {angle[:30]}... | {mood[:25]}...")
            return True
        else:
            print(f"  ⚠️  이미지 생성 결과 없음")
            return False

    except Exception as e:
        print(f"  ❌ 생성 실패: {e}")
        return False


# ==========================================
# 🔍 MD 파일에서 image_prompt + slug 추출
# ==========================================
def get_info_from_md(md_filename):
    md_path = os.path.join(CONTENT_DIR, md_filename)
    if not os.path.exists(md_path):
        return None, None
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
        prompt = str(post.get('image_prompt', '')).strip()
        thumbnail = str(post.get('thumbnail', '')).strip()
        slug = os.path.splitext(os.path.basename(thumbnail))[0] if thumbnail else None
        return prompt or None, slug
    except Exception as e:
        print(f"  ⚠️  MD 읽기 오류: {e}")
        return None, None


# ==========================================
# 🚀 메인 실행
# ==========================================
def generate_all_images():
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # 영문 MD 파일만 기준 (_ko, _ja 제외)
    en_files = [
        f for f in os.listdir(CONTENT_DIR)
        if f.endswith('.md') and not f.endswith('_ko.md') and not f.endswith('_ja.md')
    ]

    total = len(en_files)
    print(f"\n⛩️  총 {total}개 신사 이미지 확인 시작...")
    print(f"   GCP: {GCP_PROJECT} / {GCP_LOCATION}")
    print(f"   모델: imagen-4.0-fast-generate-001\n")

    success = 0
    skipped = 0
    failed  = 0

    for i, md_file in enumerate(sorted(en_files), 1):
        image_prompt, slug = get_info_from_md(md_file)

        if not slug:
            slug = md_file.replace('.md', '')

        # webp로 저장
        save_path = os.path.join(IMAGES_DIR, f"{slug}.webp")

        print(f"[{i:03d}/{total}] {slug}")

        if os.path.exists(save_path) and os.path.basename(save_path) not in PROTECTED:
            print(f"  ⏭️  이미 존재 → 스킵")
            skipped += 1
            continue

        if not image_prompt:
            print(f"  ⚠️  image_prompt 없음 → 기본 프롬프트 사용")
            shrine_name = slug.replace('_', ' ').title()
            # 기본 프롬프트도 신사 종류별로 랜덤
            shrine_types = [
                "ancient Shinto shrine with vermilion torii gates",
                "sacred Japanese shrine surrounded by towering cedar forest",
                "historic temple complex with traditional wooden architecture",
                "mountain shrine with stone steps winding through the trees",
            ]
            image_prompt = (
                f"A {random.choice(shrine_types)} called {shrine_name} in Japan"
            )

        ok = generate_image(image_prompt, save_path)
        if ok:
            success += 1
        else:
            failed += 1

        time.sleep(1.0)

    print("\n" + "─" * 50)
    print(f"🎉 이미지 생성 완료!")
    print(f"   ✅ 성공  : {success}개")
    print(f"   ⏭️  스킵  : {skipped}개")
    print(f"   ❌ 실패  : {failed}개")
    print("─" * 50)


if __name__ == "__main__":
    generate_all_images()