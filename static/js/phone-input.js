/**
 * Philippine Mobile Number Input Component
 * =========================================
 * Auto-initializes on any <input data-phone-input="true">.
 *
 * Features:
 *   • Live formatting as user types  (0917 123 4567  or  +63 917 123 4567)
 *   • Smart cursor-position management — no jumping or digit loss
 *   • Real-time validation feedback   (border colour + status icon)
 *   • Strips formatting before form submission so Django receives clean digits
 *   • Digit counter that updates live
 *
 * Accepted formats (input):
 *   09171234567 | +639171234567 | 9171234567
 *
 * Stored format (server):
 *   +639171234567  (E.164)
 */

(function () {
    'use strict';

    /* ------------------------------------------------------------------ */
    /*  CONSTANTS                                                          */
    /* ------------------------------------------------------------------ */

    const PH_MOBILE_RE = /^(\+?63|0)?9\d{9}$/;   // matches clean digit string

    const CLASSES = {
        neutral : 'border-gray-300',
        focus   : 'ring-2 ring-primary-500 border-primary-500',
        valid   : 'border-emerald-500 ring-2 ring-emerald-200',
        invalid : 'border-red-400 ring-2 ring-red-200',
    };

    // Status icons injected into the wrapper
    const ICON_VALID = `
        <svg class="w-4 h-4 text-emerald-500" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
        </svg>`;

    const ICON_INVALID = `
        <svg class="w-4 h-4 text-red-400" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>`;

    /* ------------------------------------------------------------------ */
    /*  HELPERS                                                           */
    /* ------------------------------------------------------------------ */

    /** Strip everything except digits (and an optional leading +). */
    function stripToDigits(str) {
        const s = str.trim();
        if (s.startsWith('+')) {
            return '+' + s.slice(1).replace(/\D/g, '');
        }
        return s.replace(/\D/g, '');
    }

    /** Get the 10-digit mobile core (9XXXXXXXXX) or null. */
    function extractMobile(clean) {
        const d = clean.startsWith('+') ? clean.slice(1) : clean;
        if (d.startsWith('63') && d.length >= 12) return d.slice(2, 12);
        if (d.startsWith('0')  && d.length >= 11) return d.slice(1, 11);
        if (d.startsWith('9')  && d.length >= 10) return d.slice(0, 10);
        return null;
    }

    /** Is the clean value a complete, valid PH mobile number? */
    function isValid(clean) {
        const d = clean.replace(/\+/g, '');
        return PH_MOBILE_RE.test(clean.replace(/\+/, '')) || PH_MOBILE_RE.test('+' + d);
    }

    /**
     * Format a digit-only string into a readable PH mobile number.
     *   +63 → +63 917 123 4567
     *    0  → 0917 123 4567
     * raw 9 → 0917 123 4567   (auto-prefix 0)
     */
    function formatPhone(clean) {
        let digits = clean.startsWith('+') ? clean.slice(1) : clean;
        digits = digits.replace(/\D/g, '');

        // +63 prefix
        if (clean.startsWith('+') || digits.startsWith('63')) {
            const cc = digits.startsWith('63') ? digits.slice(2) : digits;
            // We work only with the mobile part
            const m = digits.startsWith('63') ? digits.slice(2) : digits;
            // Rebuild
            let out = '+63';
            if (m.length > 0) out += ' ' + m.slice(0, 3);
            if (m.length > 3) out += ' ' + m.slice(3, 6);
            if (m.length > 6) out += ' ' + m.slice(6, 10);
            return out;
        }

        // Local 0-prefix
        if (digits.startsWith('0')) {
            const m = digits.slice(1);
            let out = '0' + m.slice(0, 3);
            if (m.length > 3) out += ' ' + m.slice(3, 6);
            if (m.length > 6) out += ' ' + m.slice(6, 10);
            return out;
        }

        // Raw 9-start
        if (digits.startsWith('9')) {
            let out = '0' + digits.slice(0, 3);
            if (digits.length > 3) out += ' ' + digits.slice(3, 6);
            if (digits.length > 6) out += ' ' + digits.slice(6, 10);
            return out;
        }

        // Anything else — return as-is
        return clean;
    }

    /** Count significant digits (those that map to the 10-digit mobile). */
    function countMobileDigits(clean) {
        const m = extractMobile(clean);
        return m ? m.replace(/\D/g, '').length : 0;
    }

    /* ------------------------------------------------------------------ */
    /*  UI HELPERS                                                        */
    /* ------------------------------------------------------------------ */

    function setInputState(input, state) {
        // Remove all state classes
        Object.values(CLASSES).forEach(c =>
            c.split(' ').forEach(cls => input.classList.remove(cls))
        );
        // Apply new state
        if (CLASSES[state]) {
            CLASSES[state].split(' ').forEach(cls => input.classList.add(cls));
        }
    }

    /** Get or create the status-icon container (right side of input). */
    function getStatusEl(input) {
        let el = input.parentElement.querySelector('[data-phone-status]');
        if (!el) {
            el = document.createElement('div');
            el.setAttribute('data-phone-status', '');
            el.className = 'absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none transition-opacity duration-200';
            input.parentElement.appendChild(el);
        }
        return el;
    }

    /** Get or create the digit-counter element below the input. */
    function getCounterEl(input) {
        // Look for a sibling with data-phone-counter
        const wrapper = input.closest('[data-phone-wrapper]') || input.parentElement.parentElement;
        let el = wrapper.querySelector('[data-phone-counter]');
        return el;   // may be null — template must include it if desired
    }

    function updateStatusIcon(input, clean) {
        const statusEl = getStatusEl(input);
        const value = clean || stripToDigits(input.value);

        if (!value || value === '' || value === '+') {
            statusEl.innerHTML = '';
            statusEl.style.opacity = '0';
            return;
        }

        const valid = isValid(value);
        statusEl.style.opacity = '1';
        statusEl.innerHTML = valid ? ICON_VALID : ICON_INVALID;
    }

    function updateCounter(input, clean) {
        const counterEl = getCounterEl(input);
        if (!counterEl) return;

        const value = clean || stripToDigits(input.value);
        const count = countMobileDigits(value);
        const needed = 10;

        if (!value || value === '' || value === '+') {
            counterEl.textContent = '10 digits needed';
            counterEl.className = counterEl.className.replace(/text-\S+/g, '') + ' text-gray-400';
            return;
        }

        const remaining = needed - count;
        if (remaining > 0) {
            counterEl.textContent = `${remaining} digit${remaining !== 1 ? 's' : ''} left`;
            counterEl.className = counterEl.className.replace(/text-\S+/g, '') + ' text-amber-500';
        } else if (remaining === 0) {
            counterEl.textContent = 'Valid number';
            counterEl.className = counterEl.className.replace(/text-\S+/g, '') + ' text-emerald-500';
        } else {
            counterEl.textContent = 'Too many digits';
            counterEl.className = counterEl.className.replace(/text-\S+/g, '') + ' text-red-400';
        }
    }

    /* ------------------------------------------------------------------ */
    /*  CORE INPUT HANDLER                                                */
    /* ------------------------------------------------------------------ */

    function handleInput(e) {
        const input = e.target;
        const raw   = input.value;
        const clean = stripToDigits(raw);

        // Limit total significant digits (country code + 10 mobile = 12, or 0 + 10 = 11)
        const digits = clean.replace(/\+/g, '');
        let maxDigits = 12;  // +639XXXXXXXXX
        if (digits.startsWith('0')) maxDigits = 11;
        if (digits.startsWith('9') && !digits.startsWith('63')) maxDigits = 10;

        if (digits.length > maxDigits) {
            // Trim excess digits
            const trimmed = clean.startsWith('+')
                ? '+' + digits.slice(0, maxDigits)
                : digits.slice(0, maxDigits);
            const formatted = formatPhone(trimmed);
            input.value = formatted;
            updateStatusIcon(input, trimmed);
            updateCounter(input, trimmed);
            return;
        }

        // Format and set
        const formatted = formatPhone(clean);

        // Calculate new cursor position
        const oldCursor = input.selectionStart;
        const digitsBeforeCursor = stripToDigits(raw.slice(0, oldCursor)).replace(/\+/g, '').length;

        input.value = formatted;

        // Restore cursor: count digits in formatted string until we hit digitsBeforeCursor
        let newCursor = 0;
        let digitsSeen = 0;
        for (let i = 0; i < formatted.length; i++) {
            if (/\d/.test(formatted[i])) {
                digitsSeen++;
                if (digitsSeen === digitsBeforeCursor) {
                    newCursor = i + 1;
                    break;
                }
            }
            // Account for + at position 0
            if (formatted[i] === '+' && i === 0) continue;
        }
        if (digitsSeen < digitsBeforeCursor) {
            newCursor = formatted.length;
        }

        input.setSelectionRange(newCursor, newCursor);

        // Visual feedback
        updateStatusIcon(input, clean);
        updateCounter(input, clean);
    }

    function handleBlur(e) {
        const input = e.target;
        const clean = stripToDigits(input.value);

        if (!clean || clean === '' || clean === '+') {
            setInputState(input, 'neutral');
            input.setCustomValidity('');
            return;
        }

        if (isValid(clean)) {
            setInputState(input, 'valid');
            input.setCustomValidity('');
        } else {
            setInputState(input, 'invalid');
            input.setCustomValidity(
                'Enter a valid Philippine mobile number (e.g., 0917 123 4567)'
            );
            input.reportValidity();
        }
    }

    function handleFocus(e) {
        const input = e.target;
        const clean = stripToDigits(input.value);

        if (clean && isValid(clean)) {
            setInputState(input, 'valid');
        } else {
            setInputState(input, 'neutral');
        }
        input.setCustomValidity('');
    }

    /* ------------------------------------------------------------------ */
    /*  FORM SUBMIT — strip formatting so Django gets clean values        */
    /* ------------------------------------------------------------------ */

    function handleFormSubmit(e) {
        const form = e.target;
        const phoneInputs = form.querySelectorAll('input[data-phone-input]');

        phoneInputs.forEach(input => {
            const clean = stripToDigits(input.value);
            if (clean) {
                input.value = clean;
            }
        });
    }

    /* ------------------------------------------------------------------ */
    /*  INITIALISE                                                        */
    /* ------------------------------------------------------------------ */

    function initPhoneInputs() {
        const inputs = document.querySelectorAll('input[data-phone-input]');

        // Track forms we've already attached submit listeners to
        const processedForms = new WeakSet();

        inputs.forEach(input => {
            // Skip if already initialised
            if (input.dataset.phoneInitialised) return;
            input.dataset.phoneInitialised = 'true';

            // Ensure parent is position:relative for the status icon
            if (input.parentElement) {
                input.parentElement.style.position = 'relative';
            }

            // Bind events
            input.addEventListener('input',  handleInput);
            input.addEventListener('blur',   handleBlur);
            input.addEventListener('focus',  handleFocus);

            // Format any pre-filled value
            if (input.value) {
                const clean = stripToDigits(input.value);
                input.value = formatPhone(clean);
                updateStatusIcon(input, clean);
                updateCounter(input, clean);
                if (isValid(clean)) {
                    setInputState(input, 'valid');
                }
            }

            // Attach submit handler to parent form
            const form = input.closest('form');
            if (form && !processedForms.has(form)) {
                processedForms.add(form);
                form.addEventListener('submit', handleFormSubmit);
            }
        });
    }

    // Run on DOMContentLoaded and also export for dynamic content
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPhoneInputs);
    } else {
        initPhoneInputs();
    }

    // Expose for re-initialisation after dynamic content loads
    window.initPhoneInputs = initPhoneInputs;

})();
