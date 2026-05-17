from django.test import SimpleTestCase

from core.roles import (
    LEGACY_ROLE_STUDENT,
    ROLE_PATIENT,
    expand_roles,
    normalize_role,
    role_matches,
)


class RoleNormalizationTests(SimpleTestCase):
    def test_normalize_legacy_student(self):
        self.assertEqual(normalize_role(LEGACY_ROLE_STUDENT), ROLE_PATIENT)

    def test_normalize_patient_unchanged(self):
        self.assertEqual(normalize_role(ROLE_PATIENT), ROLE_PATIENT)

    def test_expand_roles_includes_patient_for_legacy(self):
        self.assertEqual(expand_roles(LEGACY_ROLE_STUDENT), frozenset({ROLE_PATIENT}))

    def test_role_matches_legacy_decorator(self):
        self.assertTrue(role_matches(ROLE_PATIENT, LEGACY_ROLE_STUDENT))
        self.assertTrue(role_matches(LEGACY_ROLE_STUDENT, ROLE_PATIENT))
