# Configuration Setup Guide

## Quick Start

1. **Copy the example configuration:**
   ```bash
   cp config.example.yaml config.yaml
   ```

2. **Edit `config.yaml` with your settings:**
   - Update passwords (required)
   - Configure your email settings if using contact form
   - Customize imprint and data protection information
   - Adjust data import settings if needed

3. **Start the application:**
   ```bash
   python main.py
   ```

## Important Notes

- `config.yaml` is **NOT tracked by Git** (it's in `.gitignore`)
- This protects your sensitive information like passwords and email credentials
- Always keep `config.example.yaml` updated with the structure
- Never commit `config.yaml` to version control

## Configuration Sections

| Section | Description |
|---------|-------------|
| `database` | Database file path |
| `passwords` | User and admin passwords |
| `data_import` | CSV file path, encoding, and delimiter |
| `imprint` | Legal imprint (Impressum) information |
| `datenschutz` | Data protection (Datenschutz) information |
| `contact` | Contact form settings |
| `email` | SMTP email server configuration |

## Need Help?

See [CONFIGURATION.md](CONFIGURATION.md) for detailed documentation of all configuration options.

## Security Best Practices

1. Change default passwords immediately
2. Use strong, unique passwords
3. Never share your `config.yaml` file
4. For Gmail, use App Passwords instead of your regular password
5. Keep the `config.yaml` file secure and backed up separately

