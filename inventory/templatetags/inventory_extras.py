from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
@register.filter
def get_pid_suffix(pid):
    if pid and len(pid) >= 4:
        return pid[-4:]
    return pid

@register.filter
def get_tws_format(product):
    pid_suffix = ""
    if product.pid and len(product.pid) >= 4:
        pid_suffix = product.pid[-4:]
    
    # Format: TWS[JO_WIP]_[PID_SUFFIX]
    # We'll use the WIP from the job order
    wip = product.job_order.wip if product.job_order else ""
    # Remove "WIP-" prefix if present
    wip = wip.replace("WIP-", "")
    
    return f"TWS{wip}_{pid_suffix}"

@register.filter
def has_auth_perm(user, perm_name):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.auth_assignments.filter(item__name=perm_name).exists()
