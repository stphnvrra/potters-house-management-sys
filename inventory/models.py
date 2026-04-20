from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class InventoryItem(models.Model):
    item_type = models.CharField(max_length=100)
    sku = models.CharField(max_length=50, unique=True)
    image = models.TextField(default='', blank=True)  # Using TextField for base64 or long paths
    name = models.CharField(max_length=200)
    sub_unit = models.CharField(max_length=50, default='', blank=True)
    description = models.TextField(default='', blank=True)
    datetime_updated = models.CharField(max_length=50, default='', blank=True)
    last_inventory = models.CharField(max_length=50, default='', blank=True)
    total_purchases = models.FloatField(default=0.0)
    total_withdrawal = models.FloatField(default=0.0)
    total_balance = models.FloatField(default=0.0)
    price = models.FloatField(default=0.0)
    inventory_value = models.FloatField(default=0.0)
    is_negative = models.CharField(max_length=10, default='no')
    color = models.CharField(max_length=100, default='', blank=True)
    model = models.CharField(max_length=100, default='', blank=True)
    shape = models.CharField(max_length=100, default='', blank=True)
    size = models.CharField(max_length=100, default='', blank=True)
    dimensions = models.CharField(max_length=100, default='', blank=True)
    volume = models.CharField(max_length=100, default='', blank=True)
    material = models.CharField(max_length=100, default='', blank=True)
    addon = models.CharField(max_length=200, default='', blank=True)
    other = models.CharField(max_length=200, default='', blank=True)
    occasion = models.CharField(max_length=200, default='', blank=True)
    is_archived = models.BooleanField(default=False)
    cost = models.FloatField(default=0.0)
    shipping_fee = models.FloatField(default=0.0)
    updated_by = models.CharField(max_length=100, default='admin')

    @property
    def total_cost(self):
        return (self.cost or 0) + (self.shipping_fee or 0)

    @property
    def full_description(self):
        parts = []
        if self.color: parts.append(self.color)
        if self.model: parts.append(self.model)
        if self.shape: parts.append(self.shape)
        if self.size: parts.append(self.size)
        if self.dimensions: parts.append(self.dimensions)
        if self.volume: parts.append(self.volume)
        if self.material: parts.append(self.material)
        if self.addon: parts.append(self.addon)
        if self.other: parts.append(self.other)
        if self.occasion: parts.append(self.occasion)
        return ", ".join(parts)

    def __str__(self):
        return self.name

class InventoryLog(models.Model):
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='logs')
    user = models.CharField(max_length=100, default='Stephen')
    transaction_type = models.CharField(max_length=50)
    quantity = models.CharField(max_length=50)
    timestamp = models.DateTimeField(default=timezone.now)
    notes = models.TextField(default='', blank=True)

class PurchaseOrderRequest(models.Model):
    request_type = models.CharField(max_length=50, default='-')
    name = models.CharField(max_length=200)
    description = models.TextField(default='', blank=True)
    remarks = models.TextField(default='', blank=True)
    quantity = models.FloatField(default=0)
    unit = models.CharField(max_length=50, default='pc')
    status = models.CharField(max_length=50, default='created')
    purchase_order_id = models.CharField(max_length=100, default='', blank=True)
    supplier = models.CharField(max_length=200, default='', blank=True)
    datetime_created = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=100, default='Stephen')
    datetime_added = models.DateTimeField(null=True, blank=True)
    added_by = models.CharField(max_length=100, default='', blank=True)

class PurchaseOrder(models.Model):
    po_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=50, default='Locked')
    po_number = models.CharField(max_length=100)
    supplier = models.CharField(max_length=200, default='', blank=True)
    quantity = models.IntegerField(default=1)
    comments = models.TextField(default='', blank=True)
    total = models.FloatField(default=0)
    datetime_created = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=100, default='Stephen')
    is_archived = models.BooleanField(default=False)

class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='po_items')
    product_name = models.CharField(max_length=200)
    quantity = models.FloatField(default=1)
    unit = models.CharField(max_length=50, default='pc')
    unit_price = models.FloatField(default=0)
    total = models.FloatField(default=0)
    remarks = models.TextField(default='', blank=True)
    description = models.TextField(default='', blank=True)

