class ArabicSlugConverter:
    # Includes:
    # - English letters/numbers
    # - Arabic unicode block \u0600-\u06FF
    # - Hyphens and underscores
    regex = r"[-\w\u0600-\u06FF]+"

    def to_python(self, value):
        return value

    def to_url(self, value):
        return value
