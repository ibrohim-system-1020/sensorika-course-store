# Sensorika Course Store

Imtihon uchun kurs sotish loyihasi: FastAPI sayt + demo payment + admin tasdiqlashi + real Telegram Bot API.

## Oqim
1. User ro‘yxatdan o‘tadi va Telegram ID kiritadi.
2. Kursni tanlaydi.
3. `Sensorika Pay` DEMO checkout orqali test karta bilan to‘lov yuboradi.
4. Buyurtma `review` holatiga o‘tadi.
5. Admin `/admin` dan `Tasdiqlash` bosadi.
6. Bot real Telegram API orqali 30 daqiqalik join-request invite link yaratadi.
7. Userning order sahifasi har 2 soniyada statusni tekshiradi va link paydo bo‘lishi bilan avtomatik Telegram kanaliga yo‘naltiradi.
8. Bot faqat buyurtmadagi Telegram ID ni kanalga qabul qiladi va linkni revoke qiladi.

> Demo payment haqiqiy pul yechmaydi. U imtihonda payment workflow ko‘rsatish uchun.

## Windows o‘rnatish
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env -Force
```

`.env`:
```env
BOT_TOKEN=YANGI_BOT_TOKEN
PRIVATE_CHANNEL_ID=-1001234567890
SECRET_KEY=sensorika-super-secret-key
BASE_URL=http://127.0.0.1:8000
```

## Telegram
- Botni yopiq kanalga admin qiling.
- `Invite Users` / foydalanuvchi qo‘shish huquqini bering.
- User botga `/start` yozib o‘z Telegram ID sini oladi.

## Ishga tushirish
Terminal 1:
```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --reload
```

Terminal 2:
```powershell
.\.venv\Scripts\python.exe bot.py
```

Sayt: `http://127.0.0.1:8000`

Admin: `http://127.0.0.1:8000/admin`
- login: `admin`
- parol: `admin123`

## Test karta
Checkout avtomatik quyidagini ko‘rsatadi:
`8600 0000 0000 1234`

Bu faqat DEMO.
