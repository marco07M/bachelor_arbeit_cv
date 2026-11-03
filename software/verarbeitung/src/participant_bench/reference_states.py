"""Reference assessability is decided from reference evidence, never model output."""


def reference_state(person, field, config):
    explicit = getattr(person, "field_states", {}).get(field)
    value = getattr(person, field)
    if field == "user_id" and value and not config.usable_id(value) and explicit not in ("unknown", "illegible", "uncertain"):
        return "masked"
    if explicit:
        return explicit
    return "read" if value.strip() else "unknown"


def assessable_reference(person, field, config):
    return reference_state(person, field, config) == "read"
