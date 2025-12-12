# Hotel Pricing Agent - Organization Setup Guide

## For IT Admin: Initial Setup

### 1. Deploy to Shared Location

Copy the entire `pricing_agent` folder to a shared network drive:
```
\\your-server\shared\HotelPricingAgent\
```

### 2. One-Time Setup Script for Each User

Create `setup_user.bat` in the shared folder:

```batch
@echo off
echo Installing Hotel Pricing Agent for %USERNAME%...

REM Install Python if not present
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed!
    echo Please install Python 3.8 or higher from python.org
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Setup complete for %USERNAME%!
echo.
echo Creating desktop shortcut...

REM Create desktop shortcut
set SCRIPT_DIR=%~dp0
set SHORTCUT="%USERPROFILE%\Desktop\Hotel Pricing Agent.lnk"
powershell "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%SCRIPT_DIR%launch.bat'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.IconLocation = 'shell32.dll,21'; $s.Save()"

echo.
echo Desktop shortcut created!
echo You can now launch the app from your desktop.
pause
```

### 3. Create Launcher for Users

Create `launch.bat` in the shared folder:

```batch
@echo off
title Hotel Pricing Agent Launcher

echo ========================================
echo   Hotel Pricing Agent
echo   Starting application...
echo ========================================
echo.

REM Kill any existing instances
taskkill /F /IM python.exe /T >nul 2>&1
timeout /t 1 /nobreak >nul

REM Get the directory where this script is located
set APP_DIR=%~dp0
cd /d "%APP_DIR%"

echo Starting Backend API...
start "Pricing Agent Backend" /MIN cmd /c "cd /d "%APP_DIR%backend" && python -m uvicorn app.main:app --reload --port 8000"

timeout /t 5 /nobreak >nul

echo Starting User Interface...
start "Pricing Agent UI" cmd /c "cd /d "%APP_DIR%" && streamlit run ui/streamlit_app.py --server.port 8501 && pause"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Application Started!
echo ========================================
echo.
echo Opening browser to http://localhost:8501
echo.
echo IMPORTANT: Do not close the terminal windows!
echo Close this window only after you finish using the app.
echo.

start http://localhost:8501

pause
```

---

## Option 2: Central Server Deployment (Recommended for Teams)

Deploy as a single server that everyone accesses via browser.

### Setup:

1. **Install on a Windows Server:**
```batch
cd C:\inetpub\HotelPricingAgent
pip install -r requirements.txt
```

2. **Create Windows Service for Backend:**

Create `install_backend_service.bat`:
```batch
@echo off
nssm install PricingAgentBackend "C:\Path\To\Python\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8000"
nssm set PricingAgentBackend AppDirectory "C:\inetpub\HotelPricingAgent\backend"
nssm set PricingAgentBackend Start SERVICE_AUTO_START
nssm start PricingAgentBackend
```

3. **Create Windows Service for Streamlit:**

Create `install_ui_service.bat`:
```batch
@echo off
nssm install PricingAgentUI "C:\Path\To\Python\Scripts\streamlit.exe" "run ui/streamlit_app.py --server.port 8501 --server.address 0.0.0.0"
nssm set PricingAgentUI AppDirectory "C:\inetpub\HotelPricingAgent"
nssm set PricingAgentUI Start SERVICE_AUTO_START
nssm start PricingAgentUI
```

4. **Update API URL in streamlit_app.py:**
```python
API_BASE_URL = os.getenv("API_BASE_URL", "http://your-server:8000")
```

**Users access via:** `http://your-server:8501`

---

## Option 3: Docker Container (Most Professional)

Package everything in Docker for easy deployment.

### Create Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose ports
EXPOSE 8000 8501

# Create startup script
RUN echo '#!/bin/bash\n\
cd /app/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 &\n\
cd /app && streamlit run ui/streamlit_app.py --server.port 8501 --server.address 0.0.0.0\n\
' > /app/start.sh && chmod +x /app/start.sh

CMD ["/app/start.sh"]
```

### Create docker-compose.yml:

```yaml
version: '3.8'
services:
  pricing-agent:
    build: .
    ports:
      - "8000:8000"
      - "8501:8501"
    volumes:
      - ./config:/app/config
      - ./pricing_agent.db:/app/pricing_agent.db
    environment:
      - LIGHTHOUSE_API_KEY=${LIGHTHOUSE_API_KEY}
      - SB_PROPERTY_ID=${SB_PROPERTY_ID}
    restart: unless-stopped
```

**Deploy:** `docker-compose up -d`

---

## Option 4: Cloud Deployment (Azure/AWS)

Deploy to Azure App Service or AWS EC2 for remote access.

### For Azure:

1. Create Azure App Service
2. Deploy backend as one app service
3. Deploy Streamlit UI as another app service
4. Use Azure SQL Database instead of SQLite

### For AWS:

1. Launch EC2 instance
2. Install Docker
3. Deploy using docker-compose
4. Use RDS for database

---

## Recommended Approach Based on Team Size:

| Team Size | Recommendation |
|-----------|----------------|
| 2-5 users | **Option 1**: Shared network drive |
| 5-20 users | **Option 2**: Central Windows Server |
| 20+ users | **Option 3**: Docker on server or **Option 4**: Cloud |

---

## User Access Control

### Add Authentication to Streamlit:

Install: `pip install streamlit-authenticator`

Update `streamlit_app.py`:

```python
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# Load user credentials
with open('config/users.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

name, authentication_status, username = authenticator.login('Login', 'main')

if authentication_status:
    authenticator.logout('Logout', 'main')
    st.write(f'Welcome *{name}*')
    # Your existing app code here
elif authentication_status == False:
    st.error('Username/Password is incorrect')
elif authentication_status == None:
    st.warning('Please enter your username and password')
```

Create `config/users.yaml`:
```yaml
credentials:
  usernames:
    jsmith:
      name: John Smith
      password: $2b$12$... # hashed password
    mjones:
      name: Mary Jones
      password: $2b$12$... # hashed password
cookie:
  name: pricing_agent_cookie
  key: random_signature_key
  expiry_days: 30
```

---

## Training Materials

Create quick reference card for users:

**HOTEL PRICING AGENT - Quick Reference**

1. **Launch App**: Double-click desktop shortcut
2. **Wait**: 10 seconds for services to start
3. **Browser Opens**: Automatically to http://localhost:8501
4. **Add Competitors**: Go to "Competitor Management" tab
5. **Generate Pricing**: Select dates and room type, click "Generate"
6. **Review**: Check recommendations before pushing
7. **Push Rates**: Click "Push to Simple Booking" when ready
8. **Close**: Close both terminal windows when done

**Support**: Contact IT Helpdesk or email pricing-support@company.com

---

## Maintenance & Updates

**For Admins:**

1. **Update Application:**
```batch
cd \\server\shared\HotelPricingAgent
git pull  # if using git
# Or copy new files
```

2. **Update Dependencies:**
```batch
pip install -r requirements.txt --upgrade
```

3. **Backup Database:**
```batch
copy pricing_agent.db pricing_agent.db.backup
```

4. **View Logs:**
- Backend logs: Check backend terminal
- UI logs: Check Streamlit terminal
- Set up logging to files for production

---

Would you like me to implement any of these options? I can help you set up the one that best fits your organization's infrastructure!
