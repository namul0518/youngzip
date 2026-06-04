import streamlit as st
import streamlit.components.v1 as components
import json
from pathlib import Path

# 페이지 설정
st.set_page_config(
    page_title="영끌내집 — 내 집 마련 계산기",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# [테스트용] 로그인 강제 승인
st.session_state["logged_in"] = True
st.session_state["user_profile"] = {"nickname": "테스트유저", "email": "test@test.com", "provider": "naver"}

st.info("테스트 모드: 로그인 완료 상태입니다.")

# 계산기 렌더링
CALC = Path(__file__).parent / "calculator.html"
if not CALC.exists():
    st.error("calculator.html 파일이 없습니다.")
    st.stop()

html = CALC.read_text(encoding="utf-8")
extra_css = """
<style>
  #loginGate button { display: none !important; }
</style>
"""
html = html.replace(
    "<head>",
    f"<head>{extra_css}<script>var APP_LOGGED_IN=true;var APP_AUTH_URL='';</script>",
    1,
)

# 모바일: 결과 렌더 후 부모창 스크롤 처리
scroll_js = """
<script>
window.addEventListener('message', function(e){
  if(e.data && e.data.type === 'scrollToTop'){
    window.scrollTo({top:0, behavior:'smooth'});
  }
});
</script>
"""
html = html.replace("</body>", scroll_js + "</body>", 1)

components.html(html, height=2400, scrolling=False)