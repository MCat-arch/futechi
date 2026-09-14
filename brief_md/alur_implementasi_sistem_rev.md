# Alur Implementasi Sistem Deteksi Kesehatan Ayam
## FCOS-Lite (Edge) + LangGraph Terpadu (Image Extraction + GraphRAG)

> Dokumen ini menjelaskan alur implementasi keseluruhan sistem, dibagi per phase.
> **Catatan pemisahan sumber:** bagian yang berasal dari paper asli ditandai
> `[PAPER]`; bagian yang merupakan pengembangan/tambahan di luar paper ditandai
> `[TAMBAHAN]`. Ini penting agar batas antara metode tervalidasi dan hipotesis
> desain tetap jelas.

---

## Ringkasan Perubahan Arsitektur Terbaru

Perubahan kunci dari rancangan sebelumnya: **VLM bukan lagi modul terpisah dalam
pipeline linear (A→B→C)**, melainkan menjadi **node di dalam satu LangGraph yang
sama dengan GraphRAG**. Ekstraksi image-ke-teks dan reasoning diagnosis kini hidup
dalam satu orkestrasi state graph, bukan layanan-layanan terpisah yang dirangkai
manual.

Model tahap pertama untuk node ekstraksi: **GLM-5.3-Flash** (natively multimodal,
Zhipu/Z.ai, rilis 26 Agustus 2026, MIT license, dapat self-host atau via API).

---

## PHASE 1 — Model Deteksi Visual (Edge Vision) `[PAPER]`

**Tujuan:** menghasilkan model FCOS-Lite terlatih & terkuantisasi untuk deteksi
+ klasifikasi biner (healthy/sick) per frame di sensor IMX500.

### 1.1 Arsitektur model (tidak diubah dari paper)
- Backbone: MobileNetV2
- Neck: FPN 3-level (P3/P4/P5, stride 8/16/32)
- Head: Dethead (shared antar level, tanpa centerness)
- Input: 320×320×3 → output: cls (2ch: healthy/sick) + reg (4ch: l,t,r,b)

### 1.2 Loss function (sesuai paper)
- Klasifikasi: Gradient Weighting Loss / WCE (µ=0.7)
- Lokalisasi: CIoU Loss
- `L_det = L_WCE + L_CIoU`

### 1.3 Training pipeline (sesuai paper)
1. Latih Teacher (FCOS + ResNet50), 40 epoch
2. Latih Student (FCOS-Lite) baseline, 40 epoch
3. Knowledge Distillation: Teacher (frozen) → Student, 50 epoch
   - `L = L_focal + L_global + L_det`
4. Pilih model terbaik berdasarkan mAP + F1 di validation set

### 1.4 Deployment (sesuai paper)
- Export PyTorch → TFLite → kuantisasi int8 (~3.3MB)
- Deploy ke logic chip IMX500

### Status pengerjaan
- [x] Arsitektur student (fcos_lite_model.py)
- [x] Target assignment + training loop (fcos_lite_train.py)
- [ ] Ganti dataset dummy → dataset asli (video rekaman sendiri, Futechi Farm)
- [ ] Bangun & latih teacher (ResNet50)
- [ ] Knowledge distillation
- [ ] Export TFLite int8

### Catatan jujur
Model ini HANYA menghasilkan label biner (healthy/sick) + bbox. Ia TIDAK
mengekstrak fitur tekstural spesifik (warna jengger, tekstur bulu) — itu tugas
node ekstraksi di Phase 4. Kontribusi FCOS-Lite terhadap diagnosis akhir sebatas
**lokalisasi + gerbang biner** (kapan memicu pipeline hilir), bukan mengurangi
beban analisis visual node ekstraksi.

---

## PHASE 2 — Edge Orchestration (Host Raspberry Pi) `[TAMBAHAN]`

**Tujuan:** menyaring noise sesaat & menyiapkan kandidat frame berkualitas
sebelum dikirim ke server. Semua berjalan di HOST BOARD (Pi 4B/5), BUKAN di dalam
chip IMX500 (chip itu hanya menjalankan inferensi neural network).

