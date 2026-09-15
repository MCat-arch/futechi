// =====================================================================
// Seed 001 -- Katalog penyakit/kondisi ayam petelur (inisialisasi awal graph)
//
// SUMBER: tabel "Penyakit / Kondisi -- Gejala visual yang dapat difoto --
// Validasi -- Referensi -- Tingkat akurasi" (brief proyek, 2026-09-15).
// Semua data di file ini berstatus data_status = "draft_literature":
// diturunkan dari tabel tsb, BELUM direview dokter hewan.
//
// Keputusan pemodelan:
//   - "Mismanagement" & "Feed Quality" BUKAN penyakit (sesuai kolom validasi)
//     -> dimodelkan sebagai EnvironmentalCondition (source manual_inspection /
//        visual_observation) + InspectionAction.
//   - Gejala yang tidak bisa dinilai dari foto (rales/audio, bau, catatan
//     produksi/mortalitas) -> Symptom, bukan VisualFeature.
//   - specificity mengikuti aturan di ontology/relationship_definitions.yaml.
//   - onset_stage HANYA diisi bila sumber menyebutnya (mis. "kronis",
//     "tanpa gejala awal"); selebihnya dikosongkan, bukan ditebak.
//   - TIDAK ada MedicalTreatment: tabel sumber tidak memuat obat/dosis.
//   - Mitigasi & relasi lingkungan di luar tabel ada di 002 (draft terpisah).
//
// Format: SATU statement per baris/blok (diakhiri ";"). Relasi memakai
// MATCH by id lalu MERGE tanpa property + SET, supaya idempotent dan tidak
// menduplikasi relasi saat property berubah.
// =====================================================================

// ---------------------------------------------------------------------
// Disease
// ---------------------------------------------------------------------
MERGE (d:Disease {id: "DIS-001"})
SET d.name = "CRD (Mycoplasma gallisepticum)",
    d.desc = "Penyakit pernapasan kronis akibat infeksi Mycoplasma gallisepticum.",
    d.condition_type = "infectious_bacterial",
    d.base_severity = "medium",
    d.notifiable = false,
    d.validation_note = "Sesuai untuk rales, konjungtivitis, dan leleran hidung. Mata cekung tidak khas CRD (lebih mengarah ke dehidrasi).",
    d.diagnostic_note = "PCR real-time: sensitivitas ~65-80%, spesifisitas ~95-100%. Serologi sensitivitas tinggi tetapi tidak membedakan infeksi aktif vs paparan.",
    d.reference_hint = "pmc.ncbi.nlm.nih (+2), pubmed.ncbi.nlm.nih (+2)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-002"})
SET d.name = "aMPV / Swollen Head Syndrome",
    d.desc = "Infeksi avian metapneumovirus dengan pembengkakan kepala dan tanda respirasi.",
    d.condition_type = "infectious_viral",
    d.base_severity = "medium",
    d.notifiable = false,
    d.validation_note = "Sesuai untuk pembengkakan kepala dan tanda respirasi. SHS sering melibatkan infeksi sekunder (E. coli, Mycoplasma).",
    d.diagnostic_note = "Diagnosis definitif memerlukan PCR/RT-PCR atau isolasi virus. Tidak ada angka sensitivitas/spesifisitas tunggal yang baku untuk diagnosis klinis saja.",
    d.reference_hint = "msdvetmanual (+1), wecahn",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-003"})
SET d.name = "Infectious Coryza",
    d.desc = "Infeksi bakteri saluran pernapasan atas dengan pembengkakan wajah dan leleran hidung.",
    d.condition_type = "infectious_bacterial",
    d.base_severity = "medium",
    d.notifiable = false,
    d.validation_note = "Sesuai untuk pembengkakan wajah dan leleran hidung. Bau busuk tidak dapat dinilai dari foto.",
    d.diagnostic_note = "PCR sinus infraorbital dilaporkan lebih akurat daripada kultur. Satu studi melaporkan kesepakatan ~98,5% dengan isolat dan sensitivitas diagnostik ~98,5% vs PCR konvensional.",
    d.reference_hint = "pubmed.ncbi.nlm.nih (+3), zvjz.journals.ekb",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-004"})
SET d.name = "Infectious Bronchitis (IB)",
    d.desc = "Infeksi virus pada saluran pernapasan dan saluran reproduksi yang menurunkan kualitas telur.",
    d.condition_type = "infectious_viral",
    d.base_severity = "medium",
    d.notifiable = false,
    d.validation_note = "Sesuai untuk tanda respirasi ringan dan kelainan telur. Telur abnormal tidak spesifik hanya untuk IB.",
    d.diagnostic_note = "Diagnosis memerlukan PCR/sequencing untuk strain. Tidak ada angka sensitivitas/spesifisitas tunggal untuk gejala klinis atau kelainan telur saja.",
    d.reference_hint = "msdvetmanual (+2)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-005"})
SET d.name = "Infectious Laryngotracheitis (ILT)",
    d.desc = "Infeksi virus pada laring dan trakea dengan gangguan napas berat.",
    d.condition_type = "infectious_viral",
    d.base_severity = "high",
    d.notifiable = false,
    d.validation_note = "Sesuai untuk bentuk berat. Darah tidak selalu ada dan tidak eksklusif untuk ILT.",
    d.diagnostic_note = "Pada kasus berat, tanda klinis + nekropsi cukup untuk diagnosis presumtif. Konfirmasi dengan histopatologi trakea dan PCR. Satu studi lapangan melaporkan spesifisitas ~70% dan sensitivitas ~55% untuk diagnosis klinis+nekropsi vs serologi.",
    d.reference_hint = "edis.ifas.ufl (+1), msdvetmanual",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-006"})
