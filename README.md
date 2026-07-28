# Cross-Project Equipment Dashboard

The Streamlit app turns imported equipment registers into a portfolio view. Each
Excel source file is treated as a project by default, although any database column
can be selected as the project dimension.

## Business metrics and recommended KPIs

| KPI | Definition | Business use |
| --- | --- | --- |
| Projects in scope | Distinct projects after filters | Confirms the comparison population |
| Unique equipment | Distinct, nonblank equipment identifiers | Measures portfolio breadth |
| Shared equipment | Equipment appearing in more than one project | Finds standardization candidates |
| Project-specific equipment | Equipment appearing in exactly one project | Highlights exceptions and specialist needs |
| Equipment reuse rate | Shared equipment / all unique equipment × 100 | Tracks portfolio standardization |
| Portfolio coverage | Projects using an item / projects in scope × 100 | Compares reuse intensity between items |
| Heavily reused equipment | Equipment used in at least the selected number of projects | Prioritizes framework agreements, spares, and standards |

## Processing logic

1. Load the imported rows from SQLite and apply optional KKS/equipment filters.
2. Select the equipment identifier and project columns. `source_file` is the
   default project dimension.
3. Trim values, remove blanks, and deduplicate equipment–project pairs so repeated
   register lines do not inflate reuse.
4. Group by equipment and count distinct projects.
5. Classify a count of one as **Project-specific** and a count above one as
   **Shared**. Calculate portfolio coverage against all filtered projects.
6. Apply the user-controlled heavy-reuse threshold and rebuild every KPI,
   visualization, table, and export from the same filtered population.

## Streamlit layout and visualizations

- **Sidebar:** data-field mapping, KKS filters, and heavy-reuse threshold.
- **KPI strip:** five headline portfolio measures.
- **Portfolio overview:** shared/specific comparison, project footprints, and a
  distribution of the number of projects using each item.
- **Reuse leaders:** ranked, threshold-aware table with portfolio coverage bars.
- **Project matrix:** boolean equipment-by-project coverage table and CSV export.
- **Records:** auditable filtered source data.
- **Import panel:** collapsible Excel upload and database cleanup controls.

Run the dashboard with:

```bash
streamlit run Import.py
```
