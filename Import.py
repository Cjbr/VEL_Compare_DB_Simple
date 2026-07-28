"""Streamlit dashboard for comparing equipment use across projects."""

import os
import sqlite3

import pandas as pd
import streamlit as st


DB_PATH = os.environ.get(
    "VEL_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "vel_data.db")
)


def load_data(db_path=DB_PATH):
    """Return imported records, or an empty frame when the database is not ready."""
    if not os.path.exists(db_path):
        return pd.DataFrame()
    try:
        with sqlite3.connect(db_path) as connection:
            return pd.read_sql("SELECT * FROM my_table", connection)
    except (sqlite3.DatabaseError, pd.errors.DatabaseError):
        return pd.DataFrame()


def build_equipment_summary(dataframe, equipment_column, project_column):
    """Create one row per equipment ID with project membership and reuse metrics."""
    pairs = dataframe[[equipment_column, project_column]].copy()
    pairs.columns = ["equipment", "project"]
    pairs = pairs.dropna()
    pairs["equipment"] = pairs["equipment"].astype(str).str.strip()
    pairs["project"] = pairs["project"].astype(str).str.strip()
    pairs = pairs[(pairs["equipment"] != "") & (pairs["project"] != "")].drop_duplicates()

    total_projects = pairs["project"].nunique()
    summary = (
        pairs.groupby("equipment", as_index=False)
        .agg(project_count=("project", "nunique"), projects=("project", lambda x: ", ".join(sorted(x))))
        .sort_values(["project_count", "equipment"], ascending=[False, True])
    )
    summary["reuse_rate"] = (
        summary["project_count"].div(total_projects).mul(100) if total_projects else 0.0
    )
    summary["classification"] = summary["project_count"].map(
        lambda count: "Shared" if count > 1 else "Project-specific"
    )
    return pairs, summary


def filter_rows(dataframe, kks_filter, device):
    """Apply optional KKS filters to the first column."""
    values = dataframe.iloc[:, 0].fillna("").astype(str).str.upper()
    mask = pd.Series(True, index=dataframe.index)
    if kks_filter.strip():
        expected = kks_filter.strip().upper()
        mask &= values.str.slice(2, 2 + len(expected)).eq(expected)
    if device.strip():
        mask &= values.str.contains(device.strip().upper(), regex=False)
    return dataframe.loc[mask]


def render_import_panel():
    """Render database administration and Excel import controls."""
    with st.expander("Import & database management"):
        st.caption(f"Database: {DB_PATH}")
        uploaded_file = st.file_uploader("Add a project Excel file", type=["xlsx", "xls"])
        if st.button("Import file", type="primary", disabled=uploaded_file is None):
            try:
                with sqlite3.connect(DB_PATH) as connection:
                    try:
                        duplicate = pd.read_sql(
                            "SELECT COUNT(*) count FROM my_table WHERE source_file = ?",
                            connection,
                            params=(uploaded_file.name,),
                        ).iloc[0, 0]
                    except (sqlite3.DatabaseError, pd.errors.DatabaseError):
                        duplicate = 0
                    if duplicate:
                        st.warning(f"{uploaded_file.name} has already been imported.")
                    else:
                        imported = pd.read_excel(uploaded_file, sheet_name="Query", header=1, usecols="A:U")
                        imported["source_file"] = uploaded_file.name
                        imported.to_sql("my_table", connection, if_exists="append", index=False)
                        st.success(f"Imported {len(imported):,} records from {uploaded_file.name}.")
                        st.rerun()
            except (ImportError, OSError, TypeError, ValueError, sqlite3.DatabaseError) as error:
                st.error(f"The file could not be imported: {error}")

        data = load_data()
        if not data.empty and "source_file" in data:
            files = sorted(data["source_file"].dropna().unique())
            selected = st.selectbox("Imported file", ["Select a file…"] + files)
            if selected != "Select a file…" and st.button("Delete selected file"):
                with sqlite3.connect(DB_PATH) as connection:
                    connection.execute("DELETE FROM my_table WHERE source_file = ?", (selected,))
                st.rerun()


