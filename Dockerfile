# استخدام نسخة بايثون رسمية وخفيفة
FROM python:3.10-slim

# تثبيت ffmpeg وهو ضروري لدمج الصوت والفيديو وتحويل MP3
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ ملفات المشروع بالكامل
COPY . .

# إنشاء مجلد التحميلات (اختياري لأن الكود ينشئه تلقائياً)
RUN mkdir -p downloads && chmod 777 downloads

# تحديد البورت (Render يستخدم غالباً 10000 أو يكتشفه تلقائياً)
EXPOSE 10000

# تشغيل التطبيق باستخدام gunicorn (أفضل في الإنتاج من Flask السريع)
# تم رفع الـ timeout لأن عمليات التحميل والدمج تأخذ وقتاً
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app", "--timeout", "600"]
