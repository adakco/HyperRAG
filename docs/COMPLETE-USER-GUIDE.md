# راهنمای کامل استفاده از HyperRAG

**Last Updated:** 2025-10-27  
**Version:** 1.0  
**Status:** Production Ready

---

## 📋 فهرست مطالب

1. [شروع سریع](#شروع-سریع)
2. [راه‌اندازی سیستم](#راه‌اندازی-سیستم)
3. [استفاده عملی](#استفاده-عملی)
4. [مثال‌های کاربردی](#مثال‌های-کاربردی)
5. [Monitoring و Debugging](#monitoring-و-debugging)

---

## 🚀 شروع سریع

### پیش‌نیازها
- Python 3.9+
- دسترسی به سرور 192.168.2.23 (برای Infrastructure)
- دسترسی به اینترنت (برای دانلود مدل‌ها)

### نصب سریع

```bash
# 1. کلون کردن پروژه
git clone <repository-url>
cd Hyper-RAG

# 2. شروع سرویس‌ها (تمام کارها اتوماتیک است!)
./start-services-host.sh

# 3. بررسی وضعیت
curl http://localhost:8000/health  # Ingestor
curl http://localhost:8002/health  # Retriever
```

---

## 🔧 راه‌اندازی سیستم

### حالت 1: Host Mode (توصیه می‌شود)

```bash
# همه سرویس‌ها روی localhost و infrastructure روی 192.168.2.23
./start-services-host.sh
```

**چه اتفاقی می‌افتد:**
1. ✅ 13 سرویس HyperRAG روی localhost شروع می‌شوند
2. ✅ اتصال به PostgreSQL، Redis، NATS، Qdrant، MinIO، Neo4j روی سرور
3. ✅ مدل‌های AI دانلود و آماده می‌شوند

**Ports:**
- 8000-8012:ควบคุม Services
- 192.168.2.23: Infrastructure

### حالت 2: Docker Mode

```bash
# اگر Docker نصب داری
./start-services.sh
```

---

## 📚 استفاده عملی

### 1. آپلود و پردازش سند

#### انگلیسی

```bash
# ساخت فایل تست
echo "Python is a high-level programming language. It is widely used in AI and data science." > test.txt

# آپلود سند
curl -X POST "http://localhost:8000/ingest" \
  -F "doc_id=python-guide-001" \
  -F "tenant=mycompany" \
  -F "project=docs" \
  -F "lang=en" \
  -F "title=Python Programming" \
  -F "file=@test.txt"

# پاسخ:
# {
#   "doc_id": "python-guide-001",
#   "version": 1730123456,
#   "status": "ingested",
#   "uri_raw": "s3://raw/mycompany/docs/python-guide-001/1730123456"
# }
```

#### فارسی

```bash
# ساخت فایل تست
echo "پایتون یک زبان برنامه‌نویسی سطح بالا است. این زبان در هوش مصنوعی و علم داده استفاده می‌شود." > test_fa.txt

# آپلود سند فارسی
curl -X POST "http://localhost:8000/ingest" \
  -F "doc_id=python-guide-fa-001" \
  -F "tenant=mycompany" \
  -F "project=docs" \
  -F "lang=fa" \
  -F "title=برنامه‌نویسی پایتون" \
  -F "file=@test_fa.txt"
```

### 2. جستجو و بازیابی

#### جستجوی ساده

```bash
curl -X POST "http://localhost:8002/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is Python?",
    "tenant": "mycompany",
    "project": "docs",
    "lang": "en",
    "limit": 5
  }'

# پاسخ: لیست نتایج مرتب شده بر اساس relevancy
```

#### جستجوی پیچیده با Re-ranking

```bash
curl -X POST "http://localhost:8002/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How is Python used in AI?",
    "tenant": "mycompany",
    "project": "docs",
    "lang": "en",
    "limit": 3,
    "rerank": true,
    "search_mode": "balanced"
  }'
```

#### جستجوی فارسی

```bash
curl -X POST "http://localhost:8002/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "پایتون چیست؟",
    "tenant": "mycompany",
    "project": "docs",
    "lang": "fa",
    "limit": 5
  }'
```

###  sensitive content

```bash
# استفاده از Knowledge Graph
curl -X POST "http://localhost:8012/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "knowledge-doc-001",
    "content": "Python is a programming language developed by Guido van Rossum. It is used by Google and Microsoft.",
    "tenant": "mycompany",
    "lang": "en"
  }'

# پاسخ:
# {
#   "entities_count": 3,
#   "relationships_count": 2,
#   "entities": [
#     {"label": "Python", "type": "ORG"},
#     {"label": "Guido van Rossum", "type": "PERSON"}
#   ]
# }
```

### 4. Context Packing

```bash
# بسته‌بندی چند context برای ارسال به LLM
curl -X POST "http://localhost:8009/pack" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the benefits of Python?",
    "contexts": [
      "Python is easy to learn",
      "Python has a large community",
      "Python is used in AI and data science"
    ],
    "lang": "en",
    "tenant": "mycompany",
    "max_tokens": 500
  }'
```

### 5. Memory Management

```bash
# ذخیره حافظه episod
curl -X POST "http://localhost:8010/store" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "mycompany",
    "content": "User asked about Python programming",
    "memory_type": "episodic",
    "lang": "en"
  }'

# جستجو در حافظه
curl -X POST "http://localhost:8010/retrieve" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant": "mycompany",
    "query": "What did the user ask before?",
    "memory_type": "episodic",
    "lang": "en"
  }'
```

---

## 💼 مثال‌های کاربردی

### سناریو 1: Chatbot با دانش پایه

```python
import requests
import json

# 1. آپلود مستندات آموزشی
documents = [
    "Python basics",
    "Python advanced",
    "Python for AI"
]

for doc in documents:
    with open(f"{doc}.txt", "rb") as f:
        response = requests.post(
            "http://localhost:8000/ingest",
            files={"file": f},
            data={
                "doc_id": f"course-{doc.lower().replace(' ', '-')}",
                "tenant": "academy",
                "project": "python-course",
                "lang": "en"
            }
        )
    print(f"Uploaded: {doc}")

# 2. پاسخ به سوال دانشجو
def answer_student_question(question):
    response = requests.post(
        "http://localhost:8002/retrieve",
        json={
            "query": question,
            "tenant": "academy",
            "project": "python-course",
            "lang": "en",
            "limit": 3
        }
    )
    results = response.json()
    return results["results"][0]["content"]

# استفاده
answer = answer_student_question("How do I create a list in Python?")
print(answer)
```

### سناریو 2: جستجوی چندزبانه

```python
import requests

def search_multilingual(query, language):
    """جستجوی چندزبانه"""
    response = requests.post(
        "http://localhost:8002/retrieve",
        json={
            "query": query,
            "tenant": "multilang",
            "project": "docs",
            "lang": language,
            "limit": 5
        }
    )
    return response.json()

# جستجو به انگلیسی
results_en = search_multilingual("What is machine learning?", "en")

# جستجو به فارسی
results_fa = search_multilingual("یادگیری ماشین چیست؟", "fa")
```

### سناریو 3: استخراج دانش از متون

```python
import requests

def extract_knowledge(text):
    """استخراج entities و relationships از متن"""
    response = requests.post(
        "http://localhost:8012/extract",
        json={
            "doc_id": f"knowledge-{int(time.time())}",
            "content": text,
            "tenant": "knowledge-base",
            "lang": "en"
        }
    )
    return response.json()

# استفاده
knowledge = extract_knowledge(
    "Apple was founded by Steve Jobs. It produces iPhones and MacBooks."
)

print(f"Found {knowledge['entities_count']} entities")
print(f"Found {knowledge['relationships_count']} relationships")

for entity in knowledge["entities"]:
    print(f"- {entity['label']} ({entity['type']})")
```

---

## 🔍 Monitoring و Debugging

### 1. وضعیت سرویس‌ها

```bash
# بررسی health همه سرویس‌ها
for port in 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010 8011 8012; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/health | jq -r '.status' || echo "FAILED"
done
```

### 2. مشاهده Metametrics

```bash
# مشاهده metrics هر سرویس
curl http://localhost:8002/metrics  # Retriever metrics
curl http://localhost:8004/metrics  # Embedder metrics
```

### 3. Grafana Monitoring

```
دسترسی: http://192.168.2.23:3001
User: admin
Pass: admin123

Dashboards:
- HyperRAG Overview
- HyperRAG Quality
- Service Graph
```

### 4. Logs

```bash
# مشاهده لاگ‌های سرویس‌ها
tail -f /tmp/hyperrag-ingestor.log
tail -f /tmp/hyperrag-retriever.log

# یا از Loki
curl http://192.168.2.23:3100/loki/api/v1/query
```

---

## 🎯 Best Practices

### 1. سازماندهی Documents

```bash
# برای هر tenant/project ساختار مشابه داشته باشید
tenant/project/doc_id

# مثال:
mycompany/technical-docs/python-basics
mycompany/faq/common-questions
```

### 2. مدیریت حافظه

```python
# برای هر session یک session_id منحصر به فرد استفاده کنید
session_id = f"user-{user_id}-session-{datetime.now()}"

# ذخیره context در حافظه
store_memory(
    tenant="mycompany",
    content=f"User context: {context}",
    session_id=session_id,
    memory_type="episodic"
)
```

### 3. بهینه‌سازی جستجو

```python
# برای queries کوتاه: search_mode="fast"
# برای queries پیچیده: search_mode="balanced"
# برای accuracy بالاتر: search_mode="thorough"

response = requests.post(
    "http://localhost:8002/retrieve",
    json={
        "query": "complex technical question",
        "search_mode": "thorough",  # بهتر است دقت بالاتر
        "rerank": True
    }
)
```

---

## 🆘 Troubleshooting

### مشکل 1: سرویس‌ها شروع نمی‌شوند

```bash
# بررسی PIDs
ps aux | grep hyperrag

# حذف تمام سرویس‌های قدیمی
./stop-services-host.sh

# شروع مجدد
./start-services-host.sh
```

### مشکل 2: جستجو نتیجه برنمی‌گرداند

```bash
# 1. بررسی اینکه document embedding شده
curl http://localhost:8000/documents/{doc_id}/status

# 2. بررسی Qdrant
curl http://192.168.2.23:6333/collections

# 3. تست دستی embedding
curl -X POST http://localhost:8004/embed \
  -H "Content-Type: application/json" \
  -d '{"doc_id": "test", "version": "1", ...}'
```

### مشکل 3: Timeout در جستجو

```bash
# افزایش timeout در client
timeout=60

# یا استفاده از search_mode="fast"
```

---

## 📊 Performance Tips

1. **استفاده از CACHE**
   - نتایج جستجوی متداول را cache کنید
   - Memory service برای session data

2. **Batch Processing**
   - چند document را باهم آپلود کنید
   - Embedding در batch انجام می‌شود

3. **Asynchronous Calls**
   - برای multiple queries از async استفاده کنید

4. **Monitoring**
   - مرتباً Grafana را چک کنید
   - Metrics را track کنید

---

## 🎉 خلاصه

سیستم HyperRAG آماده استفاده است! 

**سریع‌ترین راه:**
```bash
1. ./start-services-host.sh
2. آپلود سند
3. جستجو کن!
```

**Support:**
- Documentation: `docs/`
- Issues: GitHub Issues
- Email: support@hyperrag.ai

---

**ساخته شده با ❤️ برای جامعه AI**

