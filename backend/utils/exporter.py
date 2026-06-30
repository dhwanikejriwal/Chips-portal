# backend/utils/exporter.py
import pandas as pd
import io
from fastapi.responses import StreamingResponse
from datetime import datetime, date

def generate_excel_export(query_data, column_mappings: dict, filename_prefix: str):
    """
    Universal reusable function to export any database model dataset or dictionary matrix.
    Safely handles both SQLAlchemy object properties and direct dictionary keys.
    """
    extracted_rows = []
    
    for record in query_data:
        row = {}
        for db_field, excel_header in column_mappings.items():
            value = None
            
            # 🛡️ SAFE EXTRACTION MATRIX: Check dictionary keys first, then object attributes
            if isinstance(record, dict):
                if db_field in record:
                    value = record[db_field]
            elif hasattr(record, db_field):
                value = getattr(record, db_field, None)
            
            # Format timestamps and dates cleanly for spreadsheets
            if isinstance(value, (datetime, date)):
                value = value.strftime("%Y-%m-%d %H:%M:%S")
            elif value is None:
                value = "—"
                
            row[excel_header] = value
        extracted_rows.append(row)
        
    # Convert matrix list directly into a Pandas DataFrame
    df = pd.DataFrame(extracted_rows)
    
    # Write the spreadsheet binary output directly into an in-memory byte buffer
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Exported Log")
        
        # UI Polish: Auto-adjust excel column widths based on longest character string length
        worksheet = writer.sheets["Exported Log"]
        for col in worksheet.columns:
            # Safely stringify contents to evaluate character lengths
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = max(max_len + 3, 11)

    output.seek(0)
    
    # Format a secure timestamp string for the file wrapper name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = {
        'Content-Disposition': f'attachment; filename="{filename_prefix}_{timestamp}.xlsx"',
        'Cache-Control': 'no-cache'
    }
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )