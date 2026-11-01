r"""review_page.py — /wf-review-page의 굽는 부품. 실제 파일에서 artifact HTML을 만들고 사용자의 표시를 artifact db로 받는다.

언제: 사용자에게 판단 · 승인 · 행동을 요청하기 전, 긴 일의 상태판. 주제의 생성 script가 import해서 쓴다.
kind: tool
status: active

쓰는 법(주제의 exec\build_<무엇>.py 안에서):
  import sys; sys.path.insert(0, r"~/.claude\workflow\tools")
  import review_page as R
  body = [R.card("요지", R.ul(["…", "…"])), R.card("설계 문서", R.render_md(R.read(r"C:\...\12_x.md"))),
          R.card("바뀌는 파일", R.filebox(r"C:\...\SKILL.md", "새 판"))]
  R.write(r"C:\...\artifacts\x.html", "페이지 이름", body, marks=[("ALL", "이 설계 전체", "맞으면 맞음")], collection="x_marks")
그다음 Artifact 도구로 publish(capabilities {"db": {}}), 같은 파일 경로로 다시 구워 같은 URL에 갱신.
금지어(회사 절 [1])는 굽는 단계에서 가린다. 원천: ~\.claude\private\redact.
"""
import datetime
import html
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    import redact_check as _rc  # noqa: E402
    _TERMS = _rc.compile_terms(_rc.load_terms(sections=("1",)))
except Exception:            # 금지어 원천이 없어도 굽기는 한다(가리지 못했다고 페이지에 적음)
    _rc, _TERMS = None, None

NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

STYLE = """
:root{--bg:#eef1f4;--panel:#fff;--ink:#18212e;--muted:#5b6676;--line:#c9d0da;--chip:#f4f6f9;--core:#2f4fb3;--ok:#13806f;--warn:#b5720f;--bad:#c2410c;--new:#6b3fb0;
--f:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif;--m:"IBM Plex Mono",ui-monospace,Consolas,monospace}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#11161d;--panel:#19202a;--ink:#e6ebf2;--muted:#9aa5b5;--line:#2d3644;--chip:#202833;--core:#7e9cf5;--ok:#3cc3ab;--warn:#e6a63d;--bad:#f0805a;--new:#ad86ef;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#11161d;--panel:#19202a;--ink:#e6ebf2;--muted:#9aa5b5;--line:#2d3644;--chip:#202833;--core:#7e9cf5;--ok:#3cc3ab;--warn:#e6a63d;--bad:#f0805a;--new:#ad86ef;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font-family:var(--f);font-size:15px;line-height:1.6}
.w{max-width:900px;margin:0 auto;padding-block:20px 48px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));display:grid;gap:14px}
h1{font-size:1.45rem;margin:0;text-wrap:balance}h2{font-size:1.15rem;margin:0 0 6px}h3{font-size:1rem;margin:10px 0 4px}
.lead{color:var(--muted);margin:0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;min-width:0}
.k{font-family:var(--m);font-size:.74rem;letter-spacing:.06em;color:var(--muted);text-transform:uppercase}
table{border-collapse:collapse;width:100%;font-size:.88rem}td,th{border-top:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}th{color:var(--muted);font-weight:500}
.tw{overflow-x:auto}
code,.path{font-family:var(--m);font-size:.82rem;word-break:break-all}
.pill{display:inline-block;font-family:var(--m);font-size:.72rem;padding:1px 8px;border-radius:999px;border:1px solid currentColor;white-space:nowrap}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.new{color:var(--new)}.muted{color:var(--muted)}
details{border-top:1px solid var(--line);padding:6px 0}summary{cursor:pointer;font-weight:600}
pre{background:var(--chip);border-radius:8px;padding:10px;overflow-x:auto;font-family:var(--m);font-size:.78rem;line-height:1.5;white-space:pre-wrap;word-break:break-word;max-height:520px;overflow-y:auto}
.q{border-top:1px solid var(--line);padding:10px 0;display:grid;gap:6px}
.q .t{font-weight:600}.q .h{color:var(--muted);font-size:.9rem}
.marks{display:flex;gap:6px;flex-wrap:wrap}.marks button{font:inherit;font-size:.85rem;padding:5px 12px;border-radius:8px;border:1px solid var(--line);background:var(--chip);color:var(--ink);cursor:pointer}
.marks button[aria-pressed="true"]{border-color:var(--core);box-shadow:inset 0 0 0 1px var(--core);font-weight:600}
textarea{font:inherit;width:100%;min-height:56px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);padding:6px 8px;box-sizing:border-box}
.saved{font-size:.78rem;color:var(--muted)}
button:focus-visible,summary:focus-visible,textarea:focus-visible{outline:2px solid var(--core);outline-offset:2px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
"""