SET d.name = "CCRD (Kompleks Penyakit Respirasi Kronis)",
    d.desc = "Kompleks penyakit respirasi kronis dengan infeksi sekunder, bukan diagnosis etiologis tunggal.",
    d.condition_type = "disease_complex",
    d.base_severity = "high",
    d.notifiable = false,
    d.validation_note = "Perlu koreksi: CCRD bukan diagnosis etiologis tunggal. Lebih tepat disebut kompleks penyakit respirasi kronis dengan infeksi sekunder.",
    d.diagnostic_note = "Tidak ada akurasi khusus. Diagnosis bergantung pada identifikasi agen primer dan sekunder (MG, E. coli, virus respirasi).",
    d.reference_hint = "pmc.ncbi.nlm.nih (+1)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-007"})
SET d.name = "Newcastle Disease (ND)",
    d.desc = "Infeksi virus Newcastle Disease dengan tanda saraf, gangguan pencernaan, dan penurunan produksi.",
    d.condition_type = "infectious_viral",
    d.base_severity = "critical",
    d.notifiable = true,
    d.validation_note = "Sesuai untuk tanda saraf dan produksi. Diare hijau dan tortikolis tidak patognomonik.",
    d.diagnostic_note = "Diagnosis definitif memerlukan isolasi virus/PCR/sequencing. Variasi klinis tinggi sehingga konfirmasi lab diperlukan.",
    d.reference_hint = "tandfonline (+1), pmc.ncbi.nlm.nih",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-008"})
SET d.name = "Avian Influenza H9 (LPAI)",
    d.desc = "Infeksi avian influenza H9 patogenisitas rendah, sering ringan atau tanpa gejala jelas.",
    d.condition_type = "infectious_viral",
    d.base_severity = "medium",
    d.notifiable = false,
    d.validation_note = "Sesuai bahwa H9N2 dapat asimtomatik atau ringan, namun tidak dapat dibedakan dari CRD hanya dari foto.",
    d.diagnostic_note = "Diagnosis memerlukan PCR/RT-PCR. H9N2 sering ringan, tetapi dapat berat dengan infeksi sekunder atau strain tertentu.",
    d.reference_hint = "pmc.ncbi.nlm.nih",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-009"})
SET d.name = "Avian Influenza H5 (HPAI)",
    d.desc = "Infeksi avian influenza H5 patogenisitas tinggi dengan kematian mendadak tinggi.",
    d.condition_type = "infectious_viral",
    d.base_severity = "critical",
    d.notifiable = true,
    d.validation_note = "Sesuai untuk kematian mendadak dan sianosis. Petechiae di kaki tidak spesifik HPAI.",
    d.diagnostic_note = "Diagnosis definitif memerlukan PCR/sequencing. Tanda klinis sangat bervariasi, dari kematian mendadak tanpa tanda hingga penyakit berat.",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-010"})
SET d.name = "Infectious Bursal Disease (IBD/Gumboro)",
    d.desc = "Infeksi virus pada bursa Fabricius yang menyebabkan imunosupresi.",
    d.condition_type = "infectious_viral",
    d.base_severity = "high",
    d.notifiable = false,
    d.validation_note = "Sesuai untuk ayam muda. Pada layer dewasa lebih sering imunosupresi subklinis. Diare putih tidak spesifik.",
    d.diagnostic_note = "Diagnosis klinis + nekropsi bursa khas. Konfirmasi dengan deteksi antigen/genom virus atau serologi. Tidak ada angka sensitivitas/spesifisitas tunggal untuk gejala saja.",
    d.reference_hint = "fao (+2)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-011"})
SET d.name = "Reovirus / Viral Arthritis (Tenosynovitis)",
    d.desc = "Infeksi reovirus dengan radang sendi dan selaput tendon.",
    d.condition_type = "infectious_viral",
    d.base_severity = "medium",
    d.notifiable = false,
    d.validation_note = "Sesuai untuk bentuk artritis/tenosynovitis. Pembengkakan hock juga dapat disebabkan bakteri, trauma, atau masalah nutrisi.",
    d.diagnostic_note = "Diagnosis memerlukan PCR/RT-PCR atau isolasi virus. Serologi hanya menunjukkan paparan, bukan penyakit aktif.",
    d.reference_hint = "pubmed.ncbi.nlm.nih (+2), woah (+1)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-012"})
SET d.name = "Egg Drop Syndrome '76 (EDS)",
    d.desc = "Infeksi virus yang menurunkan kualitas kerabang telur, ayam sering tampak sehat.",
    d.condition_type = "infectious_viral",
    d.base_severity = "low",
    d.notifiable = false,
    d.validation_note = "Sangat sesuai. Ayam sering tanpa gejala klinis lain.",
    d.diagnostic_note = "Diagnosis dengan PCR atau HI. Tanda telur saja tidak spesifik (IB, AI, ND, heat stress, gangguan nutrisi juga dapat menyebabkan telur abnormal).",
    d.reference_hint = "pmc.ncbi.nlm.nih (+3)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-013"})
SET d.name = "Koksidiosis",
    d.desc = "Infeksi protozoa Eimeria pada usus.",
    d.condition_type = "parasitic",
    d.base_severity = "medium",
    d.notifiable = false,
    d.validation_note = "Sesuai untuk beberapa spesies Eimeria (terutama E. tenella yang berdarah). Tidak semua koksidiosis berdarah.",
    d.diagnostic_note = "Diagnosis praktis: lesi usus + mikroskop oocyst. Tidak ada angka sensitivitas/spesifisitas tunggal untuk gejala feses saja.",
    d.reference_hint = "pubmed.ncbi.nlm.nih (+2)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-014"})
SET d.name = "Helminthiasis (Cacingan)",
    d.desc = "Infeksi cacing pada saluran pencernaan.",
    d.condition_type = "parasitic",
    d.base_severity = "low",
    d.notifiable = false,
    d.validation_note = "Sesuai sebagai skrining kasar. Banyak infeksi subklinis dan cacing tidak selalu terlihat.",
    d.diagnostic_note = "Diagnosis definitif dengan nekropsi atau uji feses (flotasi, McMaster). PCR tersedia untuk beberapa spesies.",
    d.reference_hint = "api.drum.lib.umd (+1)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-015"})
