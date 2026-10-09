import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


class Shop(models.Model):
    """Multi-tenant root entity: Isolates data between different shops."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Custom user model supporting Shop Owner, Staff, and Read-Only Customer roles."""
    class Role(models.TextChoices):
        OWNER = 'OWNER', 'Shop Owner'
        STAFF = 'STAFF', 'Shop Staff'
        CUSTOMER = 'CUSTOMER', 'Customer'

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='users', null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Customer(models.Model):
    """Customer profile registered by shop owner/staff."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='customers')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='customer_profile')
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    nrc_or_id = models.CharField(max_length=50, help_text="NRC / National ID Card Number")
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['shop', 'phone_number']),
            models.Index(fields=['shop', 'full_name']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"


class Product(models.Model):
    """Inventory items tracked via IMEI or Serial Number."""
    class Status(models.TextChoices):
        AVAILABLE = 'AVAILABLE', 'Available'
        SOLD = 'SOLD', 'Sold under Installment'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
    brand = models.CharField(max_length=100)
    model_name = models.CharField(max_length=100)
    imei_or_serial = models.CharField(max_length=100, unique=True, help_text="IMEI or Serial Number")
    cash_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.brand} {self.model_name} (IMEI/SN: {self.imei_or_serial})"


class InstallmentContract(models.Model):
    """Installment Agreement connecting Customer and Product."""
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed'
        OVERDUE = 'OVERDUE', 'Overdue'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract_number = models.CharField(max_length=50, unique=True, editable=False)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='contracts')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='contracts')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='contracts')
    
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    down_payment = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    total_interest = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_contract_amount = models.DecimalField(max_digits=12, decimal_places=2)
    financed_principal = models.DecimalField(max_digits=12, decimal_places=2)
    
    duration_months = models.IntegerField(validators=[MinValueValidator(1)])
    monthly_installment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.down_payment >= self.selling_price:
            raise ValidationError("Down payment cannot be greater than or equal to selling price.")

    def save(self, *args, **kwargs):
        if not self.contract_number:
            self.contract_number = f"AGR-{uuid.uuid4().hex[:8].upper()}"
        self.financed_principal = self.selling_price - self.down_payment
        self.total_contract_amount = self.financed_principal + self.total_interest
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.contract_number} - {self.customer.full_name}"


class RepaymentSchedule(models.Model):
    """Server-generated monthly payment schedule."""
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PAID = 'PAID', 'Paid'
        PARTIAL = 'PARTIAL', 'Partially Paid'
        OVERDUE = 'OVERDUE', 'Overdue'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contract = models.ForeignKey(InstallmentContract, on_delete=models.CASCADE, related_name='schedules')
    installment_number = models.IntegerField()
    due_date = models.DateField()
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    class Meta:
        ordering = ['installment_number']
        unique_together = ('contract', 'installment_number')

    def remaining_amount(self):
        return self.expected_amount - self.paid_amount

    def __str__(self):
        return f"{self.contract.contract_number} - Month #{self.installment_number}"


class PaymentRecord(models.Model):
    """Append-only manual cash payment log."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    receipt_number = models.CharField(max_length=50, unique=True, editable=False)
    contract = models.ForeignKey(InstallmentContract, on_delete=models.PROTECT, related_name='payments')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='collected_payments')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-payment_date']

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = f"REC-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} - {self.amount_paid} MMK"