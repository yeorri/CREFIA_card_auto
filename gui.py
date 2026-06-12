"""카드매입자료 자동 다운로드 — Tkinter GUI (모던 테마).

여신금융협회(cardsales.or.kr) 가맹점 매입내역 엑셀을 여러 거래처(계정) 순회하며 자동 저장.
로그인 입력은 OS 스캔코드(Python), 데이터 다운로드는 Chrome 확장이 담당.

사용 전: Chrome에 확장(extension 폴더) 설치 + Chrome 1개 열어둠 + 영문 입력.
실행:  python gui.py
"""
from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import orchestrate  # noqa: E402
import updater  # noqa: E402


def resource_path(name):
    """개발/배포(frozen exe) 모두에서 동봉 리소스 경로."""
    base = getattr(sys, "_MEIPASS", None)
    base = Path(base) if base else Path(__file__).resolve().parent
    return base / name

# ── 디자인 토큰 ──────────────────────────────────────────
FONT = "Malgun Gothic"
MONO = "Consolas"
BG = "#EEF1F6"
CARD = "#FFFFFF"
HEAD = "#0F172A"
INK = "#0F172A"
MUTE = "#64748B"
BORDER = "#E2E8F0"
ACCENT = "#6366F1"
ACCENT_DK = "#4F46E5"
GHOST = "#EEF1F6"
GHOST_BD = "#CBD5E1"
DANGER = "#EF4444"
CONSOLE_BG = "#0B1220"
CONSOLE_FG = "#D7E0EA"


def card(parent, title=None):
    wrap = tk.Frame(parent, bg=BG)
    wrap.pack(fill="x", padx=16, pady=(0, 12))
    if title:
        tk.Label(wrap, text=title, bg=BG, fg=MUTE,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(0, 5))
    inner = tk.Frame(wrap, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
    inner.pack(fill="x")
    pad = tk.Frame(inner, bg=CARD)
    pad.pack(fill="x", padx=14, pady=12)
    return pad


def button(parent, text, cmd, kind="accent", width=None):
    styles = {
        "accent": (ACCENT, "#FFFFFF", ACCENT_DK),
        "ghost": (GHOST, INK, "#E2E8F0"),
        "danger": (DANGER, "#FFFFFF", "#DC2626"),
    }
    bg, fg, active = styles[kind]
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                  activebackground=active, activeforeground=fg,
                  relief="flat", bd=0, cursor="hand2",
                  font=(FONT, 9, "bold"), padx=14, pady=7,
                  highlightthickness=(1 if kind == "ghost" else 0),
                  highlightbackground=GHOST_BD)
    if width:
        b.config(width=width)
    b.bind("<Enter>", lambda e: b.config(bg=active))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


def entry(parent, width=14, show=None):
    e = tk.Entry(parent, width=width, show=show, relief="flat", bg="#FFFFFF",
                 fg=INK, font=(FONT, 10), highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT,
                 insertbackground=INK)
    return e