SET d.name = "Necrotic Enteritis (NE)",
    d.desc = "Radang nekrotik usus akibat Clostridium perfringens, sering subklinis.",
    d.condition_type = "infectious_bacterial",
    d.base_severity = "high",
    d.notifiable = false,
    d.validation_note = "Perlu koreksi: NE sering subklinis. Tanda klinis tidak spesifik dan mirip koksidiosis atau gangguan usus lain.",
    d.diagnostic_note = "Diagnosis memerlukan lesi usus + histopatologi + deteksi C. perfringens dan toksin (mis. netB). Tidak ada akurasi untuk gejala feses saja.",
    d.reference_hint = "link.springer (+2)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-016"})
SET d.name = "Mikotoksikosis (Mycotoxin)",
    d.desc = "Gangguan kesehatan akibat pakan tercemar mikotoksin.",
    d.condition_type = "toxic",
    d.base_severity = "medium",
    d.notifiable = false,
    d.validation_note = "Perlu koreksi: jamur terlihat tidak menjamin ada mikotoksin, dan tidak ada jamur terlihat tidak menjamin bebas toksin.",
    d.diagnostic_note = "Diagnosis definitif dengan deteksi dan kuantifikasi toksin (HPLC/ELISA). Tanda klinis sangat bervariasi tergantung jenis dan dosis toksin.",
    d.reference_hint = "pubmed.ncbi.nlm.nih (+2)",
    d.data_status = "draft_literature";

MERGE (d:Disease {id: "DIS-017"})
SET d.name = "Heat Stress",
    d.desc = "Stres panas akibat suhu dan kelembapan lingkungan yang tinggi.",
    d.condition_type = "environmental",
    d.base_severity = "high",
    d.notifiable = false,
    d.validation_note = "Sesuai untuk panting, sayap terbuka, dan peningkatan minum. Jengger kebiruan bukan tanda utama dan harus dianggap tanda bahaya.",
    d.diagnostic_note = "Tidak ada angka sensitivitas/spesifisitas. Diagnosis berdasarkan kombinasi tanda perilaku, fisiologi, dan parameter lingkungan (suhu, kelembapan, THI).",
    d.reference_hint = "pmc.ncbi.nlm.nih (+2)",
    d.data_status = "draft_literature";

