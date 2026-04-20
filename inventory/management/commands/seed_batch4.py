from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from inventory.models import JobOrderProduct, Employee, EmployeeSalary, Payroll, PayrollRecord
import random
from decimal import Decimal

class Command(BaseCommand):
    help = 'Seeds mock data for CGS, Salaries, and Payroll modules.'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding Employee Salaries...')
        employees = Employee.objects.all()
        if not employees.exists():
            # Create some mock employees
            for name in ['Alice Smith', 'Bob Johnson', 'Charlie Brown']:
                Employee.objects.create(full_name=name, status='Active')
            employees = Employee.objects.all()

        for emp in employees:
            salary, created = EmployeeSalary.objects.get_or_create(employee=emp)
            if created or salary.salary_amount == 0:
                salary.salary_amount = Decimal(random.randint(400, 800))
                salary.save()

        self.stdout.write('Seeding JobOrderProduct Costs...')
        jo_products = JobOrderProduct.objects.all()
        for jop in jo_products:
            if jop.materials_cost == 0:
                jop.materials_cost = Decimal(random.uniform(100.0, 500.0))
                jop.labor_cost = Decimal(random.uniform(50.0, 300.0))
                jop.overhead_cost = Decimal(random.uniform(20.0, 100.0))
                jop.markup_cost = Decimal(random.uniform(50.0, 200.0))
                jop.save()

        self.stdout.write('Seeding Payrolls...')
        now = timezone.now()
        start_date = (now - timedelta(days=15)).date()
        end_date = now.date()
        
        payroll, created = Payroll.objects.get_or_create(
            start_date=start_date,
            end_date=end_date,
            defaults={'status': 'Pending'}
        )
        
        if created:
            for emp in employees:
                salary = emp.employeesalary.salary_amount if hasattr(emp, 'employeesalary') else Decimal(random.randint(400, 800))
                labor = Decimal(random.uniform(0, 10))
                PayrollRecord.objects.create(
                    payroll=payroll,
                    employee=emp,
                    salary_rate=salary,
                    total_labor=labor,
                    total_amount=salary + labor
                )

        self.stdout.write(self.style.SUCCESS('Successfully seeded Batch 4 data!'))
