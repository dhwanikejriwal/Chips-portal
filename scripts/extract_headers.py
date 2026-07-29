import pandas as pd
import json
import numpy as np

f = 'sample reports/District wise kit count chips.xlsx'
try:
    df = pd.read_excel(f)
    result = {
        'columns': df.columns.tolist(),
        'row1': df.iloc[0].replace({np.nan: None}).to_dict() if len(df) > 0 else None,
        'row2': df.iloc[1].replace({np.nan: None}).to_dict() if len(df) > 1 else None
    }
except Exception as e:
    result = {'error': str(e)}
        
print(json.dumps(result, indent=2, default=str))
