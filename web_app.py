import streamlit as st
import streamlit.components.v1 as components

# 페이지 설정
st.set_page_config(layout="wide")

# index.html 파일 읽기
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
    components.html(html_code, height=5000, scrolling=False)
except FileNotFoundError:
    st.error("index.html 파일을 찾을 수 없습니다.")
