import os
import re
import time
import frontmatter
from google import genai
from google.genai import types
from dotenv import load_dotenv

# ==========================================
# ⚙️ 설정
# ==========================================
load_dotenv()

# Vertex AI 방식 (gcloud auth application-default login 필요)
GCP_PROJECT  = os.environ.get("GCP_PROJECT", "starful-258005")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
BASE_DIR    = os.path.dirname(SCRIPT_DIR)
CONTENT_DIR = os.path.join(BASE_DIR, 'app', 'content')
IMAGES_DIR  = os.path.join(BASE_DIR, 'app', 'content', 'images')  # 신사는 /content/images/

PROTECTED = {'logo.jpg', 'favicon.ico', 'Torii.png', 'omikuji_box.png'}

# ==========================================
# 🖼️ Imagen 4 이미지 생성 (Vertex AI)
# ==========================================
def generate_image(image_prompt, save_path):
    client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT,
        location=GCP_LOCATION,
    )

    enhanced_prompt = (
        f"{image_prompt}, "
        "photorealistic, ultra-detailed, professional travel photography, "
        "golden hour lighting, cinematic atmosphere, "
        "shot on Sony A7R V with 24mm wide angle lens, "
        "sharp foreground with natural bokeh background, 8K resolution"
    )

    try:
        response = client.models.generate_images(
            model='imagen-4.0-generate-001',
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
            print(f"  🖼️  생성 완료 ({size_kb:.0f}KB)")
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
    """MD 파일에서 image_prompt와 slug를 읽어옵니다."""
    md_path = os.path.join(CONTENT_DIR, md_filename)
    if not os.path.exists(md_path):
        return None, None
    try:
        with open(md_path, 'r', encoding='utf-8') as f:
            post = frontmatter.load(f)
        prompt = str(post.get('image_prompt', '')).strip()
        thumbnail = str(post.get('thumbnail', '')).strip()
        # thumbnail: /content/images/shrine_slug.webp → shrine_slug
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

    # 영문 MD 파일만 기준으로 처리 (_ko, _ja 제외)
    en_files = [
        f for f in os.listdir(CONTENT_DIR)
        if f.endswith('.md') and not f.endswith('_ko.md') and not f.endswith('_ja.md')
    ]

    total = len(en_files)
    print(f"\n⛩️  총 {total}개 신사 이미지 확인 시작...")
    print(f"   GCP 프로젝트: {GCP_PROJECT} / {GCP_LOCATION}\n")

    success = 0
    skipped = 0
    failed  = 0

    for i, md_file in enumerate(sorted(en_files), 1):
        image_prompt, slug = get_info_from_md(md_file)

        # slug가 없으면 MD 파일명에서 추출
        if not slug:
            slug = md_file.replace('.md', '')

        # webp로 저장 (신사 사이트 기준)
        save_path = os.path.join(IMAGES_DIR, f"{slug}.webp")

        print(f"[{i:03d}/{total}] {slug}")

        # 이미 이미지가 있으면 스킵
        if os.path.exists(save_path) and os.path.basename(save_path) not in PROTECTED:
            print(f"  ⏭️  이미 존재 → 스킵")
            skipped += 1
            continue

        # image_prompt 없으면 기본 프롬프트
        if not image_prompt:
            print(f"  ⚠️  image_prompt 없음 → 기본 프롬프트 사용")
            shrine_name = slug.replace('_', ' ').title()
            image_prompt = (
                f"A beautiful Japanese Shinto shrine called {shrine_name}, "
                "traditional red torii gates, stone lanterns, ancient cedar trees, "
                "sacred grounds with gravel path, morning mist atmosphere"
            )

        print(f"  📝 프롬프트: {image_prompt[:60]}...")

        ok = generate_image(image_prompt, save_path)
        if ok:
            success += 1
        else:
            failed += 1

        time.sleep(1.0)

    print("\n" + "─" * 50)
    print(f"🎉 이미지 생성 완료!")
    print(f"   ✅ 성공  : {success}개")
    print(f"   ⏭️  스킵  : {skipped}개 (이미 존재)")
    print(f"   ❌ 실패  : {failed}개")
    print("─" * 50)


if __name__ == "__main__":
    generate_all_images()
