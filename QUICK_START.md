# Hotel Pricing Agent - Quick Start Guide

## 🚀 Getting Started in 3 Easy Steps

### Step 1: Add Your Competitors 🏢

Navigate to the **Competitor Management** tab and add hotels you want to track:

```
Example Competitors:
┌──────────────────────────────────────┐
│ 🟢 Grand Hotel Roma                  │
│ 🔗 https://grandhotelroma.com        │
│                            [🗑️ Delete]│
├──────────────────────────────────────┤
│ 🟢 Hotel Luxury Palace               │
│ 🔗 https://luxurypalace.com          │
│                            [🗑️ Delete]│
├──────────────────────────────────────┤
│ 🔴 Budget Inn (Inactive)             │
│ 🔗 No website specified              │
│                            [🗑️ Delete]│
└──────────────────────────────────────┘
```

**Pro Tip**: Add at least 3-5 competitors for better pricing insights!

---

### Step 2: Configure Your Analysis 📊

Go to the **Pricing Dashboard** tab and set your parameters:

#### Date Range
- **Start Date**: Select when to begin analysis (e.g., Today)
- **End Date**: Select when to end analysis (e.g., 120 days from today)

#### Room Configuration
- **Room Type**: Choose occupancy level
  - 🛏️ Single (1 guest)
  - 🛏️🛏️ Double (2 guests) ← Most common
  - 🛏️🛏️🛏️ Triple (3 guests)
  - 🛏️🛏️🛏️🛏️ Family (4 guests)

#### Pricing Strategy
- **Weekend Uplift**: +10% (charge more on weekends)
- **Market Position**: -5% (undercut competitors by 5%)

---

### Step 3: Generate & Review 📈

Click **"🔄 Generate Pricing Recommendations"** and review:

```
Results Summary:
┌─────────────────────────────────────────────┐
│  Total Days: 120                            │
│  Avg. Recommended Rate: €145.50            │
│  Avg. Current Rate: €140.00                │
│  Avg. Change: +3.9%                        │
└─────────────────────────────────────────────┘

Detailed Recommendations:
┌────────────┬────────┬─────────────┬──────────────────┬──────────────────┬──────────┬───────────┐
│ Date       │ Day    │ Current     │ Recommended      │ Lowest Comp.     │ Change   │ Change %  │
├────────────┼────────┼─────────────┼──────────────────┼──────────────────┼──────────┼───────────┤
│ 2025-11-25 │ Tuesday│ €140.00     │ €142.50         │ €150.00          │ +2.50€   │ +1.8%     │
│ 2025-11-26 │ Wed    │ €140.00     │ €143.00         │ €152.00          │ +3.00€   │ +2.1%     │
│ 2025-11-27 │ Thu    │ €140.00     │ €144.00         │ €155.00          │ +4.00€   │ +2.9%     │
│ 2025-11-28 │ Friday │ €160.00     │ €165.00         │ €175.00          │ +5.00€   │ +3.1%     │
│ 2025-11-29 │ Saturday│ €180.00    │ €192.50         │ €205.00          │ +12.50€  │ +6.9%     │
│ 2025-11-30 │ Sunday │ €180.00     │ €187.00         │ €198.00          │ +7.00€   │ +3.9%     │
└────────────┴────────┴─────────────┴──────────────────┴──────────────────┴──────────┴───────────┘
```

---

## 🎯 Understanding Your Options

### Room Type / Occupancy

Different room types attract different rates:

| Type | Occupancy | Best For | Typical Use |
|------|-----------|----------|-------------|
| Single | 1 guest | Business travelers | 15% of bookings |
| **Double** | 2 guests | Couples, standard rooms | **60% of bookings** |
| Triple | 3 guests | Small families | 20% of bookings |
| Family | 4 guests | Larger families | 5% of bookings |

💡 **Tip**: Start with Double (2 guests) as it's the most common room type!

---

### Weekend Uplift

