# Module 5 – Giỏ hàng & Tách đơn

Node.js + Express + SQLite (better-sqlite3), giao diện HTML thuần.

## Chạy
```bash
npm install
npm start          # http://localhost:3000
npm run seed       # reset DB về dữ liệu mẫu
```

## Cấu trúc
| File | Vai trò |
|---|---|
| `db.js` | Schema, index, trigger append-only cho timeline, dữ liệu mẫu |
| `cartService.js` | Chọn/bỏ chọn, tính tiền & ship tách theo shop |
| `orderService.js` | Checkout tách đơn (1 transaction), đổi trạng thái, timeline |
| `orderStatus.js` | Bảng chuyển trạng thái hợp lệ + quyền theo actor |
| `server.js` | REST API |
| `public/index.html` | UI giỏ hàng + danh sách đơn + timeline |

## API
`GET /api/cart` · `POST /api/cart/items` · `PATCH /api/cart/items/:id` · `DELETE /api/cart/items/:id`
`PATCH /api/cart/select` · `GET /api/cart/summary` · `POST /api/checkout`
`GET /api/orders` · `GET /api/orders/:id` · `PATCH /api/orders/:id/status`
