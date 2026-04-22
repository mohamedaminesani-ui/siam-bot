import os, json, io, sqlite3, logging
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak)
from reportlab.lib.styles import ParagraphStyle
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, ContextTypes, filters)
logging.basicConfig(level=logging.INFO)
BOT_TOKEN = "8656004270:AAEhk7pvVWVJnD2DAO0HoMMSK1Sio83QWvo"
DB_PATH = "/content/siam_2025.db"
SKIP = "⏭ Passer"
class DB:
    def __init__(self):
        self.p=DB_PATH; c=sqlite3.connect(self.p); c.row_factory=sqlite3.Row
        c.executescript("""
            CREATE TABLE IF NOT EXISTS stands(id INTEGER PRIMARY KEY AUTOINCREMENT,brand TEXT,stand_num TEXT,category TEXT,cat_icon TEXT,products TEXT,prix TEXT,power TEXT,contact TEXT,remark TEXT,tags TEXT DEFAULT '[]',created_at TEXT);
            CREATE TABLE IF NOT EXISTS gaps(id INTEGER PRIMARY KEY AUTOINCREMENT,machine TEXT,brand TEXT,reason TEXT,market TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS loncin(id INTEGER PRIMARY KEY DEFAULT 1,present INTEGER,stand_num TEXT,oem TEXT,gamme TEXT,prix TEXT,contact TEXT,remark TEXT,updated_at TEXT);
            CREATE TABLE IF NOT EXISTS benchmark(id INTEGER PRIMARY KEY AUTOINCREMENT,brand TEXT,model TEXT,prix TEXT,power TEXT,stihl_equiv TEXT,created_at TEXT);
            CREATE TABLE IF NOT EXISTS synthese(id INTEGER PRIMARY KEY DEFAULT 1,insights TEXT,menaces TEXT,opps TEXT,actions TEXT,updated_at TEXT);
            CREATE TABLE IF NOT EXISTS objectifs(id TEXT PRIMARY KEY,done INTEGER DEFAULT 0);
        """); c.commit(); c.close()
    def _c(self): c=sqlite3.connect(self.p); c.row_factory=sqlite3.Row; return c
    def add_stand(self,brand,stand_num,cat,icon,products,prix,power,contact,remark,tags):
        with self._c() as c: c.execute("INSERT INTO stands(brand,stand_num,category,cat_icon,products,prix,power,contact,remark,tags,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(brand,stand_num,cat,icon,products,prix,power,contact,remark,json.dumps(tags),datetime.now().strftime("%H:%M")))
    def get_stands(self):
        with self._c() as c: return [dict(r) for r in c.execute("SELECT * FROM stands ORDER BY id")]
    def add_gap(self,machine,brand,reason,market):
        with self._c() as c: c.execute("INSERT INTO gaps(machine,brand,reason,market,created_at) VALUES(?,?,?,?,?)",(machine,brand,reason,market,datetime.now().strftime("%H:%M")))
    def get_gaps(self):
        with self._c() as c: return [dict(r) for r in c.execute("SELECT * FROM gaps")]
    def set_loncin(self,present,stand_num,oem,gamme,prix,contact,remark):
        with self._c() as c:
            c.execute("DELETE FROM loncin")
            c.execute("INSERT INTO loncin(id,present,stand_num,oem,gamme,prix,contact,remark,updated_at) VALUES(1,?,?,?,?,?,?,?,?)",(1 if present else 0,stand_num,oem,gamme,prix,contact,remark,datetime.now().strftime("%H:%M")))
    def get_loncin(self):
        with self._c() as c: r=c.execute("SELECT * FROM loncin WHERE id=1").fetchone(); return dict(r) if r else None
    def add_bench(self,brand,model,prix,power,equiv):
        with self._c() as c: c.execute("INSERT INTO benchmark(brand,model,prix,power,stihl_equiv,created_at) VALUES(?,?,?,?,?,?)",(brand,model,prix,power,equiv,datetime.now().strftime("%H:%M")))
    def get_bench(self):
        with self._c() as c: return [dict(r) for r in c.execute("SELECT * FROM benchmark")]
    def set_synthese(self,insights,menaces,opps,actions):
        with self._c() as c:
            c.execute("DELETE FROM synthese")
            c.execute("INSERT INTO synthese(id,insights,menaces,opps,actions,updated_at) VALUES(1,?,?,?,?,?)",(insights,menaces,opps,actions,datetime.now().strftime("%H:%M")))
    def get_synthese(self):
        with self._c() as c: r=c.execute("SELECT * FROM synthese WHERE id=1").fetchone(); return dict(r) if r else None
    def toggle_obj(self,oid):
        with self._c() as c:
            e=c.execute("SELECT done FROM objectifs WHERE id=?",(oid,)).fetchone()
            if e: c.execute("UPDATE objectifs SET done=? WHERE id=?",(0 if e["done"] else 1,oid))
            else: c.execute("INSERT INTO objectifs(id,done) VALUES(?,1)",(oid,))
    def get_objectifs(self):
        with self._c() as c: return {r["id"]:bool(r["done"]) for r in c.execute("SELECT id,done FROM objectifs")}
    def stats(self):
        with self._c() as c:
            return {"stands":c.execute("SELECT COUNT(*) FROM stands").fetchone()[0],"gaps":c.execute("SELECT COUNT(*) FROM gaps").fetchone()[0],"bench":c.execute("SELECT COUNT(*) FROM benchmark").fetchone()[0],"loncin":1 if c.execute("SELECT COUNT(*) FROM loncin").fetchone()[0] else 0,"synthese":1 if c.execute("SELECT COUNT(*) FROM synthese").fetchone()[0] else 0}
    def reset(self):
        with self._c() as c:
            for t in ["stands","gaps","loncin","benchmark","synthese","objectifs"]: c.execute(f"DELETE FROM {t}")
db=DB()
G1=HexColor("#1E5B3A");OR=HexColor("#D4500A");INK=HexColor("#1A1A1A");GRY=HexColor("#888888");PAL=HexColor("#F4F0E8");RUL=HexColor("#DDDDDD");RED=HexColor("#E74C3C");GP=HexColor("#7CB342");WRM=HexColor("#FAF8F4")
CAT_COLORS={"Marques Premium":"#E74C3C","Gap STIHL":"#D4500A","OEM / Loncin":"#9B59B6","Innovation":"#3498DB","Agri Motorisé":"#27AE60","Jardinage / Outdoor":"#1ABC9C","Fabricant → Moteur 4T":"#F39C12"}
_id=[0]
def S(size=9,color=INK,bold=False,italic=False,align=TA_LEFT,leading=None):
    _id[0]+=1; fn="Helvetica-Bold" if bold else ("Helvetica-Oblique" if italic else "Helvetica")
    return ParagraphStyle(f"x{_id[0]}",fontName=fn,fontSize=size,textColor=color,leading=leading or max(10,int(size*1.45)),alignment=align)
def P(t,**k): return Paragraph(str(t or "—"),S(**k))
def SP(h=4): return Spacer(1,h*mm)
def T(rows,widths,ex=None):
    t=Table(rows,colWidths=[w*mm for w in widths])
    base=[("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")]
    t.setStyle(TableStyle(base+(ex or []))); return t
def generate_pdf():
    buf=io.BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,leftMargin=18*mm,rightMargin=14*mm,topMargin=12*mm,bottomMargin=14*mm)
    story=[]; today=datetime.now().strftime("%d %B %Y"); obj_done=db.get_objectifs(); n_done=sum(obj_done.values())
    stands=db.get_stands(); gaps=db.get_gaps(); bench=db.get_bench(); loncin=db.get_loncin(); syn=db.get_synthese()
    story.append(T([[P("SIAM  2025",size=36,color=white,bold=True,leading=38),P("Rapport Intelligence Terrain · STIHL AF/ME",size=11,color=HexColor("#AADDBB"),italic=True,align=TA_RIGHT)]],[95,71],[("BACKGROUND",(0,0),(-1,-1),G1),("TOPPADDING",(0,0),(-1,-1),12*mm),("BOTTOMPADDING",(0,0),(-1,-1),10*mm),("LEFTPADDING",(0,0),(0,-1),12*mm),("RIGHTPADDING",(0,0),(-1,-1),8*mm),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(T([[P("DATE",size=7,color=HexColor("#88BBAA"),bold=True,align=TA_CENTER),P("OBSERVATEUR",size=7,color=HexColor("#88BBAA"),bold=True,align=TA_CENTER),P("STANDS",size=7,color=HexColor("#88BBAA"),bold=True,align=TA_CENTER),P("OBJECTIFS",size=7,color=HexColor("#88BBAA"),bold=True,align=TA_CENTER)],[P(today,size=10,bold=True,align=TA_CENTER),P("Mohamed Amine",size=10,bold=True,align=TA_CENTER),P(str(len(stands)),size=12,color=OR,bold=True,align=TA_CENTER),P(f"{n_done}/7",size=12,color=GP,bold=True,align=TA_CENTER)]],[42,52,38,38],[("BACKGROUND",(0,0),(-1,0),G1),("BACKGROUND",(0,1),(-1,1),PAL),("LINEBELOW",(0,1),(-1,1),1,RUL),("LINEBEFORE",(1,0),(-1,-1),0.5,HexColor("#2E7D52")),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3)]))
    story.append(SP(5))
    if stands:
        story.append(P("FICHES EXPOSANTS",size=12,bold=True)); story.append(SP(2))
        for s in stands:
            tags=json.loads(s.get("tags") or "[]"); cc=HexColor(CAT_COLORS.get(s.get("category",""),"#888888"))
            meta=f"{s.get('cat_icon','')} {s.get('category','')}"; 
            if s.get("stand_num"): meta+=f" · Stand {s['stand_num']}"
            rows=[[P(s["brand"],size=12,bold=True),P(meta,size=8,color=cc,align=TA_RIGHT)]]
            for lbl,val in [("PRODUITS",s.get("products")),("PRIX",("  ·  ".join(filter(None,[s.get("prix"),s.get("power")])))),("CONTACT",s.get("contact")),("OPPORTUNITÉ STIHL",s.get("remark")),("TAGS","  ".join(f"[{t}]" for t in tags) if tags else None)]:
                if val: rows.append([P(lbl,size=7,color=GRY,bold=True),P(val,size=9)])
            story.append(KeepTogether([T(rows,[42,124],[("BACKGROUND",(0,0),(-1,0),PAL),("LINEBELOW",(0,0),(-1,0),1,RUL),("BOX",(0,0),(-1,-1),0.5,RUL),("LINELEFT",(0,0),(0,-1),3,cc)]),SP(3)]))
    if gaps:
        story.append(P("GAPS — ABSENT CHEZ STIHL",size=10,bold=True)); story.append(SP(2))
        g_rows=[[P(h,size=7,color=white,bold=True) for h in ["Machine","Marque","Raison","Marché"]]]
        for g in gaps: g_rows.append([P(g.get(k) or "—",size=9) for k in ["machine","brand","reason","market"]])
        story.append(T(g_rows,[42,30,62,32],[("BACKGROUND",(0,0),(-1,0),INK),("LINEBELOW",(0,0),(-1,-1),0.4,RUL)])); story.append(SP(3))
    if loncin:
        story.append(P("LONCIN / OEM MOTEURS 4T",size=10,bold=True)); story.append(SP(2))
        lrows=[[P("PRÉSENT ?",size=7,color=GRY,bold=True),P("✅ OUI" if loncin.get("present") else "❌ NON",size=10,bold=True,color=GP if loncin.get("present") else RED)]]
        for lbl,key in [("N° STAND","stand_num"),("OEM","oem"),("GAMME","gamme"),("PRIX","prix"),("CONTACT","contact"),("REMARQUES","remark")]:
            if loncin.get(key): lrows.append([P(lbl,size=7,color=GRY,bold=True),P(loncin[key],size=9)])
        story.append(T(lrows,[44,122],[("LINEBELOW",(0,0),(-1,-1),0.4,RUL)])); story.append(SP(3))
    if bench:
        story.append(P("BENCHMARK CONCURRENTIEL",size=10,bold=True)); story.append(SP(2))
        b_rows=[[P(h,size=7,color=white,bold=True) for h in ["Marque","Modèle","Prix MAD","cc/W","Équiv. STIHL ?"]]]
        for r in bench: b_rows.append([P(r.get(k) or "—",size=9) for k in ["brand","model","prix","power","stihl_equiv"]])
        story.append(T(b_rows,[30,54,26,26,30],[("BACKGROUND",(0,0),(-1,0),INK),("LINEBELOW",(0,0),(-1,-1),0.4,RUL)])); story.append(SP(3))
    if syn:
        story.append(P("SYNTHÈSE FIN DE JOURNÉE",size=10,bold=True)); story.append(SP(2))
        for k,lbl in [("insights","🏆 Top Insights"),("menaces","⚠️ Menaces"),("opps","💡 Opportunités"),("actions","📌 Actions")]:
            if syn.get(k): story.append(P(lbl,size=8,color=GRY,bold=True)); story.append(P(syn[k],size=9)); story.append(SP(2))
    story.append(T([[P("📲 Après le SIAM : partage ce PDF avec Claude → étude de marché Excel + rapport exécutif STIHL AF/ME",size=9,color=G1,italic=True)]],[162],[("BACKGROUND",(0,0),(-1,-1),HexColor("#E8F4ED")),("LINELEFT",(0,0),(0,-1),3,G1),("TOPPADDING",(0,0),(-1,-1),4*mm),("BOTTOMPADDING",(0,0),(-1,-1),4*mm),("LEFTPADDING",(0,0),(-1,-1),5*mm)]))
    doc.build(story); return buf.getvalue()
(ST_BRAND,ST_CAT,ST_NUM,ST_PRODUCTS,ST_PRIX,ST_POWER,ST_CONTACT,ST_REMARK,ST_TAGS)=range(9)
(GP_MACHINE,GP_BRAND,GP_REASON,GP_MARKET)=range(4)
(LC_PRESENT,LC_STAND,LC_OEM,LC_GAMME,LC_PRIX,LC_CONTACT,LC_REMARK)=range(7)
(BN_BRAND,BN_MODEL,BN_PRIX,BN_POWER,BN_EQUIV)=range(5)
(SY_INSIGHTS,SY_MENACES,SY_OPPS,SY_ACTIONS)=range(4)
CATS=[("🏆 Marques Premium","Marques Premium","🏆"),("🔍 Gap STIHL","Gap STIHL","🔍"),("⚙️ OEM / Loncin","OEM / Loncin","⚙️"),("💡 Innovation","Innovation","💡"),("🚜 Agri Motorisé","Agri Motorisé","🚜"),("🌿 Jardinage / Outdoor","Jardinage / Outdoor","🌿"),("🔧 Fabricant → Moteur 4T","Fabricant → Moteur 4T","🔧")]
TAGS_LIST=["💰 Prix relevé","📸 Photo prise","📄 Fiche technique","👤 Contact pris","🔎 À investiguer","🆕 Nouveau produit","💡 Opportunité STIHL"]
OBJS=[("o1","🏆","Marques Premium","Toutes les marques premium"),("o2","🔍","Gap STIHL","Machines absentes chez STIHL"),("o3","⚙️","OEM / Loncin","Présence Loncin"),("o4","🔧","Moteur 4T","Fabricants moteur 4T"),("o5","💡","Innovation","Innovations"),("o6","🚜","Agri Motorisé","Benchmark agri"),("o7","🌿","Jardinage","Offre jardin")]
def cat_kb():
    r=[]
    for i in range(0,len(CATS),2):
        row=[InlineKeyboardButton(CATS[i][0],callback_data=f"cat_{i}")]
        if i+1<len(CATS): row.append(InlineKeyboardButton(CATS[i+1][0],callback_data=f"cat_{i+1}"))
        r.append(row)
    return InlineKeyboardMarkup(r)
def yn_kb(): return InlineKeyboardMarkup([[InlineKeyboardButton("✅ OUI",callback_data="yn_yes"),InlineKeyboardButton("❌ NON",callback_data="yn_no")]])
def tags_kb(sel):
    r=[[InlineKeyboardButton(("✅ " if t in sel else "")+t,callback_data=f"tag_{i}")] for i,t in enumerate(TAGS_LIST)]
    r.append([InlineKeyboardButton("✔️ Valider",callback_data="tag_done")]); return InlineKeyboardMarkup(r)
def obj_kb(done):
    r=[[InlineKeyboardButton(("✅" if done.get(oid) else "⬜")+f" {icon} {t[:35]}",callback_data=f"obj_{oid}")] for oid,icon,t,_ in OBJS]
    r.append([InlineKeyboardButton("🔙 Fermer",callback_data="obj_close")]); return InlineKeyboardMarkup(r)
def fmt(t): return "" if t==SKIP else t
async def cmd_start(u,c):
    st=db.stats()
    await u.message.reply_text(f"🟢 *SIAM 2025 — Bot STIHL AF/ME*\n\n🏪 Stands: *{st['stands']}* · 🔍 Gaps: *{st['gaps']}* · 💰 Bench: *{st['bench']}*\n\n🏪 /stand · 🔍 /gap · ⚙️ /loncin\n💰 /benchmark · 📋 /synthese\n🎯 /objectifs · 📊 /voir · 📄 /rapport · 🗑 /reset",parse_mode="Markdown")
async def cmd_objectifs(u,c):
    done=db.get_objectifs(); nb=sum(done.values())
    await u.message.reply_text(f"🎯 *Objectifs — {nb}/7*",parse_mode="Markdown",reply_markup=obj_kb(done))
async def cb_obj(u,c):
    q=u.callback_query; await q.answer(); d=q.data
    if d=="obj_close": await q.edit_message_reply_markup(reply_markup=None); return
    db.toggle_obj(d[4:]); done=db.get_objectifs(); nb=sum(done.values())
    await q.edit_message_text(f"🎯 *Objectifs — {nb}/7*",parse_mode="Markdown",reply_markup=obj_kb(done))
async def st0(u,c): c.user_data.clear(); await u.message.reply_text("🏪 *Marque / Société ?*",parse_mode="Markdown",reply_markup=ReplyKeyboardRemove()); return ST_BRAND
async def st1(u,c): c.user_data["brand"]=u.message.text.strip(); await u.message.reply_text(f"✅ *{c.user_data['brand']}*\n\nCatégorie ?",parse_mode="Markdown",reply_markup=cat_kb()); return ST_CAT
async def st2(u,c):
    q=u.callback_query; await q.answer(); i=int(q.data.split("_")[1])
    c.user_data["cat_label"]=CATS[i][1]; c.user_data["cat_icon"]=CATS[i][2]
    await q.edit_message_text(f"✅ {CATS[i][0]}\n\nN° stand ? (ou /skip)",parse_mode="Markdown"); return ST_NUM
async def st3(u,c): t=u.message.text.strip(); c.user_data["stand_num"]="" if t=="/skip" else t; await u.message.reply_text("Produits observés ?",parse_mode="Markdown"); return ST_PRODUCTS
async def st4(u,c): c.user_data["products"]=u.message.text.strip(); await u.message.reply_text("💰 Prix ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return ST_PRIX
async def st5(u,c): c.user_data["prix"]=fmt(u.message.text.strip()); await u.message.reply_text("⚡ Puissance/cc ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return ST_POWER
async def st6(u,c): c.user_data["power"]=fmt(u.message.text.strip()); await u.message.reply_text("👤 Contact ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return ST_CONTACT
async def st7(u,c): c.user_data["contact"]=fmt(u.message.text.strip()); await u.message.reply_text("💡 Remarque STIHL ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return ST_REMARK
async def st8(u,c):
    c.user_data["remark"]=fmt(u.message.text.strip()); c.user_data["tags"]=[]
    await u.message.reply_text("🏷 Tags ?",reply_markup=ReplyKeyboardRemove())
    await u.message.reply_text("👇",reply_markup=tags_kb([])); return ST_TAGS
async def st9(u,c):
    q=u.callback_query; await q.answer(); d=q.data
    if d=="tag_done":
        x=c.user_data
        db.add_stand(x["brand"],x.get("stand_num",""),x.get("cat_label",""),x.get("cat_icon",""),x.get("products",""),x.get("prix",""),x.get("power",""),x.get("contact",""),x.get("remark",""),x.get("tags",[]))
        await q.edit_message_text(f"✅ *{x['brand']}* enregistré !",parse_mode="Markdown"); return ConversationHandler.END
    if d.startswith("tag_"):
        i=int(d[4:]); t=TAGS_LIST[i]; tags=c.user_data.get("tags",[])
        c.user_data["tags"]=(tags+[t]) if t not in tags else [x for x in tags if x!=t]
        await q.edit_message_reply_markup(reply_markup=tags_kb(c.user_data["tags"]))
    return ST_TAGS
async def gp0(u,c): c.user_data.clear(); await u.message.reply_text("🔍 Machine absente chez STIHL ?",reply_markup=ReplyKeyboardRemove()); return GP_MACHINE
async def gp1(u,c): c.user_data["machine"]=u.message.text.strip(); await u.message.reply_text("Quelle marque ?"); return GP_BRAND
async def gp2(u,c): c.user_data["brand"]=u.message.text.strip(); await u.message.reply_text("Pourquoi c'est un gap ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return GP_REASON
async def gp3(u,c): c.user_data["reason"]=fmt(u.message.text.strip()); await u.message.reply_text("Marché cible ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return GP_MARKET
async def gp4(u,c):
    d=c.user_data; d["market"]=fmt(u.message.text.strip())
    db.add_gap(d["machine"],d["brand"],d.get("reason",""),d.get("market",""))
    await u.message.reply_text(f"✅ *{d['machine']}* enregistré !",parse_mode="Markdown",reply_markup=ReplyKeyboardRemove()); return ConversationHandler.END
async def lc0(u,c): c.user_data.clear(); await u.message.reply_text("⚙️ Loncin présent ?",reply_markup=yn_kb()); return LC_PRESENT
async def lc1(u,c):
    q=u.callback_query; await q.answer(); c.user_data["present"]=q.data=="yn_yes"
    await q.edit_message_text(f"{'✅ OUI' if c.user_data['present'] else '❌ NON'}\n\nN° stand ? (ou /skip)"); return LC_STAND
async def lc2(u,c): t=u.message.text.strip(); c.user_data["stand_num"]="" if t=="/skip" else t; await u.message.reply_text("OEM / Distributeurs ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return LC_OEM
async def lc3(u,c): c.user_data["oem"]=fmt(u.message.text.strip()); await u.message.reply_text("Gamme moteurs ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return LC_GAMME
async def lc4(u,c): c.user_data["gamme"]=fmt(u.message.text.strip()); await u.message.reply_text("Prix / conditions ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return LC_PRIX
async def lc5(u,c): c.user_data["prix"]=fmt(u.message.text.strip()); await u.message.reply_text("Contact ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return LC_CONTACT
async def lc6(u,c): c.user_data["contact"]=fmt(u.message.text.strip()); await u.message.reply_text("Remarques ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return LC_REMARK
async def lc7(u,c):
    d=c.user_data; d["remark"]=fmt(u.message.text.strip())
    db.set_loncin(d["present"],d.get("stand_num",""),d.get("oem",""),d.get("gamme",""),d.get("prix",""),d.get("contact",""),d.get("remark",""))
    await u.message.reply_text("✅ Loncin enregistré !",reply_markup=ReplyKeyboardRemove()); return ConversationHandler.END
async def bn0(u,c): c.user_data.clear(); await u.message.reply_text("💰 Marque ?",reply_markup=ReplyKeyboardRemove()); return BN_BRAND
async def bn1(u,c): c.user_data["brand"]=u.message.text.strip(); await u.message.reply_text("Modèle ?"); return BN_MODEL
async def bn2(u,c): c.user_data["model"]=u.message.text.strip(); await u.message.reply_text("Prix (MAD/€) ?"); return BN_PRIX
async def bn3(u,c): c.user_data["prix"]=u.message.text.strip(); await u.message.reply_text("Puissance/cc ?",reply_markup=ReplyKeyboardMarkup([[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return BN_POWER
async def bn4(u,c): c.user_data["power"]=fmt(u.message.text.strip()); await u.message.reply_text("Équivalent STIHL ?",reply_markup=ReplyKeyboardMarkup([["Oui","Non","Partiel"],[SKIP]],one_time_keyboard=True,resize_keyboard=True)); return BN_EQUIV
async def bn5(u,c):
    d=c.user_data; d["equiv"]=fmt(u.message.text.strip())
    db.add_bench(d["brand"],d["model"],d["prix"],d.get("power",""),d.get("equiv",""))
    await u.message.reply_text(f"✅ *{d['brand']}* enregistré !",parse_mode="Markdown",reply_markup=ReplyKeyboardRemove()); return ConversationHandler.END
async def sy0(u,c): c.user_data.clear(); await u.message.reply_text("📋 Top 3 insights ?",reply_markup=ReplyKeyboardRemove()); return SY_INSIGHTS
async def sy1(u,c): c.user_data["insights"]=u.message.text.strip(); await u.message.reply_text("Menaces / Risques ?"); return SY_MENACES
async def sy2(u,c): c.user_data["menaces"]=u.message.text.strip(); await u.message.reply_text("Opportunités STIHL ?"); return SY_OPPS
async def sy3(u,c): c.user_data["opps"]=u.message.text.strip(); await u.message.reply_text("Actions immédiates ?"); return SY_ACTIONS
async def sy4(u,c):
    d=c.user_data; d["actions"]=u.message.text.strip()
    db.set_synthese(d["insights"],d["menaces"],d["opps"],d["actions"])
    await u.message.reply_text("✅ Synthèse enregistrée ! Tape /rapport 📄"); return ConversationHandler.END
async def cmd_voir(u,c):
    st=db.stats(); done=sum(db.get_objectifs().values())
    t=f"📊 *État SIAM 2025*\n🎯 {done}/7 · 🏪 {st['stands']} stands · 🔍 {st['gaps']} gaps · 💰 {st['bench']} prix\n"
    stands=db.get_stands()
    if stands: t+="\n".join(f"• *{s['brand']}*{' · Stand '+s['stand_num'] if s.get('stand_num') else ''}" for s in stands[-5:])
    await u.message.reply_text(t,parse_mode="Markdown")
async def cmd_rapport(u,c):
    st=db.stats()
    if not any([st["stands"],st["gaps"],st["bench"]]): await u.message.reply_text("⚠️ Aucune donnée. Commence par /stand"); return
    msg=await u.message.reply_text("⏳ Génération PDF...")
    try:
        pdf=generate_pdf()
        await u.message.reply_document(document=pdf,filename="SIAM_2025_Rapport.pdf",caption=f"📄 *SIAM 2025*\n🏪 {st['stands']} stands · 🔍 {st['gaps']} gaps",parse_mode="Markdown")
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Erreur : {e}")
async def cmd_reset(u,c):
    await u.message.reply_text("⚠️ Effacer tout ?",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ OUI",callback_data="reset_yes"),InlineKeyboardButton("❌ Non",callback_data="reset_no")]]))
async def cb_reset(u,c):
    q=u.callback_query; await q.answer()
    if q.data=="reset_yes": db.reset(); await q.edit_message_text("🗑 Données effacées.")
    else: await q.edit_message_text("✅ Annulé.")
def main():
    app=Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",cmd_start))
    app.add_handler(CommandHandler("objectifs",cmd_objectifs))
    app.add_handler(CommandHandler("voir",cmd_voir))
    app.add_handler(CommandHandler("rapport",cmd_rapport))
    app.add_handler(CommandHandler("reset",cmd_reset))
    app.add_handler(CallbackQueryHandler(cb_obj,pattern=r"^obj_"))
    app.add_handler(CallbackQueryHandler(cb_reset,pattern=r"^reset_"))
    TX=filters.TEXT&~filters.COMMAND
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("stand",st0)],states={ST_BRAND:[MessageHandler(TX,st1)],ST_CAT:[CallbackQueryHandler(st2,pattern=r"^cat_")],ST_NUM:[MessageHandler(TX,st3)],ST_PRODUCTS:[MessageHandler(TX,st4)],ST_PRIX:[MessageHandler(TX,st5)],ST_POWER:[MessageHandler(TX,st6)],ST_CONTACT:[MessageHandler(TX,st7)],ST_REMARK:[MessageHandler(TX,st8)],ST_TAGS:[CallbackQueryHandler(st9,pattern=r"^tag_")]},fallbacks=[CommandHandler("cancel",lambda u,c:(u.message.reply_text("❌"),ConversationHandler.END)[1])],allow_reentry=True))
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("gap",gp0)],states={GP_MACHINE:[MessageHandler(TX,gp1)],GP_BRAND:[MessageHandler(TX,gp2)],GP_REASON:[MessageHandler(TX,gp3)],GP_MARKET:[MessageHandler(TX,gp4)]},fallbacks=[CommandHandler("cancel",lambda u,c:(u.message.reply_text("❌"),ConversationHandler.END)[1])],allow_reentry=True))
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("loncin",lc0)],states={LC_PRESENT:[CallbackQueryHandler(lc1,pattern=r"^yn_")],LC_STAND:[MessageHandler(TX,lc2)],LC_OEM:[MessageHandler(TX,lc3)],LC_GAMME:[MessageHandler(TX,lc4)],LC_PRIX:[MessageHandler(TX,lc5)],LC_CONTACT:[MessageHandler(TX,lc6)],LC_REMARK:[MessageHandler(TX,lc7)]},fallbacks=[CommandHandler("cancel",lambda u,c:(u.message.reply_text("❌"),ConversationHandler.END)[1])],allow_reentry=True))
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("benchmark",bn0)],states={BN_BRAND:[MessageHandler(TX,bn1)],BN_MODEL:[MessageHandler(TX,bn2)],BN_PRIX:[MessageHandler(TX,bn3)],BN_POWER:[MessageHandler(TX,bn4)],BN_EQUIV:[MessageHandler(TX,bn5)]},fallbacks=[CommandHandler("cancel",lambda u,c:(u.message.reply_text("❌"),ConversationHandler.END)[1])],allow_reentry=True))
    app.add_handler(ConversationHandler(entry_points=[CommandHandler("synthese",sy0)],states={SY_INSIGHTS:[MessageHandler(TX,sy1)],SY_MENACES:[MessageHandler(TX,sy2)],SY_OPPS:[MessageHandler(TX,sy3)],SY_ACTIONS:[MessageHandler(TX,sy4)]},fallbacks=[CommandHandler("cancel",lambda u,c:(u.message.reply_text("❌"),ConversationHandler.END)[1])],allow_reentry=True))
    print("🟢 Bot SIAM 2025 démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
main()
