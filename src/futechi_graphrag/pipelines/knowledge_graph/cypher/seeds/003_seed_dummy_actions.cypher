// =====================================================================
// Seed 003 -- DATA DUMMY mitigasi spesifik & obat (data_status = "dummy")
//
// TUJUAN: mengisi graph supaya alur Tahap 2 reveal (mitigasi + referensi
// obat setelah konfirmasi "Sakit") bisa diuji end-to-end.
//
// BUKAN REKOMENDASI MEDIS. Semua nama, dosis, dan withdrawal period di sini
// adalah placeholder berlabel "[DUMMY]" dan WAJIB diganti data tervalidasi
// dokter hewan / label obat terdaftar sebelum dipakai di lapangan.
// Hapus seluruh file ini (dan node-nya) saat data asli tersedia.
// =====================================================================

// ---------------------------------------------------------------------
// MitigationAction dummy -- satu per penyakit/kondisi
// ---------------------------------------------------------------------
MERGE (n:MitigationAction {id: "MA-101"}) SET n.name = "dummy_mitigation_crd", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik CRD. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-102"}) SET n.name = "dummy_mitigation_ampv_shs", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik aMPV / Swollen Head Syndrome. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-103"}) SET n.name = "dummy_mitigation_coryza", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Infectious Coryza. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-104"}) SET n.name = "dummy_mitigation_ib", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Infectious Bronchitis. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-105"}) SET n.name = "dummy_mitigation_ilt", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik ILT. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-106"}) SET n.name = "dummy_mitigation_ccrd", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik CCRD. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-107"}) SET n.name = "dummy_mitigation_nd", n.priority = "high", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Newcastle Disease. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-108"}) SET n.name = "dummy_mitigation_ai_h9", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Avian Influenza H9. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-109"}) SET n.name = "dummy_mitigation_hpai", n.priority = "high", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik HPAI. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-110"}) SET n.name = "dummy_mitigation_ibd", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik IBD/Gumboro. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-111"}) SET n.name = "dummy_mitigation_reovirus", n.priority = "low", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Reovirus. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-112"}) SET n.name = "dummy_mitigation_eds", n.priority = "low", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Egg Drop Syndrome. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-113"}) SET n.name = "dummy_mitigation_koksidiosis", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Koksidiosis. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-114"}) SET n.name = "dummy_mitigation_helminthiasis", n.priority = "low", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Helminthiasis. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-115"}) SET n.name = "dummy_mitigation_ne", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Necrotic Enteritis. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-116"}) SET n.name = "dummy_mitigation_mikotoksikosis", n.priority = "medium", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Mikotoksikosis. Ganti dengan protokol dari dokter hewan.";
MERGE (n:MitigationAction {id: "MA-117"}) SET n.name = "dummy_mitigation_heat_stress", n.priority = "high", n.data_status = "dummy", n.instruction = "[DUMMY] Placeholder mitigasi spesifik Heat Stress. Ganti dengan protokol dari dokter hewan.";