Charge more during high-demand periods:

- **0%**: No weekend pricing difference
- **+10%**: Standard weekend premium (recommended)
- **+20%**: High-demand markets (city centers, tourist areas)
- **+5%**: Lower weekend demand (business hotels)

**Example**: If base rate is €100
- Weekday: €100
- Weekend with +10% uplift: €110

---

### Market Position

Control how you price against competitors:

| Setting | Strategy | When to Use |
|---------|----------|-------------|
| **-10%** | Aggressive undercut | Low occupancy, need to fill rooms |
| **-5%** | Competitive pricing | Standard market competition |
| **0%** | Match competitors | Balanced approach |
| **+5%** | Premium positioning | High-quality property, strong brand |
| **+10%** | Luxury pricing | Unique property, limited competition |

---

## ⚙️ Advanced Tips

### 1. Dynamic Pricing Strategy

Adjust your market position based on occupancy:
- **< 40% occupancy**: Use -10% to -15% (attract bookings)
- **40-70% occupancy**: Use -5% to 0% (balanced)
- **> 70% occupancy**: Use 0% to +10% (maximize revenue)

### 2. Seasonal Adjustments

Modify weekend uplift by season:
- **High Season**: +15% to +25%
- **Shoulder Season**: +10%
- **Low Season**: +5% or even 0%

### 3. Regular Reviews

- **Daily**: Check upcoming weekend rates
- **Weekly**: Review next 30 days
- **Monthly**: Analyze 90-120 day horizon

### 4. Competitor Management

- Review competitor list monthly
- Remove closed/irrelevant hotels
- Add new competitors in your market
- Keep websites updated for quick checks

---

## 📤 Pushing Rates to Your System

### Before You Push:

1. ✅ Review all recommended rates carefully
2. ✅ Check for unusual spikes or drops
3. ✅ Verify weekend rates make sense
4. ✅ Ensure rates are within min/max limits

### Safety Features:

- **DRY_RUN Mode**: Test without making changes (default)
- **Rate Limits**: System prevents rates below minimum or above maximum
- **Max Change %**: Prevents dramatic rate swings (default: ±10%)

### To Go Live:

1. Set `DRY_RUN=false` in your `.env` file
2. Generate recommendations
3. Review carefully
4. Click **"📤 Push to Simple Booking"**
5. Confirm success message

---

## 🆘 Common Questions

### Q: How often should I generate recommendations?
**A**: Daily is ideal, but at least 2-3 times per week for best results.

### Q: Can I have different strategies for different room types?
**A**: Yes! Run the analysis separately for each occupancy level (Single, Double, Triple, Family).

### Q: What if I don't have competitor websites?
**A**: Websites are optional. The system will still track rates, but having URLs makes manual verification easier.

### Q: Why aren't my rates pushing?
**A**: Check that `DRY_RUN=false` in your `.env` file and verify your Simple Booking credentials are correct.

### Q: Can I override individual dates?
**A**: Currently, you can review recommendations and choose not to push them. For individual date changes, use your booking system directly.

---

## 🎓 Best Practices Checklist

- [ ] Add at least 3-5 direct competitors
- [ ] Include competitor websites for easy reference
- [ ] Start with Double (2 guests) occupancy
- [ ] Use +10% weekend uplift as baseline
- [ ] Set market position between -5% and +5% initially
- [ ] Test with DRY_RUN=true first
- [ ] Review recommendations before pushing
- [ ] Run analysis at least 3x per week
- [ ] Adjust strategy based on actual occupancy
- [ ] Monitor results and fine-tune parameters

---

## 📞 Need Help?

If you encounter issues:
1. Check the **Settings** tab for current configuration
2. Verify backend is running (http://localhost:8000/health)
3. Review error messages in the UI
4. Check backend logs for detailed errors

---

**Happy Pricing! 🎉**

Remember: The goal is to maximize revenue while maintaining competitive rates. Start conservative and adjust based on results.
