MERGE (d:Disease {id: "DIS-001"})
SET d.name = "Newcastle Disease",
    d.desc = "Penyakit virus menular menyerang sistem saraf dan pernapasan unggas",
    d.base_severity = "high"

MERGE (vf1:VisualFeature {id: "VF-001"})
SET vf1.name = "lowered_head_posture"

MERGE (vf2:VisualFeature {id: "VF-002"})
SET vf2.name = "irregular_feather_appearance"

MERGE (ec1:EnvironmentalCondition {id: "EC-001"})
SET ec1.name = "humidity_attention"

MERGE (ia1:InspectionAction {id: "IA-001"})
SET ia1.name = "observe_breathing",
    ia1.instruction = "Dengarkan suara napas ayam selama 30 detik dari jarak dekat"

MERGE (ma1:MitigationAction {id: "MA-001"})
SET ma1.name = "increase_ventilation",
    ma1.instruction = "Naikkan kecepatan kipas ventilasi kandang",
    ma1.priority = "high"

MERGE (mt1:MedicalTreatment {id: "MT-001"})
SET mt1.name = "Amoxicillin",
    mt1.dosage = "10mg/kg berat badan, 2x sehari",
    mt1.withdrawal_period = "7 hari"

MERGE (d)-[:HAS_VISUAL_FEATURE {specificity: "high", onset_stage: "early", mechanism: "gangguan neurologis akibat infeksi virus"}]->(vf1)
MERGE (d)-[:HAS_VISUAL_FEATURE {specificity: "low", onset_stage: "middle"}]->(vf2)
MERGE (d)-[:ASSOCIATED_WITH_ENVIRONMENT {strength: "medium"}]->(ec1)
MERGE (d)-[:REQUIRES_INSPECTION]->(ia1)
MERGE (d)-[:MITIGATED_BY]->(ma1)
MERGE (d)-[:TREATED_WITH {dosage: "10mg/kg BB, 2x sehari", withdrawal_period: "7 hari"}]->(mt1);
