from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode


def show_aggrid(df, height=400, fit_columns=True):
    """Render a DataFrame as an AgGrid table with auto-sized columns."""
    if df is None or df.empty:
        return
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, minWidth=60)
    gb.configure_grid_options(domLayout="autoHeight")
    grid_options = gb.build()
    AgGrid(
        df,
        gridOptions=grid_options,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        theme="streamlit",
        height=height,
        use_container_width=True,
    )
