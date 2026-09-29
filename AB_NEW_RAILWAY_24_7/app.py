import base64
import os,secrets,string,json,random
from datetime import datetime
from functools import wraps
from flask import Flask,render_template,request,redirect,url_for,session,jsonify,abort,Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from flask_socketio import SocketIO,emit,join_room
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps

app=Flask(__name__); app.config['SECRET_KEY']=os.getenv('SECRET_KEY','ab-new-local-secret-change-later')
DATA_DIR=os.environ.get('AB_DATA_DIR','')
if DATA_DIR:
 os.makedirs(DATA_DIR,exist_ok=True)
 DB_PATH=os.path.join(DATA_DIR,'ab_new.db')
else:
 DB_PATH=os.path.join(os.path.dirname(os.path.abspath(__file__)),'ab_new.db')
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///'+DB_PATH; app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
db=SQLAlchemy(app); socketio=SocketIO(app,cors_allowed_origins='*',async_mode='threading')
RANKS=['المالك','كبار الشخصيات','النخبة','العبيد']

def now(): return datetime.now()
class User(db.Model):
 id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(40),unique=True,nullable=False); display_name=db.Column(db.String(60),nullable=False); password_hash=db.Column(db.String(255),nullable=False); rank=db.Column(db.String(40),default='العبيد'); points=db.Column(db.Integer,default=0); is_owner=db.Column(db.Boolean,default=False); is_muted=db.Column(db.Boolean,default=False); is_banned=db.Column(db.Boolean,default=False); created_at=db.Column(db.DateTime,default=now); avatar=db.Column(db.String(40),default='avatar1'); premium_avatar=db.Column(db.Boolean,default=False); bio=db.Column(db.String(140),default='')
class Invite(db.Model):
 id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(64),unique=True,nullable=False); active=db.Column(db.Boolean,default=True); max_uses=db.Column(db.Integer,default=1); uses=db.Column(db.Integer,default=0)
class SlaveMessage(db.Model):
 id=db.Column(db.Integer,primary_key=True)
 user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False,index=True)
 body=db.Column(db.String(1000),nullable=False)
 created_at=db.Column(db.DateTime,default=now,index=True)
 user=db.relationship('User')

class Message(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),nullable=False); body=db.Column(db.String(1000),nullable=False); created_at=db.Column(db.DateTime,default=now); user=db.relationship('User')
class AutoReply(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,db.ForeignKey('user.id'),unique=True,nullable=False); text=db.Column(db.String(500),nullable=False); active=db.Column(db.Boolean,default=True); trigger=db.Column(db.String(30),default='any'); keyword=db.Column(db.String(120),default='')
class Audit(db.Model):
 id=db.Column(db.Integer,primary_key=True); text=db.Column(db.String(500)); created_at=db.Column(db.DateTime,default=now)
class Game(db.Model):
 id=db.Column(db.Integer,primary_key=True); x_user_id=db.Column(db.Integer,nullable=False); o_user_id=db.Column(db.Integer,nullable=False); board=db.Column(db.String(9),default='---------'); turn=db.Column(db.String(1),default='X'); status=db.Column(db.String(20),default='pending'); winner_id=db.Column(db.Integer)
class PrivateMessage(db.Model):
 id=db.Column(db.Integer,primary_key=True); from_user_id=db.Column(db.Integer,nullable=True); to_user_id=db.Column(db.Integer,nullable=False); body=db.Column(db.String(1000),nullable=False); system=db.Column(db.Boolean,default=False); created_at=db.Column(db.DateTime,default=now)
class TableGame(db.Model):
 id=db.Column(db.Integer,primary_key=True); kind=db.Column(db.String(20),nullable=False); host_id=db.Column(db.Integer,nullable=False); player_ids=db.Column(db.String(100),default=''); max_players=db.Column(db.Integer,default=2); status=db.Column(db.String(20),default='lobby'); state=db.Column(db.Text,default='{}'); winner_id=db.Column(db.Integer); created_at=db.Column(db.DateTime,default=now)
class Quiz(db.Model):
 id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(8),unique=True,nullable=False); title=db.Column(db.String(100),nullable=False); host_id=db.Column(db.Integer,nullable=False); status=db.Column(db.String(20),default='lobby'); current_index=db.Column(db.Integer,default=0); question_started_at=db.Column(db.DateTime); time_limit=db.Column(db.Integer,default=30); created_at=db.Column(db.DateTime,default=now)
class Question(db.Model):
 id=db.Column(db.Integer,primary_key=True); quiz_id=db.Column(db.Integer,db.ForeignKey('quiz.id'),nullable=False); text=db.Column(db.String(300),nullable=False); a=db.Column(db.String(150),nullable=False); b=db.Column(db.String(150),nullable=False); c=db.Column(db.String(150),nullable=False); d=db.Column(db.String(150),nullable=False); correct=db.Column(db.String(1),nullable=False)
class QuizPlayer(db.Model):
 id=db.Column(db.Integer,primary_key=True); quiz_id=db.Column(db.Integer,nullable=False); user_id=db.Column(db.Integer,nullable=False); score=db.Column(db.Integer,default=0); unique=db.UniqueConstraint('quiz_id','user_id')

class StoreProduct(db.Model):
 id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(100),nullable=False); price=db.Column(db.Integer,default=0); kind=db.Column(db.String(30),default='badge'); image=db.Column(db.String(255),nullable=False); active=db.Column(db.Boolean,default=True); created_at=db.Column(db.DateTime,default=now)
class Purchase(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,nullable=False); product_id=db.Column(db.Integer,nullable=False); active=db.Column(db.Boolean,default=False); price_paid=db.Column(db.Integer,default=0); created_at=db.Column(db.DateTime,default=now); unique=db.UniqueConstraint('user_id','product_id')
class PointRequest(db.Model):
 id=db.Column(db.Integer,primary_key=True); user_id=db.Column(db.Integer,nullable=False); amount=db.Column(db.Integer,nullable=False); note=db.Column(db.String(300),default=''); status=db.Column(db.String(20),default='pending'); created_at=db.Column(db.DateTime,default=now)

