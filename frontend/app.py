"""Semester Sentinel: Streamlit interface.

Run:     streamlit run app.py
4 tabs:  Upload -> Review -> Dashboard -> Export

Streamlit reminder: the whole file runs again from top to bottom on every click.
To keep data between two clicks, we store it in st.session_state.
"""
import json
from datetime import date
from pathlib import Path
from urllib.parse import quote

import pandas as pd
import streamlit as st

import api
import logic

st.set_page_config(page_title="Semester Sentinel", page_icon="🛡️", layout="wide")

DEMO_FILE = Path(__file__).parent / "demo.json"
COLUMNS = ["course", "title", "kind", "due", "weight"]
LEVEL_LABELS = {"green": "🟢 Calm", "yellow": "🟡 Busy", "orange": "🟠 Heavy", "red": "🔴 Final Boss"}


# ---------- Data shared between tabs ----------

def set_deadlines(rows, source):
    """Replaces all deadlines (demo or upload)."""
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["due"] = pd.to_datetime(df["due"], errors="coerce").dt.date  # text -> real date
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0)

    st.session_state["table"] = df                         # what the Review table shows at first
    st.session_state["deadlines"] = df.to_dict("records")  # what the other tabs read
    st.session_state["source"] = source
    # Changing this number forces the Review table to reload with the new data
    st.session_state["table_id"] = st.session_state["table_id"] + 1


# First run: create empty values
if "deadlines" not in st.session_state:
    st.session_state["deadlines"] = []
    st.session_state["table"] = pd.DataFrame(columns=COLUMNS)
    st.session_state["source"] = None
    st.session_state["table_id"] = 0


# ---------- Header ----------

st.title("🛡️ Semester Sentinel")
st.caption("Spot your \"Final Boss\" weeks before they hit.")

if st.button("Load demo", type="primary"):
    with open(DEMO_FILE, encoding="utf-8") as f:
        set_deadlines(json.load(f), "demo")
    st.toast("Demo data loaded: check the Dashboard.")

if st.session_state["source"]:
    st.info("Source: " + st.session_state["source"] + " · " + str(len(st.session_state["deadlines"])) + " deadlines")

tab_upload, tab_review, tab_dash, tab_export = st.tabs(["1. Upload", "2. Review", "3. Dashboard", "4. Export"])


# ---------- Tab 1: Upload ----------

with tab_upload:
    st.subheader("Upload your syllabus")
    files = st.file_uploader("3 to 6 syllabus (PDF, .docx or .txt)", type=["pdf", "docx", "txt"], accept_multiple_files=True)
    term_start = st.date_input("Term start date", value=date(2026, 9, 8))

    # One "course name" field per file
    names = []
    for f in files:
        guess = f.name.split("_")[0].split(".")[0].upper()  # "MATH1000U_fall.pdf" -> "MATH1000U"
        names.append(st.text_input("Course name for " + f.name, value=guess, key="name_" + f.name))

    good_count = 3 <= len(files) <= 6
    if len(files) > 0 and not good_count:
        st.warning(str(len(files)) + " file(s): you need between 3 and 6.")

    if st.button("Analyze syllabus", disabled=not good_count):
        with st.spinner("Reading the syllabus… (can take 1 to 2 minutes)"):
            try:
                rows, errors = api.parse_syllabi(files, names, term_start)
                set_deadlines(rows, "syllabus")
                st.success(str(len(rows)) + " deadlines found. Check them on the Review tab.")
                for e in errors:
                    st.warning(str(e.get("file")) + ": " + str(e.get("error")))
            except api.ApiError as err:
                st.error(str(err))

    st.caption("Server: " + api.API_URL)


# ---------- Tab 2: Review ----------

