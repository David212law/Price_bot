# PRICE_BOT — گزارش وضعیت نهایی (2026-11-06)

## خلاصه اجرایی
۱۶ جلسه کار. پروژه متوقف تا migration به hedged paper bots.

## آنچه PROVEN است:
- **D-543**: رفع SR inflation (√tpy). Keltner/RSI/MACD SR معتبر.
- **زیرساخت**: pipeline_contract.py + health_check.py
- **M31 funding edge وجود دارد** (تئوریک ۸-۱۶، hedged واقعی ۱۱.۴۱)

## آنچه PROMISING است:
- **D-552**: هج دلتا-نوترال M31. HL SR ۰.۴۷→۱۱.۴۱، DD ۶۸٪→۰.۲۱٪. فقط در بازه صعودی (2024-10 to 2026-10). بحران تست نشده.
- **D-551**: Hybrid_v3_Wallex. ۴/۶ بهتر از Buy&Hold. Paper متوقف.
- **D-553**: Researcher v3. Coverage ۹/۱۶. نیاز به کاهش ۸→۳ regime.

## آنچه بحرانی است:
- **همه ۱۰ ربات Paper UNHEDGED** — فقط funding، نه price P&L
- Paper equity = FAKE. DD واقعی در بحران: ۶۸٪.
- همه ورک‌فلوها متوقف
- Migration: ۲-۳ هفته (MIGRATION_PLAN.md)

## آنچه REJECTED است (۸ framework):
MLP (D-528)، Combo ۹۰/۱۰، Combo ۹۵/۵، Rule price-based، Rule funding-based، D-550 v1، D-550 v2.

## قوانین برای AI جدید:
۱. AI کد اجرا نمی‌کند (D-347)
۲. قبل از تغییر، فایل بخوان
۳. هیچ framework جدید بدون ۱۶ تست + crisis
۴. Fee واقعی در همه تست‌ها
۵. Baselines (M31، Keltner) دست‌نخورده
۶. Blacklist (M31 variants) هرگز نادیده نشود
۷. هیچ بهینه‌سازی روی data (۸ تلاش شکست خورد)
۸. اگر شک داری، PIPELINE_STATE.md بخوان

## گام‌های بعدی:
- هفته ۱: کد hedged (۵-۷ روز)
- هفته ۲: تست ۷۰/۳۰ (۳-۴ روز)
- هفته ۳: فعال‌سازی ۶ ربات (۳-۴ روز)
- سپس Paper test ۶ ماه
- Live Gate 2027-05-02 (در خطر، ممکن است تمدید شود)