class Answer(db.Model):
 id=db.Column(db.Integer,primary_key=True); quiz_id=db.Column(db.Integer,nullable=False); question_id=db.Column(db.Integer,nullable=False); user_id=db.Column(db.Integer,nullable=False); choice=db.Column(db.String(1)); correct=db.Column(db.Boolean,default=False); unique=db.UniqueConstraint('question_id','user_id')

def me():
 uid=session.get('uid'); return db.session.get(User,uid) if uid else None
def login_required(f):
 @wraps(f)
 def w(*a,**k):
  u=me()
  if not u or u.is_banned: session.clear(); return redirect(url_for('login'))
  return f(*a,**k)
 return w
def owner_required(f):
 @wraps(f)
 def w(*a,**k):
  u=me()
  if not u or not u.is_owner: abort(403)
  return f(*a,**k)
 return w
def log(t): db.session.add(Audit(text=t))
def roomcode():
 while True:
  c=''.join(secrets.choice(string.ascii_uppercase+string.digits) for _ in range(6))
  if not Quiz.query.filter_by(code=c).first(): return c

def equipped_product(u,kind):
 row=(db.session.query(Purchase,StoreProduct)
      .join(StoreProduct,Purchase.product_id==StoreProduct.id)
      .filter(Purchase.user_id==u.id,Purchase.active==True,StoreProduct.kind==kind).first())
 return row[1] if row else None

def appearance(u):
 av=equipped_product(u,'avatar'); title=equipped_product(u,'title')
 crown=equipped_product(u,'badge') or equipped_product(u,'crown'); frame=equipped_product(u,'frame')
 return {'avatar': av.image if av else f"/static/img/{u.avatar or 'avatar1'}.svg",
         'title': title.name if title else '', 'crown': crown.image if crown else '',
         'frame': frame.image if frame else ''}

def avatar_url(u): return appearance(u)['avatar']
def shown_name(u):
 a=appearance(u); return f"{u.display_name} ({a['title']})" if a['title'] else u.display_name
def push_system_message(text):
 owner=User.query.filter_by(is_owner=True).first()
 if not owner:return
 m=Message(user_id=owner.id,body=text);db.session.add(m);db.session.commit();socketio.emit('new_message',{'id':m.id,'user_id':owner.id,'name':'اب نيو','username':'system','rank':'النظام','body':text,'time':m.created_at.strftime('%H:%M'),'owner':True,'avatar':'/static/img/logo.svg'})
@socketio.on('connect')
def sock_connect():
 u=me()
 if u: join_room(f'user:{u.id}')
@socketio.on('join_game')
def sock_join_game(data):
 u=me(); gid=int(data.get('game_id',0)) if data else 0
 g=db.session.get(Game,gid)
 if u and g and u.id in (g.x_user_id,g.o_user_id): join_room(f'game:{gid}')