st.set_page_config(page_title="Equipment Portfolio", page_icon="⚙️", layout="wide")
st.title("Cross-Project Equipment Dashboard")
st.caption("See what is unique, what is shared, and where standardization is already happening.")

render_import_panel()
raw_data = load_data()

if raw_data.empty:
    st.info("Import at least one project file to begin comparing equipment.")
    st.stop()

columns = list(raw_data.columns)
default_project = columns.index("source_file") if "source_file" in columns else min(1, len(columns) - 1)
with st.sidebar:
    st.header("Dashboard controls")
    equipment_column = st.selectbox("Equipment identifier", columns, index=0)
    project_column = st.selectbox("Project", columns, index=default_project)
    kks_filter = st.text_input("KKS letters at position 3", value="")
    device_filter = st.text_input("Equipment contains", value="")

filtered_data = filter_rows(raw_data, kks_filter, device_filter)
pairs, equipment = build_equipment_summary(filtered_data, equipment_column, project_column)
project_total = pairs["project"].nunique()
equipment_total = len(equipment)
shared_total = int((equipment["project_count"] > 1).sum()) if equipment_total else 0
specific_total = equipment_total - shared_total
reuse_rate = shared_total / equipment_total * 100 if equipment_total else 0
heavy_threshold = st.sidebar.slider(
    "Heavy reuse threshold (projects)", 2, max(2, project_total), min(3, max(2, project_total))
)
heavy_total = int((equipment["project_count"] >= heavy_threshold).sum()) if equipment_total else 0

metric_columns = st.columns(5)
metrics = [
    ("Projects", project_total, "in scope"),
    ("Unique equipment", equipment_total, "distinct IDs"),
    ("Shared equipment", shared_total, f"{reuse_rate:.1f}% of equipment"),
    ("Project-specific", specific_total, "used by one project"),
    ("Heavily reused", heavy_total, f"used in {heavy_threshold}+ projects"),
]
for column, (label, value, help_text) in zip(metric_columns, metrics):
    column.metric(label, f"{value:,}", help=help_text)

st.divider()
overview_tab, reuse_tab, matrix_tab, records_tab = st.tabs(
    ["Portfolio overview", "Reuse leaders", "Project matrix", "Records"]
)

with overview_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Shared vs. project-specific")
        classification = equipment["classification"].value_counts().rename_axis("type").to_frame("equipment")
        st.bar_chart(classification, horizontal=True)
    with right:
        st.subheader("Equipment footprint by project")
        project_counts = pairs.groupby("project")["equipment"].nunique().sort_values(ascending=False)
        st.bar_chart(project_counts, horizontal=True)
    st.subheader("Reuse distribution")
    distribution = equipment["project_count"].value_counts().sort_index().rename_axis("projects").to_frame("equipment")
    st.bar_chart(distribution)

with reuse_tab:
    st.subheader("Most reused equipment")
    leaders = equipment[equipment["project_count"] >= heavy_threshold].copy()
    st.dataframe(
        leaders.rename(columns={
            "equipment": "Equipment", "project_count": "Projects", "projects": "Project list",
            "reuse_rate": "Portfolio coverage (%)", "classification": "Type",
        }),
        hide_index=True,
        use_container_width=True,
        column_config={"Portfolio coverage (%)": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)},
    )

with matrix_tab:
    st.subheader("Equipment × project coverage")
    matrix = pd.crosstab(pairs["equipment"], pairs["project"]).astype(bool)
    matrix.insert(0, "Project count", matrix.sum(axis=1))
    st.dataframe(matrix.sort_values("Project count", ascending=False), use_container_width=True)
    st.download_button("Download coverage matrix", matrix.to_csv().encode("utf-8"), "equipment_coverage.csv", "text/csv")

with records_tab:
    st.subheader("Filtered source records")
    st.dataframe(filtered_data, hide_index=True, use_container_width=True)
    st.caption(f"{len(filtered_data):,} records shown")
