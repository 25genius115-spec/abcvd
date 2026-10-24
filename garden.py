"""인증 기록을 하나의 일러스트 정원으로 보여줍니다."""
import base64
from html import escape
import json
import math
from pathlib import Path

import streamlit as st


ASSETS = Path(__file__).resolve().parent / 'assets'
METRICS = {'탄소': ('co2_saved_kg', 'kgCO₂e', 1)}
SPECIES = [
    ('garden_simple_round.png', '초록 나무'),
    ('garden_simple_pink.png', '벚나무'),
    ('garden_simple_pine.png', '소나무'),
]
# 길을 비워두고 원경부터 전경으로 심는 위치입니다. 기록이 늘어도 기존 나무는 움직이지 않습니다.
POSITIONS = [
    (24, 29, 1.05), (73, 26, 1.02), (47, 43, .72), (12, 45, .70),
    (86, 43, .74), (52, 21, 1.04), (9, 13, 1.08), (91, 12, 1.09),
    (34, 10, 1.15), (69, 7, 1.16), (64, 42, .72), (37, 30, .90),
]


@st.cache_data(show_spinner=False)
def art_data(filename):
    return base64.b64encode((ASSETS / filename).read_bytes()).decode('ascii')


def tree_size(value, reference):
    if value is None or value <= 0:
        return .45
    return .5 + .5 * min(value / reference, 1)


def savings_breakdown(records, field):
    """현재 표시한 기록만 합산합니다. 미확인 값은 0으로 바꾸지 않습니다."""
    confirmed, estimated = [], []
    for row in records:
        value = row.get(field)
        if value is None:
            continue
        target = estimated if field in row.get('garden_estimated_fields', []) else confirmed
        target.append(value)
    return {
        'total': sum(confirmed) + sum(estimated) if confirmed or estimated else None,
        'confirmed': sum(confirmed) if confirmed else None,
        'estimated': sum(estimated) if estimated else None,
        'count': len(confirmed) + len(estimated),
    }


def show_record_basis(row):
    """선택한 나무에 연결된 실제 저장 근거와 문헌의 가정을 보여줍니다."""
    evidence = row.get('impact_evidence') or []
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except (TypeError, ValueError):
            evidence = []
    if row.get('impact_verified'):
        st.markdown('**제품별 확인 근거**')
        if row.get('impact_basis'):
            st.write(row['impact_basis'])
        for item in evidence if isinstance(evidence, list) else []:
            if item.get('metric') != 'co2':
                continue
            if item.get('formula'):
                st.code(item['formula'], language=None, wrap_lines=True)
            if item.get('quote'):
                st.text(item['quote'])
        for index, source in enumerate((row.get('impact_source') or '').splitlines(), 1):
            if source.startswith(('https://', 'http://')):
                st.link_button(f'제품 자료 {index}', source)
    if row.get('co2_saved_kg') is None:
        st.caption('제품별 탄소 수치가 없으면 적용 가능한 품목 기준표를 확인합니다.')
    estimate = row.get('estimate') or {}
    if estimate.get('version') == 'workbook-reference-v2':
        st.markdown('**품목별 참고 예상값**')
        st.write(estimate['basis'])
        st.code(estimate['formula'], language=None, wrap_lines=True)
        st.caption(estimate['assumptions'])
        st.caption('평가 범위: ' + estimate['scope'])
        st.caption('추정 방식: ' + estimate['method'])
        st.caption('출처 위치: ' + estimate['source_note'].split('위치:')[-1].strip())
        if estimate.get('source_check') != 'primary_checked':
            st.caption('제공된 기준표의 참고 수치입니다. 원문을 독립적으로 재검증한 제품별 확인값은 아닙니다.')
        for index, source in enumerate(estimate['sources'], 1):
            st.link_button(f'참고 자료 {index}', source)
        if not estimate['aggregate_on_purchase']:
            st.info('사용 횟수·에너지·중량 조건의 시나리오입니다. 구매만으로 누적 절감량에 합산하지 않습니다.')
        st.caption('개별 제품의 실측값이 아닙니다. 참고 예상값은 랭킹·보상에서 제외됩니다.')


