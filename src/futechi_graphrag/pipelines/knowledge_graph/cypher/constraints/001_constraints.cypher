CREATE CONSTRAINT disease_id_unique IF NOT EXISTS FOR (d:Disease) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT visualfeature_id_unique IF NOT EXISTS FOR (vf:VisualFeature) REQUIRE vf.id IS UNIQUE;
CREATE CONSTRAINT symptom_id_unique IF NOT EXISTS FOR (s:Symptom) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT environmentalcondition_id_unique IF NOT EXISTS FOR (ec:EnvironmentalCondition) REQUIRE ec.id IS UNIQUE;
CREATE CONSTRAINT inspectionaction_id_unique IF NOT EXISTS FOR (ia:InspectionAction) REQUIRE ia.id IS UNIQUE;
CREATE CONSTRAINT mitigationaction_id_unique IF NOT EXISTS FOR (ma:MitigationAction) REQUIRE ma.id IS UNIQUE;
CREATE CONSTRAINT medicaltreatment_id_unique IF NOT EXISTS FOR (mt:MedicalTreatment) REQUIRE mt.id IS UNIQUE;
