# 연구회 운영위원회 회의자료 생성기

한국언론학회 **연구회 운영위원회 회의자료**(제52-1차 회의자료 HWP 양식 기준)를 웹에서 입력·취합하여
PDF로 자동 생성하는 서비스입니다. 제53대 집행부용으로 초기값이 들어 있습니다.

## 실행

```bash
cd meeting-docs
.\run.bat
```

처음 실행 시 가상환경 생성, 패키지 설치, PDF용 Chromium(약 120MB) 설치까지 자동으로 진행됩니다.
이후 브라우저에서 <http://localhost:8766> 을 엽니다. 같은 네트워크의 다른 PC에서는 `http://<이 PC IP>:8766`.

- 관리자 초기 계정: `admin` / `admin1234` → **설정** 페이지에서 반드시 변경
- 포트 변경: 환경변수 `MEETING_DOCS_PORT`
- 데이터 위치: `data/app.db`(SQLite), `data/uploads/`(이미지). 이 폴더만 백업하면 됩니다.

## 사용 흐름

1. **관리자(사무국)**
   - 설정: 학회명, 대수(53), 회장 성명·소속, 학회 로고, 제53대 이미지(표지 하단), 비밀번호
   - 위원회 명단: 집행부 위원(직책/성명/소속) 편집, 드래그로 순서 변경
   - 연구회 명단: 연구회명·회장·총무, 신임(*)·예비·활성 여부, **연구회별 접속코드** 확인/재발급
   - 회의 만들기 → 기본 정보(일시·장소·방식·진행자·보고 기간 상/하반기) → 안건 순서 편집(드래그/▲▼, 일반 안건은 마크다운 본문 + 이미지)
2. **연구회(회장·총무)**
   - `/g/login` 에서 연구회 선택 + 접속코드 입력
   - "{지난 반기} 활동 내역" / "{다음 반기} 활동 계획" 두 구역에 자유 서술 또는 항목 추가
     (정기학술대회 세션 / 세미나·워크숍·특강 / 출판·저술 / 기타), 사진 업로드(선택)
   - 임시저장 → 미리보기 → 제출 완료 (마감 전까지 수정 가능)
3. **취합·출력**
   - 취합 현황 페이지에서 연구회별 제출 상태 확인, 미제출 연구회는 관리자가 대리 입력 가능
   - **PDF 저장**(다운로드) / **인쇄(PDF)**: 표지·진행 순서·안건·연구회별 보고 표가 HWP 양식과 같은 순서로 생성되며,
     표지에 학회 로고와 제53대 이미지, 모든 페이지 바닥글에 작은 로고 + 페이지 번호가 들어갑니다.

## 웹(인터넷)에서 접속하게 하기

이 서비스는 서버 프로그램(FastAPI + SQLite + PDF용 Chromium)이라 GitHub Pages 같은 정적 호스팅에는 올릴 수 없고,
컨테이너를 실행해 주는 호스팅이 필요합니다. 저장소에 `Dockerfile`과 설정이 들어 있어 아래 중 하나를 고르면 됩니다.

| 방법 | 비용 | 절차 |
|---|---|---|
| **Render** (권장, 가장 간단) | Starter 약 $7/월(1GB 디스크 포함) | 1) https://render.com 가입 후 GitHub 연결 2) `https://render.com/deploy?repo=<이 저장소 URL>` 접속 3) `MEETING_DOCS_ADMIN_PASSWORD`(최초 관리자 비밀번호) 입력 → 몇 분 뒤 `https://meeting-docs-xxxx.onrender.com` 발급 |
| **Fly.io** | 소형 VM + 볼륨, 월 $2~5 수준 | `fly launch`(Dockerfile 자동 인식) → `fly volumes create data` → `fly secrets set MEETING_DOCS_SECRET=...` → `fly deploy` |
| **자체 서버/VPS** | 서버 비용 | `docker compose up -d` 후 Caddy/Nginx 로 도메인·HTTPS 연결. 또는 GHCR 이미지 `ghcr.io/<owner>/<repo>:latest` 바로 실행 |
| **내 PC 임시 공개** | 무료 | PC에서 `run.bat` 실행 후 `cloudflared tunnel --url http://localhost:8766` 으로 임시 주소 발급(PC를 켜 둔 동안만 접속 가능) |

공통 환경변수

- `MEETING_DOCS_SECRET`: 세션 서명 키(긴 임의 문자열). 비워 두면 `data/secret_key.txt`에 자동 생성
- `MEETING_DOCS_ADMIN_PASSWORD`: 최초 실행 시 admin 계정 비밀번호(기본 admin1234)
- `MEETING_DOCS_DATA`: DB·업로드 저장 폴더(컨테이너에서는 `/data`, 반드시 영구 디스크/볼륨에 연결)

Render 무료 플랜은 디스크를 지원하지 않아 재배포·재시작 때 입력 데이터가 사라지므로 실제 운영에는 Starter 이상을 쓰세요.
main 브랜치에 푸시하면 GitHub Actions 가 이미지를 빌드하고 서버 기동·PDF 생성까지 자동 점검합니다.

## 구조

```
app/main.py      라우팅(FastAPI)          app/db.py       SQLite 스키마·시드
app/auth.py      로그인/세션             app/docgen.py   문서 컨텍스트·마크다운·PDF(Playwright)
app/templates/   관리자·연구회 화면, doc.html(회의자료 본문)
app/static/      CSS·JS, img/logo_ksjcs.png(학회 로고), img/term53.svg(기본 53대 이미지)
```

## 참고

- 초기 연구회 명단은 제52-1차 회의자료(2025.11.14)의 30개 연구회이며, 집행부 위원은 제53대 워크숍 회의록 기준입니다.
  관리자 페이지에서 수정하세요.
- 제53대 전용 이미지 파일이 없어 기본 이미지(`term53.svg`)를 넣었습니다. 설정 페이지에서 실제 이미지로 교체하면 됩니다.
- PDF는 Chromium으로 렌더링하므로 PC에 설치된 한글 글꼴(함초롬바탕/맑은 고딕)을 사용합니다.
