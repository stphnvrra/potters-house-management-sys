import os
import django
import random
from datetime import datetime, timedelta

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'potters_inventory_prod.settings')
django.setup()

from inventory.models import (
    InventoryItem, InventoryLog, PurchaseOrderRequest, 
    PurchaseOrder, PurchaseOrderItem, Product, 
    ProductComboItem, ProductMaterial
)

# Constants for generating random data
ITEM_TYPES = ['RAW Materials', 'Indirect Materials', 'Print Materials', 'Special Boards/Papers', 'Printing Process', 'Garments', 'Office Supplies', 'Assets', 'Obsolete']
COLORS = ['Red', 'Blue', 'Green', 'Yellow', 'White', 'Black', 'Orange', 'Purple', 'Brown', 'Grey', 'Pink', 'Beige', 'Navy', 'Teal', 'Coral']
SHAPES = ['Round', 'Square', 'Cylindrical', 'Flat', 'Irregular', 'Oval', 'Rectangular', 'Triangular']
SIZES = ['Small', 'Medium', 'Large', 'XL', 'XXL', 'Mini', 'Jumbo']
UNITS = ['kg', 'pc', 'liter', 'bag', 'box', 'roll', 'meter', 'set', 'pack']
SUPPLIERS = ['Pottery Supply Co.', 'Clay World', 'Glaze Master', 'Tool Hub', 'Packaging Pros', 'Fabric House', 'Paint Palace', 'Chemical Solutions', 'Craft Central', 'Material Depot']
USERS = ['Stephen', 'Admin', 'John Doe', 'Jane Smith', 'Mark Johnson', 'Sarah Wilson']
STATUSES = ['created', 'pending', 'ordered', 'received', 'cancelled']
PRODUCT_TYPES = ['Combo', 'Government', 'Invites', 'Prints', 'Souvenirs', 'Others', 'Corporate', 'Events', 'Wedding']
PRODUCT_NAMES = [
    'Cashmere', 'Burlap Bag', 'Kraft Box', 'DOT Rubber Slippers', 'DOT Care Kits',
    'Transparent Pouch', 'Sun Screen Sachet', 'Insect Repellant', 'Face Towel',
    'Polygon Invites', 'PVC ID Card', 'Bamboo Tumbler', 'Nordic Mug', 'Wooden Fan',
    'CE Pocket Tool', 'Hot & Cold Tum', 'Bath Towel', 'Nordic Mug E', 
    'Lei Special Ribbon', 'RG Turn', 'Wbox', 'Sbox', 'Ceramic Plate', 'Glass Jar',
    'Cotton Tote', 'Leather Wallet', 'Silk Scarf', 'Canvas Print', 'Metal Keychain',
    'Wooden Coaster', 'Paper Envelope', 'Fabric Pouch', 'Eco Bag', 'Acrylic Stand'
]
MATERIAL_CATEGORIES = ['Major Raw Materials', 'Other Raw Materials', 'Consumables', 'Packing & Packaging', 'Labor Cost']
MATERIALS = ['Ceramic', 'Metal', 'Wood', 'Plastic', 'Glass', 'Leather', 'Fabric', 'Rubber', 'Silicone', 'Cotton']

def generate_random_date(start_date=None, end_date=None):
    if not start_date:
        start_date = datetime.now() - timedelta(days=365)
    if not end_date:
        end_date = datetime.now()
    
    time_between_dates = end_date - start_date
    days_between_dates = time_between_dates.days
    random_number_of_days = random.randrange(days_between_dates + 1) if days_between_dates > 0 else 0
    return start_date + timedelta(days=random_number_of_days)