// ---------------------------------------------------------------------
// VisualFeature (name/observation_target/description WAJIB sama dengan canonical_terms.yaml)
// ---------------------------------------------------------------------
MERGE (n:VisualFeature {id: "VF-001"}) SET n.name = "lowered_head_posture", n.observation_target = "bird", n.description = "Ayam lesu: kepala tertunduk, mata setengah tertutup, kurang responsif";
MERGE (n:VisualFeature {id: "VF-002"}) SET n.name = "irregular_feather_appearance", n.observation_target = "bird", n.description = "Bulu kusam, kusut, atau berdiri tidak rapi";
MERGE (n:VisualFeature {id: "VF-003"}) SET n.name = "watery_foamy_eyes", n.observation_target = "bird", n.description = "Mata berair atau ada busa di sudut mata";
MERGE (n:VisualFeature {id: "VF-004"}) SET n.name = "conjunctivitis", n.observation_target = "bird", n.description = "Kelopak/selaput mata merah dan meradang";
MERGE (n:VisualFeature {id: "VF-005"}) SET n.name = "mild_infraorbital_sinus_swelling", n.observation_target = "bird", n.description = "Pembengkakan ringan di bawah atau depan mata (sinus infraorbital)";
MERGE (n:VisualFeature {id: "VF-006"}) SET n.name = "nasal_discharge", n.observation_target = "bird", n.description = "Leleran atau cairan keluar dari lubang hidung";
MERGE (n:VisualFeature {id: "VF-007"}) SET n.name = "wet_feathers_around_nostrils", n.observation_target = "bird", n.description = "Bulu di sekitar lubang hidung basah atau kotor";
MERGE (n:VisualFeature {id: "VF-008"}) SET n.name = "marked_head_swelling", n.observation_target = "bird", n.description = "Pembengkakan kepala yang nyata di sekitar mata dan wajah";
MERGE (n:VisualFeature {id: "VF-009"}) SET n.name = "swollen_eyes_shut", n.observation_target = "bird", n.description = "Mata bengkak sampai tertutup";
MERGE (n:VisualFeature {id: "VF-010"}) SET n.name = "torticollis", n.observation_target = "bird", n.description = "Leher terpuntir atau kepala miring abnormal";
MERGE (n:VisualFeature {id: "VF-011"}) SET n.name = "facial_wattle_swelling", n.observation_target = "bird", n.description = "Wajah bengkak, terutama di sekitar mata dan pial";
MERGE (n:VisualFeature {id: "VF-012"}) SET n.name = "matted_facial_feathers", n.observation_target = "bird", n.description = "Bulu wajah menggumpal karena eksudat";
MERGE (n:VisualFeature {id: "VF-013"}) SET n.name = "open_mouth_breathing", n.observation_target = "bird", n.description = "Bernapas dengan mulut terbuka atau megap-megap";
MERGE (n:VisualFeature {id: "VF-014"}) SET n.name = "gasping_neck_extended", n.observation_target = "bird", n.description = "Megap dengan leher menjulur ke atas dan mulut terbuka";
MERGE (n:VisualFeature {id: "VF-015"}) SET n.name = "bloody_mucus_beak", n.observation_target = "bird", n.description = "Lendir bercampur darah di sekitar paruh";
MERGE (n:VisualFeature {id: "VF-016"}) SET n.name = "head_tremor", n.observation_target = "bird", n.description = "Kepala gemetar atau tremor";
MERGE (n:VisualFeature {id: "VF-017"}) SET n.name = "paralysis_staggering_gait", n.observation_target = "bird", n.description = "Kelumpuhan, tidak mampu berdiri, atau jalan sempoyongan";
MERGE (n:VisualFeature {id: "VF-018"}) SET n.name = "sunken_eyes", n.observation_target = "bird", n.description = "Mata cekung (tanda dehidrasi)";
MERGE (n:VisualFeature {id: "VF-019"}) SET n.name = "pasty_vent", n.observation_target = "bird", n.description = "Bulu sekitar kloaka basah, kotor, atau menggumpal";
MERGE (n:VisualFeature {id: "VF-020"}) SET n.name = "pale_comb", n.observation_target = "bird", n.description = "Jengger dan pial pucat";
MERGE (n:VisualFeature {id: "VF-021"}) SET n.name = "cyanotic_comb_wattle", n.observation_target = "bird", n.description = "Jengger atau pial kebiruan sampai kehitaman (sianosis)";
MERGE (n:VisualFeature {id: "VF-022"}) SET n.name = "shank_petechiae", n.observation_target = "bird", n.description = "Bintik perdarahan (petechiae) pada kulit kaki";
MERGE (n:VisualFeature {id: "VF-023"}) SET n.name = "emaciation", n.observation_target = "bird", n.description = "Badan kurus, tulang dada menonjol";
MERGE (n:VisualFeature {id: "VF-024"}) SET n.name = "lameness", n.observation_target = "bird", n.description = "Pincang, sulit berjalan atau berdiri";
MERGE (n:VisualFeature {id: "VF-025"}) SET n.name = "swollen_hock_joint", n.observation_target = "bird", n.description = "Sendi hock (tumit) bengkak";
MERGE (n:VisualFeature {id: "VF-026"}) SET n.name = "wings_held_away_from_body", n.observation_target = "bird", n.description = "Sayap dibuka atau dijauhkan dari badan";
MERGE (n:VisualFeature {id: "VF-027"}) SET n.name = "diarrhea", n.observation_target = "feces_litter", n.description = "Feses encer (diare) tanpa warna khas";
MERGE (n:VisualFeature {id: "VF-028"}) SET n.name = "green_diarrhea", n.observation_target = "feces_litter", n.description = "Feses encer berwarna kehijauan";
MERGE (n:VisualFeature {id: "VF-029"}) SET n.name = "white_watery_diarrhea", n.observation_target = "feces_litter", n.description = "Feses encer berwarna putih";
MERGE (n:VisualFeature {id: "VF-030"}) SET n.name = "dark_mucoid_diarrhea", n.observation_target = "feces_litter", n.description = "Feses gelap dan berlendir";
MERGE (n:VisualFeature {id: "VF-031"}) SET n.name = "bloody_feces", n.observation_target = "feces_litter", n.description = "Darah pada feses atau litter";
MERGE (n:VisualFeature {id: "VF-032"}) SET n.name = "visible_worms_in_feces", n.observation_target = "feces_litter", n.description = "Cacing terlihat pada feses";
MERGE (n:VisualFeature {id: "VF-033"}) SET n.name = "thin_soft_eggshell", n.observation_target = "egg", n.description = "Kerabang telur tipis atau lembek";
MERGE (n:VisualFeature {id: "VF-034"}) SET n.name = "shell_less_egg", n.observation_target = "egg", n.description = "Telur tanpa kerabang";
MERGE (n:VisualFeature {id: "VF-035"}) SET n.name = "rough_wrinkled_eggshell", n.observation_target = "egg", n.description = "Kerabang kasar atau bergelombang";
MERGE (n:VisualFeature {id: "VF-036"}) SET n.name = "misshapen_egg", n.observation_target = "egg", n.description = "Bentuk telur abnormal";
MERGE (n:VisualFeature {id: "VF-037"}) SET n.name = "pale_uneven_eggshell", n.observation_target = "egg", n.description = "Warna kerabang pucat atau pigmentasi tidak merata";
MERGE (n:VisualFeature {id: "VF-038"}) SET n.name = "visible_mold_on_feed", n.observation_target = "feed", n.description = "Jamur terlihat pada pakan (biru-hijau atau hitam)";
MERGE (n:VisualFeature {id: "VF-039"}) SET n.name = "caked_damp_feed", n.observation_target = "feed", n.description = "Pakan menggumpal atau lembap";
MERGE (n:VisualFeature {id: "VF-040"}) SET n.name = "uneven_flock_growth", n.observation_target = "flock", n.description = "Ukuran atau pertumbuhan ayam dalam kelompok tidak seragam";
MERGE (n:VisualFeature {id: "VF-041"}) SET n.name = "huddling_in_shade_or_near_fan", n.observation_target = "flock", n.description = "Ayam berkerumun di area teduh atau dekat kipas";

// ---------------------------------------------------------------------
// Symptom (tidak dapat dinilai dari foto)
// ---------------------------------------------------------------------
MERGE (n:Symptom {id: "SY-001"}) SET n.name = "tracheal_rales", n.observation_mode = "audio", n.description = "Suara ngorok (rales) saat bernapas";
MERGE (n:Symptom {id: "SY-002"}) SET n.name = "coughing", n.observation_mode = "audio", n.description = "Batuk";
MERGE (n:Symptom {id: "SY-003"}) SET n.name = "foul_odor_exudate", n.observation_mode = "olfactory", n.description = "Bau busuk dari eksudat wajah atau hidung";
MERGE (n:Symptom {id: "SY-004"}) SET n.name = "egg_production_drop", n.observation_mode = "production_record", n.description = "Penurunan produksi telur";
MERGE (n:Symptom {id: "SY-005"}) SET n.name = "sudden_high_mortality", n.observation_mode = "mortality_record", n.description = "Kematian mendadak dalam jumlah tinggi";
MERGE (n:Symptom {id: "SY-006"}) SET n.name = "increased_mortality", n.observation_mode = "mortality_record", n.description = "Mortalitas meningkat bertahap";
MERGE (n:Symptom {id: "SY-007"}) SET n.name = "increased_water_intake", n.observation_mode = "production_record", n.description = "Konsumsi air minum meningkat";
MERGE (n:Symptom {id: "SY-008"}) SET n.name = "decreased_performance", n.observation_mode = "production_record", n.description = "Performa (bobot atau produksi) menurun";

