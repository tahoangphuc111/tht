"""
Configuration for the wiki application.
"""
from django.apps import AppConfig


class WikiConfig(AppConfig):
    """Configuration class for the wiki app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wiki'

    def ready(self):
        """Perform initialization when the app is ready."""
        # pylint: disable=import-outside-toplevel, unused-import
        from . import signals
