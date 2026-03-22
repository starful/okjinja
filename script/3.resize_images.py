import os
import sys
import io
from PIL import Image

# ==========================================================
# [설정] 원본 이미지가 있는 폴더 (이곳의 파일들이 직접 수정됩니다)
# ==========================================================
SOURCE_DIR = os.path.join('app', 'content', 'images')

# 압축 기준 및 목표 용량 (단위: KB)
TARGET_THRESHOLD_KB = 100  # 이 용량을 넘거나, WebP가 아니면 처리 대상
TARGET_SIZE_KB = 90        # 압축 후 목표 용량

# 이미지 최대 가로 크기 및 품질 설정
MAX_WIDTH = 1200
START_QUALITY = 90
MIN_QUALITY = 50
# ==========================================================

def compress_to_target_size(img, target_bytes):
    """
    이미지를 목표 파일 크기 미만이 될 때까지 품질을 낮추며 메모리 상에서 압축합니다.
    """
    buffer = io.BytesIO()
    
    for quality in range(START_QUALITY, MIN_QUALITY - 1, -5):
        buffer.seek(0)
        buffer.truncate()
        img.save(buffer, 'webp', quality=quality, method=6)
        
        if buffer.tell() < target_bytes:
            return buffer
            
    # 최소 품질에서도 목표 크기 초과 시 그대로 반환
    return buffer

def process_image_inplace(filepath):
    """
    이미지를 읽어서 최적화한 뒤, 원본 위치에 WebP로 저장하고 기존 파일은 정리합니다.
    """
    try:
        filename = os.path.basename(filepath)
        name, ext = os.path.splitext(filename)
        
        # 이미 최적화된 WebP이고 용량도 작다면 스킵
        original_size = os.path.getsize(filepath)
        is_webp = ext.lower() == '.webp'
        
        with Image.open(filepath) as img:
            width, height = img.size
            needs_resize = width > MAX_WIDTH
            
            # [조건] 1. WebP이고 2. 용량도 작고 3. 리사이징도 필요 없으면 -> 패스
            if is_webp and original_size < (TARGET_THRESHOLD_KB * 1024) and not needs_resize:
                return "SKIPPED"

            print(f"⚡ Processing: {filename} ({original_size/1024:.1f} KB) -> WebP converting...")

            # 1. 리사이징 (가로 1200px 초과 시)
            if needs_resize:
                ratio = MAX_WIDTH / float(width)
                new_height = int(float(height) * ratio)
                img = img.resize((MAX_WIDTH, new_height), Image.Resampling.LANCZOS)

            # 2. 색상 모드 변환 (투명도 없는 JPG 등은 RGB로, PNG는 유지하거나 변환)
            # 신사 사진 등 실사 이미지는 RGB가 압축률이 좋습니다.
            if img.mode in ('RGBA', 'P') and not is_webp:
                 # 필요하다면 투명도 유지 로직 추가 가능하나, 보통 사진은 RGB 변환
                 img = img.convert('RGB')
            elif img.mode != 'RGB':
                 img = img.convert('RGB')

            # 3. 압축 실행
            target_bytes = TARGET_SIZE_KB * 1024
            compressed_buffer = compress_to_target_size(img, target_bytes)
            
            # 4. 저장 (무조건 .webp 확장자로 저장)
            new_filename = name + ".webp"
            new_filepath = os.path.join(os.path.dirname(filepath), new_filename)
            
            with open(new_filepath, 'wb') as f:
                f.write(compressed_buffer.getvalue())
            
            final_size = os.path.getsize(new_filepath)

            # 5. [중요] 원본 파일이 WebP가 아니었다면(예: .jpg), 원본 삭제
            if filepath != new_filepath:
                os.remove(filepath)
                return f"CONVERTED (Deleted {ext})"
            
            return f"OPTIMIZED ({original_size/1024:.1f}KB -> {final_size/1024:.1f}KB)"

    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return "ERROR"

def main():
    if not os.path.exists(SOURCE_DIR):
        print(f"❌ Error: Directory '{SOURCE_DIR}' not found.")
        sys.exit(1)

    print(f"🚀 Starting In-Place Image Optimization...")
    print(f"   Target: {SOURCE_DIR}")
    print(f"   Format: Force Convert to WebP")
    print("-" * 50)

    files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    total_files = len(files)
    
    processed_count = 0
    
    for i, filename in enumerate(files):
        filepath = os.path.join(SOURCE_DIR, filename)
        result = process_image_inplace(filepath)
        
        if result != "SKIPPED":
            processed_count += 1
            print(f"   [{i+1}/{total_files}] {result}")

    print("-" * 50)
    print(f"✨ Complete! Optimized {processed_count} images directly in source folder.")

if __name__ == '__main__':
    main()