class Product(models.Model):
    product_type = models.CharField(max_length=100, default='', blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(default='', blank=True)
    quantity = models.FloatField(default=1.0)
    unit = models.CharField(max_length=50, default='set')
    srp = models.FloatField(default=0.0)
    mp = models.FloatField(default=0.0)
    lp = models.FloatField(default=0.0)
    markup = models.FloatField(default=0.0)
    overhead = models.FloatField(default=0.0)
    image = models.TextField(null=True, blank=True)
    is_combo = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=100, default='Stephen')
    is_archived = models.BooleanField(default=False)

class ProductComboItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='combo_items')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_combo_items')
    linked_product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_combo_items')
    item_name = models.CharField(max_length=200, default='', blank=True)
    quantity = models.FloatField(default=1.0)

class ProductMaterial(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='materials')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='product_materials')
    category = models.CharField(max_length=100)
    item_name = models.CharField(max_length=200, default='', blank=True)
    quantity = models.FloatField(default=1.0)
    cost = models.FloatField(default=0.0)
    total_cost = models.FloatField(default=0.0)

class PurchaseOrderLog(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50) # create, update, archive, lock, unlock
    po_number = models.CharField(max_length=100, default='', blank=True)
    details = models.TextField(default='', blank=True)
    user = models.CharField(max_length=100, default='Stephen')
    timestamp = models.DateTimeField(default=timezone.now)

class PurchaseOrderRequestLog(models.Model):
    purchase_order_request = models.ForeignKey(PurchaseOrderRequest, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50) # create, update, delete, add_to_po
    item_name = models.CharField(max_length=200, default='', blank=True)
    details = models.TextField(default='', blank=True)
    user = models.CharField(max_length=100, default='Stephen')
    timestamp = models.DateTimeField(default=timezone.now)


# ============================================================
# Employment Section Models
# ============================================================

class Employee(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('On-Leave', 'On-Leave'),
        ('Terminated', 'Terminated'),
    ]
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]
    CONTRACT_CHOICES = [
        ('Full-Time', 'Full-Time'),
        ('Part-Time', 'Part-Time'),
        ('Contract', 'Contract'),
        ('Probationary', 'Probationary'),
        ('Intern', 'Intern'),
    ]

    # Basic Info
    employee_id = models.CharField(max_length=50, unique=True)  # e.g. EMP-0001
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, default='', blank=True)
    avatar = models.TextField(default='', blank=True)  # base64 encoded image

    # Personal
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male')
    marital_status = models.CharField(max_length=50, default='Single', blank=True)
    nationality = models.CharField(max_length=100, default='Filipino', blank=True)

    # Contact
    work_email = models.EmailField(max_length=200, default='', blank=True)
    personal_email = models.EmailField(max_length=200, default='', blank=True)
    phone = models.CharField(max_length=50, default='', blank=True)
    home_address = models.TextField(default='', blank=True)

    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=200, default='', blank=True)
    emergency_contact_phone = models.CharField(max_length=50, default='', blank=True)
    emergency_contact_relationship = models.CharField(max_length=100, default='', blank=True)

    # Employment Details
    position = models.CharField(max_length=200, default='', blank=True)
    department = models.CharField(max_length=200, default='', blank=True)
    reporting_manager = models.CharField(max_length=200, default='', blank=True)
    date_hired = models.DateField(null=True, blank=True)
    probation_end_date = models.DateField(null=True, blank=True)
    contract_type = models.CharField(max_length=50, choices=CONTRACT_CHOICES, default='Full-Time')
    contract_renewal_date = models.DateField(null=True, blank=True)
    salary = models.FloatField(default=0.0)
    pay_grade = models.CharField(max_length=50, default='', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')

    # Meta
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=100, default='admin')

    @property
    def age(self):
        if not self.date_of_birth:
            return "N/A"
        from datetime import date
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

    @property
    def full_name(self):
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name[0] + '.')
        parts.append(self.last_name)
        return ' '.join(parts)

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"


