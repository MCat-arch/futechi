# Tahap 2 — Domain Layer (Kode Penuh + Test)

Ini adalah implementasi lengkap **Tahap 2: Domain Layer** dari panduan
implementasi Poultry GraphRAG-Vet. Semua kode di `src/poultry_graphrag/domain/`
adalah logika bisnis MURNI — tidak ada dependensi ke Neo4j, LLM, HTTP,
atau database apa pun. Sudah divalidasi: **50 unit test, semua PASSED**.

## Cara pakai

1. Copy folder `src/poultry_graphrag/domain/` ke lokasi yang sama persis
   di repo Anda (`graphdb/src/poultry_graphrag/domain/`).
2. Copy folder `tests/unit/domain/` ke lokasi yang sama persis
   (`graphdb/tests/unit/domain/`).
3. Install pytest: `pip install pytest`
4. Jalankan dari root project: `pytest tests/unit/domain/ -v`

## Struktur file yang dibuat

```
src/poultry_graphrag/
├─ __init__.py
└─ domain/
   ├─ __init__.py                      # dokumentasi aturan domain layer
   ├─ exceptions.py                    # InvalidTransitionError, CaseAlreadyResolvedError
   ├─ entities/
   │  ├─ case.py                       # entity Case + semua method mutasi
   │  ├─ cage.py                       # entity Cage + exclusion/cooldown logic
   │  └─ confirmation.py               # entity Confirmation
   ├─ value_objects/
   │  ├─ enums.py                      # semua enum status
   │  ├─ severity.py                   # perhitungan severity dinamis
   │  └─ observations.py               # VisualFeatureObservation, EnvironmentSnapshot, dst
   ├─ state_machine/
   │  └─ case_state_machine.py         # tabel transisi valid + fungsi transition()
   └─ policies/
      ├─ cooldown_policy.py
      ├─ safety_net_policy.py
      └─ ttl_policy.py

tests/unit/domain/
├─ test_severity.py           (7 test)
├─ test_case.py                (13 test)
├─ test_cage.py                 (10 test)
├─ test_confirmation.py         (3 test)
├─ test_case_state_machine.py   (9 test)
└─ test_policies.py             (8 test)
```

## Catatan penting sebelum lanjut ke Tahap 3+

- **Nilai threshold masih placeholder**, ditandai jelas di kode
  (`DEFAULT_COOLDOWN_CYCLES=3`, `DEFAULT_SAFETY_NET_THRESHOLD=3`,
  `DEFAULT_TTL_HOURS=24`, `ONSET_STAGE_MULTIPLIER`). Semua ini WAJIB
  dikalibrasi ulang setelah pilot deployment / masukan pakar vet —
  sudah didesain sebagai `override` parameter supaya gampang diganti
  dari config/env tanpa ubah kode.
- **Semua fungsi domain menerima `now: datetime` sebagai parameter**,
  bukan memanggil `datetime.now()` sendiri — ini yang membuat unit test
  di atas 100% deterministik (tidak ada test yang "kadang gagal"
  tergantung jam berapa dijalankan).
- **`transition()` di `case_state_machine.py` adalah satu-satunya pintu
  resmi** untuk mengubah `Case.status`. Saat masuk ke Tahap 9
  (application/use_cases), SELALU panggil lewat `transition()`, jangan
  panggil `Case.resolve()` dkk secara langsung dari use case.
