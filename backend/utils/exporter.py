# backend/utils/exporter.py
import pandas as pd
import io
from fastapi.responses import StreamingResponse
from datetime import datetime, date

def generate_csv_export(query_data, column_mappings: dict, filename_prefix: str):
    """
    Universal reusable function to export any database model dataset or dictionary matrix.
    Safely handles both SQLAlchemy object properties and direct dictionary keys.
    """
    extracted_rows = []
    
    for record in query_data:
        row = {}
        for db_field, csv_header in column_mappings.items():
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
                
            row[csv_header] = value
        extracted_rows.append(row)
        
    # Convert matrix list directly into a Pandas DataFrame
    df = pd.DataFrame(extracted_rows)
    
    csv_data = df.to_csv(index=False)
    output = io.BytesIO(csv_data.encode('utf-8'))
    
    # Format a secure timestamp string for the file wrapper name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    headers = {
        'Content-Disposition': f'attachment; filename="{filename_prefix}_{timestamp}.csv"',
        'Cache-Control': 'no-cache'
    }
    
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers=headers
    )