> **Catatan sumber:** seluruh Phase 2 adalah tambahan di luar paper. Paper asli
> langsung mengeluarkan metadata per-frame tanpa temporal logic. Namun paper asli
> secara eksplisit membuka opsi mengirim gambar/ROI (bukan hanya byte) khusus
> untuk kasus unhealthy — jadi Phase 2 memanfaatkan opsi yang sudah disediakan
> penulis, bukan menyimpang darinya.

### 2.1 Terima metadata per-frame
IMX500 → host via bus CSI-2: `{bbox, class, confidence}` per frame @~27fps.
IMX500 sendiri TIDAK punya interface jaringan — host wajib ada untuk relay data
keluar (ini juga kondisi di paper asli: IMX500 dipasang dengan Pi 4B / Pi Zero 2W).

### 2.2 IoU Tracking (kontinuitas identitas individu)
- Referensi metode: SORT (Simple Online and Realtime Tracking) — asosiasi
  detection-ke-track via IoU antar-frame berurutan.
- **Kenapa perlu:** FCOS-Lite mendeteksi tiap ayam per-frame (spasial), TAPI
  tidak punya identitas lintas-waktu (temporal). Tanpa tracking, debounce di 2.3
  bisa keliru menghitung 3 ekor berbeda sebagai 1 kasus konsisten.
- **Peringatan:** ini berlawanan filosofi PoultryFI (yang sengaja menghindari
  tracking individu). Pilihan desain yang disengaja menyimpang dari rujukan itu.
- Kondisi kandang baterai berdesakan (dari dataset paper) justru menaikkan risiko
  salah-asosiasi → tracking makin penting, bukan makin bisa diabaikan.

### 2.3 Debounce State Machine
- **Fungsi:** menyaring false-positive sesaat (motion blur, oklusi sekilas) SEBELUM
  memicu proses hilir yang mahal (node ekstraksi + graph).
- **Aturan:** "sick" dianggap terkonfirmasi jika muncul di **≥3 dari 5 sample**
  dalam jendela **3–5 detik**, per-track (bukan per-frame, bukan per-kandang).
- Sampling untuk debounce boleh turun ke ~1–2 fps (tidak perlu semua 27 frame).
- **State per track:** count "sick" sejauh ini, waktu mulai window, waktu window
  berakhir, status trigger.
- Referensi prinsip: temporal event-validation / multi-frame confirmation via IoU
  (pola umum di video object detection untuk menekan false alarm).
- **Catatan:** angka 3/5 & jendela 3-5 detik adalah parameter desain, BELUM
  divalidasi empiris di literatur. Perlu diuji sendiri.

### 2.4 Frame Selection (pilih 3 frame terbaik dari track terkonfirmasi)
Kriteria seleksi:
1. Confidence deteksi FCOS-Lite tertinggi
2. Bbox paling utuh (tidak terpotong tepi frame) — `[referensi ADA]`
3. Blur score terendah via varians Laplacian (Pech-Pacheco 2000) — `[referensi ADA]`

- Jumlah default: **3 frame** (ganjil → majority vote tanpa tie). Boleh naik ke 5
  hanya untuk kasus anomaly sangat tinggi/ambigu.
- **Catatan:** angka "3" & kriteria "confidence tertinggi" untuk seleksi frame
  BELUM ada referensi validasinya — parameter desain.

### 2.5 Crop RoI + padding
- Crop dari bbox hasil deteksi (bukan full frame).
- Padding **relatif** terhadap ukuran bbox (bukan piksel absolut), ~20–30%.
- Ambil dari **buffer resolusi native** IMX500 (hingga 4056×3040), BUKAN dari
  input 320×320 — fitur dual-output IMX500 (tensor inferensi + frame native
  dikirim bersamaan via CSI-2) `[referensi dokumentasi resmi ADA]`.
- Alasan: 320×320 cukup untuk bbox tapi terlalu rendah untuk detail tekstur
  bulu/warna jengger yang dibutuhkan node ekstraksi.
