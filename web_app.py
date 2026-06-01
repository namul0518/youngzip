import streamlit as st
import streamlit.components.v1 as components
import requests

# Secrets에서 값 불러오기
CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
REDIRECT_URI = "https://youngzip.streamlit.app"

st.set_page_config(layout="wide")

if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

params = st.query_params
code = params.get("code")
state = params.get("state")

# 로그인 인증 처리
if code and st.session_state["user_info"] is None:
    token_url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={code}&state={state}"
    res = requests.get(token_url).json()
    
    if "access_token" in res:
        headers = {"Authorization": f"Bearer {res['access_token']}"}
        profile = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers).json()
        st.session_state["user_info"] = profile["response"]
        st.query_params.clear()
        st.rerun()
    else:
        st.error(f"인증 실패: {res.get('error_description', '알 수 없음')}")

# 화면 표시
if st.session_state["user_info"] is None:
    st.title("🔐 영끌내집 로그인")
    auth_url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state=1234"
    st.markdown(f'<a href="{auth_url}" style="padding:15px; background:#03C75A; color:white; border-radius:10px; text-decoration:none;">네이버로 로그인</a>', unsafe_allow_html=True)
else:
    # --- 수정할 부분 시작 ---
    if st.sidebar.button("로그아웃"):
        st.session_state["user_info"] = None
        # 네이버 로그아웃 페이지로 이동시키는 스크립트 실행
        components.html("""
            <script>
                window.location.href = "https://nid.naver.com/nidlogin.logout";
            </script>
        """, height=0)
        st.rerun()
    # --- 수정할 부분 끝 ---
    
    with open("index.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=2500, scrolling=False)
