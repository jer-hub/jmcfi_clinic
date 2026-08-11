/**
 * Shared age-from-DOB helpers (matches core profile form behavior).
 */
function ageFromDateOfBirth(isoDate) {
  if (!isoDate) return '';
  const dob = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(dob.getTime())) return '';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (dob > today) return '';
  let age = today.getFullYear() - dob.getFullYear();
  const monthDiff = today.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < dob.getDate())) {
    age -= 1;
  }
  return String(Math.max(age, 0));
}

function bindAgeFromDateOfBirth(dobId = 'id_date_of_birth', ageId = 'id_age') {
  const dobInput = document.getElementById(dobId);
  const ageInput = document.getElementById(ageId);
  if (!dobInput || !ageInput) return;

  const syncAge = () => {
    ageInput.value = ageFromDateOfBirth(dobInput.value);
  };

  dobInput.addEventListener('change', syncAge);
  dobInput.addEventListener('input', syncAge);
  if (dobInput.value) {
    syncAge();
  }
}

document.addEventListener('DOMContentLoaded', () => bindAgeFromDateOfBirth());
