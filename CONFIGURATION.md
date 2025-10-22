# Configuration Guide

This document describes how to configure the Medical Term Mapper application.

## Configuration File

All configuration is stored in a **YAML configuration file** (`config.yaml`). This file is **not tracked by Git** to keep sensitive information (like passwords and email credentials) secure.

### Initial Setup

1. Copy the example configuration file:
   ```bash
   cp config.example.yaml config.yaml
   ```

2. Edit `config.yaml` with your settings

3. Restart the application after making changes

**Important:** The `config.yaml` file is in `.gitignore` and will not be committed to version control. Always keep `config.example.yaml` updated with the structure (but without sensitive data).

## Configuration Structure

The configuration file is organized into several sections:

```yaml
database: { ... }
passwords: { ... }
data_import: { ... }
imprint: { ... }
datenschutz: { ... }
contact: { ... }
email: { ... }
```

## Database Configuration

```yaml
database:
  path: database.db
```

| Field | Description | Default |
|-------|-------------|---------|
| `path` | Path to SQLite database file | `database.db` |

## Password Configuration

```yaml
passwords:
  global_password: mapping2024
  admin_password: admin2024
```

| Field | Description | Example |
|-------|-------------|---------|
| `global_password` | Password for all users to access the application | `mapping2024` |
| `admin_password` | Password for admin console access | `admin2024` |

**Security:** Change these from the defaults before deploying!

## Data Import Configuration

```yaml
data_import:
  csv_path: data/data.CSV
  encoding: latin-1
  delimiter: ";"
```

| Field | Description | Example |
|-------|-------------|---------|
| `csv_path` | Path to the CSV file with terms | `data/data.CSV` |
| `encoding` | Character encoding of the CSV file | `latin-1` or `utf-8` |
| `delimiter` | CSV delimiter character | `;` or `,` |

The CSV file should have columns: `Kategorie` and `Item`

## Imprint Configuration (Impressum)

Required for German law compliance (Impressumspflicht).

```yaml
imprint:
  enabled: true
  type: organization  # or 'private'
  organization: Your Organization Name
  street: Street Address
  city: City, Postal Code
  country: Germany
  email: contact@example.com
  phone: "+49 123 456789"
  representative: Name of Representative
  register: Register Court and Number (if applicable)
  vat_id: VAT ID (if applicable)
  private_name: Your Full Name
```

### Imprint Fields

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `enabled` | Yes | Show/hide imprint page | `True` or `False` |
| `type` | Yes | Type of imprint | `'organization'` or `'private'` |

**For Organizations (type='organization'):**

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `organization` | Yes | Organization name | `"Medical University Hospital"` |
| `street` | Yes | Street address | `"Hauptstraße 123"` |
| `city` | Yes | City and postal code | `"12345 Berlin"` |
| `country` | Yes | Country | `"Germany"` |
| `email` | Yes | Contact email | `"contact@example.com"` |
| `phone` | No | Phone number | `"+49 30 12345678"` |
| `representative` | No | Legal representative | `"Dr. Max Mustermann"` |
| `register` | No | Commercial register | `"Amtsgericht Berlin HRB 12345"` |
| `vat_id` | No | VAT identification | `"DE123456789"` |

**For Private Persons (type='private'):**

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `private_name` | Yes | Your full name | `"Max Mustermann"` |
| `street` or `private_street` | Yes | Street address | `"Hauptstraße 123"` |
| `city` or `private_city` | Yes | City and postal code | `"12345 Berlin"` |
| `country` or `private_country` | Yes | Country | `"Germany"` |
| `email` or `private_email` | Yes | Contact email | `"contact@example.com"` |
| `phone` or `private_phone` | No | Phone number | `"+49 30 12345678"` |

### Example: Private Person Imprint

```yaml
imprint:
  enabled: true
  type: private
  private_name: Dr. Max Mustermann
  street: Musterstraße 42
  city: 12345 Musterstadt
  country: Deutschland
  email: max.mustermann@example.com
  phone: "+49 123 456789"
```

### To Hide the Imprint

Set `enabled` to `false`:

```yaml
imprint:
  enabled: false
```

This will make `/imprint` return a 404 error and hide the link from the footer.

## Data Protection Configuration (Datenschutzerklärung)

