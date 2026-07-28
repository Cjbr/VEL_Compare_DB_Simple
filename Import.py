import os
import sqlite3

import pandas as pd
import streamlit as st

db_path = os.environ.get(
    "VEL_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "vel_data.db")
)


def filter_rows(dataframe, kks_filter, device):
    """Apply the sidebar filters to the first (KKS) column."""
    kks_values = dataframe.iloc[:, 0].fillna("").astype(str).str.upper()
    mask = pd.Series(True, index=dataframe.index)
    expected = kks_filter.strip().upper()
    expected_device = device.strip().upper()

    if expected:
        mask &= kks_values.str.slice(2, 2 + len(expected)).eq(expected)

    if expected_device:
        mask &= kks_values.str.contains(expected_device, regex=False)

    return dataframe.loc[mask]


st.title("VEL Import Tool")

# ─────────────────────────────────────────
# SHARED FILTER — drives sections 2, 3, 4
# ─────────────────────────────────────────
st.sidebar.header("Filter Settings")
shared_filter = st.sidebar.text_input(
    "KKS Filter by letters at position 3 (e.g. CHA)", value="CHA"
)
device_filter = st.sidebar.text_input(
    "KKS Filter by letters at position device (e.g. -M01)", value="-M01"
)

# ─────────────────────────────────────────
# SECTION 1 — Database Status
# ─────────────────────────────────────────
st.sidebar.header("1. Database Status")

if os.path.exists(db_path):
    st.sidebar.success("Database found")
    st.sidebar.write(f"**Path:** {db_path}")
    st.sidebar.write(f"**File:** {os.path.basename(db_path)}")

    try:
        with sqlite3.connect(db_path) as conn:
            imported_files = pd.read_sql("SELECT DISTINCT source_file FROM my_table", conn)
        st.sidebar.write("**Imported files:**")
        st.sidebar.dataframe(imported_files)
    except (sqlite3.DatabaseError, pd.errors.DatabaseError):
        imported_files = pd.DataFrame(columns=["source_file"])
        st.sidebar.warning("Database exists but no data imported yet.")

    # --- Delete an imported file from DB ---
    st.sidebar.subheader("Delete imported file from DB")
    try:
        imported_files_list = imported_files["source_file"].dropna().tolist()
        file_to_delete = st.sidebar.selectbox(
            "Select file to delete", options=["-- Select --"] + imported_files_list
        )

        if file_to_delete != "-- Select --":
            if st.sidebar.button(f"Delete '{file_to_delete}' from database"):
                with sqlite3.connect(db_path) as conn:
                    conn.execute(
                        "DELETE FROM my_table WHERE source_file = ?", (file_to_delete,)
                    )
                st.sidebar.success(f"'{file_to_delete}' deleted.")
                st.rerun()
    except (sqlite3.DatabaseError, pd.errors.DatabaseError):
        st.sidebar.info("No data to delete yet.")

else:
    st.sidebar.warning("No database found. It will be created on first import.")
    st.sidebar.write(f"**Path:** {db_path}")

# ─────────────────────────────────────────
# SECTION 2 — Import File
# ─────────────────────────────────────────
st.header("2. Import File")

with st.form("import_form"):

    uploaded_file = st.file_uploader(
        "Choose an Excel file",
        type=["xlsx", "xls"]
    )

    submit_import = st.form_submit_button("Import File")

    if submit_import and not uploaded_file:
        st.warning("Choose an Excel file before importing.")

    if submit_import and uploaded_file:
        conn = None
        try:
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            conn = sqlite3.connect(db_path)
            # Check if file already imported
            try:
                existing = pd.read_sql(
                    "SELECT COUNT(*) AS cnt FROM my_table WHERE source_file = ?",
                    conn,
                    params=(uploaded_file.name,),
                )
                already_imported = existing.iloc[0]["cnt"] > 0
            except (sqlite3.DatabaseError, pd.errors.DatabaseError):
                # The table does not exist before the first import.
                already_imported = False

            if already_imported:
                st.warning(f"File '{uploaded_file.name}' has already been imported.")
            else:
                df = pd.read_excel(
                    uploaded_file,
                    sheet_name="Query",
                    header=1,
                    usecols="A:U",
                )
                df["source_file"] = uploaded_file.name
                df.to_sql(
                    name="my_table",
                    con=conn,
                    if_exists="append",
                    index=False,
                )
                conn.commit()
                st.success(f"Done! {len(df)} rows saved from {uploaded_file.name}")
        except (
            ImportError,
            KeyError,
            OSError,
            TypeError,
            ValueError,
            sqlite3.DatabaseError,
            pd.errors.DatabaseError,
        ) as error:
            st.error(f"The file could not be imported: {error}")
        finally:
            if conn is not None:
                conn.close()


# ─────────────────────────────────────────
# SECTION 3 — DB Viewer
# ─────────────────────────────────────────
st.header("3. Current Database Viewer")
active_filter = " ".join(
    value.strip().upper() for value in (shared_filter, device_filter) if value.strip()
)
st.write(f"Active filter: **{active_filter or 'None (showing all)'}**")

if os.path.exists(db_path):
    try:
        with sqlite3.connect(db_path) as conn:
            full_df = pd.read_sql("SELECT * FROM my_table", conn)

        if not full_df.empty:
            # Selection of extra column by user, default column 1 (second)
            selected_column = st.selectbox(
                "Extra Column",
                full_df.columns,
                index=1
            )

            first_col = full_df.columns[0]

            viewed_df = filter_rows(full_df, shared_filter, device_filter)

            display_columns = list(
                dict.fromkeys([first_col, "source_file", selected_column])
            )
            st.dataframe(viewed_df[display_columns])
            st.write(f"**Rows shown:** {len(viewed_df)}")
        else:
            st.info("No data in database yet.")
    except (KeyError, sqlite3.DatabaseError, pd.errors.DatabaseError):
        st.info("No data in database yet.")
