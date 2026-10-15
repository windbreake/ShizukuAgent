"""Model IDs are routing keys; display names must never be role placeholders."""
PLACEHOLDER_NAMES = {'primary agent model', 'primary model', 'agent model', 'default model'}


def model_display_name(model):
    name = str(model.get('name') or '').strip()
    remote_id = str(model.get('model') or model.get('id') or '').strip()
    return remote_id if not name or name.casefold() in PLACEHOLDER_NAMES else name
