# Flow Sistem Final: Poultry GraphRAG-Vet
## Deteksi Penyakit Ayam Berbasis Computer Vision, VLM, dan Knowledge Graph

---

## 0. Asumsi yang Digunakan (perlu dikonfirmasi ke pemilik produk/pakar vet)

| # | Asumsi | Alasan |
|---|---|---|
| A1 | "Sehat" = false alarm murni (tidak ada indikasi apa pun). "Tidak Sakit" = ada anomali teramati tapi bukan penyakit (mis. stres sesaat/postur wajar). Keduanya masuk exclusion, tapi dicatat kategori terpisah. | Diperlukan untuk kualitas feedback loop KG dan evaluasi akurasi VLM ke depan |
| A2 | Jika case terkonfirmasi (sakit/tidak sakit/sehat) sebelum jadwal deteksi ke-2 pada hari yang sama, deteksi ke-2 untuk cage tsb **di-skip** | Konsisten dengan prinsip cage yang sudah settled tidak perlu dideteksi ulang |
| A3 | "Menambah alert" pada deteksi ke-2 berarti alert baru ditambahkan ke case yang **sama** (bukan case baru terpisah), dengan evidence dari deteksi ke-2 digabung ke evidence deteksi pertama | Mencegah proliferasi case duplikat untuk gejala yang sama |

---

## 1. Arsitektur Tingkat Tinggi

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│   EDGE DEVICE    │     │   SERVER LAYER    │     │      APLIKASI USER      │
│  (per kandang)   │     │                    │     │                          │
│                  │     │  ┌──────────────┐  │     │  ┌────────────────────┐  │
│ CV Real-time     │────▶│  │  Case Intake  │  │     │  │  Daftar Alert       │  │
│ Anomaly Detector │     │  │  & Dedup      │  │     │  │  (per cage_id)      │  │
│ (2x/hari         │     │  └──────┬───────┘  │     │  │                     │  │
│  terjadwal)      │     │         │           │     │  │  - Kondisi terduga  │  │
│                  │     │  ┌──────▼───────┐  │────▶│  │  - Mitigasi         │  │
│ Rotary Encoder   │     │  │  Modul A      │  │     │  │  - Aksi medis+dosis │  │
│ (cage_id)        │     │  │  VLM+Sensor   │  │     │  │  - Withdrawal period│  │
└─────────┬────────┘     │  └──────┬───────┘  │     │  └──────────┬─────────┘  │
          │              │         │           │     │             │            │
          │ sensor        │  ┌──────▼───────┐  │     │  ┌──────────▼─────────┐  │
          │ lingkungan    │  │  Modul B      │  │     │  │  Tombol Konfirmasi  │  │
          └──────────────▶│  │  Graph        │  │     │  │  [Sakit] [Tidak     │  │
                          │  │  Retrieval    │  │     │  │   Sakit] [Sehat]    │  │
                          │  └──────┬───────┘  │     │  └──────────┬─────────┘  │
                          │         │           │     │             │            │
                          │  ┌──────▼───────┐  │◀────┴─────────────┘            │
                          │  │  Modul C      │  │
                          │  │  Constrained  │  │
                          │  │  LLM Reasoning│  │
                          │  └──────┬───────┘  │
                          │         │           │
                          │  ┌──────▼───────┐  │
                          │  │  Case State   │  │
                          │  │  Machine +    │  │
                          │  │  Exclusion    │  │
                          │  │  Store        │  │
                          │  └──────────────┘  │
                          └────────────────────┘
```

---

## 2. FASE 1 — Deteksi Anomali (Edge, Real-time)

### 2.1 Jadwal Deteksi
- Sistem menjalankan **2 sesi deteksi terjadwal per hari** (mis. pagi & sore) per kandang.
- Di dalam satu sesi, computer vision berjalan real-time menyapu tiap cage_id (via rotary encoder untuk identifikasi posisi).

### 2.2 Pipeline Deteksi per Cage
```
1. Rotary encoder → cage_id terdeteksi
2. Kamera capture MULTI-FRAME (5 frame, interval 1 detik,
   dimulai begitu YOLO mendeteksi 1 ekor ayam di cage tsb)
