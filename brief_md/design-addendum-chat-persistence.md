# Design Addendum: Chat Persistence & Riwayat Kandang

Dokumen ini mencatat keputusan desain tambahan yang dibuat SETELAH Tahap 1–5
selesai dikerjakan, sebagai referensi wajib saat mengimplementasikan
Tahap 7 (Modul C), Tahap 8 (Orchestration), dan Tahap 10 (Persistence).

**Konteks pertanyaan awal:** setelah case dibuat dan user melihat daftar
kemungkinan penyakit + tindakan, apakah sesi chat lanjutan tetap
"ingat" konteks — termasuk saat user mengonfirmasi lewat tombol
(bukan lewat chat), dan termasuk riwayat kandang dari kasus-kasus lama.

---

## Keputusan 1 — Dua Lapis Memori yang Terpisah

| Lapis | Menyimpan | Kunci | Diupdate oleh |
|---|---|---|---|
| LangGraph Checkpointer | Riwayat percakapan (messages) | `thread_id = case_id` | Hanya lewat `chat_graph.invoke()` |
| Case Store | Status resmi (status, related_conditions, confirmed_condition) | `case_id`, bisa query by `cage_id` | Use case lain juga (`confirm_case`, tombol UI) |

**Implikasi:** checkpointer TIDAK otomatis tahu perubahan yang terjadi
lewat tombol konfirmasi. Wajib ada langkah sinkronisasi eksplisit
(Keputusan 2) di setiap giliran chat.

---

## Keputusan 2 — Node `sync_case_state` (WAJIB, urutan pertama di chat_graph)

Sebelum chat merespons apa pun, ambil ulang status Case terbaru dari
Case Store — supaya perubahan lewat tombol (di luar chat) ikut
terbaca oleh sesi chat yang sedang berjalan.

```
chat_graph urutan node:
  sync_case_state → load_cage_history → retrieve → respond
```

### Efek pada scoping retrieval (Modul B saat dipanggil dari chat)

| `case_status` saat itu | Scope query Modul B |
|---|---|
| `PENDING_CONFIRMATION` | Multi-kandidat seperti biasa |
| `CONFIRMED_SICK` | HANYA untuk `confirmed_disease`, kandidat lama tidak dimunculkan lagi |

---

## Keputusan 3 — Riwayat Kandang HANYA di Chat, TIDAK di Tier 1 (diagnostic_graph)

**Keputusan:** riwayat case-case lama dari cage yang sama HANYA
ditambahkan sebagai konteks di `chat_graph`, TIDAK ditambahkan ke
`diagnostic_graph` (alert pertama/Tier 1 yang otomatis tampil saat
case baru dibuat).

**Alasan:**
- Tier 1 harus tetap cepat & ringan (alert pertama, bukan hasil eksplorasi)
- Risiko bias historis ("pernah kena X, jadi curiga X lagi") lebih
  berbahaya di Tier 1 karena belum ada ruang diskusi/nuansa seperti di chat
- Bisa dipertimbangkan ulang setelah pilot kalau ternyata dibutuhkan

### Detail implementasi (node `load_cage_history`)

- Sumber: method baru `CaseStore.find_resolved_cases_by_cage(cage_id, exclude_case_id, limit=5, since_days=90)`
- DTO baru: `CageHistoryEntry(case_id, resolved_at, outcome, confirmed_condition)`
- Dibatasi `limit=5` dan `since_days=90` — PLACEHOLDER, wajib dikalibrasi
  ulang setelah pilot (sama seperti threshold lain di proyek ini)

### Cara disajikan ke LLM (Modul C)

Riwayat kandang ditulis sebagai **blok terpisah** dari `graph_context`,
diberi label eksplisit sebagai catatan, BUKAN bukti diagnostik utama:

```
CATATAN RIWAYAT (informasional, 90 hari terakhir):
- 2026-07-15: dikonfirmasi Newcastle Disease
- 2026-06-02: dikonfirmasi sehat (false alarm)

BUKTI SAAT INI (dasar utama diagnosis):
- [graph_context dari retrieval saat ini]
```

---

## Keputusan 4 — Tambahan Hard Constraint (Modul C, Tahap 7)

Rule baru yang WAJIB ditambahkan ke `SYSTEM_PROMPT_TEMPLATE`:

```
11. Riwayat kandang HANYA konteks tambahan, BUKAN bukti diagnostik
    utama. Diagnosis/kandidat penyakit tetap harus didasarkan pada
    GRAPH CONTEXT saat ini. Riwayat boleh disebut sebagai catatan,
    tapi TIDAK boleh dijadikan alasan tunggal untuk menaikkan
    kemungkinan penyakit yang sama tanpa dukungan evidence dari
    graph context saat ini.
```

**Alasan:** mencegah bias konfirmasi baru ("dulu kena X, pasti X lagi")
yang tidak ada di paper asli GraphRAG-Vet dan berisiko muncul akibat
fitur riwayat kandang yang baru ditambahkan ini.

---

## Checklist Implementasi per Tahap

- [ ] **Tahap 7** — Tambahkan rule #11 ke `prompt_constraints.py`
- [ ] **Tahap 8** — Buat `ChatState` dengan field: `case_status`,
      `confirmed_disease`, `cage_history` (selain field yang sudah
      direncanakan sebelumnya: `case_id`, `cage_id`, `messages`, `graph_context`)
- [ ] **Tahap 8** — Implementasikan node `sync_case_state` dan
      `load_cage_history` di `chat_graph.py`, urutan: sync → history → retrieve → respond
- [ ] **Tahap 8** — Retrieval di chat WAJIB kondisional sesuai
      `case_status` (lihat tabel Keputusan 2)
- [ ] **Tahap 9** — `chat_case_context()` use case memanggil
      `chat_graph` dengan `thread_id = case_id`
- [ ] **Tahap 10** — Implementasikan `CaseStore.find_resolved_cases_by_cage()`
      + DTO `CageHistoryEntry`, index `cage_id` + `resolved_at` di Case Store
