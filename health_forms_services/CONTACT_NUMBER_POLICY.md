# Health Forms Services Contact Number Policy

## Scope
This policy applies to the New Health Profile form and Personal Info section edits in Health Forms Services.

## Covered Fields
- Mobile Number
- Telephone Number
- Guardian Contact

## Allowed Inputs
Fields must be Philippine mobile numbers only. Accepted user input formats:
- `09171234567`
- `9171234567`
- `+639171234567`

Spaces, dashes, dots, and parentheses may be entered by users, but values must still resolve to a valid PH mobile number.

## Normalized Storage Format
All covered fields are stored in E.164 PH format:
- `+63XXXXXXXXXX`

Example:
- Input: `0917 123 4567`
- Stored: `+639171234567`

## Validation Rule
Input must resolve to exactly 10 mobile digits beginning with `9` after PH prefix normalization.
Invalid input must be rejected with validation error.

## UI Behavior
- Contact fields use PH phone input UI (`data-phone-input`) with live validation feedback.
- Users are shown PH-only helper text and digit-progress hints.

## Security and Data Quality Notes
- Validation is enforced server-side through form clean methods.
- Client-side formatting is assistive only and not source of truth.
- This policy is intended to keep emergency/contact data consistent and callable in PH context.
