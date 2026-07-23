import pandas as pd
import numpy as np

df = pd.DataFrame({
    'A': [1.0, 2.5, np.nan, 4.0],
    'B': ['text', 'more', np.nan, 'text']
})

html = df.to_html(na_rep='', float_format='{:.0f}'.format)
print(html)
