from backend.database import engine
from backend.models.base import Base
import importlib
import pkgutil
import backend.models

for module_info in pkgutil.walk_packages(backend.models.__path__, backend.models.__name__ + '.'):
    importlib.import_module(module_info.name)

metadata = Base.metadata
mermaid = ['erDiagram']

for table_name, table in metadata.tables.items():
    mermaid.append(f'    {table_name} {{')
    for column in table.columns:
        pk = ' PK' if column.primary_key else ''
        fk = ' FK' if column.foreign_keys else ''
        type_name = str(column.type).split('(')[0].split(' ')[0].lower()
        mermaid.append(f'        {type_name} {column.name}{pk}{fk}')
    mermaid.append('    }')

for table_name, table in metadata.tables.items():
    for column in table.columns:
        for fk in column.foreign_keys:
            target_table = fk.column.table.name
            mermaid.append(f'    {target_table} ||--o{{ {table_name} : \"{column.name}\"')

import re

erd_text = '\\n'.join(mermaid)

with open('database_schema_erd_v6.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Use regex to replace the content between "const diagram = `erDiagram" and "`;"
new_html = re.sub(r'const diagram = `erDiagram[\s\S]*?`;', f'const diagram = `{erd_text}`;', html)

with open('database_schema_erd_v6.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

