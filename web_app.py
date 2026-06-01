import streamlit as st
import streamlit.components.v1 as components

# 페이지 설정
st.set_page_config(page_title="영끌내집", layout="wide")

# index.html 파일의 내용을 그대로 읽어서 화면에 뿌려줍니다.
with open("index.html", "r", encoding="utf-8") as f:
    html_code = f.read()

# 이제 버튼과 자바스크립트가 정상 작동합니다.
components.html(html_code, height=1500)
