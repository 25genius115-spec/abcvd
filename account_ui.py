"""메인 화면 앞에 표시하는 로그인·회원가입 화면."""
import streamlit as st

from api_client import APIError, get_current_user, login_user, register_user


def clear_session():
    # 다른 사용자가 이전 구매 사진·인증번호·개인 기록을 이어받지 않게 합니다.
    st.session_state.clear()


def require_login():
    token = st.session_state.get("auth_token")
    if token:
        try:
            user = get_current_user(token)
        except APIError as error:
            if error.status_code == 401:
                clear_session()
                st.warning("로그인이 만료되었습니다. 다시 로그인해주세요.")
            else:
                st.warning(str(error))
                st.stop()
        else:
            for key in ("username", "display_name", "role", "developer_tools_enabled"):
                st.session_state[key] = user[key]
            return

    st.title("🌱 초록선택")
    st.write("작은 선택이 숲이 되는 곳.")
    login_tab, register_tab = st.tabs(["로그인", "회원가입"])
    with login_tab:
        with st.form("login", clear_on_submit=True):
            username = st.text_input("아이디", max_chars=64, autocomplete="username")
            password = st.text_input("비밀번호", type="password", max_chars=256, autocomplete="current-password")
            submitted = st.form_submit_button("로그인", type="primary", width="stretch")
        if submitted:
            try:
                result = login_user(username, password)
            except APIError as error:
                st.warning(str(error))
            else:
                clear_session()
                st.session_state.auth_token = result["token"]
                for key in ("username", "display_name", "role", "developer_tools_enabled"):
                    st.session_state[key] = result["user"][key]
                st.session_state.user_id = result["user"]["id"]
                st.rerun()
    with register_tab:
        with st.form("register", clear_on_submit=True):
            username = st.text_input("아이디", max_chars=64, key="register_username")
            name = st.text_input("표시 이름", max_chars=100)
            password = st.text_input("비밀번호 (6자 이상)", type="password", max_chars=256)
            confirm = st.text_input("비밀번호 확인", type="password", max_chars=256)
            submitted = st.form_submit_button("회원가입", type="primary", width="stretch")
        if submitted:
            if password != confirm:
                st.warning("비밀번호가 일치하지 않습니다.")
            else:
                try:
                    register_user(username, password, name)
                except APIError as error:
                    st.warning(str(error))
                else:
                    st.success("가입되었습니다. 로그인 탭에서 로그인해주세요.")
    st.stop()
