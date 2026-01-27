# Health Profile Form - Complete Field Reference

## All Form Elements from PDF F-HSS-20-0001

### SECTION 1: PERSONAL INFORMATION

#### Basic Personal Details
- [ ] Last Name
- [ ] First Name
- [ ] Middle Name
- [ ] Permanent Address
- [ ] Zip Code
- [ ] Current Address
- [ ] Religion
- [ ] Place of Birth
- [ ] Date of Birth (mm/dd/yyyy)
- [ ] Citizenship
- [ ] Age

#### Status & Contact
- [ ] Gender
  - [ ] Male
  - [ ] Female
- [ ] Civil Status
  - [ ] Single
  - [ ] Married
  - [ ] Widowed
  - [ ] Separated
- [ ] Email Address
- [ ] Mobile No.
- [ ] Telephone No.

#### Designation & Department
- [ ] Designation
  - [ ] Student
  - [ ] Employee
- [ ] Department/College/Office

#### Emergency Contact
- [ ] Name of Guardian
- [ ] Contact No.

---

### SECTION 2: MEDICAL HISTORY

#### A. IMMUNIZATION RECORDS (with Date of Last Immunization)
- [ ] COVID-19 (Date: ___________)
- [ ] Influenza (Date: ___________)
- [ ] Pneumonia (Date: ___________)
- [ ] Polio (Date: ___________)
- [ ] Hepatitis B (Date: ___________)
- [ ] BCG (Date: ___________)
- [ ] DPT/Tetanus (Date: ___________)
- [ ] Rotavirus (Date: ___________)
- [ ] Hib (Date: ___________)
- [ ] Measles/MMR (Date: ___________)
- [ ] Others: (Please specify) _________________

