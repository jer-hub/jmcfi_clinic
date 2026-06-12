from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from core.roles import PATIENT_ROLE_VALUES

from .models import (
    Medicine, MedicineCategory, Batch, Supplier,
    PurchaseOrder, PurchaseOrderItem, Dispensing, StockAdjustment,
)

User = get_user_model()

# Reusable widget classes
INPUT_CLASS = (
    'form-control mt-1 block w-full rounded-xl border border-gray-200 bg-white px-4 py-3 '
    'text-sm text-gray-900 shadow-sm outline-none transition duration-200 '
    'placeholder:text-gray-400 hover:border-gray-300 '
    'focus:border-primary-400 focus:outline-none focus:ring-4 focus:ring-primary-100'
)
SELECT_CLASS = (
    'form-select mt-1 block w-full rounded-xl border border-gray-200 bg-white px-4 py-3 pr-10 '
    'text-sm text-gray-900 shadow-sm outline-none transition duration-200 '
    'hover:border-gray-300 focus:border-primary-400 focus:outline-none focus:ring-4 focus:ring-primary-100'
)
TEXTAREA_CLASS = INPUT_CLASS + ' min-h-[110px] resize-y'
CHECKBOX_CLASS = (
    'form-check-input mt-1 h-5 w-5 rounded border border-gray-300 text-primary-600 '
    'shadow-sm transition focus:ring-4 focus:ring-primary-100 focus:outline-none'
)


class MedicineCategoryForm(forms.ModelForm):
    class Meta:
        model = MedicineCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g., Analgesic'}),
            'description': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }


