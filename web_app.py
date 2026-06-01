import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

# 세션에 로그인 상태 저장 (없으면 False로 초기화)
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# 로그인 여부에 따라 화면 분기
if not st.session_state["logged_in"]:
    st.title("🔐 영끌내집 이용을 위한 로그인")
    # 네이버 로그인 테스트 버튼
    if st.button("네이버로 로그인하기"):
        # 여기서 실제 네이버 연동 로직이 작동합니다.
        st.session_state["logged_in"] = True
        st.rerun()
else:
    # 로그인 성공 시 index.html 띄우기
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    
    # 여기서 scrolling=False를 설정하여 스크롤바 2개 문제 방지
    components.html(html_code, height=2500, scrolling=False)
    
    # 로그아웃 버튼 (사이드바에 배치)
    if st.sidebar.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()