3. YOLO → deteksi & tracking 1 ekor ayam per frame
4. Anomaly detector → hitung anomaly_score per frame
5. Ambil rata-rata anomaly_score dari 5 frame (majority-based)
   - Jika ayam keluar frame di sebagian sampel → frame tsb di-drop,
     minimal 3 dari 5 frame valid untuk lanjut; jika <3 valid →
     tandai capture_quality: "low", tetap lanjut tapi diberi
     flag ke Modul A untuk kehati-hatian ekstra
6. Jika anomaly_score rata-rata > threshold → lanjut ke 2.3
7. Jika tidak → tidak ada tindakan, siklus lanjut ke cage berikutnya
```

### 2.3 Cek Status Cage Sebelum Membuat Case
**Sebelum** case baru dibuat, sistem WAJIB mengecek status cage_id di Exclusion Store:

```
IF cage_id.status == CONFIRMED_SICK (masih dalam masa treatment)
    → SKIP, tidak buat case baru, tidak alert
    (cage sedang ditangani, hindari alert berulang untuk penyakit yang sama)

ELSE IF cage_id.status == CONFIRMED_FALSE_ALARM AND masih dalam cooldown
    → Catat anomali di log background (TIDAK dikirim sebagai alert baru)
    → Tapi: jika ini adalah anomali ke-3 selama masa cooldown
      → ESKALASI paksa ke petugas meski masih cooldown
        (lihat 6.3 Safety-Net)

ELSE IF ada case AKTIF (PENDING_CONFIRMATION) untuk cage_id ini hari ini
    → Bukan case baru. Evidence baru DIGABUNG ke case yang sama.
    → Tambah entri alert baru pada case (accumulate),
      naikkan alert_count, update last_detected_at
    → Kirim NOTIFIKASI ULANG ke user (alert masih outstanding)

ELSE (cage_id eligible, tidak ada case aktif)
    → Buat CASE BARU, lanjut ke Fase 2
```

---

## 3. FASE 2 — Pemrosesan Server (GraphRAG-Vet Modifikasi)

### 3.1 Case Intake
Payload yang dikirim dari edge ke server:
```json
{
  "case_id": "CASE-20260824-B40-01",
  "cage_id": "B40",
  "zone_id": "Z3",
  "detected_at": "2026-08-24T08:15:00+07:00",
  "detection_session": "morning",
  "anomaly_score": 0.84,
  "capture_quality": "high",
  "image_frames": ["IMG-001a", "IMG-001b", "IMG-001c"],
  "raw_environment": {
    "temperature_c": 30.5,
    "humidity_percent": 76,
    "ammonia_ppm": 22
  }
}
```

### 3.2 Modul A — Visual-Sensor Semantic Mapping

```
Multi-frame images
      ↓
VLM semantic extraction (per frame)
      ↓
Aggregasi antar-frame (majority vote / rata-rata confidence per fitur)
      ↓
Filter confidence: fitur dengan confidence < 0.6 DIBUANG
   (tidak ikut jadi parameter query — bukan didowngrade, tapi dihapus)
      ↓
Canonical mapping (dictionary + fuzzy/synonym matching)
      ↓
Sensor normalization (raw value → status semantik via threshold)
      ↓
Entity validation terhadap ontology allowlist
      ↓
IF proporsi fitur unmapped > 50% dari total fitur terekstrak
      → tandai case.requires_manual_review = true
      → BYPASS ke Fallback Template (lihat 3.5), skip Modul B/C generatif
ELSE
      → lanjut ke Modul B
