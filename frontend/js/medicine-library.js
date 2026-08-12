// General medicine library — common generic drug names used to power the
// autocomplete on the "Add Prescription" form (see doctor-portal.js,
// openAddPrescriptionModal). This is a static, hand-curated list (not
// pulled from any external API) so it works instantly, offline, and with
// zero dependencies or rate limits. Add/remove names here any time — no
// other file needs to change.
//
// Grouped by category purely for readability; the app just flattens this
// into one list.

// Brand names a Pakistani GP reaches for constantly — shown at the very
// top of the dropdown before the doctor types anything, so the most
// commonly prescribed items never require scrolling or typing.
const PAKISTAN_COMMON_MEDICINES = [
  "Panadol (Paracetamol)",
  "Panadol Extra",
  "Panadol CF",
  "Brufen (Ibuprofen)",
  "Disprin (Aspirin)",
  "Calpol (Paracetamol Syrup)",
  "Augmentin (Co-Amoxiclav)",
  "Amoxil (Amoxicillin)",
  "Flagyl (Metronidazole)",
  "Risek (Omeprazole)",
  "Ponstan (Mefenamic Acid)",
  "Buscopan (Hyoscine Butylbromide)",
  "Zimax (Azithromycin)",
  "Zinnat (Cefuroxime)",
  "Motilium (Domperidone)",
  "Septran (Co-trimoxazole)",
  "Arinac Forte",
  "Grippex",
  "Neurobion Forte",
  "Surbex-Z",
  "ORS (Oral Rehydration Salts)",
  "Eno",
];

const MEDICINE_LIBRARY_BY_CATEGORY = {
  "Analgesics / Antipyretics": [
    "Paracetamol", "Ibuprofen", "Aspirin", "Diclofenac Sodium", "Mefenamic Acid",
    "Naproxen", "Tramadol", "Ketorolac", "Nimesulide", "Celecoxib",
  ],
  "Antibiotics": [
    "Amoxicillin", "Amoxicillin/Clavulanic Acid", "Azithromycin", "Ciprofloxacin",
    "Levofloxacin", "Cefixime", "Cefuroxime", "Ceftriaxone", "Doxycycline",
    "Metronidazole", "Clarithromycin", "Erythromycin", "Flucloxacillin",
    "Co-trimoxazole", "Clindamycin", "Ampicillin", "Cephradine", "Ofloxacin",
    "Nitrofurantoin", "Rifampicin",
  ],
  "Antifungal": [
    "Fluconazole", "Clotrimazole", "Ketoconazole", "Terbinafine", "Miconazole", "Griseofulvin",
  ],
  "Antiviral": [
    "Acyclovir", "Oseltamivir", "Valacyclovir",
  ],
  "Antihistamines / Allergy": [
    "Cetirizine", "Loratadine", "Fexofenadine", "Chlorpheniramine", "Levocetirizine",
    "Diphenhydramine", "Desloratadine", "Montelukast",
  ],
  "Respiratory / Cough & Cold": [
    "Salbutamol", "Montelukast", "Budesonide Inhaler", "Ambroxol", "Dextromethorphan",
    "Guaifenesin", "Bromhexine", "Theophylline", "Ipratropium Bromide",
    "Levosalbutamol", "Pseudoephedrine",
  ],
  "Gastrointestinal": [
    "Omeprazole", "Esomeprazole", "Pantoprazole", "Ranitidine", "Domperidone",
    "Metoclopramide", "Loperamide", "Oral Rehydration Salts (ORS)", "Simethicone",
    "Lactulose", "Sucralfate", "Mebeverine", "Rabeprazole", "Bisacodyl",
    "Ondansetron", "Dicyclomine",
  ],
  "Cardiovascular / Antihypertensive": [
    "Amlodipine", "Losartan", "Atenolol", "Metoprolol", "Enalapril", "Lisinopril",
    "Bisoprolol", "Nifedipine", "Hydrochlorothiazide", "Furosemide",
    "Spironolactone", "Telmisartan", "Valsartan", "Atorvastatin", "Rosuvastatin",
    "Clopidogrel", "Digoxin", "Isosorbide Mononitrate", "Carvedilol",
  ],
  "Antidiabetic": [
    "Metformin", "Glimepiride", "Gliclazide", "Sitagliptin", "Insulin (Regular)",
    "Insulin Glargine", "Pioglitazone", "Vildagliptin", "Empagliflozin",
  ],
  "Vitamins / Supplements": [
    "Multivitamin", "Vitamin D3", "Vitamin B Complex", "Vitamin C", "Folic Acid",
    "Calcium Carbonate", "Ferrous Sulfate", "Zinc Sulfate", "Iron + Folic Acid",
    "Omega-3 Fish Oil", "Vitamin B12 (Cyanocobalamin)", "Magnesium Oxide",
  ],
  "Steroids / Hormones": [
    "Prednisolone", "Dexamethasone", "Hydrocortisone", "Betamethasone", "Levothyroxine",
  ],
  "Topical / Dermatological": [
    "Betamethasone Cream", "Clotrimazole Cream", "Mupirocin Ointment",
    "Hydrocortisone Cream", "Calamine Lotion", "Silver Sulfadiazine Cream",
    "Fusidic Acid Cream", "Permethrin Cream",
  ],
  "Eye / Ear": [
    "Chloramphenicol Eye Drops", "Ciprofloxacin Eye Drops", "Moxifloxacin Eye Drops",
    "Sodium Chloride Eye Drops", "Ofloxacin Ear Drops",
  ],
  "Anti-emetic / Vertigo": [
    "Domperidone", "Ondansetron", "Meclizine", "Betahistine", "Prochlorperazine",
  ],
  "CNS / Psychiatric": [
    "Sertraline", "Fluoxetine", "Escitalopram", "Amitriptyline", "Alprazolam",
    "Diazepam", "Risperidone", "Gabapentin", "Pregabalin", "Sodium Valproate",
    "Carbamazepine", "Zolpidem",
  ],
  "Anticoagulant / Antiplatelet": [
    "Aspirin", "Clopidogrel", "Warfarin", "Enoxaparin", "Rivaroxaban",
  ],
  "Others / General": [
    "Tranexamic Acid", "Hyoscine Butylbromide", "Allopurinol", "Colchicine",
    "Finasteride", "Tamsulosin", "Sildenafil", "Misoprostol", "Methylergometrine",
    "Oxytocin", "Ivermectin", "Albendazole", "Mebendazole",
  ],
};

