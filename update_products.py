"""실행: python3 update_products.py — 검색 하나가 실패해도 다음 대체품을 진행합니다."""
import json
import os
import re
import unicodedata
from pathlib import Path

from docx import Document
from backend.database import get_connection, initialize_database
from backend.product_catalog import migrate_catalog, save_product
from backend.product_search import search_products
from backend.exa_search import ExaSearchError

ROOT = Path(__file__).resolve().parent


def find_document():
    for path in ROOT.glob('*.docx'):
        if unicodedata.normalize('NFC', path.name) == '친환경_대체품_목록.docx':
            return path
    raise FileNotFoundError('프로젝트 폴더에 친환경_대체품_목록.docx가 필요합니다.')


def extract_alternatives(path):
    document = Document(path)
    category = '기타'
    result = []
    seen = set()

    def add(original, alternatives, group):
        for alternative in re.split(r'[,，\n]+', alternatives):
            alternative = alternative.strip()
            key = (group, original.strip(), alternative)
            if all(key) and key not in seen:
                seen.add(key)
                result.append(dict(zip(('category', 'original_product', 'alternative_type'), key)))

    # 문서 순서대로 문단·표를 읽어 카테고리 제목을 유지합니다.
    for block in document.iter_inner_content():
        if hasattr(block, 'text'):
            text = block.text.strip()
            heading = re.match(r'^\d+[.)]\s*(.+)$', text)
            if heading and '→' not in text and '->' not in text:
                category = heading.group(1).strip()
            elif '→' in text or '->' in text:
                original, alternatives = re.split(r'→|->', text, maxsplit=1)
                add(original, alternatives, category)
        else:
            for row in block.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if any('기존 제품' == value or '카테고리' == value for value in cells):
                    continue
                if len(cells) >= 3:
                    if cells[0]:
                        category = cells[0]
                    add(cells[1], cells[2], category)
                elif len(cells) == 2:
                    add(cells[0], cells[1], category)
    return result


def main():
    alternatives = extract_alternatives(find_document())
    # 같은 대체품이 여러 분류에 있으면 검색을 재사용하되 원문 추출 목록은 보존합니다.
    unique = {}
    for item in alternatives:
        unique.setdefault(item['alternative_type'], item)
    report = {'extracted_alternatives': len(alternatives), 'unique_searches': len(unique),
              'saved_products': 0, 'failed_searches': [], 'empty_searches': [],
              'skipped_duplicates': 0, 'status': 'complete'}
    initialize_database()
    with get_connection() as connection:
        migrate_catalog(connection)
    key = os.getenv('EXA_API_KEY')
    if not key:
        report['status'] = 'blocked_missing_api_key'
        (ROOT / 'product_collection_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"대체품 {len(alternatives)}개 추출. EXA_API_KEY를 설정한 터미널에서 실행해주세요. 검색은 실행하지 않았습니다.")
        return

    for alternative in unique.values():
        try:
            products = search_products(alternative)
            if not products:
                report['empty_searches'].append(alternative['alternative_type'])
            for product in products:
                saved = save_product(product)
                report['saved_products'] += saved
                report['skipped_duplicates'] += int(not saved)
        except ExaSearchError as error:
            report['status'] = 'stopped_provider_error'
            report['message'] = str(error)
            report['failed_searches'].append(alternative['alternative_type'])
            report['unattempted_searches'] = len(unique) - list(unique).index(alternative['alternative_type']) - 1
            (ROOT / 'product_collection_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(str(error))
            break
        except Exception:
            # 키나 제공자 응답 원문을 출력/저장하지 않습니다.
            report['failed_searches'].append(alternative['alternative_type'])
        (ROOT / 'product_collection_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"추출 {len(alternatives)}개 / 저장 {report['saved_products']}개 / 실패 검색어 {len(report['failed_searches'])}개")


if __name__ == '__main__':
    main()