- **Catatan:** prinsip "padding relatif, jangan crop ketat" didukung literatur
  (ClipGrader pakai 1.2–1.5× ukuran box); tapi angka pas 20-30% adalah hipotesis,
  perlu diuji.
- Cek tabrakan dengan bbox individu lain setelah padding → kecilkan padding atau
  tandai `neighbor_present=true`.

### 2.6 Local Queue + Retry
- Simpan crop+metadata ke storage lokal dulu, kirim ulang saat koneksi pulih.
- **Kritis untuk reliability** — peternakan sering internet tidak stabil. Tanpa
  ini, kasus sakit bisa hilang saat koneksi putus.

### 2.7 Kirim payload ke server
- Protokol: HTTP POST atau MQTT (event-driven, bukan streaming).
- Payload: `{crops[3], track_id, confidence, timestamp, env_data (opsional)}`

---

## PHASE 3 — Server Ingestion & Preprocessing `[TAMBAHAN]`

**Tujuan:** menerima payload & menyiapkan frame untuk masuk ke LangGraph state.

1. Endpoint menerima payload (HTTP/MQTT)
2. Preprocessing frame:
   - Resize sesuai kebutuhan input GLM-5.3-Flash
   - Normalisasi warna/kontras
   - (Opsional) deblur/enhancement ringan
3. Bentuk objek state awal LangGraph:
   `{crops, case_id, track_id, confidence, timestamp, env_data}`

---

## PHASE 4 — LangGraph Terpadu (Image Extraction Node + GraphRAG) `[TAMBAHAN]`
### ← INTI PERUBAHAN ARSITEKTUR

Bukan lagi "VLM lalu RAG" (pipeline linear), tapi **satu graph** dengan beberapa
node yang berbagi satu state. Ini mengubah topologi dari pipeline linear menjadi
graph terorkestrasi.

### Struktur Graph

```
              ┌───────────────────────────────────────────────┐
              │              LangGraph State                    │
              │  {crops, case_id, extracted_features,           │
              │   kg_context, diagnosis, confidence,            │
              │   recommendation, requires_manual_review}       │
              └───────────────────────────────────────────────┘

[ENTRY]
   │
   ▼
┌────────────────────────────┐
│ Node 1: Image→Text          │  Model: GLM-5.3-Flash (tahap pertama)
│ Extraction                  │  - input: 3 crops resolusi native
│                             │  - ekstrak fitur semantik: warna jengger,
│                             │    tekstur bulu (irregular_feather_appearance),
│                             │    postur, dll. + confidence per fitur
│                             │  - agregasi antar-3-frame (majority/rata-rata)
│                             │  - tulis extracted_features ke state
└────────────┬───────────────┘
             │
             ▼ (conditional edge)
      ┌──────────────────┐
      │ Fitur cukup &     │── tidak ──► set requires_manual_review=true
      │ ter-mapping?      │             → Fallback Template → [OUTPUT]
      └──────┬───────────┘
             │ ya
             ▼
┌────────────────────────────┐
│ Node 2: GraphRAG Retrieval  │  - query knowledge graph penyakit (Cypher)
│                             │    berdasarkan extracted_features
│                             │  - ambil kandidat Disease + relasi
│                             │    (HAS_VISUAL_FEATURE, HAS_SYMPTOM,
│                             │     ASSOCIATED_WITH_ENVIRONMENT, dll.)
│                             │  - tulis kg_context ke state
└────────────┬───────────────┘
             │
             ▼ (conditional edge)
      ┌──────────────────┐
      │ kg_context kosong?│── ya ──► Fallback Template → [OUTPUT]
      └──────┬───────────┘
             │ tidak
             ▼
┌────────────────────────────┐
│ Node 3: Diagnosis Reasoning │  - LLM reasoning diferensial
│                             │  - input: extracted_features + kg_context
│                             │    (+ env_data jika ada)
│                             │  - output: diagnosis diferensial + confidence
└────────────┬───────────────┘
             │
             ▼
┌────────────────────────────┐
│ Node 4: Recommendation      │  - sintesis rekomendasi tindakan/mitigasi
│                             │    + treatment (dosis, withdrawal period)
└────────────┬───────────────┘
             │
             ▼
         [OUTPUT] → dashboard / notifikasi peternak
```

