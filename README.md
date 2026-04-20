# CP Wiki

CP Wiki is a knowledge base platform designed for competitive programming notes and community discussions. It provides structured storage for algorithm patterns, data structures, and contest strategies.

## Requirements

- Python 3.10+
- Django 5.0+
- Node.js (for SCSS builds)

## Installation

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the environment:
   Create `config/local_settings.py` based on the provided template to override default settings.

4. Run migrations:
   ```bash
   python manage.py migrate
   ```

5. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Development

SCSS files are located in `static/scss`. To rebuild the CSS, use:
```bash
npm run build:css
```

## Contribution

All pull requests must pass the CI build tests before merging. Use the provided template for submission.

a