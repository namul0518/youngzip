import streamlit as st
import streamlit.components.v1 as components

# 스트림릿 화면 설정
st.set_page_config(page_title="영끌내집", layout="wide")

# index.html 파일을 읽어옵니다.
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    # 읽어온 HTML을 화면에 출력합니다.
    components.html(html_content, height=2500, scrolling=True)
except FileNotFoundError:
    st.error("index.html 파일을 찾을 수 없습니다.")
