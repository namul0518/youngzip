import streamlit as st
import streamlit.components.v1 as components
import requests
import secrets
from urllib.parse import urlencode

# 네이버 개발자 센터에서 받은 정보 (여기를 채우세요!)
CLIENT_ID = "r5bY8mbtvz12MEgtwN6j"
CLIENT_SECRET = "k7e7OJuB7I"
REDIRECT_URI = "https://youngzip.streamlit.app"

# 1. 로그인 상태 확인
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

# 2. 로그인 안 됐을 때 (로그인 버튼 + 인증 로직)
if st.session_state["user_info"] is None:
    st.title("🔐 영끌내집 네이버 로그인")
    
    # 보안용 state 생성
    state = secrets.token_urlsafe(16)
    st.session_state["oauth_state"] = state
    
    # 네이버 로그인 주소 생성
    auth_url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state={state}"
    
    st.markdown(f'<a href="{auth_url}" style="padding:15px; background:#03C75A; color:white; border-radius:10px; text-decoration:none;">네이버로 로그인</a>', unsafe_allow_html=True)

    # 네이버가 보내준 코드를 확인 (로그인 성공 후 돌아왔을 때)
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"]
        # 토큰 받기 (간략화)
        token_url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={code}&state={state}"
        token_res = requests.get(token_url).json()
        
        if "access_token" in token_res:
            # 프로필 가져오기
            headers = {"Authorization": f"Bearer {token_res['access_token']}"}
            profile = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers).json()
            st.session_state["user_info"] = profile["response"]
            st.rerun()

# 3. 로그인 성공 시 계산기 보여주기
else:
    st.success(f"{st.session_state['user_info']['name']}님 환영합니다!")
    
    # index.html 불러오기
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    components.html(html_code, height=2500)
    
    if st.sidebar.button("로그아웃"):
        st.session_state["user_info"] = None
        st.rerun()
