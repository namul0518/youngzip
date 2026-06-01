import streamlit as st
import streamlit.components.v1 as components
import requests

# 네이버 정보
CLIENT_ID = "r5bY8mbtvz12MEgtwN6j"
CLIENT_SECRET = "k7e7OJuB7I"
REDIRECT_URI = "https://youngzip.streamlit.app"

# 1. 로그인 확인 및 파라미터 체크
query_params = st.query_params
code = query_params.get("code")
state = query_params.get("state")

if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

# 2. 로그인 로직
if code and not st.session_state["user_info"]:
    # 토큰 요청
    token_url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={code}&state={state}"
    token_res = requests.get(token_url).json()
    
    if "access_token" in token_res:
        headers = {"Authorization": f"Bearer {token_res['access_token']}"}
        profile = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers).json()
        st.session_state["user_info"] = profile["response"]
        st.rerun() # 정보 저장 후 새로고침

# 3. 화면 표시
if st.session_state["user_info"] is None:
    st.title("🔐 영끌내집 로그인")
    auth_url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state=RANDOM_STATE"
    st.markdown(f'<a href="{auth_url}">네이버로 로그인</a>', unsafe_allow_html=True)
else:
    st.success(f"{st.session_state['user_info']['name']}님 환영합니다!")
    with open("index.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=2500)