// ---------------------------------------------------------------------
// EnvironmentalCondition (sensor + faktor manajemen dari baris "Mismanagement" & "Feed Quality")
// ---------------------------------------------------------------------
MERGE (n:EnvironmentalCondition {id: "EC-001"}) SET n.name = "temperature_attention", n.source = "sensor", n.description = "Suhu kandang di atas ambang perhatian", n.threshold_ref = "suhu > 30 C (nilai awal sensor_normalizer, perlu kalibrasi)";
MERGE (n:EnvironmentalCondition {id: "EC-002"}) SET n.name = "humidity_attention", n.source = "sensor", n.description = "Kelembapan kandang di atas ambang perhatian", n.threshold_ref = "RH > 75% (nilai awal sensor_normalizer, perlu kalibrasi)";
MERGE (n:EnvironmentalCondition {id: "EC-003"}) SET n.name = "ammonia_attention", n.source = "sensor", n.description = "Kadar amonia kandang di atas ambang perhatian", n.threshold_ref = "NH3 > 20 ppm (nilai awal sensor_normalizer, ambang perlu ditentukan dari literatur)";
MERGE (n:EnvironmentalCondition {id: "EC-004"}) SET n.name = "overcrowding", n.source = "manual_inspection", n.description = "Kepadatan kandang berlebih";
MERGE (n:EnvironmentalCondition {id: "EC-005"}) SET n.name = "wet_litter", n.source = "manual_inspection", n.description = "Litter atau alas kandang basah";
MERGE (n:EnvironmentalCondition {id: "EC-006"}) SET n.name = "uneven_flock_clustering", n.source = "visual_observation", n.description = "Ayam menggerombol tidak merata";
MERGE (n:EnvironmentalCondition {id: "EC-007"}) SET n.name = "feather_pecking_cannibalism", n.source = "visual_observation", n.description = "Patuk bulu atau kanibalisme";
MERGE (n:EnvironmentalCondition {id: "EC-008"}) SET n.name = "poor_feed_quality", n.source = "manual_inspection", n.description = "Inspeksi visual pakan buruk (warna, bau, tekstur, debu, gumpalan, kelembapan)";

// ---------------------------------------------------------------------
// InspectionAction (pemeriksaan peternak + rujukan konfirmasi dari kolom "Tingkat akurasi")
// ---------------------------------------------------------------------
MERGE (n:InspectionAction {id: "IA-001"}) SET n.name = "observe_breathing", n.performed_by = "farmer", n.instruction = "Dengarkan suara napas ayam dari jarak dekat selama 30 detik. Catat ada tidaknya rales, batuk, atau megap.";
MERGE (n:InspectionAction {id: "IA-002"}) SET n.name = "check_eyes_nose_sinus", n.performed_by = "farmer", n.instruction = "Periksa mata, lubang hidung, dan area sinus: leleran, busa, bengkak, atau kelopak merah.";
MERGE (n:InspectionAction {id: "IA-003"}) SET n.name = "check_exudate_odor", n.performed_by = "farmer", n.instruction = "Cium apakah eksudat wajah atau hidung berbau busuk.";
MERGE (n:InspectionAction {id: "IA-004"}) SET n.name = "review_egg_production_quality", n.performed_by = "farmer", n.instruction = "Cek catatan produksi telur 7 hari terakhir dan periksa kerabang: tipis, lembek, tanpa kerabang, kasar, bentuk, dan warna.";
MERGE (n:InspectionAction {id: "IA-005"}) SET n.name = "check_neurological_signs", n.performed_by = "farmer", n.instruction = "Amati ayam 1-2 menit: leher terpuntir, tremor kepala, keseimbangan, dan kemampuan berdiri.";
MERGE (n:InspectionAction {id: "IA-006"}) SET n.name = "review_mortality_records", n.performed_by = "farmer", n.instruction = "Bandingkan jumlah kematian harian di blok ini dengan hari-hari sebelumnya.";
MERGE (n:InspectionAction {id: "IA-007"}) SET n.name = "inspect_feces", n.performed_by = "farmer", n.instruction = "Periksa feses segar: konsistensi, warna (hijau, putih, gelap), lendir, darah, dan cacing.";
MERGE (n:InspectionAction {id: "IA-008"}) SET n.name = "check_joints_gait", n.performed_by = "farmer", n.instruction = "Amati cara berjalan dan raba sendi hock: bengkak, hangat, atau nyeri.";
MERGE (n:InspectionAction {id: "IA-009"}) SET n.name = "inspect_feed_quality", n.performed_by = "farmer", n.instruction = "Periksa pakan: warna, bau, tekstur, debu, gumpalan, kelembapan, dan jamur. Inspeksi visual tidak dapat memastikan ada atau tidaknya mikotoksin.";
MERGE (n:InspectionAction {id: "IA-010"}) SET n.name = "check_environment_thi", n.performed_by = "farmer", n.instruction = "Cek suhu, kelembapan (THI), ventilasi, dan konsumsi air minum.";
MERGE (n:InspectionAction {id: "IA-011"}) SET n.name = "check_stocking_management", n.performed_by = "farmer", n.instruction = "Periksa kepadatan kandang, kondisi litter, pola berkerumun, dan tanda patuk bulu.";
MERGE (n:InspectionAction {id: "IA-012"}) SET n.name = "refer_pcr_test", n.performed_by = "veterinarian_lab", n.instruction = "Hubungi dokter hewan untuk pengambilan sampel swab dan uji PCR/RT-PCR.";
MERGE (n:InspectionAction {id: "IA-013"}) SET n.name = "refer_necropsy", n.performed_by = "veterinarian_lab", n.instruction = "Serahkan ayam sakit atau bangkai ke dokter hewan untuk nekropsi dan histopatologi.";
MERGE (n:InspectionAction {id: "IA-014"}) SET n.name = "refer_fecal_parasitology", n.performed_by = "veterinarian_lab", n.instruction = "Kirim sampel feses ke laboratorium untuk uji flotasi/McMaster dan pemeriksaan oocyst.";
MERGE (n:InspectionAction {id: "IA-015"}) SET n.name = "refer_feed_mycotoxin_test", n.performed_by = "veterinarian_lab", n.instruction = "Kirim sampel pakan ke laboratorium untuk uji mikotoksin (HPLC/ELISA).";
MERGE (n:InspectionAction {id: "IA-016"}) SET n.name = "refer_serology_test", n.performed_by = "veterinarian_lab", n.instruction = "Hubungi dokter hewan untuk uji serologi (mis. HI). Serologi menunjukkan paparan, belum tentu infeksi aktif.";

