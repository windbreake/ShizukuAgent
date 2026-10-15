"""Shared advertised and enforced mode policy."""
READ_ONLY = {'read_file', 'list_dir', 'search_memory', 'add_memory', 'todowrite', 'todoread', 'list_skills', 'list_mcp_tools'}
SANDBOX_BLOCKED = {'run_local_agent', 'run_skill', 'call_mcp'}

def allowed(name, mode):
    if mode == 'chat':
        return name in READ_ONLY
    if mode == 'sandbox':
        return name not in SANDBOX_BLOCKED
    return True
