import pandas as pd
import sqlite3
import streamlit as st
import os
from io import BytesIO

db_path = r"D:\your_database.db"

st.title("VEL Import Tool")

# ─────────────────────────────────────────
# SHARED FILTER — drives sections 2, 3, 4
# ─────────────────────────────────────────
st.sidebar.header("Filter Settings")
shared_filter = st.sidebar.text_input("KKS Filter by letters at position 3 (e.g. CHA)", value="CHA")
device_filter = st.sidebar.text_input("KKS Filter by letters at position device (e.g. -M01)", value="-M01")

# ─────────────────────────────────────────
# SECTION 1 — Database Status
# ─────────────────────────────────────────
st.sidebar.header("1. Database Status")

if os.path.exists(db_path):
    st.sidebar.success("Database found")
    st.sidebar.write(f"**Path:** {db_path}")
    st.sidebar.write(f"**File:** {os.path.basename(db_path)}")

    conn = sqlite3.connect(db_path)
    try:
        imported_files = pd.read_sql("SELECT DISTINCT source_file FROM my_table", conn)
        st.sidebar.write("**Imported files:**")
        st.sidebar.dataframe(imported_files)
    except:
        st.sidebar.warning("Database exists but no data imported yet.")
    conn.close()

    # --- Delete an imported file from DB ---
    st.sidebar.subheader("Delete imported file from DB")
    conn = sqlite3.connect(db_path)
    try:
        imported_files_list = pd.read_sql("SELECT DISTINCT source_file FROM my_table", conn)["source_file"].tolist()
        file_to_delete = st.sidebar.selectbox("Select file to delete", options=["-- Select --"] + imported_files_list)

        if file_to_delete != "-- Select --":
            if st.sidebar.button(f"Delete '{file_to_delete}' from database"):
                conn2 = sqlite3.connect(db_path)
                conn2.execute("DELETE FROM my_table WHERE source_file = ?", (file_to_delete,))
                conn2.commit()
                conn2.close()
                st.sidebar.success(f"'{file_to_delete}' deleted. Please refresh.")
    except:
        st.sidebar.info("No data to delete yet.")
    conn.close()

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

    if submit_import and uploaded_file:

        conn = sqlite3.connect(db_path)

        try:
            # Check if file already imported
            existing = pd.read_sql(
                "SELECT COUNT(*) AS cnt FROM my_table WHERE source_file = ?",
                conn,
                params=(uploaded_file.name,)
            )

            already_imported = existing.iloc[0]["cnt"] > 0

        except Exception:
            # Table doesn't exist yet
            already_imported = False

        if already_imported:

            st.warning(
                f"File '{uploaded_file.name}' has already been imported."
            )

        else:

            df = pd.read_excel(
                uploaded_file,
                sheet_name="Query",
                header=1,
                usecols="A:U"
            )

            df["source_file"] = uploaded_file.name

            df.to_sql(
                name="my_table",
                con=conn,
                if_exists="append",
                index=False
            )

            st.success(
                f"Done! {len(df)} rows saved from {uploaded_file.name}"
            )

        conn.close()

        #st.rerun()


# ─────────────────────────────────────────
# SECTION 3 — DB Viewer
# ─────────────────────────────────────────
st.header("3. Current Database Viewer")
st.write(f"Active filter: **{shared_filter.upper() + device_filter.upper() if shared_filter else 'None (showing all)'}**")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    try:
        full_df = pd.read_sql("SELECT * FROM my_table", conn)

        if not full_df.empty:
            
            #Selection of extra column by user, default column 1 (second)
            selected_column = st.selectbox(
                "Extra Column",
                full_df.columns,
                index=1
            )

            first_col = full_df.columns[0]

            # Apply shared filter
            if shared_filter:
                viewed_df = full_df[full_df.iloc[:, 0].astype(str).str[2:2+len(shared_filter)] == shared_filter.upper()]
            else:
                viewed_df = full_df.copy()

            st.dataframe(viewed_df[[first_col, "source_file", selected_column]])
            st.write(f"**Rows shown:** {len(viewed_df)}")
        else:
            st.info("No data in database yet.")
    except:
        st.info("No data in database yet.")
    conn.close()

