# Health Profile Form - PDF to Django Model Mapping

## Document Reference
- **Form Number**: F-HSS-20-0001
- **Organization**: Jose Maria College Foundation, Inc.
- **Location**: Philippine-Japan Friendship Highway, Sasa, Davao City, 8000

---

## Form Structure Mapping

### 1. PERSONAL INFORMATION SECTION
**PDF Fields** → **Django Model Fields**

| PDF Field | Model Field | Type | Notes |
|-----------|------------|------|-------|
| Name (Last, First, Middle) | `last_name`, `first_name`, `middle_name` | CharField | Required |
| Permanent Address | `permanent_address` | TextField | Optional |
| Zip Code | `zip_code` | CharField | Max 10 chars |
| Current Address | `current_address` | TextField | Optional |
| Religion | `religion` | CharField | Optional |
| Civil Status | `civil_status` | Choice Field | Single, Married, Widowed, Separated |
| Place of Birth | `place_of_birth` | CharField | Optional |
| Date of Birth (mm/dd/yyyy) | `date_of_birth` | DateField | Optional |
| Citizenship | `citizenship` | CharField | Optional |
| Age | `age` | PositiveIntegerField | Optional |
| Gender | `gender` | Choice Field | Male, Female |
| Email Address | `email_address` | EmailField | Optional |
| Mobile No. | `mobile_number` | CharField | Max 20 chars |
| Telephone No. | `telephone_number` | CharField | Max 20 chars |
| Designation | `designation` | Choice Field | Student, Employee |
| Department/College/Office | `department_college_office` | CharField | Optional |

**Emergency Contact**

| PDF Field | Model Field | Type | Notes |
|-----------|------------|------|-------|
| Name of Guardian | `guardian_name` | CharField | Max 200 chars |
| Contact No. | `guardian_contact` | CharField | Max 20 chars |

---

### 2. MEDICAL HISTORY SECTION

#### Immunization Records
- **Model Field**: `immunization_records` (JSONField)
- **PDF Checkboxes**:
  - COVID-19
  - Influenza
  - Pneumonia
  - Polio
  - Hepatitis B
  - BCG
  - DPT/Tetanus
  - Rotavirus
  - Hib
  - Measles/MMR
  - Others (specify)

**JSON Format Example**:
```json
{
  "covid_19": {"date": "2024-01-15"},
  "influenza": {"date": "2024-01-15"},
  "pneumonia": {"date": "2023-05-10"},
  "others": "Varicella (2023-06-20)"
}
```

#### Illnesses/Medical Conditions
- **Model Field**: `illness_history` (JSONField)
- **PDF Checkboxes**:
  - Measles
  - Mumps
  - Rubella
  - Chickenpox
  - PTB/PKI
  - Hypertension
  - Diabetes Mellitus
  - Asthma
  - Others (specify)

**JSON Format Example**:
```json
[
  {"condition": "Hypertension", "status": "active"},
  {"condition": "Asthma", "status": "managed"}
]
```

#### Allergies
- **Model Field**: `allergies` (TextField)
- **Max**: Unlimited text

#### Current Medications
- **Model Field**: `current_medications` (TextField)
- **Max**: Unlimited text

---

### 3. OB-GYN HISTORY SECTION (Female Only)

| PDF Field | Model Field | Type | Notes |
|-----------|------------|------|-------|
| Menarche | `menarche_age` | PositiveIntegerField | Optional |
| Duration | `menstrual_duration` | CharField | e.g., "5 days" |
| Interval | `menstrual_interval` | CharField | e.g., "28 days" |
| Amount | `menstrual_amount` | CharField | e.g., "Moderate" |
| Symptoms | `menstrual_symptoms` | TextField | Optional |
| Obstetric History | `obstetric_history` | TextField | Optional |

---

### 4. PRESENT ILLNESS SECTION

| PDF Field | Model Field | Type | Notes |
|-----------|------------|------|-------|
| State history of present illness | `present_illness` | TextField | Optional |

---

### 5. PHYSICAL EXAMINATION SECTION

#### Vital Signs
| PDF Field | Model Field | Type | Notes |
|-----------|------------|------|-------|
| BP (Blood Pressure) | `blood_pressure` | CharField | Format: "120/80" |
| HR (Heart Rate) | `heart_rate` | PositiveIntegerField | bpm |
| RR (Respiratory Rate) | `respiratory_rate` | PositiveIntegerField | /min |
| Temp (Temperature) | `temperature` | DecimalField | °C, 1 decimal |
| SpO2 (Oxygen Saturation) | `spo2` | DecimalField | %, 2 decimals |

#### Anthropometrics
| PDF Field | Model Field | Type | Notes |
|-----------|------------|------|-------|
| Ht (Height) | `height` | DecimalField | meters, 2 decimals |
| Wt (Weight) | `weight` | DecimalField | kg, 2 decimals |
| BMI | `bmi` | DecimalField | Auto-calculated |
| Remarks | `bmi_remarks` | CharField | Auto-generated (Underweight/Normal/Overweight/Obese) |

#### Physical Exam Findings
- **Model Field**: `physical_exam_findings` (JSONField)
- **PDF Sections**: General, HEENT, Chest and Lungs, Abdomen, Genitourinary, Extremities, Neurologic

**JSON Format Example**:
```json
{
  "general": "Well-nourished, alert",
  "heent": "Normocephalic, no abnormalities",
  "chest_lungs": "Clear bilateral lung fields",
  "abdomen": "Soft, non-tender",
  "genitourinary": "Normal",
  "extremities": "No edema",
  "neurologic": "Alert and oriented"
}
```

#### Other Significant Findings
- **Model Field**: `other_findings` (TextField)
- **Max**: Unlimited text

---

