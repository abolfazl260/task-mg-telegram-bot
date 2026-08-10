from services.database import sync_all,sync_one,sync_execute

def init_teams():
 from services.user_service import init_users
 init_users()
def read_teams(): return sync_all('teams')
def write_teams(rows):
 for r in rows: sync_execute('UPDATE teams SET name=?,owner_id=?,editor_code=?,viewer_code=?,created_at=? WHERE team_id=?',(r.get('name',''),str(r.get('owner_id','')),r.get('editor_code',''),r.get('viewer_code',''),r.get('created_at',''),r.get('team_id')))
def append_team(r): sync_execute('INSERT INTO teams(team_id,name,owner_id,editor_code,viewer_code,created_at) VALUES(?,?,?,?,?,?)',(r['team_id'],r.get('name',''),str(r.get('owner_id','')),r.get('editor_code',''),r.get('viewer_code',''),r.get('created_at','')))
def read_members(): return sync_all('team_members')
def write_members(rows):
 for r in rows: append_member(r)
def append_member(r):
 old=sync_one('team_members','team_id=? AND user_id=?',(r.get('team_id'),str(r.get('user_id'))))
 if old: sync_execute('UPDATE team_members SET role=?,display_name=?,username=?,joined_at=? WHERE team_id=? AND user_id=?',(r.get('role','viewer'),r.get('display_name',''),r.get('username',''),r.get('joined_at',''),r.get('team_id'),str(r.get('user_id'))))
 else: sync_execute('INSERT INTO team_members(team_id,user_id,role,display_name,username,joined_at) VALUES(?,?,?,?,?,?)',(r.get('team_id'),str(r.get('user_id')),r.get('role','viewer'),r.get('display_name',''),r.get('username',''),r.get('joined_at','')))
