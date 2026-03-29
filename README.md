# CP Wiki Django

Trang wiki lập trình thi đấu viết bằng Django, hỗ trợ quản lý người dùng, CRUD bài viết, bình luận, tìm kiếm, phân quyền theo nhóm và chỉnh sửa nội dung bằng Markdown với Martor.

## Tính năng chính

- Đăng ký, đăng nhập, cập nhật hồ sơ và đổi mật khẩu bằng Django User model.
- Tạo, sửa, xóa và xem bài viết wiki với tiêu đề, nội dung, ngày tạo và tác giả.
- Người dùng thường chỉ bình luận dưới bài viết; nhóm `admin`, `editor`, `contributor` có thể đăng bài.
- Soạn thảo nội dung bài viết bằng Martor Markdown editor với live preview.
- Hỗ trợ KaTeX cho công thức như `$n$` và `$$\sum_{i=1}^{n} i$$`.
- Giao diện được tổ chức theo SCSS và build sang CSS bằng Sass.
- Font base của giao diện dùng file `Lucida Grande.ttf` local trong `static/fonts/`.
- Trang hồ sơ riêng với biểu đồ Chart.js, heatmap contribution và recent activity.
- Bài viết có thể bật hoặc tắt bình luận ngay trong form tạo/sửa bài.
- Phân loại bài viết theo danh mục như thuật toán, cấu trúc dữ liệu, bài toán thi đấu.
- Tìm kiếm theo tiêu đề hoặc nội dung bằng truy vấn Django ORM.
- Phân quyền theo nhóm `admin` và `user`.
- Trang hướng dẫn sử dụng cho người dùng lần đầu truy cập.
- Bổ sung tính năng tự động tạo `slug` duy nhất khi tạo hoặc cập nhật bài viết với các tiêu đề trùng nhau.
- Sửa lỗi: khi người dùng nhập `slug` trùng lịch bài viết hiện có, hệ thống sẽ ghi đè bằng slug title đã chuẩn hoá và giữ tính duy nhất.
- Bổ sung metadata bài viết như thời gian đọc ước tính, lọc theo tác giả và sắp xếp theo điểm vote.
- Form đăng nhập được style đồng bộ hơn để người mới vào dự án có trải nghiệm nhất quán.

## Yêu cầu

- Python 3.12+
- Node.js 20+ và npm
- SQLite3 mặc định đi kèm Python là đủ để chạy local

## Cài đặt nhanh

1. Tạo virtual environment và cài dependency Python:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2. Cài dependency frontend:

```bash
npm install
```

3. Tạo file môi trường local:

```bash
cp .env.example .env
```

4. Build CSS từ SCSS:

```bash
npm run build:css
```

5. Chạy migrate:

```bash
python manage.py migrate
```

6. Tạo tài khoản admin:

```bash
python manage.py createsuperuser
```

7. Khởi động server:

```bash
python manage.py runserver
```

Sau khi chạy, mở `http://127.0.0.1:8000/`.

## Cấu hình môi trường

Project hiện đọc biến môi trường từ file `.env` nếu file này tồn tại.

Các biến quan trọng:

- `DJANGO_SECRET_KEY`: secret key cho Django.
- `DJANGO_DEBUG`: bật/tắt debug (`True` hoặc `False`).
- `DJANGO_ALLOWED_HOSTS`: danh sách host, phân tách bằng dấu phẩy.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: danh sách origin tin cậy cho CSRF.
- `DJANGO_DB_PATH`: đường dẫn file SQLite.
- `DJANGO_LANGUAGE_CODE`: mặc định là `vi`.
- `DJANGO_TIME_ZONE`: mặc định là `Asia/Ho_Chi_Minh`.
- `SITE_URL`: domain local hoặc production để tham chiếu khi cần.

Ví dụ local:

```env
DJANGO_SECRET_KEY=dev-only-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000
```

## Dữ liệu demo

```bash
python manage.py loaddata wiki/fixtures/demo_fixture.json
```

- Tài khoản mẫu trong fixture dùng mật khẩu `demo12345`.
- Fixture tạo sẵn category, article, comment và profile để bạn xem nhanh giao diện.
- Nếu muốn thử quyền đăng bài, hãy gán thêm role `editor` hoặc `contributor` cho `demo_editor` trong Django admin.

## Thiết lập quyền

- Sau khi migrate, hệ thống tự tạo 4 nhóm mặc định: `admin`, `editor`, `contributor`, `user`.
- `user` có thể xem bài viết và gửi bình luận.
- `editor` và `contributor` có thể đăng bài; `admin` có thể quản lý toàn bộ bài viết, danh mục và bình luận.
- Superuser có thể gán người dùng vào nhóm trong Django admin.

## Frontend workflow

```bash
npm run build:css
npm run watch:css
./scripts/build_styles.sh
```

- Nguồn SCSS nằm tại `static/scss/site.scss`.
- File build đầu ra là `static/css/site.css`.
- Script shell build nhanh nằm tại `scripts/build_styles.sh`.

## Chạy kiểm tra

```bash
python manage.py check
python manage.py test
```

## Luồng sử dụng cơ bản

1. Đăng ký tài khoản mới.
2. Đăng nhập và cập nhật thông tin cá nhân ở trang `Tài khoản`.
3. Vào `Bài viết` để tạo ghi chú mới.
4. Dùng ô tìm kiếm để tra cứu theo từ khóa, tác giả, danh mục hoặc điểm vote.
5. Admin truy cập `Danh mục` để tạo hoặc chỉnh sửa các nhóm chủ đề.
