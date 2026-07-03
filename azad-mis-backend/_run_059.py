import sys
sys.path.insert(0, '/home/kedar/azad-mis-backend')
from database import get_cursor
with get_cursor() as cur:
    with open('/home/kedar/azad-mis-backend/sql/059_mobiliser_sangini_roles.sql') as f:
        sql = f.read()
    cur.execute(sql)
    cur.execute("SELECT id, name FROM mis_azad.roles ORDER BY id")
    print('All roles after migration:')
    for r in cur.fetchall():
        print(' ', r['id'], '|', r['name'])
print('migration OK')
