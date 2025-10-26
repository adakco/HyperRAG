# مستندات فنی فارسی - سیستم HyperRAG

**تاریخ به‌روزرسانی:** ۱۴۰۴/۰۸/۰۴  
**نسخه:** ۱.۰  
**وضعیت:** آماده تولید

---

## فهرست مطالب

1. [معرفی کلی](#معرفی-کلی)
2. [معماری سیستم](#معماری-سیستم)
3. [سرویس‌های اصلی](#سرویس‌های-اصلی)
4. [جریان داده](#جریان-داده)
5. [راهنمای استفاده](#راهنمای-استفاده)
6. [عیب‌یابی](#عیب‌یابی)

---

## معرفی کلی

HyperRAG یک سیستم **RAG** (Retrieval-Augmented Generation) مبتنی بر معماری میکروسرویس است که قابلیت پردازش و جستجوی هوشمند اسناد را برای سیستم‌های هوش مصنوعی فراهم می‌کند.

### ویژگی‌های کلیدی

- ✅ **پردازش چندزبانه**: پشتیبانی از فارسی و انگلیسی
- ✅ **معماری میکروسرویس**: ۱۲ سرویس مستقل
- ✅ **مقیاس‌پذیری**: قابلیت اجرا در محیط‌های کلود
- ✅ **امنیت**: جداسازی داده‌ها بر اساس tenant
- ✅ **مشاهده‌پذیری**: لاگ‌ها، متریک‌ها و tracing کامل

---

## معماری سیستم

### اجزای اصلی

#### ۱. سرویس‌های پردازش سند

- **Ingestor** (پورت ۸۰۰۰): دریافت و ذخیره اسناد
- **Normalizer** (پورت ۸۰۰۱): پاکسازی و نرمال‌سازی متن
- **Chunker** (پورت ۸۰۰۳): تقسیم متن به قطعات
- **Embedder** (پورت ۸۰۰۴): تبدیل متن به بردار

#### ۲. سرویس‌های جستجو و پردازش

- **Retriever** (پورت ۸۰۰۲): جستجوی هوشمند
- **Reranker** (پورت ۸۰۱۱): مرتب‌سازی مجدد نتایج
- **Evaluator** (پورت ۸۰۰۵): ارزیابی کیفیت پاسخ‌ها

#### ۳. سرویس‌های پشتیبان

- **Agent Orchestrator** (پورت ۸۰۰۶): هماهنگی agentها
- **Policy** (پورت ۸۰۰۷): مدیریت دسترسی
- **Costing** (پورت ۸۰۰۸): محاسبه هزینه‌ها
- **Pack Long-RAG** (پورت ۸۰۰۹): مدیریت contextهای طولانی
- **Memory** (پورت ۸۰۱۰): مدیریت حافظه مکالمه

### زیرساخت ذخیره‌سازی

- **MinIO**: ذخیره فایل‌های خام، پاکسازی و chunkشده
- **PostgreSQL**: ذخیره متادیتای سندها و chunks
- **Qdrant**: پایگاه داده برداری برای embeddings
- **Redis**: cache و session management
- **NATS**: پیام‌رسانی بین سرویس‌ها

---

## سرویس‌های اصلی

### ۱. سرویس Ingestion (دریافت سند)

**مسئولیت:** دریافت سند از کاربر و شروع فرایند پردازش

#### فرایند کار:

1. دریافت فایل از کاربر
2. محاسبه hash برای شناسایی duplicates
3. ذخیره در MinIO در مسیر: `s3://raw/{tenant}/{project}/{doc_id}/{version}`
4. ذخیره متادیتا در PostgreSQL
5. انتشار event `doc.ingested.v1` در NATS

#### نمونه استفاده:

```bash
curl -X POST http://localhost:8000/ingest \
  -F "doc_id=سند-تست-001" \
  -F "tenant=acme" \
  -F "project=alpha" \
  -F "lang=fa" \
  -F "file=@document.pdf"
```

#### پاسخ نمونه:

```json
{
    "doc_id": "سند-تست-001",
    "version": 1761400000,
    "status": "success",
    "uri_raw": "s3://raw/acme/alpha/سند-تست-001/1761400000",
    "sha256": "abc123...",
    "file_size": 12345
}
```

---

### ۲. سرویس Normalization (نرمال‌سازی)

**مسئولیت:** پاکسازی و نرمال‌سازی متن

#### فرایند کار:

1. دانلود فایل raw از MinIO
2. استخراج متن از فایل (PDF, Word, ...)
3. **تشخیص PII**: شناسایی اطلاعات شخصی (ایمیل، تلفن، ...)
4. **حذف PII**: حذف یا anonymize کردن اطلاعات حساس
5. **نرمال‌سازی**: 
   - فارسی: استفاده از کتابخانه Hazm
   - انگلیسی: پاکسازی استاندارد
6. ذخیره متن پاکسازی شده در: `s3://clean/{tenant}/clean/{doc_id}/{version}`

#### ویژگی خاص برای فارسی:

- استفاده از کتابخانه Hazm برای tokenization فارسی
- پشتیبانی از حروف کشیده و عربی
- نرمال‌سازی اعدادی و تاریخ‌ها

#### نمونه استفاده:

```bash
curl -X POST "http://localhost:8001/normalize?doc_id=سند-تست-001&version=1761400000&uri_raw=s3://raw/acme/alpha/سند-تست-001/1761400000&lang=fa&tenant=acme"
```

---

### ۳. سرویس Chunking (تقسیم سند)

**مسئولیت:** تقسیم متن به قطعات کوچک‌تر برای پردازش

#### فرایند کار:

1. دانلود متن پاکسازی شده از MinIO
2. **تقسیم هوشمند**:
   - **فارسی**: استفاده از sentence tokenization
   - **انگلیسی**: استفاده از recursive character splitter
3. محاسبه تعداد token برای هر chunk
4. ذخیره chunks به صورت JSON در: `s3://clean/{tenant}/chunked/{doc_id}/{version}`
5. ذخیره metadata در جداول `document_chunks` و `document_versions`

#### پارامترها:

- **Chunk Size**: ۵۰۰ token (قابل تنظیم)
- **Overlap**: ۵۰ token برای حفظ context

#### نمونه استفاده:

```bash
curl -X POST "http://localhost:8003/chunk?doc_id=سند-تست-001&version=1761400000&uri_clean=s3://clean/acme/clean/سند-تست-001/1761400000&lang=fa&tenant=acme"
```

---

### ۴. سرویس Embedding (تبدیل به بردار)

**مسئولیت:** تبدیل متن به بردارهای عددی برای جستجو

#### فرایند کار:

1. دانلود chunks از MinIO
2. **انتخاب مدل**:
   - **فارسی**: `HooshvareLab/bert-fa-base-uncased` (384 بعد)
   - **انگلیسی**: `text-embedding-3-large` (3072 بعد)
3. تبدیل هر chunk به بردار
4. ذخیره در Qdrant با metadata کامل
5. به‌روزرسانی PostgreSQL با ID بردارها

#### ساختار داده در Qdrant:

```python
{
    "id": "uuid",
    "vector": [0.1, 0.2, ...],
    "payload": {
        "chunk_id": "doc_id_version_index",
        "doc_id": "doc-001",
        "content": "chunk content...",
        "lang": "fa",
        "tenant": "acme",
        "project": "alpha"
    }
}
```

#### نمونه استفاده:

```bash
curl -X POST "http://localhost:8004/embed?doc_id=سند-تست-001&version=1761400000&uri_processed=s3://clean/acme/chunked/سند-تست-001/1761400000&lang=fa&tenant=acme&project=alpha"
```

---

### ۵. سرویس Retrieval (جستجو)

**مسئولیت:** جستجوی هوشمند در پایگاه داده برداری

#### فرایند کار:

1. تبدیل query به بردار با استفاده از مدل مناسب
2. **جستجوی Hybrid**:
   - **Dense Search**: جستجوی معنایی در Qdrant
   - **Sparse Search**: جستجوی واژه‌ای (BM25)
3. **فیلتر کردن**: بر اساس tenant، project، language
4. **RRF** (Reciprocal Rank Fusion): ترکیب نتایج
5. **Reranking**: مرتب‌سازی مجدد برای بهبود نتایج
6. بازگرداندن top-k نتایج

#### پارامترها:

- **k_dense**: تعداد نتایج جستجوی معنایی (پیش‌فرض: ۱۰)
- **k_sparse**: تعداد نتایج جستجوی واژه‌ای (پیش‌فرض: ۱۰)
- **k_final**: تعداد نتایج نهایی (پیش‌فرض: ۵)

#### نمونه استفاده:

```bash
curl -X POST http://localhost:8002/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "متن جستجو",
    "lang": "fa",
    "tenant": "acme",
    "project": "alpha",
    "k_dense": 10,
    "k_final": 5
  }'
```

#### نمونه پاسخ:

```json
{
    "query": "متن جستجو",
    "results": [
        {
            "chunk_id": "doc-001_1761400000_0",
            "content": "محتوای مرتبط...",
            "doc_id": "doc-001",
            "score": 0.95
        }
    ],
    "total": 5,
    "processing_time_ms": 350
}
```

---

## جریان داده

### جریان کامل Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                     ورود سند                                 │
└────────────────────┬────────────────────────────────────────┘
                     ▼
         ┌───────────────────────┐
         │   1. INGESTOR         │
         │   - دریافت فایل      │
         │   - محاسبه hash      │
         │   - ذخیره در MinIO   │
         └───────────┬───────────┘
                     │ Event: doc.ingested.v1
                     ▼
         ┌───────────────────────┐
         │   2. NORMALIZER       │
         │   - دانلود فایل       │
         │   - حذف PII           │
         │   - نرمال‌سازی متن   │
         │   - ذخیره text        │
         └───────────┬───────────┘
                     │ Event: doc.normalized.v1
                     ▼
         ┌───────────────────────┐
         │   3. CHUNKER          │
         │   - دانلود text       │
         │   - تقسیم به chunks   │
         │   - ذخیره chunks      │
         └───────────┬───────────┘
                     │ Event: doc.chunked.v1
                     ▼
         ┌───────────────────────┐
         │   4. EMBEDDER         │
         │   - دانلود chunks     │
         │   - تبدیل به بردار   │
         │   - ذخیره در Qdrant   │
         └───────────┬───────────┘
                     │ Event: doc.embedded.v1
                     ▼
         ┌───────────────────────┐
         │   5. RETRIEVER        │
         │   - جستجوی semantic   │
         │   - فیلتر results     │
         │   - بازگشت نتایج      │
         └───────────────────────┘
```

### مسیرهای ذخیره‌سازی در MinIO

```
bucket: raw/
  └── {tenant}/
      └── {project}/
          └── {doc_id}/
              └── {version}           # فایل خام

bucket: clean/
  ├── {tenant}/
  │   ├── clean/
  │   │   └── {doc_id}/
  │   │       └── {version}         # متن پاکسازی شده
  │   └── chunked/
  │       └── {doc_id}/
  │           └── {version}            # chunks به صورت JSON
```

### جداول دیتابیس PostgreSQL

```sql
-- جدول اصلی اسناد
CREATE TABLE documents (
    doc_id TEXT PRIMARY KEY,
    tenant TEXT NOT NULL,
    project TEXT NOT NULL,
    lang TEXT DEFAULT 'en',
    latest_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- جدول ورژن‌های سند
CREATE TABLE document_versions (
    doc_id TEXT,
    version TEXT,
    sha256 TEXT,
    uri_raw TEXT,
    uri_clean TEXT,
    lang TEXT DEFAULT 'en',
    chunk_count INTEGER,
    embedding_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (doc_id, version)
);

-- جدول chunks
CREATE TABLE document_chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    version TEXT NOT NULL,
    chunk_index INTEGER,
    content TEXT,
    lang TEXT,
    token_count INTEGER,
    embedding TEXT,  -- Qdrant point ID
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## راهنمای استفاده

### نصب و راه‌اندازی

```bash
# راه‌اندازی سرویس‌ها
./start-services-host.sh

# بررسی وضعیت
curl http://localhost:8000/health
```

### تست کامل Pipeline

```bash
# اجرای تست اتوماتیک
python3 test-complete-pipeline.py
```

### ورود یک سند فارسی

```bash
# Step 1: Ingestion
curl -X POST http://localhost:8000/ingest \
  -F "doc_id=test-fa-001" \
  -F "tenant=acme" \
  -F "project=alpha" \
  -F "lang=fa" \
  -F "file=@document.pdf"

# خروجی: doc_id, version, uri_raw

# Step 2-4: پردازش خودکار از طریق events

# Step 5: جستجو
curl -X POST http://localhost:8002/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "موضوع جستجو",
    "lang": "fa",
    "tenant": "acme",
    "project": "alpha",
    "k_dense": 10,
    "k_final": 5
  }'
```

---

## عیب‌یابی

### مشکل: سرویس‌ها پاسخ نمی‌دهند

```bash
# بررسی وضعیت سرویس‌ها
ps aux | grep ingestor

# ری‌استارت همه سرویس‌ها
./stop-services-host.sh
./start-services-host.sh
```

### مشکل: MinIO در دسترس نیست

```bash
# بررسی سلامت MinIO
curl http://192.168.2.23:9190/minio/health/live

# بررسی لیست bucketها
aws --endpoint-url=http://192.168.2.23:9190 s3 ls
```

### مشکل: PostgreSQL اتصال ندارد

```bash
# تست اتصال
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -c "SELECT NOW();"

# بررسی جداول
psql -h 192.168.2.23 -p 5442 -U adak -d heyperrag -c "\dt"
```

### مشکل: Qdrant بازگردانی نتایج ندارد

```bash
# بررسی collection
curl http://192.168.2.23:6333/collections

# بررسی points
curl -X POST "http://192.168.2.23:6333/collections/documents/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "with_payload": true, "filter": {"must": [{"key": "tenant", "match": {"value": "acme"}}]}}'
```

### مشکل: retriever صفر نتیجه برمی‌گرداند

**علل احتمالی:**
1. Project field در embedder تنظیم نشده
2. Filter ها در retriever با داده‌های ذخیره شده مطابقت ندارند
3. Query با محتوای ذخیره شده مطابقت معنایی ندارد

**راهکار:**
```bash
# بررسی payload در Qdrant
curl -X POST "http://192.168.2.23:6333/collections/documents/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 1, "with_payload": true}' | jq '.result.points[0].payload'

# باید شامل: tenant, project, lang باشد
```

---

## معیارهای عملکرد

### زمان‌بندی پیشنهادی (p95)

- **Ingestion**: < ۵۰۰ms
- **Normalization**: < ۵۰۰ms
- **Chunking**: < ۳۰۰ms
- **Embedding**: < ۶s
- **Retrieval**: < ۱۵۰۰ms

### ظرفیت سیستم

- **پشتیبانی از**: میلیون‌ها سند
- **جستجو**: زیر ۲ ثانیه
- **مقیاس**: افقی (horizontal scaling)
- **دسترس‌پذیری**: ۹۹.۹٪

---

## امنیت

### جداسازی داده‌ها

- **Multi-tenancy**: هر tenant داده‌های خود را دارد
- **Row-Level Security**: فیلتر در SQL
- **MinIO Prefixes**: جداسازی در سطح storage
- **Qdrant Filters**: فیلتر در payload

### حفاظت از اطلاعات

- **PII Detection**: شناسایی و حذف اطلاعات شخصی
- **SHA256 Verification**: جلوگیری از duplicates
- **ACL**: Access Control Lists
- **Audit Trail**: ثبت تمام عملیات

---

## خلاصه

این سیستم یک راهکار کامل برای پردازش و جستجوی هوشمند اسناد فارسی و انگلیسی است. با معماری میکروسرویس، قابلیت مقیاس‌پذیری، و پشتیبانی کامل از زبان فارسی، می‌تواند به عنوان هسته RAG در سیستم‌های بزرگ استفاده شود.

**مستندات بیشتر:**
- [Services-Documentation.md](Services-Documentation.md) - جزئیات سرویس‌ها
- [Service-Testing-Guide.md](Service-Testing-Guide.md) - راهنمای تست
- [Technical-Spec.md](Technical-Spec.md) - مشخصات فنی
- [Architecture.md](Architecture.md) - معماری

---

**تماس:** برای سوالات و پشتیبانی با تیم توسعه تماس بگیرید.