class EmploymentHistory(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='employment_history')
    company_name = models.CharField(max_length=200)
    role = models.CharField(max_length=200, default='', blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    responsibilities = models.TextField(default='', blank=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.role} at {self.company_name}"


class EmployeeEducation(models.Model):
    TYPE_CHOICES = [
        ('education', 'Education'),
        ('certification', 'Certification'),
        ('license', 'License'),
    ]
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='education_records')
    entry_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='education')
    degree = models.CharField(max_length=200, default='', blank=True)  # or certification name
    institution = models.CharField(max_length=200, default='', blank=True)
    year_completed = models.IntegerField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)  # for certifications/licenses

    class Meta:
        ordering = ['-year_completed']

    def __str__(self):
        return f"{self.degree} - {self.institution}"


class EmployeeSkill(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class EmployeeDocument(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='documents')
    file_name = models.CharField(max_length=255)
    file_data = models.TextField()  # base64 encoded file content
    file_type = models.CharField(max_length=100, default='application/octet-stream')  # MIME type
    document_type = models.CharField(max_length=100, default='Other', blank=True)  # Resume, ID, Certificate, etc.
    uploaded_at = models.DateTimeField(default=timezone.now)
    uploaded_by = models.CharField(max_length=100, default='admin')

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.file_name} ({self.document_type})"


# ============================================================
# Dashboard Activity Log
# ============================================================

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
        ('archived', 'Archived'),
        ('restored', 'Restored'),
        ('uploaded', 'Uploaded'),
        ('exported', 'Exported'),
        ('login', 'Login'),
        ('status_change', 'Status Change'),
        ('acknowledged', 'Acknowledged'),
        ('transferred', 'Transferred'),
        ('generated', 'Generated'),
        ('sent_to_production', 'Sent to Production'),
    ]
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    description = models.TextField(default='', blank=True)
    user = models.CharField(max_length=100, default='admin')
    entity_type = models.CharField(max_length=100, default='', blank=True)  # e.g. 'InventoryItem', 'Employee', 'PurchaseOrder'
    entity_id = models.IntegerField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.action}] {self.description} by {self.user}"


# ============================================================
# Operations Section Models
# ============================================================

class Client(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, default='', blank=True)
    business_name = models.CharField(max_length=200, default='', blank=True)
    mobile_number = models.CharField(max_length=50, default='', blank=True)
    email_address = models.EmailField(max_length=200, default='', blank=True)
    facebook = models.CharField(max_length=200, default='', blank=True)
    tin = models.CharField(max_length=50, default='', blank=True)
    total_balance = models.FloatField(default=0.0)
    date_enrolled = models.DateTimeField(default=timezone.now)
    enrolled_by = models.CharField(max_length=100, default='Stephen')
    is_archived = models.BooleanField(default=False)

    @property
    def full_name(self):
        parts = [self.first_name]
        if self.middle_name:
            parts.append(self.middle_name[0] + '.')
        parts.append(self.last_name)
        return ' '.join(parts)

    def __str__(self):
        return f"{self.full_name} ({self.business_name})" if self.business_name else self.full_name


