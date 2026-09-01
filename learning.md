# Learning Progress & Mentor Notes

## 1. Status sesi saat ini

Kami berada di fase transisi dari fondasi sistem ke integrasi orchestration yang benar. Fokus utama bukan menambah fitur baru, melainkan memastikan kontrak state, history, dan retrieval sudah konsisten sebelum lanjut ke pengembangan yang lebih luas.

Poin yang sudah masuk ke arah yang benar:
- Rule #11 sudah tertulis di `CHAT_SYSTEM_PROMPT`.
- `CaseStore` dan `CageHistoryEntry` sudah ada dalam bentuk kontrak minimal.
- `ChatState` sudah mendefinisikan field yang dibutuhkan untuk chat runtime.
- `sync_case_state` dan `load_cage_history` sudah menjadi bagian dari arsitektur yang diasumsikan.
- Import legacy `poultry_graphrag` sudah dibersihkan dari area Modul C yang sedang aktif.

Poin yang masih belum final dan perlu difokuskan:
- sinkronisasi `case_status` dan `confirmed_disease` ke `ChatState` secara nyata
- conditional retrieval berdasarkan status case
- `thread_id = case_id` pada checkpointer
- persistence nyata untuk `CaseStore`, bukan hanya in-memory
- end-to-end testing untuk riwayat kandang dan konfirmasi

## 2. Prinsip arsitektur yang wajib dijaga

### A. Pemisahan jelas antara checkpointer dan case store

Ini adalah keputusan utama yang tidak boleh dilanggar:
- LangGraph checkpointer menyimpan `messages` berdasarkan `thread_id = case_id`.
- CaseStore menyimpan status resmi case dan data konfirmasi, seperti `status`, `confirmed_condition`, `cage_id`, serta `resolved_at`.

Tujuannya:
- riwayat percakapan tetap terpisah dari status domain
- status case tidak boleh tergantung pada isi chat saja
- setiap thread chat tetap bisa di-query dengan cara yang deterministik

### B. Urutan eksekusi chat harus konsisten

Urutan yang benar adalah:
1. `sync_case_state`
2. `load_cage_history`
3. `retrieve`
4. `respond`

Jika urutannya dibalik, sistem berisiko:
- retrieval memakai state yang tidak terbarui
- cage history ikut dipakai sebagai bukti utama padahal harus bersifat informasional
- konfirmasi penyakit aktif tidak tercermin pada prompt saat ini

### C. Riwayat kandang adalah konteks, bukan bukti utama

Ini adalah aturan kunci untuk diagnosis:
- `cage_history` boleh dijadikan catatan contextual
- tetapi `graph_context` saat ini tetap menjadi sumber utama
- jika graph context kosong, sistem harus secara jujur mengatakan bahwa data terverifikasi tidak tersedia, bukan mengarang diagnosis dari memori lama

### D. Status case harus memengaruhi retrieval

Retrieval harus bersifat conditional:
- `PENDING_CONFIRMATION`: retrieval normal, multi-kandidat masih diperbolehkan
- `CONFIRMED_SICK`: retrieval harus difokuskan ke `confirmed_disease` saja

Ini penting agar keputusan chat tidak kembali mengajukan kandidat yang sudah tidak relevan.

## 3. Pengaturan kontrak state yang disarankan

### `ChatState` harus berisi elemen berikut
- `case_id`
- `cage_id`
- `case_status`
- `confirmed_disease`
- `messages`
- `graph_context`
- `cage_history`

Catatan penting:
- `messages` boleh dipersist di checkpointer
- `case_status` dan `confirmed_disease` sebaiknya dipulihkan dari `CaseStore` di awal turn
- `cage_history` harus dibatasi pada `limit=5` dan `since_days=90`

### `CaseStore` harus menjaga domain truth

CaseStore bukan hanya untuk chat. Ia berperan sebagai sumber kebenaran untuk:
- status case
- keputusan konfirmasi
- data kondisi yang sudah dikonfirmasi
- riwayat resolved case per cage

Jika nanti ada persistence DB, pastikan indeks seperti:
- `cage_id`
- `resolved_at`
- `status`

## 4. Panduan desain implementasi yang harus diikuti

### Prioritas 1: sinkronisasi status nyata

Sebelum retrieval atau response, lakukan pembaruan state dari `CaseStore` ke `ChatState`.

