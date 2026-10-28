"""SQLite 저장소: 스키마, 연결, 초기 데이터(시드).

모든 표는 단순 구조로 유지한다. 유연한 데이터(안건 이미지, 연구회 보고 내용)는 JSON 컬럼에 둔다.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("MEETING_DOCS_DATA", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    pw_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'admin',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS committee_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    name TEXT NOT NULL,
    affiliation TEXT NOT NULL DEFAULT '',
    sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    chair_name TEXT NOT NULL DEFAULT '',
    chair_affiliation TEXT NOT NULL DEFAULT '',
    secretaries TEXT NOT NULL DEFAULT '',
    is_new INTEGER NOT NULL DEFAULT 0,
    is_preliminary INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    access_code TEXT NOT NULL,
    sort INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    title TEXT NOT NULL DEFAULT '연구회 운영위원회',
    date_text TEXT NOT NULL DEFAULT '',
    place TEXT NOT NULL DEFAULT '',
    method TEXT NOT NULL DEFAULT '',
    host_name TEXT NOT NULL DEFAULT '',
    host_title TEXT NOT NULL DEFAULT '',
    past_label TEXT NOT NULL DEFAULT '',
    plan_label TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agenda_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    sort INTEGER NOT NULL DEFAULT 0,
    kind TEXT NOT NULL DEFAULT 'text',
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    images TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    data TEXT NOT NULL DEFAULT '{}',
    submitted INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT '',
    UNIQUE(meeting_id, group_id)
);
"""


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------- settings
def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def all_settings(conn: sqlite3.Connection) -> dict:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}


def new_access_code() -> str:
    # 연구회 접속코드: 혼동되기 쉬운 문자(0/O, 1/I/l) 제외 6자리
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))


# ---------------------------------------------------------------- seed data
DEFAULT_SETTINGS = {
    "society_name": "한국언론학회",
    "society_name_en": "Korean Society for Journalism & Communication Studies",
    "term": "53",
    "president_name": "홍경수",
    "president_affiliation": "아주대학교",
    "logo_file": "",        # 비어 있으면 static/img/logo_ksjcs.png 사용
    "term_image_file": "",  # 비어 있으면 static/img/term53.svg 사용
    "cover_note": "",
}

# 제53대 집행부(2026.10 집행부 워크숍 회의록 기준). 차기회장 등은 관리자 페이지에서 추가.
SEED_COMMITTEE = [
    ("부 회 장", "유경한", "전북대학교"),
    ("총무이사", "이승현", "동서울대학교"),
    ("연구이사", "서수민", "서강대학교"),
]

# 제52-1차 회의자료(2025.11.14) 연구회 명단을 초기값으로 사용. 가나다 순.
SEED_GROUPS = [
    ("건강 커뮤니케이션", "김활빈", "강원대학교", "박혜영(한신대학교)"),
    ("과학보건환경위험 커뮤니케이션", "백혜진", "한양대학교", "임인재(성균관대학교)"),
    ("광고", "안주아", "동신대학교", "김유미(호남대학교)"),
    ("국제 커뮤니케이션", "백강희", "한남대학교", "전창영(한국언론진흥재단)"),
    ("문화/젠더", "김수아", "서울대학교", "이규탁(조지메이슨대학교)\n이신혜(부산대학교)"),
    ("미디어 경제/경영", "지성욱", "한국외국어대학교", "이상엽(연세대학교)"),
    ("미디어 교육", "이숙정", "중앙대학교", "류숙(서강대학교)\n황현정(우아한형제들)"),
    ("미디어데이터사이언스", "정용찬", "홍익대학교", "고흥석(국립군산대학교)\n성윤택(KOBACO)"),
    ("미디어블록체인&스타트업", "이성민", "한국방송통신대학교", "박찬경(경북대학교)\n이창준(성균관대학교)\n진소연(서강대학교)"),
    ("미디어콘텐츠", "남윤재", "경희대학교", "김세환(동서대학교)\n정창원(단국대학교)"),
    ("방송과 뉴미디어", "홍경수", "아주대학교", "김대규(서울대학교)\n이승현(동서울대학교)\n오창학(광운대학교)\n황현정(KISDI)"),
    ("언론과 사회", "이준웅", "서울대학교", "이훈(경희대학교)"),
    ("언론법제윤리", "이영희", "한양대학교", "박현아(한국게임정책자율기구)"),
    ("영상매체", "노광우", "한림대학교", "정영희(고려대학교 정보문화연구소)"),
    ("인터랙션", "정세훈", "고려대학교", "박세진(한양대학교)"),
    ("저널리즘", "임종섭", "서강대학교", "이정훈(대진대학교)\n한지영(KAIST)"),
    ("정치 커뮤니케이션", "최지향", "이화여자대학교", "김범수(동국대학교)\n김민철(중앙대학교)\n이상원(고려대학교)\n전창영(한국언론진흥재단)"),
    ("조직 커뮤니케이션", "권장원", "대구가톨릭대학교", "임소영(고려대학교)\n김자림(연세대학교)\n이정현(계명대학교)"),
    ("종교와 커뮤니케이션", "유지윤", "아신대학교", "서도원(연세대학교)"),
    ("지역언론", "이진로", "영산대학교", "김미경(청운대학교)"),
    ("출판과 커뮤니케이션", "이완수", "동서대학교", "김희주(인천대학교)"),
    ("커뮤니케이션과 역사", "이종숙", "고려대학교", "윤상길(신한대학교)\n이성민(한국방송통신대학교)"),
    ("커뮤니케이션 정책", "조영신", "SK브로드밴드", ""),
    ("커뮤니케이션 철학과 사상", "박선희", "조선대학교", "이동후(인천대학교)\n김상민(연세대학교)\n임연경(이화여자대학교)"),
    ("컴퓨테이셔널방법론", "정낙원", "서울여자대학교", "이신행(중앙대학교)"),
    ("평화 커뮤니케이션", "이종희", "인천광역시 선거방송토론위원회", "조수진(장로회신학대학교)\n임종석(상지대학교)\n윤복실(서강대학교)\n김연숙(숭실대학교)"),
    ("플랫폼", "윤호영", "이화여자대학교", "허윤철(인터넷신문협회)\n김지희(서울대학교)"),
    ("홍보", "최일도", "한국언론진흥재단", ""),
    ("휴먼 커뮤니케이션", "이진로", "영산대학교", "이윤복(충남대학교)"),
    ("스포츠/게임", "김형민", "충남대학교", "이재길(한림대학교)"),
]
PRELIMINARY_GROUPS = {"스포츠/게임"}

