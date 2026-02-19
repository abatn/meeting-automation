import logging
from typing import List, Dict, Any
import pandas as pd
import os

logger = logging.getLogger(__name__)

async def generate_excel_from_data(data: List[Dict[str, Any]], filename: str) -> str:
    """
    Generates an Excel file from a list of dictionaries.
    """
    logger.info(f"Generating Excel report: {filename}")

    output_dir = "temp_reports"
    os.makedirs(output_dir, exist_ok=True)
    excel_path = os.path.join(output_dir, filename)

    if not data:
        logger.warning(f"No data provided for Excel report {filename}. Creating an empty Excel file.")
        df = pd.DataFrame()
    else:
        df = pd.DataFrame(data)
        # Basic formatting for datetime objects
        for col in df.columns:
            if df[col].dtype == 'object' and df[col].apply(lambda x: isinstance(x, str) and 'T' in x and '-' in x and ':' in x).any():
                try:
                    df[col] = pd.to_datetime(df[col])
                except Exception:
                    pass # Keep as string if conversion fails

    # Write to Excel
    writer = pd.ExcelWriter(excel_path, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='Report Data', index=False)

    # Optional: Auto-fit columns
    worksheet = writer.sheets['Report Data']
    for i, col in enumerate(df.columns):
        max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
        worksheet.set_column(i, i, max_len)

    writer.close()
    logger.info(f"Excel report saved to {excel_path}")
    return excel_path