"""
Forms for the wiki application.
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from martor.fields import MartorFormField
from martor.widgets import MartorWidget

from .models import (
    Article, Category, Comment, Profile,
    UploadedFile, Question, Choice
)

User = get_user_model()


class SignUpForm(UserCreationForm):
    """Form for user registration."""
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        """Metadata for the SignUpForm."""
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            'username': 'Tên đăng nhập',
            'first_name': 'Tên',
            'last_name': 'Họ',
            'email': 'Email',
            'password1': 'Mật khẩu',
            'password2': 'Nhập lại mật khẩu',
        }
        for name, field in self.fields.items():
            field.widget.attrs.update({
                'class': 'form-control form-control-lg',
                'placeholder': placeholders.get(name, ''),
            })


class LoginForm(AuthenticationForm):
    """Form for user login."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class UserUpdateForm(forms.ModelForm):
    """Form for updating basic user information."""
    class Meta:
        """Metadata for the UserUpdateForm."""
        model = User
        fields = ('first_name', 'last_name', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class ProfileForm(forms.ModelForm):
    """Form for updating user profile."""
    class Meta:
        """Metadata for the ProfileForm."""
        model = Profile
        fields = (
            'display_name', 'bio', 'avatar',
            'is_profile_private', 'show_email_publicly'
        )
        widgets = {
            'bio': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Chia sẻ một chút về lĩnh vực bạn đang học...'
            }),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
            'is_profile_private': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
            'show_email_publicly': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['display_name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Tên hiển thị',
        })
        self.fields['is_profile_private'].help_text = (
            'Khi bật, người khác sẽ chỉ thấy trạng thái hồ sơ riêng tư.'
        )
        self.fields['show_email_publicly'].help_text = (
            'Email chỉ hiển thị cho người khác khi hồ sơ đang ở chế độ công khai.'
        )


class CategoryForm(forms.ModelForm):
    """Form for creating/updating categories."""
    class Meta:
        """Metadata for the CategoryForm."""
        model = Category
        fields = ('name', 'slug', 'description')
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control',
                'placeholder': 'Mô tả ngắn cho danh mục'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Ví dụ: Thuật toán đồ thị',
        })
        self.fields['slug'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'thuat-toan-do-thi',
        })


class ArticleForm(forms.ModelForm):
    """Form for creating/updating articles."""
    change_summary = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tóm tắt các thay đổi của bạn (không bắt buộc)...',
        })
    )
    content = MartorFormField(
        widget=MartorWidget(attrs={
            'class': 'form-control',
            'placeholder': (
                '# Tiêu đề ghi chú\n\n'
                'Mô tả ý tưởng, độ phức tạp, ví dụ code...'
            ),
        })
    )

    class Meta:
        """Metadata for the ArticleForm."""
        model = Article
        fields = (
            'title', 'slug', 'category',
            'allow_comments', 'content', 'change_summary'
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Ví dụ: Segment Tree cơ bản',
        })
        self.fields['slug'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'segment-tree-co-ban',
        })
        self.fields['slug'].help_text = (
            'Có thể để trống, hệ thống sẽ tự tạo từ tiêu đề.'
        )
        self.fields['category'].widget.attrs.update({'class': 'form-select'})
        self.fields['category'].required = False
        self.fields['category'].empty_label = 'Chưa phân loại'
        self.fields['category'].help_text = (
            'Có thể để trống, bài viết sẽ tự chuyển vào danh mục Chưa phân loại.'
        )
        self.fields['allow_comments'].widget.attrs.update({
            'class': 'form-check-input'
        })
        self.fields['allow_comments'].help_text = (
            'Bật để người dùng có quyền được phép bình luận dưới bài viết này.'
        )


class CommentForm(forms.ModelForm):
    """Form for adding comments."""
    captcha_answer = forms.IntegerField(
        label='Xác thực: bạn là người thật',
        required=True,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'placeholder': 'Nhập kết quả'}
        ),
    )
    content = MartorFormField(
        widget=MartorWidget(attrs={
            'class': 'form-control',
            'placeholder': (
                'Đặt câu hỏi, góp ý lời giải, hoặc bổ sung mẹo tối ưu...'
            ),
        })
    )

    class Meta:
        """Metadata for the CommentForm."""
        model = Comment
        fields = ('content',)


class UploadFileForm(forms.ModelForm):
    """Form for uploading files."""
    class Meta:
        """Metadata for the UploadFileForm."""
        model = UploadedFile
        fields = ('file', 'description')
        widgets = {
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Mô tả ngắn file (tùy chọn)'
            }),
        }

    def clean_file(self):
        """Validate uploaded file size."""
        file = self.cleaned_data.get('file')
        if file and file.size > 15 * 1024 * 1024:
            raise forms.ValidationError(
                'File quá lớn. Vui lòng upload tối đa 15MB.'
            )
        return file


class QuestionForm(forms.ModelForm):
    """Form for creating quiz questions."""
    content = MartorFormField(
        label='Nội dung câu hỏi',
        widget=MartorWidget(attrs={
            'class': 'form-control',
            'placeholder': 'Nội dung câu hỏi (hỗ trợ Markdown)...',
        })
    )
    explanation = MartorFormField(
        label='Giải thích đáp án',
        required=False,
        widget=MartorWidget(attrs={
            'class': 'form-control',
            'placeholder': (
                'Giải thích đáp án (sẽ hiển thị sau khi người dùng trả lời)...'
            ),
        })
    )

    class Meta:
        """Metadata for the QuestionForm."""
        model = Question
        fields = ('content', 'explanation', 'order')
        widgets = {
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Thứ tự ưu tiên hiển thị'
            }),
        }


class ChoiceForm(forms.ModelForm):
    """Form for quiz choices."""
    class Meta:
        """Metadata for the ChoiceForm."""
        model = Choice
        fields = ('content', 'is_correct')
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nhập nội dung lựa chọn...'
            }),
            'is_correct': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }


ChoiceFormSet = inlineformset_factory(
    Question, Choice, form=ChoiceForm,
    extra=4,
    can_delete=True
)