// Generic names, flattened + de-duplicated + alphabetically sorted.
const GENERIC_MEDICINE_NAMES = Array.from(
  new Set(Object.values(MEDICINE_LIBRARY_BY_CATEGORY).flat())
).sort((a, b) => a.localeCompare(b));

// What the dropdown actually shows: Pakistan-common brand names first
// (so the doctor sees Panadol, Augmentin, etc. before scrolling or typing
// anything), followed by the full generic list.
const MEDICINE_LIBRARY = [...PAKISTAN_COMMON_MEDICINES, ...GENERIC_MEDICINE_NAMES];

// Dosage/strength suggestions for the "Dosage" dropdown. Kept as a plain
// list (not tied to a specific medicine) since one field covers every drug
// on the form — the doctor can still type a value not on this list.
const DOSAGE_OPTIONS = [
  "125mg", "250mg", "500mg", "650mg", "1g (1000mg)",
  "5mg", "10mg", "20mg", "40mg",
  "1 tablet", "2 tablets",
  "5ml", "10ml", "1 tsp (5ml)", "2 tsp (10ml)",
  "1 drop", "2 drops",
  "1 sachet",
];

// Duration suggestions for the "Duration" dropdown.
const DURATION_OPTIONS = [
  "3 days", "5 days", "7 days", "10 days", "14 days",
  "1 week", "2 weeks", "3 weeks",
  "1 month", "2 months", "3 months",
  "Until finished", "As needed (SOS)",
];

window.MEDICINE_LIBRARY = MEDICINE_LIBRARY;
window.MEDICINE_LIBRARY_BY_CATEGORY = MEDICINE_LIBRARY_BY_CATEGORY;
window.PAKISTAN_COMMON_MEDICINES = PAKISTAN_COMMON_MEDICINES;
window.DOSAGE_OPTIONS = DOSAGE_OPTIONS;
window.DURATION_OPTIONS = DURATION_OPTIONS;

// Diagnostic: if this line never shows up in the browser console, this
// file (js/medicine-library.js) never loaded at all — check the Network
// tab for a 404 on it, or a browser cache serving something stale.
console.log(
  `[medicine-library] Loaded: ${MEDICINE_LIBRARY.length} medicines, `
  + `${DOSAGE_OPTIONS.length} dosage options, ${DURATION_OPTIONS.length} duration options.`
);