### 6. DIAGNOSTIC TESTS SECTION

- **Model Field**: `diagnostic_tests` (JSONField)
- **PDF Test Options**:
  - Chest X-ray
  - CBC (Complete Blood Count)
  - Urinalysis
  - Drug Test
  - Psychological Test
  - HBsAg (Hepatitis B Surface Antigen)
  - Anti-HBs Titer
  - Fecalysis
  - Others (specify)

**JSON Format Example**:
```json
{
  "chest_xray": {
    "date": "2024-01-10",
    "findings": "Normal"
  },
  "cbc": {
    "date": "2024-01-10",
    "findings": "WBC 7.5, RBC normal"
  },
  "urinalysis": {
    "date": "2024-01-10",
    "findings": "Normal"
  },
  "drug_test": {
    "date": "2024-01-10",
    "findings": "Negative"
  }
}
```

---

### 7. CLINICAL SUMMARY SECTION

| PDF Field | Model Field | Type | Notes |
|-----------|------------|------|-------|
| Impression | `physician_impression` | TextField | Doctor's impression |
| Final Remarks and Recommendations | `final_remarks` | TextField | Final assessment |
| Recommendations | `recommendations` | TextField | Treatment plan |
| Physician's Name & Signature | `examining_physician` | CharField | Physician name |
| Date | `examination_date` | DateField | Examination date |

---

### 8. FORM METADATA (System Fields)

| Field | Type | Purpose |
|-------|------|---------|
| `user` | ForeignKey | Patient/User reference |
| `status` | CharField | Pending, Completed, Rejected |
| `created_at` | DateTimeField | Form creation timestamp |
| `updated_at` | DateTimeField | Last update timestamp |
| `reviewed_at` | DateTimeField | Review completion timestamp |
| `reviewed_by` | ForeignKey | Staff/Doctor who reviewed |
| `review_notes` | TextField | Review comments |

---

## Implementation Summary

### Models
- ✅ **HealthProfileForm**: Main data model with all PDF form fields

### Forms (Django ModelForms)
- ✅ **HealthProfilePersonalInfoForm**: Personal information section
- ✅ **HealthProfileMedicalHistoryForm**: Medical history section
- ✅ **HealthProfilePhysicalExamForm**: Physical examination section
- ✅ **HealthProfileDiagnosticTestsForm**: Diagnostic tests section (newly added)
- ✅ **HealthProfileClinicalSummaryForm**: Clinical summary section
- ✅ **HealthFormReviewForm**: Staff review and approval section

### Views
- ✅ **health_forms_list**: List all forms with search/filter
- ✅ **form_detail**: View form details
- ✅ **edit_form**: Edit form sections
- ✅ **review_form**: Staff/Doctor review
- ✅ **delete_form**: Delete form
- ✅ **create_form**: Create new form

### Features
- ✅ Role-based access control (Staff/Doctor can review all; Students see own forms)
- ✅ BMI auto-calculation
- ✅ JSON storage for immunization records, medical history, exam findings, diagnostic tests
- ✅ Form status tracking (Pending → Completed/Rejected)
- ✅ Audit trail (created_at, updated_at, reviewed_at, reviewed_by)

---

## Usage Examples

### Creating a Health Profile Form

```python
from health_forms_services.models import HealthProfileForm

form = HealthProfileForm.objects.create(
    user=request.user,
    last_name="Doe",
    first_name="John",
    date_of_birth="1990-05-15",
    gender="male",
    designation="student",
    mobile_number="09123456789",
    email_address="john@example.com",
)
```

### Updating Immunization Records

```python
form.immunization_records = {
    "covid_19": {"date": "2024-01-15", "vaccine": "Moderna"},
    "influenza": {"date": "2024-01-15", "vaccine": "FluVax"},
}
form.save()
```

### Auto-calculating BMI

```python
form.height = 1.75  # meters
form.weight = 70    # kg
form.calculate_bmi()  # Sets bmi=22.86, bmi_remarks="Normal"
form.save()
```

### Adding Diagnostic Test Results

```python
form.diagnostic_tests = {
    "chest_xray": {
        "date": "2024-01-10",
        "findings": "Normal, no abnormalities"
    },
    "cbc": {
        "date": "2024-01-10",
        "findings": "WBC 7.5, Hgb 14.2"
    }
}
form.save()
```

---

## Database Schema

### HealthProfileForm Table
```
├── id (Primary Key)
├── user_id (Foreign Key → User)
├── status (pending|completed|rejected)
├── created_at
├── updated_at
├── reviewed_at
├── reviewed_by_id (Foreign Key → User)
├── review_notes
├── [Personal Info Fields]
├── [Medical History Fields]
├── [OB-GYN Fields]
├── [Physical Exam Fields]
├── [Diagnostic Tests Field - JSON]
├── [Clinical Summary Fields]
└── [Other Fields]
```

---

## Next Steps

1. **Run Migrations** (if any new fields were added):
   ```bash
   python manage.py makemigrations health_forms_services
   python manage.py migrate health_forms_services
   ```

2. **Update Templates** (if needed):
   - Add diagnostic tests section to form templates
   - Update form_detail.html to display test results
   - Update edit_form.html with diagnostic tests form

3. **Testing**:
   - Create test forms with all sections filled
   - Verify BMI calculation
   - Test role-based access control
   - Validate JSON fields

4. **Admin Interface**:
   - Forms are already registered in admin.py
   - Can manage forms through Django admin

---

## Notes

- All JSONField entries should follow the documented format for consistency
- BMI is auto-calculated when height and weight are provided
- Form status workflow: Pending → Completed (or Rejected)
- Only staff/doctors can review and change form status
- Students can only edit their own forms
- All timestamps are automatically managed by Django
