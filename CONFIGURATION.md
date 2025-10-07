# Configuration Guide

This document describes how to configure the Medical Term Mapper application.

## Configuration Location

All configuration is done in [main.py](main.py) at the top of the file.

## Password Configuration

### Global User Password
All users share the same password to access the application.

```python
GLOBAL_PASSWORD = 'mapping2024'  # Line 20
```

**To change**: Edit line 20 in [main.py](main.py)

### Admin Console Password
Separate password for accessing the admin console.

```python
ADMIN_PASSWORD = 'admin2024'  # Line 21
```

**To change**: Edit line 21 in [main.py](main.py)

## Imprint Configuration (Impressum)

Required for German law compliance (Impressumspflicht).

```python
IMPRINT_CONFIG = {
    'enabled': True,  # Set to False to hide imprint
    'organization': 'Your Organization Name',
    'street': 'Street Address',
    'city': 'City, Postal Code',
    'country': 'Germany',
    'email': 'contact@example.com',
    'phone': '+49 123 456789',
    'representative': 'Name of Representative',
    'register': 'Register Court and Number (if applicable)',
    'vat_id': 'VAT ID (if applicable)',
}
```

**Location**: Lines 24-35 in [main.py](main.py)

### Imprint Fields

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `enabled` | Yes | Show/hide imprint page | `True` or `False` |
| `organization` | Yes | Organization name | `"Medical University Hospital"` |
| `street` | Yes | Street address | `"Hauptstraße 123"` |
| `city` | Yes | City and postal code | `"12345 Berlin"` |
| `country` | Yes | Country | `"Germany"` |
| `email` | Yes | Contact email | `"contact@example.com"` |
| `phone` | No | Phone number | `"+49 30 12345678"` |
| `representative` | No | Legal representative | `"Dr. Max Mustermann"` |
| `register` | No | Commercial register | `"Amtsgericht Berlin HRB 12345"` |
| `vat_id` | No | VAT identification | `"DE123456789"` |

### To Hide the Imprint

Set `enabled` to `False`:

```python
IMPRINT_CONFIG = {
    'enabled': False,
    # ... rest of config
}
```

This will make `/imprint` return a 404 error and hide the link from the footer.

### To Update Imprint Information

1. Open [main.py](main.py)
2. Find the `IMPRINT_CONFIG` dictionary (around line 24)
3. Update the relevant fields with your information
4. Restart the application

## Database Configuration

The database file location can be changed:

```python
DATABASE = 'database.db'  # Line 19
```

## CSV Data Source

Terms are imported from:

```
data/data.CSV
```

Format: UTF-8 encoded, semicolon-separated
Columns: `Kategorie;Item`

## After Making Changes

**Important**: Restart the server after changing any configuration:

```bash
# Stop the current server (Ctrl+C if running in foreground)
# Then restart:
python main.py
```

## Security Recommendations

1. **Change default passwords** before deploying to production
2. Use strong, unique passwords
3. Keep configuration file secure (not in public repositories)
4. Consider using environment variables for sensitive data in production
5. Enable HTTPS in production deployment
