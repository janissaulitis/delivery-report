"""
Delivery report builder: web front end for report.py
Upload a tournament's production logs -> client PDF report + internal payroll and data-issues file.
"""
import base64, html, os, shutil, tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

import kit
import report

HERE = Path(__file__).parent
SAMPLES = {
    "Sample week (messy, as logged)": HERE / "sample",
    "Sample week with extra mistakes (test file)": HERE / "sample_mistakes" / "logs_with_mistakes.xlsx",
}
FILES = {
    "production_log.csv": "Production log",
    "faults.csv": "Fault / incident log",
    "distribution.xlsx": "Distribution & audience",
    "crew_timesheet.csv": "Crew timesheet",
    "entry_list.csv": "Tournament entry list",
}

kit.page("Client Report", "Turns a week of messy production logs into a checked client report", mark="report", icon="📄",
         theme="stub", meta="For production companies and rights holders · tournament data is invented")

PORTFOLIO = "https://janis-saulitis-portfolio.netlify.app"
DEMO_VIDEO = os.environ.get("DEMO_VIDEO", PORTFOLIO + "/media/report.mp4")
build_clicked = False


def _build_button(bar):
    global build_clicked
    build_clicked = bar.button("▶  Build the sample report", type="primary", key="build_btn")
    bar.space("stretch")


kit.demo(DEMO_VIDEO, "Client Report in 1 minute",
         "1. Click **Build the sample report**: five messy log files are checked in about 10 seconds.\n"
         "2. Read the data check: what was fixed, what is held back to confirm, what was left out.\n"
         "3. Download the client PDF, plus the internal Excel with crew overtime and a to-do list of data problems.\n"
         "4. Try your own files under **Use my own logs**.", extra=_build_button)
st.markdown("<style>.st-key-k_demo [data-testid='stBaseButton-primary']{} @media (max-width:640px){.st-key-k_demo{flex-wrap:wrap}}</style>",
            unsafe_allow_html=True)
answer_box = st.container()

work = Path(st.session_state.setdefault("work", tempfile.mkdtemp(prefix="delivery_")))
run_source = None
if build_clicked:
    run_source = SAMPLES["Sample week with extra mistakes (test file)"]

left, right = st.columns([1, 1], gap="large", vertical_alignment="top")
FIXES = [("11.18 · 1330 · 13", "11:18 · 13:30 · 13:00", "fixed", "Fixed"), ("R33", "R32", "fixed", "Fixed"),
         ("Tenniss TV", "Tennis TV", "fixed", "Fixed"), ("4.629 viewers", "4 629 viewers", "fixed", "Fixed"),
         ("130 966 viewers", "20× the usual audience", "held", "Held back"), ("off air 19:12, on air 19:29", "impossible times", "flag", "Flagged")]
with left:
    st.markdown('<div class="k-paper"><div class="eyebrow">From 5 messy log files</div><h3>Every fix, listed.<br>Nothing guessed.</h3>'
                '<div class="k-fix h"><span>Typed in the log</span><span>In the report</span><span style="text-align:right">Action</span></div>'
                + "".join(f'<div class="k-fix"><s>{html.escape(a)}</s><b>{html.escape(b)}</b><span class="k-stamp {c}">{t}</span></div>'
                          for a, b, c, t in FIXES) + "</div>", unsafe_allow_html=True)
with right:
    img = base64.b64encode((HERE / "assets" / "report_preview.png").read_bytes()).decode()
    st.markdown(f'<div class="k-tilt" style="padding:6px 10px 0"><img src="data:image/png;base64,{img}" style="width:100%" alt="Page 1 of the client report"></div>',
                unsafe_allow_html=True)
    st.markdown('<div class="k-note-s" style="margin-top:22px;padding:14px 16px;border:1px solid var(--k-line);background:var(--k-surface);border-radius:4px">'
                '<b>Plus an internal Excel</b><br><span style="color:var(--k-muted)">crew overtime for payroll, and a to-do list of every data problem</span></div>',
                unsafe_allow_html=True)


# ------------------------------------------------------------------ own logs / other sample
with st.expander("Use my own logs, or the other sample"):
    mode = st.radio("Source", ["Try a sample", "Upload my own logs"], horizontal=True, label_visibility="collapsed")
    source = None
    if mode == "Try a sample":
        pick = st.selectbox("Sample", list(SAMPLES))
        source = SAMPLES[pick]
        files = [source] if source.is_file() else sorted(p for p in source.iterdir() if p.is_file())
        st.markdown('<p class="small">Download the sample files to see what goes in:</p>', unsafe_allow_html=True)
        for f in files + ([source.parent / "entry_list.csv"] if source.is_file() else []):
            st.download_button(f"⬇ {f.name}", f.read_bytes(), file_name=f.name, key=f"dl_{f.parent.name}_{f.name}")
    else:
        st.markdown("Upload **one Excel workbook** with the four logs as tabs (e.g. downloaded from Google Sheets), "
                    "**or** the four separate files. The entry list (one player per line) is optional; "
                    "without it the sample tournament's list is used.")
        up = st.file_uploader("Logs", type=["csv", "xlsx"], accept_multiple_files=True)
        if up:
            folder = work / "upload"
            shutil.rmtree(folder, ignore_errors=True); folder.mkdir(parents=True)
            for u in up: (folder / u.name).write_bytes(u.getvalue())
            if not (folder / "entry_list.csv").exists():
                shutil.copy(HERE / "sample" / "entry_list.csv", folder / "entry_list.csv")
            workbooks = [folder / u.name for u in up if u.name.lower().endswith(".xlsx") and u.name.lower() != "distribution.xlsx"]
            missing = [f for f in FILES if f != "entry_list.csv" and not (folder / f).exists()]
            if workbooks:
                source = workbooks[0]
            elif missing:
                st.warning("Still missing: " + ", ".join(FILES[m] + f" ({m})" for m in missing))
            else:
                source = folder
    if source and st.button("Build the report"):
        run_source = source

