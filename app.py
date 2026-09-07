import os
import re
import secrets
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from db import connect, init_db, hash_password, verify_password
from telegram_api import create_join_link, send_message, configured

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Sensorika Course Store")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "dev-secret-change-me"))
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

@app.on_event("startup")
def startup():
    init_db()


def current_user(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        return None
    con = connect()
    row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    con.close()
    return row


def need_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(401)
    return user


def need_admin(request: Request):
    user = need_user(request)
    if not user["is_admin"]:
        raise HTTPException(403)
    return user

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    con = connect()
    courses = con.execute("SELECT * FROM courses WHERE is_active=1").fetchall()
    con.close()
    return templates.TemplateResponse("index.html", {"request": request, "courses": courses, "user": current_user(request)})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "user": current_user(request), "error": None})

@app.post("/register", response_class=HTMLResponse)
def register(request: Request, full_name: str = Form(...), username: str = Form(...), password: str = Form(...), telegram_id: str = Form("")):
    if len(password) < 6:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Parol kamida 6 ta belgidan iborat bo‘lsin.", "user": None})
    try:
        tg = int(telegram_id) if telegram_id.strip() else None
    except ValueError:
        tg = None
    con = connect()
    try:
        cur = con.execute("INSERT INTO users(full_name,username,password_hash,telegram_id) VALUES(?,?,?,?)",
                          (full_name.strip(), username.strip().lower(), hash_password(password), tg))
        con.commit()
        request.session["user_id"] = cur.lastrowid
    except Exception:
        con.close()
        return templates.TemplateResponse("register.html", {"request": request, "error": "Bu username band.", "user": None})
    con.close()
    return RedirectResponse("/", 303)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None, "user": current_user(request)})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    con = connect()
    u = con.execute("SELECT * FROM users WHERE username=?", (username.strip().lower(),)).fetchone()
    con.close()
    if not u or not verify_password(password, u["password_hash"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Login yoki parol xato.", "user": None})
    request.session["user_id"] = u["id"]
    return RedirectResponse("/admin" if u["is_admin"] else "/", 303)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", 303)

@app.post("/buy/{course_id}")
def buy(course_id: int, request: Request):
    user = need_user(request)
    if not user["telegram_id"]:
        return RedirectResponse("/profile?need_tg=1", 303)
    con = connect()
    course = con.execute("SELECT * FROM courses WHERE id=? AND is_active=1", (course_id,)).fetchone()
    if not course:
        con.close()
        raise HTTPException(404)
    active = con.execute(
        "SELECT id FROM orders WHERE user_id=? AND course_id=? AND status IN ('pending','review','paid') ORDER BY id DESC LIMIT 1",
        (user["id"], course_id),
    ).fetchone()
    if active:
        oid = active["id"]
    else:
        cur = con.execute("INSERT INTO orders(user_id,course_id,amount) VALUES(?,?,?)", (user["id"], course_id, course["price"]))
        con.commit()
        oid = cur.lastrowid
    con.close()
    return RedirectResponse(f"/order/{oid}", 303)

@app.get("/order/{order_id}", response_class=HTMLResponse)
def order_page(order_id: int, request: Request):
    user = need_user(request)
    con = connect()
    order = con.execute("""
        SELECT o.*, c.title course_title, u.telegram_id FROM orders o
        JOIN courses c ON c.id=o.course_id JOIN users u ON u.id=o.user_id
        WHERE o.id=? AND o.user_id=?
    """, (order_id, user["id"])).fetchone()
    con.close()
    if not order:
        raise HTTPException(404)
    return templates.TemplateResponse("order.html", {"request": request, "order": order, "user": user})

@app.post("/order/{order_id}/demo-pay")
def demo_pay(
    order_id: int,
    request: Request,
    payment_method: str = Form(...),
    card_number: str = Form(...),
):
    """Imtihon uchun DEMO payment gateway: haqiqiy pul yechilmaydi."""
    user = need_user(request)
    method = payment_method.upper().strip()
    if method not in {"UZCARD", "HUMO", "VISA"}:
        method = "DEMO CARD"
    digits = re.sub(r"\D", "", card_number)
    if len(digits) < 4:
        return RedirectResponse(f"/order/{order_id}?pay_error=1", 303)
    last4 = digits[-4:]

    con = connect()
    order = con.execute("SELECT * FROM orders WHERE id=? AND user_id=?", (order_id, user["id"])).fetchone()
    if not order:
        con.close()
        raise HTTPException(404)
    if order["status"] not in ("pending", "rejected"):
        con.close()
        return RedirectResponse(f"/order/{order_id}", 303)

    payment_ref = f"SP-{order_id:05d}-{secrets.token_hex(3).upper()}"
    con.execute("""
        UPDATE orders
        SET status='review', payment_method=?, payment_last4=?, payment_ref=?,
            payment_submitted_at=CURRENT_TIMESTAMP, invite_link=NULL
        WHERE id=?
    """, (method, last4, payment_ref, order_id))
    con.commit()
    con.close()
    return RedirectResponse(f"/order/{order_id}?submitted=1", 303)

@app.get("/api/order/{order_id}")
def order_status(order_id: int, request: Request):
    user = need_user(request)
    con = connect()
    o = con.execute(
        "SELECT status, invite_link, payment_ref FROM orders WHERE id=? AND user_id=?",
        (order_id, user["id"]),
    ).fetchone()
    con.close()
    if not o:
        raise HTTPException(404)
    return JSONResponse(dict(o))

@app.get("/profile", response_class=HTMLResponse)
def profile(request: Request):
    user = need_user(request)
    con = connect()
    orders = con.execute("""
        SELECT o.*, c.title course_title FROM orders o JOIN courses c ON c.id=o.course_id
        WHERE o.user_id=? ORDER BY o.id DESC
    """, (user["id"],)).fetchall()
    con.close()
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "orders": orders})

