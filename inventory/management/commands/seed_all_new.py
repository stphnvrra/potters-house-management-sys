from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from inventory.models import (
    Client, JobOrder, ExpenseCategory, ExpenseType, Supplier, 
    ExpenseSummary, Expense, Payment, DeliveryReceipt, WithdrawalSlip, PurchaseOrder
)
import random
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds mock data for Expenses, Payments, DRs, and WSs.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding Expense Categories and Types...')
        cat_ops, _ = ExpenseCategory.objects.get_or_create(name='Operating Expenses')
        cat_mat, _ = ExpenseCategory.objects.get_or_create(name='Materials')
        
        type_rent, _ = ExpenseType.objects.get_or_create(category=cat_ops, name='Rent/Lease')
        type_util, _ = ExpenseType.objects.get_or_create(category=cat_ops, name='Utilities')
        type_raw, _ = ExpenseType.objects.get_or_create(category=cat_mat, name='Raw Materials')
        
        self.stdout.write('Seeding Suppliers...')
        sup1, _ = Supplier.objects.get_or_create(name='Global Paper Co.', contact_number='09123456789')
        sup2, _ = Supplier.objects.get_or_create(name='Ink Masters Inc.', contact_number='09987654321')

        self.stdout.write('Seeding Expenses...')
        for i in range(5):
            Expense.objects.get_or_create(
                dv_number=f'DV-2026-00{i+1}',
                particular=f'Purchase of supplies batch {i+1}',
                expense_type=random.choice([type_rent, type_util, type_raw]),
                supplier=random.choice([sup1, sup2, None]),
                amount=random.uniform(1000, 5000),
                receipt_number=f'OR-{random.randint(10000,99999)}',
                mode=random.choice(['Cash', 'Gcash', 'BPI'])
            )

        self.stdout.write('Seeding Expense Summary...')
        ExpenseSummary.objects.get_or_create(
            date=timezone.now().date(),
            cash_from_chin_yu=10000.0,
            transaction_by_chin_yu=2500.0,
            cash_reimbursement=500.0
        )

        self.stdout.write('Seeding Clients & Job Orders...')
        client, _ = Client.objects.get_or_create(first_name='Acme', last_name='Corp', business_name='Acme Inc.')
        jo, _ = JobOrder.objects.get_or_create(client=client, wip='WIP-001', amount_due=15000, balance=5000)

        self.stdout.write('Seeding Payments...')
        Payment.objects.get_or_create(
            client=client,
            job_order=jo,
            payment_type='OR',
            or_number='OR-998877',
            amount=10000.0
        )

        self.stdout.write('Seeding Withdrawal Slips...')
        WithdrawalSlip.objects.get_or_create(wip='WIP-001', name='Client XYZ Materials', status='Approved')

        self.stdout.write('Seeding Delivery Receipts...')
        po = PurchaseOrder.objects.first()
        DeliveryReceipt.objects.get_or_create(
            purchase_order=po,
            supplier='Ink Masters Inc.',
            status='Open',
            comments='Partial delivery received.'
        )

        self.stdout.write(self.style.SUCCESS('Successfully seeded all new tables!'))