def species_for(purchase_id):
    # 인증 ID로 수종을 고정해 새로고침해도 같은 나무를 보여줍니다.
    return SPECIES[(purchase_id - 1) % len(SPECIES)]


def scene_html(records, field, unit, reference, owner, total, zone=1, carbon_records=None):
    trees = []
    for index, row in enumerate(records):
        x, bottom, depth = POSITIONS[index]
        size = tree_size(row.get(field), reference)
        # 기본 나무도 보이게 하고, 성장은 풍경에 어울리는 범위로 제한합니다.
        width = (17 + size * 9) * depth
        height = (25 + size * 15) * depth
        filename, species = species_for(row['purchase_id'])
        value = row.get(field)
        status = '성장 데이터 확인 중' if value is None else f'{value:,.3g} {unit}'
        if field in row.get('garden_estimated_fields', []):
            status += ' · 추정'
        if row.get('verification_method') == 'DEVELOPER_TEST':
            status += ' · 시연'
        title = escape(f"{species} · {row['product_name']} · {status}", quote=True)
        trees.append(f'''<div class="garden-tree" tabindex="0" role="img" aria-label="{title}"
            style="left:{x}%;bottom:{bottom}%;width:{width:.2f}%;height:{height:.2f}%;
            z-index:{100-round(bottom)};--delay:{index*.17:.2f}s">
            <span class="tree-shadow"></span><img class="tree-paint" alt="{title}" src="data:image/png;base64,{art_data(filename)}">
            </div>''')
    safe_owner = escape(str(owner), quote=True)
    carbon = savings_breakdown(carbon_records if carbon_records is not None else records, 'co2_saved_kg')
    estimated = carbon['estimated'] is not None
    headline = '예상 탄소 절감량' if estimated else '내가 줄인 탄소'
    amount = (('약 ' if estimated else '') + f"{carbon['total']:,.4g} <span>kgCO₂e</span>") if carbon['total'] is not None else '확인 중'
    return '''<style>
    .painted-garden{position:relative;isolation:isolate;overflow:hidden;border-radius:24px;
      aspect-ratio:1.36;background:#e8edda;
      box-shadow:0 8px 28px #334b3210;color:#304536;margin:6px 0 18px}
    .garden-background{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:-1}
    .painted-garden::after{content:"";position:absolute;inset:0;pointer-events:none;z-index:200;
      box-shadow:inset 0 0 80px #f7f2dc30;border:1px solid #ffffff70;border-radius:24px}
    .garden-heading{position:absolute;top:5%;left:5%;right:5%;z-index:210;text-align:center}
    .garden-heading p{font-size:clamp(14px,2.5vw,19px);color:#52664d;margin:0 0 4px}
    .garden-heading strong{display:block;font-size:clamp(30px,6vw,48px);font-weight:650;
      line-height:1.2;letter-spacing:-1px;color:#304536}
    .garden-heading strong span{font-size:.42em;font-weight:500;letter-spacing:0}
    .garden-light{position:absolute;inset:0;pointer-events:none;z-index:120;
      background:radial-gradient(ellipse at 12% 3%,#fff3bc60,transparent 58%);mix-blend-mode:soft-light}
    .garden-spark{position:absolute;width:3px;height:3px;border-radius:50%;background:#fff6cd;
      box-shadow:0 0 7px #fff6cd;pointer-events:none;z-index:125;animation:garden-drift 8s infinite ease-in-out}
    .garden-spark:nth-of-type(2){animation-delay:-3s}.garden-spark:nth-of-type(3){animation-delay:-5s}
    .garden-tree{position:absolute;transform:translateX(-50%);outline:none}
    .tree-paint{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;object-position:center bottom;
      filter:drop-shadow(3px 7px 3px #32472c13);transform-origin:50% 100%;
      animation:garden-arrive .65s both;animation-delay:var(--delay);transition:filter .25s,transform .25s}
    .tree-shadow{position:absolute;width:58%;height:8%;bottom:-1%;left:22%;
      background:#344e3533;border-radius:50%;filter:blur(5px)}
    .garden-tree:hover .tree-paint,.garden-tree:focus .tree-paint{transform:scale(1.045);
      filter:drop-shadow(2px 6px 5px #334a3130)}
    @keyframes garden-arrive{from{opacity:0;transform:translateY(9px) scale(.95)}to{opacity:1;transform:none}}
    @keyframes garden-drift{0%,100%{opacity:0;transform:translate(0,0)}40%,70%{opacity:.7}80%{transform:translate(10px,-16px)}}
    @media(prefers-reduced-motion:reduce){.tree-paint,.garden-spark{animation:none;transition:none}}
    @media(max-width:480px){.painted-garden{aspect-ratio:1.1;border-radius:18px}
      .garden-heading{top:6%}}
    </style>''' + f'''<section class="painted-garden" aria-label="{safe_owner}님의 정원"
      ><img class="garden-background" alt="부드러운 초록 언덕과 산책길이 있는 정원" src="data:image/png;base64,{art_data('garden_simple_meadow.png')}"><header class="garden-heading"><p>{headline}</p><strong>{amount}</strong></header>
      {''.join(trees)}<div class="garden-light"></div>
      <span class="garden-spark" style="left:18%;top:48%"></span>
      <span class="garden-spark" style="left:64%;top:65%"></span>
      <span class="garden-spark" style="left:83%;top:38%"></span>
      </section>'''


