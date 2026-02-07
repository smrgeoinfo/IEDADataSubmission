from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class OrcidSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Populate the custom User.orcid field from the social login UID."""

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.orcid = sociallogin.account.uid
        # Use ORCID as username to satisfy the unique constraint
        user.username = sociallogin.account.uid
        return user

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        # Store the access token for potential API calls
        token = sociallogin.token
        if token:
            user.orcid_access_token = token.token
            user.save(update_fields=["orcid_access_token"])
        return user