Configuration for the data protection / privacy policy page. Supports both organizations and private persons.

```yaml
datenschutz:
  enabled: true
  type: organization  # or 'private'
  organization: Your Organization Name
  street: Street Address
  city: City, Postal Code
  phone: "+49 123 456789"
  fax: "+49 123 456788"
  email: contact@example.com
  website: www.example.com
  representatives:
    - Prof. Dr. Name (Position)
    - Dr. Name (Position)
  register_court: Amtsgericht City
  register_number: VR 12345
  private_name: Your Full Name
  contact_email: privacy@example.com
  hosting_provider: Provider Name
  last_updated: Month Year
```

### Data Protection Fields

**Common Fields:**

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `enabled` | Yes | Show/hide page | `True` or `False` |
| `type` | Yes | Type of entity | `'organization'` or `'private'` |
| `street` | Yes | Street address | `"Roritzerstraße 27"` |
| `city` | Yes | City and postal code | `"90419 Nürnberg"` |
| `email` | Yes | General email | `"dgai@dgai-ev.de"` |
| `website` | Yes | Website URL | `"www.dgai.de"` |
| `contact_email` | Yes | Contact for privacy inquiries | `"privacy@example.com"` |
| `hosting_provider` | No | Hosting provider name | `"IONOS SE"` |
| `last_updated` | No | Last update date | `"Oktober 2025"` |

**For Organizations (type='organization'):**

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `organization` | Yes | Organization name | `"DGAI e.V."` |
| `phone` | Yes | Phone number | `"0049-911-933780"` |
| `fax` | No | Fax number | `"0049-911-3938195"` |
| `representatives` | No | List of representatives | Array of strings |
| `register_court` | No | Register court | `"Amtsgericht Heidelberg"` |
| `register_number` | No | Register number | `"VR 319"` |

**For Private Persons (type='private'):**

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `private_name` | Yes | Your full name | `"Max Mustermann"` |
| `private_street` or `street` | Yes | Street address | `"Hauptstraße 123"` |
| `private_city` or `city` | Yes | City and postal code | `"12345 Berlin"` |
| `private_email` or `email` | Yes | Contact email | `"contact@example.com"` |
| `private_phone` or `phone` | No | Phone number | `"+49 30 12345678"` |

### Example: Organization

```yaml
datenschutz:
  enabled: true
  type: organization
  organization: Medical Research Institute
  street: Research Street 10
  city: 12345 Research City
  phone: "+49 123 456789"
  email: info@research.example
  website: www.research.example
  representatives:
    - Prof. Dr. Jane Doe (Director)
    - Dr. John Smith (Deputy Director)
  contact_email: privacy@research.example
  last_updated: Oktober 2025
```

### Example: Private Person

```yaml
datenschutz:
  enabled: true
  type: private
  private_name: Dr. Max Mustermann
  street: Musterstraße 42
  city: 12345 Musterstadt
  email: datenschutz@example.com
  website: www.example.com
  contact_email: contact@example.com
  hosting_provider: IONOS SE
  last_updated: Oktober 2025
```

### To Hide the Data Protection Page

Set `enabled` to `false`:

```yaml
datenschutz:
  enabled: false
```

This will make `/datenschutz` return a 404 error and hide the link from the footer.

### To Update Information

1. Edit `config.yaml`
2. Find the `imprint` or `datenschutz` section
3. Update the relevant fields with your information
4. Restart the application

## Contact Form Configuration

Configuration for the contact form that allows users to send messages.

```yaml
contact:
  enabled: true
  email: contact@example.com
  store_in_db: true
  send_email: false
  subjects:
    - Allgemeine Anfrage
    - Technischer Support
    - Feedback zur Studie
    - Datenschutzanfrage
    - Sonstiges
```

### Contact Form Fields

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `enabled` | Yes | Show/hide contact form | `True` or `False` |
| `email` | Yes | Email address for receiving messages | `"contact@example.com"` |
| `store_in_db` | Yes | Store messages in database | `True` or `False` |
| `send_email` | Yes | Send messages via email | `True` or `False` |
| `subjects` | Yes | List of subject options for dropdown | Array of strings |

## Email Server Configuration

Configuration for sending contact form emails via SMTP.

