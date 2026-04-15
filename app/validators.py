import re
from django.core.exceptions import ValidationError
# from django.utils.translation import gettext as _


class ComplexPasswordValidator:
    def validate(self, password, user=None):
        # At least one uppercase letter
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                ("This password must contain at least one uppercase letter."),
                code='password_no_upper',
            )
        # At least one number
        if not re.search(r'\d', password):
            raise ValidationError(
                ("This password must contain at least one number."),
                code='password_no_number',
            )
        # At least one special character
        if not re.search(r'[^A-Za-z0-9]', password):
            raise ValidationError(
                ("This password must contain at least one special character."),
                code='password_no_special',
            )

    # def get_help_text(self):
    #     return (
    #         "Your password must contain at least one uppercase letter, "
    #         "one number, and one special character."
    #     )
