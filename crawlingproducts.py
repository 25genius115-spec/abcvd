# crawl_products.py

import argparse
import csv
import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from docx import Document


SEARCH_URL = "https://search.danawa.com/dsearch.php"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

OUTPUT_COLUMNS = [
    "category",
    "original_product",
    "alternative_type",
    "product_name",
    "price",
    "shop",
    "product_url",
    "image_url",
    "eco_reason",
    "eco_verified",
    "co2_saved_kg",
    "plastic_saved_g",
    "water_saved_l",
]


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_url(url):
    if not url:
        return ""

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return urljoin("https://search.danawa.com", url)

    return url


def parse_price(text):
    if not text:
        return None

    numbers = re.sub(r"[^\d]", "", text)

    if not numbers:
        return None

    try:
        return int(numbers)
    except ValueError:
        return None


# --------------------------------------------------
# 1. DOCX에서 "일반 제품 → 친환경 대체품" 자동 추출
# --------------------------------------------------

def load_alternatives_from_docx(docx_path):
    doc = Document(docx_path)

    current_category = ""
    items = []

    for paragraph in doc.paragraphs:
        text = clean_text(paragraph.text)

        if not text:
            continue

        # "1. 먹고 마시기", "2. 쇼핑·포장" 같은 카테고리
        category_match = re.match(r"^\d+\.\s*(.+)$", text)

        if category_match:
            current_category = category_match.group(1).strip()
            continue

        # ● 플라스틱 칫솔 → 대나무 칫솔, 교체형 칫솔
        if "→" not in text:
            continue

        text = re.sub(r"^[●•\-]\s*", "", text)

        left, right = text.split("→", 1)

        original_product = clean_text(left)

        # 문서에서는 쉼표로 여러 대체품이 구분됨.
        # '교체형·재사용 면도기'의 · 는 그대로 유지.
        alternatives = [
            clean_text(x)
            for x in right.split(",")
            if clean_text(x)
        ]

        for alternative in alternatives:
            items.append({
                "category": current_category,
                "original_product": original_product,
                "alternative_type": alternative,
            })

    return items


# --------------------------------------------------
# 2. 다나와 검색
# --------------------------------------------------

def search_danawa(session, keyword, limit=3):
    params = {
        "query": keyword,
        "tab": "goods",
    }

    response = session.get(
        SEARCH_URL,
        params=params,
        headers=HEADERS,
        timeout=15,
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 현재/과거 다나와 구조를 모두 어느 정도 대응
    product_nodes = soup.select(
        "li.prod_item, "
        "div.main_prodlist li.prod_item"
    )

    results = []
    seen_urls = set()

    for node in product_nodes:

        classes = " ".join(node.get("class", []))

        # 광고 영역 제외
        if "prod_ad_item" in classes:
            continue

        # 상품명
        name_tag = (
            node.select_one("p.prod_name a")
            or node.select_one("a[name='productName']")
            or node.select_one(".prod_name a")
        )

        if not name_tag:
            continue

        product_name = clean_text(name_tag.get_text(" ", strip=True))

        if not product_name:
            continue

        product_url = normalize_url(name_tag.get("href", ""))

        if not product_url:
            continue

        if product_url in seen_urls:
            continue

        # 가격
        price_tag = (
            node.select_one("p.price_sect strong")
            or node.select_one(".price_sect strong")
            or node.select_one(".price_sect a")
        )

        price = parse_price(
            price_tag.get_text(" ", strip=True)
            if price_tag
            else ""
        )

        # 이미지
        image_tag = (
            node.select_one("a.thumb_link img")
            or node.select_one(".thumb_image img")
            or node.select_one("img")
        )

        image_url = ""

        if image_tag:
            image_url = (
                image_tag.get("data-original-src")
                or image_tag.get("data-src")
                or image_tag.get("src")
                or ""
            )

            image_url = normalize_url(image_url)

        # 품절 여부
        node_text = clean_text(node.get_text(" ", strip=True))

        if "품절" in node_text:
            continue

        seen_urls.add(product_url)

        results.append({
            "product_name": product_name,
            "price": price,
            "shop": "다나와",
            "product_url": product_url,
            "image_url": image_url,
        })

        if len(results) >= limit:
            break

    return results


# --------------------------------------------------
# 3. 전체 자동 수집
# --------------------------------------------------

def crawl_all(docx_path, output_path, limit_per_keyword=3):

    alternatives = load_alternatives_from_docx(docx_path)

    print(f"대체품 검색어: {len(alternatives)}개")

    session = requests.Session()

    rows = []
    failed = []

    global_seen = set()

    for index, item in enumerate(alternatives, start=1):

        keyword = item["alternative_type"]

        print(
            f"[{index}/{len(alternatives)}] "
            f"{item['original_product']} → {keyword}"
        )

        try:
            products = search_danawa(
                session,
                keyword,
                limit=limit_per_keyword,
            )

            if not products:
                failed.append(keyword)
                continue

            for product in products:

                # 전체 DB 중복 제거
                dedupe_key = product["product_url"]

                if dedupe_key in global_seen:
                    continue

                global_seen.add(dedupe_key)

                rows.append({
                    "category": item["category"],
                    "original_product": item["original_product"],
                    "alternative_type": keyword,
                    "product_name": product["product_name"],
                    "price": product["price"],
                    "shop": product["shop"],
                    "product_url": product["product_url"],
                    "image_url": product["image_url"],

                    # 이번 단계에서는 환경효과를 임의 생성하지 않음
                    "eco_reason": f"{item['original_product']}의 대체품",
                    "eco_verified": False,
                    "co2_saved_kg": "",
                    "plastic_saved_g": "",
                    "water_saved_l": "",
                })

        except Exception as e:
            print(f"  실패: {e}")
            failed.append(keyword)

        # 서버에 과도한 요청을 보내지 않도록 간격
        time.sleep(random.uniform(0.8, 1.5))

    save_csv(rows, output_path)

    print()
    print("완료")
    print(f"수집 제품: {len(rows)}개")
    print(f"실패 검색어: {len(failed)}개")

    if failed:
        print("실패 목록:")
        for keyword in failed:
            print(f"- {keyword}")


def save_csv(rows, output_path):

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=OUTPUT_COLUMNS,
        )

        writer.writeheader()
        writer.writerows(rows)


# --------------------------------------------------
# 실행
# --------------------------------------------------

if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "docx",
        help="친환경 대체품 목록 DOCX",
    )

    parser.add_argument(
        "--output",
        default="data/products.csv",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="대체품 하나당 가져올 상품 수",
    )

    args = parser.parse_args()

    crawl_all(
        args.docx,
        args.output,
        args.limit,
    )
