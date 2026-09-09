"""KP restrictions for requests authenticated with an Open WebUI API key."""

from fastapi import HTTPException, status


def is_api_key_request(request) -> bool:
    # Set only after authentication; never infer this from client metadata.
    return getattr(request.state, 'auth_type', None) == 'api_key'


def check_api_key_path(request) -> None:
    # These routes expose knowledge content or administer executable filters.
    # Apply this independently of the configurable API-key endpoint allowlist.
    restricted_paths = (
        '/api/v1/knowledge',
        '/api/v1/retrieval',
        '/api/v1/files',
        '/api/v1/functions',
        '/api/v1/pipelines',
    )
    path = request.scope['path']
    if any(path == prefix or path.startswith(prefix + '/') for prefix in restricted_paths):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Knowledge, files, and filters are not available with API keys.',
        )
