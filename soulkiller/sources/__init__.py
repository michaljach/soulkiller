"""Registry: folder under data/raw/  ->  ingest function(cfg, root)."""
from . import calendar, files, git, gmail, google_extras, meta_chats, social, telegram, whatsapp

# Google Takeout is unpacked once into raw/google/Takeout/... and several parsers read from it.
SOURCES = {
    "gmail":     ("google", gmail.ingest),
    "calendar":  ("google", calendar.ingest),
    "drive":     ("google", files.drive),
    "lifelog":   ("google", google_extras.ingest),
    "messenger": ("facebook", meta_chats.messenger),
    "facebook":  ("facebook", social.facebook_posts),
    "instagram": ("instagram", meta_chats.instagram),
    "whatsapp":  ("whatsapp", whatsapp.ingest),
    "telegram":  ("telegram", telegram.ingest),
    "twitter":   ("twitter", social.twitter),
    "reddit":    ("reddit", social.reddit),
    "linkedin":  ("linkedin", social.linkedin),
    "notes":     ("notes", files.notes),
    "git":       ("git", git.ingest),
}