DISCUSSION_TEMPLATE = """1. 연구회 재정 지원 방안

○ 정기학술대회 연구회 세션 구성 지원
- (내용을 입력하세요)

○ 우수연구회 시상
- (내용을 입력하세요)

2. 연구회별 정회원 현황 조사

| 연번 | 연구회명 | 정회원 수 | 활동회원 | 납부대기 회원 |
|---|---|---|---|---|
| 1 | (연구회명) | 0 | 0 | 0 |

3. 2027 봄철 정기학술대회

- 일시: 2027년 5월 14일(목)~15일(금)
- 장소: 목포대학교
"""

SEED_AGENDA = [
    ("opening", "개회 및 성원 보고", ""),
    ("greeting", "회장 인사", ""),
    ("committee", "연구회 운영위원회 위원 소개", ""),
    ("reports", "연구회별 활동 및 향후 계획 보고", ""),
    ("text", "논의 및 보고 사항", DISCUSSION_TEMPLATE),
    ("closing", "폐회", ""),
]


def init_db(pw_hasher) -> None:
    """스키마 생성 + 최초 1회 시드. pw_hasher(평문)->해시 문자열."""
    with db() as conn:
        conn.executescript(SCHEMA)
        for k, v in DEFAULT_SETTINGS.items():
            if conn.execute("SELECT 1 FROM settings WHERE key=?", (k,)).fetchone() is None:
                set_setting(conn, k, v)

        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO users(username, pw_hash, role, created_at) VALUES(?,?,?,?)",
                ("admin", pw_hasher(os.environ.get("MEETING_DOCS_ADMIN_PASSWORD") or "admin1234"), "admin", now_iso()),
            )

        if conn.execute("SELECT COUNT(*) FROM committee_members").fetchone()[0] == 0:
            for i, (role, name, aff) in enumerate(SEED_COMMITTEE):
                conn.execute(
                    "INSERT INTO committee_members(role, name, affiliation, sort) VALUES(?,?,?,?)",
                    (role, name, aff, i),
                )

        if conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0] == 0:
            for i, (name, chair, aff, secs) in enumerate(SEED_GROUPS):
                conn.execute(
                    "INSERT INTO groups(name, chair_name, chair_affiliation, secretaries, is_new, is_preliminary, "
                    "active, access_code, sort) VALUES(?,?,?,?,?,?,?,?,?)",
                    (name, chair, aff, secs, 0, 1 if name in PRELIMINARY_GROUPS else 0, 1, new_access_code(), i),
                )

        if conn.execute("SELECT COUNT(*) FROM meetings").fetchone()[0] == 0:
            cur = conn.execute(
                "INSERT INTO meetings(term, seq, title, date_text, place, method, host_name, host_title, "
                "past_label, plan_label, status, created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    53, 1, "연구회 운영위원회",
                    "2026년 11월 20일(금) 11:00",
                    "한국인터넷신문협회 회의실",
                    "오프라인 회의와 zoom을 통한 온라인 회의 병행",
                    "유경한", "제53대 한국언론학회 부회장, 전북대학교",
                    "2026년도 하반기", "2027년도 상반기",
                    "open", now_iso(),
                ),
            )
            mid = cur.lastrowid
            for i, (kind, title, body) in enumerate(SEED_AGENDA):
                conn.execute(
                    "INSERT INTO agenda_items(meeting_id, sort, kind, title, body, images) VALUES(?,?,?,?,?,?)",
                    (mid, i, kind, title, body, "[]"),
                )


# ---------------------------------------------------------------- helpers
def rows(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def row(conn: sqlite3.Connection, sql: str, params=()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def loads(s: str, default):
    try:
        return json.loads(s) if s else default
    except json.JSONDecodeError:
        return default


def empty_report(group: dict) -> dict:
    return {
        "chair": f"{group['chair_name']}({group['chair_affiliation']})" if group["chair_name"] else "",
        "secretaries": group["secretaries"],
        "no_report": False,
        "past": {"intro": "", "items": [], "images": []},
        "plan": {"intro": "", "items": [], "images": []},
    }
