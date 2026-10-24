import streamlit as st

from api_client import APIError, logout_user
from account_ui import clear_session, require_login

st.set_page_config(
    page_title="초록선택 | 친환경 제품 찾기",
    page_icon="🌱",
    layout="centered",
    initial_sidebar_state="expanded",
)

require_login()

# 모든 페이지의 이동 메뉴를 여기에서 관리합니다.
pages = [
    st.Page("pages/home.py", title="홈", icon="🏡", default=True),
    st.Page("pages/find_products.py", title="제품 찾기", icon="🌿"),
    st.Page("pages/purchase.py", title="제품 인증", icon="🧾"),
    st.Page("pages/impact.py", title="나의 정원", icon="🌏"),
    st.Page("pages/ranking.py", title="월간 랭킹", icon="🏆"),
]
if st.session_state.get('role') == 'developer' and st.session_state.get('developer_tools_enabled'):
    pages.append(st.Page('pages/admin.py', title='관리자 패널', icon='🛠️'))
page = st.navigation(pages)

with st.sidebar:
    st.divider()
    st.write(f"{st.session_state.display_name}님")
    if st.button("로그아웃"):
        try:
            logout_user(st.session_state.auth_token)
        except APIError as error:
            if error.status_code != 401:
                st.warning("서버에서 로그아웃하지 못했습니다. 다시 시도해주세요.")
                st.stop()
        clear_session()
        st.rerun()

page.run()