```

**Output Modul A:**
```json
{
  "case_id": "CASE-20260824-B40-01",
  "visual_features": [
    {"name": "lowered_head_posture", "confidence": 0.88},
    {"name": "irregular_feather_appearance", "confidence": 0.74}
  ],
  "environment_conditions": ["humidity_attention", "ammonia_attention"],
  "raw_environment_values": {
    "temperature_c": 30.5, "humidity_percent": 76, "ammonia_ppm": 22
  },
  "unmapped_features": [],
  "case_status": "ready_for_graph_retrieval"
}
```

### 3.3 Modul B — Template Graph Retrieval (Full Query, Tanpa Gating)

```cypher
MATCH (d:Disease)-[hf:HAS_VISUAL_FEATURE]->(vf:VisualFeature)
WHERE vf.name IN $visual_features
  AND NOT d.id IN $recently_excluded_diseases  // dari false-alarm/tidak-sakit sebelumnya (opsional)
OPTIONAL MATCH (d)-[hs:HAS_SYMPTOM]->(s:Symptom)
OPTIONAL MATCH (d)-[ae:ASSOCIATED_WITH_ENVIRONMENT]->(ec:EnvironmentalCondition)
  WHERE ec.name IN $environment_conditions
OPTIONAL MATCH (d)-[:REQUIRES_INSPECTION]->(ia:InspectionAction)
OPTIONAL MATCH (d)-[:MITIGATED_BY]->(ma:MitigationAction)
OPTIONAL MATCH (d)-[:TREATED_WITH]->(mt:MedicalTreatment)
RETURN d, hf, vf, hs, s, ae, ec, ia, ma, mt
LIMIT 20
```

Catatan penting:
- Query mengambil **semua kandidat Disease sekaligus** (bukan satu-satu), agar LLM di Modul C bisa melakukan multi-hop differential reasoning lintas kandidat.
- Atribut relasi (`specificity`, `onset_stage`, `mechanism` pada `HAS_VISUAL_FEATURE`/`HAS_SYMPTOM`) ikut terbawa — ini pengganti scoring numerik, jadi bahan reasoning tekstual LLM.
- **Tidak ada gating** pada `TREATED_WITH` — semua diambil sekaligus sesuai keputusan akses terbuka.

**Boundary check:**
```
IF hasil query kosong (tidak ada Disease match)
    → graph_context = NULL
    → JALANKAN FALLBACK TEMPLATE (3.5), STOP di sini (tidak lanjut ke LLM generatif)
ELSE
    → valid_graph_context, lanjut ke Modul C
```

**Fallback minimal (bukan self-correction Cypher berulang seperti versi asli):**
```
1. Cek ulang canonical entity mapping (barangkali ada typo/istilah belum ternormalisasi)
2. Cek synonym dictionary sekali lagi
3. Jalankan ulang template SEKALI
4. Jika tetap kosong → Fallback Template (3.5)
```

### 3.4 Modul C — Constrained LLM Reasoning

**Context assembly (contoh):**
```
CASE DATA
- Cage: B40, Zone: Z3
- Deteksi: sesi pagi, anomaly_score 0.84, capture_quality: high
- Fitur visual (confidence):
  - lowered_head_posture (0.88)
  - irregular_feather_appearance (0.74)
- Lingkungan: suhu 30.5°C, kelembapan 76% (attention), amonia 22ppm (attention)

GRAPH CONTEXT (multi-kandidat, dengan atribut untuk differential reasoning)
- Disease A -[HAS_VISUAL_FEATURE: lowered_head_posture, specificity: high, onset: early, mechanism: "..."]
- Disease B -[HAS_VISUAL_FEATURE: lowered_head_posture, specificity: low, onset: middle]
- Disease A -[ASSOCIATED_WITH_ENVIRONMENT: humidity_attention, strength: medium]
- Disease A -[MITIGATED_BY: increase_ventilation, priority: high]
- Disease A -[TREATED_WITH: {drug_name}, dosage: "...", withdrawal_period: "7 hari"]
- Disease A -[REQUIRES_INSPECTION: observe_breathing, check_nasal_discharge]
```

**Hard constraints (system prompt):**
```
Role: Anda adalah asisten screening kesehatan unggas.