MATCH (d:Disease {id: "DIS-001"}), (t:MitigationAction {id: "MA-101"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-002"}), (t:MitigationAction {id: "MA-102"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-003"}), (t:MitigationAction {id: "MA-103"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-004"}), (t:MitigationAction {id: "MA-104"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-005"}), (t:MitigationAction {id: "MA-105"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-006"}), (t:MitigationAction {id: "MA-106"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-007"}), (t:MitigationAction {id: "MA-107"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-008"}), (t:MitigationAction {id: "MA-108"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-009"}), (t:MitigationAction {id: "MA-109"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-010"}), (t:MitigationAction {id: "MA-110"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-011"}), (t:MitigationAction {id: "MA-111"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-012"}), (t:MitigationAction {id: "MA-112"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-013"}), (t:MitigationAction {id: "MA-113"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-014"}), (t:MitigationAction {id: "MA-114"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-015"}), (t:MitigationAction {id: "MA-115"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-016"}), (t:MitigationAction {id: "MA-116"}) MERGE (d)-[:MITIGATED_BY]->(t);
MATCH (d:Disease {id: "DIS-017"}), (t:MitigationAction {id: "MA-117"}) MERGE (d)-[:MITIGATED_BY]->(t);

// ---------------------------------------------------------------------
// MedicalTreatment dummy -- satu per penyakit/kondisi
// ---------------------------------------------------------------------
MERGE (n:MedicalTreatment {id: "MT-001"}) SET n.name = "[DUMMY] Obat referensi CRD", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] 7 hari", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-002"}) SET n.name = "[DUMMY] Terapi suportif aMPV / SHS", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-003"}) SET n.name = "[DUMMY] Obat referensi Infectious Coryza", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] 7 hari", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-004"}) SET n.name = "[DUMMY] Terapi suportif Infectious Bronchitis", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-005"}) SET n.name = "[DUMMY] Terapi suportif ILT", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-006"}) SET n.name = "[DUMMY] Obat referensi CCRD", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] 7 hari", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-007"}) SET n.name = "[DUMMY] Terapi suportif Newcastle Disease", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-008"}) SET n.name = "[DUMMY] Terapi suportif Avian Influenza H9", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-009"}) SET n.name = "[DUMMY] Tindakan otoritas HPAI", n.dosage = "[DUMMY] placeholder, ikuti arahan otoritas kesehatan hewan", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-010"}) SET n.name = "[DUMMY] Terapi suportif IBD/Gumboro", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-011"}) SET n.name = "[DUMMY] Terapi suportif Reovirus", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-012"}) SET n.name = "[DUMMY] Terapi suportif Egg Drop Syndrome", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-013"}) SET n.name = "[DUMMY] Obat referensi Koksidiosis", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] 5 hari", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-014"}) SET n.name = "[DUMMY] Obat referensi Helminthiasis", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] 7 hari", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-015"}) SET n.name = "[DUMMY] Obat referensi Necrotic Enteritis", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] 7 hari", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-016"}) SET n.name = "[DUMMY] Pengikat toksin pakan", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";
MERGE (n:MedicalTreatment {id: "MT-017"}) SET n.name = "[DUMMY] Terapi suportif Heat Stress", n.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", n.withdrawal_period = "[DUMMY] Tidak berlaku", n.data_status = "dummy";

MATCH (d:Disease {id: "DIS-001"}), (t:MedicalTreatment {id: "MT-001"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] 7 hari", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-002"}), (t:MedicalTreatment {id: "MT-002"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-003"}), (t:MedicalTreatment {id: "MT-003"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] 7 hari", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-004"}), (t:MedicalTreatment {id: "MT-004"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-005"}), (t:MedicalTreatment {id: "MT-005"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-006"}), (t:MedicalTreatment {id: "MT-006"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] 7 hari", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-007"}), (t:MedicalTreatment {id: "MT-007"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-008"}), (t:MedicalTreatment {id: "MT-008"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-009"}), (t:MedicalTreatment {id: "MT-009"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder, ikuti arahan otoritas kesehatan hewan", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-010"}), (t:MedicalTreatment {id: "MT-010"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-011"}), (t:MedicalTreatment {id: "MT-011"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-012"}), (t:MedicalTreatment {id: "MT-012"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-013"}), (t:MedicalTreatment {id: "MT-013"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] 5 hari", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-014"}), (t:MedicalTreatment {id: "MT-014"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] 7 hari", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-015"}), (t:MedicalTreatment {id: "MT-015"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] 7 hari", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-016"}), (t:MedicalTreatment {id: "MT-016"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
MATCH (d:Disease {id: "DIS-017"}), (t:MedicalTreatment {id: "MT-017"}) MERGE (d)-[r:TREATED_WITH]->(t) SET r.dosage = "[DUMMY] placeholder dosis, bukan rekomendasi", r.withdrawal_period = "[DUMMY] Tidak berlaku", r.data_status = "dummy";
