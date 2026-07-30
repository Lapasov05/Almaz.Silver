"""Demo bilim bazasi (knowledge_base) — AI grounding uchun realistik test yozuvlari.

Mijozlar ko'p beradigan savollar (kumush parvarishi, o'lcham, yetkazish, to'lov, kafolat, qadoq...).
Guardrailga mos: DOIM Kumush 925 + rodiy / serkon toshi; olmos/oltin YO'Q.

IDEMPOTENT: title bo'yicha mavjud yozuv o'tkazib yuboriladi (6 ta default seed bilan to'qnashmaydi).

Ishga tushirish:
    docker compose exec -T api python -m app.demo_knowledge
"""
import asyncio

import app.core.models_registry  # noqa: F401 — barcha model
from sqlalchemy import select

from app.core.database import SessionLocal
from app.modules.ai.models import KnowledgeBase

# (type, title, content) — type: faq | policy | delivery | payment | company | guarantee
DEMO_KNOWLEDGE: list[tuple[str, str, str]] = [
    ("faq", "Kumush qorayib qoladimi",
     "Bizning mahsulotlar Kumush 925 proba ustiga rodiy qoplama bilan ishlangan. Rodiy qatlami "
     "kumushni oksidlanishdan himoya qiladi, shuning uchun oddiy kumushga qaraganda ancha uzoq "
     "yaltirab turadi va tez qoraymaydi. To'g'ri parvarishda uzoq yillar chiройли qoladi."),
    ("faq", "Taqinchoqni qanday parvarish qilaman",
     "Suv, atir, krem va tozalash vositalaridan saqlang. Cho'milish, sport yoki uy yumushlaridan "
     "oldin yechib qo'ying. Yumshoq quruq mato bilan arting. Alohida qutida, boshqa buyumlardan "
     "ajratib saqlang — shunda rodiy qoplama uzoqroq turadi."),
    ("faq", "Allergiya bo'lishi mumkinmi",
     "Kumush 925 + rodiy qoplama teriga yumshoq, ko'pchilikda allergiya chaqirmaydi (rodiy "
     "gipoallergen metall). Ammo o'ta sezgir teri bo'lsa, individual holat bo'lishi mumkin."),
    ("faq", "Serkon toshi nima",
     "Serkon (tsirkon, CZ) — yorqin, tиниq va chiройли sun'iy tosh. U yorug'likda go'zal "
     "tovlanadi va mahsulotga hashamatli ko'rinish beradi. Barcha toshlarimiz serkon."),
    ("faq", "O'lchamni qanday bilaman",
     "Uzuk o'lchamini bilish uchun: mavjud uzukchangiz ichki diametrini o'lchang yoki barmog'ingizni "
     "ip/qog'oz tasma bilan o'rab, uzunligini o'lchang. Bilmasangiz — o'rta o'lcham (18) tavsiya "
     "qilamiz, keyin kerak bo'lsa zargar moslab beradi."),
    ("faq", "Sovg'aga olsam qanday qadoqlaysiz",
     "Har bir buyurtma chiройли qadoqda beriladi. Qo'shimcha rangli sovg'a qutisini ham tanlashingiz "
     "mumkin (ba'zi ranglar tekin, ba'zilari arzon qo'shimcha narxda). Sovg'abop ko'rinish kafolatlanadi."),
    ("faq", "Uzukka ism yozdirsa bo'ladimi",
     "Ha, ba'zi uzuklarga ism yoki qisqa yozuv (gravyurka) qilib beramiz — bu buyurtmani "
     "shaxsiy va esda qolarli qiladi. Narxi va imkoniyati mahsulotga qarab; operator/AI aniq aytadi."),
    ("delivery", "Yetkazish qancha vaqt oladi",
     "Toshkent bo'ylab odatda 1–2 ish kuni. Viloyatlarga BTS pochta orqali 2–4 ish kunida yetkaziladi. "
     "To'lov tasdiqlangach buyurtma tayyorlanadi va jo'natiladi."),
    ("delivery", "Viloyatga yetkazasizmi",
     "Ha, O'zbekiston bo'ylab yetkazamiz. Toshkent — 50 000 so'm, viloyatlar (BTS orqali) — 30 000 so'm "
     "(qat'iy narx). Viloyatda eng yaqin BTS filialini tanlaysiz."),
    ("payment", "Naqd yoki yetkazishda to'lasa bo'ladimi",
     "Yo'q, to'lov faqat oldindan (prepaid) — kartaga. Bu buyurtmani kafolatlaydi. Kartaga to'lab, "
     "chek rasmini va karta egasi ism-familiyasini yuborasiz; tasdiqlangach buyurtma jo'natiladi."),
    ("payment", "To'lovni qanday qilaman",
     "Biz beradigan asosiy kartaga to'laysiz. So'ng to'lov chekining rasmini (skrinshot) va to'lovchi "
     "ism-familiyasini yuborasiz. Operator tekshirib tasdiqlaydi — shundan keyin buyurtma tayyorlanadi."),
    ("guarantee", "Kafolat muddati qancha",
     "Mahsulotlarga kafolat beriladi (odatda 12 oy): rodiy qoplama va zavod nuqsonlariga. Aniq muddat "
     "sozlamalarda belgilanadi. Kafolat noto'g'ri parvarish/mexanik shikastni qamramaydi."),
    ("policy", "Mahsulotni almashtirsa/qaytarsa bo'ladimi",
     "O'lcham to'g'ri kelmasa uzukni zargar moslab/almashtirib beradi (xizmat haqi bo'lishi mumkin). "
     "Qaytarish/almashtirish shartlari operator orqali hal qilinadi — buyum yangi va shikastsiz bo'lishi kerak."),
    ("policy", "Qanday metall va toshdan tayyorlanadi",
     "Barcha mahsulotlarimiz Kumush 925 proba + rodiy qoplamadan, toshlari serkon (tsirkon). "
     "Faqat shu material bilan ishlaymiz — bu sifat va hamyonbop narx muvozanatini beradi."),
    ("company", "Qanday buyurtma beraman",
     "Yoqqan mahsulotni ayting (yoki Instagram post/story linkini yuboring). AI/operator mavjudligini, "
     "narx va o'lchamni aniqlaydi, so'ng manzil va to'lovni rasmiylashtiradi. Hammasi shu chatда."),
    ("company", "Ish vaqti va bog'lanish",
     "Buyurtmalarni Instagram va Telegram orqali qabul qilamiz — xabar yozing, AI sotuvchimiz darhol "
     "yordam beradi. Murakkab holatlarda jonli operatorga ulaymiz."),
]


async def main() -> None:
    async with SessionLocal() as db:
        existing = {t for (t,) in (await db.execute(select(KnowledgeBase.title))).all()}
        added = 0
        for kb_type, title, content in DEMO_KNOWLEDGE:
            if title in existing:
                continue
            db.add(KnowledgeBase(type=kb_type, title=title, content=content))
            added += 1
        await db.commit()
        total = len((await db.execute(select(KnowledgeBase.id))).all())
    print(f"✅ Bilim bazasi: {added} yangi yozuv qo'shildi (o'tkazib yuborilgan mavjud: {len(DEMO_KNOWLEDGE) - added}).")
    print(f"   Jami knowledge_base yozuvlari: {total}.")


if __name__ == "__main__":
    asyncio.run(main())