### Keuntungan struktur graph vs pipeline linear
- **Conditional edges:** jika ekstraksi Node 1 ambigu, graph bisa loop balik
  minta frame tambahan atau eskalasi ke model lebih besar. Frasa "tahap pertama
  pakai GLM-5.3-Flash" mengisyaratkan routing bertingkat — struktur graph
  memudahkan ini.
- **Shared state:** semua node baca/tulis state yang sama, tidak perlu passing
  manual antar-layanan.
- **Ekstensibilitas:** mudah tambah node (mis. node fusi sensor lingkungan)
  tanpa membongkar pipeline.

### Peringatan jujur
- "Tahap pertama" mengisyaratkan tahap kedua — kriteria eskalasi BELUM
  ditentukan. Risiko over-engineering: lebih baik mulai dengan Flash saja, ukur
  dulu, baru tambah tahap lanjut kalau terbukti perlu.
- GLM-5.3-Flash sangat baru (rilis ~3 minggu lalu per dokumen ini), benchmark
  independen minim, klaim performa sebagian besar dari vendor. Risiko untuk
  sistem diagnosis produksi. Kelebihan: MIT + self-host + murah (kontrol biaya
  & privasi data farm).
- Error compounding lintas node tetap ada: salah baca fitur di Node 1 diwarisi
  Node 2-4. Struktur graph tidak otomatis menyelesaikan ini; malah menambah
  titik kegagalan baru (routing logic).

---

## PHASE 5 — Integrasi Data Lingkungan (opsional) `[TAMBAHAN]`

- Sensor suhu/kelembapan/amonia dibaca mikrokontroler terpisah (mis. ESP32),
  BUKAN disatukan ke arsitektur model vision.
- Masuk sebagai **node tambahan** di graph yang sama (late fusion di level state),
  memberi konteks lingkungan ke Node 3 (reasoning).
- Pola late fusion ini konsisten dengan PoultryFI (AAM/PPFM menggabungkan
  modalitas di level fitur/output, bukan di dalam satu model).
- **Catatan:** PoultryFI TIDAK memasang sensor amonia (hanya suhu/kelembapan);
  penambahan amonia adalah ekstensi Anda, ambang bahaya perlu ditentukan dari
  literatur sendiri.

---

## Tabel Ringkas: Sama vs Beda dari Paper Asli

| Aspek                         | Status              |
|-------------------------------|---------------------|
| Arsitektur & training model   | `[PAPER]` identik   |
| Kuantisasi & deploy IMX500    | `[PAPER]` identik   |
| Inferensi per-frame           | `[PAPER]` identik   |
| Host board wajib              | `[PAPER]` sama (Pi) |
| IoU tracking                  | `[TAMBAHAN]` baru   |
| Debounce state machine        | `[TAMBAHAN]` baru   |
| Frame selection + crop        | `[TAMBAHAN]` baru   |
| Kirim gambar (bukan byte)     | `[TAMBAHAN]` — opsi paper |
| Tier server                   | `[TAMBAHAN]` baru   |
| LangGraph (extraction+RAG)    | `[TAMBAHAN]` baru   |
| Basis pengetahuan penyakit    | `[TAMBAHAN]` baru   |

## Peringatan Akhir soal Validasi

Akurasi end-to-end pipeline gabungan ini **belum pernah divalidasi di manapun**.
Angka mAP 94.3% dari paper hanya mengukur deteksi biner, BUKAN akurasi diagnosis
diferensial akhir. Jangan asumsikan sistem akhir seakurat FCOS-Lite — yang diukur
bukan hal yang sama. Error tiap tahap berpotensi terakumulasi (false negative
FCOS-Lite = kasus tidak pernah sampai ke graph sama sekali).
