import streamlit as st
import os
import secrets
from urllib.parse import urlencode
import requests
import csv
from datetime import datetime
from pathlib import Path

# 페이지 설정
st.set_page_config(page_title="부동산 분석 엔진", layout="wide")

# 1. 스트림릿 시크릿에서 키 가져오기 (오류 방지)
try:
    NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
    NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]
except:
    st.error("⚠️ Streamlit Secrets에 NAVER_CLIENT_ID와 NAVER_CLIENT_SECRET을 설정해주세요.")
    st.stop()

# 리다이렉트 주소는 배포 환경에 맞게 고정
REDIRECT_URI = "https://youngzip.streamlit.app"
NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"

# 세션 상태 초기화
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

# 로그인 함수들
def build_naver_auth_url(state):
    params = {"response_type": "code", "client_id": NAVER_CLIENT_ID, "redirect_uri": REDIRECT_URI, "state": state}
    return f"{NAVER_AUTH_URL}?{urlencode(params)}"

# UI 시작
st.markdown("## 🏠 부동산 분석 엔진")

# 탭 나누기
tab1, tab2, tab3 = st.tabs(["📊 주담대 한도", "🏠 정책대출 진단", "🎯 맞춤 유형 추천"])

with tab1:
    st.info("여기에 계산기 기능을 넣으세요.")

with tab2:
    if not st.session_state["logged_in"]:
        st.warning("정책대출 진단을 이용하려면 로그인이 필요합니다.")
        state = secrets.token_urlsafe(16)
        st.session_state["oauth_state"] = state
        auth_url = build_naver_auth_url(state)
        st.markdown(f'<a href="{auth_url}" style="padding:10px; background:#03C75A; color:white; border-radius:5px; text-decoration:none;">네이버로 로그인</a>', unsafe_allow_html=True)
    else:
        st.success("정책대출 진단 페이지입니다.")

with tab3:
    if not st.session_state["logged_in"]:
        st.warning("맞춤 유형 추천을 이용하려면 로그인이 필요합니다.")
    else:
        st.write("맞춤 유형 추천 페이지입니다.")
