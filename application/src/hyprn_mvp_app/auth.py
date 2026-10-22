"""Local owner provisioning, scrypt passwords and revocable opaque sessions.

Agent credentials: a delegated agent API session (15 minutes, cookie and cross-site request
values returned once, hashes stored) for the embedded Assistant. Session credentials
never leave the application or enter logs.
"""
import argparse
import getpass
import hashlib
import hmac
import secrets
import time
from .contracts import DomainError, uid
from .store import AGENT_WRITE_EFFECTS, Store

AGENT_SESSION_SECONDS=15*60

def token_hash(token):return hashlib.sha256(token.encode()).hexdigest()

def password_hash(password,salt=None):
    if not 16<=len(password)<=1024:raise DomainError("invalid_request",400)
    salt=salt or secrets.token_hex(16)
    value=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=2**17,r=8,p=1,maxmem=256*1024*1024).hex()
    return "scrypt$"+salt+"$"+value

class Auth:
    def __init__(self,store,origin):
        self.store,self.origin=store,origin

    def provision(self,username,password):
        if not username or len(username)>128:raise DomainError("invalid_request",400)
        hashed=password_hash(password)
        with self.store.connection(write=True) as db:
            if db.execute("SELECT 1 FROM users").fetchone():raise DomainError("reference_conflict")
            actor=uid()
            db.execute("INSERT INTO users(actor_id,username,password_hash) VALUES(?,?,?)",(actor,username,hashed))
            return actor

    def recover(self,password):
        # Local administrative operation only; deliberately has no HTTP route.
        hashed=password_hash(password)
        with self.store.connection(write=True) as db:
            if not db.execute("SELECT 1 FROM users").fetchone():raise DomainError("resource_not_found",404)
            db.execute("UPDATE users SET password_hash=?,failures=0,locked_until=0",(hashed,))
            db.execute("DELETE FROM sessions")
            # Recovery also ends every agent delegation and agent API session.
            self.store.revoke_all_agent_credentials(db,"owner_recovery")

    def login(self,username,password):
        failure=None
        with self.store.connection(write=True) as db:
            row=db.execute("SELECT * FROM users WHERE username=?",(username,)).fetchone()
            if row and row["locked_until"]>time.time():raise DomainError("rate_limited",429)
            stored=row["password_hash"] if row else "scrypt$"+"00"*16+"$"+"00"*64
            try:valid=hmac.compare_digest(stored,password_hash(password,stored.split("$")[1]))
            except DomainError:valid=False
            if not row or not valid:
                if row:
                    count=row["failures"]+1
                    db.execute("UPDATE users SET failures=?,locked_until=? WHERE actor_id=?",
                               (count,time.time()+60 if count>=5 else 0,row["actor_id"]))
                failure=DomainError("unauthenticated",401)
            else:
                token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
                expires=time.time()+8*60*60
                db.execute("UPDATE users SET failures=0,locked_until=0 WHERE actor_id=?",(row["actor_id"],))
                db.execute("INSERT INTO sessions VALUES(?,?,?,?)",
                           (token_hash(token),row["actor_id"],token_hash(csrf),expires))
                result=dict(token=token,csrf_token=csrf,actor_id=row["actor_id"],expires_at=expires)
        if failure:raise failure
        return result

    def authenticate(self,token):
        """The session of cookie value ``token``: ``kind`` (``user`` or ``agent``),
        ``actor_id``, ``csrf_hash``, ``expires_at``, ``delegation_id``, ``study_id``,
        ``effects`` and ``read_only``. An agent session is valid only while its delegation is
        live."""
        if not isinstance(token,str) or not token or len(token)>256:raise DomainError("unauthenticated",401)
        now=time.time()
        with self.store.authentication_connection() as db:
            row=db.execute("SELECT actor_id,csrf_hash,expires_at FROM sessions WHERE token_hash=? AND expires_at>?",
                           (token_hash(token),now)).fetchone()
            if row is not None:
                return dict(row,kind="user",delegation_id=None,study_id=None,effects=None,read_only=False)
            row=db.execute("SELECT actor_id,csrf_hash,expires_at,delegation_id,read_only FROM agent_api_sessions "
                           "WHERE token_hash=? AND expires_at>?",(token_hash(token),now)).fetchone()
            delegation=self.store.live_delegation(db,row["delegation_id"]) if row else None
            if delegation is None or delegation["agent_actor_id"]!=row["actor_id"]:
                raise DomainError("unauthenticated",401)
            return dict(row,kind="agent",study_id=delegation["study_id"],effects=delegation["effects"],
                        read_only=bool(row["read_only"]))

    def mint_agent_session(self,delegation_id):
        """A 15-minute API session for the agent actor of live delegation ``delegation_id``.

        Returns the cookie (``token``) and cross-site request (``csrf_token``) values once,
        for the in-process caller only; only their hashes are stored. The session is read-only
        unless the delegation holds a write effect."""
        token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        with self.store.connection(write=True) as db:
            delegation=self.store.live_delegation(db,delegation_id) if isinstance(delegation_id,str) else None
            if delegation is None:raise DomainError("unauthenticated",401)
            read_only=not (delegation["effects"]&AGENT_WRITE_EFFECTS and delegation["role_ceiling"]=="writer")
            expires=min(time.time()+AGENT_SESSION_SECONDS,delegation["expires_at"])
            db.execute("INSERT INTO agent_api_sessions VALUES(?,?,?,?,?,?)",
                       (token_hash(token),token_hash(csrf),delegation_id,delegation["agent_actor_id"],int(read_only),expires))
        return dict(token=token,csrf_token=csrf,actor_id=delegation["agent_actor_id"],delegation_id=delegation_id,
                    study_id=delegation["study_id"],read_only=read_only,expires_at=expires)

    def revoke_delegation(self,delegation_id,reason="revoked"):
        """End delegation ``delegation_id`` with its agent API sessions; the
        agent's next call is refused. Returns whether it was live."""
        with self.store.connection(write=True) as db:
            return self.store.revoke_delegation(db,delegation_id,reason)

    def authorize_origin(self,origin):
        if origin!=self.origin:raise DomainError("forbidden",403)

    def authorize_mutation(self,token,origin,csrf):
        self.authorize_origin(origin)
        session=self.authenticate(token)
        if not csrf or not hmac.compare_digest(session["csrf_hash"],token_hash(csrf)):
            raise DomainError("forbidden",403)
        return session

    def logout(self,token):
        with self.store.connection(write=True) as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?",(token_hash(token),))

def main():
    parser=argparse.ArgumentParser(description="Local owner provisioning/recovery; never prints passwords")
    parser.add_argument("action",choices=["provision","recover"])
    parser.add_argument("--store",required=True)
    parser.add_argument("--username",default="owner")
    args=parser.parse_args()
    password=getpass.getpass("New owner password (16+ characters): ")
    if password!=getpass.getpass("Confirm password: "):raise SystemExit("Passwords differ")
    auth=Auth(Store(args.store),"")
    if args.action=="provision":auth.provision(args.username,password)
    else:auth.recover(password)
    print("Owner credentials saved; recovery revokes all previous sessions.")

if __name__=="__main__":main()
