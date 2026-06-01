import streamlit as st
import streamlit.components.v1 as components
import requests

# 네이버 정보 (네이버 개발자 센터 설정과 동일해야 함)
CLIENT_ID = "r5bY8mbtvz12MEgtwN6j"
CLIENT_SECRET = "k7e7OJuB7I"
REDIRECT_URI = "https://youngzip.streamlit.app"

st.set_page_config(page_title="영끌내집", layout="wide")

# 세션에 정보 저장
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

# 1. 로그인 인증 처리 (주소창의 code를 읽어옴)
query_params = st.query_params
code = query_params.get("code")
state = query_params.get("state")

if code and st.session_state["user_info"] is None:
    # 네이버로부터 토큰 받기
    token_url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={code}&state={state}"
    token_res = requests.get(token_url).json()
    
    if "access_token" in token_res:
        headers = {"Authorization": f"Bearer {token_res['access_token']}"}
        profile = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers).json()
        st.session_state["user_info"] = profile["response"]
        # 주소창에서 code 파라미터 삭제 (중요: 무한루프 방지)
        st.query_params.clear()
        st.rerun()

# 2. 로그인 화면 출력
if st.session_state["user_info"] is None:
    st.title("🔐 영끌내집 네이버 로그인")
    auth_url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state=RANDOM_STATE"
    st.markdown(f'<a href="{auth_url}" style="padding:15px; background:#03C75A; color:white; border-radius:10px; text-decoration:none;">네이버로 로그인</a>', unsafe_allow_html=True)

# 3. 로그인 성공 시 계산기 출력
else:
    st.sidebar.success(f"{st.session_state['user_info']['name']}님 환영합니다!")
    if st.sidebar.button("로그아웃"):
        st.session_state["user_info"] = None
        st.rerun()
    
    with open("index.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=2500)
