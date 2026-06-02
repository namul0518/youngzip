#!/bin/bash
# Nginx를 거치지 않고 바로 FastAPI와 Streamlit을 각각 실행하거나, 
# 혹은 Render에서 제공하는 명령어를 직접 사용하도록 합니다.
# 우선 간단하게 Streamlit만 먼저 띄워보겠습니다.
streamlit run streamlit_app.py --server.port $PORT
