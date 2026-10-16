"""Message identity and reversible session boundaries, independent of LLM windows."""
import uuid
from copy import deepcopy


def fork(storage, thread, persona):
    """Copy visible history, retaining tool context but never source record ownership."""
    messages = deepcopy(visible(load(storage, thread, persona)))
    for message in messages:
        message['id'] = uuid.uuid4().hex
        message.pop('record_id', None)
    target = 's_' + uuid.uuid4().hex
    storage.save_checkpoint(target, persona, {'messages': messages})
    return target


def load(storage, thread, persona):
    checkpoint = storage.load_checkpoint(thread, persona) or {'messages': []}
    changed = False
    for message in checkpoint.get('messages', []):
        if not message.get('id'):
            message['id'] = uuid.uuid4().hex
            changed = True
    if changed:
        storage.save_checkpoint(thread, persona, checkpoint)
    return checkpoint


def visible(checkpoint):
    messages = checkpoint.get('messages') or []
    boundary = (checkpoint.get('revert') or {}).get('message_id')
    if boundary:
        index = next((i for i, message in enumerate(messages) if message['id'] == boundary), len(messages))
        return messages[:index]
    return messages


def revert(storage, thread, persona, message_id):
    checkpoint = load(storage, thread, persona)
    messages = checkpoint.get('messages') or []
    target = next((m for m in messages if m['id'] == message_id and m['role'] == 'user'), None)
    if target is None:
        raise ValueError('消息不存在于此会话，请重新加载会话')
    checkpoint['revert'] = {'message_id': message_id}
    checkpoint.pop('context',None)
    storage.save_checkpoint(thread, persona, checkpoint)
    return target['content'], visible(checkpoint)
