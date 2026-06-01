import streamlit as st
import streamlit.components.v1 as components
import requests

CLIENT_ID = "r5bY8mbtvz12MEgtwN6j"
CLIENT_SECRET = "k7e7OJuB7I"
REDIRECT_URI = "https://youngzip.streamlit.app"

st.set_page_config(layout="wide")

# 세션에 정보가 있으면 바로 계산기 보여주기
if "user_info" in st.session_state and st.session_state["user_info"]:
    st.sidebar.write(f"환영합니다, {st.session_state['user_info']['name']}님!")
    if st.sidebar.button("로그아웃"):
        st.session_state["user_info"] = None
        st.rerun()
    with open("index.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=2500, scrolling=False)
else:
    # 로그인 처리 로직
    params = st.query_params
    code = params.get("code")
    state = params.get("state")
    
    if code:
        # 네이버 토큰 요청
        token_url = f"https://nid.naver.com/oauth2.0/token?grant_type=authorization_code&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&code={code}&state={state}"
        token_res = requests.get(token_url).json()
        
        if "access_token" in token_res:
            headers = {"Authorization": f"Bearer {token_res['access_token']}"}
            profile = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers).json()
            st.session_state["user_info"] = profile["response"]
            # 쿼리 파라미터 삭제 (무한 루프 방지)
            st.query_params.clear()
            st.rerun()
        else:
            st.error("로그인 정보 확인 실패. 다시 시도해 주세요.")
            st.session_state["user_info"] = None
    else:
        # 로그인 화면
        st.title("🔐 영끌내집 로그인")
        auth_url = f"https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&state=1234"
        st.markdown(f'<a href="{auth_url}" style="padding:15px; background:#03C75A; color:white; border-radius:10px; text-decoration:none;">네이버로 로그인</a>', unsafe_allow_html=True)
