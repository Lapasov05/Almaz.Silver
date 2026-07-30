# Ma'lumotni tozalash — `reset_data`

`user`/`role`/config/reference'dan tashqari **hamma ma'lumotni** o'chiradi. Demo/test ma'lumotni
tozalab, tizimni toza holatga qaytarish uchun (tizim ishlab turadi — login, sozlama, kanal kalitlari qoladi).

## Nima saqlanadi / nima o'chadi

| Saqlanadi (tegilmaydi) | O'chadi (bo'shatiladi) |
|---|---|
| **RBAC:** user, role, permission, role_permission, user_role | product, variant, product_media, category |
| **Config:** setting, payment_card, integration_config (IG/TG kalitlari) | box, box_media, combo_item |
| **Reference:** material, gender, stone | customer, conversation, message |
| `alembic_version` (migratsiya holati) | order, order_item, order_status_history |
| | delivery, checkout_token, customer_location, bts_branch |
| | payment, knowledge_base, audit_log, notification, integration_event |

> Ro'yxat **dinamik**: `PRESERVE` to'plamdan (`app/reset_data.py`) tashqari metadata'dagi har bir jadval
> o'chadi — kelajakda yangi jadval qo'shilsa, u ham avtomatik o'chirilishi kerak bo'lganlar qatoriga tushadi.

## Ishlatish

```bash
# 1) DRY-RUN — nima o'chishini (qator sonlari bilan) ko'rsatadi, HECH NARSA o'chirmaydi
make reset-data

# 2) HAQIQIY o'chirish — tasdiqlagach
make reset-data-confirm
```

Yoki to'g'ridan-to'g'ri:
```bash
docker compose exec -T api python -m app.reset_data                     # DRY-RUN
docker compose exec -T -e RESET_CONFIRM=yes api python -m app.reset_data # HAQIQIY
```

## Xavfsizlik
- **Default — DRY-RUN.** O'chirish faqat `RESET_CONFIRM=yes` (yoki `--yes`) bilan.
- Bitta `TRUNCATE ... RESTART IDENTITY CASCADE` — FK'lar avtomatik hal bo'ladi, ID ketma-ketligi 1'dan boshlanadi.
- Saqlanadigan jadvallar o'chiriladiganlarga **FK bilan bog'lanmagan**, shuning uchun CASCADE ularga tegmaydi (tekshirilgan).
- **Qaytarib bo'lmaydi.** Prod'da ishlatishdan oldin backup oling (`scripts/backup.sh`).
