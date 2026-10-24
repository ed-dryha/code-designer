"""Single entry point for the grammar pack: configure cache, gate downloads."""
import tree_sitter_language_pack as tslp


class GrammarUnavailable(Exception):
    def __init__(self, language, reason, detail=""):
        super().__init__(f"{language}: {reason} {detail}".strip())
        self.language = language
        self.reason = reason


def open_pack(cache_dir, allow_download=False):
    """Configure the pack with cache_dir (must precede any parser call)."""
    tslp.configure(tslp.PackConfig(cache_dir=str(cache_dir)))
    return Pack(allow_download)


class Pack:
    def __init__(self, allow_download):
        self.allow_download = allow_download

    def load(self, language):
        """Return (parser, tree_sitter Language) or raise GrammarUnavailable."""
        if language not in tslp.downloaded_languages():
            if not self.allow_download:
                raise GrammarUnavailable(language, "no-grammar", "not in cache; run setup or --allow-download")
            try:
                tslp.download([language])
            except tslp.DownloadError as e:
                raise GrammarUnavailable(language, "download-failed", str(e)[:200])
            # ChecksumMismatchError intentionally not caught: hard failure.
        try:
            return tslp.get_parser(language), tslp.get_language(language)
        except tslp.DownloadError as e:
            raise GrammarUnavailable(language, "download-failed", str(e)[:200])
        except tslp.LanguageNotFoundError as e:
            raise GrammarUnavailable(language, "no-grammar", str(e)[:200])
