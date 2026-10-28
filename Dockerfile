# 연구회 운영위원회 회의자료 생성기 — 컨테이너 이미지
# 빌드:  docker build -t meeting-docs .
# 실행:  docker run -p 8766:8766 -v meeting_docs_data:/data -e MEETING_DOCS_SECRET=<임의 긴 문자열> meeting-docs
FROM mcr.microsoft.com/playwright/python:v1.64.1-noble

# 한글 글꼴 (PDF 렌더링용). 나눔명조/고딕 + Noto CJK
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-nanum fonts-noto-cjk \
    && fc-cache -f && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/

# DB·업로드 이미지는 /data 볼륨에 저장
ENV MEETING_DOCS_DATA=/data \
    PYTHONUTF8=1 \
    PORT=8766
RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8766

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