// ---------------------------------------------------------------------
// HAS_VISUAL_FEATURE
// ---------------------------------------------------------------------
// DIS-001 CRD
MATCH (d:Disease {id: "DIS-001"}), (t:VisualFeature {id: "VF-003"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium";
MATCH (d:Disease {id: "DIS-001"}), (t:VisualFeature {id: "VF-004"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-001"}), (t:VisualFeature {id: "VF-005"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium", r.clinical_note = "Pembengkakan ringan";
MATCH (d:Disease {id: "DIS-001"}), (t:VisualFeature {id: "VF-006"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-001"}), (t:VisualFeature {id: "VF-007"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium";
MATCH (d:Disease {id: "DIS-001"}), (t:VisualFeature {id: "VF-018"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Tidak khas CRD, lebih mengarah ke dehidrasi";
// DIS-002 aMPV / SHS
MATCH (d:Disease {id: "DIS-002"}), (t:VisualFeature {id: "VF-008"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "high", r.clinical_note = "Pembengkakan periorbital/infraorbital nyata";
MATCH (d:Disease {id: "DIS-002"}), (t:VisualFeature {id: "VF-009"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "high";
MATCH (d:Disease {id: "DIS-002"}), (t:VisualFeature {id: "VF-004"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-002"}), (t:VisualFeature {id: "VF-006"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-002"}), (t:VisualFeature {id: "VF-010"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Kadang, pada kasus berat";
// DIS-003 Infectious Coryza
MATCH (d:Disease {id: "DIS-003"}), (t:VisualFeature {id: "VF-011"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "high";
MATCH (d:Disease {id: "DIS-003"}), (t:VisualFeature {id: "VF-006"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Leleran hidung kental";
MATCH (d:Disease {id: "DIS-003"}), (t:VisualFeature {id: "VF-004"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-003"}), (t:VisualFeature {id: "VF-012"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium";
MATCH (d:Disease {id: "DIS-003"}), (t:VisualFeature {id: "VF-027"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Kadang diare";
// DIS-004 Infectious Bronchitis
MATCH (d:Disease {id: "DIS-004"}), (t:VisualFeature {id: "VF-013"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Megap ringan";
MATCH (d:Disease {id: "DIS-004"}), (t:VisualFeature {id: "VF-004"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-004"}), (t:VisualFeature {id: "VF-033"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Telur abnormal tidak spesifik hanya untuk IB";
MATCH (d:Disease {id: "DIS-004"}), (t:VisualFeature {id: "VF-035"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Telur abnormal tidak spesifik hanya untuk IB";
MATCH (d:Disease {id: "DIS-004"}), (t:VisualFeature {id: "VF-036"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Telur abnormal tidak spesifik hanya untuk IB";
MATCH (d:Disease {id: "DIS-004"}), (t:VisualFeature {id: "VF-037"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Telur abnormal tidak spesifik hanya untuk IB";
// DIS-005 ILT
MATCH (d:Disease {id: "DIS-005"}), (t:VisualFeature {id: "VF-014"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "high", r.clinical_note = "Sesuai untuk bentuk berat";
MATCH (d:Disease {id: "DIS-005"}), (t:VisualFeature {id: "VF-013"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-005"}), (t:VisualFeature {id: "VF-015"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium", r.clinical_note = "Darah tidak selalu ada dan tidak eksklusif untuk ILT";
// DIS-006 CCRD (sumber: "kronis" -> onset_stage late)
MATCH (d:Disease {id: "DIS-006"}), (t:VisualFeature {id: "VF-002"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.onset_stage = "late";
MATCH (d:Disease {id: "DIS-006"}), (t:VisualFeature {id: "VF-023"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.onset_stage = "late";
MATCH (d:Disease {id: "DIS-006"}), (t:VisualFeature {id: "VF-006"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.onset_stage = "late", r.clinical_note = "Gejala respirasi lebih parah";
MATCH (d:Disease {id: "DIS-006"}), (t:VisualFeature {id: "VF-013"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.onset_stage = "late", r.clinical_note = "Gejala respirasi lebih parah";
// DIS-007 Newcastle Disease
MATCH (d:Disease {id: "DIS-007"}), (t:VisualFeature {id: "VF-010"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium", r.clinical_note = "Tidak patognomonik";
MATCH (d:Disease {id: "DIS-007"}), (t:VisualFeature {id: "VF-016"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium";
MATCH (d:Disease {id: "DIS-007"}), (t:VisualFeature {id: "VF-017"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium";
MATCH (d:Disease {id: "DIS-007"}), (t:VisualFeature {id: "VF-028"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Diare sering kehijauan, tidak patognomonik";
MATCH (d:Disease {id: "DIS-007"}), (t:VisualFeature {id: "VF-036"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Telur bentuk aneh";
// DIS-008 AI H9 (LPAI)
MATCH (d:Disease {id: "DIS-008"}), (t:VisualFeature {id: "VF-004"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Gejala ringan mirip CRD, tidak dapat dibedakan dari CRD hanya dari foto";
MATCH (d:Disease {id: "DIS-008"}), (t:VisualFeature {id: "VF-006"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Gejala ringan mirip CRD, tidak dapat dibedakan dari CRD hanya dari foto";
// DIS-009 AI H5 (HPAI)
MATCH (d:Disease {id: "DIS-009"}), (t:VisualFeature {id: "VF-021"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "high", r.clinical_note = "Sianosis sesuai untuk HPAI";
MATCH (d:Disease {id: "DIS-009"}), (t:VisualFeature {id: "VF-008"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium";
MATCH (d:Disease {id: "DIS-009"}), (t:VisualFeature {id: "VF-022"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Tidak spesifik HPAI";
// DIS-010 IBD / Gumboro
MATCH (d:Disease {id: "DIS-010"}), (t:VisualFeature {id: "VF-029"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Diare putih tidak spesifik";
MATCH (d:Disease {id: "DIS-010"}), (t:VisualFeature {id: "VF-019"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Pasty vent";
MATCH (d:Disease {id: "DIS-010"}), (t:VisualFeature {id: "VF-001"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Lesu";
MATCH (d:Disease {id: "DIS-010"}), (t:VisualFeature {id: "VF-018"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium", r.clinical_note = "Dehidrasi";
// DIS-011 Reovirus
MATCH (d:Disease {id: "DIS-011"}), (t:VisualFeature {id: "VF-024"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium";
MATCH (d:Disease {id: "DIS-011"}), (t:VisualFeature {id: "VF-025"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium", r.clinical_note = "Juga dapat disebabkan bakteri, trauma, atau masalah nutrisi";
// DIS-012 EDS
MATCH (d:Disease {id: "DIS-012"}), (t:VisualFeature {id: "VF-033"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium", r.clinical_note = "Ayam sering tampak sehat. Tanda telur saja tidak spesifik";
MATCH (d:Disease {id: "DIS-012"}), (t:VisualFeature {id: "VF-034"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium", r.clinical_note = "Ayam sering tampak sehat. Tanda telur saja tidak spesifik";
MATCH (d:Disease {id: "DIS-012"}), (t:VisualFeature {id: "VF-037"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium", r.clinical_note = "Ayam sering tampak sehat. Tanda telur saja tidak spesifik";
// DIS-013 Koksidiosis
MATCH (d:Disease {id: "DIS-013"}), (t:VisualFeature {id: "VF-031"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "medium", r.clinical_note = "Terutama E. tenella. Tidak semua koksidiosis berdarah";
MATCH (d:Disease {id: "DIS-013"}), (t:VisualFeature {id: "VF-019"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Bulu kusut di sekitar kloaka";
MATCH (d:Disease {id: "DIS-013"}), (t:VisualFeature {id: "VF-020"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Anemia";
// DIS-014 Helminthiasis
MATCH (d:Disease {id: "DIS-014"}), (t:VisualFeature {id: "VF-032"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "high", r.clinical_note = "Cacing tidak selalu terlihat, banyak infeksi subklinis";
MATCH (d:Disease {id: "DIS-014"}), (t:VisualFeature {id: "VF-002"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-014"}), (t:VisualFeature {id: "VF-023"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-014"}), (t:VisualFeature {id: "VF-020"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Anemia";
// DIS-015 Necrotic Enteritis
MATCH (d:Disease {id: "DIS-015"}), (t:VisualFeature {id: "VF-030"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Tanda klinis tidak spesifik, mirip koksidiosis atau gangguan usus lain";
MATCH (d:Disease {id: "DIS-015"}), (t:VisualFeature {id: "VF-031"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Kadang berdarah";
MATCH (d:Disease {id: "DIS-015"}), (t:VisualFeature {id: "VF-019"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Bulu kloaka kotor";
// DIS-016 Mikotoksikosis
MATCH (d:Disease {id: "DIS-016"}), (t:VisualFeature {id: "VF-038"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Jamur terlihat tidak menjamin ada mikotoksin";
MATCH (d:Disease {id: "DIS-016"}), (t:VisualFeature {id: "VF-039"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-016"}), (t:VisualFeature {id: "VF-040"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-016"}), (t:VisualFeature {id: "VF-002"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low";
// DIS-017 Heat Stress
MATCH (d:Disease {id: "DIS-017"}), (t:VisualFeature {id: "VF-013"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Panting";
MATCH (d:Disease {id: "DIS-017"}), (t:VisualFeature {id: "VF-026"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "high";
MATCH (d:Disease {id: "DIS-017"}), (t:VisualFeature {id: "VF-041"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "high";
MATCH (d:Disease {id: "DIS-017"}), (t:VisualFeature {id: "VF-020"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Kadang";
MATCH (d:Disease {id: "DIS-017"}), (t:VisualFeature {id: "VF-021"}) MERGE (d)-[r:HAS_VISUAL_FEATURE]->(t) SET r.specificity = "low", r.clinical_note = "Bukan tanda utama, harus dianggap tanda bahaya";

// ---------------------------------------------------------------------
// HAS_SYMPTOM
// ---------------------------------------------------------------------
MATCH (d:Disease {id: "DIS-001"}), (t:Symptom {id: "SY-001"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "low", r.clinical_note = "Rales (audio)";
MATCH (d:Disease {id: "DIS-003"}), (t:Symptom {id: "SY-003"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "medium", r.clinical_note = "Bau busuk tidak dapat dinilai dari foto";
MATCH (d:Disease {id: "DIS-004"}), (t:Symptom {id: "SY-002"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "low", r.clinical_note = "Batuk ringan";
MATCH (d:Disease {id: "DIS-004"}), (t:Symptom {id: "SY-001"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-005"}), (t:Symptom {id: "SY-002"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "medium";
MATCH (d:Disease {id: "DIS-005"}), (t:Symptom {id: "SY-001"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-006"}), (t:Symptom {id: "SY-006"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "medium", r.onset_stage = "late", r.clinical_note = "Mortalitas lebih tinggi";
MATCH (d:Disease {id: "DIS-006"}), (t:Symptom {id: "SY-001"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "low", r.onset_stage = "late";
MATCH (d:Disease {id: "DIS-007"}), (t:Symptom {id: "SY-004"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "low", r.clinical_note = "Penurunan produksi";
MATCH (d:Disease {id: "DIS-008"}), (t:Symptom {id: "SY-004"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "medium", r.clinical_note = "Sering tanpa tanda jelas selain penurunan produksi telur";
MATCH (d:Disease {id: "DIS-008"}), (t:Symptom {id: "SY-001"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "low";
MATCH (d:Disease {id: "DIS-009"}), (t:Symptom {id: "SY-005"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "high", r.onset_stage = "early", r.clinical_note = "Dapat terjadi tanpa gejala awal";
MATCH (d:Disease {id: "DIS-015"}), (t:Symptom {id: "SY-005"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "low", r.clinical_note = "Pada kasus akut";
MATCH (d:Disease {id: "DIS-016"}), (t:Symptom {id: "SY-008"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "low", r.clinical_note = "Performa turun";
MATCH (d:Disease {id: "DIS-017"}), (t:Symptom {id: "SY-007"}) MERGE (d)-[r:HAS_SYMPTOM]->(t) SET r.specificity = "medium", r.clinical_note = "Konsumsi air naik";

// ---------------------------------------------------------------------
// ASSOCIATED_WITH_ENVIRONMENT (hanya yang disebut tabel sumber)
// ---------------------------------------------------------------------
MATCH (d:Disease {id: "DIS-017"}), (t:EnvironmentalCondition {id: "EC-001"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "high", r.data_status = "draft_literature", r.note = "Diagnosis berdasarkan parameter lingkungan (suhu, kelembapan, THI)";
MATCH (d:Disease {id: "DIS-017"}), (t:EnvironmentalCondition {id: "EC-002"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "medium", r.data_status = "draft_literature", r.note = "Diagnosis berdasarkan parameter lingkungan (suhu, kelembapan, THI)";
MATCH (d:Disease {id: "DIS-016"}), (t:EnvironmentalCondition {id: "EC-008"}) MERGE (d)-[r:ASSOCIATED_WITH_ENVIRONMENT]->(t) SET r.strength = "medium", r.data_status = "draft_literature", r.note = "Inspeksi visual pakan tidak menentukan kualitas nutrisi atau mikotoksin";

// ---------------------------------------------------------------------
// REQUIRES_INSPECTION
// ---------------------------------------------------------------------
MATCH (d:Disease {id: "DIS-001"}), (t:InspectionAction {id: "IA-001"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-001"}), (t:InspectionAction {id: "IA-002"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-001"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-001"}), (t:InspectionAction {id: "IA-016"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-002"}), (t:InspectionAction {id: "IA-002"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-002"}), (t:InspectionAction {id: "IA-005"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-002"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-003"}), (t:InspectionAction {id: "IA-002"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-003"}), (t:InspectionAction {id: "IA-003"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-003"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-004"}), (t:InspectionAction {id: "IA-001"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-004"}), (t:InspectionAction {id: "IA-004"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-004"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-005"}), (t:InspectionAction {id: "IA-001"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-005"}), (t:InspectionAction {id: "IA-013"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-005"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-006"}), (t:InspectionAction {id: "IA-001"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-006"}), (t:InspectionAction {id: "IA-006"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-006"}), (t:InspectionAction {id: "IA-013"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-007"}), (t:InspectionAction {id: "IA-005"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-007"}), (t:InspectionAction {id: "IA-007"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-007"}), (t:InspectionAction {id: "IA-004"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-007"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-008"}), (t:InspectionAction {id: "IA-001"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-008"}), (t:InspectionAction {id: "IA-004"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-008"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-009"}), (t:InspectionAction {id: "IA-006"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-009"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-010"}), (t:InspectionAction {id: "IA-007"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-010"}), (t:InspectionAction {id: "IA-013"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-010"}), (t:InspectionAction {id: "IA-016"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-011"}), (t:InspectionAction {id: "IA-008"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-011"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-012"}), (t:InspectionAction {id: "IA-004"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-012"}), (t:InspectionAction {id: "IA-012"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-012"}), (t:InspectionAction {id: "IA-016"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-013"}), (t:InspectionAction {id: "IA-007"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-013"}), (t:InspectionAction {id: "IA-014"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-013"}), (t:InspectionAction {id: "IA-013"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-014"}), (t:InspectionAction {id: "IA-007"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-014"}), (t:InspectionAction {id: "IA-014"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-014"}), (t:InspectionAction {id: "IA-013"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-015"}), (t:InspectionAction {id: "IA-007"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-015"}), (t:InspectionAction {id: "IA-006"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-015"}), (t:InspectionAction {id: "IA-013"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-016"}), (t:InspectionAction {id: "IA-009"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-016"}), (t:InspectionAction {id: "IA-015"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-017"}), (t:InspectionAction {id: "IA-010"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
MATCH (d:Disease {id: "DIS-017"}), (t:InspectionAction {id: "IA-011"}) MERGE (d)-[:REQUIRES_INSPECTION]->(t);