with tab_review:
    st.subheader("Check and fix the deadlines")
    st.caption("Click a cell to edit it. Add or delete rows at the bottom of the table.")

    edited = st.data_editor(
        st.session_state["table"],
        key="table_" + str(st.session_state["table_id"]),
        num_rows="dynamic",   # lets the user add / delete rows
        hide_index=True,
        width="stretch",
        column_config={
            "course": st.column_config.TextColumn("Course"),
            "title": st.column_config.TextColumn("Title"),
            "kind": st.column_config.SelectboxColumn("Type", options=logic.KINDS),
            "due": st.column_config.DateColumn("Date"),
            "weight": st.column_config.NumberColumn("Weight (%)", min_value=0, max_value=100),
        },
    )
    # What the user edited becomes the new list of deadlines
    st.session_state["deadlines"] = edited.to_dict("records")

    without_date = len(st.session_state["deadlines"]) - len(logic.clean(st.session_state["deadlines"]))
    if without_date > 0:
        st.warning(str(without_date) + " deadline(s) without a date: they are ignored on the Dashboard.")


# ---------- Tab 3: Dashboard ----------

with tab_dash:
    deadlines = st.session_state["deadlines"]
    weeks = logic.weekly_scores(deadlines)

    if len(weeks) == 0:
        st.info("No data yet. Click \"Load demo\" or upload your syllabus.")
    else:
        collisions = logic.find_collisions(deadlines)

        # Count Final Boss weeks and find the worst week
        boss_count = 0
        worst = weeks[0]
        for w in weeks:
            if w["is_final_boss"]:
                boss_count = boss_count + 1
            if w["score"] > worst["score"]:
                worst = w

        # 4 key numbers
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Deadlines", len(logic.clean(deadlines)))
        c2.metric("Final Boss weeks", boss_count)
        c3.metric("Collisions", len(collisions))
        c4.metric("Worst week", str(worst["score"]) + " pts")

        # Alerts
        for w in weeks:
            if w["is_final_boss"]:
                st.error("🔥 Final Boss Week: week of " + str(w["week_start"]) + " (" + str(w["score"]) + " points)")
        for c in collisions:
            names = []
            for d in c["items"]:
                names.append(d["course"] + " " + d["title"] + " (" + str(d["due"]) + ")")
            st.warning("⚠️ Collision from " + str(c["start"]) + " to " + str(c["end"]) + ": " + ", ".join(names))

        # Weekly table
        st.markdown("#### Score by week")
        week_rows = []
        for w in weeks:
            titles = []
            for d in w["items"]:
                titles.append(d["course"] + " " + d["title"])
            week_rows.append({
                "Week of": str(w["week_start"]),
                "Level": LEVEL_LABELS[w["level"]],
                "Score": w["score"],
                "Deadlines": " · ".join(titles),
            })
        st.dataframe(pd.DataFrame(week_rows), hide_index=True, width="stretch")
        st.caption("Points: exam 4 · project 3 · quiz 1.5 · assignment 1 · ×1.5 if weight ≥ 20%. "
                "Green < 4 · Yellow 4 to 7.9 · Orange 8 to 11.9 · Red ≥ 12.")

        # Chart
        chart = pd.DataFrame(week_rows).set_index("Week of")["Score"]
        st.bar_chart(chart)

        # Suggested start dates
        st.markdown("#### When to start? (orange and red weeks)")
        starts = logic.suggested_starts(deadlines)
        if len(starts) == 0:
            st.success("No heavy weeks: nothing to start early.")
        else:
            start_rows = []
            for s in starts:
                start_rows.append({
                    "Course": s["course"],
                    "Deadline": s["title"],
                    "Due date": str(s["due"]),
                    "Start by": str(s["start_by"]),
                    "Days ahead": s["days_ahead"],
                })
            st.table(pd.DataFrame(start_rows))


# ---------- Tab 4: Export ----------

with tab_export:
    st.subheader("Export to your calendar")
    count = len(logic.clean(st.session_state["deadlines"]))
    if count == 0:
        st.info("Nothing to export yet.")
    else:
        st.write(str(count) + " deadlines, each with a reminder the day before.")
        st.download_button(
            "Download semester.ics",
            data=logic.to_ics(st.session_state["deadlines"]),
            file_name="semester.ics",
            mime="text/calendar",
            type="primary",
        )
        st.caption("Open the file with Google Calendar, Outlook or Apple Calendar.")


