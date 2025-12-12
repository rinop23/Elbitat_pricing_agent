# Hotel Pricing Agent - Installation Guide

## For Individual Users (No Shared Network)

### Prerequisites
- Windows 10/11
- Internet connection for initial setup
- Admin rights (for Python installation only)

---

## Installation Steps

### Step 1: Install Python (One-Time)

1. Download Python 3.11 from: https://www.python.org/downloads/
2. **IMPORTANT**: Check "Add Python to PATH" during installation
3. Click "Install Now"
4. Restart your computer

### Step 2: Install the Pricing Agent

1. Extract the `pricing_agent.zip` file to a location like:
   - `C:\HotelPricingAgent\`
   - Or your Desktop

2. Double-click **`INSTALL.bat`** in the extracted folder

3. Wait for installation to complete (2-3 minutes)

4. A desktop shortcut will be created

### Step 3: Configure Your Settings

1. Open the `config` folder
2. Edit `settings.yaml` with your hotel details
3. Create a `.env` file (copy from `.env.example`)
4. Add your API credentials:
   ```
   LIGHTHOUSE_PROPERTY_ID=your_property_id
   LIGHTHOUSE_API_KEY=your_api_key
   SB_PROPERTY_ID=your_simple_booking_id
   SB_RATE_PLAN_ID=BAR
   CURRENCY=EUR
   DRY_RUN=true
   ```

### Step 4: Launch the Application

- **Double-click** the desktop shortcut "Hotel Pricing Agent"
- Or run `launch.bat` from the application folder
- Browser will open automatically
- First launch takes ~10 seconds

---

## Daily Use

1. **Start**: Double-click desktop shortcut
2. **Use**: Browser opens to the application
3. **Stop**: Close both terminal windows when done

---

## Troubleshooting

### "Python not found"
- Reinstall Python and check "Add to PATH"
- Restart computer

### "Port already in use"
- Close any running Python processes
- Restart your computer

### "Module not found"
- Run `INSTALL.bat` again
- Or manually: Open terminal in app folder and run `pip install -r requirements.txt`

### Application won't start
- Check Windows Firewall isn't blocking ports 8000/8501
- Try running as Administrator

---

## Updating the Application

1. Download new version
2. Extract to same location (overwrite files)
3. Run `INSTALL.bat` again
4. Your data and settings are preserved

---

## Support

Contact: [Your IT Support Email]
Documentation: See README.md and USER_GUIDE.md