# ------------------------------------------------------------------ run
if run_source:
    out = work / "out"
    shutil.rmtree(out, ignore_errors=True)
    try:
        with st.spinner("Reading and checking the logs…"):
            s, matches, faults, dist, shifts, issues = report.build(Path(run_source), out, pdf=False)
        pdf_bytes, pdf_error = None, None
        with st.spinner("Making the PDF…"):
            try:
                report.write_pdf(out / "delivery_report.html", out / "delivery_report.pdf")
                pdf_bytes = (out / "delivery_report.pdf").read_bytes()
            except Exception as e:
                pdf_error = str(e)
        st.session_state["result"] = dict(
            s=s, issues=[vars(i) for i in issues.items], html=(out / "delivery_report.html").read_text(encoding="utf-8"),
            xlsx=(out / "internal_ops.xlsx").read_bytes(), pdf=pdf_bytes, pdf_error=pdf_error,
            overtime=pd.read_excel(out / "internal_ops.xlsx", sheet_name="Overtime (payroll)"))
    except SystemExit as e:
        st.error(f"Couldn't read the logs: {e}")
        st.session_state.pop("result", None)
    except Exception as e:
        st.error(f"Something in the files couldn't be read ({type(e).__name__}: {e}). Check the column headers match the sample files.")
        st.session_state.pop("result", None)

# ------------------------------------------------------------------ results
res = st.session_state.get("result")
if res:
    s = res["s"]
    lv = pd.Series([i["level"] for i in res["issues"]]).value_counts()
    with answer_box:
        kit.answer("Report built and checked",
                   f"{s['matches']} matches, {s['on_air_min'] / 60:.0f} hours on air, {s['uptime_pct']:.1f}% on-air reliability",
                   f"<b>{lv.get('INFO', 0)}</b> typos were read automatically, <b>{lv.get('WARN', 0)}</b> figures are held back "
                   f"for someone to confirm, and <b>{lv.get('ERROR', 0)}</b> impossible entries were left out of the numbers. "
                   "The client report and the internal file are ready to download below.",
                   [("Matches produced", str(s["matches"])), ("Hours on air", f"{s['on_air_min'] / 60:.1f}"),
                    ("On-air reliability", f"{s['uptime_pct']:.2f}%"), ("Peak audience", f"{s['viewers_peak']:,}".replace(",", " "))],
                   tone="good")
    st.markdown("#### Your files")
    d = st.columns(2)
    if res["pdf"]:
        d[0].download_button("⬇ Client report (PDF)", res["pdf"], file_name="delivery_report.pdf", mime="application/pdf", type="primary")
    else:
        d[0].download_button("⬇ Client report (HTML, print to PDF)", res["html"], file_name="delivery_report.html", mime="text/html")
        st.caption(f"PDF engine not available here, so the report is offered as a printable web page. ({res['pdf_error'][:120]})")
    d[1].download_button("⬇ Internal file: overtime + data issues (Excel)", res["xlsx"], file_name="internal_ops.xlsx")

    t1, t2, t3 = st.tabs(["Client report", "Data issues (to-do)", "Overtime (payroll)"])
    with t1:
        st.caption("What the rights holder receives. No payroll or internal file details.")
        st.iframe(res["html"], height=1100)
    with t2:
        st.caption("For whoever owns the logs: what was read automatically, what was held back, and what must be fixed.")
        show = st.multiselect("Show", ["Left out", "Held back", "Read automatically"], default=["Left out", "Held back"])
        lvl = {"ERROR": "Left out", "WARN": "Held back", "INFO": "Fixed"}
        rows = sorted(res["issues"], key=lambda i: (["ERROR", "WARN", "INFO"].index(i["level"]), i["source"], i["row"] or 0))
        kit.table([{**i, "level": lvl[i["level"]], "row": i["row"] or "", "effect": i["effect"] or "—"} for i in rows if lvl[i["level"]] in show],
                  [kit.col("", "level", "chip", {"Left out": "bad", "Held back": "warn", "Read automatically": "info"}),
                   kit.col("File", "source", "muted"), kit.col("Row", "row", "num"), kit.col("Field", "field", "strong"),
                   kit.col("Value", "value", "code"), kit.col("Problem", "problem", "wrap"), kit.col("Effect on report", "effect", "muted")],
                  max_height=520)
    with t3:
        st.caption("Internal only. Minutes past the planned end of shift, per person per day, paid at double rate.")
        ot = res["overtime"]
        days = [c for c in ot.columns if c not in ("Person", "Total (min)", "Total", "Pay rate")]
        kit.table([{**r, **{d: (f"{int(r[d])} min" if r[d] else "—") for d in days}} for r in ot.to_dict("records")],
                  [kit.col("Person", "Person", "strong")] + [kit.col(d, d, "num") for d in days]
                  + [kit.col("Total", "Total", "num"), kit.col("Pay", "Pay rate", "chip", {"Double rate": "warn"})])

kit.footer("report.py · 12 automated tests, including a file deliberately filled with mistakes")