# ---------- Footer: Ontario Tech banner ----------
# Drawn in HTML/CSS (no image), so it stays sharp at any size.
# position: fixed + bottom: 0 keeps the bar stuck to the bottom of the window, full width.
# The main container gets extra space at the bottom so the bar never hides the content.
# Careful: no blank lines (even lines with only spaces) inside the CSS, or st.markdown breaks it.

FOOTER_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@600;700&display=swap');
[data-testid="stMainBlockContainer"] { padding-bottom: 96px; }
.ot-footer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  height: 64px;
  overflow: hidden;
  background: #0077CA;
  border-top: 4px solid #003C71;
  display: flex;
  align-items: center;
  padding: 0 24px;
}
.ot-ring {
  position: absolute;
  border-radius: 50%;
  box-sizing: border-box;
}
.ot-ring-dark { width: 300px; height: 300px; left: 40%; bottom: 0; border: 34px solid #003C71; }
.ot-ring-light { width: 300px; height: 300px; left: calc(40% + 190px); bottom: -30px; border: 34px solid #0062AE; }
.ot-brand { position: relative; font-family: 'Figtree', 'Segoe UI', Arial, sans-serif; color: #FFFFFF; line-height: 1; }
.ot-name { font-weight: 700; font-size: 24px; letter-spacing: -0.01em; }
.ot-name span { color: #F26B21; }
.ot-uni { font-weight: 600; font-size: 9.5px; letter-spacing: 0.2em; margin-top: 3px; }
@media (max-width: 600px) {
  .ot-footer { height: 52px; padding: 0 16px; }
  .ot-name { font-size: 20px; }
  .ot-uni { font-size: 8px; }
  .ot-ring-dark { left: 55%; }
  .ot-ring-light { display: none; }
}
</style>
"""

FOOTER_HTML = (
    '<div class="ot-footer">'
    '<div class="ot-ring ot-ring-light"></div>'
    '<div class="ot-ring ot-ring-dark"></div>'
    '<div class="ot-brand"><div class="ot-name">Ontario<span>Tech</span></div><div class="ot-uni">UNIVERSITY</div></div>'
    '</div>'
)

st.markdown(FOOTER_CSS + FOOTER_HTML, unsafe_allow_html=True)


# ---------- Background: blurred Ontario Tech logo ----------
# The logo is drawn in SVG (dark blue shield, light blue arc, orange corner).
# feGaussianBlur blurs it, opacity makes it faint, and it is set as the page background.
# To change it: stdDeviation = how blurry, opacity = how visible.

LOGO_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 670 880'>"
    "<filter id='blur' x='-10%' y='-10%' width='120%' height='120%'><feGaussianBlur stdDeviation='6'/></filter>"
    "<g filter='url(#blur)' opacity='0.5'>"
    "<path d='M90 358 H125 A333 333 0 0 1 458 691 V760' fill='none' stroke='#1E90E8' stroke-width='80'/>"
    "<path d='M388 162 H87 V553 A248 248 0 0 0 583 553 V355' fill='none' stroke='#0F5BB5' stroke-width='78'/>"
    "<path d='M465 125 H622 V280 H545 V200 H465 Z' fill='#F26B21'/>"
    "</g>"
    "</svg>"
)

BACKGROUND_CSS = (
    "<style>.stApp {"
    " background-image: url(\"data:image/svg+xml," + quote(LOGO_SVG) + "\") !important;"
    " background-repeat: no-repeat !important;"
    " background-position: center 45% !important;"
    " background-size: min(55vh, 85vw) auto !important;"
    " background-attachment: fixed !important;"
    "}</style>"
)

st.markdown(BACKGROUND_CSS, unsafe_allow_html=True)