def seed_data():
    print("Clearing existing data (except for auth)...")
    InventoryItem.objects.all().delete()
    InventoryLog.objects.all().delete()
    PurchaseOrder.objects.all().delete()
    PurchaseOrderRequest.objects.all().delete()
    Product.objects.all().delete()
    
    # 1. Create Inventory Items (200 items)
    print("Creating 200 Inventory Items...")
    items = []
    for i in range(200):
        item_type = random.choice(ITEM_TYPES)
        color = random.choice(COLORS)
        name = f"{color} {item_type} {i+1}"
        
        item = InventoryItem(
            item_type=item_type,
            sku=f"SKU-{1000+i}",
            name=name,
            image='', 
            sub_unit=random.choice(UNITS),
            description=f"Description for {name}",
            total_purchases="0",
            total_withdrawal="0",
            total_balance="0",
            price=str(round(random.uniform(10.0, 500.0), 2)),
            is_negative='no',
            color=color,
            model=f"Model-{random.choice(['A', 'B', 'C', 'D', 'E'])}{i}",
            shape=random.choice(SHAPES),
            size=random.choice(SIZES),
            dimensions=f"{random.randint(10,50)}x{random.randint(10,50)}x{random.randint(10,50)}",
            volume=f"{random.randint(1,10)}L",
            material=random.choice(MATERIALS),
            addon=random.choice(['Handle', 'Lid', 'Strap', 'Zipper', '']),
            other=random.choice(['Premium', 'Standard', 'Economy', '']),
            occasion=random.choice(['Birthday', 'Wedding', 'Corporate', 'Holiday', '']),
            is_archived=random.choice([True, False, False, False, False]),
            cost=str(round(random.uniform(5, 300), 2)),
            shipping_fee=str(round(random.uniform(0, 50), 2)),
            updated_by=random.choice(USERS),
            datetime_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        item.save()
        items.append(item)
    
    print(f"Created {len(items)} inventory items. Now generating history...")

    # 2. Generate History (Logs) for each item and update totals
    logs_to_create = []
    for item in items:
        num_transactions = random.randint(5, 25)
        current_balance = 0.0
        total_purchases = 0.0
        total_withdrawals = 0.0
        current_date = datetime.now() - timedelta(days=random.randint(100, 365))
        
        for t in range(num_transactions):
            current_date += timedelta(days=random.randint(1, 10))
            if current_date > datetime.now():
                current_date = datetime.now()
            
            if current_balance <= 0:
                trans_type = 'purchase'
            else:
                trans_type = random.choices(
                    ['purchase', 'withdrawal', 'damage', 'returned', 'adjustment'],
                    weights=[30, 50, 5, 5, 10], k=1
                )[0]
            
            qty = float(random.randint(1, 50))
            if trans_type == 'purchase' or trans_type == 'returned':
                current_balance += qty
                if trans_type == 'purchase': total_purchases += qty
            elif trans_type == 'withdrawal' or trans_type == 'damage':
                current_balance -= qty
                if trans_type == 'withdrawal': total_withdrawals += qty
            elif trans_type == 'adjustment':
                change = random.choice([qty, -qty])
                current_balance += change
                qty = abs(change)
                
            logs_to_create.append(InventoryLog(
                inventory_item=item,
                user=random.choice(USERS),
                transaction_type=trans_type,
                quantity=str(qty),
                timestamp=current_date,
                notes=f"Auto-generated {trans_type}"
            ))
            
        item.total_purchases = str(total_purchases)
        item.total_withdrawal = str(total_withdrawals)
        item.total_balance = str(current_balance)
        item.is_negative = 'yes' if current_balance < 0 else 'no'
        try:
            item.inventory_value = str(round(current_balance * float(item.price), 2))
        except:
            item.inventory_value = "0"
        item.datetime_updated = current_date.strftime('%Y-%m-%d %H:%M:%S')
        item.save()

    InventoryLog.objects.bulk_create(logs_to_create)
    print(f"Generated {len(logs_to_create)} inventory logs and updated item totals.")

    # 3. Create Purchase Orders (100 POs)
    print("Seeding 100 Purchase Orders...")
    for i in range(100):
        po = PurchaseOrder.objects.create(
            po_date=generate_random_date(),
            status=random.choice(['Open', 'Locked', 'Pending', 'Completed']),
            po_number=f"PO-{2025}-{1000+i}",
            supplier=random.choice(SUPPLIERS),
            quantity=0,
            comments=f"Generated PO #{i+1}",
            total=0,
            datetime_created=generate_random_date(),
            created_by=random.choice(USERS),
            is_archived=random.choice([True, False, False, False])
        )
        
        po_total = 0
        po_qty = 0
        num_items = random.randint(1, 8)
        for _ in range(num_items):
            inv_item = random.choice(items)
            qty = random.randint(10, 100)
            u_price = float(inv_item.price)
            line_total = round(qty * u_price, 2)
            
            PurchaseOrderItem.objects.create(
                purchase_order=po,
                inventory_item=inv_item,
                product_name=inv_item.name,
                quantity=qty,
                unit=inv_item.sub_unit,
                unit_price=u_price,
                total=line_total,
                remarks="Auto-added",
                description=inv_item.description
            )
            po_total += line_total
            po_qty += qty
            
        po.total = round(po_total, 2)
        po.quantity = po_qty
        po.save()
        
    print("Created 100 Purchase Orders with items.")
        
    # 4. Create Purchase Order Requests (100 PRs)
    print("Seeding 100 Purchase Order Requests...")
    for i in range(100):
        inv_item = random.choice(items)
        PurchaseOrderRequest.objects.create(
            request_type=random.choice(['ASAP', 'STOCKING', '-']),
            name=inv_item.name,
            description=inv_item.description,
            remarks=f"Generated Request #{i+1}",
            quantity=random.randint(1, 50),
            unit=inv_item.sub_unit,
            status=random.choice(STATUSES),
            supplier=random.choice(SUPPLIERS),
            datetime_created=generate_random_date(),
            created_by=random.choice(USERS)
        )

    print("Created 100 Purchase Order Requests.")

    # 5. Create Products (150 products)
    print("Seeding 150 Products...")
    products = []
    for i in range(150):
        is_combo = random.random() > 0.7
        product_type = 'Combo' if is_combo else random.choice(PRODUCT_TYPES)
        if is_combo:
            name_parts = random.sample(PRODUCT_NAMES, random.randint(2, 4))
            name = ' + '.join(name_parts)
        else:
            name_base = random.choice(PRODUCT_NAMES)
            name = f"{name_base} {random.choice(['(V)', '(E)', '(E&V)', ''])}" if random.random() > 0.5 else name_base
        
        markup = round(random.uniform(50, 2000), 2)
        overhead = round(random.uniform(10, 200), 2)
        
        product = Product.objects.create(
            product_type=product_type,
            name=name.strip(),
            description=f"Generated product description",
            quantity=round(random.uniform(1, 10), 2),
            unit='set' if is_combo else random.choice(['pc', 'pair', 'pack']),
            srp=round(markup + overhead, 2),
            mp=round(markup, 2),
            lp=round(markup * 0.9, 2),
            markup=markup,
            overhead=overhead,
            is_combo=is_combo,
            created_at=generate_random_date(),
            updated_at=datetime.now(),
            created_by=random.choice(USERS),
            is_archived=False
        )
        products.append(product)
        
        # Add combo items if applicable
        if is_combo:
            num_combo_items = random.randint(2, 5)
            selected_items = random.sample(items, min(num_combo_items, len(items)))
            for inv_item in selected_items:
                ProductComboItem.objects.create(
                    product=product,
                    inventory_item=inv_item,
                    item_name=inv_item.name,
                    quantity=random.randint(1, 3)
                )
        
        # Add materials to all products
        num_materials = random.randint(2, 6)
        selected_materials = random.sample(items, min(num_materials, len(items)))
        for inv_item in selected_materials:
            qty = round(random.uniform(0.5, 10), 2)
            cost = float(inv_item.cost) if inv_item.cost else round(random.uniform(5, 100), 2)
            ProductMaterial.objects.create(
                product=product,
                inventory_item=inv_item,
                category=random.choice(MATERIAL_CATEGORIES),
                item_name=inv_item.name,
                quantity=qty,
                cost=cost,
                total_cost=round(qty * cost, 2)
            )
    
    print(f"Created 150 products with items and materials.")
    
    print("\n" + "="*50)
    print("SEEDING COMPLETED SUCCESSFULLY!")
    print("="*50 + "\n")

if __name__ == '__main__':
    seed_data()
