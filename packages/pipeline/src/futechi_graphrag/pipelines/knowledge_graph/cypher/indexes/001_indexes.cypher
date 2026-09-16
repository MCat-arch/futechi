CREATE INDEX visualfeature_name_idx IF NOT EXISTS FOR (vf:VisualFeature) ON (vf.name);
CREATE INDEX symptom_name_idx IF NOT EXISTS FOR (s:Symptom) ON (s.name);
CREATE INDEX environmentalcondition_name_idx IF NOT EXISTS FOR (ec:EnvironmentalCondition) ON (ec.name);
CREATE INDEX disease_name_idx IF NOT EXISTS FOR (d:Disease) ON (d.name);