#### B. ILLNESSES/MEDICAL CONDITIONS
- [ ] Measles
- [ ] Mumps
- [ ] Rubella
- [ ] Chickenpox
- [ ] PTB/PKI (Pulmonary Tuberculosis / Pulmonary Koch's Infection)
- [ ] Hypertension
- [ ] Diabetes Mellitus
- [ ] Asthma
- [ ] Others: (Please specify) _________________

#### C. Medical Information
- [ ] Allergies: (Please specify)
  ____________________________________________________

- [ ] Current Medications: (Please specify)
  ____________________________________________________

---

### SECTION 3: OB-GYN HISTORY (For Females Only)

#### Menstrual History
- [ ] Menarche: ___________
- [ ] Duration: ____________
- [ ] Interval: _____________
- [ ] Amount: _____________
- [ ] Symptoms: ___________

#### Obstetric History
- [ ] Obstetric History:
  ____________________________________________________

---

### SECTION 4: PRESENT ILLNESS

- [ ] State history of present illness (if any):
  ____________________________________________________

---

### SECTION 5: PHYSICAL EXAMINATION

#### A. VITAL SIGNS
- [ ] BP (Blood Pressure): ___________
- [ ] HR (Heart Rate): ___________
- [ ] RR (Respiratory Rate): ___________
- [ ] Temp (Temperature): ___________
- [ ] SpO2 (Oxygen Saturation): ___________

#### B. ANTHROPOMETRICS
- [ ] Ht (Height in meters): ___________
- [ ] Wt (Weight in kg): ___________
- [ ] BMI: ___________ (Auto-calculated)
- [ ] Remarks: ___________

#### C. PHYSICAL EXAMINATION FINDINGS

**System Review:**
- [ ] General:
  ____________________________________________________

- [ ] HEENT (Head, Eyes, Ears, Nose, Throat):
  ____________________________________________________

- [ ] Chest and Lungs:
  ____________________________________________________

- [ ] Abdomen:
  ____________________________________________________

- [ ] Genitourinary:
  ____________________________________________________

- [ ] Extremities:
  ____________________________________________________

- [ ] Neurologic:
  ____________________________________________________

- [ ] Other Significant Findings:
  ____________________________________________________

---

### SECTION 6: DIAGNOSTIC TESTS (with Date of Examination and Findings)

- [ ] Chest X-ray
  - Date: ___________
  - Findings: ____________________________________________________

- [ ] CBC (Complete Blood Count)
  - Date: ___________
  - Findings: ____________________________________________________

- [ ] Urinalysis
  - Date: ___________
  - Findings: ____________________________________________________

- [ ] Drug Test
  - Date: ___________
  - Findings: ____________________________________________________

- [ ] Psychological Test
  - Date: ___________
  - Findings: ____________________________________________________

- [ ] HBsAg (Hepatitis B Surface Antigen)
  - Date: ___________
  - Findings: ____________________________________________________

- [ ] Anti-HBs Titer
  - Date: ___________
  - Findings: ____________________________________________________

- [ ] Fecalysis
  - Date: ___________
  - Findings: ____________________________________________________

- [ ] Others: (Please specify)
  ____________________________________________________

---

### SECTION 7: CLINICAL SUMMARY

#### Physician's Assessment
- [ ] Impression:
  ____________________________________________________

#### Final Assessment
- [ ] Final Remarks and Recommendations:
  ____________________________________________________

#### Physician Information
- [ ] Physician's Name: _______________________________
- [ ] Signature: _______________________________
- [ ] Date: _______________________________

---

## Database Field Mapping

### Model Fields by Section

#### SECTION 2: IMMUNIZATION (Boolean Checkboxes + Dates)
```
immunization_covid19 (Boolean) + immunization_covid19_date
immunization_influenza + immunization_influenza_date
immunization_pneumonia + immunization_pneumonia_date
immunization_polio + immunization_polio_date
immunization_hepatitis_b + immunization_hepatitis_b_date
immunization_bcg + immunization_bcg_date
immunization_dpt_tetanus + immunization_dpt_tetanus_date
immunization_rotavirus + immunization_rotavirus_date
immunization_hib + immunization_hib_date
immunization_measles_mmr + immunization_measles_mmr_date
immunization_others (TextField)
```

#### SECTION 2: ILLNESSES (Boolean Checkboxes)
```
illness_measles (Boolean)
illness_mumps (Boolean)
illness_rubella (Boolean)
illness_chickenpox (Boolean)
illness_ptb_pki (Boolean)
illness_hypertension (Boolean)
illness_diabetes (Boolean)
illness_asthma (Boolean)
illness_others (TextField)
```

#### SECTION 5: PHYSICAL EXAM FINDINGS (TextFields)
```
exam_general (TextField)
exam_heent (TextField)
exam_chest_lungs (TextField)
exam_abdomen (TextField)
exam_genitourinary (TextField)
exam_extremities (TextField)
exam_neurologic (TextField)
exam_other_findings (TextField)
```

#### SECTION 6: DIAGNOSTIC TESTS (Boolean + Findings + Dates)
```
test_chest_xray (Boolean) + test_chest_xray_findings (TextField) + test_chest_xray_date
test_cbc + test_cbc_findings + test_cbc_date
test_urinalysis + test_urinalysis_findings + test_urinalysis_date
test_drug_test + test_drug_test_findings + test_drug_test_date
test_psychological + test_psychological_findings + test_psychological_date
test_hbsag + test_hbsag_findings + test_hbsag_date
test_anti_hbs_titer + test_anti_hbs_titer_findings + test_anti_hbs_titer_date
test_fecalysis + test_fecalysis_findings + test_fecalysis_date
test_others (TextField)
```

---

## Form Usage

### Medical History Form
Includes all checkboxes for:
- 10 Immunization vaccines with date fields
- 8 Medical conditions with "Others" option
- Allergies, Current Medications, and Present Illness

### Physical Exam Form
Includes:
- All vital signs (BP, HR, RR, Temp, SpO2)
- Height, Weight, BMI (auto-calculated)
- 8 System review text areas (General, HEENT, Chest/Lungs, Abdomen, Genitourinary, Extremities, Neurologic, Other)

### Diagnostic Tests Form
Includes all 8 standard tests + "Others":
- Each test has: Checkbox, Date field, and Findings text area
- All tests support custom documentation

---

## Total Fields Added

- **Boolean (Checkbox) Fields**: 28 (10 immunizations + 8 illnesses + 8 diagnostic tests)
- **Date Fields**: 28 (paired with checkbox fields)
- **Text Fields**: 20 (8 exam findings + 8 test findings + 2 others + 2 OB-GYN + 1 allergies + 1 medications)
- **Total New Fields**: 76+

---

## Notes for Users

1. **Checkboxes**: Check a box if the patient has received that vaccine or has that medical condition
2. **Dates**: Enter the date when the vaccine was administered or condition was identified
3. **Findings**: For diagnostic tests, enter the actual test results/findings
4. **OB-GYN**: Only relevant for female patients
5. **BMI**: Auto-calculated from Height and Weight
6. **Physical Exam**: Can document findings for each body system

All forms support the complete health profile from the PDF form!
