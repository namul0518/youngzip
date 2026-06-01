import streamlit as st
import streamlit.components.v1 as components
import requests

# 네이버 개발자 센터의 앱 정보와 정확히 일치해야 합니다.
CLIENT_ID = "r5bY8mbtvz12MEgtwN6j"
CLIENT_SECRET = "k7e7OJuB7I"
REDIRECT_URI = "https://youngzip.streamlit.app"

st.set_page_config(layout="wide")

# 1. 세션 상태 관리 (로그인 정보 유지)
if "user_info" not in st.session_state:
    st.session_state["user_info"] = None

# 2. 주소창의 code 파라미터 확인 (네이버에서 돌아왔을 때)
params = st.query_params
code = params.get("code")
state = params.get("state")

if code and st.session_state["user_info"] is None:
    # 네이버 토큰 요청
    token_url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={code}&state={state}"
    token_res = requests.get(token_url).json()
    
    if "access_token" in token_res:
        # 사용자 프로필 가져오기
        headers = {"Authorization": f"Bearer {token_res['access_token']}"}
        profile = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers).json()
        st.session_state["user_info"] = profile["response"]
        # 주소창 정리 (무한 루프 방지)
        st.query_params.clear()
        st.rerun()

# 3. 화면 분기
if st.session_state["user_info"] is None:
    st.title("🔐 영끌내집 로그인")
    # 네이버 로그인 주소 생성 (state는 임시 고정값)
    auth_url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state=1234"
    st.markdown(f'<a href="{auth_url}" style="padding:15px; background:#03C75A; color:white; border-radius:10px; text-decoration:none;">네이버로 로그인</a>', unsafe_allow_html=True)
else:
    # 로그인 성공 시 계산기 띄우기
    st.sidebar.write(f"환영합니다, {st.session_state['user_info']['name']}님!")
    if st.sidebar.button("로그아웃"):
        st.session_state["user_info"] = None
        st.rerun()
    
    with open("index.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=2500, scrolling=False)
