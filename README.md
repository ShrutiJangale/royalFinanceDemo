## RoyalFinanceAI -  Bank Statement Analyzer

Step-by-step guide to set up and run the app locally.

### Project Structure (key parts)
```
royalFinanceDemo/
├─ royalfinanceAI/
│  ├─ manage.py
│  ├─ bankstatement_project/
│  └─ statement_analyzer/
└─ venv/  (created locally; ignored by git)
```

### 1) Clone or open the project
If you're starting from this folder already, skip to step 2.
```bash
git clone "https://github.com/ShrutiJangale/royalFinanceDemo.git"
cd royalFinanceDemo
```

### 2) Create and activate a virtual environment 
```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3) Install dependencies
```bash
cd .\royalfinanceAI\
pip install -r requirements.txt
```

### 4) Environment variables
Create a `.env` file next to `manage.py` at `royalfinanceAI\.env` if needed. Example:
```
KEY_OPENAI = ""
GEMINI_API_KEY=""
OPEN_AI_MODEL = ""
MAX_TOKEN_LIMIT = 

```

### 5) Run database migrations
```bash
python manage.py migrate
```

 create a superuser for the admin panel
```bash
python manage.py createsuperuser
```

### 6) Start the development server
```bash
python manage.py runserver
```
Open your browser at:  http://127.0.0.1:8000/



