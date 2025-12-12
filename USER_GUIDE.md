# Hotel Pricing Agent - User Guide 🏨

An intelligent hotel pricing recommendation system that analyzes competitor rates and generates optimal pricing strategies for your property.

## Features

### 📊 Pricing Dashboard
- **Flexible Date Range Selection**: Choose custom start and end dates for pricing analysis
- **Room Type Configuration**: Select occupancy levels (Single, Double, Triple, Family rooms)
- **Real-time Competitor Analysis**: Fetch and analyze competitor rates from multiple sources
- **Dynamic Pricing Parameters**: Adjust weekend uplift and market positioning on the fly
- **Visual Metrics**: View average rates, changes, and trends at a glance
- **Detailed Recommendations**: See day-by-day pricing suggestions with competitor comparisons

### 🏢 Competitor Management
- **Easy Competitor Addition**: Add competitor hotels with names and websites
- **Website Tracking**: Keep track of competitor websites for quick reference
- **Active/Inactive Status**: Enable or disable competitor tracking as needed
- **Quick Management**: View, edit, and delete competitors through an intuitive interface

### ⚙️ Settings & Configuration
- **Centralized Settings**: View all pricing parameters in one place
- **Rate Limits**: Monitor minimum and maximum rate boundaries
- **Default Parameters**: Check default horizon, occupancy, and pricing strategy settings

## Getting Started

### Running the Application

#### 1. Start the Backend API:
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

#### 2. Launch the Streamlit UI:
```bash
streamlit run ui/streamlit_app.py
```

The application will open in your default web browser at `http://localhost:8501`

## User Guide

### Managing Competitors

1. **Navigate to the "Competitor Management" tab**
2. **Add a New Competitor:**
   - Click "➕ Add New Competitor"
   - Enter the hotel name (required)
   - Add the website URL (optional but recommended)
   - Set active status
   - Click "Add Competitor"

3. **View Competitors:**
   - All competitors are displayed with their status (🟢 Active / 🔴 Inactive)
   - Click the website link to visit competitor sites
   - Use the Delete button to remove competitors

### Generating Pricing Recommendations

1. **Navigate to the "Pricing Dashboard" tab**
2. **Select Date Range:**
   - Choose a start date (today or later)
   - Choose an end date (after the start date)
   
3. **Configure Room Settings:**
   - Select room type/occupancy:
     - Single (1 guest)
     - Double (2 guests) - default
     - Triple (3 guests)
     - Family (4 guests)
   
4. **Adjust Pricing Strategy:**
   - **Weekend Uplift (%)**: Percentage increase for weekend rates (e.g., 10% = €100 becomes €110 on weekends)
   - **Market Position (%)**: 
     - Negative values = undercut competitors (e.g., -5% = price 5% below lowest competitor)
     - Positive values = premium pricing (e.g., +10% = price 10% above lowest competitor)

5. **Generate Recommendations:**
   - Click "🔄 Generate Pricing Recommendations"
   - Wait for analysis to complete
   - Review the metrics and detailed recommendations

6. **Push to Booking System:**
   - Review the recommendations carefully
   - Click "📤 Push to Simple Booking" when ready
   - Note: Set `DRY_RUN=false` in `.env` to enable live updates

### Understanding the Results

The dashboard displays:
- **Total Days**: Number of days analyzed
- **Avg. Recommended Rate**: Your optimal average rate
- **Avg. Current Rate**: Your existing average rate
- **Avg. Change**: Percentage change from current to recommended

The detailed table shows:
- **Date**: The specific date
- **Day**: Day of the week
- **Current Rate**: Your existing rate
- **Recommended Rate**: AI-generated optimal rate
- **Lowest Competitor**: Lowest competitor rate found
- **Change**: Absolute and percentage change

## Configuration

### Environment Variables (`.env`)

```env
LIGHTHOUSE_PROPERTY_ID=your_property_id
LIGHTHOUSE_API_KEY=your_api_key
SB_PROPERTY_ID=your_simple_booking_property_id
SB_RATE_PLAN_ID=BAR
CURRENCY=EUR
DRY_RUN=true  # Set to false to enable live rate updates
API_BASE_URL=http://localhost:8000
```

### Settings File (`config/settings.yaml`)

```yaml
hotel:
  name: "My Hotel"
  currency: EUR
  property_id: ""
  rate_plan_id: "BAR"
  timezone: Europe/Rome

pricing:
  min_rate: 80.0          # Minimum allowed rate
  max_rate: 300.0         # Maximum allowed rate
  weekend_uplift: 10.0    # Default weekend uplift %
  undercut: 0.0           # Default market position
  lead_buckets:           # Advance booking discounts
    7: 0                  # 7 days advance: no discount
    21: -5                # 21 days advance: -5%
    60: -10               # 60 days advance: -10%
  max_change_pct: 0.10    # Maximum 10% change per run

run:
  horizon_days: 120       # Default analysis period
  occupancy: 2            # Default occupancy
```

## Tips for Best Results

1. **Keep Competitors Updated**: Regularly review and update your competitor list
2. **Add Website URLs**: Makes it easier to verify competitor information
3. **Monitor Market Position**: Adjust your undercut/markup based on occupancy levels
4. **Review Before Pushing**: Always review recommendations before pushing to live system
5. **Use DRY_RUN Mode**: Test with `DRY_RUN=true` before going live
6. **Regular Analysis**: Run pricing analysis daily or weekly for optimal results

## Troubleshooting

### Backend Not Connecting
- Ensure the backend API is running on port 8000
- Check `API_BASE_URL` in environment variables
- Verify firewall settings

### No Competitors Showing
- Check backend database connection
- Ensure competitors were added successfully
- Check browser console for errors

### Rate Push Failing
- Verify Simple Booking credentials
- Check `DRY_RUN` setting in `.env`
- Ensure rate plan ID is correct

## Room Type / Occupancy Guide

Different room types have different occupancies:
- **Single (1 guest)**: Solo travelers, business trips
- **Double (2 guests)**: Standard double rooms, most common
- **Triple (3 guests)**: Larger rooms, family rooms with 3 beds
- **Family (4 guests)**: Family suites, larger accommodations

The pricing agent will fetch competitor rates specifically for the selected occupancy level, ensuring accurate comparisons.

---

Made with ❤️ for hotel revenue management
