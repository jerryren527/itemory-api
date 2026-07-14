from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from .models import CustomUser


class CustomUserCreationForm(forms.ModelForm):
    """
    Form for creating new users in Django admin.
    """
    # the PasswordInput widget renders <input type="password"> in HTML.
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(
        label="Confirm password", widget=forms.PasswordInput)

    # Configurations.
    class Meta:
        model = CustomUser
        # Specifies that these fields from CustomUser model should be included on the form. password1 and password2 are added manually and are not part of the model itself.
        fields = ("email",)

    # Django automatically calls methods named "clean_<fieldname>()" when cleaning form data.
    def clean_password2(self):
        # self.cleaned_data is an instance attribute to the form object, self. self.cleaned_data is defined and initialized with data from the form fields when full_clean() is called in Django's BaseForm class. self.cleaned_data is accessible in your code like so:
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return p2

    # Override the default save behavior of ModelForm.
    def save(self, commit=True):
        # Calls the parent ModelForm's save(), but with commit=False. This creates the CustomUser model instance but does not save it to the database yet.
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.has_password = True  # because admin-created users MUST have passwords

        if commit:
            # Include this check for 'if commit:' in instances where you need to perform an action on the model instances after it's been created from the form's data but before it is saved to the database. E.g., adding a field that wasn't on the form to the model instance before saving it to the databse.
            user.save()
        return user


class CustomUserChangeForm(forms.ModelForm):
    """
    Form for updating users in Django admin.
    """
    password = ReadOnlyPasswordHashField(label="Password")

    class Meta:
        model = CustomUser
        fields = (
            "email",
            "password",
            "has_password",
            "google_account_linked",
            "google_sub",
            "google_picture_url",
            "is_active",
            "is_staff",
            "is_superuser",
        )
