from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
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
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)


class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ['medicine', 'quantity_ordered', 'unit_cost']
        widgets = {
            'medicine': forms.Select(attrs={'class': SELECT_CLASS}),
            'quantity_ordered': forms.NumberInput(attrs={'class': INPUT_CLASS}),
            'unit_cost': forms.NumberInput(attrs={'class': INPUT_CLASS, 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['medicine'].queryset = Medicine.objects.filter(is_active=True)


PurchaseOrderItemFormSet = forms.inlineformset_factory(
    PurchaseOrder, PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=1, can_delete=True,
)


class DispensingForm(forms.ModelForm):
    medicine = forms.ModelChoiceField(
        queryset=Medicine.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
        help_text='Select the medicine to dispense',
    )

    class Meta:
        model = Dispensing
        fields = [
            'patient', 'medicine', 'batch', 'quantity',
            'prescription_reference', 'prescribing_doctor', 'reason',
        ]
        widgets = {
            'patient': forms.Select(attrs={'class': SELECT_CLASS}),
            'batch': forms.Select(attrs={'class': SELECT_CLASS}),
            'quantity': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': '1'}),
            'prescription_reference': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'prescribing_doctor': forms.Select(attrs={'class': SELECT_CLASS}),
            'reason': forms.Textarea(attrs={'class': TEXTAREA_CLASS, 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['patient'].queryset = User.objects.filter(is_active=True)
        self.fields['patient'].label_from_instance = (
            lambda u: f"{u.first_name} {u.last_name} ({u.email})"
        )
        self.fields['prescribing_doctor'].queryset = User.objects.filter(
            role__in=['staff', 'doctor'], is_active=True
        )
        self.fields['prescribing_doctor'].label_from_instance = (
            lambda u: f"Dr. {u.first_name} {u.last_name}"
        )
        self.fields['prescribing_doctor'].required = False
        # Default: show all available batches; JS on template can filter by medicine
        self.fields['batch'].queryset = Batch.objects.filter(quantity__gt=0).select_related('medicine')
        self.fields['batch'].label_from_instance = (
            lambda b: f"{b.medicine.name} – Batch {b.batch_number} (Qty: {b.quantity}, Exp: {b.expiry_date})"
        )

    def clean(self):
        cleaned = super().clean()
        batch = cleaned.get('batch')
        qty = cleaned.get('quantity')
        if batch and qty:
            if qty > batch.quantity:
                raise forms.ValidationError(
                    f'Insufficient stock. Only {batch.quantity} available in this batch.'
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
