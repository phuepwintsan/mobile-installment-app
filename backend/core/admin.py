from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Shop, User, Customer, Product, InstallmentContract, RepaymentSchedule, PaymentRecord


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'created_at')
    search_fields = ('name', 'phone')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'phone_number', 'role', 'shop', 'is_staff')
    list_filter = ('role', 'shop', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Shop Info', {'fields': ('role', 'shop', 'phone_number')}),
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'nrc_or_id', 'shop', 'created_at')
    list_filter = ('shop',)
    search_fields = ('full_name', 'phone_number', 'nrc_or_id')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('brand', 'model_name', 'imei_or_serial', 'cash_price', 'status', 'shop')
    list_filter = ('status', 'brand', 'shop')
    search_fields = ('brand', 'model_name', 'imei_or_serial')


class RepaymentScheduleInline(admin.TabularInline):
    model = RepaymentSchedule
    extra = 0
    readonly_fields = ('installment_number', 'due_date', 'expected_amount', 'paid_amount', 'status')
    can_delete = False


class PaymentRecordInline(admin.TabularInline):
    model = PaymentRecord
    extra = 0
    readonly_fields = ('receipt_number', 'amount_paid', 'payment_date', 'received_by')
    can_delete = False


@admin.register(InstallmentContract)
class InstallmentContractAdmin(admin.ModelAdmin):
    list_display = (
        'contract_number', 'customer', 'product', 'total_contract_amount',
        'down_payment', 'duration_months', 'status', 'shop'
    )
    list_filter = ('status', 'shop', 'created_at')
    search_fields = ('contract_number', 'customer__full_name', 'product__imei_or_serial')
    inlines = [RepaymentScheduleInline, PaymentRecordInline]
    readonly_fields = ('contract_number', 'financed_principal', 'total_contract_amount')


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'contract', 'amount_paid', 'payment_date', 'received_by')
    search_fields = ('receipt_number', 'contract__contract_number')
    readonly_fields = ('receipt_number', 'payment_date')