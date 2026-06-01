import streamlit as st
import streamlit.components.v1 as components
import requests
import secrets

CLIENT_ID = "r5bY8mbtvz12MEgtwN6j"
CLIENT_SECRET = "k7e7OJuB7I"
REDIRECT_URI = "https://youngzip.streamlit.app"

st.set_page_config(layout="wide")

# 세션 관리
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

# 로그인 성공 후 돌아왔을 때 처리
query_params = st.query_params
code = query_params.get("code")
state = query_params.get("state")

if code and st.session_state["user_info"] is None:
    # 1. 토큰 요청
    token_url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={code}&state={state}"
    res = requests.get(token_url).json()
    
    if "access_token" in res:
        # 2. 프로필 조회
        headers = {"Authorization": f"Bearer {res['access_token']}"}
        profile = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers).json()
        st.session_state["user_info"] = profile["response"]
        
        # 3. 주소창 비우기 (필수)
        st.query_params.clear()
        st.rerun()
    else:
        st.error(f"인증 실패: {res.get('error')}")

# 화면 출력
if st.session_state["user_info"] is None:
    st.title("🔐 영끌내집 로그인")
    # 고유 state 생성
    my_state = secrets.token_hex(16)
    auth_url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={my_state}"
    st.markdown(f'<a href="{auth_url}" style="padding:15px; background:#03C75A; color:white; border-radius:10px; text-decoration:none;">네이버로 로그인</a>', unsafe_allow_html=True)
else:
    # 로그인 성공 시 계산기
    if st.sidebar.button("로그아웃"):
        st.session_state["user_info"] = None
        st.rerun()
    with open("index.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=2500, scrolling=False)
