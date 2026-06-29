"""Shared builders for health form detail personal-info section grids."""


def text_field(label, value, span='half'):
    return {'label': label, 'value': value or '—', 'type': 'text', 'span': span}


def present_text(label, value, span='half'):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == '—':
        return None
    return text_field(label, text, span=span)


BASE_PERSONAL_FIELD_LABELS = {
    'date_of_birth': 'Date of Birth',
    'place_of_birth': 'Place of Birth',
    'age': 'Age',
    'gender': 'Gender',
    'civil_status': 'Civil Status',
    'email_address': 'Email Address',
    'contact_number': 'Contact No.',
    'telephone_number': 'Telephone No.',
    'address': 'Address',
    'designation': 'Designation',
    'department_college_office': 'Department / College / Office',
    'guardian_name': 'Name of Guardian',
    'guardian_contact': 'Contact No.',
}


def base_personal_value_map(obj):
    """Common demographic/contact values for PatientChart and dental form models."""
    email = getattr(obj, 'email_address', '') or ''
    user = getattr(obj, 'user', None)
    if not email and user is not None and getattr(user, 'email', None):
        email = user.email
    return {
        'date_of_birth': obj.date_of_birth.strftime('%B %d, %Y') if obj.date_of_birth else '',
        'place_of_birth': obj.place_of_birth,
        'age': obj.age,
        'gender': obj.get_gender_display() if obj.gender else '',
        'civil_status': obj.get_civil_status_display() if obj.civil_status else '',
        'email_address': email,
        'contact_number': obj.contact_number,
        'telephone_number': obj.telephone_number,
        'address': obj.address,
        'designation': obj.get_designation_display() if obj.designation else '',
        'department_college_office': obj.department_college_office,
        'guardian_name': obj.guardian_name,
        'guardian_contact': obj.guardian_contact,
    }


def build_personal_info_groups(
    obj,
    section_specs,
    *,
    label_map,
    value_map,
    append_groups=None,
):
    """Build grouped read-only personal info fields from a section spec tuple."""
    groups = [{
        'label': 'Name',
        'fields': [text_field('Full Name', obj.get_full_name(), span='full')],
    }]
    full_width_fields = frozenset({'address'})

    for spec in section_specs:
        if spec['label'] == 'Full Name':
            continue
        fields = []
        for fname in spec['fields']:
            if fname not in label_map:
                continue
            field = present_text(
                label_map[fname],
                value_map.get(fname),
                span='full' if fname in full_width_fields else 'half',
            )
            if field:
                fields.append(field)
        if fields:
            groups.append({'label': spec['label'], 'fields': fields})

    if append_groups:
        groups.extend(append_groups)
    return groups
