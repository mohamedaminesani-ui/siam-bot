import os, json, io, sqlite3, logging, threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak
from reportlab.lib.styles import ParagraphStyle
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

import os, json, io, sqlite3, logging, threading
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8656004270:AAEhk7pvVWVJnD2DAO0HoMMSK1Sio83QWvo")
DB_PATH = "/app/siam_2025.db"
SKIP = "⏭ Passer"

# ── WEB SERVER (keep Fly.io happy) ─────────────────────
class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, *a): pass
threading.Thread(target=lambda: HTTPServer(("0.0.0.0", 8080), H).serve_forever(), daemon=True).start()

# ── DATABASE ────────────────────────────────────────────
class DB:
    def __init__(self):
        self.p = DB_PATH
        with sqlite3.connect(self.p) as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS stands(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    num_stand TEXT, societe TEXT, secteur TEXT,
                    produits TEXT, prix TEXT, machines_conc TEXT,
                    gap_stihl TEXT, contact TEXT, remarque TEXT,
                    created_at TEXT
                );
            """)
    def _c(self): c=sqlite3.connect(self.p); c.row_factory=sqlite3.Row; return c
    def add(self, num_stand, societe, secteur, produits, prix, machines_conc, gap_stihl, contact, remarque):
        with self._c() as c:
            c.execute("INSERT INTO stands(num_stand,societe,secteur,produits,prix,machines_conc,gap_stihl,contact,remarque,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (num_stand,societe,secteur,produits,prix,machines_conc,gap_stihl,contact,remarque,datetime.now().strftime("%H:%M")))
    def all(self):
        with self._c() as c: return [dict(r) for r in c.execute("SELECT * FROM stands ORDER BY id")]
    def count(self):
        with self._c() as c: return c.execute("SELECT COUNT(*) FROM stands").fetchone()[0]
    def reset(self):
        with self._c() as c: c.execute("DELETE FROM stands")
    def delete(self, sid):
        with self._c() as c: c.execute("DELETE FROM stands WHERE id=?", (sid,))

db = DB()

# ── PDF ─────────────────────────────────────────────────
G1=HexColor("#1E5B3A"); G2=HexColor("#2E7D52"); OR=HexColor("#D4500A")
INK=HexColor("#1A1A1A"); GRY=HexColor("#888888"); PAL=HexColor("#F4F0E8")
RUL=HexColor("#DDDDDD"); WRM=HexColor("#FAF8F4"); RED=HexColor("#E74C3C")
_n=[0]
def S(size=9,color=INK,bold=False,italic=False,align=TA_LEFT,leading=None):
    _n[0]+=1
    fn="Helvetica-Bold" if bold else ("Helvetica-Oblique" if italic else "Helvetica")
    return ParagraphStyle(f"s{_n[0]}",fontName=fn,fontSize=size,textColor=color,
        leading=leading or max(10,int(size*1.5)),alignment=align)
def P(t,**k): return Paragraph(str(t or "—"),S(**k))
def SP(h=3): return Spacer(1,h*mm)
def T(rows,widths,ex=None):
    t=Table(rows,colWidths=[w*mm for w in widths])
    base=[("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
          ("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
          ("VALIGN",(0,0),(-1,-1),"TOP")]
    t.setStyle(TableStyle(base+(ex or []))); return t

SECTEUR_COLORS = {
    "🌿 Jardinage / Outdoor": "#1ABC9C",
    "🚜 Agri / Viticulture":  "#27AE60",
    "⚙️ OEM / Fabricant":    "#9B59B6",
    "🏭 Distribution":        "#3498DB",
    "🔧 SAV / Pièces":        "#F39C12",
    "🔴 Concurrent direct":   "#E74C3C",
    "💡 Autre":               "#888888",
}

def generate_pdf():
    stands = db.all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=16*mm, rightMargin=14*mm, topMargin=12*mm, bottomMargin=12*mm)
    story = []
    today = datetime.now().strftime("%d %B %Y")

    # ── COVER ──
    story.append(T([[
        P("SIAM  2025", size=34, color=white, bold=True, leading=36),
        P(f"Rapport Intelligence Terrain\nSTIHL AF/ME · {today}", size=10,
          color=HexColor("#AADDBB"), italic=True, align=TA_RIGHT)
    ]], [95, 71], [
        ("BACKGROUND",(0,0),(-1,-1),G1),
        ("TOPPADDING",(0,0),(-1,-1),10*mm),
        ("BOTTOMPADDING",(0,0),(-1,-1),8*mm),
        ("LEFTPADDING",(0,0),(0,-1),10*mm),
        ("RIGHTPADDING",(0,0),(-1,-1),6*mm),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(T([[
        P("STANDS VISITÉS", size=7, color=HexColor("#88BBAA"), bold=True, align=TA_CENTER),
        P("SOCIÉTÉS", size=7, color=HexColor("#88BBAA"), bold=True, align=TA_CENTER),
        P("GAPS IDENTIFIÉS", size=7, color=HexColor("#88BBAA"), bold=True, align=TA_CENTER),
        P("DATE", size=7, color=HexColor("#88BBAA"), bold=True, align=TA_CENTER),
    ],[
        P(str(len(stands)), size=14, bold=True, color=OR, align=TA_CENTER),
        P(str(len(set(s["societe"] for s in stands))), size=14, bold=True, align=TA_CENTER),
        P(str(len([s for s in stands if s.get("gap_stihl") and s["gap_stihl"].strip()])), size=14, bold=True, color=RED, align=TA_CENTER),
        P(today, size=10, bold=True, align=TA_CENTER),
    ]], [42,42,42,44], [
        ("BACKGROUND",(0,0),(-1,0),G1),
        ("BACKGROUND",(0,1),(-1,1),PAL),
        ("LINEBELOW",(0,1),(-1,1),1,RUL),
        ("LINEBEFORE",(1,0),(-1,-1),0.5,G2),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),
    ]))
    story.append(SP(6))

    # ── FICHES PAR STAND ──
    story.append(P("① FICHES EXPOSANTS", size=12, bold=True))
    story.append(SP(4))

    for s in stands:
        cc = HexColor(SECTEUR_COLORS.get(s.get("secteur",""), "#888888"))
        rows = []
        # Header
        rows.append([
            P(f"{s.get('societe','?')}", size=13, bold=True),
            P(f"{s.get('secteur','')}  {'· Stand '+s['num_stand'] if s.get('num_stand') else ''}  {'· '+s['created_at'] if s.get('created_at') else ''}", size=8, color=cc, align=TA_RIGHT),
        ])
        # Fields
        for lbl, key in [
            ("PRODUITS / GAMME OBSERVÉS", "produits"),
            ("PRIX RELEVÉS", "prix"),
            ("MACHINES CONCURRENTES", "machines_conc"),
            ("GAP VS STIHL", "gap_stihl"),
            ("CONTACT", "contact"),
            ("REMARQUE", "remarque"),
        ]:
            val = s.get(key)
            if val and val.strip():
                rows.append([P(lbl, size=7, color=GRY, bold=True), P(val, size=9)])

        ex = [
            ("BACKGROUND",(0,0),(-1,0), PAL),
            ("LINEBELOW",(0,0),(-1,0), 1, RUL),
            ("BOX",(0,0),(-1,-1), 0.5, RUL),
            ("LINELEFT",(0,0),(0,-1), 3, cc),
        ]
        for i in range(1, len(rows)):
            ex.append(("LINEBELOW",(0,i),(-1,i),0.3,HexColor("#EEEEEE")))

        story.append(KeepTogether([T(rows, [44, 122], ex), SP(3)]))

    # ── TABLEAU COMPARATIF ──
    story.append(PageBreak())
    story.append(P("② TABLEAU COMPARATIF — BENCHMARK TERRAIN", size=12, bold=True))
    story.append(SP(2))
    story.append(P("Vue synthétique de tous les exposants visités", size=9, color=GRY, italic=True))
    story.append(SP(4))

    # Header
    hdr = [P(h, size=7, color=white, bold=True)
           for h in ["Stand","Société","Secteur","Produits / Prix","Machines conc.","Gap STIHL"]]
    bench_rows = [hdr]
    for s in stands:
        bench_rows.append([
            P(s.get("num_stand") or "—", size=8),
            P(s.get("societe") or "—", size=8, bold=True),
            P(s.get("secteur") or "—", size=7),
            P(f"{s.get('produits','—')}\n{s.get('prix','') if s.get('prix') else ''}", size=8),
            P(s.get("machines_conc") or "—", size=8),
            P(s.get("gap_stihl") or "—", size=8, color=RED if s.get("gap_stihl") else INK),
        ])

    bt = Table(bench_rows, colWidths=[14*mm, 30*mm, 24*mm, 38*mm, 34*mm, 26*mm])
    bt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),INK),
        ("LINEBELOW",(0,0),(-1,-1),0.4,RUL),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[WRM,PAL]),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("BOX",(0,0),(-1,-1),0.5,RUL),
    ]))
    story.append(bt)
    story.append(SP(6))

    # ── GAPS SUMMARY ──
    gaps = [s for s in stands if s.get("gap_stihl") and s["gap_stihl"].strip()]
    if gaps:
        story.append(P("③ SYNTHÈSE — GAPS PRODUITS VS STIHL", size=12, bold=True))
        story.append(SP(3))
        g_rows = [[P(h, size=7, color=white, bold=True) for h in ["Société","Gap identifié","Machine concurrente"]]]
        for s in gaps:
            g_rows.append([
                P(s.get("societe") or "—", size=9, bold=True),
                P(s.get("gap_stihl") or "—", size=9, color=RED),
                P(s.get("machines_conc") or "—", size=9),
            ])
        gt = Table(g_rows, colWidths=[40*mm, 75*mm, 51*mm])
        gt.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),RED),
            ("LINEBELOW",(0,0),(-1,-1),0.4,RUL),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[WRM,PAL]),
            ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
            ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
        ]))
        story.append(gt)
        story.append(SP(5))

    # Footer note
    story.append(T([[P("📲 Partage ce rapport avec Claude → étude de marché Excel complète + rapport exécutif STIHL AF/ME",
                       size=9, color=G1, italic=True)]], [166], [
        ("BACKGROUND",(0,0),(-1,-1),HexColor("#E8F4ED")),
        ("LINELEFT",(0,0),(0,-1),3,G1),
        ("TOPPADDING",(0,0),(-1,-1),4*mm),("BOTTOMPADDING",(0,0),(-1,-1),4*mm),
        ("LEFTPADDING",(0,0),(-1,-1),5*mm),
    ]))

    doc.build(story)
    return buf.getvalue()

# ── CONVERSATION STATES ─────────────────────────────────
(S_NUM, S_SOC, S_SEC, S_PROD, S_PRIX, S_CONC, S_GAP, S_CONT, S_REM) = range(9)

SECTEURS = [
    ["🌿 Jardinage / Outdoor", "🚜 Agri / Viticulture"],
    ["⚙️ OEM / Fabricant",    "🏭 Distribution"],
    ["🔧 SAV / Pièces",       "🔴 Concurrent direct"],
    ["💡 Autre"],
]

def sec_kb(): return ReplyKeyboardMarkup(SECTEURS, one_time_keyboard=True, resize_keyboard=True)
def skip_kb(): return ReplyKeyboardMarkup([[SKIP]], one_time_keyboard=True, resize_keyboard=True)
def fmt(t): return "" if t == SKIP else t

# ── HANDLERS ────────────────────────────────────────────
async def cmd_start(u, c):
    n = db.count()
    await u.message.reply_text(
        f"🟢 *SIAM 2025 — Bot Intelligence Terrain*\n"
        f"_STIHL AF/ME · Mohamed Amine_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🏪 Stands enregistrés : *{n}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏪 /stand — Saisir un exposant\n"
        f"📊 /voir — Voir tous les stands\n"
        f"📄 /rapport — Générer le PDF\n"
        f"🗑 /reset — Effacer tout",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

async def cmd_voir(u, c):
    stands = db.all()
    if not stands:
        await u.message.reply_text("Aucun stand enregistré. Commence par /stand")
        return
    text = f"📊 *{len(stands)} stands enregistrés*\n\n"
    for s in stands:
        text += f"*{s['id']}. {s.get('societe','?')}*"
        if s.get("num_stand"): text += f" · Stand {s['num_stand']}"
        text += f"\n{s.get('secteur','')}\n"
        if s.get("produits"): text += f"_{s['produits'][:60]}..._\n" if len(s.get("produits","")) > 60 else f"_{s['produits']}_\n"
        text += "\n"
    await u.message.reply_text(text, parse_mode="Markdown")

async def cmd_rapport(u, c):
    if db.count() == 0:
        await u.message.reply_text("⚠️ Aucune donnée. Commence par /stand"); return
    msg = await u.message.reply_text("⏳ Génération du rapport PDF...")
    try:
        pdf = generate_pdf()
        await u.message.reply_document(
            document=pdf, filename="SIAM_2025_Rapport.pdf",
            caption=f"📄 *SIAM 2025 — STIHL AF/ME*\n🏪 {db.count()} stands · Fiches + Tableau comparatif",
            parse_mode="Markdown"
        )
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Erreur : {e}")

async def cmd_reset(u, c):
    await u.message.reply_text("⚠️ Effacer tous les stands ?",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ OUI — Tout effacer", callback_data="reset_yes"),
            InlineKeyboardButton("❌ Annuler", callback_data="reset_no"),
        ]]))

async def cb_reset(u, c):
    q = u.callback_query; await q.answer()
    if q.data == "reset_yes": db.reset(); await q.edit_message_text("🗑 Tous les stands effacés.")
    else: await q.edit_message_text("✅ Annulé.")

async def cmd_cancel(u, c):
    await u.message.reply_text("❌ Saisie annulée.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ── /stand conversation ──────────────────────────────────
async def stand_start(u, c):
    c.user_data.clear()
    await u.message.reply_text(
        "🏪 *Nouveau stand*\n\nQuel est le *numéro du stand* ?\n_(ou /skip si tu ne l'as pas)_",
        parse_mode="Markdown", reply_markup=skip_kb()
    )
    return S_NUM

async def s_num(u, c):
    c.user_data["num_stand"] = fmt(u.message.text.strip())
    await u.message.reply_text("*Nom de la société / marque ?*", parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove())
    return S_SOC

async def s_soc(u, c):
    c.user_data["societe"] = u.message.text.strip()
    await u.message.reply_text(
        f"✅ *{c.user_data['societe']}*\n\nQuel est le *secteur* ?",
        parse_mode="Markdown", reply_markup=sec_kb()
    )
    return S_SEC

async def s_sec(u, c):
    c.user_data["secteur"] = u.message.text.strip()
    await u.message.reply_text(
        "Quels sont les *produits / machines* observés ?\n"
        "_Modèles, gammes, spécifications..._",
        parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )
    return S_PROD

async def s_prod(u, c):
    c.user_data["produits"] = u.message.text.strip()
    await u.message.reply_text("💰 *Prix relevés* ? (MAD / €)\n_(ou /skip)_",
        parse_mode="Markdown", reply_markup=skip_kb())
    return S_PRIX

async def s_prix(u, c):
    c.user_data["prix"] = fmt(u.message.text.strip())
    await u.message.reply_text(
        "⚔️ *Machines concurrentes à STIHL ?*\n"
        "_Modèles qui font face à nos produits_\n_(ou /skip)_",
        parse_mode="Markdown", reply_markup=skip_kb()
    )
    return S_CONC

async def s_conc(u, c):
    c.user_data["machines_conc"] = fmt(u.message.text.strip())
    await u.message.reply_text(
        "🔍 *Gap vs STIHL ?*\n"
        "_Machines / segments qu'ils ont et qu'on n'a pas_\n_(ou /skip)_",
        parse_mode="Markdown", reply_markup=skip_kb()
    )
    return S_GAP

async def s_gap(u, c):
    c.user_data["gap_stihl"] = fmt(u.message.text.strip())
    await u.message.reply_text("👤 *Contact ?* (nom, tél, email)\n_(ou /skip)_",
        parse_mode="Markdown", reply_markup=skip_kb())
    return S_CONT

async def s_cont(u, c):
    c.user_data["contact"] = fmt(u.message.text.strip())
    await u.message.reply_text("💡 *Remarque générale ?*\n_(ou /skip)_",
        parse_mode="Markdown", reply_markup=skip_kb())
    return S_REM

async def s_rem(u, c):
    d = c.user_data
    d["remarque"] = fmt(u.message.text.strip())
    db.add(d.get("num_stand",""), d.get("societe",""), d.get("secteur",""),
           d.get("produits",""), d.get("prix",""), d.get("machines_conc",""),
           d.get("gap_stihl",""), d.get("contact",""), d.get("remarque",""))

    summary = (
        f"✅ *Stand enregistré !*\n\n"
        f"🏪 *{d.get('societe','')}*"
        f"{' · Stand ' + d['num_stand'] if d.get('num_stand') else ''}\n"
        f"📂 {d.get('secteur','')}\n"
    )
    if d.get("produits"):     summary += f"📦 {d['produits'][:80]}\n"
    if d.get("prix"):         summary += f"💰 {d['prix']}\n"
    if d.get("machines_conc"): summary += f"⚔️ {d['machines_conc'][:60]}\n"
    if d.get("gap_stihl"):    summary += f"🔍 GAP: {d['gap_stihl'][:60]}\n"
    if d.get("contact"):      summary += f"👤 {d['contact']}\n"
    summary += f"\n_Total: {db.count()} stands · /stand pour continuer_"

    await u.message.reply_text(summary, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ── MAIN ────────────────────────────────────────────────
def main():
    from telegram.ext import ConversationHandler
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("voir", cmd_voir))
    app.add_handler(CommandHandler("rapport", cmd_rapport))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CallbackQueryHandler(cb_reset, pattern=r"^reset_"))

    TX = filters.TEXT & ~filters.COMMAND
    stand_conv = ConversationHandler(
        entry_points=[CommandHandler("stand", stand_start)],
        states={
            S_NUM:  [MessageHandler(TX, s_num)],
            S_SOC:  [MessageHandler(TX, s_soc)],
            S_SEC:  [MessageHandler(TX, s_sec)],
            S_PROD: [MessageHandler(TX, s_prod)],
            S_PRIX: [MessageHandler(TX, s_prix)],
            S_CONC: [MessageHandler(TX, s_conc)],
            S_GAP:  [MessageHandler(TX, s_gap)],
            S_CONT: [MessageHandler(TX, s_cont)],
            S_REM:  [MessageHandler(TX, s_rem)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )
    app.add_handler(stand_conv)

    print("🟢 Bot SIAM 2025 — Nouveau format démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

main()
