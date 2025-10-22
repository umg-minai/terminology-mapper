# Medical Term Mapper - Gamified Edition

A web-based application for mapping medical terms to standardized terminologies with gamification features to make the process engaging and motivating.

## Features

### Core Functionality
- **Pseudonymized Login**: Simple username-based authentication
- **Smart Term Selection**: Prioritizes terms with fewer than 2 mappings
- **Session-Based Mapping**: Customizable sessions (10, 15, or 20 terms)
- **Category Display**: Terms shown with their category context
- **Multiple Code Support**: Add multiple codes per term (across different vocabularies)

### Advanced Mapping Features
- **Vocabulary Selection**: Choose from SNOMED CT, ICD-10, or LOINC
- **Auto-Detection**: Automatic vocabulary detection based on code format
  - SNOMED CT: 6-18 digit codes (e.g., 123456789)
  - ICD-10: Letter + 2 digits with optional extensions (e.g., I10, E11.9)
  - LOINC: Codes with dash separator (e.g., LP12345-6, 1234-5)
- **Exact Match Indicator**: Checkbox to mark if the code is an exact match
- **No Code Found**: Button to indicate when no appropriate code exists

### Gamification Elements
- **Progress Tracking**: Overall progress bar showing completion status
- **Leaderboard**: Competitive ranking based on total mappings
- **User Statistics**: Track your mappings, completed sessions, and 7-day streak
- **Session Progress**: Visual progress bar during mapping sessions
- **Responsive Design**: Clean, modern UI that works on all devices

### Keyboard Shortcuts
- **Ctrl+Enter**: Submit current mapping and continue
- **Ctrl+N**: Mark as "No Code Found"

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up configuration:
```bash
cp config.example.yaml config.yaml
```
Then edit `config.yaml` with your settings (see [CONFIG_SETUP.md](CONFIG_SETUP.md) for details).

3. Make sure your medical terms are in the CSV file specified in your configuration (default: `data/data.CSV`) with format:
```
Kategorie;Item
Administration;ADT-Update
Administration;Ambulanz
```

4. Run the application:
```bash
python main.py
```

5. Open your browser and navigate to:
```
http://localhost:5000
```

## Configuration

All configuration is stored in `config.yaml` (not tracked by Git). Key settings include:

- **Passwords**: User and admin authentication
- **Data Import**: CSV file path, encoding, and delimiter
- **Imprint & Privacy**: Legal compliance information (required in Germany)
- **Contact Form**: Enable/disable and configure email notifications
- **Email**: SMTP settings for sending contact form emails

See [CONFIGURATION.md](CONFIGURATION.md) for complete documentation.

## How It Works

1. **Login**: Enter a pseudonymized username to start
2. **Dashboard**: View your stats, overall progress, and leaderboard
3. **Start Session**: Choose session size (10-20 terms)
4. **Map Terms**:
   - View term with category
   - Enter code(s) - vocabulary is auto-detected
   - Mark exact match if applicable
   - Add multiple codes if needed
   - Click "No Code Found" if no appropriate code exists
5. **Complete**: Review your session and start another or return to dashboard

## Database Schema

- **users**: Stores pseudonymized usernames and total points
- **terms**: Medical terms with categories imported from CSV
- **mappings**: User mappings with JSON-encoded codes array containing:
  - `code`: The terminology code
  - `vocabulary`: SNOMED, ICD10, or LOINC
  - `exact_match`: Boolean indicating if it's an exact match
  - `no_code_found`: Boolean flag for terms without codes
- **sessions**: Tracking of user sessions

## Data Format

The application imports terms from a CSV file. The path, encoding, and delimiter are configurable in `config.yaml`:

```yaml
data_import:
  csv_path: data/data.CSV
  encoding: latin-1
  delimiter: ";"
```

CSV format requirements:
- Column 1: **Kategorie** (Category)
- Column 2: **Item** (Medical term)

Example:
```csv
Kategorie;Item
Administration;Aufnahmedatum
Administration;Entlassungsdatum
Diagnose;Hauptdiagnose
```

## Technical Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **Session Management**: Starlette SessionMiddleware
- **Minimal dependencies**: Lightweight and portable

## Vocabulary Detection Logic

The application automatically detects the vocabulary based on code patterns:

- **SNOMED CT**: Pure numeric codes with 6-18 digits
- **ICD-10**: Starts with letter (A-T, V-Z), followed by 2 digits, optional dot and extensions
- **LOINC**: Optional "LP" prefix, 4-6 digits, dash, and check digit

Users can override the auto-detection by manually selecting the vocabulary.

## Development

The application uses FastAPI with:
- Async/await support for better performance
- Jinja2 templates for server-side rendering
- SQLite for data persistence
- Session-based authentication
- JSON storage for flexible code data structure