MARKS_JS = """<script>
const KEY="@@KEY@@";let db=null;const state={};const pending={};
function paint(id){const q=document.querySelector('.q[data-id="'+id+'"]');if(!q)return;const s=state[id]||{};
q.querySelectorAll('.marks button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.m===s.mark)));
const ta=q.querySelector('textarea');if(document.activeElement!==ta)ta.value=s.note||"";}
async function save(id){const q=document.querySelector('.q[data-id="'+id+'"]');const sv=q.querySelector('.saved');
if(!db){sv.textContent="저장할 수 없음: 채팅에 적어 주십시오";return}
const s=state[id]||{};sv.textContent="저장 중…";
try{if(pending[id])await pending[id];pending[id]=db.collection(KEY).doc(id).set({mark:s.mark||"",note:s.note||"",at:new Date().toISOString()});await pending[id];sv.textContent="저장됨"}catch(e){sv.textContent="저장 실패: "+(e&&e.message||e)}}
document.querySelectorAll('.q').forEach(q=>{const id=q.dataset.id;
q.querySelectorAll('.marks button').forEach(b=>b.onclick=()=>{state[id]=state[id]||{};state[id].mark=state[id].mark===b.dataset.m?"":b.dataset.m;paint(id);save(id)});
let t=null;q.querySelector('textarea').addEventListener('input',ev=>{state[id]=state[id]||{};state[id].note=ev.target.value;clearTimeout(t);t=setTimeout(()=>save(id),700)})});
(async()=>{try{db=await claude.use("db")}catch(e){db=null}
const st=document.getElementById('dbState');if(!db){if(st)st.textContent="이 화면에서는 저장소가 열리지 않습니다. 채팅에 적어 주십시오.";return}
if(st)st.textContent="표시와 메모는 바로 저장됩니다. 다 하셨으면 채팅에 \\"답함\\"이라고만 적어 주십시오.";
db.collection(KEY).onSnapshot(snap=>{snap.docs.forEach(d=>{const v=d.data()||{};state[d.id]={mark:v.mark||"",note:typeof v.note==="string"?v.note:""};paint(d.id)})})})();
</script>"""


def mask(s):
    return _rc.mask_text(s, _TERMS) if (s and _rc and _TERMS) else s


def e(s):
    return html.escape(mask(str(s)))


def read(p, limit=None):
    p = pathlib.Path(p)
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    if limit and t.count("\n") > limit:
        t = "\n".join(t.split("\n")[:limit]) + "\n… (앞 %d줄만 보임, 전체는 파일에서)" % limit
    return t


def filebox(path, title=None, limit=400, note=""):
    """파일 전문을 접힌 상자로. 요약으로 대신하지 않는다."""
    p = pathlib.Path(path)
    t = read(p, limit)
    n = 0 if t is None else t.count("\n") + 1
    head = '%s <span class="muted">· %d줄</span>' % (e(title or p.name), n)
    if t is None:
        return '<details><summary>%s <span class="pill bad">없음</span></summary><p class="path">%s</p></details>' % (head, e(p))
    return ('<details><summary>%s</summary><p class="path">%s</p>' % (head, e(p))
            + ('<p class="muted">%s</p>' % e(note) if note else "") + "<pre>%s</pre></details>" % e(t))


def table(headers, rows):
    return ('<div class="tw"><table><tr>' + "".join("<th>%s</th>" % e(h) for h in headers) + "</tr>"
            + "".join("<tr>" + "".join("<td>%s</td>" % e(c) for c in r) + "</tr>" for r in rows) + "</table></div>")


def ul(items):
    return "<ul>" + "".join("<li>%s</li>" % e(x) for x in items) + "</ul>"


def card(title, inner, kicker=""):
    return '<div class="card">%s<h2>%s</h2>%s</div>' % (('<div class="k">%s</div>' % e(kicker)) if kicker else "", e(title), inner)