class JobOrder(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='job_orders')
    transaction_date = models.DateTimeField(default=timezone.now)
    transaction_mode = models.CharField(max_length=100, default='Walk-in', blank=True)
    due_date = models.DateField(null=True, blank=True)
    quantity = models.FloatField(default=0)
    wip = models.CharField(max_length=100, default='', blank=True)
    remarks = models.TextField(default='', blank=True)
    order_type = models.CharField(max_length=100, default='Events') # Gov, Events, etc.
    delivery_mode = models.CharField(max_length=100, default='PICK-UP', blank=True) # PICK-UP, DELIVERY
    amount_due = models.FloatField(default=0.0)
    discount = models.FloatField(default=0.0)
    amount_paid = models.FloatField(default=0.0)
    balance = models.FloatField(default=0.0)
    is_fully_paid = models.BooleanField(default=False)
    product_release_status = models.CharField(max_length=50, default='Pending') # Pending, Released
    status = models.CharField(max_length=50, default='ACTIVE') # ACTIVE, DONE, VOID
    is_archived = models.BooleanField(default=False)
    datetime_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=100, default='Stephen')
    
    def update_release_status(self):
        """Updates the product_release_status based on the release state of its products."""
        products = self.products.all()
        if not products.exists():
            return
            
        total_products = products.count()
        released_products = products.filter(is_released=True).count()
        
        if released_products == 0:
            new_release_status = 'Pending'
        elif released_products == total_products:
            new_release_status = 'Complete'
        else:
            new_release_status = 'Partial'
            
        update_fields = []
        if self.product_release_status != new_release_status:
            self.product_release_status = new_release_status
            update_fields.append('product_release_status')

        # Auto-update Job Order status to DONE when releasing is Complete
        if new_release_status == 'Complete' and self.status != 'DONE' and self.status != 'VOID':
            self.status = 'DONE'
            update_fields.append('status')
        elif new_release_status != 'Complete' and self.status == 'DONE':
            # Revert to ACTIVE if something was un-released
            self.status = 'ACTIVE'
            update_fields.append('status')
            
        if update_fields:
            # Save without triggering infinite recursion if we were called from JobOrderProduct.save()
            super().save(update_fields=update_fields)

    def update_totals(self):
        """Recalculates amount_due from products and then updates balance."""
        total = sum(p.quantity * p.unit_price for p in self.products.all())
        self.amount_due = total
        self.save()

    def save(self, *args, **kwargs):
        # Always recalculate balance before saving
        # Use round to handle float precision issues
        raw_balance = self.amount_due - self.discount - self.amount_paid
        self.balance = max(0, round(raw_balance, 2))
        
        # Determine if fully paid. 
        # A JO is fully paid if balance is 0 and there was an actual amount due
        if self.balance <= 0 and self.amount_due > 0:
            self.is_fully_paid = True
        # If balance > 0, it certainly isn't fully paid
        elif self.balance > 0:
            self.is_fully_paid = False
            
        super().save(*args, **kwargs)

    @property
    def get_total_amount(self):
        return self.amount_due

    def __str__(self):
        return f"JO-{self.id} for {self.client.full_name}"


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Expense Categories"


class ExpenseType(models.Model):
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE, related_name='types')
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.category.name} - {self.name}"


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_number = models.CharField(max_length=100, default='', blank=True)
    email = models.EmailField(max_length=100, default='', blank=True)
    facebook = models.CharField(max_length=100, default='', blank=True)
    address = models.TextField(default='', blank=True)
    description = models.TextField(default='', blank=True)
    tin = models.CharField(max_length=100, default='', blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class ExpenseSummary(models.Model):
    date = models.DateField(default=timezone.now)
    cash_from_chin_yu = models.FloatField(default=0.0)
    transaction_by_chin_yu = models.FloatField(default=0.0)
    cash_reimbursement = models.FloatField(default=0.0)
    others = models.FloatField(default=0.0)
    updated_by = models.CharField(max_length=100, default='Stephen')
    datetime_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Summary for {self.date}"

    class Meta:
        verbose_name_plural = "Expense Summaries"


class Expense(models.Model):
    dv_number = models.CharField(max_length=100, default='', blank=True)
    date = models.DateField(default=timezone.now)
    particular = models.TextField()
    expense_type = models.ForeignKey(ExpenseType, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    fund_source = models.CharField(max_length=100, default='Cash') # e.g., Cash, Landbank, Gcash, BPI, etc.
    amount = models.FloatField(default=0.0)
    receipt_number = models.CharField(max_length=100, default='', blank=True)
    classification = models.CharField(max_length=100, default='', blank=True)
    mode = models.CharField(max_length=100, default='Cash')
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=100, default='Stephen')

    def __str__(self):
        return f"Expense: {self.particular} - {self.amount}"


class ProductionArea(models.Model):
    name = models.CharField(max_length=100)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['display_order']


class JobOrderProduct(models.Model):
    job_order = models.ForeignKey(JobOrder, on_delete=models.CASCADE, related_name='products')
    transaction_date = models.DateField(default=timezone.now)
    pid = models.CharField(max_length=100, default='', blank=True) # Product ID from system
    name = models.CharField(max_length=200) # Client Name/Label
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_products')
    product_type = models.CharField(max_length=100, default='', blank=True)
    product_name = models.CharField(max_length=200)
    quantity = models.FloatField(default=0)
    unit_price = models.FloatField(default=0.0)
    status = models.CharField(max_length=100, default='Pending') # e.g., Pending, PH 2026-03-11
    
    # Workflow tracking
    current_area = models.ForeignKey(ProductionArea, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.CharField(max_length=100, default='', blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    last_transfer_remarks = models.TextField(default='', blank=True)
    
    is_packed = models.BooleanField(default=False)
    packed_at = models.DateTimeField(null=True, blank=True)
    is_released = models.BooleanField(default=False)
    released_at = models.DateTimeField(null=True, blank=True)
    qty_released = models.FloatField(default=0)
    due_date = models.DateField(null=True, blank=True)
    
    # Withdrawal Slip Link
    withdrawal_slip = models.ForeignKey('WithdrawalSlip', on_delete=models.SET_NULL, null=True, blank=True, related_name='jo_products')
    
    # Cost tracking for CGS
    materials_cost = models.FloatField(default=0.0)
    labor_cost = models.FloatField(default=0.0)
    overhead_cost = models.FloatField(default=0.0)
    markup_cost = models.FloatField(default=0.0)
    
    datetime_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=100, default='Stephen')

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        # Always update parent JobOrder release status after saving a product
        if self.job_order:
            self.job_order.update_release_status()

    def __str__(self):
        return f"{self.product_name} ({self.quantity}) for {self.job_order.wip}"


class JobOrderProductMaterial(models.Model):
    job_order_product = models.ForeignKey(JobOrderProduct, on_delete=models.CASCADE, related_name='jop_materials')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='jop_materials')
    category = models.CharField(max_length=100)
    item_name = models.CharField(max_length=200, default='', blank=True)
    quantity = models.FloatField(default=1.0)
    cost = models.FloatField(default=0.0)
    total_cost = models.FloatField(default=0.0)
    quantity_released = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.item_name} for {self.job_order_product.product_name}"


