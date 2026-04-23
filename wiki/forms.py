"""
Forms for the wiki application.
"""

from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from martor.fields import MartorFormField
from martor.widgets import MartorWidget

from .models import (
    Article,
    Category,
    Choice,
    CodingExercise,
    CodingTestCase,
    Comment,
    Profile,
    Question,
    UploadedFile,
)

User = get_user_model()


class SignUpForm(UserCreationForm):
    """Form for user registration."""

    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        """Metadata for the SignUpForm."""

        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "username": "Tên đăng nhập",
            "first_name": "Tên",
            "last_name": "Họ",
            "email": "Email",
            "password1": "Mật khẩu",
            "password2": "Nhập lại mật khẩu",
        }
        for name, field in self.fields.items():
            field.widget.attrs.update(
                {
                    "class": "form-control form-control-lg",
                    "placeholder": placeholders.get(name, ""),
                }
            )


class LoginForm(AuthenticationForm):
    """Form for user login."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})


class UserUpdateForm(forms.ModelForm):
    """Form for updating basic user information."""

    class Meta:
        """Metadata for the UserUpdateForm."""

        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})


class ProfileForm(forms.ModelForm):
    """Form for updating user profile."""

    class Meta:
        """Metadata for the ProfileForm."""

        model = Profile
        fields = (
            "display_name",
            "bio",
            "avatar",
            "is_profile_private",
            "show_email_publicly",
        )
        widgets = {
            "bio": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-control",
                    "placeholder": "Chia sẻ một chút về lĩnh vực bạn đang học...",
                }
            ),
            "avatar": forms.FileInput(attrs={"class": "form-control"}),
            "is_profile_private": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "show_email_publicly": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Tên hiển thị",
            }
        )
        self.fields["is_profile_private"].help_text = (
            "Khi bật, người khác sẽ chỉ thấy trạng thái hồ sơ riêng tư."
        )
        self.fields["show_email_publicly"].help_text = (
            "Email chỉ hiển thị cho người khác khi hồ sơ đang ở chế độ công khai."
        )


class CategoryForm(forms.ModelForm):
    """Form for creating/updating categories."""

    class Meta:
        """Metadata for the CategoryForm."""

        model = Category
        fields = ("name", "slug", "description")
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-control",
                    "placeholder": "Mô tả ngắn cho danh mục",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Ví dụ: Thuật toán đồ thị",
            }
        )
        self.fields["slug"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "thuat-toan-do-thi",
            }
        )


class ArticleForm(forms.ModelForm):
    """Form for creating/updating articles."""

    change_summary = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tóm tắt các thay đổi của bạn (không bắt buộc)...",
            }
        ),
    )
    content = MartorFormField(
        widget=MartorWidget(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "# Tiêu đề ghi chú\n\n" "Mô tả ý tưởng, độ phức tạp, ví dụ code..."
                ),
            }
        )
    )

    class Meta:
        """Metadata for the ArticleForm."""

        model = Article
        fields = (
            "title",
            "slug",
            "category",
            "tags",
            "allow_comments",
            "content",
            "change_summary",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Gắn thẻ (ví dụ: segment-tree, dp, math)",
            }
        )
        self.fields["tags"].help_text = "Các thẻ cách nhau bằng dấu phẩy."
        self.fields["title"].widget.attrs.update(
            {
                "class": "form-control form-control-lg",
                "placeholder": "Ví dụ: Segment Tree cơ bản",
            }
        )
        self.fields["slug"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "segment-tree-co-ban",
            }
        )
        self.fields["slug"].help_text = (
            "Có thể để trống, hệ thống sẽ tự tạo từ tiêu đề."
        )
        self.fields["category"].widget.attrs.update({"class": "form-select"})
        self.fields["category"].required = False
        self.fields["category"].empty_label = "Chưa phân loại"
        self.fields["category"].help_text = (
            "Có thể để trống, bài viết sẽ tự chuyển vào danh mục Chưa phân loại."
        )
        self.fields["allow_comments"].widget.attrs.update({"class": "form-check-input"})
        self.fields["allow_comments"].help_text = (
            "Bật để người dùng có quyền được phép bình luận dưới bài viết này."
        )


class CommentForm(forms.ModelForm):
    """Form for adding comments."""

    content = MartorFormField(
        widget=MartorWidget(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Đặt câu hỏi, góp ý lời giải, hoặc bổ sung mẹo tối ưu..."
                ),
            }
        )
    )

    class Meta:
        """Metadata for the CommentForm."""

        model = Comment
        fields = ("content",)


class UploadFileForm(forms.ModelForm):
    """Form for uploading files."""

    class Meta:
        """Metadata for the UploadFileForm."""

        model = UploadedFile
        fields = ("file", "description")
        widgets = {
            "description": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Mô tả ngắn file (tùy chọn)",
                }
            ),
        }

    def clean_file(self):
        """Validate uploaded file size."""
        file = self.cleaned_data.get("file")
        if file and file.size > 15 * 1024 * 1024:
            raise forms.ValidationError("File quá lớn. Vui lòng upload tối đa 15MB.")
        return file


class QuestionForm(forms.ModelForm):
    """Form for creating quiz questions."""

    content = MartorFormField(
        label="Nội dung câu hỏi",
        widget=MartorWidget(
            attrs={
                "class": "form-control",
                "placeholder": "Nội dung câu hỏi (hỗ trợ Markdown)...",
            }
        ),
    )
    explanation = MartorFormField(
        label="Giải thích đáp án",
        required=False,
        widget=MartorWidget(
            attrs={
                "class": "form-control",
                "placeholder": (
                    "Giải thích đáp án (sẽ hiển thị sau khi người dùng trả lời)..."
                ),
            }
        ),
    )

    class Meta:
        """Metadata for the QuestionForm."""

        model = Question
        fields = ("content", "explanation", "order")
        widgets = {
            "order": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Thứ tự ưu tiên hiển thị",
                }
            ),
        }


class ChoiceForm(forms.ModelForm):
    """Form for quiz choices."""

    class Meta:
        """Metadata for the ChoiceForm."""

        model = Choice
        fields = ("content", "is_correct")
        widgets = {
            "content": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nhập nội dung lựa chọn...",
                }
            ),
            "is_correct": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


def get_code_language_choices():
    """Expose enabled judge languages as form choices."""
    configs = getattr(settings, "CODE_EXECUTION_LANGUAGE_CONFIGS", {})
    return [
        (key, cfg.get("label", key))
        for key, cfg in configs.items()
        if cfg.get("enabled")
    ]


class CodingExerciseForm(forms.ModelForm):
    """Form for configuring a coding exercise."""

    allowed_languages = forms.MultipleChoiceField(
        choices=(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        """Metadata for CodingExerciseForm."""

        model = CodingExercise
        fields = (
            "title",
            "description",
            "is_enabled",
            "allowed_languages",
            "default_language",
            "time_limit_ms",
            "memory_limit_mb",
            "compare_mode",
        )
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 5,
                    "class": "form-control",
                    "placeholder": "Mo ta bai tap code, yeu cau input/output...",
                }
            ),
            "is_enabled": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "default_language": forms.Select(attrs={"class": "form-select"}),
            "time_limit_ms": forms.NumberInput(attrs={"class": "form-control"}),
            "memory_limit_mb": forms.NumberInput(attrs={"class": "form-control"}),
            "compare_mode": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        language_choices = get_code_language_choices()
        self.fields["allowed_languages"].choices = language_choices
        self.fields["allowed_languages"].help_text = (
            "Chi cac ngon ngu duoc chon moi hien ra o Monaco."
        )
        self.fields["default_language"].choices = [
            ("", "Chon ngon ngu mac dinh")
        ] + language_choices
        self.fields["title"].widget.attrs.update(
            {"class": "form-control", "placeholder": "Vi du: In ra tong 2 so"}
        )

        starter_map = self.instance.starter_code_map if self.instance.pk else {}
        language_configs = getattr(settings, "CODE_EXECUTION_LANGUAGE_CONFIGS", {})
        for language_key, config in language_configs.items():
            field_name = f"starter_code_{language_key}"
            self.fields[field_name] = forms.CharField(
                required=False,
                label=f"Starter code - {config.get('label', language_key)}",
                widget=forms.Textarea(
                    attrs={
                        "rows": 8,
                        "class": "form-control font-monospace",
                        "placeholder": "Starter code cho ngon ngu nay",
                    }
                ),
                initial=starter_map.get(
                    language_key, config.get("starter_code", "")
                ),
            )

    def clean(self):
        """Ensure default language is part of the allowed set."""
        cleaned_data = super().clean()
        allowed_languages = cleaned_data.get("allowed_languages") or []
        default_language = cleaned_data.get("default_language")
        if default_language and default_language not in allowed_languages:
            self.add_error(
                "default_language", "Ngon ngu mac dinh phai nam trong danh sach cho phep."
            )
        if cleaned_data.get("is_enabled") and not allowed_languages:
            self.add_error(
                "allowed_languages", "Can chon it nhat mot ngon ngu khi bat bai tap code."
            )
        return cleaned_data

    def save(self, commit=True):
        """Persist starter codes as a JSON map."""
        instance = super().save(commit=False)
        starter_map = {}
        for language_key in getattr(settings, "CODE_EXECUTION_LANGUAGE_CONFIGS", {}):
            starter_value = self.cleaned_data.get(f"starter_code_{language_key}", "")
            if starter_value:
                starter_map[language_key] = starter_value
        instance.starter_code_map = starter_map
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class CodingTestCaseForm(forms.ModelForm):
    """Form for creating and editing coding exercise testcases."""

    class Meta:
        """Metadata for CodingTestCaseForm."""

        model = CodingTestCase
        fields = (
            "name",
            "input_text",
            "expected_output_text",
            "input_file",
            "expected_output_file",
            "is_sample",
            "order",
            "score",
        )
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "sample-1"}
            ),
            "input_text": forms.Textarea(
                attrs={
                    "rows": 6,
                    "class": "form-control font-monospace",
                    "placeholder": "Nhap input raw neu khong upload file",
                }
            ),
            "expected_output_text": forms.Textarea(
                attrs={
                    "rows": 6,
                    "class": "form-control font-monospace",
                    "placeholder": "Nhap output raw neu khong upload file",
                }
            ),
            "input_file": forms.FileInput(attrs={"class": "form-control"}),
            "expected_output_file": forms.FileInput(attrs={"class": "form-control"}),
            "is_sample": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "order": forms.NumberInput(attrs={"class": "form-control"}),
            "score": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        """Require either raw text or uploaded files for both sides."""
        cleaned_data = super().clean()
        if not (cleaned_data.get("input_text") or cleaned_data.get("input_file")):
            self.add_error("input_text", "Can input raw hoac file input.")
        if not (
            cleaned_data.get("expected_output_text")
            or cleaned_data.get("expected_output_file")
        ):
            self.add_error(
                "expected_output_text", "Can output raw hoac file output."
            )
        return cleaned_data


ChoiceFormSet = inlineformset_factory(
    Question, Choice, form=ChoiceForm, extra=4, can_delete=True
)
