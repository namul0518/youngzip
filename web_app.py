import streamlit as st
import streamlit.components.v1 as components

# 스트림릿 설정 (가장 안전한 기본값)
st.set_page_config(layout="wide")

# index.html 파일 읽기
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    components.html(html_code, height=2500, scrolling=False)
except Exception as e:
    st.error(f"파일을 불러오는 중 에러가 발생했습니다: {e}")