Aturan:
1. Gunakan HANYA case data dan graph context yang diberikan.
2. Jangan mengarang gejala, penyakit, atau relasi graf.
3. Jangan menyimpulkan diagnosis pasti (definitive_diagnosis selalu null pada tahap ini).
4. Jika ada beberapa kandidat penyakit dengan gejala tumpang tindih,
   jelaskan perbedaannya berdasarkan specificity/onset_stage/mechanism
   yang tersedia di graph context — JANGAN memberi angka skor buatan.
5. Jika graph_context kosong, kembalikan status insufficient_data.
6. Tampilkan withdrawal_period apa adanya dari graph, jangan diubah/diringkas.
7. Sertakan disclaimer bahwa informasi obat bersifat referensi,
   penggunaan harus melalui pengawasan pihak berwenang (dokter hewan/petugas terlatih).
8. Bedakan jelas: observed_anomalies (fakta teramati) vs
   related_conditions (kemungkinan, bukan kepastian).
9. recommended_checks HANYA dari InspectionAction yang diambil dari graph.
10. recommended_mitigations HANYA dari MitigationAction yang diambil dari graph.
```

**Output terstruktur (satu tahap, informasi lengkap):**
```json
{
  "case_id": "CASE-20260824-B40-01",
  "status": "needs_manual_confirmation",
  "severity": {
    "level": "medium",
    "computed_from": "base_severity(Disease A)=medium x onset_stage(early)=1.0"
  },
  "observed_anomalies": ["lowered_head_posture", "irregular_feather_appearance"],
  "related_conditions": [
    {
      "name": "Disease A",
      "evidence": ["lowered_head_posture (high specificity, early stage)"],
      "differential_note": "Lebih mungkin dibanding Disease B karena specificity tinggi & muncul di tahap awal"
    },
    {
      "name": "Disease B",
      "evidence": ["lowered_head_posture (low specificity)"],
      "differential_note": "Kurang didukung, gejala ini kurang spesifik untuk penyakit ini"
    }
  ],
  "definitive_diagnosis": null,
  "recommended_checks": ["observe_breathing", "check_nasal_discharge"],
  "recommended_mitigations": [
    {"action": "increase_ventilation", "priority": "high"}
  ],
  "medical_reference": [
    {
      "for_condition": "Disease A",
      "treatment": "{drug_name}",
      "dosage": "...",
      "withdrawal_period": "7 hari",
      "disclaimer": "Informasi referensi, gunakan dengan pengawasan pihak berwenang"
    }
  ],
  "uncertainty": "medium — dua kandidat penyakit bergejala tumpang tindih, perlu konfirmasi manual"
}
```

### 3.5 Fallback Template (Boundary Kosong / Unmapped Tinggi)

Respons **tetap/non-generatif** (bukan LLM bebas, untuk menghindari hallucination di titik paling rawan):
```json
{
  "case_id": "CASE-20260824-B40-01",
  "status": "insufficient_data",
  "message": "Tidak ditemukan kecocokan kondisi terverifikasi di knowledge graph. Disarankan pemeriksaan manual.",
  "recommended_checks": ["general_visual_check", "monitor_24h"],
  "related_conditions": [],
  "medical_reference": [],
  "graph_context": null
}
```

---

## 4. FASE 3 — Output ke Aplikasi & Interaksi User

### 4.1 Tampilan Aplikasi
- **Daftar Alert**: list ayam sakit (per cage_id), diurutkan berdasar severity yang dihitung dinamis, dengan badge alert_count jika sudah lebih dari 1x terdeteksi.
- **Detail Card** per alert: observed_anomalies, related_conditions (dengan differential_note dari LLM), recommended_checks, recommended_mitigations, medical_reference (obat + withdrawal_period + disclaimer) — **semua tampil sekaligus**, tidak bertahap.
- **Chat terbuka**: user bisa bertanya lanjutan ke LLM terkait case ini; setiap jawaban baru tetap melakukan retrieval graph ulang (tidak murni mengandalkan memori percakapan) agar tetap grounded.
- **3 Tombol konfirmasi**: `[Sakit]` `[Tidak Sakit]` `[Sehat]`

### 4.2 Efek Tombol Konfirmasi

| Tombol | Efek pada Case | Efek pada Cage | Efek pada Deteksi Selanjutnya |
|---|---|---|---|
| **Sakit** | `status → CONFIRMED_SICK` | `cage.status = CONFIRMED_SICK` | Dikecualikan total sampai `RECOVERED` (manual oleh petugas / lihat 6.2) |
| **Tidak Sakit** | `status → CONFIRMED_NOT_SICK` | `cage.status = COOLDOWN(reason: not_sick)` | Dikecualikan sementara N siklus (lihat 6.1), dengan safety-net eskalasi |
| **Sehat** | `status → CONFIRMED_HEALTHY` | `cage.status = COOLDOWN(reason: false_alarm)` | Dikecualikan sementara N siklus (lihat 6.1), dengan safety-net eskalasi |

Begitu salah satu tombol ditekan:
1. Case ditandai `resolved_at = now()`.
2. **Jika masih ada sesi deteksi ke-2 di hari yang sama** untuk cage tsb → sesi tersebut **di-skip** untuk cage ini (Asumsi A2).
3. Data konfirmasi disimpan untuk feedback loop KG (lihat Bagian 7).

---

## 5. State Machine Case (Lengkap)

```
                    ┌─────────────┐
                    │  DETECTED   │ (deteksi sesi 1 atau 2)
                    └──────┬──────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  PENDING_CONFIRMATION    │◀────────┐
              └───────────┬──────────────┘         │
                           │                         │ deteksi sesi ke-2
        ┌──────────────────┼───────────────┐        │ (masih hari sama,
        │                  │               │        │  belum dikonfirmasi)
        ▼                  ▼               ▼        │
  [user: Sakit]     [user: Tdk Sakit] [user: Sehat]  │
        │                  │               │         │
        │                  │               │    ─────┘ (alert_count++,
        ▼                  ▼               ▼           evidence digabung)
 CONFIRMED_SICK    CONFIRMED_NOT_SICK  CONFIRMED_HEALTHY
        │                  │               │
        ▼                  ▼               ▼
 cage EXCLUDED       cage COOLDOWN    cage COOLDOWN
 (sampai treatment    (N siklus,       (N siklus,
  selesai/manual       reason:          reason:
  reset)                not_sick)       false_alarm)
        │                  │               │
        ▼                  ▼               ▼
   RECOVERED          ELIGIBLE_AGAIN   ELIGIBLE_AGAIN
   (manual oleh        (otomatis        (otomatis
    petugas)            setelah          setelah
        │                cooldown)        cooldown)
        ▼
   cage kembali eligible


  ── Jalur khusus: tidak dikonfirmasi ──
  PENDING_CONFIRMATION
        │
        │ (melewati TTL, mis. akhir hari / 24 jam)
        ▼
  UNCONFIRMED_ESCALATED  (prioritas alert dinaikkan,
                          tetap tampil, tidak hilang)