Tujuannya:
- case status selalu konsisten dengan record resmi
- `confirmed_disease` tidak bertahan pada state lama
- `graph_context` bisa diperlakukan sesuai status yang aktif

### Prioritas 2: retrieval conditional

Implementasikan logika berikut:
- jika `case_status == "CONFIRMED_SICK"`: batasi hasil retrieval hanya ke `confirmed_disease`
- jika `case_status == "PENDING_CONFIRMATION"`: tetap gunakan konteks kandidat yang relevan dengan case aktif
- jika tidak ada `graph_context`: tangani sebagai kondisi data tidak tersedia, bukan fallback umum

### Prioritas 3: pembatasan riwayat kandang

Ketika mengisi `cage_history`:
- gunakan `find_resolved_cases_by_cage(cage_id, exclude_case_id, limit=5, since_days=90)`
- hanya ambil kasus yang sudah resolved
- jangan masukkan kasus yang sedang aktif atau belum resolved
- jangan gunakan historical data sebagai satu-satunya alasan diagnosa

### Prioritas 4: test yang menutup bug nyata

Uji yang harus ada:
1. `PENDING_CONFIRMATION` + cage history present + graph context valid
2. `CONFIRMED_SICK` + confirmed disease active
3. graph context kosong + cage history present
4. prompt menyatakan riwayat kandang bersifat informational saja
5. sync state mengambil status terbaru dari `CaseStore`
6. retrieval conditional untuk confirmed disease

## 5. Kesalahan umum yang harus dihindari

- Menganggap riwayat lama sebagai sumber bukti utama.
- Menyimpan status case di chat state tanpa sinkronisasi ke CaseStore.
- Menggunakan `thread_id` acak atau tidak konsisten.
- Menggabungkan `messages` dan `case_status` dalam satu store tanpa pemisahan domain.
- Memasukkan import legacy ke path active.
- Mengubah nama field domain secara tidak konsisten tanpa update kontrak graph/prompt.

## 6. Fokus pengembangan berikutnya

### Milestone berikutnya
- Selesaikan wiring `sync_case_state -> load_cage_history -> retrieve -> respond`.
- Pastikan `ChatState` dibangun dari data case yang benar.
- Buat retrieval conditional yang memanfaatkan `case_status`.
- Validasi behavior prompt dengan `case_status` dan `confirmed_disease`.
- Ubah store menjadi DB-backed bila ekspektasi produk sudah siap.

### Pedoman kualitas
- coverage harus menutup edge case chat state, prompt constraints, dan retrieval conditional
- semua fungsi harus memiliki fallback bila data tidak lengkap
- setiap hasil yang dikembalikan ke user harus mengandung jelas sumber data: graph context vs historical note
- semua error handling harus berakhir pada pesan yang aman dan tidak mengarang diagnosis

## 7. Mentor guidance singkat

Sistem ini sudah memiliki fondasi arsitektur yang kuat: domain model, graph retrieval, semantic mapping, dan prompt constraint utama sudah ada. Kelemahan utama sekarang bukan pada model data, melainkan pada koneksi runtime antara state, history, dan retrieval.

Jangan lanjut ke fitur baru sebelum alur berikut benar-benar mapan:
- state live dari CaseStore
- history cage terpisah dan terbatas
- retrieval sesuai status case
- prompt selalu menjaga perbedaan antara data saat ini dan riwayat lama

Jika ingin melanjutkan ke implementation, maka urutan yang paling masuk akal adalah:
1. perbaiki contract ChatState dan sync logic
2. implementasikan conditional retrieval
3. lalu lanjut ke prompt/integrasi runtime
4. baru setelah itu fokus ke persistence DB-backed dan end-to-end test

## 8. Catatan pembelajaran

Poin pembelajaran yang paling penting dari fase ini adalah bahwa dalam sistem seperti ini, "status resmi" harus memiliki pemilik yang jelas. Jika status case dan memori percakapan dicampur, semua keputusan akan berantakan. Model yang sehat adalah:
- state live di CaseStore
- chat history di checkpointer
- evidence utama di graph context
- historical cage notes sebagai catatan tambahan yang dibatasi

Ini adalah fondasi yang tepat untuk pengembangan lanjutan yang aman dan terdokumentasi.
