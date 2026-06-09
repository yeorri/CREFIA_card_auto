/* inpage.js — 페이지 MAIN world에서 실행. 사이트의 jQuery/함수를 그대로 사용한다.
 *
 * 실제 사용자 흐름을 그대로 자동화:
 *   날짜입력 → 조회 → 전체 체크 → 상세조회 → 상세 엑셀(goSubExcelPrint) 다운로드
 *
 * 조회/상세조회가 '페이지 리로드'를 일으켜도 끊기지 않도록, 진행 단계를
 * sessionStorage에 저장하는 상태머신으로 동작한다. 페이지가 새로 로드될 때마다
 * resume()이 저장된 단계를 보고 이어서 진행한다.
 *
 * content script와 CustomEvent로 통신:
 *   수신 'cardsales-cmd'  detail={action:'run', from, to}
 *   송신 'cardsales-log'  detail=문자열
 */
(function () {
  "use strict";

  const KEY = "cs_job";

  function log(m) {
    try { window.dispatchEvent(new CustomEvent("cardsales-log", { detail: String(m) })); } catch (e) {}
  }
  function jq() { return window.jQuery || window.$; }
  function onPurchaseTerm() { return /\/page\/purchase\/term/.test(location.pathname); }

  function getJob() { try { return JSON.parse(sessionStorage.getItem(KEY)); } catch (e) { return null; } }
  function setJob(j) { sessionStorage.setItem(KEY, JSON.stringify(j)); }
  function clearJob() { sessionStorage.removeItem(KEY); }

  function waitFor(cond, onDone, opts) {
    opts = opts || {};
    const interval = opts.interval || 250;
    let tries = opts.tries || 40;
    (function tick() {
      let ok = false; try { ok = !!cond(); } catch (e) {}
      if (ok) return onDone(true);
      if (--tries <= 0) return onDone(false);
      setTimeout(tick, interval);
    })();
  }

  function summaryRows() {
    return document.querySelectorAll(".table_cell_body input[type=checkbox]").length;
  }
  function checkedCount() {
    return document.querySelectorAll(".table_cell_body input[type=checkbox]:checked").length;
  }
  function clickExact(text, selector) {
    const els = [...document.querySelectorAll(selector || "a,button,input[type=button]")]
      .filter((el) => (el.innerText || el.value || "").trim() === text);
    const el = els[0];
    if (el) { el.scrollIntoView({ block: "center" }); el.click(); }
    return el;
  }

  // ── 명령 진입점 ─────────────────────────────────────────
  function run(from, to) {
    if (!onPurchaseTerm()) {
      log("✗ '기간별 매입내역' 화면이 아닙니다. 매입내역 → 기간별 매입내역 조회 로 이동 후 실행하세요.");
      return;
    }
    const $ = jq();
    if (!$) { log("jQuery를 찾지 못했습니다."); return; }
    setJob({ from: from, to: to, stage: "await_summary", t: Date.now() });
    $("#searchStrDate").val(from).trigger("change");
    $("#searchEndDate").val(to).trigger("change");
    log("① 날짜 입력: " + from + " ~ " + to + " → 조회");
    const b = document.querySelector("#searchBtn");
    if (!b) { log("✗ 조회 버튼(#searchBtn)을 못 찾음"); clearJob(); return; }
    b.click();
    setTimeout(resume, 1500); // 리로드 안 하는(ajax) 경우 대비
  }

  // ── 상태머신: 페이지 로드/검색 후마다 호출되어 이어서 진행 ──
  function resume() {
    const job = getJob();
    if (!job) return;
    if (Date.now() - job.t > 120000) { clearJob(); return; }
    if (!onPurchaseTerm()) return;
    const $ = jq();
    if (!$) return;

    if (job.stage === "await_summary") {
      waitFor(summaryRows, function (ok) {
        if (!ok) { log("✗ 요약 결과가 없습니다 (해당 기간 데이터 없음일 수 있음)"); clearJob(); return; }
        log("② 요약 " + summaryRows() + "행 로드됨");
        // 전체 체크
        const head = document.querySelector(".table_cell_header input[type=checkbox]")
          || document.querySelector("input[name='checkbox-inline']");
        if (head && !head.checked) head.click();
        setTimeout(function () {
          if (checkedCount() === 0) {
            $(".table_cell_body input[type=checkbox]").prop("checked", true).trigger("change");
          }
          log("③ 전체 체크: " + checkedCount() + "/" + summaryRows());
          // 다음 단계 저장 후 상세조회
          setJob({ from: job.from, to: job.to, stage: "await_detail", t: Date.now() });
          const d = clickExact("상세조회", "a,button,input[type=button]");
          if (!d) { log("✗ 상세조회 버튼을 못 찾음"); clearJob(); return; }
          log("④ 상세조회 클릭 — 상세내역 대기...");
          setTimeout(resume, 1800); // ajax 경우 대비
        }, 500);
      }, { tries: 40 });
    } else if (job.stage === "await_detail") {
      // 상세 데이터가 채워질 시간을 준 뒤 상세 엑셀 호출
      waitFor(function () { return typeof window.goSubExcelPrint === "function"; }, function (ok) {
        setTimeout(function () {
          log("⑤ 상세 엑셀 다운로드 시도...");
          try {
            if (typeof window.goSubExcelPrint === "function") {
              window.goSubExcelPrint("Excel");
              log("✓ 완료 — 다운로드가 시작되는지 확인하세요.");
            } else {
              log("✗ goSubExcelPrint 함수를 찾지 못함");
            }
          } catch (e) { log("✗ 엑셀 호출 오류: " + e); }
          clearJob();
        }, 2000);
      }, { tries: 20 });
    }
  }

  // 로그인은 Python(스캔코드 OS입력)이 담당한다. 확장은 데이터 다운로드만.
  window.addEventListener("cardsales-cmd", function (e) {
    const d = (e && e.detail) || {};
    if (d.action === "run") run(d.from, d.to);
  });

  // 페이지가 (리로드 등으로) 새로 로드될 때 진행 중 작업 이어가기
  if (onPurchaseTerm() && getJob()) {
    setTimeout(resume, 800);
  }

  log("준비됨.");
})();
