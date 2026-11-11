# نقشه راه D-554 — Migration به Hedged Paper Bots

**زمان:** ۲-۳ هفته | **اولویت:** بحرانی

## مشکل
همه ۱۰ ربات Paper فقط funding را simulate می‌کنند. DD واقعی در بحران: ۶۸٪. Paper نشان می‌دهد DD=۰.۱٪ = FAKE.

## هفته ۱ — کد (۵-۷ روز)

برای هر allocator (۱۰ فایل):
۱. اضافه کردن `spot_holdings` + `perp_short` به state
۲. تغییر `earned` به:
   funding_income + spot_pnl + perp_pnl
۳. اضافه کردن rebalance (هر ۳۰ روز)
۴. اضافه کردن fee: ۰.۰۳۵٪ HL، ۰.۶٪ Wallex

## هفته ۲ — تست (۳-۴ روز)
- ۷۰/۳۰ OOS روی داده تاریخی
- هدف: HL SR≈۱۱.۴۱، DD≈۰.۲۱٪ | Aster SR≈۵.۱۳، DD≈۰.۳۹٪

## هفته ۳ — فعال‌سازی (۳-۴ روز)
کاهش ۱۲ ربات به ۶ (ببینید PIPELINE_STATE.md)

## معیار موفقیت
- Paper SR در ۱۰٪ backtest SR
- Paper DD در ۲۰٪ backtest DD
- بدون FAKE equity

## Rollback
- .yml.paused → .yml
- git revert allocator changes