def save_store_image(file_storage, kind):
    """Owner can upload PNG/JPG/WEBP; normalize profile assets automatically."""
    if not file_storage or not file_storage.filename: return ""
    raw=Image.open(file_storage.stream).convert("RGBA")
    if kind in ("avatar","frame","badge","crown"):
        raw=ImageOps.contain(raw,(1024,1024))
        canvas=Image.new("RGBA",(1024,1024),(0,0,0,0))
        canvas.alpha_composite(raw,((1024-raw.width)//2,(1024-raw.height)//2)); raw=canvas
    else: raw.thumbnail((1400,1400),Image.Resampling.LANCZOS)
    name=secrets.token_hex(12)+".webp"
    out=os.path.join(app.root_path,"static","uploads",name); os.makedirs(os.path.dirname(out),exist_ok=True)
    raw.save(out,"WEBP",quality=94,method=6)
    return "/static/uploads/"+name

def make_full_backup():
    payload={"format":"ab-new-backup-v2","created_at":datetime.utcnow().isoformat()+"Z","tables":{},"assets":{}}
    ins=inspect(db.engine)
    for table in ins.get_table_names():
        rows=db.session.execute(db.text(f'SELECT * FROM "{table}"')).mappings().all()
        clean=[]
        for row in rows:
            d={}
            for k,v in dict(row).items():
                if isinstance(v,(bytes,bytearray)): v=base64.b64encode(v).decode()
                elif hasattr(v,"isoformat"): v=v.isoformat()
                d[k]=v
            clean.append(d)
        payload["tables"][table]=clean
    up=os.path.join(app.root_path,"static","uploads")
    if os.path.isdir(up):
        for fn in os.listdir(up):
            fp=os.path.join(up,fn)
            if os.path.isfile(fp):
                with open(fp,"rb") as f: payload["assets"][fn]=base64.b64encode(f.read()).decode()
    return payload

@app.route('/')
def index(): return redirect(url_for('chat') if me() else url_for('login'))
@app.route('/setup',methods=['GET','POST'])
def setup():
 if User.query.filter_by(is_owner=True).first(): return redirect(url_for('login'))
 if request.method=='POST':
  n=request.form['display_name'].strip(); u=request.form['username'].strip().lower(); p=request.form['password']
  if not n or not u or len(p)<4:return render_template('setup.html',error='أكمل البيانات وكلمة المرور 4 أحرف على الأقل')
  x=User(display_name=n,username=u,password_hash=generate_password_hash(p),rank='المالك',is_owner=True); db.session.add(x); db.session.commit(); session['uid']=x.id; return redirect(url_for('chat'))
 return render_template('setup.html')
@app.route('/login',methods=['GET','POST'])
def login():
 if not User.query.filter_by(is_owner=True).first(): return redirect(url_for('setup'))
 if request.method=='POST':
  u=User.query.filter_by(username=request.form['username'].strip().lower()).first()
  if u and not u.is_banned and check_password_hash(u.password_hash,request.form['password']): session['uid']=u.id; return redirect(url_for('chat'))
  return render_template('login.html',error='بيانات الدخول غير صحيحة أو الحساب محظور')
 return render_template('login.html')
@app.route('/join/<code>',methods=['GET','POST'])
def join(code):
 inv=Invite.query.filter_by(code=code,active=True).first()
 if not inv or inv.uses>=inv.max_uses:return render_template('join.html',invalid=True)
 if request.method=='POST':
  un=request.form['username'].strip().lower(); n=request.form['display_name'].strip(); p=request.form['password']
  if User.query.filter_by(username=un).first():return render_template('join.html',error='اسم المستخدم مستخدم',code=code)
  if not un or not n or len(p)<4:return render_template('join.html',error='أكمل البيانات وكلمة المرور 4 أحرف على الأقل',code=code)
  u=User(username=un,display_name=n,password_hash=generate_password_hash(p)); db.session.add(u); inv.uses+=1; inv.active=inv.uses<inv.max_uses; db.session.commit(); session['uid']=u.id; return redirect(url_for('chat'))
 return render_template('join.html',code=code)
@app.route('/logout')
def logout():session.clear();return redirect(url_for('login'))
def slave_group_allowed(u):
 return bool(u and (u.is_owner or str(u.rank or '').strip()=='العبيد'))

@app.route('/slave-group')
@login_required
def slave_group():
 u=me()
 if not slave_group_allowed(u): abort(403)
 msgs=SlaveMessage.query.order_by(SlaveMessage.id.desc()).limit(150).all()[::-1]
 return render_template('slave_group.html',me=u,messages=msgs)

@socketio.on('join_slave_group')
def join_slave_group():
 u=me()
 if not slave_group_allowed(u): return False
 join_room('slave-group')
 emit('slave_group_joined',{'ok':True})

@socketio.on('send_slave_message')
def send_slave_message(data):
 u=me()
 if not slave_group_allowed(u) or u.is_muted or u.is_banned:return False
 body=str((data or {}).get('body','')).strip()[:1000]
 if not body:return False
 m=SlaveMessage(user_id=u.id,body=body);db.session.add(m);db.session.commit()
 emit('new_slave_message',{'id':m.id,'user_id':u.id,'name':shown_name(u),'username':u.username,
 'rank':u.rank,'body':body,'time':m.created_at.strftime('%H:%M'),'owner':u.is_owner,
 'avatar':avatar_url(u)},room='slave-group')
 return True

@app.route('/chat')
@login_required
def chat():
 return render_template('chat.html',me=me(),messages=Message.query.order_by(Message.id.desc()).limit(150).all()[::-1],users=User.query.filter_by(is_banned=False).order_by(User.points.desc()).all(),games=Game.query.filter((Game.x_user_id==me().id)|(Game.o_user_id==me().id)).order_by(Game.id.desc()).limit(10).all(),table_games=TableGame.query.order_by(TableGame.id.desc()).limit(12).all())
@socketio.on('send_message')
def send_message(data):
 u=me()
 if not u or u.is_muted or u.is_banned:return
 body=str(data.get('body','')).strip()[:1000]
 if not body:return
 m=Message(user_id=u.id,body=body);db.session.add(m);db.session.commit();emit('new_message',{'id':m.id,'user_id':u.id,'name':shown_name(u),'username':u.username,'rank':u.rank,'body':body,'time':m.created_at.strftime('%H:%M'),'owner':u.is_owner,'avatar':avatar_url(u)},broadcast=True)
 r=AutoReply.query.filter_by(user_id=u.id,active=True).first()
 if r and (r.trigger=='any' or (r.trigger=='keyword' and r.keyword and r.keyword.lower() in body.lower())):
  reply=f'{u.display_name}، {r.text}'; owner=User.query.filter_by(is_owner=True).first(); am=Message(user_id=owner.id if owner else u.id,body=reply);db.session.add(am);db.session.commit();socketio.emit('new_message',{'id':am.id,'user_id':am.user_id,'name':'اب نيو','username':'system','rank':'النظام','body':reply,'time':am.created_at.strftime('%H:%M'),'owner':True,'avatar':'/static/img/logo.svg'})

@app.post('/api/send-message')
@login_required
def api_send_message():
 u=me()
 if u.is_muted or u.is_banned:return jsonify({'ok':False}),403
 data=request.get_json(silent=True) or {};body=str(data.get('body','')).strip()[:1000]
 if not body:return jsonify({'ok':False}),400
 m=Message(user_id=u.id,body=body);db.session.add(m);db.session.commit()
 payload={'id':m.id,'user_id':u.id,'name':shown_name(u),'rank':u.rank,'body':body,'time':m.created_at.strftime('%H:%M'),'avatar':avatar_url(u)}
 socketio.emit('new_message',payload)
 return jsonify({'ok':True,'message':payload})

@app.get('/api/messages')
@login_required
def api_messages():
 after=request.args.get('after',0,type=int)
 rows=Message.query.filter(Message.id>after).order_by(Message.id).limit(100).all()
 return jsonify([{'id':m.id,'user_id':m.user_id,'name':shown_name(m.user),'rank':m.user.rank,'body':m.body,'time':m.created_at.strftime('%H:%M'),'avatar':avatar_url(m.user)} for m in rows])

@app.get('/api/live')
@login_required
def api_live():
 rows=TableGame.query.filter(TableGame.status.in_(['lobby','active'])).order_by(TableGame.id.desc()).limit(50).all()
 return jsonify({'tables':[{'id':g.id,'kind':g.kind,'label':GAME_META.get(g.kind,(g.kind,'🎮'))[0],
 'icon':GAME_META.get(g.kind,(g.kind,'🎮'))[1],'host':shown_name(db.session.get(User,g.host_id)),
 'status':g.status,'players':len(_ids(g))} for g in rows]})

@app.route('/profile',methods=['GET','POST'])
@login_required
def profile():
 u=me(); avatars=['avatar1','avatar2','avatar3','avatar4','avatar5','avatar6']; premium=['premium1','premium2','premium3']
 if request.method=='POST':
  av=request.form.get('avatar','avatar1'); allowed=avatars+(premium if u.premium_avatar or u.is_owner else [])
  if av in allowed:u.avatar=av
  u.bio=request.form.get('bio','').strip()[:140];db.session.commit();return redirect(url_for('profile'))
 wins=Game.query.filter_by(winner_id=u.id).count()+TableGame.query.filter_by(winner_id=u.id).count()
 return render_template('profile.html',me=u,avatars=avatars,premium=premium,wins=wins)
@app.get('/user/<int:uid>')
@login_required
def public_profile(uid):
 u=db.session.get(User,uid) or abort(404)
 return render_template('public_profile.html',u=u,me=me())
@app.route('/dm/<int:uid>',methods=['GET','POST'])
@login_required
def dm(uid):
 other=db.session.get(User,uid) or abort(404); u=me()
 if request.method=='POST':
  body=request.form.get('body','').strip()[:1000]
  if body:
   pm=PrivateMessage(from_user_id=u.id,to_user_id=other.id,body=body);db.session.add(pm);db.session.commit();socketio.emit('dm_new',{'from_id':u.id,'name':u.display_name,'body':body,'time':pm.created_at.strftime('%H:%M')},room=f'user:{other.id}')
  return redirect(url_for('dm',uid=uid))
 rows=PrivateMessage.query.filter(((PrivateMessage.from_user_id==u.id)&(PrivateMessage.to_user_id==other.id))|((PrivateMessage.from_user_id==other.id)&(PrivateMessage.to_user_id==u.id))|((PrivateMessage.system==True)&(PrivateMessage.to_user_id==u.id))).order_by(PrivateMessage.id).limit(200).all()
 return render_template('dm.html',me=u,other=other,rows=rows)
@app.get('/games')
@login_required
def games_hub():
 return render_template('games.html',me=me(),users=User.query.filter_by(is_banned=False).all())

@app.get('/snake')
@login_required
def snake_game(): return render_template('snake.html',me=me())

@app.get('/speed')
@login_required
def speed_game(): return render_template('speed.html',me=me())

@app.post('/admin/delete-message/<int:mid>')
@owner_required
def delete_message(mid):
 m=db.session.get(Message,mid)
 if m:db.session.delete(m);db.session.commit();socketio.emit('message_deleted',{'id':mid})
 return redirect(url_for('chat'))
@app.route('/admin')
@owner_required
def admin():
 users=User.query.order_by(User.is_owner.desc(),User.id).all(); reps={r.user_id:r for r in AutoReply.query.all()}
 return render_template('admin.html',me=me(),users=users,invites=Invite.query.order_by(Invite.id.desc()).limit(30).all(),replies=reps,ranks=RANKS,audits=Audit.query.order_by(Audit.id.desc()).limit(30).all(),products=StoreProduct.query.order_by(StoreProduct.id.desc()).all(),point_requests=PointRequest.query.order_by(PointRequest.id.desc()).limit(50).all())
@app.post('/admin/invite')
@owner_required
def create_invite():
 try:uses=max(1,min(int(request.form.get('max_uses',1)),100))
 except:uses=1
 c=secrets.token_urlsafe(8);db.session.add(Invite(code=c,max_uses=uses));log('تم إنشاء دعوة جديدة');db.session.commit();return redirect(url_for('admin'))
@app.post('/admin/invite/<int:iid>/toggle')
@owner_required
def toggle_invite(iid):
 i=db.session.get(Invite,iid)
 if i:i.active=not i.active;db.session.commit()
 return redirect(url_for('admin'))
@app.post('/admin/user/<int:uid>')
@owner_required
def edit_user(uid):
 u=db.session.get(User,uid)
 if not u or u.is_owner:return redirect(url_for('admin'))
 rank=request.form.get('rank');u.rank=rank if rank in RANKS[1:] else u.rank
 try:u.points=int(request.form.get('points',u.points))
 except:pass
 u.is_muted=request.form.get('muted')=='1';u.is_banned=request.form.get('banned')=='1';u.premium_avatar=request.form.get('premium_avatar')=='1';txt=request.form.get('auto_reply','').strip();r=AutoReply.query.filter_by(user_id=u.id).first()
 if txt:
  if not r:r=AutoReply(user_id=u.id,text=txt);db.session.add(r)
  r.text=txt;r.active=True;r.trigger=request.form.get('auto_trigger','any');r.keyword=request.form.get('auto_keyword','').strip()[:120]
 elif r:db.session.delete(r)
 log(f'تعديل المستخدم {u.username}: الرتبة {u.rank}، النقاط {u.points}');db.session.commit();return redirect(url_for('admin'))

@app.post('/game/challenge/<int:uid>')
@login_required
def challenge(uid):
 other=db.session.get(User,uid);u=me()
 if not other or other.id==u.id or other.is_banned:return redirect(url_for('chat'))
 g=Game(x_user_id=u.id,o_user_id=other.id,status='pending');db.session.add(g);db.session.commit();socketio.emit('xo_challenge',{'game_id':g.id,'from_name':u.display_name,'to_id':other.id});return redirect(url_for('chat'))
@app.route('/game/<int:gid>')
@login_required
def game(gid):
 g=db.session.get(Game,gid);u=me()
 if not g or u.id not in (g.x_user_id,g.o_user_id):abort(403)
 return render_template('game.html',game=g,me=u,x=db.session.get(User,g.x_user_id),o=db.session.get(User,g.o_user_id))
@app.post('/game/<int:gid>/accept')
@login_required
def accept_game(gid):
 g=db.session.get(Game,gid)
 if g and me().id==g.o_user_id and g.status=='pending':g.status='active';db.session.commit();socketio.emit('xo_started',{'game_id':g.id,'x_id':g.x_user_id,'o_id':g.o_user_id},room=f'game:{g.id}')
 return redirect(url_for('game',gid=gid))
@app.post('/game/<int:gid>/move/<int:cell>')
@login_required
def move(gid,cell):
 g=db.session.get(Game,gid);u=me()
 if not g or g.status!='active' or u.id not in (g.x_user_id,g.o_user_id) or cell not in range(9):return jsonify({'ok':False}),400
 sym='X' if u.id==g.x_user_id else 'O'
 if sym!=g.turn:return jsonify({'ok':False,'error':'turn'}),409
 b=list(g.board)
 if b[cell]!='-':return jsonify({'ok':False,'error':'cell'}),409
 b[cell]=sym;g.board=''.join(b);wins=[(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
 result=None
 if any(b[a]==b[c]==b[d]==sym for a,c,d in wins):
  g.status='finished';g.winner_id=u.id;u.points+=100; loser=db.session.get(User,g.o_user_id if u.id==g.x_user_id else g.x_user_id);result=f'انتهت X/O — {u.display_name} فاز على {loser.display_name} — +100 نقطة'
 elif '-' not in b:g.status='draw';result=f'انتهت X/O — تعادل بين {db.session.get(User,g.x_user_id).display_name} و {db.session.get(User,g.o_user_id).display_name}'
 else:g.turn='O' if sym=='X' else 'X'
 db.session.commit();payload={'board':g.board,'turn':g.turn,'status':g.status,'winner_id':g.winner_id};socketio.emit('xo_state',payload,room=f'game:{g.id}')
 if result:push_system_message(result)
 return jsonify({'ok':True,**payload})

def _ids(g): return [int(x) for x in (g.player_ids or '').split(',') if x]

GAME_META={
 'snakes':('حيّة ودرج','🐍🪜'),
 'xo2':('X/O','❌⭕'),
 'rps':('حجر ورقة مقص','✊'),
 'guess':('خمن الرقم','🔢'),
 'reaction':('أسرع ضغطة','⚡'),
 'colors':('اختار اللون','🎨'),
 'memory':('ذاكرة البطاقات','🃏'),
}
def _simple_initial(kind):
 if kind=='snakes':
  return {'positions':[0,0],'turn':0,'dice':None,'winner':None,
   'snakes':{'99':54,'95':75,'92':88,'74':53,'64':60,'62':19,'49':11,'46':25,'16':6},
   'ladders':{'2':38,'7':14,'8':31,'15':26,'21':42,'28':84,'36':44,'51':67,'71':91,'78':98,'87':94}}
 if kind=='xo2':return {'board':'---------','turn':0,'winner':None}
 if kind=='rps':return {'choices':[None,None],'scores':[0,0],'round':1,'winner':None,'last':None}
 if kind=='guess':return {'number':random.randint(1,100),'winner':None,'attempts':[0,0]}
 if kind=='reaction':return {'round':1,'scores':[0,0],'ready_at':now().timestamp()+random.uniform(2.0,5.0),'winner':None,'last':None}
 if kind=='colors':
  names=['أحمر','أزرق','أخضر','أصفر'];correct=random.randrange(4)
  return {'round':1,'scores':[0,0],'names':names,'correct':correct,'winner':None,'last':None}
 if kind=='memory':
  cards=list('AABBCCDDEEFFGGHH');random.shuffle(cards)
  return {'cards':cards,'matched':[],'open':[],'turn':0,'scores':[0,0],'winner':None}
 return {}

def _finish_simple(g,st,pi=None,draw=False):
 ids=_ids(g);g.status='finished'
 if draw:
  st['winner']=None;result=f'انتهت {GAME_META[g.kind][0]} — تعادل بين '+ ' و '.join(db.session.get(User,x).display_name for x in ids)
 else:
  st['winner']=pi;g.winner_id=ids[pi];u=db.session.get(User,ids[pi]);u.points+=100
  other=db.session.get(User,ids[1-pi])
  result=f'انتهت {GAME_META[g.kind][0]} — {u.display_name} فاز على {other.display_name} — +100 نقطة'
 g.state=json.dumps(st);db.session.commit()
 push_system_message(result)
 socketio.emit('table_finished',{'game_id':g.id,'result':result})
 socketio.emit('table_state',{'game_id':g.id},room=f'table:{g.id}')

def _start_table(g):
 ids=_ids(g)
 if len(ids)!=2:return
 g.status='active';g.state=json.dumps(_simple_initial(g.kind))

@app.post('/table-game/create/<kind>')
@login_required
def create_table_game(kind):
 if kind not in GAME_META:abort(404)
 # One waiting challenge per user/game. Repeated taps reopen it instead of creating duplicates.
 old=TableGame.query.filter_by(host_id=me().id,kind=kind,status='lobby').order_by(TableGame.id.desc()).first()
 if old:return redirect(url_for('table_game',gid=old.id))
 g=TableGame(kind=kind,host_id=me().id,player_ids=str(me().id),max_players=2,status='lobby',state=json.dumps(_simple_initial(kind)))
 db.session.add(g);db.session.commit()
 label,icon=GAME_META[kind]
 socketio.emit('table_invite',{'game_id':g.id,'kind':kind,'label':label,'icon':icon,'host':shown_name(me()),'max_players':2})
 return redirect(url_for('table_game',gid=g.id))

@app.route('/table-game/<int:gid>')
@login_required
def table_game(gid):
 g=db.session.get(TableGame,gid) or abort(404);ids=_ids(g)
 # Clicking the challenge card joins immediately. No second "join" screen.
 if g.status=='lobby' and me().id not in ids and len(ids)<2:
  ids.append(me().id);g.player_ids=','.join(map(str,ids));_start_table(g);db.session.commit()
  socketio.emit('table_state',{'game_id':g.id},room=f'table:{g.id}')
  socketio.emit('table_started',{'game_id':g.id})
 if me().id not in _ids(g):abort(403)
 meta=GAME_META.get(g.kind)
 if not meta: abort(404)
 return render_template('simple_game.html',g=g,me=me(),meta=meta)

@app.get('/api/table-game/<int:gid>')
@login_required
def table_state(gid):
 g=db.session.get(TableGame,gid) or abort(404);ids=_ids(g)
 if me().id not in ids:abort(403)
 st=json.loads(g.state or '{}');safe=dict(st);pi=ids.index(me().id)
 # Never reveal secrets.
 if g.kind=='guess':safe.pop('number',None)
 if g.kind=='rps':
  safe['choices']=[('✓' if x is not None else None) for x in st.get('choices',[None,None])]
 if g.kind=='colors':
  safe['target_name']=st.get('correct',0)
  safe.pop('correct',None)
 if g.kind=='memory':
  safe['cards']=[v if i in st.get('matched',[]) or i in st.get('open',[]) else None for i,v in enumerate(st['cards'])]
 return jsonify({'game_id':g.id,'kind':g.kind,'status':g.status,'players':[shown_name(db.session.get(User,x)) for x in ids],'state':safe,'you':pi})

@socketio.on('join_table')
def sock_join_table(data):
 u=me();g=db.session.get(TableGame,int(data.get('game_id',0))) if data else None
 if u and g and u.id in _ids(g):join_room(f'table:{g.id}')

@app.post('/table-game/<int:gid>/action')
@login_required
def simple_action(gid):
 g=db.session.get(TableGame,gid) or abort(404);ids=_ids(g)
 if g.status!='active' or me().id not in ids:return jsonify({'ok':False,'error':'inactive'}),409
 pi=ids.index(me().id);st=json.loads(g.state);d=request.get_json(silent=True) or {};kind=g.kind
 if kind=='snakes':
  if st['turn']!=pi:return jsonify({'ok':False,'error':'turn'}),409
  die=random.randint(1,6);old=st['positions'][pi];raw=old+die;pos=old if raw>100 else raw;jump=None
  if pos and str(pos) in st['ladders']:jump=['ladder',pos,st['ladders'][str(pos)]];pos=jump[2]
  elif pos and str(pos) in st['snakes']:jump=['snake',pos,st['snakes'][str(pos)]];pos=jump[2]
  st['dice']=die;st['positions'][pi]=pos
  if pos==100:_finish_simple(g,st,pi);return jsonify({'ok':True,'die':die,'jump':jump})
  if die!=6:st['turn']=1-pi
 elif kind=='xo2':
  if st['turn']!=pi:return jsonify({'ok':False,'error':'turn'}),409
  cell=int(d.get('cell',-1));b=list(st['board'])
  if cell not in range(9) or b[cell]!='-':return jsonify({'ok':False,'error':'cell'}),409
  sym='X' if pi==0 else 'O';b[cell]=sym;st['board']=''.join(b)
  wins=[(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
  if any(b[a]==b[c]==b[e]==sym for a,c,e in wins):_finish_simple(g,st,pi);return jsonify({'ok':True})
  if '-' not in b:_finish_simple(g,st,draw=True);return jsonify({'ok':True})
  st['turn']=1-pi
 elif kind=='rps':
  choice=str(d.get('choice',''))
  if choice not in ('rock','paper','scissors'):return jsonify({'ok':False}),400
  if st['choices'][pi] is not None:return jsonify({'ok':False,'error':'chosen'}),409
  st['choices'][pi]=choice
  if all(st['choices']):
   a,b=st['choices'];win=None
   if a!=b:win=0 if (a,b) in [('rock','scissors'),('scissors','paper'),('paper','rock')] else 1
   if win is not None:st['scores'][win]+=1
   st['last']={'choices':st['choices'][:],'winner':win};st['choices']=[None,None]
   if max(st['scores'])>=3:_finish_simple(g,st,st['scores'].index(max(st['scores'])));return jsonify({'ok':True})
   st['round']+=1
 elif kind=='guess':
  try:n=int(d.get('number'))
  except:return jsonify({'ok':False}),400
  if not 1<=n<=100:return jsonify({'ok':False}),400
  st['attempts'][pi]+=1;target=st['number']
  if n==target:_finish_simple(g,st,pi);return jsonify({'ok':True,'hint':'صح'})
  hint='أعلى' if n<target else 'أوطى'
  g.state=json.dumps(st);db.session.commit();return jsonify({'ok':True,'hint':hint})
 elif kind=='reaction':
  ts=now().timestamp()
  if ts<st['ready_at']:
   st['scores'][pi]=max(0,st['scores'][pi]-1);st['last']=f'{ids[pi]} ضغط قبل الوقت'
  else:
   st['scores'][pi]+=1;st['last']=f'{ids[pi]} كان الأسرع'
   if st['scores'][pi]>=5:_finish_simple(g,st,pi);return jsonify({'ok':True})
   st['round']+=1;st['ready_at']=ts+random.uniform(2.0,5.0)
 elif kind=='colors':
  try:choice=int(d.get('choice'))
  except:return jsonify({'ok':False}),400
  if choice==st['correct']:
   st['scores'][pi]+=1;st['last']=pi
   if st['scores'][pi]>=5:_finish_simple(g,st,pi);return jsonify({'ok':True})
   st['round']+=1;st['correct']=random.randrange(4)
  else:return jsonify({'ok':False,'error':'wrong'}),409
 elif kind=='memory':
  if st['turn']!=pi:return jsonify({'ok':False,'error':'turn'}),409
  try:cell=int(d.get('cell'))
  except:return jsonify({'ok':False}),400
  if cell not in range(16) or cell in st['matched'] or cell in st['open']:return jsonify({'ok':False}),409
  st['open'].append(cell)
  if len(st['open'])==2:
   a,b=st['open']
   if st['cards'][a]==st['cards'][b]:
    st['matched'] += [a,b];st['scores'][pi]+=1;st['open']=[]
    if len(st['matched'])==16:
     if st['scores'][0]==st['scores'][1]:_finish_simple(g,st,draw=True)
     else:_finish_simple(g,st,0 if st['scores'][0]>st['scores'][1] else 1)
     return jsonify({'ok':True})
   else:
    # Client sees the pair once; next action closes it and changes turn.
    st['pending_close']=True
  elif st.get('pending_close'):
   st['open']=[];st['pending_close']=False;st['turn']=1-pi
 else:return jsonify({'ok':False}),404
 g.state=json.dumps(st);db.session.commit();socketio.emit('table_state',{'game_id':g.id},room=f'table:{g.id}')
 return jsonify({'ok':True})

@app.post('/table-game/<int:gid>/memory-close')
@login_required
def memory_close(gid):
 g=db.session.get(TableGame,gid) or abort(404);ids=_ids(g);st=json.loads(g.state or '{}')
 if g.kind!='memory' or g.status!='active' or me().id not in ids:return jsonify({'ok':False}),409
 if st.get('pending_close'):
  st['open']=[];st['pending_close']=False;st['turn']=1-st['turn'];g.state=json.dumps(st);db.session.commit()
  socketio.emit('table_state',{'game_id':g.id},room=f'table:{g.id}')
 return jsonify({'ok':True})

@app.post('/table-game/<int:gid>/rematch')
@login_required
def table_rematch(gid):
 g=db.session.get(TableGame,gid) or abort(404);ids=_ids(g)
 if me().id not in ids or len(ids)!=2:return jsonify({'ok':False}),403
 st=json.loads(g.state or '{}');votes=set(st.get('rematch_votes',[]));votes.add(me().id)
 if len(votes)==2:
  g.status='active';g.winner_id=None;g.state=json.dumps(_simple_initial(g.kind));started=True
 else:
  st['rematch_votes']=list(votes);g.state=json.dumps(st);started=False
 db.session.commit();socketio.emit('table_state',{'game_id':g.id},room=f'table:{g.id}')
 return jsonify({'ok':True,'started':started,'votes':len(votes)})

@app.route('/quiz')
@login_required
def quiz_home():return render_template('quiz_home.html',me=me(),mine=Quiz.query.filter_by(host_id=me().id).order_by(Quiz.id.desc()).limit(10).all())
@app.post('/quiz/create')
@login_required
def quiz_create():
 title=request.form.get('title','').strip()[:100]
 if not title:return redirect(url_for('quiz_home'))
 limit=max(5,min(request.form.get('time_limit',30,type=int),300)); q=Quiz(code=roomcode(),title=title,host_id=me().id,time_limit=limit);db.session.add(q);db.session.commit();return redirect(url_for('quiz_edit',qid=q.id))
@app.route('/quiz/<int:qid>/edit',methods=['GET','POST'])
@login_required
def quiz_edit(qid):
 q=db.session.get(Quiz,qid)
 if not q or q.host_id!=me().id:abort(403)
 if request.method=='POST':
  vals=[request.form.get(x,'').strip() for x in ['text','a','b','c','d']];correct=request.form.get('correct')
  if all(vals) and correct in 'ABCD':db.session.add(Question(quiz_id=q.id,text=vals[0],a=vals[1],b=vals[2],c=vals[3],d=vals[4],correct=correct));db.session.commit()
 return render_template('quiz_edit.html',quiz=q,questions=Question.query.filter_by(quiz_id=q.id).order_by(Question.id).all())
@app.post('/quiz/join')
@login_required
def quiz_join():
 code=request.form.get('code','').strip().upper();q=Quiz.query.filter_by(code=code).first()
 if not q:return render_template('quiz_home.html',me=me(),mine=[],error='كود الغرفة غير صحيح')
 p=QuizPlayer.query.filter_by(quiz_id=q.id,user_id=me().id).first()
 if not p:db.session.add(QuizPlayer(quiz_id=q.id,user_id=me().id));db.session.commit()
 return redirect(url_for('quiz_room',qid=q.id))
@app.route('/quiz/<int:qid>')
@login_required
def quiz_room(qid):
 q=db.session.get(Quiz,qid)
 if not q:abort(404)
 ishost=q.host_id==me().id;p=QuizPlayer.query.filter_by(quiz_id=q.id,user_id=me().id).first()
 if not ishost and not p:abort(403)
 questions=Question.query.filter_by(quiz_id=q.id).order_by(Question.id).all();cur=questions[q.current_index] if q.status=='active' and q.current_index<len(questions) else None
 answered=Answer.query.filter_by(question_id=cur.id,user_id=me().id).first() if cur else None
 players=QuizPlayer.query.filter_by(quiz_id=q.id).order_by(QuizPlayer.score.desc()).all();board=[(db.session.get(User,p.user_id),p.score) for p in players]
 return render_template('quiz_room.html',quiz=q,me=me(),ishost=ishost,current=cur,answered=answered,board=board,total=len(questions))
@app.post('/quiz/<int:qid>/start')
@login_required
def quiz_start(qid):
 q=db.session.get(Quiz,qid)
 if not q or q.host_id!=me().id:abort(403)
 if Question.query.filter_by(quiz_id=q.id).count():q.status='active';q.current_index=0;q.question_started_at=now();Answer.query.filter_by(quiz_id=q.id).delete();[setattr(p,'score',0) for p in QuizPlayer.query.filter_by(quiz_id=q.id).all()];db.session.commit();socketio.emit('quiz_live',{'quiz_id':q.id,'code':q.code,'title':q.title,'host':me().display_name})
 return redirect(url_for('quiz_room',qid=q.id))
@app.post('/quiz/<int:qid>/answer')
@login_required
def quiz_answer(qid):
 q=db.session.get(Quiz,qid);p=QuizPlayer.query.filter_by(quiz_id=q.id,user_id=me().id).first() if q else None
 qs=Question.query.filter_by(quiz_id=q.id).order_by(Question.id).all() if q else []
 if not q or q.status!='active' or not p or q.current_index>=len(qs):return redirect(url_for('quiz_room',qid=qid))
 qu=qs[q.current_index]
 if not Answer.query.filter_by(question_id=qu.id,user_id=me().id).first():
  choice=request.form.get('choice');elapsed=max(0,(now()-(q.question_started_at or now())).total_seconds());ok=(choice==qu.correct and elapsed<=q.time_limit);pts=(max(1,round(100*(1-elapsed/q.time_limit))) if ok else 0);db.session.add(Answer(quiz_id=q.id,question_id=qu.id,user_id=me().id,choice=choice,correct=ok));p.score+=pts;db.session.commit()
 return redirect(url_for('quiz_room',qid=qid))
@app.post('/quiz/<int:qid>/next')
@login_required
def quiz_next(qid):
 q=db.session.get(Quiz,qid)
 if not q or q.host_id!=me().id:abort(403)
 total=Question.query.filter_by(quiz_id=q.id).count();q.current_index+=1
 if q.current_index>=total:q.status='finished'
 else:q.question_started_at=now()
 db.session.commit();return redirect(url_for('quiz_room',qid=q.id))


@app.route('/store')
@login_required
def store():
 products=StoreProduct.query.filter_by(active=True).order_by(StoreProduct.id.desc()).all(); owned={x.product_id:x for x in Purchase.query.filter_by(user_id=me().id).all()}
 return render_template('store.html',me=me(),products=products,owned=owned)

@app.post('/store/buy/<int:pid>')
@login_required
def store_buy(pid):
 p=db.session.get(StoreProduct,pid);u=me()
 if not p or not p.active:return jsonify({'ok':False,'error':'المنتج غير متاح'}),404
 if Purchase.query.filter_by(user_id=u.id,product_id=p.id).first():return jsonify({'ok':False,'error':'المنتج مملوك بالفعل'}),409
 if u.points<p.price:return jsonify({'ok':False,'error':'نقاطك غير كافية'}),409
 u.points-=p.price;db.session.add(Purchase(user_id=u.id,product_id=p.id,price_paid=p.price));db.session.commit();socketio.emit('points_changed',{'points':u.points},room=f'user:{u.id}');return jsonify({'ok':True,'points':u.points})

@app.post('/store/equip/<int:pid>')
@login_required
def store_equip(pid):
 own=Purchase.query.filter_by(user_id=me().id,product_id=pid).first();p=db.session.get(StoreProduct,pid)
 if not own or not p:return jsonify({'ok':False}),404
 for x in Purchase.query.filter_by(user_id=me().id).all():
  px=db.session.get(StoreProduct,x.product_id)
  if px and px.kind==p.kind:x.active=False
 own.active=True;db.session.commit();return jsonify({'ok':True})

@app.post('/points/request')
@login_required
def points_request():
 amount=max(1,min(request.form.get('amount',1000,type=int),10000000));note=request.form.get('note','').strip()[:300];r=PointRequest(user_id=me().id,amount=amount,note=note);db.session.add(r);db.session.commit();owner=User.query.filter_by(is_owner=True).first();socketio.emit('point_request',{'id':r.id,'name':me().display_name,'amount':amount},room=f'user:{owner.id}' if owner else None);return redirect(url_for('store'))

@app.post('/admin/points/<int:uid>')
@owner_required
def admin_points(uid):
 u=db.session.get(User,uid) or abort(404);delta=request.form.get('delta',0,type=int);reason=request.form.get('reason','').strip()[:150];u.points=max(0,u.points+delta);log(f'تعديل رصيد {u.username}: {delta:+d} — {reason or "بدون سبب"}');db.session.commit();socketio.emit('points_changed',{'points':u.points},room=f'user:{u.id}');return redirect(url_for('admin'))

@app.post('/admin/point-request/<int:rid>/<action>')
@owner_required
def admin_point_request(rid,action):
 r=db.session.get(PointRequest,rid) or abort(404)
 if r.status!='pending':return redirect(url_for('admin'))
 if action=='approve':
  u=db.session.get(User,r.user_id);u.points+=r.amount;r.status='approved';log(f'تمت الموافقة على طلب نقاط {u.username}: +{r.amount}');socketio.emit('points_changed',{'points':u.points},room=f'user:{u.id}')
 else:r.status='rejected'
 db.session.commit();return redirect(url_for('admin'))

@app.post('/admin/store/add')
@owner_required
def admin_store_add():
 name=request.form.get('name','').strip()[:100];price=max(0,request.form.get('price',0,type=int));kind=request.form.get('kind','badge');f=request.files.get('image')
 if not name or not f:return redirect(url_for('admin'))
 ext=(secure_filename(f.filename).rsplit('.',1)[-1].lower() if '.' in f.filename else '')
 if ext not in ('png','webp','jpg','jpeg'):return redirect(url_for('admin'))
 image=save_store_image(f,kind);db.session.add(StoreProduct(name=name,price=price,kind=kind,image=image));db.session.commit();socketio.emit('store_updated',{'name':name});return redirect(url_for('admin'))

@app.post('/admin/store/<int:pid>/toggle')
@owner_required
def admin_store_toggle(pid):
 p=db.session.get(StoreProduct,pid) or abort(404);p.active=not p.active;db.session.commit();socketio.emit('store_updated',{'id':p.id});return redirect(url_for('admin'))

@app.context_processor
def inject():return {'current_user':me(),'appearance':appearance,'shown_name':shown_name,'avatar_url':avatar_url}
with app.app_context():db.create_all()

@app.route("/admin/backup/export")
@login_required
def full_backup_export():
    if not me().is_owner: abort(403)
    data=json.dumps(make_full_backup(),ensure_ascii=False,indent=2).encode("utf-8")
    return Response(data,mimetype="application/json",headers={"Content-Disposition":f'attachment; filename="ab_new_full_backup_{datetime.utcnow().strftime("%Y%m%d_%H%M%S")}.json"'})

@app.route("/admin/backup/import",methods=["POST"])
@login_required
def full_backup_import():
    if not me().is_owner: abort(403)
    f=request.files.get("backup")
    try:
        payload=json.load(f)
        if payload.get("format")!="ab-new-backup-v2": raise ValueError("ملف النسخة غير صحيح")
        up=os.path.join(app.root_path,"static","uploads"); os.makedirs(up,exist_ok=True)
        for fn,b64 in payload.get("assets",{}).items():
            safe=secure_filename(fn)
            if safe:
                with open(os.path.join(up,safe),"wb") as out: out.write(base64.b64decode(b64))
        ins=inspect(db.engine); existing=set(ins.get_table_names())
        tables=[t for t in payload.get("tables",{}) if t in existing]
        db.session.execute(db.text("PRAGMA foreign_keys=OFF"))
        for t in reversed(tables): db.session.execute(db.text(f'DELETE FROM "{t}"'))
        for t in tables:
            cols={c["name"] for c in ins.get_columns(t)}
            for row in payload["tables"][t]:
                row={k:v for k,v in row.items() if k in cols}
                if not row: continue
                ks=list(row); names=",".join('"'+k+'"' for k in ks); binds=",".join(":"+k for k in ks)
                db.session.execute(db.text(f'INSERT INTO "{t}" ({names}) VALUES ({binds})'),row)
        db.session.execute(db.text("PRAGMA foreign_keys=ON")); db.session.commit()
        flash("تم استرجاع كل البيانات بنجاح")
    except Exception as e:
        db.session.rollback(); flash("فشل الاسترجاع: "+str(e)[:160])
    return redirect("/admin")


@app.get('/health')
def health():
 return {'ok':True},200

if __name__=='__main__':socketio.run(app,host='0.0.0.0',port=5000,allow_unsafe_werkzeug=True,debug=False)
