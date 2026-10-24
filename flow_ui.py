"""제품 선택부터 기여도까지 세 화면에서 같은 이동 안내를 보여줍니다."""
import streamlit as st


def show_flow(current):
    steps = [('제품 찾기', 'pages/find_products.py'),
             ('제품 인증', 'pages/purchase.py'),
             ('나의 정원', 'pages/impact.py')]
    for number, (column, (label, page)) in enumerate(zip(st.columns(3), steps), 1):
        with column:
            if number == current:
                st.markdown(f'**🟢 {number}. {label}**')
            else:
                st.page_link(page, label=f'{number}. {label}')