def label(parent, text, muted=False, bold=False):
    return tk.Label(parent, text=text, bg=CARD, fg=(MUTE if muted else INK),
                    font=(FONT, 9, "bold" if bold else "normal"))


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("여신금융협회 카드자료 자동 다운로드")
        root.geometry("1020x860")
        root.minsize(960, 840)
        root.configure(bg=BG)
        try:
            ico = resource_path("icon.ico")
            if ico.exists():
                root.iconbitmap(str(ico))
        except Exception:
            pass
        self.accounts: list[list[str]] = []
        self.save_dir = str(orchestrate.DOWNLOADS)
        self.logq: "queue.Queue[str]" = queue.Queue()
        self.worker: threading.Thread | None = None
        self.stop_flag = False
        self._style()
        self._build()
        self._poll_log()
        # 시작 1.5초 후 업데이트 확인 (네트워크 실패는 조용히 무시)
        self.root.after(1500, lambda: updater.check_async(self._on_update))

    def _on_update(self, info):
        self.root.after(0, lambda: self._show_update(info))

    def _show_update(self, info):
        msg = (f"새 버전 v{info['latest']} 이(가) 있습니다.  (현재 v{info['current']})\n\n"
               f"{info.get('notes', '')}\n\n다운로드 페이지를 열까요?")
        if messagebox.askyesno("업데이트 확인", msg):
            url = info.get("download_url") or \
                "https://github.com/yeorri/CREFIA_card_auto/releases/latest"
            webbrowser.open(url)

    def _style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=INK,
                     rowheight=26, font=(FONT, 9), borderwidth=0)
        st.configure("Treeview.Heading", background="#F8FAFC", foreground=MUTE,
                     font=(FONT, 9, "bold"), relief="flat")
        st.map("Treeview", background=[("selected", "#E0E7FF")],
               foreground=[("selected", INK)])

    # ── UI ──────────────────────────────────────────────
    def _build(self):
        head = tk.Frame(self.root, bg=HEAD, height=64)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="여신금융협회 카드자료 자동 다운로드", bg=HEAD, fg="#FFFFFF",
                 font=(FONT, 14, "bold")).pack(anchor="w", padx=18, pady=(11, 0))
        tk.Label(head, text=f"여신금융협회 가맹점 매입내역 · 다중 거래처 일괄 저장   v{updater.CURRENT_VERSION}",
                 bg=HEAD, fg="#94A3B8", font=(FONT, 8)).pack(anchor="w", padx=18)

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, pady=(14, 0))
        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(body, bg=BG, width=360)
        right.pack(side="right", fill="both", padx=(0, 16), pady=(0, 14))
        right.pack_propagate(False)

        # 거래처 추가
        c1 = card(left, "거래처 추가")
        row = tk.Frame(c1, bg=CARD)
        row.pack(fill="x")
        label(row, "업체명").grid(row=0, column=0, padx=(0, 4))
        self.e_name = entry(row, 8); self.e_name.grid(row=0, column=1, padx=(0, 10), sticky="ew")
        label(row, "아이디").grid(row=0, column=2, padx=(0, 4))
        self.e_id = entry(row, 8); self.e_id.grid(row=0, column=3, padx=(0, 10), sticky="ew")
        label(row, "비밀번호").grid(row=0, column=4, padx=(0, 4))
        self.e_pw = entry(row, 8); self.e_pw.grid(row=0, column=5, padx=(0, 10), sticky="ew")
        button(row, "+ 추가", self.add_account).grid(row=0, column=6)
        row.columnconfigure(1, weight=1)
        row.columnconfigure(3, weight=1)
        row.columnconfigure(5, weight=1)
        self.e_pw.bind("<Return>", lambda e: self.add_account())
        label(c1, "업체명을 비우면 거래처A, 거래처B… 로 자동 지정", muted=True).pack(
            anchor="w", pady=(8, 0))
        actions = tk.Frame(c1, bg=CARD)
        actions.pack(fill="x", pady=(10, 0))
        button(actions, "엑셀/CSV 불러오기", self.import_excel, "ghost").pack(side="left")
        button(actions, "선택 삭제", self.del_selected, "ghost").pack(side="left", padx=6)
        button(actions, "전체 삭제", self.clear_all, "ghost").pack(side="left")

        # 목록
        c2 = card(left, "거래처 목록")
        cols = ("name", "id", "pw")
        self.tree = ttk.Treeview(c2, columns=cols, show="headings", height=7)
        for c, t, w in (("name", "업체명", 180), ("id", "아이디", 180), ("pw", "비밀번호", 180)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="x", side="left", expand=True)
        sb = ttk.Scrollbar(c2, command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        # 설정
        c3 = card(left, "조회 방식 · 저장 폴더")
        self.mode = tk.IntVar(value=0)   # 0=매입일자 기간조회, 1=월조회(거래일 기준)

        def radio(parent, text, val):
            return tk.Radiobutton(parent, text=text, variable=self.mode, value=val,
                                  command=self._update_mode, bg=CARD, fg=INK,
                                  activebackground=CARD, activeforeground=INK,
                                  selectcolor="#FFFFFF", highlightthickness=0,
                                  font=(FONT, 9, "bold"), cursor="hand2")

        mrow = tk.Frame(c3, bg=CARD); mrow.pack(fill="x")
        radio(mrow, "매입일자 기간조회", 0).pack(side="left", padx=(0, 16))
        radio(mrow, "월 조회 (거래일/승인일 기준 정리)", 1).pack(side="left")

        # 매입일자 기간조회 입력
        self.fr_period = tk.Frame(c3, bg=CARD)
        self.fr_period.pack(fill="x", pady=(8, 0))
        label(self.fr_period, "시작일").grid(row=0, column=0, padx=(0, 4))
        self.e_from = entry(self.fr_period, 12); self.e_from.grid(row=0, column=1, padx=(0, 12))
        label(self.fr_period, "종료일").grid(row=0, column=2, padx=(0, 4))
        self.e_to = entry(self.fr_period, 12); self.e_to.grid(row=0, column=3, padx=(0, 8))
        label(self.fr_period, "매입일자 기준 · YYYYMMDD (최대 31일)", muted=True).grid(
            row=0, column=4, sticky="w")
        self.var_sort = tk.BooleanVar(value=True)
        self.chk_sort = tk.Checkbutton(
            self.fr_period, text="카드사별 정렬 정리본(.xlsx) 함께 생성",
            variable=self.var_sort, bg=CARD, fg=INK, activebackground=CARD,
            activeforeground=INK, selectcolor="#FFFFFF", highlightthickness=0,
            font=(FONT, 9), anchor="w", cursor="hand2")
        self.chk_sort.grid(row=1, column=0, columnspan=5, sticky="w", pady=(6, 0))

        # 월조회 입력
        self.fr_month = tk.Frame(c3, bg=CARD)
        self.fr_month.pack(fill="x", pady=(8, 0))
        label(self.fr_month, "연도").grid(row=0, column=0, padx=(0, 4))
        self.e_year = entry(self.fr_month, 6); self.e_year.grid(row=0, column=1, padx=(0, 12))
        label(self.fr_month, "월").grid(row=0, column=2, padx=(0, 4))
        self.e_month = entry(self.fr_month, 4); self.e_month.grid(row=0, column=3, padx=(0, 12))
        label(self.fr_month, "다음달").grid(row=0, column=4, padx=(0, 4))
        self.e_nextdays = entry(self.fr_month, 4); self.e_nextdays.insert(0, "5")
        self.e_nextdays.grid(row=0, column=5, padx=(0, 2))
        label(self.fr_month, "일까지 (거래일 기준 정리 · 카드사별 정렬)", muted=True).grid(
            row=0, column=6, sticky="w")

        r2 = tk.Frame(c3, bg=CARD); r2.pack(fill="x", pady=(10, 0))
        label(r2, "저장 폴더").pack(side="left", padx=(0, 8))
        self.lbl_dir = tk.Label(r2, text=self.save_dir, bg="#F8FAFC", fg=INK,
                                font=(FONT, 8), anchor="w", relief="flat",
                                highlightthickness=1, highlightbackground=BORDER,
                                padx=8, pady=4)
        self.lbl_dir.pack(side="left", fill="x", expand=True, padx=(0, 8))
        button(r2, "변경", self.pick_dir, "ghost").pack(side="left")
        r4 = tk.Frame(c3, bg=CARD); r4.pack(fill="x", pady=(8, 0))
        self.var_folder = tk.BooleanVar(value=False)
        self.var_consol = tk.BooleanVar(value=True)
        tk.Checkbutton(r4, text="업체명별 하위폴더",
                       variable=self.var_folder, bg=CARD, fg=INK, activebackground=CARD,
                       activeforeground=INK, selectcolor="#FFFFFF", highlightthickness=0,
                       font=(FONT, 9), anchor="w", cursor="hand2").pack(side="left", padx=(0, 16))
        tk.Checkbutton(r4, text="실행 결과 리포트 생성  ([결과]실행리포트_기간.xlsx)",
                       variable=self.var_consol, bg=CARD, fg=INK, activebackground=CARD,
                       activeforeground=INK, selectcolor="#FFFFFF", highlightthickness=0,
                       font=(FONT, 9), anchor="w", cursor="hand2").pack(side="left")
        self._update_mode()

        # 실행
        runrow = tk.Frame(left, bg=BG)
        runrow.pack(fill="x", padx=16, pady=(2, 14))
        self.btn_run = button(runrow, "자동 다운로드 시작", self.start)
        self.btn_run.config(font=(FONT, 10, "bold"), pady=10)
        self.btn_run.pack(side="left", fill="x", expand=True)
        self.btn_stop = button(runrow, "중단", self.stop, "danger")
        self.btn_stop.config(pady=10, state="disabled")
        self.btn_stop.pack(side="left", padx=(8, 0))

        # 로그 (오른쪽 큰 단)
        tk.Label(right, text="진행 상황", bg=BG, fg=MUTE,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(0, 5))
        logbox = tk.Frame(right, bg=CONSOLE_BG, highlightbackground=BORDER, highlightthickness=1)
        logbox.pack(fill="both", expand=True)
        self.log = tk.Text(logbox, bg=CONSOLE_BG, fg=CONSOLE_FG,
                           font=(MONO, 9), relief="flat", bd=0, padx=10, pady=8,
                           insertbackground=CONSOLE_FG, wrap="word")
        self.log.pack(fill="both", expand=True, side="left")
        lsb = ttk.Scrollbar(logbox, command=self.log.yview)
        lsb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=lsb.set)
        self.log.tag_config("ok", foreground="#4ADE80")
        self.log.tag_config("err", foreground="#F87171", font=(MONO, 9, "bold"))
        self.log.tag_config("retry", foreground="#FBBF24")
        self.log.tag_config("head", foreground="#A5B4FC", font=(MONO, 9, "bold"))
        self.log.tag_config("done", foreground="#34D399", font=(MONO, 10, "bold"))
        self.log.tag_config("muted", foreground="#8A99AE")

    # ── 목록 조작 ───────────────────────────────────────
    def _default_name(self):
        i = len(self.accounts)
        return "거래처" + (chr(ord("A") + i) if i < 26 else str(i + 1))

    def add_account(self):
        name = self.e_name.get().strip() or self._default_name()
        uid, pw = self.e_id.get().strip(), self.e_pw.get().strip()
        if not uid or not pw:
            messagebox.showwarning("입력", "아이디와 비밀번호를 입력하세요."); return
        self.accounts.append([name, uid, pw])
        self.tree.insert("", "end", values=(name, uid, pw))
        for e in (self.e_name, self.e_id, self.e_pw):
            e.delete(0, "end")
        self.e_name.focus()

    def import_excel(self):
        path = filedialog.askopenfilename(
            title="계정 엑셀 선택",
            filetypes=[("엑셀/CSV", "*.xlsx *.xlsm *.csv"), ("모든 파일", "*.*")])
        if not path:
            return
        try:
            rows = self._read_rows(path)
        except Exception as e:
            messagebox.showerror("불러오기 오류", str(e)); return
        added = 0
        for r in rows:
            name = (r[0] or "").strip() if len(r) > 0 else ""
            uid = (r[1] or "").strip() if len(r) > 1 else ""
            pw = (r[2] or "").strip() if len(r) > 2 else ""
            if not uid or not pw or uid in ("아이디", "id", "ID"):
                continue
            name = name or self._default_name()
            self.accounts.append([name, uid, pw])
            self.tree.insert("", "end", values=(name, uid, pw))
            added += 1
        self._log(f"엑셀에서 {added}건 추가")

    @staticmethod
    def _read_rows(path):
        if path.lower().endswith(".csv"):
            import csv
            with open(path, encoding="utf-8-sig") as fh:
                return list(csv.reader(fh))
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        return [[("" if v is None else str(v)) for v in row]
                for row in ws.iter_rows(values_only=True)]

    def del_selected(self):
        for item in self.tree.selection():
            idx = self.tree.index(item)
            self.tree.delete(item)
            if 0 <= idx < len(self.accounts):
                del self.accounts[idx]

    def clear_all(self):
        self.tree.delete(*self.tree.get_children())
        self.accounts.clear()

    def pick_dir(self):
        d = filedialog.askdirectory(title="저장 폴더 선택", initialdir=self.save_dir)
        if d:
            self.save_dir = d
            self.lbl_dir.config(text=d)

    # ── 실행 ────────────────────────────────────────────
    def _log(self, msg):
        self.logq.put(msg)

    @staticmethod
    def _tag_for(m):
        if "━━" in m:
            return "done"
        if "✓" in m:
            return "ok"
        if "✗" in m or "■" in m or "오류" in m:
            return "err"
        if "↻" in m:
            return "retry"
        if m.startswith("[월") or m.startswith("[매입") or m.startswith("저장 폴더") or "후 시작" in m:
            return "head"
        return "muted"

    def _poll_log(self):
        try:
            while True:
                msg = self.logq.get_nowait()
                self.log.insert("end", msg + "\n", self._tag_for(msg))
                self.log.see("end")
        except queue.Empty:
            pass
        self.root.after(150, self._poll_log)

    def _update_mode(self):
        period = self.mode.get() == 0
        for w in (self.e_from, self.e_to, self.chk_sort):
            w.config(state="normal" if period else "disabled")
        for w in (self.e_year, self.e_month, self.e_nextdays):
            w.config(state="normal" if not period else "disabled")

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        if not self.accounts:
            messagebox.showwarning("목록", "거래처를 1건 이상 추가하세요."); return
        accounts = [tuple(a) for a in self.accounts]

        if self.mode.get() == 0:
            # 매입일자 기간조회
            df = "".join(c for c in self.e_from.get() if c.isdigit())
            dt = "".join(c for c in self.e_to.get() if c.isdigit())
            if len(df) != 8 or len(dt) != 8:
                messagebox.showwarning("기간", "시작일/종료일을 YYYYMMDD로 입력하세요."); return
            try:
                d1, d2 = datetime.strptime(df, "%Y%m%d"), datetime.strptime(dt, "%Y%m%d")
            except ValueError:
                messagebox.showwarning("기간", "올바른 날짜가 아닙니다 (YYYYMMDD)."); return
            if d2 < d1:
                messagebox.showwarning("기간", "종료일이 시작일보다 빠릅니다."); return
            if (d2 - d1).days + 1 > 31:
                messagebox.showwarning("기간", f"조회 가능 기간은 최대 31일입니다.\n현재 {(d2 - d1).days + 1}일."); return
            sort_by_card = self.var_sort.get()
            per_folder = self.var_folder.get()
            consol = self.var_consol.get()
            desc = f"매입일자 {df}~{dt}"

            def job():
                orchestrate.run_batch(accounts, df, dt, save_dir=self.save_dir,
                                      log=self._log, should_stop=lambda: self.stop_flag,
                                      start_delay=5, sort_by_card=sort_by_card,
                                      per_company_folder=per_folder, consolidate=consol)
        else:
            # 월 조회 (거래일 기준)
            ys = "".join(c for c in self.e_year.get() if c.isdigit())
            ms = "".join(c for c in self.e_month.get() if c.isdigit())
            nds = "".join(c for c in self.e_nextdays.get() if c.isdigit()) or "5"
            if len(ys) != 4 or not ms or not (1 <= int(ms) <= 12):
                messagebox.showwarning("월조회", "연도(YYYY)와 월(1~12)을 입력하세요."); return
            if not (1 <= int(nds) <= 28):
                messagebox.showwarning("월조회", "'다음달 N일'은 1~28 사이로 입력하세요."); return
            year, month, nextdays = int(ys), int(ms), int(nds)
            per_folder = self.var_folder.get()
            consol = self.var_consol.get()
            desc = f"{year}년 {month}월 (거래일 기준, 다음달 {nextdays}일까지)"

            def job():
                orchestrate.run_batch_monthly(accounts, year, month, next_days=nextdays,
                                              save_dir=self.save_dir, log=self._log,
                                              should_stop=lambda: self.stop_flag, start_delay=5,
                                              per_company_folder=per_folder, consolidate=consol)

        if not messagebox.askokcancel(
                "확인",
                f"{len(accounts)}건 · {desc}\n\n"
                "· 시작 후 5초 안에 사용할 브라우저(크롬/웨일) 창을 클릭해 앞에 두세요.\n"
                "· 그 다음부터는 마우스/키보드를 건드리지 마세요.\n"
                "· 브라우저(확장 설치) 1개 열어둠 + 영문 입력 상태 확인."):
            return
        self.stop_flag = False
        self.btn_run.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.worker = threading.Thread(target=self._run, args=(job,), daemon=True)
        self.worker.start()

    def _run(self, job):
        try:
            job()
        except Exception as e:
            self._log(f"오류: {e}")
        finally:
            self.root.after(0, self._done)

    def _done(self):
        self.btn_run.config(state="normal")
        self.btn_stop.config(state="disabled")

    def stop(self):
        self.stop_flag = True
        self._log("중단 요청...")


def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
