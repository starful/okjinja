import os
import frontmatter
import google.generativeai as genai
import re
from dotenv import load_dotenv
import concurrent.futures  # 병렬 처리를 위한 라이브러리 추가

# --- 1. 설정 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
CONTENT_DIR = os.path.join(BASE_DIR, 'app', 'content')

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("❌ Error: GEMINI_API_KEY not found in .env file.")
    exit(1)

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-flash-latest")

CAT_MAP_KO = { "Wealth": "재물", "Love": "사랑", "Health": "건강", "Success": "성공", "Safety": "안전", "History": "역사" }
CAT_MAP_JA = { "Wealth": "金運", "Love": "縁結び", "Health": "健康", "Success": "合格・必勝", "Safety": "安全", "History": "歴史" }

def generate_version(en_post, target_lang, output_path):
    if os.path.exists(output_path):
        return "SKIPPED"

    original_content = en_post.content
    original_title = en_post.get('title', '')

    if target_lang == 'ko':
        prompt = f"""
        Role: 카메라 하나 메고 일본 구석구석을 혼자 여행하는 감성 에세이 작가 겸 블로거.
        Task: 아래 영어 신사 가이드를 바탕으로 **한국인을 위한 생생한 1인칭 여행기(블로그 포스팅)**를 새로 작성해주세요.
        
        [작성 지침]
        1. **말투:** "~해요", "~했답니다" 같은 친근하고 부드러운 구어체 사용.
        2. **내용 확장:** 원문 내용을 기반으로 오감 묘사(냄새, 소리 등)와 생생한 에피소드를 추가할 것.
        3. **온천 정보 완전 삭제 (중요):** 원문에 온천(Onsen) 이야기가 있다면 절대 번역하지 말고 완전히 삭제할 것.
        4. **구성:** 
           - **도입부:** 호기심을 자극하는 인사말과 방문 이유.
           - **본문:** 1인칭 시점의 생생한 탐방기.
           - **꿀팁:** "💡 솔직한 팁:", "⚠️ 주의사항:" 섹션 포함.
           - **결론:** "## 6. ✨ Conclusion:" 섹션으로 마무리하며 따뜻한 추천사 작성.
        5. **형식:** 마크다운 헤더(#, ##)와 이미지 링크(![...](...)) 구조는 유지. 리스트 항목 앞뒤엔 빈 줄 추가.

        [Original Title]: {original_title}
        [Original Content]:
        {original_content}
        """
        cat_map = CAT_MAP_KO

    elif target_lang == 'ja':
        prompt = f"""
        Role: カメラ片手に日本の神社仏閣を巡る、少しノスタルジックな一人旅エッセイスト兼ブロガー。
        Task: 以下の英語ガイドを元に、**日本人読者に向けた臨場感あふれる一人称の旅行記**を作成してください。

        [執筆ガイドライン]
        1. **文体:** 「〜です」「〜ます」調で、親しみやすく語りかけるように。
        2. **内容拡充:** 原文をベースにしつつ、五感の描写（香り、音など）やリアルなエピソードを大幅に加筆。
        3. **温泉情報の完全削除（重要）:** 原文に温泉の話があっても、絶対に翻訳せず、完全に削除すること。
        4. **構成:**
           - **導入:** 読者を引き込む挨拶と訪れたきっかけ。
           - **本文:** 五感を使った臨場感ある参拝レポート。
           - **アドバイス:** 「💡 ここだけの話：」「⚠️ 注意点：」などのヒント。
           - **結び:** 「## 6. ✨ Conclusion:」で締めくくる。
        5. **形式:** Markdownヘッダー(#, ##)や画像リンク(![...](...))は維持。リストの前後には空行を入れる。

        [Original Title]: {original_title}
        [Original Content]:
        {original_content}
        """
        cat_map = CAT_MAP_JA

    try:
        response = model.generate_content(prompt)
        new_content = response.text.strip()

        new_content = re.sub(r'([^\n])\n\*\s', r'\1\n\n* ', new_content)
        new_content = re.sub(r'([^\n])\n-\s', r'\1\n\n- ', new_content)

        new_post = frontmatter.Post(new_content)
        new_post.metadata = en_post.metadata.copy()
        new_post['lang'] = target_lang
        
        title_match = re.search(r'^#\s+(.+)$', new_content, re.MULTILINE)
        if title_match:
            new_post['title'] = title_match.group(1).strip()

        new_post['categories'] = [cat_map.get(c, c) for c in en_post.get('categories', [])]
        
        tag_prompt = f"Generate 10 relevant SEO tags in {target_lang} for '{new_post['title']}', comma separated."
        tag_resp = model.generate_content(tag_prompt)
        new_post['tags'] = [t.strip() for t in tag_resp.text.split(',')]

        summary_prompt = f"Summarize in {target_lang} for SEO (120 chars):\n{new_content[:500]}"
        summary_resp = model.generate_content(summary_prompt)
        new_post['excerpt'] = summary_resp.text.strip()
        new_post['humanized'] = True

        with open(output_path, 'wb') as f:
            frontmatter.dump(new_post, f)

        return f"CREATED [{target_lang.upper()}]: {os.path.basename(output_path)}"

    except Exception as e:
        return f"ERROR [{target_lang.upper()}] {original_title}: {e}"

def main():
    print(f"🚀 Starting ULTRA-FAST Multilingual Generation (Parallel Processing)...")
    
    files = [f for f in os.listdir(CONTENT_DIR) if f.endswith('.md') and not ('_ko.md' in f or '_ja.md' in f)]
    
    print(f"📊 Found {len(files)} English source files.")

    # 1. 실행할 모든 작업(Task) 리스트 만들기
    tasks = []
    for filename in files:
        en_path = os.path.join(CONTENT_DIR, filename)
        
        try:
            en_post = frontmatter.load(en_path)
        except Exception as e:
            print(f"⚠️ Failed to load {filename}: {e}")
            continue

        ko_path = os.path.join(CONTENT_DIR, filename.replace('.md', '_ko.md'))
        ja_path = os.path.join(CONTENT_DIR, filename.replace('.md', '_ja.md'))
        
        tasks.append((en_post, 'ko', ko_path))
        tasks.append((en_post, 'ja', ja_path))

    total_tasks = len(tasks)
    print(f"⚙️ Total translation tasks to run: {total_tasks}")

    # 2. 병렬 처리 시작 (max_workers로 동시에 실행할 개수 지정)
    # 유료 API의 경우 10~20개 정도를 동시에 돌려도 무방합니다.
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 모든 작업을 스레드풀에 던짐
        futures = {executor.submit(generate_version, post, lang, path): (lang, path) for post, lang, path in tasks}
        
        # 완료되는 순서대로 결과 출력
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                completed += 1
                
                # 생성 완료된 것만 로그 출력 (SKIPPED는 진행률만 표시)
                if "CREATED" in result or "ERROR" in result:
                    print(f"[{completed}/{total_tasks}] {result}")
                elif completed % 10 == 0:
                    print(f"   Progress: {completed}/{total_tasks} tasks completed.")
                    
            except Exception as exc:
                print(f"❌ Task generated an exception: {exc}")

    print("\n🎉 All multilingual versions generated!")

if __name__ == "__main__":
    main()