def _inline(s):
    s = e(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return re.sub(r"~~([^~]+)~~", r"<del>\1</del>", s)


def render_md(text):
    """설계 · 결론 문서를 페이지 안에 그대로(제목 · 목록 · 표 · 인용 · 굵게 · 코드)."""
    if text is None:
        return '<p class="bad">파일 없음</p>'
    out, i, L, lst = [], 0, text.replace("\r\n", "\n").split("\n"), None
    while i < len(L):
        ln = L[i]
        if ln.startswith("|") and i + 1 < len(L) and re.match(r"^\|[-| :]+\|$", L[i + 1].strip()):
            hdr = [c.strip() for c in ln.strip().strip("|").split("|")]
            rows, i = [], i + 2
            while i < len(L) and L[i].startswith("|"):
                rows.append([c.strip() for c in L[i].strip().strip("|").split("|")])
                i += 1
            out.append('<div class="tw"><table><tr>' + "".join("<th>%s</th>" % _inline(h) for h in hdr) + "</tr>"
                       + "".join("<tr>" + "".join("<td>%s</td>" % _inline(c) for c in r) + "</tr>" for r in rows) + "</table></div>")
            continue
        if lst and not re.match(r"^\s*(-|\d+\.) ", ln):
            out.append("</%s>" % lst)
            lst = None
        m = re.match(r"^(#{1,4}) (.*)", ln)
        if m:
            lv = min(len(m.group(1)) + 1, 4)
            out.append("<h%d>%s</h%d>" % (lv, _inline(m.group(2)), lv))
        elif re.match(r"^\s*- ", ln):
            if lst != "ul":
                out.append("<ul>")
                lst = "ul"
            out.append("<li>%s</li>" % _inline(ln.strip()[2:]))
        elif re.match(r"^\s*\d+\. ", ln):
            if lst != "ol":
                out.append("<ol>")
                lst = "ol"
            out.append("<li>%s</li>" % _inline(re.sub(r"^\s*\d+\. ", "", ln)))
        elif ln.startswith("> "):
            out.append('<p class="muted">%s</p>' % _inline(ln[2:]))
        elif ln.strip() and not ln.startswith("```"):
            out.append("<p>%s</p>" % _inline(ln))
        i += 1
    if lst:
        out.append("</%s>" % lst)
    return "".join(out)


def mark_box(qid, title, hint, choices=(("ok", "맞음"), ("fix", "고침"))):
    """사용자 표시 칸. 페이지에 둘 이하(뼈대 G) — 외부 공개본의 문단별 표시만 예외."""
    btn = "".join('<button type="button" data-m="%s" aria-pressed="false">%s</button>' % (k, e(v)) for k, v in choices)
    return ('<div class="q" data-id="%s"><div class="t">%s</div><div class="h">%s</div><div class="marks">%s</div>'
            '<textarea id="n_%s" placeholder="메모"></textarea><div class="saved"></div></div>') % (e(qid), e(title), e(hint), btn, e(qid))


def write(out_path, title, body, marks=(), collection=None, kicker=""):
    """페이지를 쓴다. title은 두 ~ 네 단어의 이름. marks=[(id, 제목, 힌트)] — 있으면 collection이 필요하다."""
    assert not marks or collection, "표시 칸이 있으면 db 모음 이름이 필요하다"
    warn = "" if _TERMS else '<p class="bad">금지어 원천을 읽지 못해 가리지 못했다 — 공유 전에 확인</p>'
    H = ['<title>%s</title>\n<meta name="claude:viewport-fit-sides" content="cover">\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">\n'
         '<style>%s</style>\n<div class="w">' % (html.escape(title), STYLE)]
    H.append('<div class="card"><div class="k">%s</div><h1>%s</h1>%s<p class="lead" id="dbState"></p></div>'
             % (e(kicker or NOW), e(title), warn))
    H.extend(body)
    if marks:
        H.append('<div class="card"><h2>표시</h2>' + "".join(mark_box(*m) for m in marks) + "</div>")
    H.append("</div>")
    if marks:
        H.append(MARKS_JS.replace("@@KEY@@", collection))
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(out_path).write_text("".join(H), encoding="utf-8")
    return out_path