```yaml
email:
  smtp_server: smtp.example.com
  smtp_port: 587
  use_tls: true
  username: your-email@example.com
  password: your-password
  from_email: noreply@example.com
  from_name: Terminology Mapper
```

### Email Configuration Fields

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `smtp_server` | Yes | SMTP server hostname | `"smtp.gmail.com"` |
| `smtp_port` | Yes | SMTP port (587 for TLS, 465 for SSL) | `587` |
| `use_tls` | Yes | Use TLS encryption | `True` |
| `username` | Yes | SMTP account username | `"user@example.com"` |
| `password` | Yes | SMTP account password | `"your-password"` |
| `from_email` | Yes | Sender email address | `"noreply@example.com"` |
| `from_name` | Yes | Sender display name | `"My Application"` |

### Common SMTP Providers

**Gmail:**
```yaml
email:
  smtp_server: smtp.gmail.com
  smtp_port: 587
  use_tls: true
  username: your-gmail@gmail.com
  password: your-app-password  # Use App Password
  from_email: your-gmail@gmail.com
  from_name: Terminology Mapper
```
Note: Use App Password, not your regular Gmail password.

**IONOS:**
```yaml
email:
  smtp_server: smtp.ionos.de
  smtp_port: 587
  use_tls: true
  username: your-email@yourdomain.com
  password: your-password
  from_email: noreply@yourdomain.com
  from_name: Terminology Mapper
```

**Microsoft 365 / Outlook:**
```yaml
email:
  smtp_server: smtp.office365.com
  smtp_port: 587
  use_tls: true
  username: your-email@outlook.com
  password: your-password
  from_email: your-email@outlook.com
  from_name: Terminology Mapper
```

### Security Note

⚠️ **Important:** The `config.yaml` file is in `.gitignore` and will NOT be committed to version control. This keeps your passwords safe.

For additional security in production, consider using environment variables:

1. Set environment variables:
   ```bash
   export SMTP_USERNAME="your-email@gmail.com"
   export SMTP_PASSWORD="your-app-password"
   ```

2. Modify the application to read from environment variables if you prefer.

### Customizing Subject Options

You can customize the subject dropdown options to match your needs:

```yaml
contact:
  enabled: true
  email: info@research.example
  store_in_db: true
  send_email: false
  subjects:
    - General Inquiry
    - Technical Problem
    - Study Feedback
    - Privacy Request
    - Collaboration
    - Other
```

### Managing Contact Messages

When `store_in_db` is `True`, all contact form submissions are stored in the database and can be viewed in the admin console:

1. Log in to the admin console at `/admin`
2. Click on "View Messages" button
3. Mark messages as read or delete them

The admin console will show:
- Total number of contact messages
- Number of unread messages (highlighted)
- Full message details including sender info

### To Hide the Contact Form

Set `enabled` to `false`:

```yaml
contact:
  enabled: false
```

This will make `/contact` return a 404 error and hide the link from the footer.

## After Making Changes

**Important**: Restart the server after changing any configuration in `config.yaml`:

```bash
# Stop the current server (Ctrl+C if running in foreground)
# Then restart:
python main.py
```

## Complete Example Configuration

Here's a complete example `config.yaml` file:

```yaml
database:
  path: database.db

passwords:
  global_password: MySecurePassword123
  admin_password: AdminSecure456

data_import:
  csv_path: data/terms.csv
  encoding: utf-8
  delimiter: ","

imprint:
  enabled: true
  type: organization
  organization: Medical Research Institute
  street: Research Street 10
  city: 12345 Research City
  country: Germany
  email: contact@research.example
  phone: "+49 123 456789"
  representative: Prof. Dr. Jane Doe

datenschutz:
  enabled: true
  type: organization
  organization: Medical Research Institute
  street: Research Street 10
  city: 12345 Research City
  email: privacy@research.example
  website: www.research.example
  contact_email: contact@research.example
  hosting_provider: IONOS SE
  last_updated: Oktober 2025

contact:
  enabled: true
  email: contact@research.example
  store_in_db: true
  send_email: true
  subjects:
    - General Inquiry
    - Technical Support
    - Study Feedback
    - Privacy Request
    - Other

email:
  smtp_server: smtp.ionos.de
  smtp_port: 587
  use_tls: true
  username: contact@research.example
  password: your-smtp-password
  from_email: noreply@research.example
  from_name: Research Institute
```