```

---

## 6. Saran Perbaikan yang Sudah Diintegrasikan

### 6.1 Cooldown untuk "Tidak Sakit" / "Sehat"
- Default cooldown: **misal 3 siklus deteksi** (≈ 1.5 hari, karena 2 sesi/hari) — nilai ini perlu dikalibrasi bersama pakar vet, sama seperti threshold lain.
- Selama cooldown, deteksi anomali TETAP berjalan di background (dicatat, tidak dialert) — bukan mematikan CV sepenuhnya.

### 6.2 Recovery dari CONFIRMED_SICK
- Tidak otomatis. Petugas/vet menekan tombol eksplisit **"Tandai Sembuh"** di aplikasi untuk mengembalikan cage ke status eligible.
- Alasan: mencegah penggantian/pemindahan ayam baru ke cage yang sama ikut ter-exclude keliru; juga karena masa penyembuhan penyakit unggas bervariasi dan tidak bisa diasumsikan otomatis dari waktu.
- Disediakan juga tombol terpisah **"Reset Monitoring Cage"** untuk kasus ayam diganti/dipindah di tengah masa exclusion.

### 6.3 Safety-Net Selama Cooldown/Exclusion
- Jika selama masa cooldown (`Tidak Sakit`/`Sehat`) terjadi anomali berulang ≥3 kali → **eskalasi paksa** ke petugas sebagai `priority_review`, meski cage secara teknis masih cooldown. Ini mencegah penyakit baru yang muncul segera setelah false-alarm sebelumnya terlewat.

### 6.4 TTL untuk Case yang Tidak Dikonfirmasi
- Case yang tidak dikonfirmasi sampai akhir hari → status `UNCONFIRMED_ESCALATED`, tetap tampil dengan prioritas dinaikkan (bukan hilang/expired diam-diam).
- Jika TTL terlewati dan ada deteksi baru di hari berikutnya untuk cage yang sama → evidence baru tetap digabung ke case yang sama (case belum resolved), bukan bikin case baru, sampai user benar-benar konfirmasi.

---

## 7. Feedback Loop (untuk perbaikan KG & model — jangka panjang)

Data yang disimpan dari setiap konfirmasi user:
```json
{
  "case_id": "...",
  "vlm_predicted_features": [...],
  "graph_predicted_conditions": [...],
  "user_confirmation": "sakit | tidak_sakit | sehat",
  "confirmed_condition_if_sakit": "...",
  "resolved_at": "..."
}
```
Ini nantinya jadi dasar evaluasi: seberapa sering `related_conditions` teratas sesuai dengan hasil konfirmasi user (semacam "confirmation match rate"), dan menjadi bahan untuk validasi ulang bersama pakar vet (Bagian 7 percakapan sebelumnya) — tapi implementasi detail evaluasi ini didesain terpisah setelah pilot berjalan.

---

## 8. Ontologi Final (Ringkasan)

```
Node:
  Disease {id, name, desc, base_severity}
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
  Disease -[:TREATED_WITH {dosage, withdrawal_period}]-> MedicalTreatment   ← akses terbuka
