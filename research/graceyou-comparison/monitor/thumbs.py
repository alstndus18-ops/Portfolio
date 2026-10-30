"""상품 갤러리용 썸네일. 최신 수집의 의류 상품(색상 묶음 1개당 대표 1장)을 받아 브랜드×카테고리별 격자 이미지로 묶는다.
  python monitor/thumbs.py
원본: monitor/cache/thumbs/<brand>/<product_id>.jpg (이미 받은 것은 다시 받지 않음)
결과: monitor/out/thumbs/<brand>-<n>.jpg (180×240 칸, 10열) + monitor/out/thumbs/index.json
브랜드 상품 사진이므로 공개 저장소에 커밋하지 않는다(.gitignore).
"""
import hashlib
import io
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import model_units, runs_by_date  # noqa: E402
from collect import CATEGORIES  # noqa: E402

HERE = Path(__file__).resolve().parent
RAW = HERE / 'cache' / 'thumbs'
OUT = HERE / 'out' / 'thumbs'
BRANDS = ['graceu', 'kume', 'nw', 'jj', 'orr', 'lamerei', 'voyonn']
W, H, COLS = 180, 240, 10


def fetch(url, path):
    if path.exists():
        return True
    try:
        time.sleep(0.25)
        req = urllib.request.Request(url if not url.startswith('//') else 'https:' + url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': url.split('/', 3)[0] + '//' + url.split('/')[2] + '/'})
        data = urllib.request.urlopen(req, timeout=30).read()
        im = Image.open(io.BytesIO(data)).convert('RGB')
        im.thumbnail((W * 2, H * 2))
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path, 'JPEG', quality=82)
        return True
    except Exception as e:  # noqa: BLE001
        print('  실패', url[:80], e, flush=True)
        return False


def cover(im):
    """3:4 칸에 맞게 가운데를 잘라 채운다."""
    r = W / H
    w, h = im.size
    if w / h > r:
        nw = int(h * r)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / r)
        im = im.crop((0, 0, w, nh))  # 세로로 길면 위쪽(얼굴·상의) 기준
    return im.resize((W, H), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    index = {}
    for b in BRANDS:
        reps = runs_by_date(b)
        run = reps[max(reps)]
        order = {p['product_id']: i for i, p in enumerate(run['products'])}
        units = model_units(b, [p for p in run['products'] if p['in_clothing_scope'] and p['sale_price'] and p.get('image_url')])
        units.sort(key=lambda p: order[p['product_id']])  # 사이트 목록 순서
        jobs = [(p['image_url'], RAW / b / (hashlib.md5(p['product_id'].encode()).hexdigest()[:12] + '.jpg')) for p in units]
        with ThreadPoolExecutor(3) as ex:
            ok = list(ex.map(lambda j: fetch(*j), jobs))
        print(b, f'{sum(ok)}/{len(ok)}', flush=True)
        for ci, c in enumerate(CATEGORIES):
            items = [(p, path) for p, (_, path), good in zip(units, jobs, ok) if good and p['category'] == c]
            if not items:
                continue
            rows = (len(items) + COLS - 1) // COLS
            sheet = Image.new('RGB', (COLS * W, rows * H), (245, 243, 240))
            for k, (p, path) in enumerate(items):
                sheet.paste(cover(Image.open(path).convert('RGB')), ((k % COLS) * W, (k // COLS) * H))
            fn = f'{b}-{ci}.jpg'
            sheet.save(OUT / fn, 'JPEG', quality=78, optimize=True, progressive=True)
            for k, (p, _) in enumerate(items):
                index[p['product_id'] + '|' + b] = [fn, k % COLS, k // COLS]
    (OUT / 'index.json').write_text(json.dumps({'cell': [W, H], 'cols': COLS, 'items': index}, ensure_ascii=False), encoding='utf-8')
    print(OUT, len(index))


if __name__ == '__main__':
    main()
