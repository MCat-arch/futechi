# Alur Sistem Terpadu: Futechi Poultry GraphRAG-Vet
## FCOS-Lite (Edge) → Server Intake → LangGraph Terpadu (Ekstraksi Citra + GraphRAG) → Aplikasi & Konfirmasi

> Dokumen ini **menggabungkan**:
> - `alur_implementasi_sistem_rev.md` (terbaru: FCOS-Lite, edge orchestration, LangGraph terpadu)
> - `flow-sistem-poultry-graphrag-vet.md` (case lifecycle, Modul A/B/C, konfirmasi user, ontologi)
> - keputusan yang **sudah tertanam di kode** branch `langgraph` tapi belum tertulis di kedua dokumen di atas
>
> Jika dua sumber bertentangan dan `_rev` bicara eksplisit → `_rev` dipakai.
> Jika sumber diam / ambigu / bertentangan dengan kode → **ditinggalkan sebagai opsi** di
> [Bagian 0.2 — Keputusan Terbuka](#02-keputusan-terbuka-perlu-anda-putuskan) dengan kode `K#`.
> Di badan dokumen, titik yang menunggu keputusan ditandai **⚠️ K#**.

### Label sumber
| Label | Arti |
|---|---|
| `[PAPER-FCOS]` | Dari paper FCOS-Lite asli (arsitektur, training, deploy IMX500) — metode tervalidasi |
| `[PAPER-GRV]` | Dari desain GraphRAG-Vet asli (hard constraint, multi-hop, refusal) |
| `[TAMBAHAN]` | Pengembangan di luar paper — hipotesis desain, perlu diuji |
| `[IMPL]` | Keputusan yang sudah ada di kode (`src/futechi_graphrag`) tapi belum ada di dokumen desain lama |

---

## 0. Asumsi & Keputusan Terbuka

### 0.1 Asumsi (dibawa dari flow lama — masih perlu konfirmasi pakar vet/pemilik produk)

| # | Asumsi | Alasan |
|---|---|---|
| A1 | "Sehat" = false alarm murni. "Tidak Sakit" = ada anomali teramati tapi bukan penyakit (stres sesaat, postur wajar). Keduanya masuk exclusion, kategori dicatat terpisah. | Kualitas feedback loop KG & evaluasi ekstraksi |
| A2 | Jika case sudah dikonfirmasi sebelum sesi deteksi ke-2 di hari yang sama, sesi ke-2 untuk cage tsb **di-skip**. | Cage yang sudah settled tidak perlu dideteksi ulang |
| A3 | Deteksi ulang pada case yang masih pending **menambah alert pada case yang sama** (evidence digabung), bukan case baru. | Mencegah case duplikat |

### 0.2 Keputusan Terbuka (perlu Anda putuskan)

Setiap item: opsi, konsekuensi, dan rekomendasi saya. Rekomendasi hanya saran — dokumen di bawah
ditulis mengikuti rekomendasi supaya tetap bisa dibaca utuh, tapi mudah diganti.

#### K1 — Jadwal deteksi: terjadwal atau kontinu?
Flow lama: **2 sesi/hari** (pagi & sore; sudah jadi enum `DetectionSession` di kode, dan A2/A3 bergantung padanya).
`_rev`: tidak menyebut jadwal, mendeskripsikan inferensi ~27 fps (terkesan kontinu).

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| **A (rekomendasi)** | Tetap 2 sesi terjadwal; FCOS-Lite + tracking + debounce hanya aktif selama sesi | A2/A3, cooldown "N siklus", enum kode tetap valid. Hemat daya & bandwidth |
| B | Kontinu 24 jam | Deteksi lebih cepat, tapi A2, cooldown per-siklus, `DetectionSession` harus didefinisikan ulang (mis. jendela waktu) |
| C | Kontinu di edge, tapi pengiriman ke server dibatch per sesi | Kompromi; logika dedup server tetap berbasis sesi |

#### K2 — Pergerakan kamera & identifikasi `cage_id`
Flow lama: kamera **menyapu** tiap cage, posisi dari **rotary encoder**.
`_rev`: IMX500 + Pi, tidak menyebut kamera bergerak/statis maupun cara mendapat `cage_id`.

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| **A (rekomendasi)** | Kamera bergerak di rel; rotary encoder → `cage_id`; kamera **berhenti (dwell) ±5 detik** per cage | Cocok dengan debounce 3–5 detik & 5 sampel. Butuh kontrol motor + sinkronisasi encoder ↔ frame |
| B | Kamera statis per blok; `cage_id` dari pemetaan posisi bbox ke region cage (kalibrasi sekali) | Tanpa mekanik, tapi 1 kamera melihat banyak cage → risiko salah-asosiasi naik, sudut pandang terbatas |

#### K3 — Unit case: 1 cage = 1 ekor, atau banyak ekor per cage?
Kode & flow lama: **1 cage = 1 ekor** (`CageStatus` docstring), case di-key `cage_id`.
`_rev`: IoU tracking karena kandang baterai **berdesakan** (banyak ekor), ada `neighbor_present`.

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| **A (rekomendasi, jika fisik kandang memang 1 ekor/cage)** | 1 cage = 1 ekor. Tracking tetap dipakai untuk memastikan 5 sampel berasal dari individu yang sama & membuang tetangga yang masuk frame | Kode domain tidak berubah. `track_id` hanya metadata edge |
| B | Banyak ekor/cage; case tetap per `cage_id`, beberapa track sakit digabung sebagai evidence case yang sama | Exclusion satu cage mengecualikan semua ekor di dalamnya (ayam sehat ikut ter-exclude) |
| C | Banyak ekor/cage; case per individu (`cage_id` + `track_id`) | Identitas individu lintas sesi **tidak stabil** (track_id hilang saat kamera pindah) → dedup A3 & cooldown hampir tidak mungkin tanpa re-ID |

#### K4 — Aturan gerbang multi-frame saat sampel valid < 3
`_rev`: "sick" terkonfirmasi jika **≥3 dari 5 sampel** per-track (tanpa konfirmasi → tidak dikirim).
Flow lama: jika <3 frame valid (ayam keluar frame) → **tetap lanjut** dengan `capture_quality: "low"`.

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| A | Ketat: <3 sampel valid → tidak trigger, catat di log edge | Lebih sedikit false alarm, risiko false negative naik |
| **B (rekomendasi)** | Trigger jika semua sampel valid (min. 2) berlabel sick → kirim dengan `capture_quality: "low"`; Node ekstraksi & reasoning diberi flag kehati-hatian | Menjaga semangat flow lama (jangan hilangkan kasus), tetap ada sinyal kualitas |
| C | Perpanjang dwell / ambil 2–3 sampel tambahan sebelum memutuskan | Hanya mungkin jika K2=A; menambah durasi sapuan |

#### K5 — Di mana cek status cage (Exclusion Store) dilakukan?
Flow lama: "sebelum case dibuat" (terkesan di edge). `_rev`: tidak dibahas; edge hanya kirim payload.

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| **A (rekomendasi)** | Di **server** saat intake; edge selalu kirim event terkonfirmasi | Satu sumber kebenaran (CaseStore). Log background saat cooldown & safety-net ≥3 anomali otomatis bisa dihitung di server. Edge tetap sederhana |
| B | Edge menarik daftar cage excluded sebelum sesi, tidak memotret cage tsb | Hemat bandwidth, tapi safety-net cooldown tidak bisa jalan (anomali tidak pernah terkirim) & bermasalah saat offline |
| C | Hybrid: edge skip hanya `EXCLUDED_SICK`; cooldown tetap dikirim | Hemat untuk cage yang sedang ditreatment, safety-net tetap jalan |

Turunannya: `case_id` dibuat **server** (edge hanya mengirim `event_id`), karena keputusan buat/gabung case ada di server.

#### K6 — Granularitas node ekstraksi & mapping di LangGraph
`_rev`: satu "Node 1: Image→Text Extraction" (termasuk agregasi 3 frame).
Kode: Modul A sudah dipecah jadi `mllm_extractor` (menggantikan `vlm_extractor` — tidak ada layanan VLM terpisah, MLLM dipanggil lewat client LLM yang sama), `canonical_mapper`, `frame_aggregator`, `confidence_filter`, `sensor_normalizer`, `mapping_validator`. Urutan di kode: ekstraksi → canonical mapping per frame → agregasi mayoritas → filter confidence.

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| **A (rekomendasi)** | 2 node: `image_extraction` (panggil model) + `semantic_mapping` (deterministik: agregasi → filter → canonical → validasi) | Sesuai file Modul A yang ada; node model bisa diganti/di-eskalasi tanpa menyentuh mapping; retry mapping (Bagian 4.4) jadi edge yang jelas |
| B | 1 node gabungan seperti `_rev` | Graph lebih ringkas, tapi loop "cek ulang mapping" harus memanggil ulang model atau disimpan manual |

#### K7 — Node Recommendation: generatif (LLM) atau deterministik?
`_rev`: "Node 4: Recommendation — **sintesis** rekomendasi + treatment (dosis, withdrawal period)".
Kode `[IMPL]`: checks, mitigasi, obat, severity, peringatan wajib lapor dibangun **deterministik dari graph** (`deterministic_builders.py`); LLM hanya menulis `differential_note` + `overall_uncertainty`.

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| **A (rekomendasi)** | Node 4 deterministik (tanpa LLM) | Dosis & withdrawal period tidak mungkin di-halusinasi; konsisten dengan hard constraint #6 flow lama |
| B | Node 4 LLM mensintesis teks rekomendasi dari graph | Teks lebih natural, tapi membuka permukaan halusinasi di data paling berisiko (obat) |
| C | Data tetap deterministik, LLM hanya membuat ringkasan naratif pendek di atasnya (field terpisah, bukan pengganti) | Kompromi; perlu validasi bahwa ringkasan tidak menyebut obat/dosis di luar data |

#### K8 — Tampilan rekomendasi: satu tahap atau dua tahap?
Flow lama: **satu tahap**, semua (checks + mitigasi + obat) tampil sekaligus.
Kode `[IMPL]` (`Case.resolve()`): **two-stage reveal** — saat pending hanya `related_conditions` + `recommended_checks`; mitigasi + obat baru dibuka setelah user tekan **Sakit** dan memilih penyakit.

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| A | Satu tahap (flow lama) | Peternak langsung dapat informasi obat; risiko memberi obat untuk penyakit yang belum tentu benar |
| **B (rekomendasi — sudah di kode)** | Dua tahap (kode) | User dipandu memeriksa dulu; tombol Sakit wajib memilih penyakit (`confirmed_condition`) |
| C | Hibrida: mitigasi non-medis (ventilasi, isolasi) tampil langsung; obat hanya setelah konfirmasi | Tindakan aman bisa segera dilakukan, obat tetap tergated. Perlu ubah `Case.attach_reasoning_result` |

#### K9 — Bentuk "confidence" pada output diagnosis
`_rev`: Node 3 output "diagnosis diferensial **+ confidence**".
Flow lama & kode: **tanpa skor numerik**, `definitive_diagnosis = null`, `overall_uncertainty` berupa teks.

| Opsi | Keterangan |
|---|---|
| **A (rekomendasi)** | Tidak ada angka; `overall_uncertainty` berupa level kategorikal (`low/medium/high`) + alasan teks — sesuai kode & aturan #4 |
| B | Angka confidence per kandidat dari LLM | Bertentangan dengan hard constraint "jangan beri skor buatan"; angka LLM tidak terkalibrasi |

#### K10 — Integrasi data lingkungan
Flow lama: `raw_environment` ikut di payload edge; dinormalisasi di Modul A; dipakai di **Cypher** (`ASSOCIATED_WITH_ENVIRONMENT`) dan prompt.
`_rev` Phase 5: **opsional**, sensor dibaca ESP32 terpisah, masuk sebagai node tambahan (late fusion) ke **Node 3 (reasoning) saja**.
Kode: `EnvironmentSnapshot` wajib di `Case`, dan `build_diagnostic_prompt` memformatnya tanpa cek `None`.

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| **A (rekomendasi)** | ESP32 terpisah → server menyimpan time-series; node `environment_fusion` mengambil bacaan terdekat berdasar `zone_id/blok_id + detected_at` **sebelum** retrieval | Lingkungan tetap bisa jadi filter di Cypher; edge vision tidak tergantung sensor; opsional (boleh kosong) |
| B | Literal `_rev`: lingkungan hanya konteks Node 3 | Cypher tidak memakai `environment_conditions` → relasi `ASSOCIATED_WITH_ENVIRONMENT` hanya terlihat LLM lewat konteks |
| C | Pi edge membaca sensor dan menyisipkan ke payload (flow lama) | Paling sederhana, tapi mengikat sensor ke unit kamera |

Apa pun opsinya: `EnvironmentSnapshot` dan prompt builder harus menerima nilai kosong. Ambang amonia harus dari literatur sendiri (PoultryFI tidak memakai sensor amonia).

#### K11 — Perilaku saat ekstraksi ambigu (routing bertingkat)
`_rev` menyebut conditional edge bisa "loop balik minta frame tambahan atau eskalasi ke model lebih besar", tapi kriteria eskalasi **belum ada**.

| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| **A (rekomendasi untuk MVP)** | Tidak ada eskalasi: ambigu → `requires_manual_review` + fallback template | Paling sederhana; ukur dulu seberapa sering ambigu |
| B | Eskalasi server-side ke model multimodal lebih besar (crop yang sama) | Tanpa kanal balik ke edge; perlu kriteria (mis. unmapped > X% atau semua fitur < 0.6) & anggaran biaya |
| C | Minta frame tambahan dari edge | Butuh kanal perintah server→edge; sesi/kamera kemungkinan sudah pindah cage — sulit jika K2=A |

#### K12 — Cara memanggil model ekstraksi untuk 3 crop
| Opsi | Keterangan | Konsekuensi |
|---|---|---|
| **A (rekomendasi)** | 3 panggilan (per crop) → `frame_aggregator` (majority / rata-rata confidence) | Sesuai flow lama & kode; agregasi transparan dan bisa diuji |
| B | 1 panggilan multi-image, model mengembalikan fitur teragregasi | Lebih murah & cepat, tapi agregasi jadi "kotak hitam" model |

#### K13 — Model LLM untuk reasoning (Node 5) & chat
Belum ditentukan di dokumen mana pun.

| Opsi | Keterangan |
|---|---|
| A | GLM-5.3-Flash juga untuk reasoning teks (satu model, self-host, murah) |
| B | Model teks terpisah yang lebih kuat untuk reasoning & chat |
| C | Konfigurabel lewat `settings.py` / `LLMClient`, diputuskan setelah evaluasi — **(rekomendasi)** |

#### K14 — Preprocessing citra di server
`_rev` Phase 3: resize, **normalisasi warna/kontras**, deblur opsional.
Risiko: warna jengger/pial adalah **fitur diagnostik** — normalisasi warna agresif dapat mengubah bukti.

| Opsi | Keterangan |
|---|---|
| **A (rekomendasi)** | Hanya resize (+ format/encoding); tanpa normalisasi warna/deblur. Simpan crop asli untuk audit |
| B | White-balance terkalibrasi (target referensi warna di kandang), tanpa normalisasi kontras |
| C | Sesuai `_rev` (normalisasi warna/kontras + deblur) — perlu uji bahwa fitur warna tidak bergeser |

#### K15 — Protokol edge → server
| Opsi | Keterangan |
|---|---|
| A | HTTP POST (multipart crop + JSON metadata) — mudah, cocok dengan retry queue lokal |
| B | MQTT (metadata) + upload objek terpisah untuk crop — event-driven, lebih hemat saat banyak device |

#### K16 — Penamaan lokasi: `zone_id` vs `blok_id`
Flow lama & `reasoner.py` memakai `zone_id`; entitas `Case` memakai `blok_id`.

| Opsi | Keterangan |
|---|---|
| A | Satu nama saja (pilih `blok_id` atau `zone_id`), refactor sisanya |
| B | Keduanya ada dengan hierarki eksplisit (mis. `zone` ⊃ `blok` ⊃ `cage`) |

---

## 1. Arsitektur Tingkat Tinggi

```
┌──────────────────────────────┐    ┌───────────────────────────────────────────┐    ┌─────────────────────────┐
│ EDGE (per kandang/blok)       │    │ SERVER                                     │    │ APLIKASI USER            │
│                               │    │                                            │    │                          │
│ IMX500  ── FCOS-Lite int8     │    │ [Phase 3] Intake                           │    │ Daftar Alert (cage_id)   │
│   │ {bbox,class,conf}/frame   │    │   ├─ validasi & simpan crop                │    │  - severity, alert_count │
│   │ + frame resolusi native   │    │   ├─ cek status cage (CaseStore/Exclusion) │    │                          │
│   ▼ (CSI-2)                   │    │   │   skip / log / merge / case baru       │    │ Detail Card              │
│ Host Pi 4B/5                  │    │   └─ preprocessing & init state            │    │  - related_conditions    │
│   ├─ jadwal sesi    ⚠️K1      │    │                │                           │───▶│  - recommended_checks    │
│   ├─ cage_id        ⚠️K2      │HTTP│                ▼                           │    │  - (mitigasi+obat) ⚠️K8  │
│   ├─ IoU tracking (SORT)      │/MQTT  [Phase 4] LangGraph diagnostic_graph      │    │                          │
│   ├─ debounce ≥3/5  ⚠️K4      │───▶│   ekstraksi → mapping → env → retrieval    │    │ Tombol konfirmasi        │
│   ├─ pilih 3 frame terbaik    │⚠️K15   → reasoning → rekomendasi / fallback    │    │ [Sakit][Tidak Sakit]     │
│   ├─ crop RoI + padding       │    │                │                           │    │ [Sehat]                  │
│   └─ local queue + retry      │    │                ▼                           │◀───│                          │
│                               │    │ CaseStore + Exclusion Store + Audit Trail  │    │ Chat lanjutan per case   │
│ ESP32 sensor lingkungan ⚠️K10 │───▶│ [Phase 6] State machine & policies         │◀──▶│  (chat_graph)            │
└──────────────────────────────┘    │ [Phase 7] Feedback store                   │    └─────────────────────────┘
                                     │ Neo4j Knowledge Graph                      │
                                     └───────────────────────────────────────────┘
```

Perubahan kunci dibanding flow lama:
- Detektor edge: **YOLO + anomaly_score → FCOS-Lite biner (healthy/sick) di IMX500**.
- Modul A → B → C bukan lagi pipeline linear yang dirangkai manual, melainkan **node-node dalam satu LangGraph** yang berbagi state.
- Model ekstraksi citra tahap pertama: **GLM-5.3-Flash** (multimodal, MIT, self-host/API).

---

## PHASE 1 — Model Deteksi Visual (Edge Vision) `[PAPER-FCOS]`

**Tujuan:** model FCOS-Lite terlatih & terkuantisasi untuk deteksi + klasifikasi biner (healthy/sick) per frame di sensor IMX500.

### 1.1 Arsitektur (tidak diubah dari paper)
- Backbone MobileNetV2; Neck FPN 3-level (P3/P4/P5, stride 8/16/32); Head Dethead shared, tanpa centerness
- Input 320×320×3 → output cls (2ch: healthy/sick) + reg (4ch: l,t,r,b)

### 1.2 Loss
- Klasifikasi: Gradient Weighting Loss / WCE (µ=0.7); Lokalisasi: CIoU
- `L_det = L_WCE + L_CIoU`

### 1.3 Training
1. Teacher (FCOS + ResNet50), 40 epoch
2. Student (FCOS-Lite) baseline, 40 epoch
3. Knowledge distillation Teacher (frozen) → Student, 50 epoch — `L = L_focal + L_global + L_det`
4. Pilih model terbaik berdasarkan mAP + F1 validation

### 1.4 Deployment
- PyTorch → TFLite → int8 (~3.3 MB) → logic chip IMX500

### 1.5 Batas kontribusi model
FCOS-Lite **hanya** menghasilkan label biner + bbox, bukan fitur tekstural (warna jengger, tekstur bulu).
Perannya: **lokalisasi + gerbang biner** (kapan memicu pipeline hilir). Analisis visual semantik tetap tugas node ekstraksi (Phase 4).
Konsekuensi: false negative FCOS-Lite = kasus tidak pernah sampai ke server.

### Status
- [x] Arsitektur student (`fcos_lite_model.py`)
- [x] Target assignment + training loop (`fcos_lite_train.py`)
- [ ] Ganti dataset dummy → video rekaman sendiri (Futechi Farm)
- [ ] Bangun & latih teacher (ResNet50)
- [ ] Knowledge distillation
- [ ] Export TFLite int8

---

## PHASE 2 — Edge Orchestration (Host Raspberry Pi) `[TAMBAHAN]`

**Tujuan:** menyaring noise sesaat & menyiapkan kandidat frame berkualitas sebelum dikirim ke server.
Semua berjalan di **host board** (Pi 4B/5), bukan di IMX500 (chip hanya menjalankan inferensi; tidak punya interface jaringan).

> Paper asli langsung mengeluarkan metadata per frame tanpa temporal logic, tapi membuka opsi mengirim gambar/ROI khusus kasus unhealthy — Phase 2 memanfaatkan opsi itu.

### 2.1 Siklus sesi deteksi ⚠️ K1, K2
```
Untuk setiap sesi terjadwal (pagi / sore):
  Untuk setiap cage di jalur sapuan:
    1. Rotary encoder → cage_id                                  (K2 = A)
    2. Kamera berhenti ±5 detik (dwell)
    3. Jalankan 2.2 → 2.7 untuk cage ini
    4. Lanjut ke cage berikutnya
```
Status cage **tidak** dicek di edge (K5 = A); semua event terkonfirmasi dikirim, server yang memutuskan.

### 2.2 Terima metadata per frame
IMX500 → host via CSI-2: `{bbox, class, confidence}` @~27 fps, **bersamaan** dengan frame resolusi native (dual-output IMX500).

### 2.3 IoU Tracking (kontinuitas identitas) ⚠️ K3
- Metode rujukan: **SORT** — asosiasi deteksi-ke-track via IoU antar-frame.
- Kenapa perlu: FCOS-Lite tidak punya identitas lintas waktu; tanpa tracking, debounce bisa menghitung beberapa ekor berbeda sebagai satu kasus konsisten.
- Jika K3 = A (1 ekor/cage): track utama = track yang bbox-nya berada di region cage aktif; track lain (tetangga yang masuk frame) diabaikan.
- Catatan: berlawanan dengan filosofi PoultryFI (menghindari tracking individu) — penyimpangan disengaja.

### 2.4 Debounce state machine (menggantikan "rata-rata anomaly_score 5 frame" flow lama) ⚠️ K4
- Sampling turun ke ~1 fps → **5 sampel** dalam jendela **3–5 detik**, per track.
- **Aturan:** `sick` terkonfirmasi jika muncul di **≥3 dari 5 sampel**.
- Sampel di mana track hilang (ayam keluar frame/oklusi) = **tidak valid**, bukan "healthy".
- Jika sampel valid < 3 → perilaku sesuai K4 (rekomendasi: trigger dengan `capture_quality: "low"` bila semua sampel valid sick).
- State per track: `sick_count`, `valid_count`, `window_start`, `window_end`, `triggered`.
- Tidak terkonfirmasi → tidak ada tindakan, lanjut ke cage berikutnya.
- Parameter 3/5 & 3–5 detik **belum divalidasi empiris** — perlu diuji.

### 2.5 Frame selection — 3 frame terbaik dari track terkonfirmasi
Kriteria (urutan prioritas):
1. Confidence `sick` FCOS-Lite tertinggi
2. Bbox paling utuh (tidak terpotong tepi frame)
3. Blur terendah — varians Laplacian (Pech-Pacheco 2000)

- Default **3 frame** (ganjil → majority vote tanpa tie); boleh 5 untuk kasus sangat ambigu.
- Angka "3" & kriteria confidence tertinggi = parameter desain, belum ada referensi validasi.

### 2.6 Crop RoI + padding
- Crop dari bbox, diambil dari **buffer resolusi native** IMX500 (hingga 4056×3040), bukan input 320×320.
- Padding **relatif** ~20–30% ukuran bbox (ClipGrader memakai 1.2–1.5×; angka pas masih hipotesis).
- Setelah padding, cek tabrakan dengan bbox individu lain → kecilkan padding atau set `neighbor_present = true`.

### 2.7 Local queue + retry
- Simpan crop + metadata ke storage lokal dulu, kirim ulang saat koneksi pulih (internet peternakan tidak stabil).
- Idempoten: setiap event punya `event_id` unik supaya pengiriman ulang tidak membuat case ganda.

### 2.8 Payload edge → server ⚠️ K15
```json
{
  "event_id": "EVT-PI03-20260824-081500-B40",
  "device_id": "PI03",
  "cage_id": "B40",
  "blok_id": "Z3",
  "detection_session": "morning",
  "detected_at": "2026-08-24T08:15:00+07:00",
  "track_id": 17,
  "debounce": {"sick_count": 4, "valid_count": 5},
  "mean_sick_confidence": 0.84,
  "capture_quality": "high",
  "neighbor_present": false,
  "crops": ["IMG-001a.jpg", "IMG-001b.jpg", "IMG-001c.jpg"],
  "crop_meta": [
    {"fcos_confidence": 0.91, "bbox_complete": true, "laplacian_var": 212.4}
  ]
}
```
- `case_id` **tidak** dibuat di edge (K5).
- `mean_sick_confidence` menggantikan `anomaly_score` flow lama (hanya informasi, bukan threshold utama — gerbangnya debounce).
- `raw_environment` tidak ada di payload jika K10 = A/B; ada jika K10 = C.
- Nama `blok_id` / `zone_id` → K16.

---

## PHASE 3 — Server Intake, Dedup & Preprocessing `[TAMBAHAN]`

**Tujuan:** menerima event, memutuskan nasib case, menyiapkan state awal LangGraph.

### 3.1 Terima & simpan
1. Endpoint menerima payload (HTTP/MQTT).
2. Cek `event_id` sudah pernah diproses → jika ya, abaikan (idempoten).
3. Simpan crop asli untuk audit trail.

### 3.2 Cek status cage sebelum membuat case
```
IF cage.status == EXCLUDED_SICK (masih masa treatment)
    → SKIP: tidak buat case, tidak alert
      (catat di log background)

ELSE IF cage.status == COOLDOWN
    → Catat anomali di log background (tidak dialert)
    → IF ini anomali ke-3 selama cooldown
        → ESKALASI paksa ke petugas sebagai priority_review (6.3 Safety-Net)

ELSE IF ada case belum resolved untuk cage ini
        (PENDING_CONFIRMATION atau UNCONFIRMED_ESCALATED)
    → Bukan case baru: jalankan diagnostic_graph untuk evidence baru,
      lalu Case.merge_new_detection(): alert_count++, fitur digabung,
      snapshot lingkungan terbaru, last_detected_at diperbarui
    → Kirim NOTIFIKASI ULANG

ELSE IF case untuk cage ini sudah resolved HARI INI
    → SKIP (A2)

ELSE
    → Buat CASE BARU (status DETECTED) → jalankan Phase 4
```
> Catatan untuk merge: apakah graph dijalankan ulang atas **gabungan** fitur lama+baru (hasil reasoning menggantikan yang lama) atau hanya menambah evidence tanpa reasoning ulang, belum ditentukan di kedua dokumen. Saran: jalankan ulang atas fitur gabungan agar `related_conditions` konsisten dengan evidence terbaru.

### 3.3 Preprocessing ⚠️ K14
- Resize sesuai input GLM-5.3-Flash.
- (Tergantung K14) normalisasi warna/kontras, deblur ringan — **hati-hati terhadap fitur warna jengger**.

### 3.4 Bentuk state awal LangGraph
```
{case_id, cage_id, blok_id, detection_session, detected_at, track_id,
 crops, capture_quality, neighbor_present, status: "processing"}
```

---

## PHASE 4 — LangGraph Diagnostic Graph (Ekstraksi Citra + GraphRAG) `[TAMBAHAN]` `[PAPER-GRV]`
### ← INTI PERUBAHAN ARSITEKTUR

Satu graph dengan node-node berbagi satu state. Riwayat kandang **tidak** dimasukkan di graph ini (hanya di chat, lihat 5.3) `[IMPL]`.

### 4.1 State
```
PipelineState
  # identitas & input
  case_id, cage_id, blok_id, detection_session, detected_at
  crops, capture_quality, neighbor_present
  raw_environment                   # opsional (K10)
  # hasil ekstraksi & mapping
  raw_frame_features                # per crop, dari model
  visual_features                   # [{name, confidence}] setelah agregasi+filter+canonical
  unmapped_features, unmapped_ratio_exceeded
  environment_conditions            # status semantik, mis. humidity_attention
  # retrieval
  graph_context, retrieval_retry_count
  # reasoning & rekomendasi
  related_conditions                # + differential_note
  overall_uncertainty
  recommended_checks, disease_actions, severity, notifiable_notice
  # kontrol
  requires_manual_review
  status: processing | insufficient_data | manual_review | done
```
(`state.py` saat ini baru memuat sebagian field ini.)

### 4.2 Struktur graph (mengikuti rekomendasi K6, K7, K10, K11)

```
[ENTRY]
   │
   ▼
┌────────────────────────────────┐
│ N1 image_extraction             │  Model: GLM-5.3-Flash (tahap pertama)     ⚠️K12, K13
│                                 │  - input: 3 crop resolusi native
│                                 │  - output per crop: fitur semantik + confidence
│                                 │    (warna jengger, irregular_feather_appearance,
│                                 │     lowered_head_posture, dll.)
│                                 │  - flag capture_quality=low diteruskan ke prompt
└──────────────┬─────────────────┘
               ▼
┌────────────────────────────────┐
│ N2 semantic_mapping             │  Deterministik (Modul A)                   ⚠️K6
│                                 │  1. agregasi antar-frame (majority / rata-rata)
│                                 │  2. buang fitur confidence < 0.6 (dihapus, bukan didowngrade)
│                                 │  3. canonical mapping (dictionary + fuzzy/synonym)
│                                 │  4. validasi terhadap ontology allowlist
└──────────────┬─────────────────┘
               ▼
┌────────────────────────────────┐
│ N3 environment_fusion (opsional)│  raw value → status semantik via threshold  ⚠️K10
│                                 │  (boleh kosong; node tidak boleh gagal)
└──────────────┬─────────────────┘
               ▼ (conditional edge)
      ┌─────────────────────────────┐
      │ visual_features kosong ATAU  │── ya ──► requires_manual_review = true ──► FB
      │ unmapped > 50% total fitur?  │
      └──────────────┬──────────────┘
                     │ tidak
                     ▼
┌────────────────────────────────┐
│ N4 graph_retrieval              │  Template Cypher terparameterisasi (4.3)
│                                 │  multi-kandidat sekaligus, tanpa gating treatment
└──────────────┬─────────────────┘
               ▼ (conditional edge)
      ┌─────────────────────────────┐
      │ graph_context kosong?        │── ya, retry = 0 ──► N2' remap (cek ulang canonical
      └──────────────┬──────────────┘                     + synonym) ──► N4 (sekali lagi)
                     │                 ── ya, retry = 1 ──► FB
                     │ tidak
                     ▼
┌────────────────────────────────┐
│ N5 differential_reasoning       │  LLM constrained (Modul C, reasoner.reason)  ⚠️K9, K13
│                                 │  HANYA menulis differential_note per kandidat
│                                 │  + overall_uncertainty
└──────────────┬─────────────────┘
               ▼
┌────────────────────────────────┐
│ N6 recommendation_builder       │  Deterministik, tanpa LLM                     ⚠️K7
│                                 │  - evidence string per kandidat
│                                 │  - recommended_checks (union, dedup)
│                                 │  - disease_actions (mitigasi + obat per penyakit)
│                                 │  - severity (worst-case antar kandidat)
│                                 │  - notifiable_notice (wajib lapor)
└──────────────┬─────────────────┘
               ▼
┌────────────────────────────────┐        ┌────────────────────────────────┐
│ N7 persist_case                 │◀───────│ FB fallback_template            │
│  - Case.attach_reasoning_result │        │  respons statis, non-generatif  │
│    (atau mark_insufficient_data │        │  status insufficient_data       │
│     dari FB)                    │        └────────────────────────────────┘
│  - status → PENDING_CONFIRMATION│
│  - kirim notifikasi             │
└──────────────┬─────────────────┘
               ▼
             [END]
```

Keuntungan dibanding pipeline linear: conditional edge (fallback, retry mapping, eskalasi K11), shared state tanpa passing manual, dan node baru (mis. eskalasi model, fusi sensor) bisa ditambah tanpa membongkar alur.

### 4.3 Template Cypher (N4) `[PAPER-GRV]` dimodifikasi
```cypher
MATCH (d:Disease)-[hf:HAS_VISUAL_FEATURE]->(vf:VisualFeature)
WHERE vf.name IN $visual_features
  AND NOT d.id IN $recently_excluded_diseases   // opsional
OPTIONAL MATCH (d)-[hs:HAS_SYMPTOM]->(s:Symptom)
OPTIONAL MATCH (d)-[ae:ASSOCIATED_WITH_ENVIRONMENT]->(ec:EnvironmentalCondition)
  WHERE ec.name IN $environment_conditions
OPTIONAL MATCH (d)-[:REQUIRES_INSPECTION]->(ia:InspectionAction)
OPTIONAL MATCH (d)-[mb:MITIGATED_BY]->(ma:MitigationAction)
OPTIONAL MATCH (d)-[tw:TREATED_WITH]->(mt:MedicalTreatment)
RETURN d, hf, vf, hs, s, ae, ec, ia, mb, ma, tw, mt
LIMIT 20
```
- Semua kandidat Disease diambil sekaligus → bahan multi-hop differential reasoning.
- Atribut relasi (`specificity`, `onset_stage`, `mechanism`) = pengganti scoring numerik.
- Tidak ada gating pada `TREATED_WITH` saat retrieval; gating tampilan diatur di K8.
- Fallback minimal: **1× retry** (cek ulang canonical + synonym → jalankan ulang template), bukan self-correction Cypher 3× seperti GraphRAG-Vet asli.

### 4.4 Hard constraints LLM `[PAPER-GRV]` `[IMPL]`
Berlaku untuk N5 dan chat (`prompt_constraints.BASE_RULES`):
1. Gunakan HANYA case data dan graph context yang diberikan.
2. Jangan mengarang gejala, penyakit, atau relasi graf.
3. Jangan menyimpulkan diagnosis pasti (`definitive_diagnosis` selalu `null`).
4. Kandidat tumpang tindih → jelaskan perbedaan dari specificity/onset_stage/mechanism — **tanpa angka skor buatan**.
5. Nama penyakit di `differential_note` wajib persis sama dengan nama kandidat.
6. Informasi obat bersifat referensi; wajib pengawasan dokter hewan/petugas terlatih.
7. Bedakan fakta teramati (`observed_anomalies`) vs kemungkinan (`related_conditions`).

Khusus N5 (`DIAGNOSTIC_SYSTEM_PROMPT`):
8. Hanya isi `differential_note` & `overall_uncertainty`; field lain sudah dibangun dari graph.
9. Jawab hanya dalam format terstruktur.

Aturan flow lama yang kini dijamin **secara struktural** oleh N6 & FB, bukan oleh prompt:
- graph_context kosong → `insufficient_data` (FB, LLM tidak dipanggil)
- withdrawal_period tampil apa adanya dari graph
- recommended_checks hanya dari `InspectionAction`; mitigasi hanya dari `MitigationAction`

### 4.5 Contoh konteks untuk N5
```
Kandang: B40, Blok/Zona: Z3
Sesi: pagi, capture_quality: high
Fitur visual teramati:
- lowered_head_posture (confidence: 0.88)
- irregular_feather_appearance (confidence: 0.74)
Lingkungan: suhu 30.5°C, kelembapan 76%, amonia 22ppm
Kondisi perhatian: humidity_attention, ammonia_attention

Kandidat penyakit dari knowledge graph:
[Disease A]
  - lowered_head_posture: specificity=high, onset_stage=early, mechanism=...
  - lingkungan humidity_attention: strength=medium
[Disease B]
  - lowered_head_posture: specificity=low, onset_stage=middle, mechanism=...
```

### 4.6 Output case (setelah N7)
```json
{
  "case_id": "CASE-20260824-B40-01",
  "status": "pending_confirmation",
  "severity": {"level": "medium", "computed_from": "max over candidates: base_severity × worst onset_stage"},
  "observed_anomalies": ["lowered_head_posture", "irregular_feather_appearance"],
  "related_conditions": [
    {
      "name": "Disease A",
      "evidence": ["lowered_head_posture (high specificity, early stage)"],
      "differential_note": "Lebih didukung dibanding Disease B karena specificity tinggi & muncul di tahap awal"
    },
    {
      "name": "Disease B",
      "evidence": ["lowered_head_posture (low specificity, middle stage)"],
      "differential_note": "Kurang didukung, gejala ini kurang spesifik untuk penyakit ini"
    }
  ],
  "definitive_diagnosis": null,
  "recommended_checks": ["observe_breathing", "check_nasal_discharge"],
  "notifiable_notice": null,
  "overall_uncertainty": "medium — dua kandidat bergejala tumpang tindih, perlu konfirmasi manual",

  "_disease_actions (internal, dibuka sesuai K8)": {
    "Disease A": {
      "mitigations": [{"action": "increase_ventilation", "priority": "high"}],
      "medical_references": [{
        "treatment": "{drug_name}", "dosage": "...", "withdrawal_period": "7 hari",
        "disclaimer": "Informasi referensi, gunakan dengan pengawasan pihak berwenang"
      }]
    }
  }
}
```

### 4.7 Fallback template (FB)
Respons tetap, non-generatif:
```json
{
  "case_id": "CASE-20260824-B40-01",
  "status": "insufficient_data",
  "requires_manual_review": true,
  "message": "Tidak ditemukan kecocokan kondisi terverifikasi di knowledge graph. Disarankan pemeriksaan manual.",
  "recommended_checks": ["general_visual_check", "monitor_24h"],
  "related_conditions": [],
  "medical_reference": [],
  "graph_context": null
}
```
Case tetap `PENDING_CONFIRMATION` (butuh review manual), tanpa kandidat penyakit.

### 4.8 Peringatan
- "Tahap pertama GLM-5.3-Flash" menyiratkan tahap kedua, tapi kriteria eskalasi belum ada (K11). Mulai dengan Flash saja, ukur dulu.
- GLM-5.3-Flash sangat baru (rilis 26 Agustus 2026); benchmark independen minim, klaim performa dominan dari vendor. Kelebihan: MIT, self-host, murah (kontrol biaya & privasi data farm).
- Error compounding: salah baca fitur di N1 diwarisi N2–N6. Struktur graph tidak menghapus ini, malah menambah titik gagal baru (routing logic).

---

## PHASE 5 — Aplikasi, Konfirmasi User & Chat

### 5.1 Tampilan
- **Daftar Alert**: per `cage_id`, urut severity dinamis, badge `alert_count` jika >1, badge `UNCONFIRMED_ESCALATED` / `priority_review`.
- **Detail Card** ⚠️ K8 — rekomendasi saat ini (B, sesuai kode):
  - Saat pending: `observed_anomalies`, `related_conditions` (+ differential_note), `recommended_checks`, `overall_uncertainty`, `notifiable_notice`, crop yang dipakai.
  - Setelah **Sakit** + pilih penyakit: `recommended_mitigations` + `medical_references` (obat, dosis, withdrawal period, disclaimer) untuk penyakit itu saja.
- **3 tombol konfirmasi**: `[Sakit]` (wajib pilih penyakit dari kandidat) `[Tidak Sakit]` `[Sehat]`.
- Tombol petugas: **Tandai Sembuh**, **Reset Monitoring Cage** (6.2).
- **Peringatan wajib lapor** `[IMPL]`: jika ada kandidat `notifiable = true` (mis. Avian Influenza), tampil peringatan deterministik untuk menghubungi otoritas kesehatan hewan.

### 5.2 Efek tombol konfirmasi

| Tombol | Case | Cage | Deteksi selanjutnya |
|---|---|---|---|
| **Sakit** | `CONFIRMED_SICK`, `confirmed_condition` diisi, mitigasi+obat dibuka | `EXCLUDED_SICK` | Dikecualikan sampai **Tandai Sembuh** |
| **Tidak Sakit** | `CONFIRMED_NOT_SICK` | `COOLDOWN(reason: not_sick)` | Dikecualikan N siklus + safety-net |
| **Sehat** | `CONFIRMED_HEALTHY` | `COOLDOWN(reason: false_alarm)` | Dikecualikan N siklus + safety-net |

Setelah tombol ditekan: `resolved_at = now()`, `confirmed_by` dicatat, sesi ke-2 hari itu di-skip untuk cage tsb (A2), data konfirmasi masuk feedback store (Phase 7).
Kasus tepi: penyakit yang dipilih tidak ada di `_disease_actions` → tampilkan "belum ada data tindakan terverifikasi untuk kondisi ini, disarankan konsultasi manual".

### 5.3 Chat lanjutan per case `[IMPL]`
Graph terpisah dari diagnostic graph:
```
sync_case_state → load_cage_history → retrieve → respond
```
- **Dua lapis memori**: checkpointer LangGraph menyimpan `messages` (`thread_id = case_id`); **CaseStore** adalah sumber kebenaran status & `confirmed_condition`.
- `sync_case_state` selalu memuat ulang status terbaru di awal tiap giliran (konsisten dengan tombol yang ditekan di luar chat).
- `load_cage_history`: maks 5 case resolved, 90 hari terakhir, cage yang sama — **informasional saja**, bukan bukti diagnosis (aturan #11).
- `retrieve`: setiap giliran melakukan retrieval graph ulang (grounded), dengan scope berdasarkan status:
  - `PENDING_CONFIRMATION` → multi-kandidat
  - `CONFIRMED_SICK` → hanya penyakit terkonfirmasi
  - `CONFIRMED_NOT_SICK` / `CONFIRMED_HEALTHY` → tanpa kandidat penyakit
- Aturan tambahan chat: graph kosong → katakan "data terverifikasi tidak tersedia", jangan menjawab dari pengetahuan umum.

---

## PHASE 6 — State Machine & Policies

### 6.1 State machine Case
```
                    ┌─────────────┐
                    │  DETECTED   │
                    └──────┬──────┘
                           │ diagnostic_graph selesai (reasoning atau fallback)
                           ▼
              ┌─────────────────────────┐
              │  PENDING_CONFIRMATION    │◀──────────┐ deteksi ulang sebelum konfirmasi
              └───────────┬──────────────┘           │ (alert_count++, evidence digabung)
                          │                          │
        ┌─────────────────┼─────────────────┐────────┘
        ▼                 ▼                 ▼
  [Sakit + penyakit] [Tidak Sakit]      [Sehat]
        ▼                 ▼                 ▼
 CONFIRMED_SICK   CONFIRMED_NOT_SICK  CONFIRMED_HEALTHY

  ── Tidak dikonfirmasi ──
  PENDING_CONFIRMATION ──(lewat TTL, mis. akhir hari/24 jam)──► UNCONFIRMED_ESCALATED
    (prioritas dinaikkan, tetap tampil; deteksi baru tetap digabung; tombol konfirmasi tetap aktif)
```

### 6.2 State machine Cage
```
ELIGIBLE ──[Sakit]──────────► EXCLUDED_SICK ──[Tandai Sembuh / Reset Monitoring]──► ELIGIBLE
ELIGIBLE ──[Tidak Sakit/Sehat]──► COOLDOWN ──(otomatis setelah N siklus)──────────► ELIGIBLE
COOLDOWN ──(anomali ke-3 selama cooldown)──► tetap COOLDOWN + eskalasi priority_review
```

### 6.3 Policies
| Policy | Aturan | File |
|---|---|---|
| **Cooldown** | Default 3 siklus deteksi (≈1.5 hari jika K1=A). Deteksi tetap berjalan & dicatat, tidak dialert. Perlu kalibrasi dengan pakar vet. | `cooldown_policy.py` |
| **Recovery** | Tidak otomatis. Petugas menekan **Tandai Sembuh**; **Reset Monitoring Cage** untuk ayam diganti/dipindah. | — (use case `mark_recovered`) |
| **Safety-net** | ≥3 anomali selama cooldown → eskalasi paksa `priority_review`. | `safety_net_policy.py` |
| **TTL** | Case pending sampai batas → `UNCONFIRMED_ESCALATED`, tidak hilang diam-diam. | `ttl_policy.py` |

---

## PHASE 7 — Feedback Loop (jangka panjang)

Disimpan dari setiap konfirmasi:
```json
{
  "case_id": "...",
  "cage_id": "...",
  "model_versions": {"fcos_lite": "...", "extractor": "GLM-5.3-Flash", "reasoner": "..."},
  "crops": ["..."],
  "extracted_features_raw": ["..."],
  "visual_features": ["..."],
  "graph_predicted_conditions": ["..."],
  "user_confirmation": "sakit | tidak_sakit | sehat",
  "confirmed_condition_if_sakit": "...",
  "resolved_at": "..."
}
```
Dasar evaluasi: **confirmation match rate** (seberapa sering kandidat yang dikonfirmasi ada di `related_conditions`), akurasi ekstraksi fitur, dan dataset tambahan untuk FCOS-Lite (label hasil konfirmasi). Desain evaluasi detail dibuat terpisah setelah pilot.
(`model_versions` & `crops` adalah tambahan agar evaluasi bisa dilacak per versi model.)

---

## Lampiran A — Ontologi Knowledge Graph

```
Node:
  Disease {id, name, desc, base_severity, notifiable}          ← notifiable: [IMPL]
  VisualFeature {id, name}
  Symptom {id, name}
  EnvironmentalCondition {id, name, threshold_ref}
  InspectionAction {id, name, instruction}
  MitigationAction {id, name, instruction, priority}
  MedicalTreatment {id, name, dosage, withdrawal_period}

Relasi:
  Disease -[:HAS_VISUAL_FEATURE {specificity, onset_stage, mechanism}]-> VisualFeature
  Disease -[:HAS_SYMPTOM {specificity, onset_stage, mechanism}]-> Symptom
  Disease -[:ASSOCIATED_WITH_ENVIRONMENT {strength}]-> EnvironmentalCondition
  Disease -[:REQUIRES_INSPECTION]-> InspectionAction
  Disease -[:MITIGATED_BY {priority}]-> MitigationAction
  Disease -[:TREATED_WITH {dosage, withdrawal_period}]-> MedicalTreatment
```

**Severity dinamis** `[IMPL]` (lebih spesifik dari flow lama):
```
severity(kandidat) = base_severity(disease) × onset_stage_multiplier(onset TERLAMBAT yang match)
onset_stage_multiplier: early=1.0, middle=1.5, late=2.0   (perlu kalibrasi)
severity(case)     = MAX severity antar kandidat           (prinsip precautionary / worst-case)
```

**Scoring numerik kandidat: tidak ada.** Differential reasoning naratif dari atribut relasi.

---

## Lampiran B — Perbandingan dengan Paper Rujukan

### B.1 Terhadap paper FCOS-Lite
| Aspek | Status |
|---|---|
| Arsitektur & training model | `[PAPER-FCOS]` identik |
| Kuantisasi & deploy IMX500 | `[PAPER-FCOS]` identik |
| Inferensi per frame | `[PAPER-FCOS]` identik |
| Host board wajib (Pi) | `[PAPER-FCOS]` sama |
| IoU tracking | `[TAMBAHAN]` |
| Debounce state machine | `[TAMBAHAN]` |
| Frame selection + crop resolusi native | `[TAMBAHAN]` |
| Kirim gambar (bukan hanya metadata) | `[TAMBAHAN]` — memakai opsi yang dibuka paper |
| Tier server, LangGraph, knowledge graph | `[TAMBAHAN]` |

### B.2 Terhadap GraphRAG-Vet asli
| Komponen asli | Di sistem ini |
|---|---|
| Intent classification | Dihilangkan (task tetap: health screening) |
| NER berbasis teks | Diganti model multimodal (GLM-5.3-Flash) + canonical mapping |
| Text-to-Cypher dinamis | Diganti template terparameterisasi |
| Image retrieval / vector DB | Dihilangkan (citra hanya untuk ekstraksi) |
| Self-correction Cypher 3× | Disederhanakan: 1× retry mapping + fallback template |
| Scoring numerik | Tidak ada di asli, tidak ditambahkan |
| Hard constraint injection | Dipertahankan, diperkuat dengan builder deterministik |
| Refusal / insufficient data | Dipertahankan, fallback template actionable |
| Dua tahap gated treatment | Flow lama: disederhanakan jadi satu tahap; kode: dua tahap berbasis konfirmasi → **K8** |
| Multi-hop reasoning | Dipertahankan via atribut relasi + subgraph multi-kandidat |
| Orkestrasi | Pipeline linear → **LangGraph** (diagnostic graph + chat graph) |

---

## Lampiran C — Pemetaan ke Kode & Status

| Bagian dokumen | Lokasi kode | Status (per `plan.md`) |
|---|---|---|
| Phase 1 FCOS-Lite | `fcos_lite_model.py`, `fcos_lite_train.py` | Arsitektur & loop training ada; data asli, teacher, KD, export belum |
| Phase 2 Edge | — | Belum ada |
| Phase 3 Intake & dedup | `domain/entities/case.py`, `cage.py`, `policies/*` | Domain done; use case `ingest_detection` & API belum |
| N1–N2 (Modul A) | `pipelines/module_a_semantic_mapping/*` | Done (dengan VLM generik; adaptasi GLM-5.3-Flash perlu dicek) |
| N3 lingkungan | `module_a_semantic_mapping/sensor_normalizer.py` | Ada; bergantung K10 |
| N4 (Modul B) | `pipelines/module_b_graph_retrieval/*` | Done |
| N5–N6, FB (Modul C) | `pipelines/module_c_reasoning/*` | Partial |
| Wiring diagnostic graph | `pipelines/orchestration/diagnostic_graph.py` | **Skeleton** — node masih placeholder, conditional edge & fallback belum tersambung |
| Chat graph | `pipelines/orchestration/chat_graph.py` | Partial — `retrieve`/`respond` placeholder |
| CaseStore / history | `infrastructure/persistence/case_store.py` | In-memory, belum DB-backed |
| Phase 7 feedback | — | Belum ada |

---

## Peringatan Akhir soal Validasi

Akurasi end-to-end sistem gabungan ini **belum pernah divalidasi**. mAP 94.3% paper FCOS-Lite hanya mengukur deteksi biner healthy/sick, **bukan** akurasi diagnosis diferensial akhir. Error tiap tahap berpotensi terakumulasi:
- false negative FCOS-Lite / debounce → kasus tidak pernah sampai ke server;
- salah ekstraksi fitur → retrieval kandidat yang salah;
- ontologi tidak lengkap → fallback berlebihan.

Semua parameter berikut masih **hipotesis desain** yang perlu diuji: debounce 3/5 & jendela 3–5 detik, jumlah 3 frame, padding 20–30%, confidence filter 0.6, ambang unmapped 50%, cooldown 3 siklus, multiplier severity, ambang sensor (terutama amonia).
