# cp wiki

cp wiki is a knowledge base platform designed for the competitive programming community supporting markdown articles category management discussions an interactive quiz system version history and a sub-mini online judge

## requirements

- python 3.10+
- nodejs 18+
- git

### 0 install prerequisites

**windows**
- [python 3.10+](https://www.python.org/downloads/windows/) (ensure "add python to path" is checked)
- [nodejs](https://nodejs.org/en/download/)
- [git](https://git-scm.com/download/win)

**linux (ubuntu)**
```bash
sudo apt update
sudo apt install -y python3 python3-venv nodejs npm git
```

**macos**
```bash
brew install python@3.10 node git
```

## installation guide

### 1 clone the repository
```bash
git clone https://github.com/tahoangphuc111/tht.git
cd tht
```

### 2 set up a virtual environment

**windows powershell**
```powershell
python -m venv venv
.\venv\Scripts\activate
```

**linux / macos terminal**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3 install dependencies

**linux (ubuntu/debian)**
```bash
sudo apt-get update
sudo apt-get install -y libcairo2-dev pkg-config
```

**python & node**
```bash
pip install -r requirements.txt
npm install
```

### 4 configuration
the system uses `config/local_settings.py` to manage environment specific settings

- create a file named `config/local_settings.py`
- example content for configuring your secret key and database
```python
# config/local_settings.py
SECRET_KEY = 'your-secret-key-goes-here'
DEBUG = True
ALLOWED_HOSTS = ['*']

# optional database override
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': 'path/to/your/db.sqlite3',
#     }
# }
```

### 5 initialize the database
```bash
python manage.py makemigrations
python manage.py migrate
```

### 6 create an admin account
```bash
python manage.py createsuperuser
```

## features

### sub-mini online judge
the platform includes a code runner service for executing and testing programming solutions

- supports multiple languages configured in services
- automatic testcase grading
- sandboxed execution for safety

### interactive quiz system
authors can attach quizzes to articles to test reader knowledge

- multiple choice questions
- instant grading and feedback
- quiz management dashboard for authors

### websocket integration
real time updates for voting and notifications using asgi

- ensure you run the server with an asgi compatible worker for full functionality
- real time vote broadcasting across connected clients

## ui development scss

source files are located in `static/scss` to compile them to css

**cross-platform (recommended)**
```bash
npm run build:css
```

**windows cmd/ps**
```powershell
.\scripts\build_styles.bat
```

<<<<<<< HEAD
All pull requests must pass the CI build tests before merging. Use the provided template for submission.

a
=======
**linux / macos terminal**
```bash
chmod +x scripts/build_styles.sh
./scripts/build_styles.sh
```

## running the application

### development server
```bash
python manage.py runserver
```

### asgi for websockets
for production or full websocket support use uvicorn or daphne
```bash
uvicorn config.asgi:application --port 8001
```

## production deployment
for production environments use the following setup with **nginx** and **uwsgi**

### 1 set up uwsgi
ensure uwsgi is installed (`pip install uwsgi`) and use the provided config:
```bash
uwsgi --ini deployment/uwsgi.ini
```

### 2 set up uvicorn (for websockets)
run the asgi server alongside uwsgi:
```bash
uvicorn config.asgi:application --port 8001 --workers 4
```

### 3 configure nginx
copy `deployment/nginx.conf` to your nginx `sites-available` folder and update the `<absolute-path-to-site>` and `<your-domain-or-ip>` placeholders
```bash
sudo cp deployment/nginx.conf /etc/nginx/sites-available/cp-wiki
sudo ln -s /etc/nginx/sites-available/cp-wiki /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

access the application at `http://your-domain-or-ip`

## contribution
all pull requests must pass automated ci tests please use the provided template when submitting your contributions
a 