```

**Severity dinamis** (bukan field statis yang langsung dipakai):
```
severity(case) = base_severity(disease) × onset_stage_multiplier
onset_stage_multiplier: early=1.0, middle=1.5, late=2.0 (perlu kalibrasi)
```

**Scoring numerik: DIHILANGKAN.** Differential reasoning dilakukan LLM secara naratif dari atribut relasi (specificity, onset_stage, mechanism), sesuai desain asli GraphRAG-Vet.

---

## 9. Ringkasan Perubahan dari GraphRAG-Vet Asli

| Komponen Asli | Status di Sistem Ini |
|---|---|
| Intent Classification | Dihilangkan (task tetap = health screening) |
| NER berbasis teks | Diganti VLM + canonical mapping |
| Text-to-Cypher dinamis | Diganti template terparameterisasi |
| Image retrieval/vector DB | Dihilangkan (citra hanya utk VLM) |
| Self-correction Cypher 3x | Disederhanakan jadi 1x retry + fallback template tetap |
| Scoring numerik | Tidak ada di asli, tidak ditambahkan di sini |
| Hard constraint injection | Dipertahankan penuh |
| Refusal/insufficient data | Dipertahankan, diperkuat dengan fallback template actionable |
| Dua tahap gated treatment | **Disederhanakan jadi satu tahap**, treatment terbuka + disclaimer |
| Multi-hop reasoning | Dipertahankan via atribut relasi + subgraph multi-kandidat |
