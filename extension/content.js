/* 카드매입자료 자동 다운로드 — content script (정리본)
 *
 * 평소엔 사용자가 건드릴 게 없다. Python GUI가 매입내역 URL에
 *   ?csauto=1&csfrom=YYYYMMDD&csto=YYYYMMDD
 * 를 붙여 이동시키면, 이 스크립트가 페이지 안에서 자동으로
 * 조회 → 전체체크 → 상세조회 → 엑셀 다운로드를 수행한다.
 *
 * 화면엔 진행 상태만 보여주는 작은 패널을 띄운다(버튼 없음).
 */
(function () {
  "use strict";
  if (window.__cardsalesPanelLoaded) return;
  window.__cardsalesPanelLoaded = true;

  // ── 작은 상태 패널 ──────────────────────────────────────
  const panel = document.createElement("div");
  panel.id = "cardsales-auto-panel";
  panel.innerHTML = `
    <div class="cs-head">카드매입 자동 다운로드 <span class="cs-x">×</span></div>
    <div class="cs-body"><textarea id="cs-out" readonly></textarea></div>`;
  const style = document.createElement("style");
  style.textContent = `
    #cardsales-auto-panel{position:fixed;top:12px;right:12px;width:280px;z-index:2147483647;
      background:#fff;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.18);
      font-family:'Malgun Gothic',sans-serif;font-size:12px;color:#0f172a;overflow:hidden;opacity:.96}
    #cardsales-auto-panel .cs-head{background:#0f172a;color:#fff;padding:7px 12px;font-weight:bold;
      cursor:move;display:flex;justify-content:space-between;align-items:center}
    #cardsales-auto-panel .cs-x{cursor:pointer;font-size:16px;line-height:1}
    #cardsales-auto-panel .cs-body{padding:8px}
    #cardsales-auto-panel textarea{width:100%;height:120px;box-sizing:border-box;resize:vertical;
      border:1px solid #e2e8f0;border-radius:6px;padding:6px;font-family:Consolas,monospace;font-size:11px;
      white-space:pre-wrap;overflow:auto}`;
  document.documentElement.appendChild(style);
  document.documentElement.appendChild(panel);

  const out = panel.querySelector("#cs-out");
  const log = (m) => { out.value += (out.value ? "\n" : "") + m; out.scrollTop = out.scrollHeight; };
  panel.querySelector(".cs-x").onclick = () => panel.remove();

  // 헤더 드래그
  (function () {
    const head = panel.querySelector(".cs-head");
    let sx, sy, ox, oy, drag = false;
    head.addEventListener("mousedown", (e) => {
      if (e.target.classList.contains("cs-x")) return;
      drag = true; sx = e.clientX; sy = e.clientY;
      const r = panel.getBoundingClientRect(); ox = r.left; oy = r.top; e.preventDefault();
    });
    document.addEventListener("mousemove", (e) => {
      if (!drag) return;
      panel.style.left = ox + (e.clientX - sx) + "px";
      panel.style.top = oy + (e.clientY - sy) + "px"; panel.style.right = "auto";
    });
    document.addEventListener("mouseup", () => { drag = false; });
  })();

  // ── inpage.js를 페이지 MAIN world에 주입 ────────────────
  (function () {
    const sc = document.createElement("script");
    sc.src = chrome.runtime.getURL("inpage.js");
    sc.charset = "utf-8";
    sc.onload = () => sc.remove();
    (document.head || document.documentElement).appendChild(sc);
  })();
  window.addEventListener("cardsales-log", (e) => log(String(e.detail)));

  // ── 자동 실행: 매입내역 URL에 csauto=1 있으면 다운로드 ──
  function normDate(s) {
    const d = (s || "").replace(/\D/g, "");
    return d.length === 8 ? `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}` : (s || "");
  }
  function maybeAutoRun() {
    if (!/\/page\/purchase\/term/.test(location.pathname)) return;
    if (sessionStorage.getItem("cs_job")) {
      const nm = sessionStorage.getItem("cs_name") || "";
      log(`진행 중${nm ? " — " + nm : ""} (조회 후 이어서)`);
      return;
    }
    const p = new URLSearchParams(location.search);
    if (p.get("csauto") !== "1") return;
    const from = normDate(p.get("csfrom")), to = normDate(p.get("csto"));
    const name = p.get("csname") || "";
    if (!from || !to) return;
    try { sessionStorage.setItem("cs_name", name); } catch (e) {}
    log(`▶ ${name ? name + " | " : ""}${from} ~ ${to}  다운로드 시작`);
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent("cardsales-cmd",
        { detail: { action: "run", from, to } }));
    }, 1500);
  }
  if (document.readyState === "complete") maybeAutoRun();
  else window.addEventListener("load", maybeAutoRun);
})();