class Payment(models.Model):
    date = models.DateTimeField(default=timezone.now)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField(max_length=100, default='OR') # OR, AR, etc.
    or_number = models.CharField(max_length=100, default='', blank=True)
    job_order = models.ForeignKey(JobOrder, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    amount = models.FloatField(default=0.0)
    ewt = models.FloatField(default=0.0)
    date_recorded = models.DateTimeField(default=timezone.now)
    received_by = models.CharField(max_length=100, default='Stephen')
    datetime_updated = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, default='Stephen')

    def __str__(self):
        return f"Payment {self.or_number}: {self.amount} from {self.client.full_name}"


class LaborOutput(models.Model):
    OUTPUT_TYPES = [
        ('DTF press', 'DTF press'),
        ('Cut/Coat', 'Cut/Coat'),
        ('Assemble', 'Assemble'),
        ('Box', 'Box'),
        ('Envelope', 'Envelope'),
        ('Subli Press', 'Subli Press'),
        ('Stick Press', 'Stick Press'),
        ('Engrave', 'Engrave'),
        ('UV', 'UV'),
        ('Vinyl Press', 'Vinyl Press'),
        ('PBOperator', 'PBOperator'),
        ('PBTranspo', 'PBTranspo'),
        ('Book Bound', 'Book Bound'),
    ]
    date_accomplished = models.DateField(default=timezone.now)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE, related_name='labor_outputs')
    job_order = models.ForeignKey(JobOrder, on_delete=models.CASCADE, related_name='labor_outputs')
    job_order_product = models.ForeignKey(JobOrderProduct, on_delete=models.CASCADE, null=True, blank=True, related_name='labor_outputs')
    particulars = models.TextField(default='', blank=True)
    total_labor_approved = models.FloatField(default=0.0)
    output_type = models.CharField(max_length=100, choices=OUTPUT_TYPES)
    quantity = models.FloatField(default=0)
    unit_price = models.FloatField(default=0.0)
    quantity_approved = models.FloatField(default=0)
    total = models.FloatField(default=0.0)
    status = models.CharField(max_length=50, default='Pending') # Pending, Approved
    datetime_approved = models.DateTimeField(null=True, blank=True)
    approved_by = models.CharField(max_length=100, default='', blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Labor: {self.employee.full_name} - {self.output_type} ({self.quantity})"


class WithdrawalSlip(models.Model):
    wip = models.CharField(max_length=100, default='', blank=True)
    name = models.CharField(max_length=200)
    status = models.CharField(max_length=100, default='Pending')
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=100, default='Stephen')

    def __str__(self):
        return f"WS-{self.id}: {self.wip}"

