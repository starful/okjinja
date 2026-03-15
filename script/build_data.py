import os
import json
import frontmatter
import markdown
from bs4 import BeautifulSoup
from datetime import datetime

# 스크립트 위치 기준 경로 설정
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

CONTENT_DIR = os.path.join(BASE_DIR, 'app', 'content')
STATIC_DIR = os.path.join(BASE_DIR, 'app', 'static')

JSON_OUTPUT = os.path.join(STATIC_DIR, 'json', 'shrines_data.json')
SITEMAP_OUTPUT = os.path.join(STATIC_DIR, 'sitemap.xml')

BASE_URL = 'https://okjinja.com'

def strip_markdown(text):
    try:
        html = markdown.markdown(text)
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text()
    except Exception as e:
        return text

def generate_sitemap(shrines):
    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    
    last_updated = datetime.now().strftime("%Y-%m-%d")

    xml.append('  <url>')
    xml.append(f'    <loc>{BASE_URL}/</loc>')
    xml.append(f'    <lastmod>{last_updated}</lastmod>')
    xml.append('    <changefreq>daily</changefreq>')
    xml.append('    <priority>1.0</priority>')
    xml.append('  </url>')

    for shrine in shrines:
        link = shrine['link']
        date_str = shrine.get('published', last_updated)
        xml.append('  <url>')
        xml.append(f'    <loc>{BASE_URL}{link}</loc>')
        xml.append(f'    <lastmod>{date_str}</lastmod>')
        xml.append('    <changefreq>weekly</changefreq>')
        xml.append('    <priority>0.8</priority>')
        xml.append('  </url>')
        
    xml.append('</urlset>')
    return '\n'.join(xml)

def main():
    print(f"🔨 빌드 스크립트 시작 (Root: {BASE_DIR})")
    
    shrines = []
    
    os.makedirs(os.path.dirname(JSON_OUTPUT), exist_ok=True)
    if not os.path.exists(CONTENT_DIR):
        print(f"❌ Content directory not found: {CONTENT_DIR}")
        return

    for filename in os.listdir(CONTENT_DIR):
        if not filename.endswith('.md'): continue
        
        filepath = os.path.join(CONTENT_DIR, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
                
                lang = post.get('lang', 'en')
                
                if post.get('draft') == True: continue
                if not post.get('lat') or not post.get('lng'): continue
                
                date_val = post.get('date')
                published_date = str(date_val) if date_val else datetime.now().strftime('%Y-%m-%d')
                
                summary = post.get('summary')
                if not summary:
                    summary = strip_markdown(post.content)[:120] + '...'

                # [수정] 온천(has_onsen) 검사 로직 완전히 삭제됨

                shrine = {
                    "id": filename.replace('.md', ''),
                    "lang": lang,
                    "title": post.get('title', 'No Title'),
                    "lat": post.get('lat'),
                    "lng": post.get('lng'),
                    "categories": post.get('categories', []),
                    "thumbnail": post.get('thumbnail', '/static/images/default.png'),
                    "address": post.get('address', ''),
                    "published": published_date,
                    "summary": summary,
                    "link": f"/shrine/{filename.replace('.md', '')}"
                }
                shrines.append(shrine)
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")

    shrines.sort(key=lambda x: x['published'], reverse=True)

    final_data = {
        "last_updated": datetime.now().strftime("%Y.%m.%d"),
        "shrines": shrines
    }
    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    sitemap_content = generate_sitemap(shrines)
    with open(SITEMAP_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(sitemap_content)

    print(f"\n🎉 빌드 완료! 총 {len(shrines)}개 신사 데이터 처리됨. (온천 정보 제거됨)")

if __name__ == "__main__":
    main()