@app.post("/profile/telegram")
def update_telegram(request: Request, telegram_id: int = Form(...)):
    user = need_user(request)
    con = connect()
    con.execute("UPDATE users SET telegram_id=? WHERE id=?", (telegram_id, user["id"]))
    con.commit()
    con.close()
    return RedirectResponse("/profile", 303)

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    admin_user = need_admin(request)
    con = connect()
    orders = con.execute("""
        SELECT o.*, u.full_name, u.username, u.telegram_id, c.title course_title
        FROM orders o JOIN users u ON u.id=o.user_id JOIN courses c ON c.id=o.course_id
        ORDER BY o.id DESC
    """).fetchall()
    con.close()
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user": admin_user,
            "orders": orders,
            "bot_configured": configured(),
            "telegram_error": request.query_params.get("error") == "telegram",
        },
    )

@app.post("/admin/order/{order_id}/approve")
def approve(order_id: int, request: Request):
    need_admin(request)
    con = connect()
    o = con.execute("""
        SELECT o.*,u.telegram_id,c.title course_title FROM orders o
        JOIN users u ON u.id=o.user_id JOIN courses c ON c.id=o.course_id WHERE o.id=?
    """, (order_id,)).fetchone()
    if not o:
        con.close()
        raise HTTPException(404)
    if o["status"] == "paid":
        con.close()
        return RedirectResponse("/admin", 303)
    if o["status"] != "review":
        con.close()
        return RedirectResponse("/admin", 303)

    if not configured():
        con.close()
        return RedirectResponse("/admin?error=telegram", 303)

    try:
        link = create_join_link(f"order-{order_id}")
        if not link:
            raise RuntimeError("Invite link yaratilmagan")
    except Exception:
        con.close()
        return RedirectResponse("/admin?error=telegram", 303)

    con.execute(
        "UPDATE orders SET status='paid', invite_link=?, paid_at=CURRENT_TIMESTAMP WHERE id=?",
        (link, order_id),
    )
    con.commit()
    con.close()

    if o["telegram_id"]:
        text = (
            f"✅ To‘lov tasdiqlandi!\n"
            f"Kurs: {o['course_title']}\n\n"
            f"Yopiq kanalga kirish havolasi (30 daqiqa):\n{link}"
        )
        try:
            send_message(o["telegram_id"], text)
        except Exception:
            pass
    return RedirectResponse("/admin", 303)

@app.post("/admin/order/{order_id}/reject")
def reject(order_id: int, request: Request):
    need_admin(request)
    con = connect()
    con.execute("UPDATE orders SET status='rejected', invite_link=NULL WHERE id=?", (order_id,))
    con.commit()
    con.close()
    return RedirectResponse("/admin", 303)