class WithdrawalSlipItem(models.Model):
    withdrawal_slip = models.ForeignKey(WithdrawalSlip, on_delete=models.CASCADE, related_name='items')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='ws_items')
    jop_material = models.ForeignKey('JobOrderProductMaterial', on_delete=models.SET_NULL, null=True, blank=True, related_name='ws_items')
    product_name = models.CharField(max_length=200, default='', blank=True)
    item_name = models.CharField(max_length=200)
    quantity = models.FloatField(default=0) # Requested quantity
    quantity_approved = models.FloatField(default=0) # Released/Approved quantity
    remarks = models.TextField(default='', blank=True)
    withdrawal_slip_number = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    released_by = models.CharField(max_length=100, default='', blank=True)
    datetime_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.item_name} ({self.quantity_approved}/{self.quantity}) for {self.withdrawal_slip}"


class DeliveryReceipt(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='delivery_receipts', null=True, blank=True)
    supplier = models.CharField(max_length=200, default='', blank=True)
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=100, default='Open') # Open, Locked
    datetime_created = models.DateTimeField(default=timezone.now)
    tag_delivered_by = models.CharField(max_length=100, default='', blank=True)
    comments = models.TextField(default='', blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"DR-{self.id} for PO-{self.purchase_order.id if self.purchase_order else 'None'}"

class DeliveryReceiptItem(models.Model):
    delivery_receipt = models.ForeignKey(DeliveryReceipt, on_delete=models.CASCADE, related_name='items')
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='dr_items')
    quantity = models.FloatField(default=0.0)
    unit = models.CharField(max_length=50, default='pc', blank=True)
    received_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.inventory_item.name} ({self.quantity}) for DR-{self.delivery_receipt.id}"

class EmployeeSalary(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='salaries')
    amount = models.FloatField(default=0.0)
    datetime_updated = models.DateTimeField(auto_now=True)
    updated_by = models.CharField(max_length=100, default='Stephen')

    def __str__(self):
        return f"{self.employee.full_name} - {self.amount}"

    class Meta:
        verbose_name_plural = "Employee Salaries"

class Payroll(models.Model):
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=50, default='Draft') # Draft, Processed, Paid
    datetime_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.CharField(max_length=100, default='Stephen')

    def __str__(self):
        return f"Payroll {self.start_date} to {self.end_date}"

class PayrollRecord(models.Model):
    payroll = models.ForeignKey(Payroll, on_delete=models.CASCADE, related_name='records')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_records')
    salary_rate = models.FloatField(default=0.0)
    total_labor = models.FloatField(default=0.0) # This is 'Production' in UI
    
    # Deductions
    cash_advance = models.FloatField(default=0.0)
    incident_report = models.FloatField(default=0.0)
    benefits = models.FloatField(default=0.0)
    absences = models.FloatField(default=0.0)
    tardiness = models.FloatField(default=0.0)
    
    total_amount = models.FloatField(default=0.0) # Net Total
    status = models.CharField(max_length=50, default='Draft')

    @property
    def total_deductions(self):
        return self.cash_advance + self.incident_report + self.benefits + self.absences + self.tardiness

    @property
    def gross_total(self):
        return self.salary_rate + self.total_labor

    @property
    def net_total(self):
        # Allow negative if deductions > gross, though unlikely
        return self.gross_total - self.total_deductions

    def save(self, *args, **kwargs):
        # Auto-calculate total_amount (Net Total) before saving
        self.total_amount = self.net_total
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Payroll for {self.employee.full_name} ({self.payroll})"


class AuthItem(models.Model):
    name = models.CharField(max_length=200, unique=True)
    type = models.IntegerField(default=0) # 0: Permission, 1: Role
    description = models.TextField(default='', blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class AuthAssignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_assignments')
    item = models.ForeignKey(AuthItem, on_delete=models.CASCADE, related_name='assignments')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'item')

    def __str__(self):
        return f"{self.user.username} - {self.item.name}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_profile')
    dashboard_type = models.CharField(max_length=100, default='admin')
    # status is handled by user.is_active
    
    def __str__(self):
        return self.user.username
