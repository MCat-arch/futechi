"""
Domain layer: logika bisnis murni.

Aturan ketat untuk folder ini:
- TIDAK BOLEH import Neo4j driver, HTTP client, LLM client, atau library I/O apa pun.
- Semua fungsi/method di sini harus bisa diuji tanpa menyalakan service eksternal.
- Kalau butuh "waktu sekarang", TERIMA sebagai parameter (now: datetime),
  jangan panggil datetime.now() di dalam domain -- supaya unit test deterministik.
"""
