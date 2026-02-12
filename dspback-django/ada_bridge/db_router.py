"""Database router for ADA read-only models."""


class AdaDatabaseRouter:
    """Route unmanaged ADA models to the 'ada' database."""

    ADA_LABELS = {"ada_bridge"}
    ADA_MODELS = {"adajsontable", "adarecord"}

    def db_for_read(self, model, **hints):
        if model._meta.model_name in self.ADA_MODELS:
            return "ada"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.model_name in self.ADA_MODELS:
            return "ada"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # Never migrate ADA models — they are unmanaged
        if model_name in self.ADA_MODELS:
            return False
        # Don't migrate catalog models to the ada database
        if db == "ada":
            return False
        return None
