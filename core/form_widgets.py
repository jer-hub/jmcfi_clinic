"""Shared Tailwind widget classes for Django forms."""

INPUT_FOCUS = (
    'focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500'
)

INPUT_CLASS = (
    'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm '
    'placeholder-gray-400 sm:text-sm '
    + INPUT_FOCUS
)
TEXTAREA_CLASS = INPUT_CLASS + ' min-h-[88px]'
SELECT_CLASS = (
    'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm sm:text-sm '
    + INPUT_FOCUS
)
CHECKBOX_CLASS = 'h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500/30'
