// =====================================================================
// Seed 002 -- DRAFT di luar tabel sumber (data_status = "draft_general_knowledge")
//
// Berisi hal yang TIDAK ada di tabel literatur tapi dibutuhkan alur sistem:
//   1. MitigationAction non-medis (Tahap 2 reveal setelah konfirmasi "Sakit")
//   2. Relasi faktor lingkungan/manajemen yang umum dikenal
//
// Sengaja dipisah dari 001 supaya mudah direview dokter hewan, diubah, atau
// dihapus seluruhnya tanpa menyentuh katalog dari tabel sumber.
// TIDAK ada obat/dosis di sini.
// =====================================================================

// ---------------------------------------------------------------------
// MitigationAction
// ---------------------------------------------------------------------
MERGE (n:MitigationAction {id: "MA-001"}) SET n.name = "isolate_affected_bird", n.priority = "high", n.data_status = "draft_general_knowledge", n.instruction = "Pisahkan ayam yang dicurigai sakit dari kelompok bila memungkinkan.";
MERGE (n:MitigationAction {id: "MA-002"}) SET n.name = "tighten_biosecurity", n.priority = "high", n.data_status = "draft_general_knowledge", n.instruction = "Batasi lalu lintas orang dan peralatan, disinfeksi alas kaki dan peralatan di blok ini.";
MERGE (n:MitigationAction {id: "MA-003"}) SET n.name = "report_to_animal_health_authority", n.priority = "high", n.data_status = "draft_general_knowledge", n.instruction = "Laporkan segera ke dinas/otoritas kesehatan hewan setempat dan jangan memindahkan ayam atau telur keluar blok sebelum ada arahan.";
MERGE (n:MitigationAction {id: "MA-004"}) SET n.name = "improve_ventilation", n.priority = "high", n.data_status = "draft_general_knowledge", n.instruction = "Tingkatkan ventilasi atau kecepatan kipas untuk menurunkan panas, kelembapan, dan amonia.";
MERGE (n:MitigationAction {id: "MA-005"}) SET n.name = "provide_cool_drinking_water", n.priority = "high", n.data_status = "draft_general_knowledge", n.instruction = "Pastikan air minum sejuk tersedia cukup di semua tempat minum.";
MERGE (n:MitigationAction {id: "MA-006"}) SET n.name = "reduce_stocking_density", n.priority = "medium", n.data_status = "draft_general_knowledge", n.instruction = "Kurangi kepadatan kandang bila memungkinkan.";
MERGE (n:MitigationAction {id: "MA-007"}) SET n.name = "improve_litter_feces_management", n.priority = "medium", n.data_status = "draft_general_knowledge", n.instruction = "Bersihkan feses atau litter basah dan perbaiki kebocoran tempat minum.";
MERGE (n:MitigationAction {id: "MA-008"}) SET n.name = "replace_suspect_feed", n.priority = "high", n.data_status = "draft_general_knowledge", n.instruction = "Hentikan pakan yang dicurigai, ganti dengan batch lain, dan simpan sampel pakan untuk uji laboratorium.";
MERGE (n:MitigationAction {id: "MA-009"}) SET n.name = "record_egg_quality_daily", n.priority = "low", n.data_status = "draft_general_knowledge", n.instruction = "Catat produksi dan kualitas kerabang harian untuk evaluasi dokter hewan.";

// ---------------------------------------------------------------------
// MITIGATED_BY
// ---------------------------------------------------------------------
// Isolasi + biosekuriti: penyakit infeksi (viral/bakteri/kompleks)
MATCH (d:Disease {id: "DIS-001"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-002"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-003"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-004"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-005"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-006"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-007"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-008"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-009"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-010"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-011"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-012"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-015"}), (t:MitigationAction {id: "MA-001"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-001"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-002"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-003"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-004"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-005"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-006"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-007"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-008"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-009"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-010"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-011"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-012"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-013"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-014"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-015"}), (t:MitigationAction {id: "MA-002"}) MERGE (d)-[:MITIGATED_BY]->(t);
// Lapor otoritas: penyakit notifiable
MATCH (d:Disease {id: "DIS-007"}), (t:MitigationAction {id: "MA-003"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-009"}), (t:MitigationAction {id: "MA-003"}) MERGE (d)-[:MITIGATED_BY]->(t);
// Lingkungan & manajemen
MATCH (d:Disease {id: "DIS-017"}), (t:MitigationAction {id: "MA-004"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-001"}), (t:MitigationAction {id: "MA-004"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-002"}), (t:MitigationAction {id: "MA-004"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-006"}), (t:MitigationAction {id: "MA-004"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-017"}), (t:MitigationAction {id: "MA-005"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-017"}), (t:MitigationAction {id: "MA-006"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-006"}), (t:MitigationAction {id: "MA-006"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-013"}), (t:MitigationAction {id: "MA-007"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-014"}), (t:MitigationAction {id: "MA-007"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-015"}), (t:MitigationAction {id: "MA-007"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-016"}), (t:MitigationAction {id: "MA-008"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-004"}), (t:MitigationAction {id: "MA-009"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-008"}), (t:MitigationAction {id: "MA-009"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-012"}), (t:MitigationAction {id: "MA-009"}) MERGE (d)-[:MITIGATED_BY]->(t);

// ---------------------------------------------------------------------
// ASSOCIATED_WITH_ENVIRONMENT (faktor predisposisi umum, di luar tabel)
// ---------------------------------------------------------------------
MATCH (d:Disease {id: "DIS-001"}), (t:EnvironmentalCondition {id: "EC-003"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "medium", r.data_status = "draft_general_knowledge", r.note = "Amonia tinggi memperberat penyakit respirasi";
MATCH (d:Disease {id: "DIS-002"}), (t:EnvironmentalCondition {id: "EC-003"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "medium", r.data_status = "draft_general_knowledge", r.note = "Amonia tinggi dan ventilasi buruk memperberat kasus";
MATCH (d:Disease {id: "DIS-006"}), (t:EnvironmentalCondition {id: "EC-003"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "high", r.data_status = "draft_general_knowledge", r.note = "Amonia tinggi memperberat penyakit respirasi kronis";
MATCH (d:Disease {id: "DIS-006"}), (t:EnvironmentalCondition {id: "EC-004"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "medium", r.data_status = "draft_general_knowledge", r.note = "Kepadatan tinggi memperberat penyakit respirasi kronis";
MATCH (d:Disease {id: "DIS-017"}), (t:EnvironmentalCondition {id: "EC-004"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "medium", r.data_status = "draft_general_knowledge", r.note = "Kepadatan tinggi menghambat pembuangan panas";
MATCH (d:Disease {id: "DIS-017"}), (t:EnvironmentalCondition {id: "EC-006"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "medium", r.data_status = "draft_general_knowledge", r.note = "Ayam menggerombol di area yang lebih sejuk";
MATCH (d:Disease {id: "DIS-013"}), (t:EnvironmentalCondition {id: "EC-005"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "high", r.data_status = "draft_general_knowledge", r.note = "Litter basah mendukung sporulasi oocyst Eimeria";
MATCH (d:Disease {id: "DIS-015"}), (t:EnvironmentalCondition {id: "EC-005"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "medium", r.data_status = "draft_general_knowledge", r.note = "Litter basah dan koksidiosis adalah faktor predisposisi NE";