def show_garden(history):
    records = sorted(history, key=lambda row: row['purchase_id'])
    field, unit, reference = METRICS['탄소']
    pages = max(1, math.ceil(len(records) / 12))
    zone = st.selectbox('정원 구역', range(1, pages + 1)) if pages > 1 else 1
    visible = records[(zone - 1) * 12:zone * 12]
    owner = st.session_state.get('display_name', '나')
    st.html(scene_html(visible, field, unit, reference, owner, len(records), zone, records))
    carbon = savings_breakdown(records, field)
    st.caption(f"인증 {len(records)}건 · 탄소 근거 {carbon['count']}건 반영")
    if carbon['estimated'] is not None:
        st.caption('품목별 참고 예상값 포함 · 개별 제품 실측값 아님 · 랭킹·보상 제외')
    with st.expander('탄소 절감량은 어떻게 계산하나요?'):
        st.write('제품 1개당 탄소 절감량 = 같은 기능·용량·사용횟수의 일반 제품 배출량 − 선택 제품 배출량')
        st.caption('같은 자료가 두 제품의 비교 단위와 범위를 명시한 경우에만 계산합니다. 직접 명시된 절감량이 있으면 그 값을 우선합니다. 묶음 상품도 인증 1건당 제품 1개 기준으로 반영합니다.')
        st.write('누적 탄소 절감량 = 근거가 확인된 인증 기록별 절감량의 합계')
        st.caption('제품별 확인값이 없으면 조건이 맞는 품목별 기준표의 예상값을 보완합니다. 같은 기록의 확인값과 예상값은 중복 합산하지 않습니다. 사용 횟수가 필요한 미래 효과는 구매 즉시 합산하지 않습니다.')
        st.caption('나무는 인증 1건에 1그루입니다. 크기는 탄소 1kgCO₂e를 화면 성장 기준으로 사용하며 실제 식재량으로 환산하지 않습니다.')
    if not records:
        return
    with st.container(border=True):
        st.markdown('#### 이 나무가 아낀 것')
        by_id = {row['purchase_id']: row for row in visible}
        selected = st.selectbox('나무 선택', list(by_id),
            format_func=lambda key: f"{species_for(key)[1]} · {by_id[key]['product_name']}")
        row = by_id[selected]
        st.write(row['product_name'])
        st.caption(f"심은 날: {row.get('activity_date') or '날짜 미확인'}")
        for metric, (key, metric_unit, _) in METRICS.items():
            value = row.get(key)
            kind = '문헌 추정' if key in row.get('garden_estimated_fields', []) else '확인값'
            st.write(f'{metric}: {value:,.3g} {metric_unit} · {kind}' if value is not None else f'{metric}: 데이터 없음')
        with st.expander('이 제품의 계산식 · 근거'):
            show_record_basis(row)
        if row.get('verification_method') == 'DEVELOPER_TEST':
            st.caption('시연 나무 · 실제 보상 제외')
