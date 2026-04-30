# Excel .xlsx/.xls parser
def parse_excel(path: str):
    import pandas as pd, openpyxl
    # Try to detect header row (skip blank leading rows)
    xl = pd.ExcelFile(path)
    sheet = xl.sheet_names[0]
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    # Find first non-empty row
    header_row = 0
    for i, row in raw.iterrows():
        if row.notna().sum() >= 2:
            header_row = i
            break
    df = pd.read_excel(path, sheet_name=sheet, header=header_row)
    df.dropna(how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)
    return df, {"source": "excel", "value_labels": {}, "column_labels": {}, "measurement_levels": {}}
