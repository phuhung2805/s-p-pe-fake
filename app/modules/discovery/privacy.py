import re

def mask_phone_number(phone: str) -> str:
    """
    Masks a phone number: e.g., '0912345005' -> '091****005'
    Preserves prefix and last 3 digits, masking middle digits.
    """
    if not phone:
        return "N/A"
    clean = re.sub(r"[^\d+]", "", phone)
    if len(clean) >= 9:
        prefix = clean[:3]
        suffix = clean[-3:]
        masked_middle = "*" * (len(clean) - 6)
        return f"{prefix}{masked_middle}{suffix}"
    return clean[:2] + "****" + clean[-2:]

def mask_street_address(address: str) -> str:
    """
    Partially redacts detailed street address to protect personal residence privacy.
    e.g., 'Số 45 Ngõ 123 Đường Cầu Giấy, Phường Quan Hoa, Cầu Giấy, Hà Nội'
    -> 'Số **, Ngõ *** Đ. Cầu Giấy, Phường Quan Hoa, Cầu Giấy, Hà Nội'
    """
    if not address:
        return "N/A"
    
    parts = [p.strip() for p in address.split(",")]
    if len(parts) > 1:
        # Mask specific house number in the first segment
        first_segment = re.sub(r"\d+", lambda m: "*" * len(m.group()), parts[0])
        return ", ".join([first_segment] + parts[1:])
    
    # Fallback masking
    return re.sub(r"\d+", "***", address)