class MedicineForm(forms.ModelForm):
    # ── Optional opening-stock fields (non-model, only used on create) ──
    opening_quantity = forms.IntegerField(
        required=False, min_value=1,
        widget=forms.NumberInput(attrs={
            'class': INPUT_CLASS, 'placeholder': 'e.g., 100', 'min': '1',
        }),
        label='Opening Quantity',
        help_text='Number of units to record as initial stock for this medicine.',
    )
    opening_batch_number = forms.CharField(
        required=False, max_length=100,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS, 'placeholder': 'e.g., BATCH-001',
        }),
        label='Batch Number',
        help_text='Unique identifier for this opening batch.',
    )
    opening_unit_cost = forms.DecimalField(
        required=False, min_value=0, decimal_places=2, max_digits=10,
        widget=forms.NumberInput(attrs={
            'class': INPUT_CLASS, 'placeholder': '0.00', 'step': '0.01',
        }),
        label='Unit Cost (₱)',
        help_text='Cost per unit for this opening batch (PHP).',
    )
    opening_expiry_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
        label='Expiry Date',
        help_text='Must be a future date.',
    )

    class Meta:
        model = Medicine
        fields = [
            'name', 'generic_name', 'brand_name', 'category',
            'description', 'unit', 'strength',
            'requires_prescription', 'reorder_level', 'max_stock_level',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'generic_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'brand_name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'category': forms.Select(attrs={'class': SELECT_CLASS}),
            'description': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
            'unit': forms.Select(attrs={'class': SELECT_CLASS}),
            'strength': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': 'e.g., 500mg'}),
            'requires_prescription': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
            'reorder_level': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'max_stock_level': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def clean(self):
        cleaned = super().clean()

        # ── 1. Threshold validation ──────────────────────────────────────────
        reorder = cleaned.get('reorder_level')
        max_stock = cleaned.get('max_stock_level')
        if reorder is not None and max_stock is not None:
            if reorder >= max_stock:
                self.add_error(
                    'reorder_level',
                    'Reorder level must be less than the maximum stock level.',
                )

        # ── 2. Duplicate detection (name + strength, case-insensitive) ───────
        name = (cleaned.get('name') or '').strip()
        strength = (cleaned.get('strength') or '').strip()
        if name:
            qs = Medicine.objects.filter(name__iexact=name)
            if strength:
                qs = qs.filter(strength__iexact=strength)
            # Exclude self when editing
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                existing = qs.first()
                label = existing.name
                if existing.strength:
                    label += f' ({existing.strength})'
                self.add_error(
                    'name',
                    f'A medicine "{label}" already exists. '
                    'Please edit the existing record instead of creating a duplicate.',
                )

        # ── 3. Opening stock cross-field validation ──────────────────────────
        opening_qty = cleaned.get('opening_quantity')
        opening_batch = (cleaned.get('opening_batch_number') or '').strip()
        opening_expiry = cleaned.get('opening_expiry_date')

        if opening_qty:
            if not opening_batch:
                self.add_error(
                    'opening_batch_number',
                    'Batch number is required when providing opening stock.',
                )
            if not opening_expiry:
                self.add_error(
                    'opening_expiry_date',
                    'Expiry date is required when providing opening stock.',
                )
            elif opening_expiry <= timezone.now().date():
                self.add_error(
                    'opening_expiry_date',
                    'Expiry date must be a date in the future.',
                )

        return cleaned


class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = [
            'medicine', 'batch_number', 'quantity', 'unit_cost',
            'manufacturing_date', 'expiry_date', 'received_date', 'notes',
        ]
        widgets = {
            'medicine': forms.Select(attrs={'class': SELECT_CLASS}),
            'batch_number': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'quantity': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'unit_cost': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01'}),
            'manufacturing_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'received_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medicine'].queryset = Medicine.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        mfg = cleaned.get('manufacturing_date')
        exp = cleaned.get('expiry_date')
        if mfg and exp and mfg >= exp:
            raise forms.ValidationError('Manufacturing date must be before expiry date.')
        return cleaned


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'email', 'phone', 'address', 'notes', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'contact_person': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASS}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'address': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASS}),
        }

    def clean(self):
        cleaned = super().clean()
        name = (cleaned.get('name') or '').strip()
        email = (cleaned.get('email') or '').strip()
        phone = (cleaned.get('phone') or '').strip()
        if name:
            cleaned['name'] = name
            qs = Supplier.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error('name', 'A supplier with this name already exists.')
        if email:
            cleaned['email'] = email
        if phone:
            cleaned['phone'] = phone
        if not email and not phone:
            self.add_error(
                'email',
                'Provide at least an email or phone number for supplier contact.',
            )
        return cleaned


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'order_date', 'expected_delivery', 'notes']
        widgets = {
            'supplier': forms.Select(attrs={'class': SELECT_CLASS}),
            'order_date': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'expected_delivery': forms.DateInput(attrs={'class': INPUT_CLASS, 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True).order_by('name')
        self.fields['supplier'].label_from_instance = (
            lambda s: f"{s.name} ({s.contact_person})" if s.contact_person else s.name
        )

    def clean(self):
        cleaned = super().clean()
        order_date = cleaned.get('order_date')
        expected = cleaned.get('expected_delivery')
        if order_date and expected and expected < order_date:
            self.add_error(
                'expected_delivery',
                'Expected delivery must be on or after the order date.',
            )
        return cleaned


class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ['medicine', 'quantity_ordered', 'unit_cost']
        widgets = {
            'medicine': forms.Select(attrs={'class': SELECT_CLASS + ' po-line-medicine'}),
            'quantity_ordered': forms.NumberInput(attrs={
                'class': INPUT_CLASS + ' po-line-qty', 'min': '1',
            }),
            'unit_cost': forms.NumberInput(attrs={
                'class': INPUT_CLASS + ' po-line-cost', 'step': '0.01', 'min': '0',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medicine'].queryset = Medicine.objects.filter(is_active=True).order_by('name')
        self.fields['medicine'].label_from_instance = (
            lambda m: (
                f"{m} — {m.current_stock} {m.get_unit_display()} "
                f"(reorder at {m.reorder_level})"
            )
        )

    def clean(self):
        cleaned = super().clean()
        qty = cleaned.get('quantity_ordered')
        cost = cleaned.get('unit_cost')
        if qty is not None and qty < 1:
            self.add_error('quantity_ordered', 'Quantity must be at least 1.')
        if cost is not None and cost < 0:
            self.add_error('unit_cost', 'Unit cost cannot be negative.')
        return cleaned


class BasePurchaseOrderItemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        medicine_ids = []
        has_line = False
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if form.cleaned_data.get('DELETE'):
                continue
            medicine = form.cleaned_data.get('medicine')
            if not medicine:
                continue
            has_line = True
            if medicine.pk in medicine_ids:
                raise forms.ValidationError(
                    'Each medicine can only appear once per purchase order.'
                )
            medicine_ids.append(medicine.pk)
        if not has_line:
            raise forms.ValidationError('Add at least one order line item.')


PurchaseOrderItemFormSet = forms.inlineformset_factory(
    PurchaseOrder, PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    formset=BasePurchaseOrderItemFormSet,
    extra=3, can_delete=True,
)


def _dispensing_medicine_queryset():
    """Active medicines with non-expired stock (cache or live batch sum)."""
    today = timezone.now().date()
    return (
        Medicine.objects.filter(is_active=True)
        .filter(
            Q(cached_non_expired_stock__gt=0)
            | Q(batches__quantity__gt=0, batches__expiry_date__gt=today)
        )
        .distinct()
        .order_by('name')
    )


def _dispensing_batch_queryset(medicine_id=None):
    today = timezone.now().date()
    qs = Batch.objects.filter(quantity__gt=0, expiry_date__gt=today).select_related('medicine')
    if medicine_id:
        qs = qs.filter(medicine_id=medicine_id)
    else:
        qs = qs.none()
    return qs.order_by('expiry_date')


class DispensingForm(forms.ModelForm):
    medicine = forms.ModelChoiceField(
        queryset=Medicine.objects.none(),
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
        help_text='Only medicines with available stock are listed.',
    )

    class Meta:
        model = Dispensing
        fields = [
            'patient', 'medicine', 'batch', 'quantity',
            'prescription_reference', 'prescribing_doctor', 'reason',
        ]
        widgets = {
            'patient': forms.HiddenInput(),
            'batch': forms.Select(attrs={'class': SELECT_CLASS}),
            'quantity': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': '1'}),
            'prescription_reference': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'prescribing_doctor': forms.Select(attrs={'class': SELECT_CLASS}),
            'reason': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medicine'].queryset = _dispensing_medicine_queryset()
        self.fields['medicine'].label_from_instance = (
            lambda m: f"{m} — {m.current_stock} {m.get_unit_display()} available"
        )

        patient_pk = None
        if self.data.get('patient'):
            patient_pk = self.data.get('patient')
        if patient_pk:
            self.fields['patient'].queryset = User.objects.filter(
                pk=patient_pk,
                role__in=PATIENT_ROLE_VALUES,
                is_active=True,
            )
        else:
            self.fields['patient'].queryset = User.objects.none()
        self.fields['patient'].error_messages = {
            'invalid_choice': 'Please select a valid patient from the search results.',
        }

        self.fields['prescribing_doctor'].queryset = User.objects.filter(
            role__in=['staff', 'doctor'], is_active=True
        )
        self.fields['prescribing_doctor'].label_from_instance = (
            lambda u: f"Dr. {u.first_name} {u.last_name}"
        )
        self.fields['prescribing_doctor'].required = False

        medicine_id = self.data.get('medicine') if self.data else None
        batch_qs = _dispensing_batch_queryset(medicine_id)
        posted_batch = self.data.get('batch') if self.data else None
        if posted_batch:
            batch_qs = (
                Batch.objects.filter(pk__in=batch_qs.values('pk'))
                | Batch.objects.filter(pk=posted_batch)
            ).distinct()
        self.fields['batch'].queryset = batch_qs
        self.fields['batch'].label_from_instance = (
            lambda b: f"Batch {b.batch_number} (Qty: {b.quantity}, Exp: {b.expiry_date})"
        )

        batch_api_base = reverse(
            'pharmacy:api_batches_for_medicine',
            kwargs={'medicine_id': 0},
        )
        medicine_api_base = reverse(
            'pharmacy:api_medicine_detail',
            kwargs={'medicine_id': 0},
        )
        self.fields['medicine'].widget.attrs.update({
            'id': 'id_medicine',
            'data-batch-api-base': batch_api_base,
            'data-medicine-api-base': medicine_api_base,
        })
        self.fields['batch'].widget.attrs.update({'id': 'id_batch'})
        self.fields['quantity'].widget.attrs.update({'id': 'id_quantity'})

    def clean(self):
        cleaned = super().clean()
        patient = cleaned.get('patient')
        if not patient:
            self.add_error('patient', 'Please select a patient from the search results.')

        medicine = cleaned.get('medicine')
        batch = cleaned.get('batch')
        qty = cleaned.get('quantity')

        if medicine and batch and batch.medicine_id != medicine.pk:
            self.add_error('batch', 'Selected batch does not belong to the chosen medicine.')

        if batch and qty and qty > batch.quantity:
            self.add_error(
                'quantity',
                f'Insufficient stock. Only {batch.quantity} available in this batch.',
            )

        if medicine and medicine.requires_prescription:
            rx_ref = (cleaned.get('prescription_reference') or '').strip()
            rx_doc = cleaned.get('prescribing_doctor')
            if not rx_ref and not rx_doc:
                self.add_error(
                    'prescription_reference',
                    'This medicine requires a prescription reference or prescribing doctor.',
                )

        return cleaned


class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ['batch', 'quantity_change', 'reason', 'notes']
        widgets = {
            'batch': forms.Select(attrs={'class': SELECT_CLASS}),
            'quantity_change': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'reason': forms.Select(attrs={'class': SELECT_CLASS}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['batch'].queryset = Batch.objects.select_related('medicine').order_by('medicine__name')
        self.fields['batch'].label_from_instance = (
            lambda b: f"{b.medicine.name} – Batch {b.batch_number} (Qty: {b.quantity})"
        )

    def clean(self):
        cleaned = super().clean()
        batch = cleaned.get('batch')
        change = cleaned.get('quantity_change')
        if batch and change:
            new_qty = batch.quantity + change
            if new_qty < 0:
                raise forms.ValidationError(
                    f'Adjustment would result in negative stock ({new_qty}). '
                    f'Current quantity: {batch.quantity}.'
                )
        return cleaned
