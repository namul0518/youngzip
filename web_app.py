import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="영끌내집", layout="wide")

# 로그인 확인
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    st.title("🔐 서비스 이용을 위해 로그인이 필요합니다.")
    # 새 창(target="_blank")으로 네이버 로그인 페이지를 띄움
    login_url = "https://nid.naver.com/oauth2.0/authorize?..." # 대표님의 실제 인증 주소
    st.markdown(f'<a href="{login_url}" target="_blank" style="padding:15px; background:#03C75A; color:white; border-radius:10px; text-decoration:none;">네이버로 로그인</a>', unsafe_allow_html=True)
    
    # 임시 확인 버튼 (로그인 연동 완료 전 테스트용)
    if st.button("테스트 로그인"):
        st.session_state["logged_in"] = True
        st.rerun()
else:
    # 로그인 되었으면 index.html 불러오기
    with open("index.html", "r", encoding="utf-8") as f:
        components.html(f.read(), height=2500)
    
    if st.sidebar.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()
