// Template retrieval utama Modul B -- SATU query mengambil SEMUA kandidat
// Disease sekaligus (bukan satu-satu), supaya LLM di Modul C bisa
// melakukan multi-hop differential reasoning lintas kandidat.
//
// TIDAK ADA gating pada TREATED_WITH -- akses referensi obat terbuka
// untuk semua user sesuai keputusan desain (urutan TAMPIL-nya yang
// bertahap, diatur di application layer / Case.resolve(), BUKAN di
// query ini).
//
// Parameter:
//   $visual_features        -- list[str], hasil filter confidence Modul A
//   $environment_conditions -- list[str], hasil sensor_normalizer Modul A
//
// Dipanggil oleh: infrastructure/neo4j/repositories/disease_repository.py

// CATATAN PERFORMA: karena ada beberapa OPTIONAL MATCH independen dari d
// (symptom, environment, inspection, mitigation, treatment), Neo4j akan
// membuat cartesian product sementara sebelum di-collect. Untuk ontologi
// skala kecil (15-30 penyakit, sesuai batasan awal proyek) ini tidak
// masalah. Kalau KG membesar signifikan (ratusan penyakit dgn banyak
// relasi), pertimbangkan pecah jadi beberapa subquery terpisah (CALL {})
// atau pakai APOC untuk menghindari blow-up cartesian product.

MATCH (d:Disease)-[hf:HAS_VISUAL_FEATURE]->(vf:VisualFeature)
WHERE vf.name IN $visual_features
OPTIONAL MATCH (d)-[hs:HAS_SYMPTOM]->(s:Symptom)
OPTIONAL MATCH (d)-[ae:ASSOCIATED_WITH_ENVIRONMENT]->(ec:EnvironmentalCondition)
  WHERE ec.name IN $environment_conditions
OPTIONAL MATCH (d)-[:REQUIRES_INSPECTION]->(ia:InspectionAction)
OPTIONAL MATCH (d)-[:MITIGATED_BY]->(ma:MitigationAction)
OPTIONAL MATCH (d)-[tw:TREATED_WITH]->(mt:MedicalTreatment)
RETURN
  d.id AS disease_id,
  d.name AS disease_name,
  d.desc AS disease_desc,
  d.base_severity AS base_severity,
  d.notifiable AS notifiable,
  collect(DISTINCT {
    name: vf.name,
    specificity: hf.specificity,
    onset_stage: hf.onset_stage,
    mechanism: hf.mechanism
  }) AS matched_visual_features,
  collect(DISTINCT {
    name: s.name,
    specificity: hs.specificity,
    onset_stage: hs.onset_stage,
    mechanism: hs.mechanism
  }) AS related_symptoms,
  collect(DISTINCT {
    name: ec.name,
    strength: ae.strength
  }) AS matched_environment,
  collect(DISTINCT {
    name: ia.name,
    instruction: ia.instruction
  }) AS inspection_actions,
  collect(DISTINCT {
    name: ma.name,
    instruction: ma.instruction,
    priority: ma.priority
  }) AS mitigation_actions,
  collect(DISTINCT {
    name: mt.name,
    dosage: tw.dosage,
    withdrawal_period: tw.withdrawal_period
  }) AS medical_treatments
ORDER BY size(matched_visual_features) DESC
LIMIT 20;
