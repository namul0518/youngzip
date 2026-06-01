import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="영끌내집", layout="wide")

# 세션 상태에 로그인 정보 저장
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# 로그인 안 되어 있을 때
if not st.session_state["logged_in"]:
    st.title("🔐 서비스 이용을 위해 로그인이 필요합니다.")
    # 네이버 로그인 버튼 (나중에 네이버 연동을 완성하면 이 버튼이 네이버로 보내줍니다)
    if st.button("네이버로 로그인"):
        st.session_state["logged_in"] = True
        st.rerun()

# 로그인 되어 있을 때
else:
    # index.html 파일을 불러옴
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    
    # 탭 클릭 시 안 사라지도록 여기에서 HTML을 띄움
    components.html(html_code, height=2500)
    
    if st.sidebar.button("로그아웃"):
        st.session_state["logged_in"] = False
        st.rerun()
