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

def humanize_file(filepath):
    try:
        post = frontmatter.load(filepath)
        original_content = post.content
        lang = post.get('lang', 'en')
        
        # 이미 변환된 파일은 스킵 (다시 돌리려면 이 두 줄을 주석 처리하세요)
        if post.get('humanized') == True:
            return "SKIPPED"

        # 언어별 초감성 블로그 프롬프트 + 온천 삭제 규칙
        if lang == 'ko':
            prompt = f"""
            Role: 카메라 하나 메고 일본 구석구석을 혼자 여행하는 감성 에세이 작가 겸 블로거.
            Task: 아래의 설명적인 신사 가이드를 **완벽하게 내가 직접 다녀온 생생한 후기**로 탈바꿈시켜라.
            
            [절대 지켜야 할 작문 규칙]
            1. **시점과 말투:** 100% 1인칭 주인공 시점("저는", "제가"). 편안하고 감성적인 "~해요", "~했어요" 체를 사용할 것. (객관적인 백과사전 말투 절대 금지)
            2. **오감 묘사:** 아침 공기의 차가움, 오래된 목조 건물에서 나는 나무 향기, 자갈길 밟는 소리 등을 시적으로 묘사할 것.
            3. **생생한 경험담:** "처음엔 길을 좀 헤맸는데...", "사진 찍으려고 30분을 기다렸어요" 같은 리얼한 에피소드를 지어내서 자연스럽게 끼워 넣을 것.
            4. **온천 정보 완전 삭제 (중요):** 원문에 있는 "근처 온천(Onsen)" 관련 추천이나 섹션은 기계적인 느낌을 주므로 **아예 언급조차 하지 말고 전부 삭제할 것.**
            5. **포맷 유지:** 마크다운 헤더(`#`, `##`)와 이미지 링크(`![...](...)`)는 절대 건드리지 말고 제자리에 둘 것. (온천 헤더는 삭제)

            [Original Content]:
            {original_content}
            """
        elif lang == 'ja':
            prompt = f"""
            Role: カメラ片手に日本の神社仏閣を巡る、少しノスタルジックな一人旅エッセイスト兼ブロガー。
            Task: 以下の説明的なガイド文を、**完全に自分が実際に足を運んで書いた生々しい体験記**に書き換えること。

            [絶対的な執筆ルール]
            1. **視点と文体:** 100%一人称（「私は」「私が」）。読者に語りかけるような、温かく親しみやすい「〜です」「〜でした」調を使用。
            2. **五感の描写:** 澄んだ朝の空気、古い木造建築から漂う線香や木の香り、玉砂利を踏む音などを情緒豊かに描写すること。
            3. **リアルなエピソード:** 「最初は道に迷ってしまったのですが…」「写真を撮るために朝早く起きました」といった、実体験風の小話を自然に織り交ぜること。
            4. **温泉情報の完全削除（重要）:** 原文にある「近くの温泉（Onsen）」に関する推奨やセクションは、機械的な印象を与えるため、**一切言及せずに完全に削除すること。**
            5. **フォーマット維持:** Markdownのヘッダー(`#`, `##`)と画像リンク(`![...](...)`)は元の位置に残すこと。（温泉のヘッダーは削除）

            [Original Content]:
            {original_content}
            """
        else: # English (en)
            prompt = f"""
            Role: A solo traveler and passionate storyteller with a camera, wandering through Japan's hidden shrines.
            Task: Transform the following descriptive shrine guide into a **vivid, deeply personal, first-hand travel essay**.

            [Strict Writing Rules]
            1. **Perspective & Tone:** 100% first-person ("I", "my"). Conversational, warm, and authentic.
            2. **Sensory Details:** The chill of the crisp morning air, the scent of old wood, the crunch of gravel under your shoes.
            3. **Real-Life Micro-Moments:** Fabricate and seamlessly weave in relatable travel moments like getting a bit lost or waiting for the perfect photo.
            4. **DELETE ONSEN INFO (CRITICAL):** Completely remove any mention, section, or recommendation regarding "Nearby Onsen" or hot springs. It makes the article look like a template. Remove it entirely.
            5. **Keep the Format:** DO NOT alter or remove any Markdown headers (`#`, `##`) or image links (`![...](...)`) EXCEPT for the Onsen header, which should be deleted.

            [Original Content]:
            {original_content}
            """

        # API 호출 (병렬 처리되므로 순식간에 동시 요청됨)
        response = model.generate_content(prompt)
        new_content = response.text.strip()
        
        new_content = re.sub(r'([^\n])\n\*\s', r'\1\n\n* ', new_content)
        new_content = re.sub(r'([^\n])\n-\s', r'\1\n\n- ', new_content)

        post.content = new_content
        post['humanized'] = True 
        
        with open(filepath, 'wb') as f:
            frontmatter.dump(post, f)
            
        return f"SUCCESS [{lang.upper()}]: {os.path.basename(filepath)}"

    except Exception as e:
        return f"ERROR processing {os.path.basename(filepath)}: {e}"

def main():
    print(f"🚀 Starting ULTRA-FAST Humanization Process (Parallel Processing)...")
    
    files = [f for f in os.listdir(CONTENT_DIR) if f.endswith('.md')]
    total_files = len(files)
    
    print(f"📊 Found {total_files} Markdown files.")
    
    # 병렬 처리 시작 (max_workers로 동시에 실행할 개수 지정)
    # 유료 API 한도에 맞춰 10개씩 동시에 요청
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 모든 작업을 스레드풀에 예약
        futures = {executor.submit(humanize_file, os.path.join(CONTENT_DIR, filename)): filename for filename in files}
        
        # 먼저 완료되는 순서대로 결과 받아오기
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                completed += 1
                
                # 변환 성공 및 에러만 출력 (스킵된 건 굳이 다 출력 안 함)
                if "SUCCESS" in result or "ERROR" in result:
                    print(f"[{completed}/{total_files}] {result}")
                elif completed % 20 == 0:  # 스킵된 파일이 많을 때 중간 진행상황 확인용
                    print(f"   Progress: {completed}/{total_files} files checked/processed.")
                    
            except Exception as exc:
                print(f"❌ Task generated an exception: {exc}")

    print("\n🎉 All files processed! Don't forget to rebuild data.")
    print("👉 Run: python script/build_data.py")

if __name__ == "__main__":
    main()