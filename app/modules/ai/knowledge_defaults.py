"""Boshlang'ich knowledge base yozuvlari (TZ 7.6) — AI grounding uchun.

Seed vaqtida qo'shiladi (title bo'yicha mavjud bo'lmasa). Aniq shartlar egadan (TZ 19).
"""
DEFAULT_KNOWLEDGE: list[dict] = [
    {
        "type": "company",
        "title": "Brend haqida",
        "content": (
            "almazsilver — O'zbekiston bo'ylab ishlaydigan zargarlik do'koni. "
            "Barcha mahsulotlar Kumush 925 proba + rodiy qoplama, toshlar serkon (tsirkon). "
            "Assortiment: uzuk, braslet, sepochka (zanjir), komplekt."
        ),
    },
    {
        "type": "guarantee",
        "title": "Kafolat",
        "content": (
            "Mahsulotlarga sifat kafolati beriladi. Rodiy qoplama va serkon toshlar sifatli. "
            "Aniq kafolat shartlari (muddat/qamrov) sozlamalarda belgilanadi."
        ),
    },
    {
        "type": "delivery",
        "title": "Yetkazib berish",
        "content": (
            "Yetkazish narxi zona bo'yicha qat'iy (fixed): Toshkent — 50 000 so'm, "
            "viloyatlar (BTS) — 30 000 so'm. To'lovdan oldin qo'shiladi."
        ),
    },
    {
        "type": "payment",
        "title": "To'lov tartibi",
        "content": (
            "To'lov faqat oldindan (prepaid). Mijoz asosiy kartaga to'laydi, chek rasmini va "
            "karta egasi ism-familiyasini yuboradi. Tasdiqlangach buyurtma tayyorlanadi."
        ),
    },
    {
        "type": "policy",
        "title": "Material va tosh",
        "content": (
            "Material doim Kumush 925 + rodiy qoplama. Tosh doim serkon (serkon toshi). "
            "Bu — CZ/tsirkon; olmos yoki tabiiy tosh emas."
        ),
    },
    {
        "type": "instruction",
        "title": "O'lcham",
        "content": (
            "Uzuk o'lchami buyurtmada belgilanadi, hamma o'lcham bir xil narx. Sovg'a bo'lsa "
            "o'rta o'lcham tavsiya qilinadi yoki ip bilan o'lchash mumkin; kerak bo'lsa 1 kunda moslanadi."
        ),
    },
]
