from django import forms


class ContactForm(forms.Form):
    name = forms.CharField(max_length=120)
    email = forms.EmailField()
    subject = forms.CharField(max_length=200, required=False)
    message = forms.CharField(max_length=5000, widget=forms.Textarea(attrs={'rows': 7}))
    # Hidden from people by CSS. Automated spam tends to fill in every field.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}))
