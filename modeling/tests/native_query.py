"""Read synthetic SQLite inside its Linux container, never through host SQLite.

Cross-OS access to a live SQLite WAL/SHM on a Docker bind mount is not a valid
concurrency test and can corrupt shared-memory assumptions.
"""
import json,os,subprocess
STORE='/store/model.sqlite3'
def container():
    # The disposable private service of this test scope, named explicitly; never a live service.
    name=os.environ['HYPRN_MVP_MODEL_CONTAINER']
    assert name.startswith('hyprn-mvp-test-'),name
    return name
def ruby(code,payload=None):
    r=subprocess.run(['docker','exec','-i','-w','/native',container(),'bundle','exec','ruby','-rjson','-rsqlite3','-e',code],
                     input=json.dumps(payload),text=True,capture_output=True,check=True)
    return json.loads(r.stdout.strip().splitlines()[-1])
def query(sql,params=()):
    code='q,p=JSON.parse(STDIN.read);db=SQLite3::Database.new("'+STORE+'",readonly:true);puts JSON.generate(db.execute(q,p));db.close'
    return ruby(code,[sql,list(params)])
class Cursor:
    def __init__(self,rows):self.rows=rows
    def fetchone(self):return self.rows[0] if self.rows else None
    def fetchall(self):return self.rows
    def __iter__(self):return iter(self.rows)
class native_connection:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql,params=()):return Cursor(query(sql,params))
def snapshot(domain_only=False):
    code=('db=SQLite3::Database.new("'+STORE+'",readonly:true);'
          'tables=db.execute("select name from sqlite_master where type=\'table\' order by name").map(&:first);'
          'puts JSON.generate(tables.to_h { |t| [t,db.execute(\'select * from "\'+t+\'" order by rowid\')] });db.close')
    data=ruby(code)
    return {t:v for t,v in data.items() if not (domain_only and t in ('modeling_commands','sqlite_sequence'))}
