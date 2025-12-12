# 🏨 Hotel Pricing Agent

An intelligent pricing recommendation system that analyzes competitor rates and generates optimal pricing strategies for hotels.

## ✨ Key Features

- 📊 **Smart Pricing Dashboard** - Visual analytics and recommendations
- 🏢 **Competitor Management** - Easy tracking of competitor hotels and rates
- 📅 **Flexible Date Selection** - Choose any date range for analysis
- 🛏️ **Room Type Selection** - Price different occupancies (Single/Double/Triple/Family)
- 📈 **Real-time Analytics** - See metrics and changes at a glance
- 🔒 **Safe Testing** - DRY_RUN mode to test before going live

## 🚀 Quick Start

### Option 1: One-Click Startup (Windows)

Double-click `start.bat` or run:
```powershell
.\start.ps1
```

### Option 2: Manual Startup

1. **Start Backend API:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

2. **Launch UI (in new terminal):**
```bash
streamlit run ui/streamlit_app.py
```

3. **Open your browser:**
   - UI: http://localhost:8501
   - API: http://localhost:8000

## 📖 Documentation

- **[Quick Start Guide](QUICK_START.md)** - Get up and running in 3 steps
- **[User Guide](USER_GUIDE.md)** - Comprehensive feature documentation
- **[Improvements](IMPROVEMENTS.md)** - What's new in this version

## 🎯 How It Works

1. **Add Competitors** - Track 3-5 competitor hotels in your market
2. **Select Dates** - Choose your analysis period (e.g., next 120 days)
3. **Choose Room Type** - Select occupancy level (Single/Double/Triple/Family)
4. **Set Strategy** - Configure weekend uplift and market positioning
5. **Generate** - Click to analyze and get recommendations
6. **Review** - Check the suggested rates and changes
7. **Push** - Send approved rates to your booking system

## 🛠️ Configuration

### Environment Variables (`.env`)
```env
LIGHTHOUSE_PROPERTY_ID=your_property_id
LIGHTHOUSE_API_KEY=your_api_key
SB_PROPERTY_ID=your_simple_booking_id
SB_RATE_PLAN_ID=BAR
CURRENCY=EUR
DRY_RUN=true  # Set to false for live updates
```

### Settings (`config/settings.yaml`)
```yaml
pricing:
  min_rate: 80.0          # Minimum rate
  max_rate: 300.0         # Maximum rate
  weekend_uplift: 10.0    # Weekend premium %
  undercut: 0.0           # Market position
  max_change_pct: 0.10    # Max change per run
```

## 📱 User Interface

### 📊 Pricing Dashboard
- Visual date range picker
- Room type selector (Single/Double/Triple/Family)
- Dynamic pricing parameters (weekend uplift, market position)
- Summary metrics (avg rates, changes)
- Detailed day-by-day recommendations
- One-click push to booking system

### 🏢 Competitor Management
- Add new competitors with names and websites
- View all tracked competitors
- Quick delete functionality
- Active/inactive status indicators
- Clickable website links

### ⚙️ Settings
- View current configuration
- Check rate limits
- Monitor default parameters
- See currency and property settings

## 💡 Tips for Best Results

- ✅ Add at least 3-5 direct competitors
- ✅ Include competitor websites for reference
- ✅ Start with Double (2 guests) - most common
- ✅ Use +10% weekend uplift as baseline
- ✅ Test with DRY_RUN=true first
- ✅ Run analysis 2-3 times per week
- ✅ Adjust strategy based on occupancy

## 🎓 Room Types Explained

| Type | Occupancy | Best For |
|------|-----------|----------|
| Single | 1 guest | Business travelers |
| **Double** | 2 guests | Standard rooms (most common) |
| Triple | 3 guests | Small families |
| Family | 4 guests | Larger families |

## 🔧 Troubleshooting

**Backend won't start?**
- Check if port 8000 is available
- Verify Python environment is activated
- Check API credentials in `.env`

**UI shows connection error?**
- Ensure backend is running
- Check `API_BASE_URL` in environment
- Verify http://localhost:8000/health works

**Can't push rates?**
- Set `DRY_RUN=false` in `.env`
- Verify Simple Booking credentials
- Check rate plan ID is correct

## 📦 Requirements

- Python 3.8+
- FastAPI
- Streamlit
- Access to Lighthouse API
- Access to Simple Booking API

## 🏗️ Project Structure

```
pricing_agent/
├── backend/              # FastAPI backend
│   └── app/
│       ├── api/         # API endpoints
│       ├── models/      # Data models
│       ├── services/    # Business logic
│       └── main.py      # App entry point
├── ui/                  # Streamlit frontend
│   └── streamlit_app.py
├── config/              # Configuration files
│   └── settings.yaml
├── agent/               # Pricing logic
├── clients/             # API clients
├── docs/                # Documentation
├── start.bat           # Windows startup script
├── start.ps1           # PowerShell startup script
└── requirements.txt    # Python dependencies
```

## 🔄 Version History

### v2.0 - Enhanced UI (Current)
- ✨ Tab-based interface with 3 sections
- ✨ Visual competitor management
- ✨ Flexible date range selection
- ✨ Named room type selection
- ✨ Improved metrics and analytics
- ✨ Better error handling
- ✨ Professional styling
- ✨ Comprehensive documentation

### v1.0 - Initial Release
- Basic pricing recommendations
- Fixed horizon configuration
- Simple table display

## 📄 License

[Add your license here]

## 🤝 Support

For questions or issues:
1. Check the documentation files
2. Review error messages in UI
3. Check backend logs
4. Verify API credentials

---

**Made with ❤️ for hotel revenue management**

Start maximizing your revenue today! 🚀
