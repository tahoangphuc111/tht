# CP Wiki 🚀

Lowkey là một cái wiki cho anh em chuyên thuật toán (Competitive Programming), highkey là project để lưu trick, snippet và thảo luận mấy bài contest khó nhằn. No cap, project này build để chạy mượt, dễ dùng và trông cũng khá là vibe.

## Có gì ở đây?
- **Algorithm Notebook**: Lưu mấy pattern Segment Tree, DFS/BFS, DP... gõ một lần xài mãi mãi.
- **Vibe UI**: Giao diện Apple-ish, sạch sẽ, không rườm rà. Quan trọng nhất là đã fix lag, chạy bao mượt.
- **Discussion**: Có chỗ để anh em vào cmt, hỏi trick, vote bài viết. 
- **Quiz**: Chỗ để test trình độ thuật toán của bản thân.

## Setup nhanh cho đỡ tốn thời gian
1. Create venv rồi cài lẹ requirements:
   ```bash
   python -m venv venv
   source venv/bin/activate # hoặc venv\Scripts\activate trên windows
   pip install -r requirements.txt
   ```
2. Config tí cho nó chạy:
   - Tạo file `config/local_settings.py` (copy cái đống trong `local_settings.py` mẫu ra).
   - Không cần dùng `.env` nữa cho mệt người.
3. Migrate db:
   ```bash
   python manage.py migrate
   ```
4. Ship it:
   ```bash
   python manage.py runserver
   ```

## Một vài note nhỏ cho dev
- Giao diện xài SCSS, muốn sửa thì vọc trong `static/scss`.
- Build CSS: `npm run build:css`.
- Config nhạy cảm thì cứ quăng vào `local_settings.py` nhé, đừng quăng lên git.

Peace out! ✌️
