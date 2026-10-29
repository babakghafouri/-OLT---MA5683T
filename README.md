# Huawei MA5683T Operator Panel

پنل فارسی اپراتور Huawei MA5683T، شامل Inventory، Resources، Uplink، وضعیت فن/دما و ثبت ONT.

## Build Windows EXE

1. فایل `OLT-MA5683T-Traffic-Live.zip` را از مکالمه ChatGPT دانلود کنید.
2. آن را در ریشه همین مخزن با مسیر دقیق `OLT-MA5683T-Traffic-Live.zip` بارگذاری و Commit کنید.
3. با push به شاخه `main`، Workflow ساخت ویندوز به‌صورت خودکار اجرا می‌شود. همچنین می‌توانید از Actions آن را دستی اجرا کنید.
4. پس از موفقیت، از Artifact با نام `OLT-MA5683T-Panel-Windows` فایل اجرایی `OLT-MA5683T-Panel.exe` را دریافت کنید.

## Live Interface Traffic

نسخه Traffic Live شامل تب «ترافیک زنده Interface» برای چهار پورت GE شناخته‌شده روی کارت‌های H801GICF در Slot 8 و 9 است:
- `0/8/0`
- `0/8/1`
- `0/9/0`
- `0/9/1`

داده با polling فقط‌خواندنی CLI از مسیر `interface giu 0/<slot>` و دستور `display port traffic <port>` جمع‌آوری می‌شود. نرخ Upstream/Downstream و نمودار تاریخچه نمایش داده می‌شوند. این قابلیت streaming telemetry نیست و باید با خروجی واقعی CLI همین دستگاه تأیید شود.

## Security

- از SSH به‌جای Telnet استفاده کنید، اگر OLT پشتیبانی می‌کند.
- هرگز رمز عبور یا IP مدیریت واقعی را داخل مخزن Commit نکنید.
- برنامه به‌صورت پیش‌فرض روی `127.0.0.1:8080` اجرا می‌شود.
- موفقیت Build به‌تنهایی، صحت همه دستورات روی OLT واقعی را تضمین نمی‌کند.
