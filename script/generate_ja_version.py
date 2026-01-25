import os
import frontmatter
import google.generativeai as genai
import time
import re
from datetime import datetime
from dotenv import load_dotenv

# --- 1. 環境設定 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
CONTENT_DIR = os.path.join(BASE_DIR, 'app', 'content')

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# 高性能モデルを使用 (gemini-1.5-flash-latest)
model = genai.GenerativeModel("gemini-flash-latest")

# カテゴリの日本語マッピング
CAT_MAP_JA = {
    "Wealth": "金運", "Love": "縁結び", "Health": "健康",
    "Success": "合格・必勝", "Safety": "安全", "History": "歴史"
}

def generate_ja_expanded():
    all_files = os.listdir(CONTENT_DIR)
    # 英語版のみを抽出 (_ko, _ja を除く)
    en_files = [f for f in all_files if f.endswith('.md') and not ('_ko.md' in f or '_ja.md' in f)]
    
    print(f"🚀 日本語コンテンツ拡張生成開始 (対象: {len(en_files)}件)")

    for filename in en_files:
        ja_filename = filename.replace('.md', '_ja.md')
        ja_filepath = os.path.join(CONTENT_DIR, ja_filename)
        
        # すでに日本語版が存在する場合はスキップ
        if os.path.exists(ja_filepath):
            continue

        print(f"🇯🇵 コンテンツ拡張中: {filename} -> {ja_filename}")
        
        en_path = os.path.join(CONTENT_DIR, filename)
        post = frontmatter.load(en_path)

        # 改行と文字数拡張のための強力なプロンプト (すべて日本語で構成)
        prompt = f"""
        Role: 神社仏閣巡りに精通した専門ライター、および神道・日本史の専門家。
        Task: 以下の英語の神社ガイドをベースに、**日本語読者のための約5,000〜7,000文字の超詳細な究極ガイド**を作成せよ。

        [指針 - Markdownの改行ルール：厳守]
        1. 箇条書き（* や -）を使用する際は、**必ず新しい行**から開始すること。
        2. 各リスト項目の間には、**必ず「空行（Empty Line）」を1行挿入**すること。項目が連続して固まるのを防げ。
        3. 段落（Paragraph）が切り替わる際も、必ず2回の改行（空行）を入れること。
        4. 情報が文字の塊（Text Block）にならないよう、小見出し（###）を多用して視覚的に整理すること。

        [補筆・拡張の指針]
        1. 既存の内容を単に訳すのではなく、圧倒的な知識量で大幅に補筆せよ。
        2. 構成案：
           - イントロ：その神社の特有の空気感や、今訪れるべき情緒的な理由。
           - 御由緒と歴史：創建にまつわる神話、時代背景、主祭神のエピソード（非常に詳しく）。
           - 境内の徹底ガイド：鳥居、参道、拝殿、摂社・末社、御神木などの意味と歴史的な見どころ。
           - パワースポットの核心：どの場所で、どのようなエネルギーや御利益を感じるべきか。
           - 御朱印と授与品：限定の御朱印のデザインや、その神社独自のお守り、絵馬の詳細。
           - 地元通の旅ヒント：周辺の老舗店、隠れた名店グルメ、歴史的な街並みの散策ルート。
           - 基本情報：テーブル形式（住所、アクセス、参拝時間）。
           - 周辺の温浴施設：近くの温泉や銭湯の情報を大幅に拡張して紹介。
        3. 文体：非常に丁寧で、読者に寄り添う「です・ます」調。
        4. 分量：日本語で5,000〜7,000文字程度。Web上で最も詳しいガイドを目指すこと。

        [Original Title]: {post.get('title')}
        [Original Content]:
        {post.content}
        """

        try:
            response = model.generate_content(prompt)
            ja_content = response.text.strip()

            # [補正] AIが万が一改行を忘れた場合の強制処理
            ja_content = re.sub(r'([^\n])\n\*\s', r'\1\n\n* ', ja_content)
            ja_content = re.sub(r'([^\n])\n-\s', r'\1\n\n- ', ja_content)

            new_post = frontmatter.Post(ja_content)
            new_post.metadata = post.metadata.copy()
            
            # タイトルの抽出
            title_match = re.search(r'^#\s+(.+)$', ja_content, re.MULTILINE)
            new_post['title'] = title_match.group(1).strip() if title_match else post.get('title')
            
            new_post['lang'] = 'ja'
            
            # タグ生成プロンプト
            tag_prompt = f"この神社に関連する日本語の検索タグ10個をカンマ区切りで作成して（例：東京旅行, 御朱印巡り...）: {new_post['title']}"
            tag_resp = model.generate_content(tag_prompt)
            new_post['tags'] = [t.strip() for t in tag_resp.text.split(',')]
            
            new_post['categories'] = [CAT_MAP_JA.get(c, c) for c in post.get('categories', [])]
            
            # 要約文生成プロンプト
            summary_prompt = f"SEO用の日本語要約文(100文字以内)を作成して。クリックしたくなるような魅力的な文章で:\n{ja_content[:500]}"
            summary_resp = model.generate_content(summary_prompt)
            new_post['excerpt'] = summary_resp.text.strip()

            with open(ja_filepath, 'wb') as f:
                frontmatter.dump(new_post, f)
            
            print(f"✅ 保存完了: {ja_filename} (約{len(ja_content)}文字)")
            time.sleep(5) 

        except Exception as e:
            print(f"❌ エラー発生 ({filename}): {e}")

if __name__ == "__main__":
    generate_ja_expanded()